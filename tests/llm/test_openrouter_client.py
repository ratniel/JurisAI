from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.llm.openrouter_client import OpenRouterClient
from src.llm.providers import build_generation_client


def _build_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class OpenRouterClientTests(unittest.TestCase):
    def test_openrouter_client_sends_openrouter_headers(self) -> None:
        client = OpenRouterClient(
            api_key="openrouter-key",
            base_url="https://openrouter.ai/api/v1",
            model="openrouter/free",
            app_name="JurisAI",
            http_referer="https://jurisai.local",
        )
        captured_kwargs: dict[str, object] = {}

        def _fake_completion(**kwargs):
            captured_kwargs.update(kwargs)
            return _build_response("Grounded answer")

        with patch("src.llm.local_openai_client.completion", _fake_completion):
            response = client.generate_text("Summarize the result.", temperature=0.1)

        self.assertEqual(response, "Grounded answer")
        self.assertEqual(captured_kwargs["model"], "openrouter/free")
        self.assertEqual(captured_kwargs["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(captured_kwargs["api_key"], "openrouter-key")
        self.assertEqual(captured_kwargs["custom_llm_provider"], "openai")
        self.assertEqual(captured_kwargs["temperature"], 0.1)
        self.assertEqual(
            captured_kwargs["extra_headers"],
            {
                "HTTP-Referer": "https://jurisai.local",
                "X-OpenRouter-Title": "JurisAI",
            },
        )
        self.assertNotIn("extra_body", captured_kwargs)

    def test_build_generation_client_returns_openrouter_client_for_gemini_placeholder_model(
        self,
    ) -> None:
        with patch(
            "src.llm.providers.settings.openrouter.model",
            "openrouter/free",
        ), patch(
            "src.llm.openrouter_client.settings.openrouter.api_key",
            "openrouter-key",
        ):
            client = build_generation_client(
                provider="openrouter",
                model="models/gemini-flash-lite-latest",
            )

        self.assertIsInstance(client, OpenRouterClient)
        self.assertEqual(client.default_model, "openrouter/free")

    def test_openrouter_client_requires_api_key(self) -> None:
        with patch("src.llm.openrouter_client.settings.openrouter.api_key", None):
            with self.assertRaisesRegex(
                ValueError,
                "Missing OpenRouter API key",
            ):
                OpenRouterClient(api_key=None)


if __name__ == "__main__":
    unittest.main()
