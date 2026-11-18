from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import BaseModel
from src.llm.local_openai_client import LocalOpenAICompatibleClient


class Answer(BaseModel):
    answer: str


def response(content: str, reasoning: str = "") -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, reasoning_content=reasoning), finish_reason="stop")])


class LMStudioStructuredOutputTests(unittest.TestCase):
    def test_sends_json_schema_and_preserves_retry_settings(self) -> None:
        client = LocalOpenAICompatibleClient(model="qwen3.5-4b-mlx")
        with patch("src.llm.local_openai_client.completion", return_value=response('{"answer":"ok"}')) as complete:
            self.assertEqual(client.generate_structured("Answer", Answer).answer, "ok")
        self.assertEqual(complete.call_args.kwargs["response_format"], {
            "type": "json_schema", "json_schema": {
                "name": "Answer", "strict": True, "schema": Answer.model_json_schema()}})
        self.assertEqual(complete.call_args.kwargs["max_retries"], 2)

    def test_qwen_fallback_uses_reasoning_only_when_content_is_empty(self) -> None:
        client = LocalOpenAICompatibleClient(model="qwen3.5-4b-mlx")
        with patch("src.llm.local_openai_client.completion", return_value=response("", '{"answer":"fallback"}')):
            self.assertEqual(client.generate_structured("Answer", Answer).answer, "fallback")
        with patch("src.llm.local_openai_client.completion", return_value=response('{"answer":"content"}', '{"answer":"reasoning"}')):
            self.assertEqual(client.generate_structured("Answer", Answer).answer, "content")

    def test_other_models_reject_reasoning_only_output(self) -> None:
        client = LocalOpenAICompatibleClient(model="other-model")
        with patch("src.llm.local_openai_client.completion", return_value=response("", '{"answer":"reasoning"}')) as complete:
            with self.assertRaises(ValueError):
                client.generate_structured("Answer", Answer)
        self.assertEqual(complete.call_count, 3)

    def test_explicit_response_format_is_preserved(self) -> None:
        client = LocalOpenAICompatibleClient(model="other-model")
        with patch("src.llm.local_openai_client.completion", return_value=response('{"answer":"ok"}')) as complete:
            client.generate_structured("Answer", Answer, response_format={"type": "json_object"})
        self.assertEqual(complete.call_args.kwargs["response_format"], {"type": "json_object"})
