from typing import TYPE_CHECKING

from src.llm.contracts import EmbeddingClient, TextGenerationClient
from src.llm.gemini_client import GeminiClient
from src.llm.llamaindex_google_client import LlamaIndexGoogleGenAIClient
from src.llm.local_openai_client import LocalOpenAICompatibleClient
from src.llm.openrouter_client import OpenRouterClient
from src.llm.providers import build_embedding_client, build_generation_client

if TYPE_CHECKING:
    from src.llm.local_embedding_client import LocalSentenceTransformerEmbeddingClient

__all__ = [
    "EmbeddingClient",
    "GeminiClient",
    "LlamaIndexGoogleGenAIClient",
    "LocalOpenAICompatibleClient",
    "LocalSentenceTransformerEmbeddingClient",
    "OpenRouterClient",
    "TextGenerationClient",
    "build_embedding_client",
    "build_generation_client",
]


def __getattr__(name: str):
    if name == "LocalSentenceTransformerEmbeddingClient":
        from src.llm.local_embedding_client import LocalSentenceTransformerEmbeddingClient

        return LocalSentenceTransformerEmbeddingClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
