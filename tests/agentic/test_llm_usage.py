import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.agentic.models import PrimaryIntent, UserIntentClassification
from src.agentic.workflow import BasicAgenticWorkflow
from src.llm.contracts import LLMInvocationMetadata, TokenUsage
from src.llm.gemini_client import GeminiClient
from src.llm.local_openai_client import LocalOpenAICompatibleClient


class LLMUsageTests(unittest.TestCase):
    def test_two_turns_preserve_cumulative_usage(self) -> None:
        classifier = Mock()
        classifier.classify.return_value = UserIntentClassification(
            primary_intent=PrimaryIntent.SMALL_TALK, confidence=1.0,
            user_goal="Greeting", reasoning="Greeting",
        )
        classifier.last_invocation_metadata = LLMInvocationMetadata(
            provider="test", model="classifier", usage=TokenUsage(total_tokens=5),
        )
        llm = Mock(spec=["generate_text", "generate_structured", "last_invocation_metadata", "default_model"])
        llm.default_model = "answer"
        llm.generate_text.return_value = "Hello"
        llm.last_invocation_metadata = LLMInvocationMetadata(
            provider="test", model="answer", usage=TokenUsage(total_tokens=3),
        )
        workflow = BasicAgenticWorkflow(llm=llm, classifier=classifier, retriever=Mock(), mongo_client=Mock())

        async def run():
            first = await workflow.run(user_message="Hello")
            second = await workflow.run(user_message="Hello again", session_snapshot=first["session_snapshot"])
            return first, second

        first, second = asyncio.run(run())
        self.assertEqual(len(first["llm_usage_records"]), 2)
        self.assertEqual(first["session_memory"]["llm_usage_totals"]["total_tokens"], 8)
        self.assertEqual(second["session_snapshot"]["llm_usage_totals"]["total_tokens"], 16)
        self.assertEqual(second["session_memory"]["llm_usage_totals"]["invocation_count"], 4)
        self.assertEqual(len(second["llm_usage_records"]), 2)

    def test_local_metadata_keeps_routed_model_usage_and_history(self) -> None:
        client = LocalOpenAICompatibleClient(model="router")
        response = SimpleNamespace(model="actual-model", usage={
            "prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14,
            "prompt_tokens_details": {"cached_tokens": 2},
            "completion_tokens_details": {"reasoning_tokens": 1},
        }, choices=[SimpleNamespace(message=SimpleNamespace(content="answer"), finish_reason="stop")])
        with patch("src.llm.local_openai_client.completion", return_value=response):
            client.generate_text("Question")
        metadata = client.last_invocation_metadata
        assert metadata is not None
        self.assertEqual(metadata.model, "actual-model")
        self.assertEqual(metadata.usage.total_tokens, 14)
        self.assertEqual(metadata.usage.cached_tokens, 2)
        self.assertEqual(metadata.usage.reasoning_tokens, 1)
        self.assertEqual(client.invocation_history[-1]["requested_model"], "router")
        self.assertEqual(client.invocation_history[-1]["response_model"], "actual-model")

    def test_gemini_token_aliases_skip_invalid_values(self) -> None:
        self.assertEqual(GeminiClient._coerce_int(None, "invalid", 7), 7)
        self.assertEqual(GeminiClient._coerce_int(None, "invalid"), 0)
