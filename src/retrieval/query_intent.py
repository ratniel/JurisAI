from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.scheme_contracts import (
    SchemeRuleFilters,
    coerce_rule_filters,
    normalize_terms,
    normalize_topics,
)
from src.topic_catalog import SCHEME_TOPIC_CATALOG


def _load_controlled_tag_lookup() -> dict[str, str]:
    tags_path = Path(__file__).resolve().parents[2] / "unique_tags.json"
    try:
        payload = json.loads(tags_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    unique_tags = payload.get("unique_tags") or []
    lookup: dict[str, str] = {}
    for item in unique_tags:
        normalized = " ".join(str(item).replace("\ufeff", " ").split()).strip()
        if not normalized:
            continue
        lookup[normalized.lower()] = normalized
    return lookup

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

CONTROLLED_TAG_LOOKUP = _load_controlled_tag_lookup()

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

QUERY_HINTS: tuple[dict[str, Any], ...] = (
    {
        "terms": ("student", "students", "school", "college", "scholarship"),
        "tags": ("Student",),
        "topics": ("Education",),
        "query_terms": ("student", "education"),
    },
    {
        "terms": ("minority", "minorities", "minority community"),
        "tags": ("Minority Community",),
        "topics": (),
        "query_terms": ("minority community",),
    },
    {
        "terms": ("disabled", "disability", "pwd", "person with disability"),
        "tags": ("Person With Disability",),
        "topics": ("Disability Support",),
        "query_terms": ("disability support", "person with disability"),
    },
    {
        "terms": ("women", "woman", "female", "girl", "girls", "mahila"),
        "tags": ("Women", "Girl"),
        "topics": ("Women Welfare",),
        "query_terms": ("women welfare",),
    },
    {
        "terms": ("child", "children", "kid", "kids"),
        "tags": (),
        "topics": ("Child Welfare",),
        "query_terms": ("child welfare",),
    },
    {
        "terms": ("farmer", "farmers", "farming", "agriculture", "kisan", "crop", "fasal"),
        "tags": ("Farmer",),
        "topics": ("Agriculture",),
        "query_terms": ("agriculture",),
    },
    {
        "terms": ("job", "jobs", "employment", "unemployment"),
        "tags": (),
        "topics": ("Employment",),
        "query_terms": ("employment",),
    },
    {
        "terms": ("training", "skill", "skills", "apprentice", "apprenticeship"),
        "tags": (),
        "topics": ("Skill Development",),
        "query_terms": ("skill development",),
    },
    {
        "terms": ("loan", "credit", "bank", "banking", "finance"),
        "tags": ("Loan",),
        "topics": ("Financial Inclusion",),
        "query_terms": ("financial inclusion", "loan"),
    },
    {
        "terms": ("health", "medical", "hospital", "treatment", "insurance"),
        "tags": ("Insurance",),
        "topics": ("Healthcare",),
        "query_terms": ("healthcare",),
    },
)


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


def _looks_like_free_text_tag(value: str) -> bool:
    return bool(value) and value == value.lower() and " " not in value


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


def _infer_topics_from_text(text: str) -> list[str]:
    lowered = _normalize_text(text).lower()
    inferred: list[str] = []

    for definition in SCHEME_TOPIC_CATALOG.topics:
        topic_name = definition.label.lower()
        if topic_name in lowered:
            inferred.append(definition.label)
            continue

        for term in definition.indicative_terms:
            if term.lower() in lowered:
                inferred.append(definition.label)
                break

    return normalize_topics(inferred)


def _infer_state_from_text(text: str) -> str | None:
    lowered = f" {_normalize_text(text).lower()} "
    for alias, canonical in STATE_ALIASES:
        if f" {alias} " in lowered:
            return canonical
    return None


def _is_agriculture_insurance_context(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    has_insurance = "insurance" in lowered
    has_agriculture = any(
        term in lowered
        for term in ("farmer", "farmers", "farming", "agriculture", "kisan", "crop", "fasal")
    )
    return has_insurance and has_agriculture


def _normalize_inferred_topics(text: str, topics: list[str]) -> list[str]:
    normalized_topics = _merge_unique([], topics)
    if (
        _is_agriculture_insurance_context(text)
        and "Agriculture" in normalized_topics
        and "Healthcare" in normalized_topics
    ):
        return [topic for topic in normalized_topics if topic != "Healthcare"]
    return normalized_topics


def _apply_query_hints(
    *,
    text: str,
    query_tags: list[str],
    query_topics: list[str],
    query_terms: list[str],
) -> tuple[list[str], list[str], list[str]]:
    lowered = _normalize_text(text).lower()
    agriculture_insurance_context = _is_agriculture_insurance_context(text)
    for hint in QUERY_HINTS:
        if not any(term in lowered for term in hint["terms"]):
            continue
        if agriculture_insurance_context and "insurance" in hint["terms"]:
            continue
        query_tags = _merge_unique(query_tags, list(hint["tags"]))
        query_topics = _merge_unique(query_topics, list(hint["topics"]))
        query_terms = _merge_unique(query_terms, list(hint["query_terms"]))
    return query_tags, query_topics, query_terms


def _canonicalize_raw_filters(
    raw_filters: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str], list[str], list[str], dict[str, Any]]:
    pending: dict[str, Any] = {}
    query_tags: list[str] = []
    query_topics: list[str] = []
    query_terms: list[str] = []
    ignored_filters: dict[str, Any] = {}

    for key, value in (raw_filters or {}).items():
        if value in (None, "", [], {}):
            continue

        lowered_key = _normalize_key(key)
        canonical_key = SPECIAL_FILTER_KEY_ALIASES.get(lowered_key, lowered_key)
        values = normalize_terms(value)

        if canonical_key in {"demographic", "occupation", "community", "category"}:
            normalized_text = " ".join(values)
            query_tags, query_topics, query_terms = _apply_query_hints(
                text=normalized_text,
                query_tags=query_tags,
                query_topics=query_topics,
                query_terms=query_terms,
            )
            if not query_terms:
                query_terms = _merge_unique(query_terms, values)
            continue

        if canonical_key == "topics":
            pending["topics"] = _merge_unique(
                list(pending.get("topics") or []),
                normalize_topics(values),
            )
            continue

        if canonical_key == "tags":
            recognized_tags: list[str] = []
            unknown_tags: list[str] = []
            for item in values:
                normalized = _normalize_text(item)
                if _looks_like_free_text_tag(normalized):
                    query_tags, query_topics, query_terms = _apply_query_hints(
                        text=normalized,
                        query_tags=query_tags,
                        query_topics=query_topics,
                        query_terms=query_terms,
                    )
                    query_terms = _merge_unique(query_terms, [normalized])
                    continue
                canonical_tag = CONTROLLED_TAG_LOOKUP.get(normalized.lower())
                if canonical_tag:
                    recognized_tags.append(canonical_tag)
                else:
                    unknown_tags.append(normalized)
            pending["tags"] = _merge_unique(
                list(pending.get("tags") or []),
                recognized_tags,
            )
            if unknown_tags:
                query_tags, query_topics, query_terms = _apply_query_hints(
                    text=" ".join(unknown_tags),
                    query_tags=query_tags,
                    query_topics=query_topics,
                    query_terms=query_terms,
                )
                query_terms = _merge_unique(query_terms, unknown_tags)
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

    return pending, query_tags, query_topics, query_terms, ignored_filters


def _build_normalized_query(
    *,
    query_text: str,
    filters: SchemeRuleFilters,
    query_topics: list[str],
    query_tags: list[str],
    query_terms: list[str],
) -> str:
    normalized = _normalize_text(query_text)
    lowered = normalized.lower()
    additions: list[str] = []

    for term in query_terms:
        if term.lower() not in lowered:
            additions.append(term)

    for tag in query_tags:
        if tag.lower() not in lowered:
            additions.append(tag)

    for topic in query_topics:
        if topic.lower() not in lowered:
            additions.append(topic)

    if filters.state and filters.state.lower() not in lowered:
        additions.append(filters.state)

    if filters.application_mode and filters.application_mode.lower() not in lowered:
        additions.append(filters.application_mode)

    if additions:
        return " ".join([normalized, *additions]).strip()
    return normalized


def build_retrieval_intent_profile(
    *,
    user_message: str,
    retrieval_query: str | None,
    raw_filters: dict[str, Any] | None,
) -> RetrievalIntentProfile:
    base_query = _normalize_text(retrieval_query) or _normalize_text(user_message)
    pending_filters, query_tags, query_topics, query_terms, ignored_filters = (
        _canonicalize_raw_filters(raw_filters)
    )

    if not pending_filters.get("state"):
        inferred_state = _infer_state_from_text(f"{user_message} {base_query}")
        if inferred_state:
            pending_filters["state"] = inferred_state

    query_tags, query_topics, query_terms = _apply_query_hints(
        text=base_query,
        query_tags=query_tags,
        query_topics=query_topics,
        query_terms=query_terms,
    )
    query_topics = _normalize_inferred_topics(
        base_query,
        _merge_unique(query_topics, _infer_topics_from_text(base_query)),
    )
    if not pending_filters.get("topics") and len(query_topics) == 1:
        pending_filters["topics"] = list(query_topics)

    filters, coerced_ignored_filters = coerce_rule_filters(pending_filters)
    ignored_filters = {
        **ignored_filters,
        **coerced_ignored_filters,
    }

    normalized_query = _build_normalized_query(
        query_text=base_query,
        filters=filters,
        query_topics=query_topics,
        query_tags=query_tags,
        query_terms=query_terms,
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
