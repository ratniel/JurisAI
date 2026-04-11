from __future__ import annotations

from typing import Any

from qdrant_client import models

from src.scheme_contracts import SchemeRuleFilters, coerce_rule_filters


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


def _derived_state_scope_condition(provider: str) -> models.Filter:
    return models.Filter(
        must=[
            _field_condition("level", "state"),
            _field_condition("provider", provider),
        ]
    )


def build_qdrant_filter(
    raw_filters: dict[str, Any] | SchemeRuleFilters | None,
) -> tuple[models.Filter | None, dict[str, Any], dict[str, Any]]:
    if not raw_filters:
        return None, {}, {}

    must: list[models.Condition] = []
    should: list[models.Condition] = []
    filters, ignored_filters = coerce_rule_filters(raw_filters)
    applied_filters: dict[str, Any] = {}

    if filters.state:
        applied_filters["state"] = filters.state
        should.extend(
            [
                _derived_state_scope_condition(filters.state),
                _field_condition("level", "central"),
            ]
        )
        applied_filters["level"] = "state"
        applied_filters["provider"] = filters.state

    if filters.topics:
        must.append(_multi_value_condition("topics", filters.topics))
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
