from __future__ import annotations

from enum import StrEnum
from typing import Any

from llama_index.core.workflow import Event
from pydantic import BaseModel, Field

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


class SessionSnapshot(BaseModel):
    user_profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    last_action: str | None = None
    conversation_summary: str | None = None
    relevant_schemes: list["RelevantScheme"] = Field(default_factory=list)


class IntentFact(BaseModel):
    key: str
    value: str


class UserIntentClassification(BaseModel):
    primary_intent: PrimaryIntent
    confidence: float = Field(ge=0.0, le=1.0)
    user_goal: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    is_followup: bool = False
    should_update_user_profile: bool = False
    extracted_profile_updates: list[IntentFact] = Field(default_factory=list)
    retrieval_query: str | None = None
    retrieval_filters: list[IntentFact] = Field(default_factory=list)
    reasoning: str = Field(
        description="Short internal rationale to help the orchestrator route the turn."
    )


class OrchestratorDecision(BaseModel):
    next_action: NextAction
    selected_agent: str
    response: str | None = None
    tool_payload: dict[str, Any] = Field(default_factory=dict)


class MongoReference(BaseModel):
    database: str | None = None
    collection: str | None = None
    document_id: str | None = None
    url: str | None = None


class RetrievedScheme(BaseModel):
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
    matched_profiles: list[str] = Field(default_factory=list)
    profile_scores: dict[str, float] = Field(default_factory=dict)


class SchemeSource(BaseModel):
    text: str | None = None
    url: str | None = None


class RelevantScheme(BaseModel):
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
    matched_profiles: list[str] = Field(default_factory=list)
    profile_scores: dict[str, float] = Field(default_factory=dict)

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
            matched_profiles=scheme.matched_profiles,
            profile_scores=scheme.profile_scores,
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
                SchemeSource.model_validate(source)
                for source in document_record.sources
            ],
            mongo_ref=scheme.mongo_ref,
            match_profile=scheme.match_profile,
            match_score=scheme.match_score,
            matched_profiles=scheme.matched_profiles,
            profile_scores=scheme.profile_scores,
        )


class AgenticTurnResult(BaseModel):
    user_message: str
    classification: UserIntentClassification
    decision: OrchestratorDecision
    session_snapshot: SessionSnapshot


class WorkflowStatusEvent(Event):
    stage: str
    detail: str


class IntentClassifiedEvent(Event):
    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification


class ToolSelectionEvent(Event):
    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification
    decision: OrchestratorDecision


class ResponseRequestedEvent(Event):
    user_message: str
    session_snapshot: SessionSnapshot
    classification: UserIntentClassification
    decision: OrchestratorDecision
