from __future__ import annotations

from typing import Any

from qdrant_client import models

from src.scheme_contracts import SchemeRuleFilters, coerce_rule_filters
from src.topic_catalog import SCHEME_TOPIC_CATALOG, canonicalize_topic

RETRIEVAL_FILTER_MODES = frozenset(
    {
        "all",
        "none",
        "state_only",
        "topics_only",
        "state_hard_topics_soft",
    }
)
_TOPIC_DISPLAY_BY_CANONICAL = {
    definition.label.lower(): definition.label for definition in SCHEME_TOPIC_CATALOG.topics
}


def _field_condition(key: str, value: str | bool) -> models.FieldCondition:
    return models.FieldCondition(
        key=key,
        match=models.MatchValue(value=value),
    )


def _multi_value_condition(key: str, values: list[str]) -> models.FieldCondition:
    return models.FieldCondition(
        key=key,
        match=models.MatchAny(any=values),
    )


def _topic_filter_values(values: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for value in values:
        canonical = canonicalize_topic(value) or str(value).strip().lower()
        for candidate in (
            canonical,
            _TOPIC_DISPLAY_BY_CANONICAL.get(canonical),
        ):
            normalized = str(candidate or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            expanded.append(normalized)
    return expanded


def _derived_state_scope_condition(provider: str) -> models.Filter:
    return models.Filter(
        must=[
            _field_condition("level", "state"),
            _field_condition("provider", provider),
        ]
    )


def build_qdrant_filter(
    raw_filters: dict[str, Any] | SchemeRuleFilters | None,
    *,
    filter_mode: str = "all",
) -> tuple[models.Filter | None, dict[str, Any], dict[str, Any]]:
    if not raw_filters:
        return None, {}, {}
    if filter_mode not in RETRIEVAL_FILTER_MODES:
        raise ValueError(
            f"Unsupported retrieval filter mode {filter_mode!r}. "
            f"Expected one of: {', '.join(sorted(RETRIEVAL_FILTER_MODES))}."
        )
    if filter_mode == "none":
        return None, {}, {}

    must: list[models.Condition] = []
    should: list[models.Condition] = []
    filters, ignored_filters = coerce_rule_filters(raw_filters)
    applied_filters: dict[str, Any] = {}

    state_enabled = filter_mode in {"all", "state_only", "state_hard_topics_soft"}
    topics_enabled = filter_mode in {"all", "topics_only"}

    if filters.state and state_enabled:
        applied_filters["state"] = filters.state
        should.extend(
            [
                _derived_state_scope_condition(filters.state),
                _field_condition("level", "central"),
            ]
        )
        applied_filters["level"] = "state"
        applied_filters["provider"] = filters.state

    if filters.topics and topics_enabled:
        must.append(_multi_value_condition("topics", _topic_filter_values(filters.topics)))
        applied_filters["topics"] = filters.topics

    for field_name in (
        "level",
        "provider",
        "provider_type",
        "ministry",
        "application_mode",
        "online",
        "offline",
        "tags",
    ):
        value = getattr(filters, field_name)
        if value not in (None, [], {}):
            ignored_filters[field_name] = value

    query_filter = None
    if must or should:
        query_filter = models.Filter(
            must=must or None,
            should=should or None,
            min_should=(
                models.MinShould(conditions=should, min_count=1) if should else None
            ),
        )
    return query_filter, applied_filters, ignored_filters
