from __future__ import annotations

from src.llm.embedding_text_formatter import (
    format_text_for_embedding,
    sentence_transformer_load_kwargs,
)


def test_nomic_query_uses_required_prefix_and_remote_code() -> None:
    model = "nomic-ai/nomic-embed-text-v1.5"

    assert format_text_for_embedding(
        "irrigation subsidy",
        model_name=model,
        task_type="RETRIEVAL_QUERY",
    ) == "search_query: irrigation subsidy"
    assert sentence_transformer_load_kwargs(model) == {"trust_remote_code": True}


def test_non_nomic_text_is_unchanged() -> None:
    assert format_text_for_embedding(
        "irrigation subsidy",
        model_name="all-MiniLM-L6-v2",
        task_type="RETRIEVAL_QUERY",
    ) == "irrigation subsidy"

