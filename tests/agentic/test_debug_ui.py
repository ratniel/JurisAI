from __future__ import annotations

import unittest

from src.agentic.debug_ui import render_linear_trace_markdown
from src.agentic.models import (
    AgenticTurnResult,
    SessionMemory,
    OrchestratorDecision,
    SessionSnapshot,
    UserIntentClassification,
    WorkflowTraceStep,
)


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


if __name__ == "__main__":
    unittest.main()
