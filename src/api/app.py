from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pymongo import AsyncMongoClient

from src.api.repository import ChatRepository
from src.api.runtime import ChatRuntimeManager
from src.api.schemas import (
    ArtifactListResponse,
    ArtifactResponse,
    CreateMessageRequest,
    CreateMessageResponse,
    CreateSessionResponse,
    GetSessionResponse,
    SelectedSchemeRequest,
    SelectedSchemeResponse,
    StreamEventEnvelope,
)
from src.config.settings import settings
from src.observability import configure_phoenix_tracing, flush_phoenix_tracing

LOGGER = logging.getLogger("uvicorn.error")


def format_sse_event(event: StreamEventEnvelope) -> str:
    payload = json.dumps(event.data, ensure_ascii=True)
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {payload}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracing_status = configure_phoenix_tracing()
    app.state.tracing_status = tracing_status
    LOGGER.info("[tracing] %s", tracing_status.detail)

    mongo_client: AsyncMongoClient[dict] = AsyncMongoClient(settings.mongodb_uri)
    repository = ChatRepository(mongo_client)
    await repository.initialize()
    app.state.mongo_client = mongo_client
    app.state.chat_repository = repository
    app.state.chat_runtime = ChatRuntimeManager(repository)
    try:
        yield
    finally:
        flush_phoenix_tracing()
        await mongo_client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="JurisAI Chat API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat/sessions", response_model=CreateSessionResponse)
    async def create_session() -> CreateSessionResponse:
        repository: ChatRepository = app.state.chat_repository
        session = await repository.create_session()
        return CreateSessionResponse(session=session)

    @app.get("/api/chat/sessions/{session_id}", response_model=GetSessionResponse)
    async def get_session(session_id: str) -> GetSessionResponse:
        repository: ChatRepository = app.state.chat_repository
        session = await repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return GetSessionResponse(session=session)

    @app.post(
        "/api/chat/sessions/{session_id}/messages",
        response_model=CreateMessageResponse,
    )
    async def create_message(
        session_id: str,
        request: CreateMessageRequest,
    ) -> CreateMessageResponse:
        repository: ChatRepository = app.state.chat_repository
        runtime: ChatRuntimeManager = app.state.chat_runtime
        session = await repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        user_message = request.message.strip()
        if request.retry:
            latest_user_message = next(
                (message for message in reversed(session.messages) if message.role == "user"),
                None,
            )
            if latest_user_message is None or latest_user_message.content != user_message:
                raise HTTPException(
                    status_code=409,
                    detail="A retry must match the latest user message in this session.",
                )

        run = await runtime.start_run(
            session=session,
            user_message=user_message,
            append_user_message=not request.retry,
        )
        return CreateMessageResponse(
            run_id=run.run_id,
            session_id=session_id,
            status="running",
            stream_path=f"/api/chat/sessions/{session_id}/runs/{run.run_id}/stream",
        )

    @app.get("/api/chat/sessions/{session_id}/runs/{run_id}/stream")
    async def stream_run(session_id: str, run_id: str) -> StreamingResponse:
        repository: ChatRepository = app.state.chat_repository
        runtime: ChatRuntimeManager = app.state.chat_runtime
        run = await repository.get_run(run_id)
        if run is None or run.session_id != session_id:
            raise HTTPException(status_code=404, detail="Run not found.")

        async def event_iterator() -> AsyncIterator[str]:
            run_state = runtime.get_run_state(run_id)
            if run_state is None:
                for event in run.events:
                    yield format_sse_event(event)
                return

            index = 0
            async for event in run_state.iter_from(index):
                yield format_sse_event(event)

        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    @app.get(
        "/api/chat/sessions/{session_id}/artifacts",
        response_model=ArtifactListResponse,
    )
    async def list_artifacts(session_id: str) -> ArtifactListResponse:
        repository: ChatRepository = app.state.chat_repository
        session = await repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return ArtifactListResponse(artifacts=session.artifacts)

    @app.get(
        "/api/chat/sessions/{session_id}/artifacts/{artifact_id}",
        response_model=ArtifactResponse,
    )
    async def get_artifact(session_id: str, artifact_id: str) -> ArtifactResponse:
        repository: ChatRepository = app.state.chat_repository
        session = await repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        for artifact in session.artifacts:
            if artifact.artifact_id == artifact_id:
                return ArtifactResponse(artifact=artifact)
        raise HTTPException(status_code=404, detail="Artifact not found.")

    @app.post(
        "/api/chat/sessions/{session_id}/selected-scheme",
        response_model=SelectedSchemeResponse,
    )
    async def set_selected_scheme(
        session_id: str,
        request: SelectedSchemeRequest,
    ) -> SelectedSchemeResponse:
        repository: ChatRepository = app.state.chat_repository
        session = await repository.update_selected_scheme(
            session_id=session_id,
            scheme_id=request.scheme_id,
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return SelectedSchemeResponse(session=session)

    frontend_dist = Path(settings.api.frontend_dist_dir)
    if frontend_dist.exists():
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", response_class=HTMLResponse)
        async def serve_frontend(full_path: str) -> HTMLResponse:
            index_file = frontend_dist / "index.html"
            if not index_file.exists():
                raise HTTPException(status_code=404, detail="Frontend build not found.")
            return HTMLResponse(index_file.read_text(encoding="utf-8"))

    return app
