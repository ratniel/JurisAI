from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from opentelemetry import trace

from src.agentic.intent_classifier import UserIntentClassifier
from src.agentic.models import AgenticTurnResult, SessionSnapshot
from src.agentic.workflow import BasicAgenticWorkflow
from src.config.settings import settings
from src.eval.filter_signals import (
    build_effective_filter_signals,
    filters_match_expected,
)
from src.eval.quality_gates import (
    record_passes_absolute_gate,
    record_passes_min_recall,
)
from src.eval.retrieval_eval import (
    _build_summary,
    _flush_tracing,
    _select_records,
    _span_id_hex,
    _trace_id_hex,
    reciprocal_rank,
    refresh_run_log,
    write_run_artifact,
)
from src.llm import build_generation_client
from src.llm.providers import EmbeddingProviderName, GenerationProviderName

TRACER = trace.get_tracer(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "evals" / "agentic_workflow" / "runs"
AGENTIC_WORKFLOW_RUN_ARTIFACT_PREFIX = "agentic_workflow_eval_"


class AgenticWorkflowRunError(RuntimeError):
    def __init__(self, message: str, llm_invocations: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.llm_invocations = llm_invocations


def default_agentic_workflow_output_path(
    *,
    started_at: datetime | None = None,
) -> Path:
    timestamp = (started_at or datetime.now(tz=UTC)).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_RUNS_ROOT / f"agentic_workflow_eval_{timestamp}.json"


def write_agentic_workflow_run_artifact(
    summary: dict[str, Any],
    output_path: Path,
) -> None:
    write_run_artifact(summary, output_path)
    if output_path.name.startswith(AGENTIC_WORKFLOW_RUN_ARTIFACT_PREFIX):
        refresh_run_log(
            output_path.parent,
            artifact_prefix=AGENTIC_WORKFLOW_RUN_ARTIFACT_PREFIX,
        )


def _client_invocations(
    client: Any,
    *,
    structured_stage: str,
    text_stage: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for metadata in getattr(client, "invocation_history", []):
        stage = (
            structured_stage
            if metadata.get("operation") == "structured_generation"
            else text_stage
        )
        records.append({"stage": stage, **metadata})
    return records


def _annotate_workflow_summary(summary: dict[str, Any]) -> None:
    records = summary.get("records") or []
    failure_ids = [
        record["record_id"]
        for record in records
        if not record.get("workflow_succeeded")
    ]
    summary["retrieval_strategy"] = summary.get("retrieval_strategy") or settings.workflow.retrieval_strategy
    summary["workflow_failure_record_ids"] = failure_ids
    summary["workflow_failure_count"] = len(failure_ids)
    summary["nonempty_answer_count"] = sum(
        bool(str(record.get("final_answer") or "").strip())
        for record in records
    )


def _classification_query_value(classification: Any, field_name: str) -> str | None:
    value = getattr(classification, field_name, None)
    if value:
        return str(value)
    return None


def _collect_actual_filters(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    actual_filters: dict[str, Any] = {}
    topics: list[str] = []
    for tool_call in tool_calls:
        input_payload = tool_call.get("input_payload", {})
        state = input_payload.get("state")
        if state and "state" not in actual_filters:
            actual_filters["state"] = state
        topics.extend(input_payload.get("topics") or [])
    deduped_topics = list(dict.fromkeys(topics))
    if deduped_topics:
        actual_filters["topics"] = deduped_topics
    actual_filters["tags"] = []
    return actual_filters


def _flatten_debug_profiles(tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("tool_name") or "tool"
        debug_payload = (tool_call.get("output_payload") or {}).get("debug") or {}
        for profile in debug_payload.get("profiles") or []:
            profile_name = profile.get("embedding_profile") or "unknown"
            profiles.append(
                {
                    "embedding_profile": f"{tool_name}:{profile_name}",
                    "query_text": profile.get("query_text"),
                    "raw_hit_count": profile.get("raw_hit_count", 0),
                    "raw_hits": profile.get("raw_hits") or [],
                }
            )
    return {"profiles": profiles}


async def _run_agentic_turn_async(
    *,
    user_message: str,
    collection_name: str,
    intent_provider: GenerationProviderName,
    intent_model: str,
    generation_provider: GenerationProviderName,
    generation_model: str,
    embedding_backend: EmbeddingProviderName,
    embedding_model: str,
    retrieval_filters_enabled: bool,
    retrieval_filter_mode: str,
    retrieval_strategy: str,
) -> AgenticTurnResult:
    from src.retrieval import QdrantSchemeSearchClient

    generation_llm = build_generation_client(
        provider=generation_provider,
        model=generation_model,
    )
    intent_llm = build_generation_client(
        provider=intent_provider,
        model=intent_model,
    )
    workflow = BasicAgenticWorkflow(
        llm=generation_llm,
        classifier=UserIntentClassifier(
            llm=intent_llm,
            provider=intent_provider,
            model=intent_model,
        ),
        retriever=QdrantSchemeSearchClient(
            collection_name=collection_name,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
        ),
        include_retrieval_debug=True,
        retrieval_filters_enabled=retrieval_filters_enabled,
        retrieval_filter_mode=retrieval_filter_mode,
        retrieval_strategy=retrieval_strategy,
    )
    try:
        result = await workflow.run(
            user_message=user_message,
            session_snapshot=SessionSnapshot().model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        invocations = _client_invocations(
            intent_llm,
            structured_stage="intent_classification",
            text_stage="intent_classification",
        ) + _client_invocations(
            generation_llm,
            structured_stage="retrieval_planning",
            text_stage="answer_generation",
        )
        raise AgenticWorkflowRunError(
            f"{type(exc).__name__}: {exc}",
            invocations,
        ) from exc

    turn_result = AgenticTurnResult.model_validate(result)
    invocations = _client_invocations(
        intent_llm,
        structured_stage="intent_classification",
        text_stage="intent_classification",
    ) + _client_invocations(
        generation_llm,
        structured_stage="retrieval_planning",
        text_stage="answer_generation",
    )
    return turn_result.model_copy(
        update={
            "decision": turn_result.decision.model_copy(
                update={
                    "tool_payload": {
                        **turn_result.decision.tool_payload,
                        "llm_invocations": invocations,
                    }
                }
            )
        }
    )


def _run_agentic_turn(
    *,
    user_message: str,
    collection_name: str,
    intent_provider: GenerationProviderName,
    intent_model: str,
    generation_provider: GenerationProviderName,
    generation_model: str,
    embedding_backend: EmbeddingProviderName,
    embedding_model: str,
    retrieval_filters_enabled: bool,
    retrieval_filter_mode: str,
    retrieval_strategy: str,
) -> AgenticTurnResult:
    return asyncio.run(
        _run_agentic_turn_async(
            user_message=user_message,
            collection_name=collection_name,
            intent_provider=intent_provider,
            intent_model=intent_model,
            generation_provider=generation_provider,
            generation_model=generation_model,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            retrieval_filters_enabled=retrieval_filters_enabled,
            retrieval_filter_mode=retrieval_filter_mode,
            retrieval_strategy=retrieval_strategy,
        )
    )


def iter_agentic_workflow_eval(
    *,
    limit: int,
    collection_name: str,
    include_debug: bool = False,
    fail_on_classifier_error: bool = False,
    intent_provider: GenerationProviderName | None = None,
    intent_model: str | None = None,
    generation_provider: GenerationProviderName | None = None,
    generation_model: str | None = None,
    embedding_backend: EmbeddingProviderName | None = None,
    embedding_model: str | None = None,
    trace_project: str = settings.phoenix.project_name,
    phoenix_endpoint: str | None = settings.phoenix.collector_endpoint,
    output_path: Path | None = None,
    persist_artifact: bool = False,
    record_ids: list[str] | None = None,
    retrieval_filters_enabled: bool | None = None,
    retrieval_filter_mode: str | None = None,
    retrieval_strategy: str | None = None,
) -> Iterator[tuple[dict[str, Any], dict[str, Any], int, int]]:
    from src.observability import configure_phoenix_tracing

    trace_config = configure_phoenix_tracing(
        project_name=trace_project,
        endpoint=phoenix_endpoint or None,
    )
    trace_status = {
        "enabled": trace_config.enabled,
        "detail": trace_config.detail,
    }
    resolved_intent_provider = intent_provider or settings.workflow.intent_provider
    resolved_intent_model = intent_model or settings.workflow.intent_model
    resolved_generation_provider = (
        generation_provider or settings.workflow.generation_provider
    )
    resolved_generation_model = generation_model or settings.workflow.generation_model
    resolved_embedding_backend = embedding_backend or settings.embeddings.backend
    resolved_embedding_model = embedding_model or settings.embedding_model(
        resolved_embedding_backend
    )
    resolved_retrieval_filters_enabled = (
        settings.workflow.retrieval_filters_enabled
        if retrieval_filters_enabled is None
        else retrieval_filters_enabled
    )
    resolved_retrieval_filter_mode = (
        settings.workflow.retrieval_filter_mode
        if retrieval_filter_mode is None
        else retrieval_filter_mode
    )
    resolved_retrieval_strategy = retrieval_strategy or settings.workflow.retrieval_strategy
    records = _select_records(record_ids)
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

    resolved_output_path = output_path or default_agentic_workflow_output_path(
        started_at=started_at
    )
    run_trace_id: str | None = None
    run_span_id: str | None = None
    final_summary: dict[str, Any] | None = None
    last_record_result: dict[str, Any] | None = None
    completed_normally = False

    try:
        with TRACER.start_as_current_span("jurisai.agentic_workflow_eval.run") as run_span:
            run_trace_id = _trace_id_hex()
            run_span_id = _span_id_hex()
            run_span.set_attribute("jurisai.eval.record_count", len(records))
            run_span.set_attribute("jurisai.eval.collection", collection_name)
            run_span.set_attribute("jurisai.eval.use_classifier", True)
            run_span.set_attribute("jurisai.eval.trace_project", trace_project)

            for index, record in enumerate(records, start=1):
                with TRACER.start_as_current_span(
                    "jurisai.agentic_workflow_eval.record"
                ) as record_span:
                    record_trace_id = _trace_id_hex()
                    record_span_id = _span_id_hex()
                    record_span.set_attribute("jurisai.eval.record_id", record.record_id)
                    record_span.set_attribute("jurisai.eval.persona_id", record.persona_id)
    
                    workflow_result: AgenticTurnResult | None = None
                    classifier_error: str | None = None
                    llm_invocations: list[dict[str, Any]] = []
    
                    try:
                        workflow_result = _run_agentic_turn(
                            user_message=record.user_query,
                            collection_name=collection_name,
                            intent_provider=resolved_intent_provider,
                            intent_model=resolved_intent_model,
                            generation_provider=resolved_generation_provider,
                            generation_model=resolved_generation_model,
                            embedding_backend=resolved_embedding_backend,
                            embedding_model=resolved_embedding_model,
                            retrieval_filters_enabled=resolved_retrieval_filters_enabled,
                            retrieval_filter_mode=resolved_retrieval_filter_mode,
                            retrieval_strategy=resolved_retrieval_strategy,
                        )
                    except Exception as exc:  # noqa: BLE001
                        if fail_on_classifier_error:
                            raise
                        classifier_error = str(exc)
                        llm_invocations = list(
                            getattr(exc, "llm_invocations", [])
                        )
                        classifier_error_record_ids.append(record.record_id)
                        record_span.set_attribute(
                            "jurisai.eval.workflow_error",
                            classifier_error[:500],
                        )
    
                    if workflow_result is None:
                        classification_payload = None
                        retrieval_query = None
                        fit_query = None
                        query_topics: list[str] = []
                        query_tags: list[str] = []
                        query_terms: list[str] = []
                        actual_filters = {"tags": [], "topics": []}
                        applied_filters: dict[str, Any] = {}
                        ignored_filters: dict[str, Any] = {}
                        raw_hit_count = 0
                        results: list[dict[str, Any]] = []
                        workflow_trace: list[dict[str, Any]] = []
                        final_answer = None
                        used_classifier_for_record = False
                        debug_payload = {"profiles": []}
                    else:
                        classification_payload = workflow_result.classification.model_dump(
                            mode="json",
                            exclude_none=True,
                        )
                        tool_payload = workflow_result.decision.tool_payload
                        llm_invocations = list(tool_payload.get("llm_invocations") or [])
                        tool_calls = list(tool_payload.get("tool_calls") or [])
                        results = list(tool_payload.get("retrieved_schemes") or [])[:limit]
                        retrieval_query = _classification_query_value(
                            workflow_result.classification,
                            "discovery_query",
                        ) or _classification_query_value(
                            workflow_result.classification,
                            "retrieval_query",
                        )
                        fit_query = _classification_query_value(
                            workflow_result.classification,
                            "fit_query",
                        )
                        query_topics = list(tool_payload.get("query_topics") or [])
                        query_tags = list(tool_payload.get("query_tags") or [])
                        query_terms = list(tool_payload.get("query_terms") or [])
                        actual_filters = _collect_actual_filters(tool_calls)
                        applied_filters = dict(tool_payload.get("applied_filters") or {})
                        ignored_filters = dict(tool_payload.get("ignored_filters") or {})
                        raw_hit_count = int(tool_payload.get("raw_hit_count") or 0)
                        retrieval_filters_enabled_for_record = bool(
                            tool_payload.get(
                                "retrieval_filters_enabled",
                                resolved_retrieval_filters_enabled,
                            )
                        )
                        retrieval_filter_mode_for_record = str(
                            tool_payload.get(
                                "retrieval_filter_mode",
                                resolved_retrieval_filter_mode,
                            )
                        )
                        candidate_filters = dict(tool_payload.get("candidate_filters") or {})
                        workflow_trace = [
                            step.model_dump(mode="json", exclude_none=True)
                            for step in workflow_result.workflow_trace
                        ]
                        final_answer = workflow_result.decision.response
                        used_classifier_for_record = True
                        debug_payload = (
                            _flatten_debug_profiles(tool_calls) if include_debug else {"profiles": []}
                        )
                    if workflow_result is None:
                        retrieval_filters_enabled_for_record = resolved_retrieval_filters_enabled
                        retrieval_filter_mode_for_record = resolved_retrieval_filter_mode
                        candidate_filters = {}
    
                    result_ids = [str(item["scheme_id"]) for item in results]
                    positives = set(record.must_retrieve_scheme_ids)
                    distractors = set(record.must_not_retrieve_scheme_ids)
                    hits_at_3 = len(
                        [scheme_id for scheme_id in result_ids[:3] if scheme_id in positives]
                    )
                    hits_at_5 = len(
                        [scheme_id for scheme_id in result_ids[:5] if scheme_id in positives]
                    )
                    recall_at_3 = hits_at_3 / len(positives)
                    recall_at_5 = hits_at_5 / len(positives)
                    mrr_at_5 = reciprocal_rank(result_ids, positives, 5)
                    distractor_pass = (
                        1.0 if not distractors.intersection(result_ids[:5]) else 0.0
                    )
                    effective_eval_filters = build_effective_filter_signals(
                        actual_filters=actual_filters,
                        query_tags=query_tags,
                        query_topics=query_topics,
                    )
                    filter_match = 1.0 if filters_match_expected(
                        expected_filters=record.expected_filters,
                        actual_filters=actual_filters,
                        query_tags=query_tags,
                        query_topics=query_topics,
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
                    record_span.set_attribute(
                        "jurisai.eval.distractor_pass",
                        bool(distractor_pass),
                    )
    
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
                        "span_id": record_span_id,
                        "user_query": record.user_query,
                        "expected_filters": record.expected_filters,
                        "required_query_terms": record.required_query_terms,
                        "must_retrieve_scheme_ids": record.must_retrieve_scheme_ids,
                        "must_not_retrieve_scheme_ids": record.must_not_retrieve_scheme_ids,
                        "notes": record.notes,
                        "classification": classification_payload,
                        "classifier_error": classifier_error,
                        "workflow_error": classifier_error,
                        "workflow_succeeded": bool(
                            workflow_result is not None
                            and str(final_answer or "").strip()
                        ),
                        "used_classifier": used_classifier_for_record,
                        "retrieval_query": retrieval_query,
                        "normalized_query": retrieval_query,
                        "embed_query": retrieval_query,
                        "fit_query": fit_query,
                        "retrieval_filters_enabled": retrieval_filters_enabled_for_record,
                        "retrieval_filter_mode": retrieval_filter_mode_for_record,
                        "retrieval_strategy": resolved_retrieval_strategy,
                        "candidate_filters": candidate_filters,
                        "query_topics": query_topics,
                        "query_tags": query_tags,
                        "query_terms": query_terms,
                        "actual_filters": actual_filters,
                        "effective_eval_filters": effective_eval_filters,
                        "applied_filters": applied_filters,
                        "ignored_filters": ignored_filters,
                        "raw_hit_count": raw_hit_count,
                        "results": results,
                        "retrieved_scheme_ids": result_ids,
                        "min_recall_at_k": record.min_recall_at_k,
                        "recall_at_3": recall_at_3,
                        "recall_at_5": recall_at_5,
                        "mrr_at_5": mrr_at_5,
                        "min_recall_pass": bool(min_recall_pass),
                        "distractor_pass": bool(distractor_pass),
                        "expected_filter_match": bool(filter_match),
                        "strict_record_pass": bool(strict_record_pass),
                        "debug": debug_payload,
                        "workflow_trace": workflow_trace,
                        "final_answer": final_answer,
                        "llm_invocations": llm_invocations,
                        "selected_response_models": list(
                            dict.fromkeys(
                                str(item["response_model"])
                                for item in llm_invocations
                                if item.get("response_model")
                            )
                        ),
                        "eval_mode": "agentic_workflow",
                        "intent_provider": resolved_intent_provider,
                        "intent_model": resolved_intent_model,
                        "generation_provider": resolved_generation_provider,
                        "generation_model": resolved_generation_model,
                        "embedding_backend": resolved_embedding_backend,
                        "embedding_model": resolved_embedding_model,
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
                        run_span_id=run_span_id,
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
                        embedding_backend=resolved_embedding_backend,
                        embedding_model=resolved_embedding_model,
                        retrieval_filters_enabled=resolved_retrieval_filters_enabled,
                        retrieval_filter_mode=resolved_retrieval_filter_mode,
                        retrieval_strategy=resolved_retrieval_strategy,
                    )
                    final_summary["eval_mode"] = "agentic_workflow"
                    _annotate_workflow_summary(final_summary)
                    yield final_summary, record_result, index, len(records)

        completed_at = datetime.now(tz=UTC)
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
            run_span_id=run_span_id,
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
            record_count=len(records) if records else 0,
            selected_record_ids=record_ids,
            intent_provider=resolved_intent_provider,
            intent_model=resolved_intent_model,
            generation_provider=resolved_generation_provider,
            generation_model=resolved_generation_model,
            embedding_backend=resolved_embedding_backend,
            embedding_model=resolved_embedding_model,
            retrieval_filters_enabled=resolved_retrieval_filters_enabled,
            retrieval_filter_mode=resolved_retrieval_filter_mode,
            retrieval_strategy=resolved_retrieval_strategy,
        )
        final_summary["eval_mode"] = "agentic_workflow"
        _annotate_workflow_summary(final_summary)
        completed_normally = True
        yield final_summary, last_record_result or {}, len(records), len(records)
    finally:
        if not completed_normally:
            completed_at = datetime.now(tz=UTC)
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
                run_span_id=run_span_id,
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
                record_count=len(records) if records else 0,
                selected_record_ids=record_ids,
                intent_provider=resolved_intent_provider,
                intent_model=resolved_intent_model,
                generation_provider=resolved_generation_provider,
                generation_model=resolved_generation_model,
                embedding_backend=resolved_embedding_backend,
                embedding_model=resolved_embedding_model,
                retrieval_filters_enabled=resolved_retrieval_filters_enabled,
                retrieval_filter_mode=resolved_retrieval_filter_mode,
                retrieval_strategy=resolved_retrieval_strategy,
            )
            final_summary["eval_mode"] = "agentic_workflow"
            _annotate_workflow_summary(final_summary)
        if persist_artifact and final_summary is not None:
            write_agentic_workflow_run_artifact(final_summary, resolved_output_path)
        _flush_tracing()


def run_agentic_workflow_eval(
    *,
    limit: int,
    collection_name: str,
    include_debug: bool = False,
    fail_on_classifier_error: bool = False,
    intent_provider: GenerationProviderName | None = None,
    intent_model: str | None = None,
    generation_provider: GenerationProviderName | None = None,
    generation_model: str | None = None,
    embedding_backend: EmbeddingProviderName | None = None,
    embedding_model: str | None = None,
    trace_project: str = settings.phoenix.project_name,
    phoenix_endpoint: str | None = settings.phoenix.collector_endpoint,
    output_path: Path | None = None,
    persist_artifact: bool = True,
    record_ids: list[str] | None = None,
    retrieval_filters_enabled: bool | None = None,
    retrieval_filter_mode: str | None = None,
    retrieval_strategy: str | None = None,
) -> dict[str, Any]:
    final_summary: dict[str, Any] | None = None
    for final_summary, _, _, _ in iter_agentic_workflow_eval(
        limit=limit,
        collection_name=collection_name,
        include_debug=include_debug,
        fail_on_classifier_error=fail_on_classifier_error,
        intent_provider=intent_provider,
        intent_model=intent_model,
        generation_provider=generation_provider,
        generation_model=generation_model,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
        trace_project=trace_project,
        phoenix_endpoint=phoenix_endpoint,
        output_path=output_path,
        persist_artifact=False,
        record_ids=record_ids,
        retrieval_filters_enabled=retrieval_filters_enabled,
        retrieval_filter_mode=retrieval_filter_mode,
        retrieval_strategy=retrieval_strategy,
    ):
        pass

    if final_summary is None:
        final_summary = _build_summary(
            started_at=datetime.now(tz=UTC),
            completed_at=datetime.now(tz=UTC),
            output_path=output_path or default_agentic_workflow_output_path(),
            collection_name=collection_name,
            include_debug=include_debug,
            limit=limit,
            trace_project=trace_project,
            trace_status={"enabled": False, "detail": "No records were evaluated."},
            run_trace_id=None,
            run_span_id=None,
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
            embedding_backend=embedding_backend or settings.embeddings.backend,
            embedding_model=embedding_model or settings.embedding_model(
                embedding_backend or settings.embeddings.backend
            ),
            retrieval_filters_enabled=(
                settings.workflow.retrieval_filters_enabled
                if retrieval_filters_enabled is None
                else retrieval_filters_enabled
            ),
            retrieval_strategy=retrieval_strategy or settings.workflow.retrieval_strategy,
            retrieval_filter_mode=(
                settings.workflow.retrieval_filter_mode
                if retrieval_filter_mode is None
                else retrieval_filter_mode
            ),
        )
    final_summary["eval_mode"] = "agentic_workflow"
    _annotate_workflow_summary(final_summary)

    if output_path is not None:
        resolved_output_path = output_path
    elif final_summary.get("output_path"):
        resolved_output_path = Path(final_summary["output_path"])
    else:
        resolved_output_path = default_agentic_workflow_output_path()
    final_summary["output_path"] = str(resolved_output_path)

    if persist_artifact:
        write_agentic_workflow_run_artifact(final_summary, resolved_output_path)
    return final_summary
