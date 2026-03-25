from __future__ import annotations

from typing import Literal

from src.llm.contracts import EmbeddingClient, TextGenerationClient
from src.llm.gemini_client import GeminiClient
from src.llm.llamaindex_google_client import LlamaIndexGoogleGenAIClient
from src.llm.local_embedding_client import LocalSentenceTransformerEmbeddingClient

GenerationProviderName = Literal["gemini", "llamaindex_google"]
EmbeddingProviderName = Literal["gemini", "local"]


def build_generation_client(
    *,
    provider: GenerationProviderName = "gemini",
    model: str | None = None,
) -> TextGenerationClient:
    if provider == "gemini":
        return GeminiClient(model=model)
    if provider == "llamaindex_google":
        return LlamaIndexGoogleGenAIClient(model=model)
    raise ValueError(f"Unsupported generation provider: {provider}")


def build_embedding_client(
    *,
    provider: EmbeddingProviderName,
    model: str,
) -> EmbeddingClient:
    if provider == "gemini":
        return GeminiClient(model=model)
    if provider == "local":
        return LocalSentenceTransformerEmbeddingClient(model_name=model)
    raise ValueError(f"Unsupported embedding provider: {provider}")
