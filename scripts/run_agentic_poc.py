from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.observability import configure_phoenix_tracing


async def _stream_events(handler: Any) -> None:
    async for event in handler.stream_events():
        if hasattr(event, "stage") and hasattr(event, "detail"):
            print(f"[{event.stage}] {event.detail}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the basic JurisAI agentic workflow POC."
    )
    parser.add_argument(
        "--message",
        required=True,
        help="User message to route through the workflow.",
    )
    parser.add_argument(
        "--session-json",
        default="{}",
        help="Optional JSON object describing the current session snapshot.",
    )
    parser.add_argument(
        "--trace-project",
        default=settings.phoenix.project_name,
        help="Phoenix project name to use when tracing is enabled.",
    )
    parser.add_argument(
        "--phoenix-endpoint",
        default=None,
        help="Optional Phoenix collector endpoint override.",
    )
    args = parser.parse_args()

    tracing_status = configure_phoenix_tracing(
        project_name=args.trace_project,
        endpoint=args.phoenix_endpoint,
    )
    print(f"[tracing] {tracing_status.detail}")

    from src.agentic.models import SessionSnapshot
    from src.agentic.workflow import BasicAgenticWorkflow

    session_snapshot = SessionSnapshot.model_validate_json(args.session_json)
    workflow = BasicAgenticWorkflow()
    handler = workflow.run(
        user_message=args.message,
        session_snapshot=session_snapshot.model_dump(),
    )

    stream_task = asyncio.create_task(_stream_events(handler))
    result = await handler
    await stream_task
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
