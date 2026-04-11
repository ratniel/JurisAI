from __future__ import annotations

import re
from typing import Any

from src.data_ingestion.topic_taxonomy import infer_topics_from_tags
from src.scheme_contracts import (
    EnrichedApplicationModes,
    EnrichedSchemeData,
    EnrichedSchemeDerivedFields,
    RawSchemeData,
)

MODE_HEADER_RE = re.compile(r"^\s*(Online|Offline)\s*$", flags=re.IGNORECASE)
ONLINE_CUE_RE = re.compile(
    r"\bonline\b|\bportal\b|\bwebsite\b|\blogin\b|\bapply online\b",
    flags=re.IGNORECASE,
)
OFFLINE_CUE_RE = re.compile(
    r"\boffline\b|\bvisit\b|\bsubmit\b|\bdistrict office\b|\bfield office\b|\bhard copy\b",
    flags=re.IGNORECASE,
)


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.replace("\ufeff", " ")
    return " ".join(cleaned.split()).strip()


def derive_provider_fields(level: str | None, provider: str | None) -> dict[str, Any]:
    provider_text = normalize_whitespace(provider)
    lowered_level = (level or "").strip().lower()

    provider_type = "other"
    state: str | None = None
    ministry: str | None = None

    if lowered_level == "state" and provider_text:
        provider_type = "state"
        state = provider_text
    elif lowered_level == "central" and provider_text:
        provider_type = "ministry"
        ministry = provider_text

    return {
        "provider_type": provider_type,
        "state": state,
        "ministry": ministry,
    }


def extract_application_modes(
    application_process: str | None,
) -> EnrichedApplicationModes:
    modes: dict[str, str | None] = {
        "online": None,
        "offline": None,
    }
    if not application_process:
        return EnrichedApplicationModes.model_validate(modes)

    raw_text = (
        application_process.replace("\ufeff", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    raw_lines = [line.strip() for line in raw_text.splitlines()]
    lines = [line for line in raw_lines if line]

    current_mode: str | None = None
    buffers: dict[str, list[str]] = {
        "online": [],
        "offline": [],
    }
    seen_headers: list[str] = []
    unscoped_lines: list[str] = []

    for line in lines:
        header_match = MODE_HEADER_RE.match(line)
        if header_match:
            current_mode = header_match.group(1).lower()
            seen_headers.append(current_mode)
            continue

        if current_mode is None:
            unscoped_lines.append(line)
            continue

        buffers[current_mode].append(line)

    if unscoped_lines and not any(buffers.values()):
        shared_block = normalize_whitespace("\n".join(unscoped_lines))
        online_cues = len(ONLINE_CUE_RE.findall(shared_block))
        offline_cues = len(OFFLINE_CUE_RE.findall(shared_block))
        if online_cues and not offline_cues:
            modes["online"] = shared_block
            return EnrichedApplicationModes.model_validate(modes)
        if offline_cues and not online_cues:
            modes["offline"] = shared_block
            return EnrichedApplicationModes.model_validate(modes)
        if online_cues and offline_cues:
            modes["online"] = shared_block
            modes["offline"] = shared_block
            return EnrichedApplicationModes.model_validate(modes)
        return EnrichedApplicationModes.model_validate(modes)

    for mode, content_lines in buffers.items():
        content = normalize_whitespace("\n".join(content_lines))
        if content:
            modes[mode] = content

    populated_modes = [mode for mode, value in modes.items() if normalize_whitespace(value)]
    empty_seen_modes = [
        mode for mode in set(seen_headers) if not normalize_whitespace(modes[mode])
    ]
    if len(populated_modes) == 1 and empty_seen_modes:
        populated_mode = populated_modes[0]
        content = modes[populated_mode] or ""
        online_cues = len(ONLINE_CUE_RE.findall(content))
        offline_cues = len(OFFLINE_CUE_RE.findall(content))

        if (
            populated_mode == "offline"
            and online_cues > offline_cues
            and online_cues > 0
        ):
            modes["online"] = content
            modes["offline"] = None

    return EnrichedApplicationModes.model_validate(modes)


def compute_enriched_fields(
    raw_document: RawSchemeData | dict[str, Any],
) -> EnrichedSchemeDerivedFields:
    raw_scheme = (
        raw_document
        if isinstance(raw_document, RawSchemeData)
        else RawSchemeData.model_validate(raw_document)
    )
    provider_fields = derive_provider_fields(
        raw_scheme.level,
        raw_scheme.provider,
    )
    application_modes = extract_application_modes(raw_scheme.application_process)
    topics = infer_topics_from_tags(raw_scheme.tags or [])

    return EnrichedSchemeDerivedFields.model_validate(
        {
            **provider_fields,
            "application_modes": application_modes,
            "topics": topics,
        }
    )


def build_enriched_scheme(
    raw_document: RawSchemeData | dict[str, Any],
) -> EnrichedSchemeData:
    raw_scheme = (
        raw_document
        if isinstance(raw_document, RawSchemeData)
        else RawSchemeData.model_validate(raw_document)
    )
    enriched_fields = compute_enriched_fields(raw_scheme)
    payload = raw_scheme.model_dump(by_alias=True)
    payload.pop("application_process", None)
    payload.update(enriched_fields.model_dump())
    return EnrichedSchemeData.model_validate(payload)


def dump_enriched_scheme_for_storage(document: EnrichedSchemeData) -> dict[str, Any]:
    payload = document.model_dump(by_alias=True, exclude_none=True)
    payload["application_modes"] = document.application_modes.model_dump()
    return payload
