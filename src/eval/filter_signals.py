from __future__ import annotations

from typing import Any


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = _normalize_text(item)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(normalized)
    return merged


def build_effective_filter_signals(
    *,
    actual_filters: dict[str, Any],
    query_tags: list[str] | None = None,
    query_topics: list[str] | None = None,
) -> dict[str, Any]:
    """Expose only filters that were actually applied by retrieval."""

    del query_tags
    del query_topics

    return {
        key: value
        for key, value in (actual_filters or {}).items()
        if value not in (None, "", [], {})
    }


def filters_match_expected(
    *,
    expected_filters: dict[str, Any],
    actual_filters: dict[str, Any],
    query_tags: list[str] | None = None,
    query_topics: list[str] | None = None,
) -> bool:
    effective_filters = build_effective_filter_signals(
        actual_filters=actual_filters,
        query_tags=query_tags,
        query_topics=query_topics,
    )

    for key, expected_value in expected_filters.items():
        actual_value = effective_filters.get(key)
        if isinstance(expected_value, list):
            expected_items = {_normalize_text(item).lower() for item in expected_value}
            actual_items = {
                _normalize_text(item).lower() for item in list(actual_value or [])
            }
            if not expected_items.issubset(actual_items):
                return False
            continue

        if _normalize_text(expected_value).lower() != _normalize_text(actual_value).lower():
            return False

    return True
