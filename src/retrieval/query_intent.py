from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.scheme_contracts import (
    SchemeRuleFilters,
    coerce_rule_filters,
    normalize_terms,
    normalize_topics,
)
from src.data_ingestion.topic_taxonomy import infer_topics_from_tags
from src.topic_catalog import CONTROLLED_TOPICS
from src.topic_catalog import CONTROLLED_TOPIC_SET

STATE_ALIASES: tuple[tuple[str, str], ...] = (
    ("andaman and nicobar islands", "Andaman and Nicobar Islands"),
    ("andhra pradesh", "Andhra Pradesh"),
    ("arunachal pradesh", "Arunachal Pradesh"),
    ("assam", "Assam"),
    ("bihar", "Bihar"),
    ("chandigarh", "Chandigarh"),
    ("chhattisgarh", "Chhattisgarh"),
    ("dadra and nagar haveli and daman and diu", "Dadra and Nagar Haveli and Daman and Diu"),
    ("daman and diu", "Dadra and Nagar Haveli and Daman and Diu"),
    ("dadra and nagar haveli", "Dadra and Nagar Haveli and Daman and Diu"),
    ("delhi", "Delhi"),
    ("nct of delhi", "Delhi"),
    ("goa", "Goa"),
    ("gujarat", "Gujarat"),
    ("haryana", "Haryana"),
    ("himachal pradesh", "Himachal Pradesh"),
    ("jammu and kashmir", "Jammu and Kashmir"),
    ("jharkhand", "Jharkhand"),
    ("karnataka", "Karnataka"),
    ("kerala", "Kerala"),
    ("ladakh", "Ladakh"),
    ("lakshadweep", "Lakshadweep"),
    ("madhya pradesh", "Madhya Pradesh"),
    ("maharashtra", "Maharashtra"),
    ("manipur", "Manipur"),
    ("meghalaya", "Meghalaya"),
    ("mizoram", "Mizoram"),
    ("nagaland", "Nagaland"),
    ("odisha", "Odisha"),
    ("orissa", "Odisha"),
    ("puducherry", "Puducherry"),
    ("pondicherry", "Puducherry"),
    ("punjab", "Punjab"),
    ("rajasthan", "Rajasthan"),
    ("sikkim", "Sikkim"),
    ("tamil nadu", "Tamil Nadu"),
    ("telangana", "Telangana"),
    ("tripura", "Tripura"),
    ("uttar pradesh", "Uttar Pradesh"),
    ("uttarakhand", "Uttarakhand"),
    ("west bengal", "West Bengal"),
)

CONTROLLED_TAG_LOOKUP = {
    "farmer": "Farmer",
    "student": "Student",
    "minority community": "Minority Community",
    "person with disability": "Person With Disability",
    "pwd": "Person With Disability",
    "women": "Women",
    "woman": "Women",
    "girl": "Girl",
    "loan": "Loan",
    "sc": "SC",
    "st": "ST",
    "obc": "OBC",
}

IMPORTANT_FILTER_KEYS = frozenset(
    {
        "state",
        "location",
        "geography",
        "demographic",
        "occupation",
        "community",
        "category",
        "application_mode",
        "online",
        "offline",
    }
)

SPECIAL_FILTER_KEY_ALIASES: dict[str, str] = {
    "category": "demographic",
    "community": "demographic",
    "geography": "state",
    "location": "state",
    "residence_state": "state",
    "state_name": "state",
}


class RetrievalIntentProfile(BaseModel):
    """Deterministic query-side intent model used to normalize retrieval requests."""

    raw_query: str
    normalized_query: str
    filters: SchemeRuleFilters = Field(default_factory=SchemeRuleFilters)
    query_topics: list[str] = Field(default_factory=list)
    query_tags: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    ignored_filters: dict[str, Any] = Field(default_factory=dict)
    important_ignored_filters: dict[str, Any] = Field(default_factory=dict)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\ufeff", " ").split()).strip()


def _normalize_key(value: Any) -> str:
    return _normalize_text(value).lower()


def _merge_unique(current: list[str], additions: list[str]) -> list[str]:
    seen = {item.lower() for item in current}
    merged = list(current)
    for item in additions:
        normalized = _normalize_text(item)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        merged.append(normalized)
    return merged


def _infer_state_from_text(text: str) -> str | None:
    lowered = f" {_normalize_text(text).lower()} "
    for alias, canonical in STATE_ALIASES:
        if f" {alias} " in lowered:
            return canonical
    return None


def _infer_tags_from_text(text: str) -> list[str]:
    lowered = f" {_normalize_text(text).lower()} "
    inferred: list[str] = []
    seen: set[str] = set()

    for alias, canonical in CONTROLLED_TAG_LOOKUP.items():
        if f" {alias} " not in lowered:
            continue
        lowered_canonical = canonical.lower()
        if lowered_canonical in seen:
            continue
        seen.add(lowered_canonical)
        inferred.append(canonical)

    return inferred


def _canonicalize_raw_filters(
    raw_filters: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pending: dict[str, Any] = {}
    ignored_filters: dict[str, Any] = {}

    for key, value in (raw_filters or {}).items():
        if value in (None, "", [], {}):
            continue

        lowered_key = _normalize_key(key)
        canonical_key = SPECIAL_FILTER_KEY_ALIASES.get(lowered_key, lowered_key)
        values = normalize_terms(value)

        if canonical_key in {"demographic", "occupation", "community", "category"}:
            recognized_tags = [
                CONTROLLED_TAG_LOOKUP[item.lower()]
                for item in values
                if item.lower() in CONTROLLED_TAG_LOOKUP
            ]
            if recognized_tags:
                pending["tags"] = _merge_unique(
                    list(pending.get("tags") or []),
                    recognized_tags,
                )
            unknown_values = [
                item for item in values if item.lower() not in CONTROLLED_TAG_LOOKUP
            ]
            if unknown_values:
                ignored_filters[key] = value
            continue

        if canonical_key == "topics":
            recognized_topics = normalize_topics(values)
            if recognized_topics:
                pending["topics"] = _merge_unique(
                    list(pending.get("topics") or []),
                    recognized_topics,
                )
            if len(recognized_topics) != len(values):
                ignored_filters[key] = value
            continue

        if canonical_key == "tags":
            recognized_tags = [
                CONTROLLED_TAG_LOOKUP[item.lower()]
                for item in values
                if item.lower() in CONTROLLED_TAG_LOOKUP
            ]
            if recognized_tags:
                pending["tags"] = _merge_unique(
                    list(pending.get("tags") or []),
                    recognized_tags,
                )
            if len(recognized_tags) != len(values):
                ignored_filters[key] = value
            continue

        if canonical_key in {
            "state",
            "level",
            "provider",
            "provider_type",
            "ministry",
            "application_mode",
            "online",
            "offline",
        }:
            if isinstance(value, list):
                normalized_values = normalize_terms(value)
                if len({item.lower() for item in normalized_values}) != 1:
                    ignored_filters[key] = value
                    continue
                pending[canonical_key] = normalized_values[0]
                continue
            pending[canonical_key] = value
            continue

        ignored_filters[key] = value

    return pending, ignored_filters


def _build_normalized_query(
    *,
    query_text: str,
    filters: SchemeRuleFilters,
) -> str:
    del filters
    return _normalize_text(query_text)


def build_retrieval_intent_profile(
    *,
    user_message: str,
    retrieval_query: str | None,
    raw_filters: dict[str, Any] | None,
) -> RetrievalIntentProfile:
    base_query = _normalize_text(retrieval_query) or _normalize_text(user_message)
    pending_filters, ignored_filters = _canonicalize_raw_filters(raw_filters)

    if not pending_filters.get("state"):
        inferred_state = _infer_state_from_text(f"{user_message} {base_query}")
        if inferred_state:
            pending_filters["state"] = inferred_state

    inferred_tags = _infer_tags_from_text(f"{user_message} {base_query}")
    if inferred_tags:
        pending_filters["tags"] = _merge_unique(
            list(pending_filters.get("tags") or []),
            inferred_tags,
        )

    filters, coerced_ignored_filters = coerce_rule_filters(pending_filters)
    ignored_filters = {
        **ignored_filters,
        **coerced_ignored_filters,
    }

    query_tags = list(filters.tags or [])
    query_terms: list[str] = []
    if filters.topics:
        query_topics = list(filters.topics)
    else:
        inferred_topics = [
            topic
            for topic in infer_topics_from_tags(filters.tags or [])
            if topic in CONTROLLED_TOPIC_SET
        ]
        query_topics = sorted(inferred_topics, key=CONTROLLED_TOPICS.index)

    normalized_query = _build_normalized_query(
        query_text=base_query,
        filters=filters,
    )
    important_ignored_filters = {
        key: value
        for key, value in ignored_filters.items()
        if _normalize_key(key) in IMPORTANT_FILTER_KEYS
    }

    return RetrievalIntentProfile(
        raw_query=base_query,
        normalized_query=normalized_query,
        filters=filters,
        query_topics=query_topics,
        query_tags=query_tags,
        query_terms=query_terms,
        ignored_filters=ignored_filters,
        important_ignored_filters=important_ignored_filters,
    )
