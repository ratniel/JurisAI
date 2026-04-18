from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.config.settings import settings

ShortlistRole = Literal[
    "core_positive",
    "central_fallback",
    "distractor_wrong_state",
    "distractor_wrong_beneficiary",
    "distractor_wrong_benefit",
]
ReviewStatus = Literal["seed_reviewed", "generated", "approved", "rejected"]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def artifacts_root() -> Path:
    return Path(settings.eval.artifacts_root)


def personas_path() -> Path:
    return artifacts_root() / "personas_v1.yaml"


def shortlists_path() -> Path:
    return artifacts_root() / "shortlists_v1.yaml"


def golden_records_path() -> Path:
    return artifacts_root() / "golden_classifier_retrieval_v1.jsonl"


class GenerationProvenance(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str
    method: str
    model: str | None = None
    prompt_version: str | None = None
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
    )
    reviewed_by: str | None = None
    notes: str | None = None


class EvalPersona(BaseModel):
    model_config = ConfigDict(extra="ignore")

    persona_id: str
    title: str
    summary: str
    geography: str
    state_focus: list[str] = Field(default_factory=list)
    demographics: list[str] = Field(default_factory=list)
    language_registers: list[str] = Field(default_factory=list)
    retrieval_focus: str
    constraints: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator(
        "persona_id",
        "title",
        "summary",
        "geography",
        "retrieval_focus",
        mode="before",
    )
    @classmethod
    def _normalize_required_text(cls, value: Any) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("required persona text field cannot be empty")
        return normalized

    @field_validator("state_focus", "demographics", "language_registers", "constraints")
    @classmethod
    def _normalize_list_fields(cls, value: list[str]) -> list[str]:
        return [_normalize_text(item) for item in value if _normalize_text(item)]


class SchemeShortlistEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    persona_id: str
    role: ShortlistRole
    scheme_id: str
    scheme_name: str
    level: str
    state: str | None = None
    topics: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rationale: str
    source_url: str | None = None

    @field_validator(
        "persona_id",
        "scheme_id",
        "scheme_name",
        "level",
        "rationale",
        mode="before",
    )
    @classmethod
    def _normalize_required_text(cls, value: Any) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("required shortlist text field cannot be empty")
        return normalized

    @field_validator("state", "source_url", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str | None:
        normalized = _normalize_text(value)
        return normalized or None

    @field_validator("topics", "tags")
    @classmethod
    def _normalize_list_fields(cls, value: list[str]) -> list[str]:
        return [_normalize_text(item) for item in value if _normalize_text(item)]


class GoldenRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    record_id: str
    persona_id: str
    user_query: str
    expected_filters: dict[str, Any] = Field(default_factory=dict)
    required_query_terms: list[str] = Field(default_factory=list)
    must_retrieve_scheme_ids: list[str] = Field(default_factory=list)
    must_not_retrieve_scheme_ids: list[str] = Field(default_factory=list)
    min_recall_at_k: int = Field(ge=1, default=2)
    notes: str = ""
    generation_provenance: GenerationProvenance
    review_status: ReviewStatus = "seed_reviewed"

    @field_validator("record_id", "persona_id", "user_query", "notes", mode="before")
    @classmethod
    def _normalize_required_text(cls, value: Any) -> str:
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("required golden-record text field cannot be empty")
        return normalized

    @field_validator(
        "required_query_terms",
        "must_retrieve_scheme_ids",
        "must_not_retrieve_scheme_ids",
    )
    @classmethod
    def _normalize_list_fields(cls, value: list[str]) -> list[str]:
        return [_normalize_text(item) for item in value if _normalize_text(item)]

    @field_validator("must_retrieve_scheme_ids")
    @classmethod
    def _require_positive_labels(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError("each golden record must have at least two positives")
        return value

    @field_validator("must_not_retrieve_scheme_ids")
    @classmethod
    def _require_negative_labels(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("each golden record must have at least one distractor")
        return value


class ReviewEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    record_id: str
    persona_id: str
    status: ReviewStatus
    reviewer: str
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            payload,
            handle,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )


def load_eval_personas(path: Path | None = None) -> list[EvalPersona]:
    payload = _read_yaml(path or personas_path())
    return [EvalPersona.model_validate(item) for item in payload]


def dump_eval_personas(personas: list[EvalPersona], path: Path | None = None) -> None:
    _write_yaml(
        path or personas_path(),
        [persona.model_dump(mode="json", exclude_none=True) for persona in personas],
    )


def load_shortlist_entries(path: Path | None = None) -> list[SchemeShortlistEntry]:
    payload = _read_yaml(path or shortlists_path())
    return [SchemeShortlistEntry.model_validate(item) for item in payload]


def dump_shortlist_entries(
    entries: list[SchemeShortlistEntry],
    path: Path | None = None,
) -> None:
    _write_yaml(
        path or shortlists_path(),
        [entry.model_dump(mode="json", exclude_none=True) for entry in entries],
    )


def load_golden_records(path: Path | None = None) -> list[GoldenRecord]:
    records: list[GoldenRecord] = []
    with (path or golden_records_path()).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            records.append(GoldenRecord.model_validate(json.loads(line)))
    return records


def dump_golden_records(records: list[GoldenRecord], path: Path | None = None) -> None:
    resolved_path = path or golden_records_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json", exclude_none=True),
                    ensure_ascii=False,
                )
            )
            handle.write("\n")
