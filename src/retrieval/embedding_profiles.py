from __future__ import annotations

from typing import Any

EMBEDDING_PROFILE_SETS: dict[str, dict[str, dict[str, Any]]] = {
    "v1": {
        "embedding_a": {
            "label": "name + details + discovery metadata",
            "fields": [
                "name",
                "details",
                "tags",
                "topics",
                "level",
                "provider",
                "provider_type",
                "state",
                "ministry",
            ],
            "purpose": "what the scheme is",
        },
        "embedding_b": {
            "label": "eligibility + benefits + fit metadata",
            "fields": [
                "eligibility",
                "benefits",
                "tags",
                "topics",
                "level",
                "state",
            ],
            "purpose": "who qualifies and what they get",
        },
    },
    "v2": {
        "embedding_a": {
            "label": "name + details",
            "fields": [
                "name",
                "details",
            ],
            "purpose": "what the scheme is",
        },
        "embedding_b": {
            "label": "eligibility + benefits",
            "fields": [
                "eligibility",
                "benefits",
            ],
            "purpose": "who qualifies and what they get",
        },
    },
}


def embedding_profiles_for_version(version: str) -> dict[str, dict[str, Any]]:
    try:
        return EMBEDDING_PROFILE_SETS[version]
    except KeyError as exc:
        available_versions = ", ".join(sorted(EMBEDDING_PROFILE_SETS))
        raise ValueError(
            f"Unsupported embedding profile version {version!r}. "
            f"Expected one of: {available_versions}."
        ) from exc
