from __future__ import annotations

import asyncio
from typing import Any

from src.agentic.models import (
    AgenticTurnResult,
    WorkflowAnswerDeltaEvent,
    WorkflowArtifactReadyEvent,
    WorkflowStatusEvent,
)
from src.agentic.workflow import BasicAgenticWorkflow
from src.api.repository import ChatRepository
from src.api.schemas import (
    ChatMessageRecord,
    ChatRunRecord,
    ChatSessionRecord,
    StreamEventEnvelope,
    utc_now,
)


class ChatRunState:
    """In-memory stream state used to fan out SSE events while a run is live."""

    def __init__(self) -> None:
        self._events: list[StreamEventEnvelope] = []
        self._condition = asyncio.Condition()
        self._finished = False

    @property
    def events(self) -> list[StreamEventEnvelope]:
        return list(self._events)

    async def publish(self, event: StreamEventEnvelope) -> None:
        async with self._condition:
            self._events.append(event)
            self._condition.notify_all()

    async def finish(self) -> None:
        async with self._condition:
            self._finished = True
            self._condition.notify_all()

    async def iter_from(self, index: int = 0):
        while True:
            async with self._condition:
                while index >= len(self._events) and not self._finished:
                    await self._condition.wait()
                if index < len(self._events):
                    event = self._events[index]
                    index += 1
                elif self._finished:
                    return
                else:
                    continue
            yield event


class ChatRuntimeManager:
    """Coordinates workflow execution with Mongo persistence and SSE fan-out."""

    def __init__(self, repository: ChatRepository) -> None:
        self._repository = repository
        self._active_runs: dict[str, ChatRunState] = {}

    async def start_run(
        self,
        *,
        session: ChatSessionRecord,
        user_message: str,
        append_user_message: bool = True,
    ) -> ChatRunRecord:
        run = await self._repository.create_run(
            session_id=session.session_id,
            user_message=user_message,
        )
        run_state = ChatRunState()
        self._active_runs[run.run_id] = run_state

        if append_user_message:
            user_entry = ChatMessageRecord(role="user", content=user_message)
            updated_session = await self._repository.append_session_message(
                session_id=session.session_id,
                message=user_entry,
            )
            if updated_session is not None:
                session = updated_session

        asyncio.create_task(self._execute_run(session=session, run=run))
        return run

    def get_run_state(self, run_id: str) -> ChatRunState | None:
        return self._active_runs.get(run_id)

    async def _execute_run(
        self,
        *,
        session: ChatSessionRecord,
        run: ChatRunRecord,
    ) -> None:
        run_state = self._active_runs[run.run_id]
        await self._repository.mark_run_running(run.run_id)
        workflow = BasicAgenticWorkflow()

        await self._publish(
            run_state,
            StreamEventEnvelope(
                event_type="run_started",
                run_id=run.run_id,
                session_id=session.session_id,
                data={"message": run.user_message},
            ),
        )

        try:
            handler = workflow.run(
                user_message=run.user_message,
                session_snapshot=session.session_snapshot.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            )
            stream_task = asyncio.create_task(
                self._forward_workflow_events(
                    handler=handler,
                    run=run,
                    run_state=run_state,
                )
            )
            result_payload = await handler
            await stream_task

            result = AgenticTurnResult.model_validate(result_payload)
            assistant_entry = ChatMessageRecord(
                role="assistant",
                content=result.decision.response or "",
                turn_id=result.turn_id,
            )
            latest_session = await self._repository.get_session(session.session_id)
            if latest_session is None:
                latest_session = session

            latest_session.messages.append(assistant_entry)
            latest_session.session_snapshot = result.session_snapshot
            latest_session.session_memory = result.session_memory
            latest_session.updated_at = utc_now()
            if result.top_schemes_artifact is not None:
                latest_session.artifacts = [
                    artifact
                    for artifact in latest_session.artifacts
                    if artifact.artifact_id != result.top_schemes_artifact.artifact_id
                ]
                latest_session.artifacts.append(result.top_schemes_artifact)

            await self._repository.save_session(latest_session)

            run.result = result
            run.events = run_state.events
            await self._publish(
                run_state,
                StreamEventEnvelope(
                    event_type="run_completed",
                    run_id=run.run_id,
                    session_id=session.session_id,
                    data={
                        "turn_id": result.turn_id,
                        "assistant_message": result.decision.response or "",
                        "session": latest_session.model_dump(
                            mode="json",
                            exclude_none=True,
                        ),
                    },
                ),
            )
            run.events = run_state.events
            await self._repository.mark_run_completed(run.run_id, run)
        except Exception as exc:  # noqa: BLE001
            await self._repository.mark_run_failed(run.run_id, error=str(exc))
            await self._publish(
                run_state,
                StreamEventEnvelope(
                    event_type="run_failed",
                    run_id=run.run_id,
                    session_id=session.session_id,
                    data={"error": str(exc)},
                ),
            )
        finally:
            await run_state.finish()

    async def _forward_workflow_events(
        self,
        *,
        handler: Any,
        run: ChatRunRecord,
        run_state: ChatRunState,
    ) -> None:
        async for event in handler.stream_events():
            envelope = self._translate_workflow_event(
                event=event,
                run_id=run.run_id,
                session_id=run.session_id,
            )
            if envelope is None:
                continue
            await self._publish(run_state, envelope)

    async def _publish(
        self,
        run_state: ChatRunState,
        event: StreamEventEnvelope,
    ) -> None:
        await run_state.publish(event)
        await self._repository.append_run_event(event.run_id, event)

    @staticmethod
    def _translate_workflow_event(
        *,
        event: Any,
        run_id: str,
        session_id: str,
    ) -> StreamEventEnvelope | None:
        if isinstance(event, WorkflowStatusEvent):
            return StreamEventEnvelope(
                event_type="stage_update",
                run_id=run_id,
                session_id=session_id,
                data={"stage": event.stage, "detail": event.detail},
            )
        if isinstance(event, WorkflowAnswerDeltaEvent):
            return StreamEventEnvelope(
                event_type="answer_delta",
                run_id=run_id,
                session_id=session_id,
                data={"delta": event.delta},
            )
        if isinstance(event, WorkflowArtifactReadyEvent):
            return StreamEventEnvelope(
                event_type="artifact_ready",
                run_id=run_id,
                session_id=session_id,
                data={
                    "artifact_type": event.artifact_type,
                    "artifact_id": event.artifact_id,
                    "artifact": event.payload,
                },
            )
        return None
