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


def build_qdrant_filter(
    raw_filters: dict[str, Any] | SchemeRuleFilters | None,
) -> tuple[models.Filter | None, dict[str, Any], dict[str, Any]]:
    if not raw_filters:
        return None, {}, {}

    must: list[models.Condition] = []
    filters, ignored_filters = coerce_rule_filters(raw_filters)
    applied_filters: dict[str, Any] = {}

    if filters.state:
        must.append(_field_condition("state", filters.state))
        applied_filters["state"] = filters.state

    if filters.level:
        must.append(_field_condition("level", filters.level))
        applied_filters["level"] = filters.level

    if filters.provider:
        must.append(_field_condition("provider", filters.provider))
        applied_filters["provider"] = filters.provider

    if filters.provider_type:
        must.append(_field_condition("provider_type", filters.provider_type))
        applied_filters["provider_type"] = filters.provider_type

    if filters.ministry:
        must.append(_field_condition("ministry", filters.ministry))
        applied_filters["ministry"] = filters.ministry

    if filters.application_mode == "online":
        must.append(_field_condition("application_modes.online", True))
        applied_filters["application_mode"] = "online"
    elif filters.application_mode == "offline":
        must.append(_field_condition("application_modes.offline", True))
        applied_filters["application_mode"] = "offline"

    if filters.online is not None:
        must.append(_field_condition("application_modes.online", filters.online))
        applied_filters["online"] = filters.online

    if filters.offline is not None:
        must.append(_field_condition("application_modes.offline", filters.offline))
        applied_filters["offline"] = filters.offline

    if filters.tags:
        must.append(_multi_value_condition("tags", filters.tags))
        applied_filters["tags"] = filters.tags

    if filters.topics:
        must.append(_multi_value_condition("topics", filters.topics))
        applied_filters["topics"] = filters.topics

    query_filter = models.Filter(must=must) if must else None
    return query_filter, applied_filters, ignored_filters
