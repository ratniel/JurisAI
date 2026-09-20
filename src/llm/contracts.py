from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


class LLMInvocationMetadata(BaseModel):
    provider: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str | None = None
    raw_usage: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class TextGenerationClient(Protocol):
    default_model: str
    last_invocation_metadata: LLMInvocationMetadata | None

    def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> str: ...

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModelT],
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0,
        **config_overrides: Any,
    ) -> StructuredModelT: ...


@runtime_checkable
class EmbeddingClient(Protocol):
    def embed_text(
        self,
        text: str,
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[float]: ...

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[list[float]]: ...
