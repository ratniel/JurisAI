from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterator

from opentelemetry import trace

from src.agentic.fact_utils import aggregate_intent_facts
from src.agentic.intent_classifier import UserIntentClassifier
from src.config.settings import settings
from src.eval.filter_signals import (
    build_effective_filter_signals,
    filters_match_expected,
)
from src.eval.quality_gates import (
    ABSOLUTE_RETRIEVAL_GATE_NAME,
    ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS,
    evaluate_summary_against_thresholds,
    record_passes_absolute_gate,
    record_passes_min_recall,
)
from src.eval.retrieval_dataset import load_golden_records
from src.observability import configure_phoenix_tracing
from src.retrieval import QdrantSchemeSearchClient, build_retrieval_intent_profile
from src.llm import build_generation_client
from src.llm.providers import GenerationProviderName

TRACER = trace.get_tracer(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "evals" / "retrieval" / "runs"


def reciprocal_rank(results: list[str], positives: set[str], limit: int) -> float:
    for index, scheme_id in enumerate(results[:limit], start=1):
        if scheme_id in positives:
            return 1.0 / index
    return 0.0


def default_run_output_path(*, started_at: datetime | None = None) -> Path:
    timestamp = (started_at or datetime.now(tz=UTC)).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_RUNS_ROOT / f"retrieval_eval_{timestamp}.json"


def write_run_artifact(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(summary)
    payload["output_path"] = str(output_path)
    serialized = json.dumps(payload, indent=2)
    output_path.write_text(serialized, encoding="utf-8")
    (output_path.parent / "latest.json").write_text(serialized, encoding="utf-8")


def _trace_id_hex() -> str | None:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context or not context.is_valid:
        return None
    return f"{context.trace_id:032x}"


def _flush_tracing() -> None:
    tracer_provider = trace.get_tracer_provider()
    method = getattr(tracer_provider, "force_flush", None)
    if callable(method):
        method()


def _raw_filters_from_classifier(classification: Any) -> dict[str, Any]:
    return aggregate_intent_facts(classification.retrieval_filters)


def _select_records(record_ids: list[str] | None = None) -> list[Any]:
    records = load_golden_records()
    if not record_ids:
        return records

    requested_ids = [record_id.strip() for record_id in record_ids if record_id.strip()]
    requested_set = set(requested_ids)
    selected = [record for record in records if record.record_id in requested_set]
    selected_ids = {record.record_id for record in selected}
    missing_ids = [record_id for record_id in requested_ids if record_id not in selected_ids]
    if missing_ids:
        raise ValueError(
            "Unknown retrieval eval record_id(s): " + ", ".join(missing_ids)
        )

    # Preserve the user-requested order instead of the file order.
    by_id = {record.record_id: record for record in selected}
    return [by_id[record_id] for record_id in requested_ids]


def _build_summary(
    *,
    started_at: datetime,
    completed_at: datetime | None,
    output_path: Path | None,
    collection_name: str,
    include_debug: bool,
    limit: int,
    trace_project: str,
    trace_status: dict[str, Any],
    run_trace_id: str | None,
    per_record: list[dict[str, Any]],
    recall_at_3_scores: list[float],
    recall_at_5_scores: list[float],
    mrr_at_5_scores: list[float],
    distractor_scores: list[float],
    filter_match_scores: list[float],
    zero_raw_hit_failures: list[float],
    min_recall_passes: list[float],
    strict_record_passes: list[float],
    classifier_error_record_ids: list[str],
    record_count: int,
    selected_record_ids: list[str] | None,
    intent_provider: str | None = None,
    intent_model: str | None = None,
    generation_provider: str | None = None,
    generation_model: str | None = None,
) -> dict[str, Any]:
    summary = {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "output_path": str(output_path) if output_path else None,
        "eval_mode": "retrieval_core",
        "record_count": record_count,
        "collection_name": collection_name,
        "collection": collection_name,
        "use_classifier": True,
        "used_classifier": True,
        "include_debug": include_debug,
        "limit": limit,
        "selected_record_ids": selected_record_ids or [],
        "intent_provider": intent_provider or settings.workflow.intent_provider,
        "intent_model": intent_model or settings.workflow.intent_model,
        "generation_provider": generation_provider or settings.workflow.generation_provider,
        "generation_model": generation_model or settings.workflow.generation_model,
        "trace_project": trace_project,
        "trace_status": trace_status,
        "run_trace_id": run_trace_id,
        "classifier_error_count": len(classifier_error_record_ids),
        "classifier_fallback_record_ids": classifier_error_record_ids,
        "avg_recall_at_3": mean(recall_at_3_scores) if recall_at_3_scores else 0.0,
        "avg_recall_at_5": mean(recall_at_5_scores) if recall_at_5_scores else 0.0,
        "avg_mrr_at_5": mean(mrr_at_5_scores) if mrr_at_5_scores else 0.0,
        "distractor_pass_rate": mean(distractor_scores) if distractor_scores else 0.0,
        "expected_filter_match_rate": (
            mean(filter_match_scores) if filter_match_scores else 0.0
        ),
        "zero_raw_hit_rate": (
            mean(zero_raw_hit_failures) if zero_raw_hit_failures else 0.0
        ),
        "per_record_min_recall_pass_rate": (
            mean(min_recall_passes) if min_recall_passes else 0.0
        ),
        "strict_record_pass_rate": (
            mean(strict_record_passes) if strict_record_passes else 0.0
        ),
        "absolute_gate_name": ABSOLUTE_RETRIEVAL_GATE_NAME,
        "absolute_gate_thresholds": ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS,
        "records": per_record,
    }
    summary["absolute_gate_failures"] = evaluate_summary_against_thresholds(
        summary=summary,
        thresholds=ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS,
    )
    summary["passes_absolute_gate"] = not summary["absolute_gate_failures"]
    return summary


def iter_retrieval_eval(
    *,
    limit: int,
    collection_name: str,
    include_debug: bool = False,
    fail_on_classifier_error: bool = False,
    intent_provider: GenerationProviderName | None = None,
    intent_model: str | None = None,
    generation_provider: GenerationProviderName | None = None,
    generation_model: str | None = None,
    trace_project: str = settings.phoenix.project_name,
    phoenix_endpoint: str | None = settings.phoenix.collector_endpoint,
    output_path: Path | None = None,
    persist_artifact: bool = False,
    record_ids: list[str] | None = None,
) -> Iterator[tuple[dict[str, Any], dict[str, Any], int, int]]:
    trace_config = configure_phoenix_tracing(
        project_name=trace_project,
        endpoint=phoenix_endpoint or None,
    )
    trace_status = {
        "enabled": trace_config.enabled,
        "detail": trace_config.detail,
    }
    records = _select_records(record_ids)
    resolved_intent_provider = intent_provider or settings.workflow.intent_provider
    resolved_intent_model = intent_model or settings.workflow.intent_model
    resolved_generation_provider = (
        generation_provider or settings.workflow.generation_provider
    )
    resolved_generation_model = generation_model or settings.workflow.generation_model
    classifier = UserIntentClassifier(
        llm=build_generation_client(
            provider=resolved_intent_provider,
            model=resolved_intent_model,
        ),
        provider=resolved_intent_provider,
        model=resolved_intent_model,
    )
    retriever = QdrantSchemeSearchClient(collection_name=collection_name)
    started_at = datetime.now(tz=UTC)

    per_record: list[dict[str, Any]] = []
    recall_at_3_scores: list[float] = []
    recall_at_5_scores: list[float] = []
    mrr_at_5_scores: list[float] = []
    distractor_scores: list[float] = []
    filter_match_scores: list[float] = []
    zero_raw_hit_failures: list[float] = []
    min_recall_passes: list[float] = []
    strict_record_passes: list[float] = []
    classifier_error_record_ids: list[str] = []

    resolved_output_path = output_path or default_run_output_path(started_at=started_at)
    run_trace_id: str | None = None
    final_summary: dict[str, Any] | None = None
    last_record_result: dict[str, Any] | None = None

    with TRACER.start_as_current_span("jurisai.retrieval_eval.run") as run_span:
        run_trace_id = _trace_id_hex()
        run_span.set_attribute("jurisai.eval.record_count", len(records))
        run_span.set_attribute("jurisai.eval.collection", collection_name)
        run_span.set_attribute("jurisai.eval.use_classifier", True)
        run_span.set_attribute("jurisai.eval.trace_project", trace_project)

        for index, record in enumerate(records, start=1):
            with TRACER.start_as_current_span("jurisai.retrieval_eval.record") as record_span:
                record_trace_id = _trace_id_hex()
                record_span.set_attribute("jurisai.eval.record_id", record.record_id)
                record_span.set_attribute("jurisai.eval.persona_id", record.persona_id)

                classification_payload: dict[str, Any] | None = None
                classifier_error: str | None = None
                retrieval_query: str | None = None
                raw_filters: dict[str, Any] = {}
                used_classifier_for_record = False

                try:
                    classification = classifier.classify(user_message=record.user_query)
                    classification_payload = classification.model_dump(
                        mode="json",
                        exclude_none=True,
                    )
                    retrieval_query = classification.retrieval_query
                    raw_filters = _raw_filters_from_classifier(classification)
                    used_classifier_for_record = True
                except Exception as exc:  # noqa: BLE001
                    if fail_on_classifier_error:
                        raise
                    classifier_error = str(exc)
                    classifier_error_record_ids.append(record.record_id)
                    record_span.set_attribute(
                        "jurisai.eval.classifier_error",
                        classifier_error[:500],
                    )

                intent_profile = build_retrieval_intent_profile(
                    user_message=record.user_query,
                    retrieval_query=retrieval_query,
                    raw_filters=raw_filters,
                )
                retrieval = retriever.search(
                    query_text=intent_profile.normalized_query,
                    raw_filters=intent_profile.filters,
                    intent_profile=intent_profile,
                    limit=limit,
                    include_debug=include_debug,
                )

                result_ids = [str(item["scheme_id"]) for item in retrieval["results"]]
                positives = set(record.must_retrieve_scheme_ids)
                distractors = set(record.must_not_retrieve_scheme_ids)
                hits_at_3 = len([scheme_id for scheme_id in result_ids[:3] if scheme_id in positives])
                hits_at_5 = len([scheme_id for scheme_id in result_ids[:5] if scheme_id in positives])
                recall_at_3 = hits_at_3 / len(positives)
                recall_at_5 = hits_at_5 / len(positives)
                mrr_at_5 = reciprocal_rank(result_ids, positives, 5)
                distractor_pass = 1.0 if not distractors.intersection(result_ids[:5]) else 0.0
                raw_hit_count = int(retrieval["raw_hit_count"])
                actual_filters = intent_profile.filters.model_dump(exclude_none=True)
                effective_eval_filters = build_effective_filter_signals(
                    actual_filters=actual_filters,
                    query_tags=intent_profile.query_tags,
                    query_topics=intent_profile.query_topics,
                )
                filter_match = 1.0 if filters_match_expected(
                    expected_filters=record.expected_filters,
                    actual_filters=actual_filters,
                    query_tags=intent_profile.query_tags,
                    query_topics=intent_profile.query_topics,
                ) else 0.0
                min_recall_pass = 1.0 if record_passes_min_recall(
                    hits_at_k=hits_at_5,
                    min_recall_at_k=record.min_recall_at_k,
                ) else 0.0
                strict_record_pass = 1.0 if record_passes_absolute_gate(
                    raw_hit_count=raw_hit_count,
                    hits_at_k=hits_at_5,
                    min_recall_at_k=record.min_recall_at_k,
                    distractor_pass=bool(distractor_pass),
                    filter_match=bool(filter_match),
                ) else 0.0

                record_span.set_attribute("jurisai.eval.raw_hit_count", raw_hit_count)
                record_span.set_attribute("jurisai.eval.returned_count", len(result_ids))
                record_span.set_attribute("jurisai.eval.recall_at_5", recall_at_5)
                record_span.set_attribute("jurisai.eval.distractor_pass", bool(distractor_pass))

                recall_at_3_scores.append(recall_at_3)
                recall_at_5_scores.append(recall_at_5)
                mrr_at_5_scores.append(mrr_at_5)
                distractor_scores.append(distractor_pass)
                filter_match_scores.append(filter_match)
                zero_raw_hit_failures.append(1.0 if raw_hit_count == 0 else 0.0)
                min_recall_passes.append(min_recall_pass)
                strict_record_passes.append(strict_record_pass)

                record_result = {
                    "record_id": record.record_id,
                    "persona_id": record.persona_id,
                    "trace_id": record_trace_id,
                    "eval_mode": "retrieval_core",
                    "intent_provider": resolved_intent_provider,
                    "intent_model": resolved_intent_model,
                    "user_query": record.user_query,
                    "expected_filters": record.expected_filters,
                    "required_query_terms": record.required_query_terms,
                    "must_retrieve_scheme_ids": record.must_retrieve_scheme_ids,
                    "must_not_retrieve_scheme_ids": record.must_not_retrieve_scheme_ids,
                    "notes": record.notes,
                    "classification": classification_payload,
                    "classifier_error": classifier_error,
                    "used_classifier": used_classifier_for_record,
                    "retrieval_query": retrieval_query,
                    "normalized_query": intent_profile.normalized_query,
                    "embed_query": intent_profile.normalized_query,
                    "query_topics": intent_profile.query_topics,
                    "query_tags": intent_profile.query_tags,
                    "query_terms": intent_profile.query_terms,
                    "actual_filters": actual_filters,
                    "effective_eval_filters": effective_eval_filters,
                    "applied_filters": retrieval["applied_filters"],
                    "ignored_filters": {
                        **intent_profile.ignored_filters,
                        **retrieval["ignored_filters"],
                    },
                    "raw_hit_count": raw_hit_count,
                    "results": retrieval["results"],
                    "retrieved_scheme_ids": result_ids,
                    "min_recall_at_k": record.min_recall_at_k,
                    "recall_at_3": recall_at_3,
                    "recall_at_5": recall_at_5,
                    "mrr_at_5": mrr_at_5,
                    "min_recall_pass": bool(min_recall_pass),
                    "distractor_pass": bool(distractor_pass),
                    "expected_filter_match": bool(filter_match),
                    "strict_record_pass": bool(strict_record_pass),
                    "debug": retrieval.get("debug") or {},
                }
                per_record.append(record_result)
                last_record_result = record_result

                final_summary = _build_summary(
                    started_at=started_at,
                    completed_at=None,
                    output_path=resolved_output_path,
                    collection_name=collection_name,
                    include_debug=include_debug,
                    limit=limit,
                    trace_project=trace_project,
                    trace_status=trace_status,
                    run_trace_id=run_trace_id,
                    per_record=per_record,
                    recall_at_3_scores=recall_at_3_scores,
                    recall_at_5_scores=recall_at_5_scores,
                    mrr_at_5_scores=mrr_at_5_scores,
                    distractor_scores=distractor_scores,
                    filter_match_scores=filter_match_scores,
                    zero_raw_hit_failures=zero_raw_hit_failures,
                    min_recall_passes=min_recall_passes,
                    strict_record_passes=strict_record_passes,
                    classifier_error_record_ids=classifier_error_record_ids,
                    record_count=len(records),
                    selected_record_ids=record_ids,
                    intent_provider=resolved_intent_provider,
                    intent_model=resolved_intent_model,
                    generation_provider=resolved_generation_provider,
                    generation_model=resolved_generation_model,
                )
                yield final_summary, record_result, index, len(records)

    completed_at = datetime.now(tz=UTC)
    if final_summary is None:
        final_summary = _build_summary(
            started_at=started_at,
            completed_at=completed_at,
            output_path=resolved_output_path,
            collection_name=collection_name,
            include_debug=include_debug,
            limit=limit,
            trace_project=trace_project,
            trace_status=trace_status,
            run_trace_id=run_trace_id,
            per_record=[],
            recall_at_3_scores=[],
            recall_at_5_scores=[],
            mrr_at_5_scores=[],
            distractor_scores=[],
            filter_match_scores=[],
            zero_raw_hit_failures=[],
            min_recall_passes=[],
            strict_record_passes=[],
            classifier_error_record_ids=[],
            record_count=0,
            selected_record_ids=record_ids,
            intent_provider=resolved_intent_provider,
            intent_model=resolved_intent_model,
            generation_provider=resolved_generation_provider,
            generation_model=resolved_generation_model,
        )
    else:
        final_summary = _build_summary(
            started_at=started_at,
            completed_at=completed_at,
            output_path=resolved_output_path,
            collection_name=collection_name,
            include_debug=include_debug,
            limit=limit,
            trace_project=trace_project,
            trace_status=trace_status,
            run_trace_id=run_trace_id,
            per_record=per_record,
            recall_at_3_scores=recall_at_3_scores,
            recall_at_5_scores=recall_at_5_scores,
            mrr_at_5_scores=mrr_at_5_scores,
            distractor_scores=distractor_scores,
            filter_match_scores=filter_match_scores,
            zero_raw_hit_failures=zero_raw_hit_failures,
            min_recall_passes=min_recall_passes,
            strict_record_passes=strict_record_passes,
            classifier_error_record_ids=classifier_error_record_ids,
            record_count=len(records),
            selected_record_ids=record_ids,
            intent_provider=resolved_intent_provider,
            intent_model=resolved_intent_model,
            generation_provider=resolved_generation_provider,
            generation_model=resolved_generation_model,
        )

    if persist_artifact:
        write_run_artifact(final_summary, resolved_output_path)
    _flush_tracing()
    yield final_summary, last_record_result or {}, len(records), len(records)


def run_retrieval_eval(
    *,
    limit: int,
    collection_name: str,
    include_debug: bool = False,
    fail_on_classifier_error: bool = False,
    intent_provider: GenerationProviderName | None = None,
    intent_model: str | None = None,
    generation_provider: GenerationProviderName | None = None,
    generation_model: str | None = None,
    trace_project: str = settings.phoenix.project_name,
    phoenix_endpoint: str | None = settings.phoenix.collector_endpoint,
    output_path: Path | None = None,
    persist_artifact: bool = True,
    record_ids: list[str] | None = None,
) -> dict[str, Any]:
    final_summary: dict[str, Any] | None = None
    for final_summary, _, _, _ in iter_retrieval_eval(
        limit=limit,
        collection_name=collection_name,
        include_debug=include_debug,
        fail_on_classifier_error=fail_on_classifier_error,
        intent_provider=intent_provider,
        intent_model=intent_model,
        generation_provider=generation_provider,
        generation_model=generation_model,
        trace_project=trace_project,
        phoenix_endpoint=phoenix_endpoint,
        output_path=output_path,
        persist_artifact=False,
        record_ids=record_ids,
    ):
        pass

    if final_summary is None:
        final_summary = _build_summary(
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            output_path=output_path or default_run_output_path(),
            collection_name=collection_name,
            include_debug=include_debug,
            limit=limit,
            trace_project=trace_project,
            trace_status={"enabled": False, "detail": "No records were evaluated."},
            run_trace_id=None,
            per_record=[],
            recall_at_3_scores=[],
            recall_at_5_scores=[],
            mrr_at_5_scores=[],
            distractor_scores=[],
            filter_match_scores=[],
            zero_raw_hit_failures=[],
            min_recall_passes=[],
            strict_record_passes=[],
            classifier_error_record_ids=[],
            record_count=0,
            selected_record_ids=record_ids,
            intent_provider=intent_provider or settings.workflow.intent_provider,
            intent_model=intent_model or settings.workflow.intent_model,
            generation_provider=generation_provider or settings.workflow.generation_provider,
            generation_model=generation_model or settings.workflow.generation_model,
        )

    if output_path is not None:
        resolved_output_path = output_path
    elif final_summary and final_summary.get("output_path"):
        resolved_output_path = Path(final_summary["output_path"])
    else:
        resolved_output_path = default_run_output_path()
    final_summary["output_path"] = str(resolved_output_path)
    if persist_artifact:
        write_run_artifact(final_summary, resolved_output_path)
    return final_summary
