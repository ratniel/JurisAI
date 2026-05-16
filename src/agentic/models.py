from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from llama_index.core.workflow import Event
from pydantic import BaseModel, Field, model_validator

from src.scheme_contracts import (
    EnrichedApplicationModes,
    EnrichedSchemeData,
    FilterableApplicationModes,
)


class PrimaryIntent(StrEnum):
    SCHEME_DISCOVERY = "scheme_discovery"
    FOLLOW_UP = "follow_up"
    PROFILE_UPDATE = "profile_update"
    GENERAL_QUESTION = "general_question"
    SMALL_TALK = "small_talk"
    OUT_OF_SCOPE = "out_of_scope"


class NextAction(StrEnum):
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    CALL_SCHEME_RETRIEVAL = "call_scheme_retrieval"
    RESPOND_DIRECTLY = "respond_directly"


class RetrievalToolName(StrEnum):
    SEMANTIC_SEARCH = "semantic_search"
    STATE_SCOPED_SEARCH = "state_scoped_search"
    TOPIC_SCOPED_SEARCH = "topic_scoped_search"


def _new_id() -> str:
    return uuid4().hex


class SchemeRef(BaseModel):
    """Compact stable handle to a scheme carried across turns."""

    scheme_id: str
    name: str | None = None
    url: str | None = None
    state: str | None = None
    level: str | None = None
    provider: str | None = None

    @classmethod
    def from_scheme(cls, scheme: Any) -> "SchemeRef":
        return cls(
            scheme_id=str(getattr(scheme, "scheme_id")),
            name=getattr(scheme, "name", None),
            url=getattr(scheme, "url", None),
            state=getattr(scheme, "state", None),
            level=getattr(scheme, "level", None),
            provider=getattr(scheme, "provider", None),
        )


class GroundingSchemeCard(BaseModel):
    """Compact answer-time scheme card injected into grounded prompts."""

    scheme_id: str
    name: str | None = None
    state: str | None = None
    level: str | None = None
    provider: str | None = None
    url: str | None = None
    why_relevant: str | None = None
    benefits_summary: str | None = None
    eligibility_summary: str | None = None
    application_summary: str | None = None
    evidence_snippets: list[str] = Field(default_factory=list)


class GroundingPack(BaseModel):
    """Per-turn compact grounding context for the answer model."""

    chat_session_id: str
    turn_id: str
    user_message: str
    retrieval_query: str | None = None
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    ignored_filters: dict[str, Any] = Field(default_factory=dict)
    important_ignored_filters: dict[str, Any] = Field(default_factory=dict)
    top_scheme_cards: list[GroundingSchemeCard] = Field(default_factory=list)
    selection_hint: str | None = None


class TopSchemeArtifactEntry(BaseModel):
    """Richer user-facing scheme payload exposed through artifact views."""

    scheme_id: str
    name: str | None = None
    url: str | None = None
    state: str | None = None
    level: str | None = None
    provider: str | None = None
    provider_type: str | None = None
    ministry: str | None = None
    details: str | None = None
    benefits: str | None = None
    eligibility: str | None = None
    documents_required: str | None = None
    faq: str | None = None
    application_modes: EnrichedApplicationModes = Field(
        default_factory=EnrichedApplicationModes
    )
    references: list["SchemeSource"] = Field(default_factory=list)
    retrieval_reason: str | None = None


class TopSchemesArtifact(BaseModel):
    """Per-turn reusable top-schemes artifact for UI rendering."""

    artifact_id: str = Field(default_factory=_new_id)
    chat_session_id: str
    turn_id: str
    artifact_type: str = "top_schemes"
    schemes: list[TopSchemeArtifactEntry] = Field(default_factory=list)


class SessionMemory(BaseModel):
    """Persistent per-chat memory distilled away from raw trace payloads."""

    chat_session_id: str = Field(default_factory=_new_id)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    conversation_summary: str | None = None
    last_user_goal: str | None = None
    last_action: str | None = None
    active_constraints: dict[str, Any] = Field(default_factory=dict)
    recent_scheme_refs: list[SchemeRef] = Field(default_factory=list)
    selected_scheme_ref: SchemeRef | None = None


class SessionSnapshot(BaseModel):
    """Conversation state carried between workflow turns."""

    chat_session_id: str | None = None
    user_profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    last_user_goal: str | None = None
    last_action: str | None = None
    conversation_summary: str | None = None
    active_constraints: dict[str, Any] = Field(default_factory=dict)
    recent_scheme_refs: list[SchemeRef] = Field(default_factory=list)
    selected_scheme_ref: SchemeRef | None = None
    relevant_schemes: list["RelevantScheme"] = Field(default_factory=list)
    latest_grounding_pack: GroundingPack | None = None
    latest_top_schemes_artifact: TopSchemesArtifact | None = None

    def to_session_memory(self) -> SessionMemory:
        recent_refs = list(self.recent_scheme_refs)
        if not recent_refs:
            recent_refs = [
                SchemeRef.from_scheme(scheme) for scheme in self.relevant_schemes[:5]
            ]

        return SessionMemory(
            chat_session_id=self.chat_session_id or _new_id(),
            user_profile=dict(self.user_profile),
            preferences=dict(self.preferences),
            conversation_summary=self.conversation_summary,
            last_user_goal=self.last_user_goal,
            last_action=self.last_action,
            active_constraints=dict(self.active_constraints),
            recent_scheme_refs=recent_refs,
            selected_scheme_ref=self.selected_scheme_ref,
        )

    @classmethod
    def from_session_memory(
        cls,
        session_memory: SessionMemory,
        *,
        relevant_schemes: list["RelevantScheme"] | None = None,
        latest_grounding_pack: GroundingPack | None = None,
        latest_top_schemes_artifact: TopSchemesArtifact | None = None,
    ) -> "SessionSnapshot":
        return cls(
            chat_session_id=session_memory.chat_session_id,
            user_profile=dict(session_memory.user_profile),
            preferences=dict(session_memory.preferences),
            last_user_goal=session_memory.last_user_goal,
            last_action=session_memory.last_action,
            conversation_summary=session_memory.conversation_summary,
            active_constraints=dict(session_memory.active_constraints),
            recent_scheme_refs=list(session_memory.recent_scheme_refs),
            selected_scheme_ref=session_memory.selected_scheme_ref,
            relevant_schemes=list(relevant_schemes or []),
            latest_grounding_pack=latest_grounding_pack,
            latest_top_schemes_artifact=latest_top_schemes_artifact,
        )


class IntentFact(BaseModel):
    """A single structured fact extracted from user input or session state."""

    key: str
    value: str


class UserIntentClassification(BaseModel):
    """Structured classifier output used to route the current user turn."""

    primary_intent: PrimaryIntent
    confidence: float = Field(ge=0.0, le=1.0)
    user_goal: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    is_followup: bool = False
    should_update_user_profile: bool = False
    extracted_profile_updates: list[IntentFact] = Field(default_factory=list)
    retrieval_query: str | None = None
    discovery_query: str | None = None
    fit_query: str | None = None
    retrieval_filters: list[IntentFact] = Field(default_factory=list)
    reasoning: str = Field(
        description="Short internal rationale to help the orchestrator route the turn."
    )

    @model_validator(mode="after")
    def _backfill_profile_queries(self) -> "UserIntentClassification":
        if self.discovery_query is None and self.retrieval_query is not None:
            self.discovery_query = self.retrieval_query
        if self.retrieval_query is None and self.discovery_query is not None:
            self.retrieval_query = self.discovery_query
        if self.fit_query is None and self.discovery_query is not None:
            self.fit_query = self.discovery_query
        return self


class OrchestratorDecision(BaseModel):
    """Workflow decision describing the next action and its payload."""

    next_action: NextAction
    selected_agent: str
    response: str | None = None
    tool_payload: dict[str, Any] = Field(default_factory=dict)


class RetrievalToolCall(BaseModel):
    """A single retrieval tool invocation selected by the LLM planner."""

    tool_name: RetrievalToolName
    query: str
    fit_query: str | None = None
    state: str | None = None
    topics: list[str] = Field(default_factory=list)
    reasoning: str | None = None

    @model_validator(mode="after")
    def _backfill_fit_query(self) -> "RetrievalToolCall":
        if self.fit_query is None:
            self.fit_query = self.query
        return self


class RetrievalPlan(BaseModel):
    """Ordered retrieval plan produced before tool execution."""

    rationale: str = ""
    tool_calls: list[RetrievalToolCall] = Field(default_factory=list)


class WorkflowTraceStep(BaseModel):
    """Structured debug step emitted for linear workflow inspection."""

    stage: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MongoReference(BaseModel):
    """Stable pointer back to the MongoDB record behind a retrieved scheme."""

    database: str | None = None
    collection: str | None = None
    document_id: str | None = None
    url: str | None = None


class RetrievedScheme(BaseModel):
    """Lean retrieval result returned from Qdrant before full Mongo hydration."""

    scheme_id: str
    name: str | None = None
    url: str | None = None
    level: str | None = None
    provider: str | None = None
    provider_type: str | None = None
    state: str | None = None
    ministry: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    application_modes: FilterableApplicationModes = Field(
        default_factory=FilterableApplicationModes
    )
    selected_fields: dict[str, Any] = Field(default_factory=dict)
    mongo_ref: MongoReference = Field(default_factory=MongoReference)
    match_profile: str
    match_score: float = Field(ge=0.0)
    adjusted_score: float | None = None
    matched_profiles: list[str] = Field(default_factory=list)
    profile_scores: dict[str, float] = Field(default_factory=dict)
    match_reasons: list[str] = Field(default_factory=list)


class SchemeSource(BaseModel):
    """Citation or source entry attached to a scheme shown in chat."""

    text: str | None = None
    url: str | None = None


class RelevantScheme(BaseModel):
    """Chat-ready scheme record with retrieval metadata plus hydrated details."""

    scheme_id: str
    name: str | None = None
    url: str | None = None
    level: str | None = None
    provider: str | None = None
    provider_type: str | None = None
    state: str | None = None
    ministry: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    application_modes: FilterableApplicationModes = Field(
        default_factory=FilterableApplicationModes
    )
    application_mode_details: EnrichedApplicationModes = Field(
        default_factory=EnrichedApplicationModes
    )
    details: str | None = None
    benefits: str | None = None
    eligibility: str | None = None
    documents_required: str | None = None
    faq: str | None = None
    sources: list[SchemeSource] = Field(default_factory=list)
    mongo_ref: MongoReference = Field(default_factory=MongoReference)
    match_profile: str
    match_score: float = Field(ge=0.0)
    adjusted_score: float | None = None
    matched_profiles: list[str] = Field(default_factory=list)
    profile_scores: dict[str, float] = Field(default_factory=dict)
    match_reasons: list[str] = Field(default_factory=list)

    @classmethod
    def from_retrieved_scheme(cls, scheme: RetrievedScheme) -> "RelevantScheme":
        return cls(
            scheme_id=scheme.scheme_id,
            name=scheme.name,
            url=scheme.url,
            level=scheme.level,
            provider=scheme.provider,
            provider_type=scheme.provider_type,
            state=scheme.state,
            ministry=scheme.ministry,
            tags=scheme.tags,
            topics=scheme.topics,
            application_modes=scheme.application_modes,
            application_mode_details=EnrichedApplicationModes(),
            details=scheme.selected_fields.get("details"),
            benefits=scheme.selected_fields.get("benefits"),
            eligibility=scheme.selected_fields.get("eligibility"),
            mongo_ref=scheme.mongo_ref,
            match_profile=scheme.match_profile,
            match_score=scheme.match_score,
            adjusted_score=scheme.adjusted_score,
            matched_profiles=scheme.matched_profiles,
            profile_scores=scheme.profile_scores,
            match_reasons=scheme.match_reasons,
        )

    @classmethod
    def from_mongo_document(
        cls,
        document: dict[str, Any],
        scheme: RetrievedScheme,
    ) -> "RelevantScheme":
        document_record = EnrichedSchemeData.model_validate(document)
        return cls(
            scheme_id=scheme.scheme_id,
            name=document_record.name or scheme.name,
            url=document_record.url or scheme.url,
            level=document_record.level or scheme.level,
            provider=document_record.provider or scheme.provider,
            provider_type=document_record.provider_type or scheme.provider_type,
            state=document_record.state or scheme.state,
            ministry=document_record.ministry or scheme.ministry,
            tags=list(document_record.tags or scheme.tags),
            topics=list(document_record.topics or scheme.topics),
            application_modes=document_record.application_modes.to_filterable(),
            application_mode_details=document_record.application_modes,
            details=document_record.details,
            benefits=document_record.benefits,
            eligibility=document_record.eligibility,
            documents_required=document_record.documents_required,
            faq=document_record.faq,
            sources=[
                SchemeSource.model_validate(
                    source.model_dump() if hasattr(source, "model_dump") else source
                )
                for source in document_record.sources
            ],
            mongo_ref=scheme.mongo_ref,
            match_profile=scheme.match_profile,
            match_score=scheme.match_score,
            adjusted_score=scheme.adjusted_score,
            matched_profiles=scheme.matched_profiles,
            profile_scores=scheme.profile_scores,
            match_reasons=scheme.match_reasons,
        )


class AgenticTurnResult(BaseModel):
    """Final workflow output for a single agentic turn."""

    turn_id: str | None = None
    user_message: str
    classification: UserIntentClassification
    decision: OrchestratorDecision
    session_memory: SessionMemory
    grounding_pack: GroundingPack | None = None
    top_schemes_artifact: TopSchemesArtifact | None = None
    session_snapshot: SessionSnapshot
    workflow_trace: list[WorkflowTraceStep] = Field(default_factory=list)


class WorkflowStatusEvent(Event):
    """Streaming status update emitted while the workflow is running."""

    stage: str
    detail: str


class WorkflowAnswerDeltaEvent(Event):
    """Streaming answer text delta emitted during final generation."""

    delta: str


class WorkflowArtifactReadyEvent(Event):
    """Signal that a UI-facing artifact is ready to render."""

    artifact_type: str
    artifact_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class IntentClassifiedEvent(Event):
    """Workflow event emitted after intent classification succeeds."""

    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification


class ToolSelectionEvent(Event):
    """Workflow event requesting execution of a retrieval or tool step."""

    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification
    decision: OrchestratorDecision


class RetrievalPlannedEvent(Event):
    """Workflow event emitted after the LLM picks retrieval tools."""

    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification
    decision: OrchestratorDecision


class ResponseRequestedEvent(Event):
    """Workflow event requesting final answer generation."""

    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification
    decision: OrchestratorDecision
