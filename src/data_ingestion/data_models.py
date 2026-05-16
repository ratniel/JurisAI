from __future__ import annotations

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel
from typing import Literal

from src.config.settings import settings
from src.scheme_contracts import SchemeSourceRecord


class RawSchemeDocument(Document):
    """Beanie document for raw scraped schemes stored in MongoDB."""

    url: str = Field(..., description="The URL of the scheme.")
    name: str = Field(..., description="The name of the scheme.")
    level: Literal["central", "state"] = Field(
        ...,
        description="Whether the scheme is central or state-level.",
    )
    provider: str = Field(
        ...,
        description="The provider of the scheme, such as a ministry or a state.",
    )
    tags: list[str] = Field(default_factory=list, description="Scheme tags.")
    details: str = Field(default="", description="The details of the scheme.")
    benefits: str = Field(default="", description="The benefits of the scheme.")
    eligibility: str = Field(default="", description="The eligibility of the scheme.")
    application_process: str = Field(
        default="",
        description="The raw application process text scraped from the source page.",
    )
    documents_required: str = Field(
        default="",
        description="The documents required for the scheme.",
    )
    faq: str = Field(
        default="",
        description="Plain-text FAQ content scraped from the source page.",
    )
    sources: list[SchemeSourceRecord] = Field(
        default_factory=list,
        description="The sources and references of the scheme.",
    )

    class Settings:
        name = settings.schemes_collection
        indexes = [
            IndexModel([("url", ASCENDING)], name="idx_scheme_url", unique=True),
            IndexModel([("name", ASCENDING)], name="idx_scheme_name"),
            IndexModel(
                [("level", ASCENDING), ("provider", ASCENDING)],
                name="idx_level_provider",
            ),
            IndexModel([("tags", ASCENDING)], name="idx_tags"),
        ]


# Backward-compatible aliases for older imports.
SchemeDetails = RawSchemeDocument
Source = SchemeSourceRecord
