from __future__ import annotations

import asyncio
import unittest

from src.agentic.debug_ui import _run_turn_async, render_linear_trace_markdown
from src.agentic.models import (
    AgenticTurnResult,
    SessionMemory,
    OrchestratorDecision,
    SessionSnapshot,
    UserIntentClassification,
    WorkflowTraceStep,
)


def _make_turn_result(*, user_message: str, response: str) -> AgenticTurnResult:
    return AgenticTurnResult(
        user_message=user_message,
        classification=UserIntentClassification.model_validate(
            {
                "primary_intent": "scheme_discovery",
                "confidence": 0.92,
                "user_goal": "Find schemes",
                "retrieval_query": "farmer scheme maharashtra",
                "reasoning": "Benefits discovery request.",
            }
        ),
        decision=OrchestratorDecision.model_validate(
            {
                "next_action": "call_scheme_retrieval",
                "selected_agent": "retrieval_planner",
                "response": response,
            }
        ),
        session_memory=SessionMemory(
            chat_session_id="chat-123",
            last_user_goal="Find schemes",
            last_action="response_generated",
        ),
        session_snapshot=SessionSnapshot(),
        workflow_trace=[],
    )


class _ReusableWorkflow:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def run(self, *, user_message: str, session_snapshot: dict[str, object]):
        self.calls.append((user_message, session_snapshot))
        return _make_turn_result(
            user_message=user_message,
            response=f"reply for {user_message}",
        ).model_dump(mode="json", exclude_none=True)


class AgenticDebugUiTests(unittest.TestCase):
    def test_linear_trace_includes_tool_io_and_final_generation(self) -> None:
        result = AgenticTurnResult(
            user_message="Farmer in Maharashtra looking for help.",
            classification=UserIntentClassification.model_validate(
                {
                    "primary_intent": "scheme_discovery",
                    "confidence": 0.92,
                    "user_goal": "Find schemes",
                    "retrieval_query": "farmer scheme maharashtra",
                    "reasoning": "Benefits discovery request.",
                }
            ),
            decision=OrchestratorDecision.model_validate(
                {
                    "next_action": "call_scheme_retrieval",
                    "selected_agent": "retrieval_planner",
                    "response": "Here are the likely schemes.",
                }
            ),
            session_memory=SessionMemory(
                chat_session_id="chat-123",
                last_user_goal="Find schemes",
                last_action="response_generated",
            ),
            session_snapshot=SessionSnapshot(),
            workflow_trace=[
                WorkflowTraceStep(
                    stage="retrieval_planned",
                    title="Retrieval Tool Plan",
                    payload={"retrieval_plan": {"tool_calls": [{"tool_name": "state_scoped_search"}]}},
                ),
                WorkflowTraceStep(
                    stage="tool_call_1",
                    title="Tool Call 1: state_scoped_search",
                    payload={
                        "input_payload": {"tool_name": "state_scoped_search", "state": "Maharashtra"},
                        "output_payload": {
                            "retrieved_schemes": [{"scheme_id": "scheme-a", "name": "Scheme A"}]
                        },
                    },
                ),
                WorkflowTraceStep(
                    stage="response_generated",
                    title="Final Grounded Generation",
                    payload={"output_payload": {"response": "Grounded answer"}},
                ),
            ],
        )

        markdown = render_linear_trace_markdown(result)

        self.assertIn("Retrieval Tool Plan", markdown)
        self.assertIn("state_scoped_search", markdown)
        self.assertIn("\"retrieved_schemes\"", markdown)
        self.assertIn("Final Grounded Generation", markdown)
        self.assertIn("Grounded answer", markdown)

    def test_run_turn_async_reuses_injected_workflow(self) -> None:
        workflow = _ReusableWorkflow()

        first = asyncio.run(
            _run_turn_async(
                workflow=workflow,
                user_message="first turn",
                session_snapshot={"chat_session_id": "chat-123"},
            )
        )
        second = asyncio.run(
            _run_turn_async(
                workflow=workflow,
                user_message="second turn",
                session_snapshot={"chat_session_id": "chat-123"},
            )
        )

        self.assertEqual(first.decision.response, "reply for first turn")
        self.assertEqual(second.decision.response, "reply for second turn")
        self.assertEqual(
            workflow.calls,
            [
                ("first turn", {"chat_session_id": "chat-123"}),
                ("second turn", {"chat_session_id": "chat-123"}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
