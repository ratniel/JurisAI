from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from uuid import uuid4

from bson import ObjectId
from opentelemetry import trace
from pymongo import AsyncMongoClient

from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step

from src.agentic.fact_utils import aggregate_intent_facts
from src.agentic.intent_classifier import UserIntentClassifier
from src.agentic.models import (
    AgenticTurnResult,
    GroundingPack,
    GroundingSchemeCard,
    IntentClassifiedEvent,
    IntentFact,
    NextAction,
    OrchestratorDecision,
    PrimaryIntent,
    RelevantScheme,
    RetrievalPlan,
    RetrievalPlannedEvent,
    RetrievalToolCall,
    RetrievalToolName,
    ResponseRequestedEvent,
    RetrievedScheme,
    SchemeRef,
    SessionMemory,
    SessionSnapshot,
    TopSchemeArtifactEntry,
    TopSchemesArtifact,
    WorkflowAnswerDeltaEvent,
    WorkflowArtifactReadyEvent,
    WorkflowTraceStep,
    ToolSelectionEvent,
    UserIntentClassification,
    WorkflowStatusEvent,
)
from src.agentic.retrieval_planner import RetrievalToolPlanner
from src.config.settings import settings
from src.data_ingestion.enrichment_pipeline import build_enriched_scheme
from src.llm import TextGenerationClient, build_generation_client
from src.retrieval import QdrantSchemeSearchClient
from src.retrieval.query_intent import build_retrieval_intent_profile
from src.scheme_contracts import normalize_text, normalize_topics

TRACER = trace.get_tracer(__name__)

REPLY_SYSTEM_PROMPT = """
You are JurisAI, a concise and careful public-benefits assistant.
Reply in plain language.
Treat the original user message as authoritative. Session summaries, retrieval rank, and retrieval metadata are derived context and must not override or narrow it.
If the orchestrator wants clarification, ask only one focused question.
If retrieval results are provided, ground the answer only in those schemes.
Treat retrieved schemes as candidates, not recommendations. Compare each scheme's stated purpose and mandatory eligibility conditions with the user's actual need before presenting it as a fit.
Distinguish materially different purposes such as a recurring pension, a one-time marriage gift, a business-startup loan, business-expansion support, training, and market access.
Do not present a scheme as relevant if its state or eligibility clearly contradicts an explicit user constraint.
When a required eligibility fact is unknown, explain the scheme conditionally (for example, "you may qualify if...") and name the fact that still needs confirmation. Never turn an unknown into an eligibility claim.
If important filters were ignored or no grounded scheme matches all explicit constraints, say so plainly.
If no suitable scheme is found, say so plainly and suggest one focused next detail that would improve retrieval.
Match the language and script of the user's message. Answer Hinglish in natural Hinglish, Hindi in Hindi, and English in English unless the user asks otherwise.
When citing results, include a short References section with scheme names and URLs when available.
""".strip()


def facts_to_dict(facts: list[IntentFact]) -> dict[str, str]:
    return {fact.key: fact.value for fact in facts}


def is_enriched_collection(collection_name: str | None) -> bool:
    return collection_name in {
        settings.mongo.schemes_enriched_collection,
        settings.mongo.test_schemes_enriched_collection,
    }


def preferred_hydration_collections(collection_name: str | None) -> tuple[str, ...]:
    resolved_collection = collection_name or settings.schemes_collection
    if resolved_collection == settings.mongo.test_schemes_collection:
        return (
            settings.mongo.test_schemes_enriched_collection,
            settings.mongo.test_schemes_collection,
        )
    if resolved_collection == settings.mongo.schemes_collection:
        return (
            settings.mongo.schemes_enriched_collection,
            settings.mongo.schemes_collection,
        )
    return (resolved_collection,)


def build_relevant_scheme_from_lookup_document(
    *,
    document: dict[str, Any],
    collection_name: str | None,
    scheme: RetrievedScheme,
) -> RelevantScheme:
    if is_enriched_collection(collection_name):
        return RelevantScheme.from_mongo_document(document, scheme)

    enriched_document = build_enriched_scheme(document)
    return RelevantScheme.from_mongo_document(
        enriched_document.model_dump(by_alias=True),
        scheme,
    )


def coerce_retrieval_plan(
    *,
    plan: RetrievalPlan | None,
    default_query: str,
    default_fit_query: str | None = None,
) -> RetrievalPlan:
    if plan is None:
        return RetrievalPlan()

    tool_calls: list[RetrievalToolCall] = []
    for call in plan.tool_calls[:3]:
        query = normalize_text(call.query) or default_query
        fit_query = normalize_text(call.fit_query) or default_fit_query or query
        tool_calls.append(
            call.model_copy(
                update={
                    "query": query,
                    "fit_query": fit_query,
                    "state": normalize_text(call.state),
                    "topics": normalize_topics(call.topics),
                    "reasoning": normalize_text(call.reasoning),
                }
            )
        )

    return RetrievalPlan(
        rationale=normalize_text(plan.rationale) or "",
        tool_calls=tool_calls,
    )


def fallback_retrieval_plan(
    *,
    user_message: str,
    classification: UserIntentClassification,
    session_snapshot: SessionSnapshot,
) -> RetrievalPlan:
    raw_filters = {
        **session_snapshot.user_profile,
        **aggregate_intent_facts(classification.retrieval_filters),
    }
    intent_profile = build_retrieval_intent_profile(
        user_message=user_message,
        retrieval_query=classification.discovery_query or classification.retrieval_query,
        fit_query=classification.fit_query,
        raw_filters=raw_filters,
    )
    base_query = intent_profile.discovery_query
    fit_query = intent_profile.fit_query
    tool_calls: list[RetrievalToolCall] = []

    if intent_profile.filters.state:
        tool_calls.append(
            RetrievalToolCall(
                tool_name=RetrievalToolName.STATE_SCOPED_SEARCH,
                query=base_query,
                fit_query=fit_query,
                state=intent_profile.filters.state,
                topics=list(intent_profile.filters.topics),
                reasoning="State constraint is explicit or strongly implied.",
            )
        )

    if intent_profile.filters.topics:
        tool_calls.append(
            RetrievalToolCall(
                tool_name=RetrievalToolName.TOPIC_SCOPED_SEARCH,
                query=base_query,
                fit_query=fit_query,
                state=intent_profile.filters.state,
                topics=list(intent_profile.filters.topics),
                reasoning="Topic intent is explicit enough to warrant a scoped lookup.",
            )
        )

    if not tool_calls:
        tool_calls.append(
            RetrievalToolCall(
                tool_name=RetrievalToolName.SEMANTIC_SEARCH,
                query=base_query,
                fit_query=fit_query,
                reasoning="Fallback to broad semantic search.",
            )
        )

    return RetrievalPlan(
        rationale="Deterministic fallback plan used after planner output was empty or unavailable.",
        tool_calls=tool_calls,
    )


def merge_retrieved_scheme_results(
    tool_calls: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    best_by_scheme: dict[str, RetrievedScheme] = {}

    for tool_call in tool_calls:
        for item in tool_call.get("output_payload", {}).get("retrieved_schemes", []):
            candidate = RetrievedScheme.model_validate(item)
            current = best_by_scheme.get(candidate.scheme_id)
            if current is None or candidate.match_score > current.match_score:
                best_by_scheme[candidate.scheme_id] = candidate

    merged = sorted(
        best_by_scheme.values(),
        key=lambda scheme: scheme.match_score,
        reverse=True,
    )
    return [scheme.model_dump() for scheme in merged[:limit]]


def _new_turn_id() -> str:
    return uuid4().hex


def _normalize_compact_text(
    value: str | None,
    *,
    max_chars: int | None = None,
) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    compact = " ".join(normalized.split())
    if max_chars is None or len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _format_mapping(value: dict[str, Any]) -> str:
    if not value:
        return "none"
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _format_scheme_ref(scheme_ref: SchemeRef | None) -> str:
    if scheme_ref is None:
        return "none"
    parts = [scheme_ref.name or scheme_ref.scheme_id]
    qualifiers = [
        item for item in (scheme_ref.state, scheme_ref.level, scheme_ref.provider) if item
    ]
    if qualifiers:
        parts.append(f"({', '.join(qualifiers)})")
    return " ".join(parts)


def _format_scheme_refs(scheme_refs: list[SchemeRef]) -> str:
    if not scheme_refs:
        return "none"
    return "; ".join(_format_scheme_ref(item) for item in scheme_refs[:5])


def _collect_recent_scheme_refs(
    relevant_schemes: list[RelevantScheme],
    *,
    limit: int = 5,
) -> list[SchemeRef]:
    return [SchemeRef.from_scheme(scheme) for scheme in relevant_schemes[:limit]]


def _build_why_relevant(scheme: RelevantScheme) -> str:
    normalized_reasons = [
        reason
        for reason in (
            _normalize_compact_text(reason, max_chars=120)
            for reason in scheme.match_reasons
        )
        if reason
    ]
    if normalized_reasons:
        return "; ".join(normalized_reasons[:2])

    qualifiers = [
        label
        for label in (
            f"state={scheme.state}" if scheme.state else None,
            f"level={scheme.level}" if scheme.level else None,
            f"provider={scheme.provider}" if scheme.provider else None,
        )
        if label
    ]
    if qualifiers:
        return f"Retrieval signals: {', '.join(qualifiers)}. Fit is not yet verified."
    return "Retrieved by semantic similarity; fit is not yet verified."


def _build_application_summary(scheme: RelevantScheme) -> str | None:
    parts: list[str] = []
    online = _normalize_compact_text(scheme.application_mode_details.online, max_chars=140)
    offline = _normalize_compact_text(
        scheme.application_mode_details.offline, max_chars=140
    )
    if online:
        parts.append(f"Online: {online}")
    elif scheme.application_modes.online:
        parts.append("Online application available.")
    if offline:
        parts.append(f"Offline: {offline}")
    elif scheme.application_modes.offline:
        parts.append("Offline application available.")
    if not parts:
        documents = _normalize_compact_text(scheme.documents_required, max_chars=140)
        if documents:
            parts.append(f"Documents: {documents}")
    return " ".join(parts) or None


def _build_evidence_snippets(scheme: RelevantScheme) -> list[str]:
    description = _normalize_compact_text(scheme.details)
    return [description] if description else []


def build_grounding_pack(
    *,
    chat_session_id: str,
    turn_id: str,
    user_message: str,
    retrieval_query: str | None,
    relevant_schemes: list[RelevantScheme],
    applied_filters: dict[str, Any],
    ignored_filters: dict[str, Any],
    important_ignored_filters: dict[str, Any],
    selected_scheme_ref: SchemeRef | None,
) -> GroundingPack:
    scheme_cards = [
        GroundingSchemeCard(
            scheme_id=scheme.scheme_id,
            name=scheme.name,
            state=scheme.state,
            level=scheme.level,
            provider=scheme.provider,
            url=scheme.url,
            why_relevant=_build_why_relevant(scheme),
            benefits_summary=_normalize_compact_text(scheme.benefits),
            eligibility_summary=_normalize_compact_text(scheme.eligibility),
            application_summary=_build_application_summary(scheme),
            evidence_snippets=_build_evidence_snippets(scheme),
        )
        for scheme in relevant_schemes[:5]
    ]
    selection_hint = None
    if selected_scheme_ref is not None:
        selection_hint = f"User-selected scheme context: {_format_scheme_ref(selected_scheme_ref)}"

    return GroundingPack(
        chat_session_id=chat_session_id,
        turn_id=turn_id,
        user_message=user_message,
        retrieval_query=retrieval_query,
        applied_filters=dict(applied_filters),
        ignored_filters=dict(ignored_filters),
        important_ignored_filters=dict(important_ignored_filters),
        top_scheme_cards=scheme_cards,
        selection_hint=selection_hint,
    )


def build_top_schemes_artifact(
    *,
    chat_session_id: str,
    turn_id: str,
    relevant_schemes: list[RelevantScheme],
) -> TopSchemesArtifact:
    return TopSchemesArtifact(
        chat_session_id=chat_session_id,
        turn_id=turn_id,
        schemes=[
            TopSchemeArtifactEntry(
                scheme_id=scheme.scheme_id,
                name=scheme.name,
                url=scheme.url,
                state=scheme.state,
                level=scheme.level,
                provider=scheme.provider,
                provider_type=scheme.provider_type,
                ministry=scheme.ministry,
                details=scheme.details,
                benefits=scheme.benefits,
                eligibility=scheme.eligibility,
                documents_required=scheme.documents_required,
                faq=scheme.faq,
                application_modes=scheme.application_mode_details,
                references=list(scheme.sources),
                retrieval_reason=_build_why_relevant(scheme),
            )
            for scheme in relevant_schemes
        ],
    )


def build_session_memory(
    *,
    user_message: str,
    session_snapshot: SessionSnapshot,
    classification: UserIntentClassification,
    decision: OrchestratorDecision,
    relevant_schemes: list[RelevantScheme],
    last_action: str,
) -> SessionMemory:
    base_memory = session_snapshot.to_session_memory()
    profile_updates = aggregate_intent_facts(classification.extracted_profile_updates)
    raw_constraints = aggregate_intent_facts(classification.retrieval_filters)
    canonical_constraints = build_retrieval_intent_profile(
        user_message=user_message,
        retrieval_query=classification.discovery_query or classification.retrieval_query,
        fit_query=classification.fit_query,
        raw_filters=raw_constraints,
    ).filters.model_dump(exclude_none=True)
    active_constraints = {
        **base_memory.active_constraints,
        **canonical_constraints,
    }
    recent_scheme_refs = (
        _collect_recent_scheme_refs(relevant_schemes)
        if relevant_schemes
        else list(base_memory.recent_scheme_refs)
    )
    summary_parts: list[str] = []
    prior_summary = _normalize_compact_text(
        base_memory.conversation_summary,
        max_chars=140,
    )
    if prior_summary:
        summary_parts.append(f"Prior context: {prior_summary}")
    current_request = _normalize_compact_text(user_message, max_chars=140)
    if current_request:
        summary_parts.append(f"Current request: {current_request}")
    if recent_scheme_refs:
        summary_parts.append(f"Recent schemes: {_format_scheme_refs(recent_scheme_refs)}")

    return SessionMemory(
        chat_session_id=session_snapshot.chat_session_id or base_memory.chat_session_id,
        user_profile={
            **base_memory.user_profile,
            **profile_updates,
        },
        preferences=dict(base_memory.preferences),
        conversation_summary=_normalize_compact_text(
            " ".join(summary_parts),
            max_chars=320,
        ),
        last_user_goal=user_message,
        last_action=last_action or decision.next_action.value,
        active_constraints=active_constraints,
        recent_scheme_refs=recent_scheme_refs,
        selected_scheme_ref=base_memory.selected_scheme_ref,
    )


def _build_reply_prompt(
    *,
    user_message: str,
    session_memory: SessionMemory,
    grounding_pack: GroundingPack | None,
) -> str:
    lines = [
        "Original user message (authoritative):",
        user_message,
        "",
        "Derived session memory (may summarize or omit nuance):",
        f"- chat_session_id: {session_memory.chat_session_id}",
        f"- user_profile: {_format_mapping(session_memory.user_profile)}",
        f"- preferences: {_format_mapping(session_memory.preferences)}",
        f"- conversation_summary: {session_memory.conversation_summary or 'none'}",
        f"- last_user_goal: {session_memory.last_user_goal or 'none'}",
        f"- last_action: {session_memory.last_action or 'none'}",
        f"- active_constraints: {_format_mapping(session_memory.active_constraints)}",
        f"- recent_scheme_refs: {_format_scheme_refs(session_memory.recent_scheme_refs)}",
        f"- selected_scheme_ref: {_format_scheme_ref(session_memory.selected_scheme_ref)}",
    ]

    if grounding_pack is None:
        lines.extend(["", "Grounding pack:", "none"])
        return "\n".join(lines).strip()

    lines.extend(
        [
            "",
            "Grounding pack:",
            f"- turn_id: {grounding_pack.turn_id}",
            f"- retrieval_query: {grounding_pack.retrieval_query or 'none'}",
            f"- applied_filters: {_format_mapping(grounding_pack.applied_filters)}",
            f"- ignored_filters: {_format_mapping(grounding_pack.ignored_filters)}",
            (
                "- important_ignored_filters: "
                f"{_format_mapping(grounding_pack.important_ignored_filters)}"
            ),
            f"- selection_hint: {grounding_pack.selection_hint or 'none'}",
            "",
            "Top scheme cards:",
        ]
    )
    if not grounding_pack.top_scheme_cards:
        lines.append("- none")
        return "\n".join(lines).strip()

    for index, card in enumerate(grounding_pack.top_scheme_cards, start=1):
        purpose = "; ".join(card.evidence_snippets) or "none"
        lines.extend(
            [
                f"{index}. {card.name or card.scheme_id}",
                f"   - location: {card.state or 'n/a'}",
                f"   - level: {card.level or 'n/a'}",
                f"   - provider: {card.provider or 'n/a'}",
                f"   - retrieval_context: {card.why_relevant or 'none'}",
                f"   - purpose_or_description: {purpose}",
                f"   - benefits_summary: {card.benefits_summary or 'none'}",
                f"   - eligibility_summary: {card.eligibility_summary or 'none'}",
                f"   - application_summary: {card.application_summary or 'none'}",
                f"   - url: {card.url or 'n/a'}",
            ]
        )
    return "\n".join(lines).strip()


def _set_trace_context_attributes(
    *,
    session_memory: SessionMemory,
    turn_id: str,
    top_schemes_artifact: TopSchemesArtifact | None = None,
) -> None:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return
    current_span.set_attribute("jurisai.chat_session_id", session_memory.chat_session_id)
    current_span.set_attribute("jurisai.turn_id", turn_id)
    if top_schemes_artifact is not None:
        current_span.set_attribute(
            "jurisai.top_schemes_artifact_id",
            top_schemes_artifact.artifact_id,
        )


class BasicAgenticWorkflow(Workflow):
    def __init__(
        self,
        *,
        classifier: UserIntentClassifier | None = None,
        llm: TextGenerationClient | None = None,
        retriever: QdrantSchemeSearchClient | None = None,
        mongo_client: AsyncMongoClient[dict[str, Any]] | None = None,
        include_retrieval_debug: bool = False,
        retrieval_filters_enabled: bool | None = None,
        retrieval_filter_mode: str | None = None,
        timeout: float | None = None,
        verbose: bool = False,
    ) -> None:
        resolved_timeout = settings.workflow.timeout_seconds if timeout is None else timeout
        super().__init__(timeout=resolved_timeout, verbose=verbose)
        self._llm = llm or build_generation_client(
            provider=settings.workflow.generation_provider,
            model=settings.workflow.generation_model,
        )
        self._classifier = classifier or UserIntentClassifier(llm=self._llm)
        self._retrieval_planner = RetrievalToolPlanner(llm=self._llm)
        self._retriever = retriever or QdrantSchemeSearchClient()
        self._mongo_client = mongo_client or AsyncMongoClient(settings.mongodb_uri)
        self._owns_mongo_client = mongo_client is None
        self._include_retrieval_debug = include_retrieval_debug
        self._retrieval_filters_enabled = (
            settings.workflow.retrieval_filters_enabled
            if retrieval_filters_enabled is None
            else retrieval_filters_enabled
        )
        self._retrieval_filter_mode = (
            settings.workflow.retrieval_filter_mode
            if retrieval_filter_mode is None
            else retrieval_filter_mode
        )

    async def aclose(self) -> None:
        if self._owns_mongo_client:
            await self._mongo_client.close()

    @staticmethod
    async def _append_trace_step(
        ctx: Context,
        *,
        stage: str,
        title: str,
        payload: dict[str, Any],
    ) -> None:
        trace_payload = WorkflowTraceStep(
            stage=stage,
            title=title,
            payload=payload,
        ).model_dump(mode="json", exclude_none=True)
        existing_trace = list(await ctx.store.get("workflow_trace", []))
        existing_trace.append(trace_payload)
        await ctx.store.set("workflow_trace", existing_trace)

    @step
    async def classify_intent(
        self,
        ctx: Context,
        ev: StartEvent,
    ) -> IntentClassifiedEvent:
        user_message = (ev.get("user_message") or "").strip()
        session_snapshot = SessionSnapshot.model_validate(
            ev.get("session_snapshot") or {}
        )
        if not user_message:
            raise ValueError("user_message is required to run the workflow.")

        session_memory = session_snapshot.to_session_memory()
        session_snapshot = session_snapshot.model_copy(
            update={"chat_session_id": session_memory.chat_session_id}
        )
        turn_id = _new_turn_id()
        await ctx.store.set("chat_session_id", session_memory.chat_session_id)
        await ctx.store.set("turn_id", turn_id)
        _set_trace_context_attributes(
            session_memory=session_memory,
            turn_id=turn_id,
        )
        classification = self._classifier.classify(
            user_message=user_message,
            session_snapshot=session_snapshot,
            session_memory=session_memory,
        )
        await ctx.store.set("classification", classification.model_dump())
        await ctx.store.set(
            "session_memory",
            session_memory.model_dump(mode="json", exclude_none=True),
        )
        await self._append_trace_step(
            ctx,
            stage="intent_classified",
            title="Intent Classification",
            payload={
                "chat_session_id": session_memory.chat_session_id,
                "turn_id": turn_id,
                "user_message": user_message,
                "session_memory": session_memory.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "classification": classification.model_dump(mode="json", exclude_none=True),
            },
        )
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="intent_classified",
                detail=(
                    f"{classification.primary_intent} "
                    f"(confidence={classification.confidence:.2f})"
                ),
            )
        )
        return IntentClassifiedEvent(
            user_message=user_message,
            session_snapshot=session_snapshot,
            classification=classification,
        )

    @step
    async def route_turn(
        self,
        ctx: Context,
        ev: IntentClassifiedEvent,
    ) -> ResponseRequestedEvent | ToolSelectionEvent:
        decision = self._decide_next_action(ev.classification, ev.session_snapshot)
        await ctx.store.set("decision", decision.model_dump())
        await self._append_trace_step(
            ctx,
            stage="decision_made",
            title="Next Action Decision",
            payload=decision.model_dump(mode="json", exclude_none=True),
        )
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="decision_made",
                detail=f"{decision.next_action} via {decision.selected_agent}",
            )
        )

        if decision.next_action == NextAction.CALL_SCHEME_RETRIEVAL:
            return ToolSelectionEvent(
                user_message=ev.user_message,
                session_snapshot=ev.session_snapshot,
                classification=ev.classification,
                decision=decision,
            )

        return ResponseRequestedEvent(
            user_message=ev.user_message,
            session_snapshot=ev.session_snapshot,
            classification=ev.classification,
            decision=decision,
        )

    @step
    async def plan_retrieval_tools(
        self,
        ctx: Context,
        ev: ToolSelectionEvent,
    ) -> RetrievalPlannedEvent:
        raw_filters = ev.decision.tool_payload.get("filters") or {}
        default_query = normalize_text(ev.decision.tool_payload.get("query")) or ev.user_message
        planner_error: str | None = None

        try:
            planned = self._retrieval_planner.plan(
                user_message=ev.user_message,
                classification=ev.classification,
                session_snapshot=ev.session_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            planner_error = str(exc)
            planned = None

        retrieval_plan = coerce_retrieval_plan(
            plan=planned,
            default_query=ev.classification.discovery_query or default_query,
            default_fit_query=ev.decision.tool_payload.get("fit_query")
            or ev.classification.fit_query,
        )
        if not retrieval_plan.tool_calls:
            retrieval_plan = fallback_retrieval_plan(
                user_message=ev.user_message,
                classification=ev.classification,
                session_snapshot=ev.session_snapshot,
            )

        updated_payload = {
            **ev.decision.tool_payload,
            "query": default_query,
            "filters": raw_filters,
            "retrieval_plan": retrieval_plan.model_dump(mode="json", exclude_none=True),
        }
        if planner_error:
            updated_payload["planner_error"] = planner_error

        decision = ev.decision.model_copy(update={"tool_payload": updated_payload})
        await ctx.store.set("retrieval_plan", updated_payload["retrieval_plan"])
        await self._append_trace_step(
            ctx,
            stage="retrieval_planned",
            title="Retrieval Tool Plan",
            payload={
                "chat_session_id": ev.session_snapshot.to_session_memory().chat_session_id,
                "turn_id": await ctx.store.get("turn_id"),
                "planner_error": planner_error,
                "retrieval_plan": updated_payload["retrieval_plan"],
            },
        )
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="retrieval_planned",
                detail=f"{len(retrieval_plan.tool_calls)} tool call(s) selected",
            )
        )
        return RetrievalPlannedEvent(
            user_message=ev.user_message,
            session_snapshot=ev.session_snapshot,
            classification=ev.classification,
            decision=decision,
        )

    @step
    async def retrieve_schemes(
        self,
        ctx: Context,
        ev: RetrievalPlannedEvent,
    ) -> ResponseRequestedEvent:
        retrieval_plan = RetrievalPlan.model_validate(
            ev.decision.tool_payload.get("retrieval_plan") or {}
        )
        executed_tool_calls: list[dict[str, Any]] = []

        for index, tool_call in enumerate(retrieval_plan.tool_calls, start=1):
            execution_record = self._execute_retrieval_tool_call(
                user_message=ev.user_message,
                tool_call=tool_call,
            )
            executed_tool_calls.append(execution_record)
            await self._append_trace_step(
                ctx,
                stage=f"tool_call_{index}",
                title=f"Tool Call {index}: {tool_call.tool_name}",
                payload=execution_record,
            )
            ctx.write_event_to_stream(
                WorkflowStatusEvent(
                    stage="retrieval_started",
                    detail=(
                        f"{tool_call.tool_name} "
                        f"with query={execution_record['input_payload']['retrieval_query']!r}"
                    ),
                )
            )

        merged_results = merge_retrieved_scheme_results(
            executed_tool_calls,
            limit=settings.workflow.retrieval_limit,
        )
        relevant_schemes = await self._hydrate_relevant_schemes(merged_results)
        updated_session_snapshot = ev.session_snapshot.model_copy(
            update={
                "last_action": "retrieval_tools_executed",
                "relevant_schemes": relevant_schemes,
            }
        )

        query_topics: list[str] = []
        query_tags: list[str] = []
        query_terms: list[str] = []
        applied_filters: dict[str, Any] = {}
        ignored_filters: dict[str, Any] = {}
        important_ignored_filters: dict[str, Any] = {}
        candidate_filters: dict[str, Any] = {}
        normalized_queries: list[str] = []
        raw_hit_count = 0
        retrieval_filters_enabled = self._retrieval_filters_enabled
        for tool_call in executed_tool_calls:
            output_payload = tool_call["output_payload"]
            normalized_queries.append(output_payload["normalized_query"])
            raw_hit_count += int(output_payload["raw_hit_count"])
            query_topics = list(dict.fromkeys(query_topics + output_payload["query_topics"]))
            query_tags = list(dict.fromkeys(query_tags + output_payload["query_tags"]))
            query_terms = list(dict.fromkeys(query_terms + output_payload["query_terms"]))
            applied_filters.update(output_payload["applied_filters"])
            ignored_filters.update(output_payload["ignored_filters"])
            important_ignored_filters.update(
                output_payload.get("important_ignored_filters") or {}
            )
            candidate_filters.update(output_payload.get("candidate_filters") or {})
            retrieval_filters_enabled = bool(
                output_payload.get(
                    "retrieval_filters_enabled",
                    retrieval_filters_enabled,
                )
            )

        turn_id = str(await ctx.store.get("turn_id") or _new_turn_id())
        session_memory = build_session_memory(
            user_message=ev.user_message,
            session_snapshot=ev.session_snapshot,
            classification=ev.classification,
            decision=ev.decision,
            relevant_schemes=relevant_schemes,
            last_action="retrieval_completed",
        )
        grounding_pack = build_grounding_pack(
            chat_session_id=session_memory.chat_session_id,
            turn_id=turn_id,
            user_message=ev.user_message,
            retrieval_query=ev.decision.tool_payload.get("query")
            or ev.classification.discovery_query
            or ev.classification.retrieval_query,
            relevant_schemes=relevant_schemes,
            applied_filters=applied_filters,
            ignored_filters=ignored_filters,
            important_ignored_filters=important_ignored_filters,
            selected_scheme_ref=session_memory.selected_scheme_ref,
        )
        top_schemes_artifact = build_top_schemes_artifact(
            chat_session_id=session_memory.chat_session_id,
            turn_id=turn_id,
            relevant_schemes=relevant_schemes,
        )
        updated_session_snapshot = SessionSnapshot.from_session_memory(
            session_memory,
            relevant_schemes=relevant_schemes,
            latest_grounding_pack=grounding_pack,
            latest_top_schemes_artifact=top_schemes_artifact,
        )
        _set_trace_context_attributes(
            session_memory=session_memory,
            turn_id=turn_id,
            top_schemes_artifact=top_schemes_artifact,
        )

        updated_payload = {
            **ev.decision.tool_payload,
            "normalized_queries": normalized_queries,
            "query_topics": query_topics,
            "query_tags": query_tags,
            "query_terms": query_terms,
            "tool_calls": executed_tool_calls,
            "retrieved_schemes": merged_results,
            "relevant_schemes": [scheme.model_dump() for scheme in relevant_schemes],
            "retrieval_filters_enabled": retrieval_filters_enabled,
            "candidate_filters": candidate_filters,
            "applied_filters": applied_filters,
            "ignored_filters": ignored_filters,
            "raw_hit_count": raw_hit_count,
            "grounding_pack_turn_id": grounding_pack.turn_id,
            "top_schemes_artifact_id": top_schemes_artifact.artifact_id,
        }
        decision = ev.decision.model_copy(update={"tool_payload": updated_payload})
        await ctx.store.set("retrieval", {"tool_calls": executed_tool_calls, "results": merged_results})
        await ctx.store.set(
            "session_memory",
            session_memory.model_dump(mode="json", exclude_none=True),
        )
        await ctx.store.set(
            "grounding_pack",
            grounding_pack.model_dump(mode="json", exclude_none=True),
        )
        await ctx.store.set(
            "top_schemes_artifact",
            top_schemes_artifact.model_dump(mode="json", exclude_none=True),
        )
        await self._append_trace_step(
            ctx,
            stage="retrieval_completed",
            title="Merged Retrieval Results",
            payload={
                "chat_session_id": session_memory.chat_session_id,
                "turn_id": turn_id,
                "tool_call_count": len(executed_tool_calls),
                "raw_hit_count": raw_hit_count,
                "grounding_pack": grounding_pack.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "top_schemes_artifact_id": top_schemes_artifact.artifact_id,
                "retrieved_schemes": merged_results,
                "session_relevant_schemes": [scheme.model_dump(mode="json", exclude_none=True) for scheme in relevant_schemes],
            },
        )
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="retrieval_completed",
                detail=(
                    f"{len(merged_results)} schemes "
                    f"(ignored_filters={list(ignored_filters.keys())})"
                ),
            )
        )
        ctx.write_event_to_stream(
            WorkflowArtifactReadyEvent(
                artifact_type=top_schemes_artifact.artifact_type,
                artifact_id=top_schemes_artifact.artifact_id,
                payload=top_schemes_artifact.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            )
        )
        return ResponseRequestedEvent(
            user_message=ev.user_message,
            session_snapshot=updated_session_snapshot,
            classification=ev.classification,
            decision=decision,
        )

    @step
    async def generate_reply(
        self,
        ctx: Context,
        ev: ResponseRequestedEvent,
    ) -> StopEvent:
        turn_id = str(await ctx.store.get("turn_id") or _new_turn_id())
        relevant_schemes = list(ev.session_snapshot.relevant_schemes)
        current_grounding_pack = ev.session_snapshot.latest_grounding_pack
        current_top_schemes_artifact = ev.session_snapshot.latest_top_schemes_artifact
        if ev.session_snapshot.last_user_goal == ev.user_message:
            base_memory = ev.session_snapshot.to_session_memory()
            session_memory = base_memory.model_copy(
                update={"last_action": "response_generated"}
            )
        else:
            session_memory = build_session_memory(
                user_message=ev.user_message,
                session_snapshot=ev.session_snapshot,
                classification=ev.classification,
                decision=ev.decision,
                relevant_schemes=relevant_schemes,
                last_action="response_generated",
            )
        final_session_snapshot = SessionSnapshot.from_session_memory(
            session_memory,
            relevant_schemes=relevant_schemes,
            latest_grounding_pack=current_grounding_pack,
            latest_top_schemes_artifact=current_top_schemes_artifact,
        )
        _set_trace_context_attributes(
            session_memory=session_memory,
            turn_id=turn_id,
            top_schemes_artifact=current_top_schemes_artifact,
        )
        generation_input = {
            "chat_session_id": session_memory.chat_session_id,
            "turn_id": turn_id,
            "user_message": ev.user_message,
            "session_memory": session_memory.model_dump(mode="json", exclude_none=True),
            "grounding_pack": (
                current_grounding_pack.model_dump(mode="json", exclude_none=True)
                if current_grounding_pack is not None
                else None
            ),
        }
        reply_prompt = _build_reply_prompt(
            user_message=ev.user_message,
            session_memory=session_memory,
            grounding_pack=current_grounding_pack,
        )
        reply_parts: list[str] = []
        astream_text = getattr(self._llm, "astream_text", None)
        if callable(astream_text):
            async for chunk in astream_text(
                reply_prompt,
                system_instruction=REPLY_SYSTEM_PROMPT,
                model=settings.workflow.generation_model,
                temperature=0.2,
            ):
                if not chunk:
                    continue
                reply_parts.append(chunk)
                ctx.write_event_to_stream(WorkflowAnswerDeltaEvent(delta=chunk))
            reply = "".join(reply_parts)
        else:
            reply = self._llm.generate_text(
                reply_prompt,
                system_instruction=REPLY_SYSTEM_PROMPT,
                model=settings.workflow.generation_model,
                temperature=0.2,
            )
            if reply:
                ctx.write_event_to_stream(WorkflowAnswerDeltaEvent(delta=reply))

        decision = ev.decision.model_copy(update={"response": reply.strip()})
        await ctx.store.set("response", decision.response)
        await ctx.store.set(
            "session_memory",
            session_memory.model_dump(mode="json", exclude_none=True),
        )
        await self._append_trace_step(
            ctx,
            stage="response_generated",
            title="Final Grounded Generation",
            payload={
                "input_payload": generation_input,
                "output_payload": {"response": decision.response},
            },
        )
        await self._append_trace_step(
            ctx,
            stage="session_memory_updated",
            title="Session Memory Updated",
            payload={
                "chat_session_id": session_memory.chat_session_id,
                "turn_id": turn_id,
                "session_memory": session_memory.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "top_schemes_artifact_id": (
                    current_top_schemes_artifact.artifact_id
                    if current_top_schemes_artifact is not None
                    else None
                ),
            },
        )
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="response_generated",
                detail=decision.selected_agent,
            )
        )
        return StopEvent(
            result=AgenticTurnResult(
                turn_id=turn_id,
                user_message=ev.user_message,
                classification=ev.classification,
                decision=decision,
                session_memory=session_memory,
                grounding_pack=current_grounding_pack,
                top_schemes_artifact=current_top_schemes_artifact,
                session_snapshot=final_session_snapshot,
                workflow_trace=[
                    WorkflowTraceStep.model_validate(item)
                    for item in await ctx.store.get("workflow_trace", [])
                ],
            ).model_dump()
        )

    def _execute_retrieval_tool_call(
        self,
        *,
        user_message: str,
        tool_call: RetrievalToolCall,
    ) -> dict[str, Any]:
        raw_filters: dict[str, Any] = {}
        if tool_call.state:
            raw_filters["state"] = tool_call.state
        if tool_call.topics:
            raw_filters["topics"] = tool_call.topics

        intent_profile = build_retrieval_intent_profile(
            user_message=user_message,
            retrieval_query=tool_call.query,
            fit_query=tool_call.fit_query,
            raw_filters=raw_filters,
        )
        retrieval = self._retriever.search(
            query_text=intent_profile.discovery_query,
            raw_filters=intent_profile.filters,
            intent_profile=intent_profile,
            limit=settings.workflow.retrieval_limit,
            include_debug=self._include_retrieval_debug,
            enable_filters=self._retrieval_filters_enabled,
            filter_mode=self._retrieval_filter_mode,
        )
        ignored_filters = {
            **intent_profile.ignored_filters,
            **retrieval["ignored_filters"],
        }
        return {
            "tool_name": tool_call.tool_name.value,
            "reasoning": tool_call.reasoning,
            "input_payload": {
                "tool_name": tool_call.tool_name.value,
                "retrieval_query": tool_call.query,
                "fit_query": tool_call.fit_query,
                "state": tool_call.state,
                "topics": tool_call.topics,
                "raw_filters": raw_filters,
            },
            "output_payload": {
                "normalized_query": intent_profile.normalized_query,
                "discovery_query": intent_profile.discovery_query,
                "fit_query": intent_profile.fit_query,
                "retrieval_filters_enabled": retrieval["retrieval_filters_enabled"],
                "retrieval_filter_mode": retrieval["retrieval_filter_mode"],
                "normalized_filters": intent_profile.filters.model_dump(exclude_none=True),
                "candidate_filters": retrieval["candidate_filters"],
                "query_topics": intent_profile.query_topics,
                "query_tags": intent_profile.query_tags,
                "query_terms": intent_profile.query_terms,
                "applied_filters": retrieval["applied_filters"],
                "ignored_filters": ignored_filters,
                "important_ignored_filters": intent_profile.important_ignored_filters,
                "raw_hit_count": retrieval["raw_hit_count"],
                "retrieved_schemes": retrieval["results"],
                "debug": retrieval.get("debug") or {},
            },
        }

    async def _hydrate_relevant_schemes(
        self,
        retrieved_schemes: list[dict[str, Any]],
    ) -> list[RelevantScheme]:
        with TRACER.start_as_current_span("jurisai.hydrate_relevant_schemes") as span:
            parsed_schemes = [
                RetrievedScheme.model_validate(scheme) for scheme in retrieved_schemes
            ]
            span.set_attribute("jurisai.retrieved_scheme_count", len(parsed_schemes))
            if not parsed_schemes:
                return []

            grouped_ids: dict[tuple[str, str], list[ObjectId]] = defaultdict(list)
            for scheme in parsed_schemes:
                document_id = scheme.mongo_ref.document_id
                if not document_id:
                    continue
                try:
                    object_id = ObjectId(document_id)
                except Exception:
                    continue

                database_name = scheme.mongo_ref.database or settings.database_name
                collection_name = scheme.mongo_ref.collection or settings.schemes_collection
                for lookup_collection in preferred_hydration_collections(collection_name):
                    grouped_ids[(database_name, lookup_collection)].append(object_id)

            span.set_attribute("jurisai.mongo_lookup_group_count", len(grouped_ids))
            documents_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
            if grouped_ids:
                for (database_name, collection_name), object_ids in grouped_ids.items():
                    documents = await self._mongo_client[database_name][
                        collection_name
                    ].find({"_id": {"$in": object_ids}}).to_list(length=None)
                    for document in documents:
                        documents_by_key[
                            (database_name, collection_name, str(document["_id"]))
                        ] = document

            span.set_attribute("jurisai.mongo_document_count", len(documents_by_key))
            hydrated_schemes: list[RelevantScheme] = []
            for scheme in parsed_schemes:
                database_name = scheme.mongo_ref.database or settings.database_name
                collection_name = scheme.mongo_ref.collection or settings.schemes_collection
                document_id = scheme.mongo_ref.document_id or ""
                resolved_document: dict[str, Any] | None = None
                resolved_collection: str | None = None
                for lookup_collection in preferred_hydration_collections(collection_name):
                    resolved_document = documents_by_key.get(
                        (database_name, lookup_collection, document_id)
                    )
                    if resolved_document is not None:
                        resolved_collection = lookup_collection
                        break

                if resolved_document is None:
                    hydrated_schemes.append(RelevantScheme.from_retrieved_scheme(scheme))
                    continue

                hydrated_schemes.append(
                    build_relevant_scheme_from_lookup_document(
                        document=resolved_document,
                        collection_name=resolved_collection,
                        scheme=scheme,
                    )
                )

            span.set_attribute("jurisai.hydrated_scheme_count", len(hydrated_schemes))
            return hydrated_schemes

    @staticmethod
    def _decide_next_action(
        classification: UserIntentClassification,
        session_snapshot: SessionSnapshot,
    ) -> OrchestratorDecision:
        if classification.needs_clarification:
            return OrchestratorDecision(
                next_action=NextAction.ASK_CLARIFYING_QUESTION,
                selected_agent="user_clarifier",
                tool_payload={
                    "missing_context": facts_to_dict(
                        classification.extracted_profile_updates
                    ),
                    "question": classification.clarification_question,
                },
            )

        if classification.primary_intent in {
            PrimaryIntent.SCHEME_DISCOVERY,
            PrimaryIntent.FOLLOW_UP,
        }:
            return OrchestratorDecision(
                next_action=NextAction.CALL_SCHEME_RETRIEVAL,
                selected_agent="retrieval_planner",
                tool_payload={
                    "query": classification.discovery_query or classification.retrieval_query,
                    "fit_query": classification.fit_query,
                    "filters": {
                        **session_snapshot.user_profile,
                        **aggregate_intent_facts(classification.retrieval_filters),
                    },
                },
            )

        return OrchestratorDecision(
            next_action=NextAction.RESPOND_DIRECTLY,
            selected_agent="chat_responder",
            tool_payload={"query": classification.user_goal},
        )
