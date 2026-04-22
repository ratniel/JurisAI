from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from src.llm.local_openai_client import LocalOpenAICompatibleClient


class SampleStructuredResponse(BaseModel):
    answer: str
    confidence: float


def _build_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class LocalOpenAICompatibleClientTests(unittest.TestCase):
    def test_generate_structured_parses_json_after_thinking(self) -> None:
        client = LocalOpenAICompatibleClient()

        with patch(
            "src.llm.local_openai_client.completion",
            lambda **_: _build_response(
                "<think>\ninternal reasoning\n</think>\n\n"
                "```json\n"
                '{"answer":"Grounded reply","confidence":0.91}\n'
                "```"
            ),
        ):
            result = client.generate_structured(
                "Classify this reply.",
                SampleStructuredResponse,
            )

        self.assertEqual(result.answer, "Grounded reply")
        self.assertEqual(result.confidence, 0.91)

    def test_generate_text_sends_chat_messages(self) -> None:
        client = LocalOpenAICompatibleClient(
            base_url="http://127.0.0.1:1234/v1",
            api_key="test-key",
            model="mlx-community/Qwen3.5-4B-MLX-4bit",
        )
        captured_kwargs: dict[str, object] = {}

        def _fake_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return _build_response("Direct answer")

        with patch("src.llm.local_openai_client.completion", _fake_completion):
            response = client.generate_text(
                "Summarize the result.",
                system_instruction="You are concise.",
                temperature=0.1,
                tools=[
                    {"type": "function", "function": {"name": "lookup", "parameters": {}}}
                ],
            )

        self.assertEqual(response, "Direct answer")
        self.assertEqual(captured_kwargs["model"], "mlx-community/Qwen3.5-4B-MLX-4bit")
        self.assertEqual(captured_kwargs["custom_llm_provider"], "openai")
        self.assertEqual(captured_kwargs["base_url"], "http://127.0.0.1:1234/v1")
        self.assertEqual(captured_kwargs["temperature"], 0.1)
        self.assertEqual(
            captured_kwargs["tools"],
            [{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
        )
        self.assertEqual(
            captured_kwargs["messages"],
            [
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "Summarize the result."},
            ],
        )

    def test_generate_text_strips_thinking_content_when_disabled(self) -> None:
        client = LocalOpenAICompatibleClient(enable_thinking=False)

        with patch(
            "src.llm.local_openai_client.completion",
            lambda **_: _build_response(
                "<think>\ninternal reasoning\n</think>\n\nFinal grounded answer."
            ),
        ):
            response = client.generate_text("Answer the question.")

        self.assertEqual(response, "Final grounded answer.")

    def test_generate_structured_uses_local_default_model_for_gemini_placeholder(
        self,
    ) -> None:
        client = LocalOpenAICompatibleClient(
            base_url="http://127.0.0.1:1234/v1",
            api_key="test-key",
            model="mlx-community/Qwen3.5-4B-MLX-4bit",
        )
        captured_kwargs: dict[str, object] = {}

        def _fake_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return _build_response('{"answer":"Grounded reply","confidence":0.91}')

        with patch("src.llm.local_openai_client.completion", _fake_completion):
            result = client.generate_structured(
                "Classify this reply.",
                SampleStructuredResponse,
                model="models/gemini-flash-lite-latest",
            )

        self.assertEqual(result.answer, "Grounded reply")
        self.assertEqual(captured_kwargs["model"], "mlx-community/Qwen3.5-4B-MLX-4bit")
        self.assertEqual(captured_kwargs["custom_llm_provider"], "openai")


if __name__ == "__main__":
    unittest.main()
