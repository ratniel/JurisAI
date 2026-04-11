from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import gradio as gr

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agentic.models import AgenticTurnResult, SessionSnapshot
from src.agentic.workflow import BasicAgenticWorkflow


def _json_block(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True)


def render_linear_trace_markdown(result: AgenticTurnResult) -> str:
    sections: list[str] = []
    for index, step in enumerate(result.workflow_trace, start=1):
        sections.append(f"### {index}. {step.title}")
        sections.append(f"`{step.stage}`")
        sections.append("```json")
        sections.append(_json_block(step.payload))
        sections.append("```")
    return "\n\n".join(sections).strip() or "No workflow trace captured."


def _render_chat_markdown(turns: list[dict[str, str]]) -> str:
    if not turns:
        return "No turns yet."

    sections: list[str] = []
    for turn in turns:
        sections.append(f"### {turn['role'].title()}")
        sections.append(turn["content"])
    return "\n\n".join(sections)


async def _run_turn_async(
    *,
    user_message: str,
    session_snapshot: dict[str, Any],
) -> AgenticTurnResult:
    workflow = BasicAgenticWorkflow()
    result = await workflow.run(
        user_message=user_message,
        session_snapshot=session_snapshot,
    )
    return AgenticTurnResult.model_validate(result)


def _run_turn(
    user_message: str,
    session_editor_value: str,
    session_state_value: dict[str, Any] | None,
    turn_history_value: list[dict[str, str]] | None,
):
    message = user_message.strip()
    if not message:
        raise gr.Error("User message is required.")

    editor_payload = session_editor_value.strip()
    if editor_payload:
        try:
            session_snapshot = SessionSnapshot.model_validate_json(editor_payload)
        except Exception as exc:  # noqa: BLE001
            raise gr.Error(f"Session JSON is invalid: {exc}") from exc
    else:
        session_snapshot = SessionSnapshot.model_validate(session_state_value or {})

    result = asyncio.run(
        _run_turn_async(
            user_message=message,
            session_snapshot=session_snapshot.model_dump(mode="json", exclude_none=True),
        )
    )

    updated_session = result.session_snapshot.model_dump(mode="json", exclude_none=True)
    updated_history = list(turn_history_value or [])
    updated_history.append({"role": "user", "content": result.user_message})
    updated_history.append(
        {"role": "assistant", "content": result.decision.response or ""}
    )

    return (
        updated_session,
        updated_history,
        result.decision.response or "",
        _render_chat_markdown(updated_history),
        render_linear_trace_markdown(result),
        result.model_dump(mode="json", exclude_none=True),
        result.session_memory.model_dump(mode="json", exclude_none=True),
        (
            result.grounding_pack.model_dump(mode="json", exclude_none=True)
            if result.grounding_pack is not None
            else {}
        ),
        (
            result.top_schemes_artifact.model_dump(mode="json", exclude_none=True)
            if result.top_schemes_artifact is not None
            else {}
        ),
        updated_session.get("relevant_schemes", []),
        _json_block(updated_session),
        _json_block(updated_session),
        "",
    )


def _reset_session():
    empty_session = SessionSnapshot().model_dump(mode="json", exclude_none=True)
    return (
        empty_session,
        [],
        "",
        "No turns yet.",
        "No workflow trace captured.",
        {},
        {},
        {},
        {},
        [],
        _json_block(empty_session),
        _json_block(empty_session),
        "",
    )


def create_agentic_debug_ui() -> gr.Blocks:
    initial_session = SessionSnapshot().model_dump(mode="json", exclude_none=True)

    with gr.Blocks(title="JurisAI Agentic Debug UI") as demo:
        session_state = gr.State(value=initial_session)
        turn_history = gr.State(value=[])

        gr.Markdown(
            """
            # JurisAI Agentic Debug UI

            Run the live workflow turn by turn and inspect the full linear trace:
            classifier output, retrieval plan, each retrieval tool call, the compact
            grounding pack, the top-schemes artifact, session memory, and final grounded
            generation.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                message = gr.Textbox(
                    label="User message",
                    lines=4,
                    placeholder="Describe the user's scheme question here...",
                )
                session_editor = gr.Code(
                    label="Session snapshot JSON",
                    language="json",
                    value=_json_block(initial_session),
                )
                with gr.Row():
                    run_button = gr.Button("Run turn", variant="primary")
                    reset_button = gr.Button("Reset session")
                assistant_reply = gr.Textbox(
                    label="Assistant reply",
                    lines=8,
                    interactive=False,
                )
                chat_markdown = gr.Markdown("No turns yet.")

            with gr.Column(scale=2):
                trace_markdown = gr.Markdown("No workflow trace captured.")
                with gr.Tabs():
                    with gr.Tab("Final Result"):
                        final_result_json = gr.JSON(label="Agentic turn result")
                    with gr.Tab("Session Memory"):
                        session_memory_json = gr.JSON(
                            label="Compact session memory"
                        )
                    with gr.Tab("Grounding Pack"):
                        grounding_pack_json = gr.JSON(
                            label="Answer-time grounding pack"
                        )
                    with gr.Tab("Top Schemes Artifact"):
                        top_schemes_artifact_json = gr.JSON(
                            label="User-facing top schemes artifact"
                        )
                    with gr.Tab("Session Schemes"):
                        session_schemes_json = gr.JSON(
                            label="Relevant schemes stored in session"
                        )
                    with gr.Tab("Session Snapshot"):
                        session_snapshot_json = gr.Code(
                            label="Current session snapshot JSON",
                            language="json",
                            value=_json_block(initial_session),
                            interactive=False,
                        )

        run_button.click(
            fn=_run_turn,
            inputs=[message, session_editor, session_state, turn_history],
            outputs=[
                session_state,
                turn_history,
                assistant_reply,
                chat_markdown,
                trace_markdown,
                final_result_json,
                session_memory_json,
                grounding_pack_json,
                top_schemes_artifact_json,
                session_schemes_json,
                session_editor,
                session_snapshot_json,
                message,
            ],
        )
        reset_button.click(
            fn=_reset_session,
            outputs=[
                session_state,
                turn_history,
                assistant_reply,
                chat_markdown,
                trace_markdown,
                final_result_json,
                session_memory_json,
                grounding_pack_json,
                top_schemes_artifact_json,
                session_schemes_json,
                session_editor,
                session_snapshot_json,
                message,
            ],
        )

    return demo


def main() -> None:
    demo = create_agentic_debug_ui()
    demo.launch(server_name="127.0.0.1", server_port=7861)


if __name__ == "__main__":
    main()
