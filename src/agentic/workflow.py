from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from bson import ObjectId
from opentelemetry import trace
from pymongo import AsyncMongoClient

from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step

from src.agentic.intent_classifier import UserIntentClassifier
from src.agentic.models import (
    AgenticTurnResult,
    IntentClassifiedEvent,
    IntentFact,
    NextAction,
    OrchestratorDecision,
    PrimaryIntent,
    RelevantScheme,
    ResponseRequestedEvent,
    RetrievedScheme,
    SessionSnapshot,
    ToolSelectionEvent,
    UserIntentClassification,
    WorkflowStatusEvent,
)
from src.config.settings import settings
from src.llm import TextGenerationClient, build_generation_client
from src.retrieval import QdrantSchemeSearchClient

TRACER = trace.get_tracer(__name__)

REPLY_SYSTEM_PROMPT = """
You are JurisAI, a concise and careful public-benefits assistant.
Reply in plain language.
If the orchestrator wants clarification, ask only one focused question.
If retrieval results are provided, ground the answer only in those schemes.
If no suitable scheme is found, say so plainly and suggest one focused next detail that would improve retrieval.
When citing results, include a short References section with scheme names and URLs when available.
""".strip()
def facts_to_dict(facts: list[IntentFact]) -> dict[str, str]:
    return {fact.key: fact.value for fact in facts}


class BasicAgenticWorkflow(Workflow):
    def __init__(
        self,
        *,
        classifier: UserIntentClassifier | None = None,
        llm: TextGenerationClient | None = None,
        retriever: QdrantSchemeSearchClient | None = None,
        timeout: float = 60.0,
        verbose: bool = False,
    ) -> None:
        super().__init__(timeout=timeout, verbose=verbose)
        self._llm = llm or build_generation_client(
            provider=settings.workflow.generation_provider,
            model=settings.workflow.generation_model,
        )
        self._classifier = classifier or UserIntentClassifier(llm=self._llm)
        self._retriever = retriever or QdrantSchemeSearchClient()

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

        classification = self._classifier.classify(
            user_message=user_message,
            session_snapshot=session_snapshot,
        )
        await ctx.store.set("classification", classification.model_dump())
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
    async def retrieve_schemes(
        self,
        ctx: Context,
        ev: ToolSelectionEvent,
    ) -> ResponseRequestedEvent:
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="retrieval_started",
                detail=(
                    f"{ev.decision.selected_agent} "
                    f"with query={ev.decision.tool_payload.get('query')!r}"
                ),
            )
        )

        query_text = (ev.decision.tool_payload.get("query") or ev.user_message).strip()
        raw_filters = ev.decision.tool_payload.get("filters") or {}
        retrieval = self._retriever.search(
            query_text=query_text,
            raw_filters=raw_filters,
            limit=settings.workflow.retrieval_limit,
        )
        relevant_schemes = await self._hydrate_relevant_schemes(retrieval["results"])
        updated_session_snapshot = ev.session_snapshot.model_copy(
            update={
                "last_action": ev.decision.selected_agent,
                "relevant_schemes": relevant_schemes,
            }
        )

        updated_payload = {
            **ev.decision.tool_payload,
            "retrieved_schemes": retrieval["results"],
            "relevant_schemes": [scheme.model_dump() for scheme in relevant_schemes],
            "applied_filters": retrieval["applied_filters"],
            "ignored_filters": retrieval["ignored_filters"],
            "raw_hit_count": retrieval["raw_hit_count"],
        }
        decision = ev.decision.model_copy(update={"tool_payload": updated_payload})
        await ctx.store.set("retrieval", retrieval)
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="retrieval_completed",
                detail=(
                    f"{len(retrieval['results'])} schemes "
                    f"(ignored_filters={list(retrieval['ignored_filters'].keys())})"
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
        reply = self._llm.generate_text(
            f"""
User message:
{ev.user_message}

Intent classification:
{ev.classification.model_dump_json(indent=2)}

Session snapshot:
{ev.session_snapshot.model_dump_json(indent=2)}

Orchestrator decision:
{ev.decision.model_dump_json(indent=2)}

Retrieved schemes:
{json.dumps(ev.decision.tool_payload.get("retrieved_schemes", []), indent=2)}
""".strip(),
            system_instruction=REPLY_SYSTEM_PROMPT,
            model=settings.workflow.generation_model,
            temperature=0.2,
        )

        decision = ev.decision.model_copy(update={"response": reply.strip()})
        await ctx.store.set("response", decision.response)
        ctx.write_event_to_stream(
            WorkflowStatusEvent(
                stage="response_generated",
                detail=decision.selected_agent,
            )
        )
        return StopEvent(
            result=AgenticTurnResult(
                user_message=ev.user_message,
                classification=ev.classification,
                decision=decision,
                session_snapshot=ev.session_snapshot,
            ).model_dump()
        )

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
                grouped_ids[(database_name, collection_name)].append(object_id)

            span.set_attribute("jurisai.mongo_lookup_group_count", len(grouped_ids))
            documents_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
            client: AsyncMongoClient[dict[str, Any]] | None = None
            try:
                if grouped_ids:
                    client = AsyncMongoClient(settings.mongodb_uri)
                    for (database_name, collection_name), object_ids in grouped_ids.items():
                        documents = await client[database_name][collection_name].find(
                            {"_id": {"$in": object_ids}}
                        ).to_list(length=None)
                        for document in documents:
                            documents_by_key[
                                (database_name, collection_name, str(document["_id"]))
                            ] = document
            finally:
                if client is not None:
                    await client.close()

            span.set_attribute("jurisai.mongo_document_count", len(documents_by_key))
            hydrated_schemes: list[RelevantScheme] = []
            for scheme in parsed_schemes:
                database_name = scheme.mongo_ref.database or settings.database_name
                collection_name = scheme.mongo_ref.collection or settings.schemes_collection
                document_id = scheme.mongo_ref.document_id or ""
                document = documents_by_key.get(
                    (database_name, collection_name, document_id)
                )
                hydrated_schemes.append(
                    RelevantScheme.from_mongo_document(document, scheme)
                    if document is not None
                    else RelevantScheme.from_retrieved_scheme(scheme)
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
                selected_agent="scheme_retrieval",
                tool_payload={
                    "query": classification.retrieval_query,
                    "filters": {
                        **session_snapshot.user_profile,
                        **facts_to_dict(classification.retrieval_filters),
                    },
                },
            )

        return OrchestratorDecision(
            next_action=NextAction.RESPOND_DIRECTLY,
            selected_agent="chat_responder",
            tool_payload={"query": classification.user_goal},
        )
