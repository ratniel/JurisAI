from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from src.agentic.models import AgenticTurnResult, SessionMemory, SessionSnapshot, TopSchemesArtifact


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class ChatMessageRecord(BaseModel):
    """Stored transcript entry for a chat session."""

    message_id: str = Field(default_factory=new_id)
    role: Literal["user", "assistant"]
    content: str
    turn_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class StreamEventEnvelope(BaseModel):
    """Serialized SSE payload persisted for replay and debugging."""

    event_id: str = Field(default_factory=new_id)
    event_type: Literal[
        "run_started",
        "stage_update",
        "answer_delta",
        "artifact_ready",
        "run_completed",
        "run_failed",
    ]
    run_id: str
    session_id: str
    created_at: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)


class ChatSessionRecord(BaseModel):
    """Persistent chat-session document stored in MongoDB."""

    session_id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    session_snapshot: SessionSnapshot = Field(default_factory=SessionSnapshot)
    session_memory: SessionMemory | None = None
    messages: list[ChatMessageRecord] = Field(default_factory=list)
    artifacts: list[TopSchemesArtifact] = Field(default_factory=list)


class ChatRunRecord(BaseModel):
    """Persistent run document stored in MongoDB."""

    run_id: str = Field(default_factory=new_id)
    session_id: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    user_message: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    events: list[StreamEventEnvelope] = Field(default_factory=list)
    result: AgenticTurnResult | None = None
    error: str | None = None


class CreateSessionResponse(BaseModel):
    """API response for a newly created chat session."""

    session: ChatSessionRecord

class GetSessionResponse(BaseModel):
    """API response when fetching a chat session."""

    session: ChatSessionRecord

class CreateMessageRequest(BaseModel):
    """POST body for a new user message."""

    message: str
    retry: bool = False


class CreateMessageResponse(BaseModel):
    """Immediate API response after a run is created."""

    run_id: str
    session_id: str
    status: Literal["queued", "running"]
    stream_path: str


class ArtifactListResponse(BaseModel):
    """List of artifacts attached to a session."""

    artifacts: list[TopSchemesArtifact]


class ArtifactResponse(BaseModel):
    """Single artifact lookup response."""

    artifact: TopSchemesArtifact


class SelectedSchemeRequest(BaseModel):
    """Set or clear the selected scheme for follow-up turns."""

    scheme_id: str | None = None


class SelectedSchemeResponse(BaseModel):
    """Updated session after selected scheme changes."""

    session: ChatSessionRecord
