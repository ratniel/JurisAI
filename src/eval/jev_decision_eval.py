"""Offline comparison of Jev decisions with the existing agentic classifier."""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Annotated, Any, Literal
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from pydantic import BaseModel, Field

from src.agentic.intent_classifier import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    UserIntentClassifier,
    _build_classifier_prompt,
)
from src.agentic.models import PrimaryIntent, SessionSnapshot
from src.config.settings import settings
from src.eval.agentic_workflow_eval import (
    DEFAULT_RUNS_ROOT,
    write_agentic_workflow_run_artifact,
)
from src.eval.retrieval_eval import _select_records
from src.llm import build_generation_client
from src.llm.providers import GenerationProviderName

QUESTIONS = {
    "primary_intent": {
        "type": "choice",
        "instructions": "Classify this user turn for a public-benefits and government-schemes assistant.",
        "criteria": {
            PrimaryIntent.SCHEME_DISCOVERY.value: "Asks about benefits, subsidies, scholarships, aid, welfare, or eligibility.",
            PrimaryIntent.FOLLOW_UP.value: "Continues a prior scheme conversation in the supplied session context.",
            PrimaryIntent.PROFILE_UPDATE.value: "Main purpose is sharing or correcting profile details.",
            PrimaryIntent.GENERAL_QUESTION.value: "A broad product or help question about the assistant.",
            PrimaryIntent.SMALL_TALK.value: "Greetings, thanks, or social conversation without a substantive request.",
            PrimaryIntent.OUT_OF_SCOPE.value: "A substantive request unrelated to the assistant's domain.",
        },
    },
    "needs_clarification": {
        "type": "choice",
        "instructions": "Would routing this turn be materially better with one more question? Use only the supplied message and session context.",
        "criteria": {
            "yes": "Missing or ambiguous context materially prevents choosing a useful next action.",
            "no": "Can usefully retrieve schemes or respond now; optional profile details need not block this.",
        },
    },
}

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: Probability
    probabilities: dict[str, Probability]


class JevResponse(BaseModel):
    model: str = Field(min_length=1)
    answers: dict[str, ChoiceAnswer]
    usage: dict[str, Annotated[int, Field(ge=0, strict=True)]]


def validate_jev_response(payload: Any) -> dict[str, Any]:
    response = JevResponse.model_validate(payload)
    if set(response.answers) != set(QUESTIONS):
        raise ValueError("Jev must answer both decision questions")
    for name, answer in response.answers.items():
        if set(answer.probabilities) != set(QUESTIONS[name]["criteria"]):
            raise ValueError(f"Unexpected Jev options for {name}")
        if answer.choice not in answer.probabilities:
            raise ValueError(f"Unknown Jev choice for {name}")
        if not math.isclose(sum(answer.probabilities.values()), 1.0, abs_tol=1e-5):
            raise ValueError(f"Jev probabilities must sum to one for {name}")
        if answer.probabilities[answer.choice] < max(answer.probabilities.values()):
            raise ValueError(f"Jev choice must have maximum probability for {name}")
    return response.model_dump(mode="json")


def call_jev(request: dict[str, Any], api_key: str) -> dict[str, Any]:
    http_request = Request(
        "https://api.typesafe.ai/v1/systemone",
        data=json.dumps(request).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    # One attempt: record failures without hiding retries in the latency measurement.
    with urlopen(http_request, timeout=30) as response:
        return validate_jev_response(json.load(response))


def decision_metrics(records: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for field in QUESTIONS:
        paired = [r for r in records if r["baseline"]["output"] and r["jev"]["output"]]
        metrics[field] = {
            "paired_count": len(paired),
            "agreement_rate": mean(
                r["baseline"]["decisions"][field] == r["jev"]["decisions"][field]
                for r in paired
            ) if paired else None,
        }
        for provider in ("baseline", "jev"):
            labeled = [r for r in records if r["expected"][field] is not None]
            scored = [r for r in labeled if r[provider]["output"]]
            confident = [
                r for r in scored
                if r[provider]["confidence"].get(field) is not None
                and r[provider]["confidence"][field] >= threshold
            ]
            metrics[field][provider] = {
                "labeled_count": len(labeled),
                "scored_count": len(scored),
                "accuracy": mean(
                    r[provider]["decisions"][field] == r["expected"][field]
                    for r in scored
                ) if scored else None,
                "confident_labeled_count": len(confident),
                "confident_wrong_count": sum(
                    r[provider]["decisions"][field] != r["expected"][field]
                    for r in confident
                ) if scored and (provider == "jev" or field == "primary_intent") else None,
            }
    for provider in ("baseline", "jev"):
        successful = [r[provider]["latency_seconds"] for r in records if r[provider]["output"]]
        metrics[provider] = {
            "error_count": sum(r[provider]["error"] is not None for r in records),
            "successful_count": len(successful),
            "median_latency_seconds": median(successful) if successful else None,
        }
    return metrics


def run_jev_decision_eval(
    *,
    dry_run: bool = False,
    record_ids: list[str] | None = None,
    intent_provider: GenerationProviderName | None = None,
    intent_model: str | None = None,
    jev_model: str = "jev-latest",
    confidence_threshold: float = 0.8,
) -> dict[str, Any]:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between zero and one")
    records = _select_records(record_ids)
    if not records:
        raise ValueError("No golden records selected")
    api_key = os.environ.get("TYPESAFE_API_KEY") or dotenv_values(".env").get("TYPESAFE_API_KEY")
    if not dry_run and not api_key:
        raise ValueError("Set TYPESAFE_API_KEY in the environment or .env, or use --dry-run")
    provider = intent_provider or settings.workflow.intent_provider
    model = intent_model or settings.workflow.intent_model
    client = None if dry_run else build_generation_client(provider=provider, model=model)
    classifier = None if dry_run else UserIntentClassifier(llm=client, provider=provider, model=model)
    started_at = datetime.now(UTC)
    stamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    output_path = DEFAULT_RUNS_ROOT / f"agentic_workflow_eval_jev_decisions_{stamp}.json"
    summary: dict[str, Any] = {
        "eval_mode": "jev_decisions_dry_run" if dry_run else "jev_decisions",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "output_path": str(output_path),
        "record_count": len(records),
        "selected_record_ids": [r.record_id for r in records],
        "intent_provider": provider,
        "intent_model": model,
        "jev_model": jev_model,
        "confidence_threshold": confidence_threshold,
        "questions": QUESTIONS,
        "baseline_system_prompt": INTENT_CLASSIFIER_SYSTEM_PROMPT,
        "records": [],
    }
    try:
        for record in records:
            snapshot = SessionSnapshot(chat_session_id=record.record_id)
            state = _build_classifier_prompt(
                user_message=record.user_query,
                session_memory=snapshot.to_session_memory(),
            )
            row: dict[str, Any] = {
                "record_id": record.record_id,
                "user_query": record.user_query,
                "expected": {
                    "primary_intent": record.expected_primary_intent,
                    "needs_clarification": record.expected_needs_clarification,
                },
                "jev_request": {"state": state, "model": jev_model, "questions": QUESTIONS},
            }
            for name in ("baseline", "jev"):
                result: dict[str, Any] = {
                    "output": None, "decisions": {}, "confidence": {},
                    "latency_seconds": None, "error": None,
                }
                row[name] = result
                if dry_run:
                    continue
                start = perf_counter()
                history_start = len(getattr(client, "invocation_history", []))
                try:
                    if name == "baseline":
                        assert classifier is not None
                        output = classifier.classify(user_message=record.user_query, session_snapshot=snapshot)
                        result["output"] = output.model_dump(mode="json")
                        result["decisions"] = {
                            "primary_intent": output.primary_intent.value,
                            "needs_clarification": output.needs_clarification,
                        }
                        result["confidence"] = {"primary_intent": output.confidence}
                    else:
                        assert api_key is not None
                        response = call_jev(row["jev_request"], api_key)
                        result["output"] = response
                        result["decisions"] = {
                            "primary_intent": response["answers"]["primary_intent"]["choice"],
                            "needs_clarification": response["answers"]["needs_clarification"]["choice"] == "yes",
                        }
                        result["confidence"] = {k: v["confidence"] for k, v in response["answers"].items()}
                except Exception as exc:
                    # Do not persist provider error bodies, which may echo credentials or input.
                    result["error"] = {"type": type(exc).__name__, "http_status": getattr(exc, "code", None)}
                finally:
                    result["latency_seconds"] = perf_counter() - start
                    if name == "baseline":
                        result["invocations"] = [
                            {k: item.get(k) for k in ("requested_model", "response_model", "usage", "attempt", "outcome")}
                            for item in getattr(client, "invocation_history", [])[history_start:]
                        ]
            summary["records"].append(row)
        summary["completed_at"] = datetime.now(UTC).isoformat()
    finally:
        summary["evaluated_record_count"] = len(summary["records"])
        summary["metrics"] = decision_metrics(summary["records"], confidence_threshold)
        summary["classifier_error_count"] = sum(
            bool(r["baseline"]["error"] or r["jev"]["error"]) for r in summary["records"]
        )
        write_agentic_workflow_run_artifact(summary, output_path)
    return summary
