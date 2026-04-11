from __future__ import annotations

import argparse
from collections.abc import AsyncIterator, Iterator
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.config.settings import settings

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


class GeminiClient:
    """Thin wrapper around google-genai using the Gemini Developer API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        api_version: str = "v1alpha",
    ) -> None:
        resolved_api_key = api_key or settings.gemini_api_key
        if not resolved_api_key:
            raise ValueError(
                "Missing Gemini API key. Set GEMINI_API_KEY in the environment or .env."
            )

        self.default_model = model or settings.gemini_model
        self._client = genai.Client(
            api_key=resolved_api_key,
            http_options=types.HttpOptions(api_version=api_version),
        )

    def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> str:
        response = self.generate(
            prompt,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            **config_overrides,
        )
        return response.text or ""

    async def agenerate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> str:
        response = await self.agenerate(
            prompt,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            **config_overrides,
        )
        return response.text or ""

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> types.GenerateContentResponse:
        return self._client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config=self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                **config_overrides,
            ),
        )

    async def agenerate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> types.GenerateContentResponse:
        return await self._client.aio.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config=self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                **config_overrides,
            ),
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModelT],
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0,
        **config_overrides: Any,
    ) -> StructuredModelT:
        response = self.generate(
            prompt,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_model,
            **config_overrides,
        )
        if response.parsed is None:
            raise ValueError("Gemini did not return a parsed structured response.")
        return response.parsed

    async def agenerate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModelT],
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0,
        **config_overrides: Any,
    ) -> StructuredModelT:
        response = await self.agenerate(
            prompt,
            model=model,
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_model,
            **config_overrides,
        )
        if response.parsed is None:
            raise ValueError("Gemini did not return a parsed structured response.")
        return response.parsed

    def stream_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> Iterator[str]:
        stream = self._client.models.generate_content_stream(
            model=model or self.default_model,
            contents=prompt,
            config=self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                **config_overrides,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def astream_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> AsyncIterator[str]:
        stream = await self._client.aio.models.generate_content_stream(
            model=model or self.default_model,
            contents=prompt,
            config=self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                **config_overrides,
            ),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    def create_chat(
        self,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> Any:
        return self._client.chats.create(
            model=model or self.default_model,
            config=self._build_config(
                system_instruction=system_instruction,
                temperature=temperature,
                **config_overrides,
            ),
        )

    def embed_text(
        self,
        text: str,
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[float]:
        return self.embed_texts(
            [text],
            model=model,
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[list[float]]:
        config_kwargs: dict[str, Any] = {"task_type": task_type}
        if output_dimensionality is not None:
            config_kwargs["output_dimensionality"] = output_dimensionality

        response = self._client.models.embed_content(
            model=model or settings.embeddings.gemini_model,
            contents=texts,
            config=types.EmbedContentConfig(**config_kwargs),
        )
        return [embedding.values for embedding in response.embeddings]

    @staticmethod
    def _build_config(
        *,
        system_instruction: str | None = None,
        temperature: float | None = None,
        **config_overrides: Any,
    ) -> types.GenerateContentConfig:
        config_kwargs: dict[str, Any] = dict(config_overrides)
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        return types.GenerateContentConfig(**config_kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple interactive Gemini chat using GEMINI_API_KEY."
    )
    parser.add_argument(
        "--model",
        default=settings.gemini_model,
        help="Gemini model to use. Defaults to settings.gemini_model.",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="Optional system instruction applied to the chat session.",
    )
    args = parser.parse_args()

    chat = GeminiClient(model=args.model).create_chat(
        system_instruction=args.system,
    )

    print(f"Gemini chat ready on model: {args.model}")
    print("Type 'exit' or 'quit' to end the session.")

    while True:
        prompt = input("You> ").strip()
        if prompt.lower() in {"exit", "quit"}:
            break
        if not prompt:
            continue

        response = chat.send_message(prompt)
        print(f"Gemini> {response.text or ''}")


if __name__ == "__main__":
    main()
