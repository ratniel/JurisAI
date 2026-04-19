from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from src.topic_catalog import CONTROLLED_TOPIC_SET, CONTROLLED_TOPICS

SchemeLevel = Literal["central", "state"]
ProviderType = Literal["state", "ministry", "other"]
ApplicationMode = Literal["online", "offline"]


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_terms(value: Any) -> list[str]:
    if value in (None, "", [], ()):
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        normalized = [normalize_text(item) for item in value]
        return [item for item in normalized if item is not None]
    normalized_value = normalize_text(value)
    return [normalized_value] if normalized_value is not None else []


def normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "online"}:
        return True
    if lowered in {"false", "0", "no", "offline"}:
        return False
    return None


def faq_mapping_to_text(value: dict[str, Any]) -> str:
    chunks: list[str] = []
    for question, answer in value.items():
        question_text = normalize_text(question)
        answer_text = normalize_text(answer)
        if question_text is None and answer_text is None:
            continue

        lines: list[str] = []
        if question_text is not None:
            lines.append(f"Q: {question_text}")
        if answer_text is not None:
            lines.append(f"A: {answer_text}")
        if lines:
            chunks.append("\n".join(lines))

    return "\n\n".join(chunks).strip()


def normalize_faq_text(value: Any) -> str:
    if value in (None, "", [], (), {}):
        return ""
    if isinstance(value, dict):
        return faq_mapping_to_text(value)
    if isinstance(value, (list, tuple)):
        parts = [normalize_faq_text(item) for item in value]
        return "\n\n".join(part for part in parts if part).strip()
    normalized = normalize_text(value)
    return normalized or ""


def normalize_topics(value: Any) -> list[str]:
    seen: set[str] = set()
    topics: list[str] = []
    for topic in normalize_terms(value):
        if topic not in CONTROLLED_TOPIC_SET or topic in seen:
            continue
        seen.add(topic)
        topics.append(topic)
    return sorted(topics, key=CONTROLLED_TOPICS.index)


class SchemeSourceRecord(BaseModel):
    """Normalized source entry stored alongside a scheme document."""

    model_config = ConfigDict(extra="ignore")

    text: str | None = None
    url: str | None = None


class EnrichedApplicationModes(BaseModel):
    """Human-readable online and offline application instructions for a scheme."""

    model_config = ConfigDict(extra="ignore")

    online: str | None = None
    offline: str | None = None

    @field_validator("online", "offline", mode="before")
    @classmethod
    def _normalize_mode_text(cls, value: Any) -> str | None:
        return normalize_text(value)

    def to_filterable(self) -> "FilterableApplicationModes":
        return FilterableApplicationModes(
            online=bool(normalize_text(self.online)),
            offline=bool(normalize_text(self.offline)),
        )


class FilterableApplicationModes(BaseModel):
    """Boolean application-mode flags used in retrieval filters and payloads."""

    model_config = ConfigDict(extra="ignore")

    online: bool = False
    offline: bool = False

    @field_validator("online", "offline", mode="before")
    @classmethod
    def _normalize_bool_value(cls, value: Any) -> bool:
        normalized = normalize_bool(value)
        return normalized if normalized is not None else False


class SchemeDocumentBase(BaseModel):
    """Shared normalized fields used by raw and enriched scheme documents."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )

    document_id: str | None = Field(default=None, alias="_id")
    url: str
    name: str
    level: SchemeLevel
    provider: str
    tags: list[str] = Field(default_factory=list)
    details: str = ""
    benefits: str = ""
    eligibility: str = ""
    documents_required: str = ""
    faq: str = Field(
        default="",
        validation_alias=AliasChoices("faq", "faq_text", "faqs"),
    )
    sources: list[SchemeSourceRecord] = Field(default_factory=list)

    @field_validator("document_id", mode="before")
    @classmethod
    def _normalize_document_id(cls, value: Any) -> str | None:
        return normalize_text(value)

    @field_validator("level", mode="before")
    @classmethod
    def _normalize_level(cls, value: Any) -> str | None:
        normalized = normalize_text(value)
        return normalized.lower() if normalized is not None else None

    @field_validator(
        "url",
        "name",
        "provider",
        "details",
        "benefits",
        "eligibility",
        "documents_required",
        mode="before",
    )
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        return normalize_text(value) or ""

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tag_lists(cls, value: Any) -> list[str]:
        return normalize_terms(value)

    @field_validator("faq", mode="before")
    @classmethod
    def _normalize_faq(cls, value: Any) -> str:
        return normalize_faq_text(value)

    @field_validator("sources", mode="before")
    @classmethod
    def _normalize_sources(
        cls,
        value: Any,
    ) -> list[dict[str, Any] | SchemeSourceRecord]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        raise TypeError("sources must be a list")


class RawSchemeData(SchemeDocumentBase):
    """Normalized raw scheme document that still includes scraped source-only fields."""

    application_process: str = ""

    @field_validator("application_process", mode="before")
    @classmethod
    def _normalize_application_process(cls, value: Any) -> str:
        return normalize_text(value) or ""


class EnrichedSchemeData(SchemeDocumentBase):
    """Derived scheme document used for retrieval, indexing, and chat hydration."""

    topics: list[str] = Field(default_factory=list)
    provider_type: ProviderType = "other"
    state: str | None = None
    ministry: str | None = None
    application_modes: EnrichedApplicationModes = Field(
        default_factory=EnrichedApplicationModes
    )

    @field_validator("topics", mode="before")
    @classmethod
    def _normalize_topics(cls, value: Any) -> list[str]:
        return normalize_topics(value)

    @field_validator("state", "ministry", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str | None:
        return normalize_text(value)

    def to_qdrant_metadata(self) -> "QdrantSchemeMetadata":
        return QdrantSchemeMetadata(
            scheme_id=self.document_id or self.url,
            name=self.name,
            url=self.url,
            level=self.level,
            provider=self.provider,
            provider_type=self.provider_type,
            state=self.state,
            ministry=self.ministry,
            tags=self.tags,
            topics=self.topics,
            application_modes=self.application_modes.to_filterable(),
        )


class EnrichedSchemeDerivedFields(BaseModel):
    """Deterministically derived metadata extracted from a raw scheme record."""

    model_config = ConfigDict(extra="ignore")

    provider_type: ProviderType = "other"
    state: str | None = None
    ministry: str | None = None
    application_modes: EnrichedApplicationModes = Field(
        default_factory=EnrichedApplicationModes
    )
    topics: list[str] = Field(default_factory=list)

    @field_validator("state", "ministry", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str | None:
        return normalize_text(value)

    @field_validator("topics", mode="before")
    @classmethod
    def _normalize_topics(cls, value: Any) -> list[str]:
        return normalize_topics(value)


class QdrantSchemeMetadata(BaseModel):
    """Compact scheme metadata stored on each Qdrant payload."""

    model_config = ConfigDict(extra="ignore")

    scheme_id: str
    name: str | None = None
    url: str | None = None
    level: SchemeLevel | None = None
    provider: str | None = None
    provider_type: ProviderType | None = None
    state: str | None = None
    ministry: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    application_modes: FilterableApplicationModes = Field(
        default_factory=FilterableApplicationModes
    )

    @classmethod
    def from_mongo_document(
        cls,
        document: EnrichedSchemeData,
    ) -> "QdrantSchemeMetadata":
        return document.to_qdrant_metadata()


class SchemeRuleFilters(BaseModel):
    """Canonical retrieval filters supported by the deterministic rule engine."""

    model_config = ConfigDict(extra="ignore")

    state: str | None = None
    level: SchemeLevel | None = None
    provider: str | None = None
    provider_type: ProviderType | None = None
    ministry: str | None = None
    application_mode: ApplicationMode | None = None
    online: bool | None = None
    offline: bool | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)

    @field_validator(
        "state",
        "provider",
        "ministry",
        mode="before",
    )
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str | None:
        return normalize_text(value)

    @field_validator(
        "level",
        "provider_type",
        "application_mode",
        mode="before",
    )
    @classmethod
    def _normalize_literal_fields(cls, value: Any) -> str | None:
        normalized = normalize_text(value)
        return normalized.lower() if normalized is not None else None

    @field_validator("online", "offline", mode="before")
    @classmethod
    def _normalize_boolean_fields(cls, value: Any) -> bool | None:
        return normalize_bool(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tag_list_fields(cls, value: Any) -> list[str]:
        return normalize_terms(value)

    @field_validator("topics", mode="before")
    @classmethod
    def _normalize_topic_list_fields(cls, value: Any) -> list[str]:
        return normalize_topics(value)


RULE_FILTER_ALIASES: dict[str, str] = {
    "application_mode": "application_mode",
    "geography": "state",
    "level": "level",
    "location": "state",
    "ministry": "ministry",
    "mode": "application_mode",
    "offline": "offline",
    "online": "online",
    "provider": "provider",
    "provider_type": "provider_type",
    "state_name": "state",
    "state": "state",
    "tag": "tags",
    "tags": "tags",
    "topic": "topics",
    "topics": "topics",
}


def coerce_rule_filters(
    raw_filters: dict[str, Any] | SchemeRuleFilters | None,
) -> tuple[SchemeRuleFilters, dict[str, Any]]:
    if raw_filters is None:
        return SchemeRuleFilters(), {}

    if isinstance(raw_filters, SchemeRuleFilters):
        return raw_filters, {}

    pending: dict[str, Any] = {}
    ignored_filters: dict[str, Any] = {}

    for key, value in raw_filters.items():
        if value in (None, "", [], {}):
            continue

        lowered_key = key.strip().lower()
        canonical_key = RULE_FILTER_ALIASES.get(lowered_key)
        if canonical_key is None:
            ignored_filters[key] = value
            continue
        pending[canonical_key] = value

    while True:
        try:
            return SchemeRuleFilters.model_validate(pending), ignored_filters
        except ValidationError as exc:
            invalid_fields = {
                str(error["loc"][0]) for error in exc.errors() if error["loc"]
            }
            if not invalid_fields:
                raise

            for field_name in invalid_fields:
                if field_name in pending:
                    ignored_filters[field_name] = pending.pop(field_name)


# Backward-compatible alias for existing imports that still refer to the
# enriched Mongo contract.
SchemeMongoDocument = EnrichedSchemeData
