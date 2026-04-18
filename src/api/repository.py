from __future__ import annotations

from typing import Any

from pymongo import AsyncMongoClient

from src.agentic.models import SchemeRef
from src.api.schemas import (
    ChatMessageRecord,
    ChatRunRecord,
    ChatSessionRecord,
    StreamEventEnvelope,
    utc_now,
)
from src.config.settings import settings


def _without_mongo_id(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {key: value for key, value in payload.items() if key != "_id"}


class ChatRepository:
    """Mongo-backed persistence for chat sessions, runs, and artifacts."""

    def __init__(self, client: AsyncMongoClient[dict[str, Any]]) -> None:
        self._client = client
        self._database = client[settings.database_name]
        self._sessions = self._database[settings.api.chat_sessions_collection]
        self._runs = self._database[settings.api.chat_runs_collection]

    async def initialize(self) -> None:
        await self._sessions.create_index("updated_at")
        await self._runs.create_index("session_id")
        await self._runs.create_index("updated_at")

    async def create_session(self) -> ChatSessionRecord:
        session = ChatSessionRecord()
        session.session_snapshot.chat_session_id = session.session_id
        await self.save_session(session)
        return session

    async def save_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        payload = session.model_dump(mode="json", exclude_none=True)
        payload["_id"] = session.session_id
        await self._sessions.replace_one({"_id": session.session_id}, payload, upsert=True)
        return session

    async def get_session(self, session_id: str) -> ChatSessionRecord | None:
        document = await self._sessions.find_one({"_id": session_id})
        if document is None:
            return None
        return ChatSessionRecord.model_validate(_without_mongo_id(document))

    async def create_run(self, *, session_id: str, user_message: str) -> ChatRunRecord:
        run = ChatRunRecord(session_id=session_id, user_message=user_message)
        await self.save_run(run)
        return run

    async def save_run(self, run: ChatRunRecord) -> ChatRunRecord:
        payload = run.model_dump(mode="json", exclude_none=True)
        payload["_id"] = run.run_id
        await self._runs.replace_one({"_id": run.run_id}, payload, upsert=True)
        return run

    async def get_run(self, run_id: str) -> ChatRunRecord | None:
        document = await self._runs.find_one({"_id": run_id})
        if document is None:
            return None
        return ChatRunRecord.model_validate(_without_mongo_id(document))

    async def append_run_event(self, run_id: str, event: StreamEventEnvelope) -> None:
        await self._runs.update_one(
            {"_id": run_id},
            {
                "$push": {"events": event.model_dump(mode="json", exclude_none=True)},
                "$set": {"updated_at": utc_now().isoformat()},
            },
        )

    async def mark_run_running(self, run_id: str) -> None:
        await self._runs.update_one(
            {"_id": run_id},
            {"$set": {"status": "running", "updated_at": utc_now().isoformat()}},
        )

    async def mark_run_completed(self, run_id: str, run: ChatRunRecord) -> None:
        run.status = "completed"
        run.updated_at = utc_now()
        await self.save_run(run)

    async def mark_run_failed(self, run_id: str, *, error: str) -> None:
        await self._runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "updated_at": utc_now().isoformat(),
                }
            },
        )

    async def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        session = await self.get_session(session_id)
        if session is None:
            return []
        return [
            artifact.model_dump(mode="json", exclude_none=True)
            for artifact in session.artifacts
        ]

    async def get_artifact(self, session_id: str, artifact_id: str) -> dict[str, Any] | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        for artifact in session.artifacts:
            if artifact.artifact_id == artifact_id:
                return artifact.model_dump(mode="json", exclude_none=True)
        return None

    async def update_selected_scheme(
        self,
        *,
        session_id: str,
        scheme_id: str | None,
    ) -> ChatSessionRecord | None:
        session = await self.get_session(session_id)
        if session is None:
            return None

        selected_ref = None
        if scheme_id:
            for scheme in session.session_snapshot.relevant_schemes:
                if scheme.scheme_id == scheme_id:
                    selected_ref = SchemeRef.from_scheme(scheme)
                    break
            if selected_ref is None:
                for scheme_ref in session.session_snapshot.recent_scheme_refs:
                    if scheme_ref.scheme_id == scheme_id:
                        selected_ref = scheme_ref
                        break

        session.session_snapshot.selected_scheme_ref = selected_ref
        if session.session_memory is not None:
            session.session_memory.selected_scheme_ref = selected_ref
        session.updated_at = utc_now()
        await self.save_session(session)
        return session

    async def append_session_message(
        self,
        *,
        session_id: str,
        message: ChatMessageRecord,
    ) -> ChatSessionRecord | None:
        session = await self.get_session(session_id)
        if session is None:
            return None
        session.messages.append(message)
        session.updated_at = utc_now()
        await self.save_session(session)
        return session

