from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from pymongo import MongoClient

from src.config.settings import settings


class CandidateScheme(BaseModel):
    """Externally sourced scheme candidate to audit against MongoDB coverage."""

    name: str
    url: str
    source: str | None = None
    notes: str | None = None


class CandidateSchemeAuditResult(BaseModel):
    """Coverage result for a single candidate scheme."""

    candidate: CandidateScheme
    status: str
    canonical_url: str
    supported_scrape_url: bool
    matched_by_url: list[dict[str, Any]] = Field(default_factory=list)
    matched_by_name: list[dict[str, Any]] = Field(default_factory=list)
    matched_by_keyword: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(query="", fragment="", path=path).geturl()


def is_supported_scheme_url(url: str) -> bool:
    parsed = urlparse(canonicalize_url(url))
    base = urlparse(settings.base_url)
    return (
        parsed.scheme == base.scheme
        and parsed.netloc == base.netloc
        and parsed.path.startswith("/schemes/")
    )


def _extract_keywords(name: str) -> list[str]:
    parts = re.findall(r"[A-Za-z0-9]+", name.lower())
    keywords = [part for part in parts if len(part) >= 4]
    seen: set[str] = set()
    unique: list[str] = []
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        unique.append(keyword)
    return unique[:4]


def _normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[A-Za-z0-9]+", value.lower()))


def _keyword_overlap_count(candidate_name: str, document_name: str) -> int:
    candidate_keywords = set(_extract_keywords(candidate_name))
    document_keywords = set(_extract_keywords(document_name))
    if not candidate_keywords or not document_keywords:
        return 0
    return len(candidate_keywords.intersection(document_keywords))


def _mongo_projection() -> dict[str, int]:
    return {
        "_id": 0,
        "name": 1,
        "url": 1,
        "provider": 1,
        "level": 1,
        "tags": 1,
        "topics": 1,
    }


def _recommendation(
    *,
    supported_scrape_url: bool,
    matched_by_url: list[dict[str, Any]],
    matched_by_name: list[dict[str, Any]],
    matched_by_keyword: list[dict[str, Any]],
) -> str:
    if matched_by_url:
        return "already_present_by_url"
    if matched_by_name:
        return "review_name_match_before_scraping"
    if matched_by_keyword:
        return "review_possible_alias_before_scraping"
    if supported_scrape_url:
        return "scrape_and_upsert_into_main_collections"
    return "manual_review_external_source"


def audit_candidate_schemes(
    *,
    candidates: list[CandidateScheme],
    mongo_uri: str = settings.mongodb_uri,
    database_name: str = settings.database_name,
    raw_collection: str = settings.mongo.schemes_collection,
) -> list[CandidateSchemeAuditResult]:
    client = MongoClient(mongo_uri)
    try:
        collection = client[database_name][raw_collection]
        results: list[CandidateSchemeAuditResult] = []
        for candidate in candidates:
            canonical_url = canonicalize_url(candidate.url)
            supported = is_supported_scheme_url(canonical_url)
            matched_by_url = list(
                collection.find({"url": canonical_url}, _mongo_projection()).limit(5)
            )
            matched_by_name = list(
                collection.find(
                    {"name": {"$regex": f"^{re.escape(candidate.name)}$", "$options": "i"}},
                    _mongo_projection(),
                ).limit(5)
            )

            keyword_clauses = [
                {"name": {"$regex": keyword, "$options": "i"}}
                for keyword in _extract_keywords(candidate.name)
            ]
            matched_by_keyword = []
            if keyword_clauses:
                keyword_candidates = list(
                    collection.find({"$or": keyword_clauses}, _mongo_projection()).limit(20)
                )
                normalized_candidate_name = _normalize_name(candidate.name)
                ranked_keyword_matches: list[tuple[int, dict[str, Any]]] = []
                for document in keyword_candidates:
                    document_name = str(document.get("name") or "")
                    overlap = _keyword_overlap_count(candidate.name, document_name)
                    if (
                        overlap < 2
                        and normalized_candidate_name not in _normalize_name(document_name)
                    ):
                        continue
                    ranked_keyword_matches.append((overlap, document))
                ranked_keyword_matches.sort(
                    key=lambda item: (item[0], len(str(item[1].get("name") or ""))),
                    reverse=True,
                )
                matched_by_keyword = [
                    document for _, document in ranked_keyword_matches[:5]
                ]

            recommendation = _recommendation(
                supported_scrape_url=supported,
                matched_by_url=matched_by_url,
                matched_by_name=matched_by_name,
                matched_by_keyword=matched_by_keyword,
            )
            if matched_by_url:
                status = "present_by_url"
            elif matched_by_name:
                status = "present_by_name"
            elif matched_by_keyword:
                status = "possible_alias_match"
            elif supported:
                status = "missing_supported_scrape_target"
            else:
                status = "missing_external_source"

            results.append(
                CandidateSchemeAuditResult(
                    candidate=candidate,
                    status=status,
                    canonical_url=canonical_url,
                    supported_scrape_url=supported,
                    matched_by_url=matched_by_url,
                    matched_by_name=matched_by_name,
                    matched_by_keyword=matched_by_keyword,
                    recommendation=recommendation,
                )
            )

        return results
    finally:
        client.close()


def load_candidate_schemes(path: str | Path) -> list[CandidateScheme]:
    candidate_path = Path(path)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("schemes") or payload.get("candidates") or []
    if not isinstance(payload, list):
        raise ValueError("Candidate file must contain a list or a top-level schemes/candidates list.")
    return [CandidateScheme.model_validate(item) for item in payload]
