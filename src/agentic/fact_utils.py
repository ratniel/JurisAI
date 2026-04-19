from __future__ import annotations

from typing import Any

from src.agentic.models import IntentFact

MULTI_VALUE_FACT_KEYS = frozenset({"tag", "tags", "topic", "topics"})


def aggregate_intent_facts(facts: list[IntentFact]) -> dict[str, Any]:
    """Preserve repeated fact keys instead of silently overwriting them."""

    aggregated: dict[str, list[str]] = {}
    seen_by_key: dict[str, set[str]] = {}

    for fact in facts:
        key = str(fact.key).strip().lower()
        value = str(fact.value).strip()
        if not key or not value:
            continue

        key_seen = seen_by_key.setdefault(key, set())
        lowered_value = value.lower()
        if lowered_value in key_seen:
            continue
        key_seen.add(lowered_value)
        aggregated.setdefault(key, []).append(value)

    payload: dict[str, Any] = {}
    for key, values in aggregated.items():
        if key in MULTI_VALUE_FACT_KEYS:
            payload[key] = values
            continue
        payload[key] = values[0] if len(values) == 1 else values
    return payload
