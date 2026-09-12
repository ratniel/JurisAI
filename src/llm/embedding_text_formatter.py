from __future__ import annotations

from typing import Any

NOMIC_TEXT_MODELS_REQUIRING_PREFIXES = ("nomic-ai/nomic-embed-text-",)

_TASK_PREFIX_BY_TYPE = {
    "RETRIEVAL_DOCUMENT": "search_document: ",
    "RETRIEVAL_QUERY": "search_query: ",
    "search_document": "search_document: ",
    "search_query": "search_query: ",
    "classification": "classification: ",
    "clustering": "clustering: ",
}


def sentence_transformer_load_kwargs(model_name: str) -> dict[str, Any]:
    if _requires_task_prefixes(model_name):
        return {"trust_remote_code": True}
    return {}


def format_text_for_embedding(
    text: str,
    *,
    model_name: str,
    task_type: str,
) -> str:
    normalized_text = text.strip()
    if not normalized_text:
        return normalized_text

    prefix = _TASK_PREFIX_BY_TYPE.get(task_type)
    if prefix is None or not _requires_task_prefixes(model_name):
        return normalized_text
    if normalized_text.lower().startswith(prefix.lower()):
        return normalized_text
    return f"{prefix}{normalized_text}"


def format_texts_for_embedding(
    texts: list[str],
    *,
    model_name: str,
    task_type: str,
) -> list[str]:
    return [
        format_text_for_embedding(
            text,
            model_name=model_name,
            task_type=task_type,
        )
        for text in texts
    ]


def _requires_task_prefixes(model_name: str) -> bool:
    normalized_model = model_name.strip().lower()
    return normalized_model.startswith(
        tuple(prefix.lower() for prefix in NOMIC_TEXT_MODELS_REQUIRING_PREFIXES)
    )
