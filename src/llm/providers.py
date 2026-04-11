from __future__ import annotations

from typing import Literal

from src.config.settings import settings
from src.llm.contracts import EmbeddingClient, TextGenerationClient
from src.llm.gemini_client import GeminiClient
from src.llm.llamaindex_google_client import LlamaIndexGoogleGenAIClient
from src.llm.local_openai_client import LocalOpenAICompatibleClient
from src.llm.openrouter_client import OpenRouterClient

GenerationProviderName = Literal[
    "gemini", "llamaindex_google", "local_openai", "openrouter"
]
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
    if provider == "local_openai":
        resolved_model = model
        if resolved_model is None or resolved_model.startswith("models/gemini-"):
            resolved_model = settings.local_generation.model
        return LocalOpenAICompatibleClient(model=resolved_model)
    if provider == "openrouter":
        resolved_model = model
        if resolved_model is None or resolved_model.startswith("models/gemini-"):
            resolved_model = settings.openrouter.model
        return OpenRouterClient(model=resolved_model)
    raise ValueError(f"Unsupported generation provider: {provider}")


def build_embedding_client(
    *,
    provider: EmbeddingProviderName,
    model: str,
) -> EmbeddingClient:
    if provider == "gemini":
        return GeminiClient(model=model)
    if provider == "local":
        from src.llm.local_embedding_client import LocalSentenceTransformerEmbeddingClient

        return LocalSentenceTransformerEmbeddingClient(model_name=model)
    raise ValueError(f"Unsupported embedding provider: {provider}")
