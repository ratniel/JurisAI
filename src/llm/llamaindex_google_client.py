from __future__ import annotations

from typing import Any, TypeVar

from llama_index.llms.google_genai import GoogleGenAI
from pydantic import BaseModel

from src.config.settings import settings
from src.llm.contracts import LLMInvocationMetadata

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


class LlamaIndexGoogleGenAIClient:
    """Adapter that exposes LlamaIndex's GoogleGenAI integration behind our contract."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> None:
        resolved_api_key = api_key or settings.gemini_api_key
        if not resolved_api_key:
            raise ValueError(
                "Missing Gemini API key. Set GEMINI_API_KEY in the environment or .env."
            )

        self.default_model = model or settings.gemini_model
        self.provider_name = "llamaindex_google"
        self.last_invocation_metadata: LLMInvocationMetadata | None = None
        self._api_key = resolved_api_key
        self._temperature = temperature
        self._max_retries = max_retries
        self._llm = self._build_llm(self.default_model, temperature=temperature)

    def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> str:
        llm = self._build_llm(
            model or self.default_model,
            temperature=temperature,
            **config_overrides,
        )
        full_prompt = self._compose_prompt(
            prompt=prompt,
            system_instruction=system_instruction,
        )
        response = llm.complete(full_prompt)
        self.last_invocation_metadata = LLMInvocationMetadata(
            provider=self.provider_name,
            model=model or self.default_model,
        )
        return response.text

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
        llm = self._build_llm(
            model or self.default_model,
            temperature=temperature,
            **config_overrides,
        )
        structured_llm = llm.as_structured_llm(response_model)
        full_prompt = self._compose_prompt(
            prompt=prompt,
            system_instruction=system_instruction,
        )
        response = structured_llm.complete(full_prompt)
        self.last_invocation_metadata = LLMInvocationMetadata(
            provider=self.provider_name,
            model=model or self.default_model,
        )
        return response.raw

    def _build_llm(
        self,
        model: str,
        *,
        temperature: float | None,
        **config_overrides: Any,
    ) -> GoogleGenAI:
        llm_kwargs = dict(config_overrides)
        llm_kwargs.pop("response_mime_type", None)
        llm_kwargs.pop("response_schema", None)
        return GoogleGenAI(
            model=model,
            api_key=self._api_key,
            temperature=self._temperature if temperature is None else temperature,
            max_retries=self._max_retries,
            **llm_kwargs,
        )

    @staticmethod
    def _compose_prompt(
        *,
        prompt: str,
        system_instruction: str | None,
    ) -> str:
        if not system_instruction:
            return prompt
        return f"System instruction:\n{system_instruction}\n\nUser prompt:\n{prompt}"
