from __future__ import annotations

from typing import Any

from opentelemetry import trace
from qdrant_client import QdrantClient, models

from src.agentic.models import MongoReference, RetrievedScheme
from src.config.settings import settings
from src.llm import EmbeddingClient, build_embedding_client
from src.llm.providers import EmbeddingProviderName
from src.retrieval.query_intent import RetrievalIntentProfile
from src.retrieval.rule_engine import RETRIEVAL_FILTER_MODES, build_qdrant_filter
from src.scheme_contracts import (
    QdrantSchemeMetadata,
    SchemeRuleFilters,
    coerce_rule_filters,
    normalize_topics,
)

TRACER = trace.get_tracer(__name__)


def _merge_filters(
    query_filter: models.Filter | None,
    profile_name: str,
) -> models.Filter:
    profile_condition = models.FieldCondition(
        key="embedding_profile",
        match=models.MatchValue(value=profile_name),
    )

    if query_filter is None:
        return models.Filter(must=[profile_condition])

    must_conditions = list(query_filter.must or [])
    must_conditions.append(profile_condition)
    return models.Filter(
        must=must_conditions,
        should=query_filter.should,
        must_not=query_filter.must_not,
    )


class QdrantSchemeSearchClient:
    def __init__(
        self,
        *,
        qdrant_url: str = settings.qdrant.url,
        collection_name: str = settings.qdrant.default_collection,
        embedding_backend: EmbeddingProviderName = settings.embeddings.backend,
        embedding_model: str = settings.embedding_model(),
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self._client = QdrantClient(url=qdrant_url, api_key=settings.qdrant.api_key)
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._embedding_client = embedding_client or build_embedding_client(
            provider=embedding_backend,
            model=embedding_model,
        )
        self._dense_vector_name_cache: str | None = None
        self._dense_vector_name_resolved = False

    def search(
        self,
        *,
        query_text: str,
        raw_filters: dict[str, Any] | SchemeRuleFilters | None = None,
        intent_profile: RetrievalIntentProfile | None = None,
        limit: int = 5,
        profiles: tuple[str, ...] = settings.qdrant.profiles,
        include_debug: bool = False,
        enable_filters: bool | None = None,
        filter_mode: str | None = None,
    ) -> dict[str, Any]:
        with TRACER.start_as_current_span("jurisai.qdrant_search") as span:
            span.set_attribute("jurisai.collection", self._collection_name)
            span.set_attribute("jurisai.embedding_model", self._embedding_model)
            span.set_attribute("jurisai.limit", limit)
            span.set_attribute("jurisai.profile_count", len(profiles))
            span.set_attribute("jurisai.query_text_length", len(query_text))
            resolved_filter_mode = self._resolve_filter_mode(
                enable_filters=enable_filters,
                filter_mode=filter_mode,
            )
            filters_enabled = resolved_filter_mode != "none"
            normalized_filters, ignored_filters = coerce_rule_filters(raw_filters)
            candidate_filters = normalized_filters.model_dump(exclude_none=True)
            query_filter = None
            applied_filters: dict[str, Any] = {}
            if filters_enabled:
                query_filter, applied_filters, filter_ignored_filters = build_qdrant_filter(
                    normalized_filters,
                    filter_mode=resolved_filter_mode,
                )
                ignored_filters = {
                    **ignored_filters,
                    **filter_ignored_filters,
                }
            span.set_attribute("jurisai.applied_filter_count", len(applied_filters))
            span.set_attribute("jurisai.ignored_filter_count", len(ignored_filters))
            span.set_attribute("jurisai.retrieval_filters_enabled", filters_enabled)
            span.set_attribute("jurisai.retrieval_filter_mode", resolved_filter_mode)

            raw_points: list[Any] = []
            per_profile_limit = max(limit, 5)
            profile_debug: list[dict[str, Any]] = []

            for profile_name in profiles:
                profile_query_text = self._profile_query_text(
                    query_text=query_text,
                    profile_name=profile_name,
                    intent_profile=intent_profile,
                )
                query_vector = self._embedding_client.embed_text(
                    profile_query_text,
                    model=self._embedding_model,
                    task_type="RETRIEVAL_QUERY",
                )
                with TRACER.start_as_current_span(
                    "jurisai.qdrant_profile_query"
                ) as profile_span:
                    profile_span.set_attribute("jurisai.collection", self._collection_name)
                    profile_span.set_attribute("jurisai.embedding_profile", profile_name)
                    profile_span.set_attribute(
                        "jurisai.profile_query_length",
                        len(profile_query_text),
                    )
                    profile_span.set_attribute("jurisai.limit", per_profile_limit)
                    response = self._client.query_points(
                        collection_name=self._collection_name,
                        query=query_vector,
                        using=self._dense_vector_name(),
                        query_filter=_merge_filters(query_filter, profile_name),
                        limit=per_profile_limit,
                        with_payload=True,
                        with_vectors=False,
                    )
                    profile_span.set_attribute("jurisai.raw_hits", len(response.points))
                    raw_points.extend(response.points)
                    if include_debug:
                        profile_debug.append(
                            {
                                "embedding_profile": profile_name,
                                "query_text": profile_query_text,
                                "raw_hit_count": len(response.points),
                                "raw_hits": [
                                    self._debug_point_summary(point) for point in response.points
                                ],
                            }
                        )

            deduped = self._dedupe_hits(raw_points)
            ordered_hits = self._rerank_hits(
                deduped,
                filter_mode=resolved_filter_mode,
                intent_profile=intent_profile,
            )
            span.set_attribute("jurisai.raw_hit_count", len(raw_points))
            span.set_attribute("jurisai.deduped_hit_count", len(deduped))
            payload = {
                "results": [result.model_dump() for result in ordered_hits[:limit]],
                "retrieval_filters_enabled": filters_enabled,
                "retrieval_filter_mode": resolved_filter_mode,
                "candidate_filters": candidate_filters,
                "applied_filters": applied_filters,
                "ignored_filters": ignored_filters,
                "raw_hit_count": len(raw_points),
            }
            if include_debug:
                payload["debug"] = {
                    "profiles": profile_debug,
                    "deduped_hits": [result.model_dump() for result in deduped],
                }
            return payload

    def _dense_vector_name(self) -> str | None:
        if self._dense_vector_name_resolved:
            return self._dense_vector_name_cache

        vectors_config = self._client.get_collection(
            self._collection_name
        ).config.params.vectors
        self._dense_vector_name_cache = (
            settings.qdrant.dense_vector_name
            if isinstance(vectors_config, dict)
            and settings.qdrant.dense_vector_name in vectors_config
            else None
        )
        self._dense_vector_name_resolved = True
        return self._dense_vector_name_cache

    @staticmethod
    def _profile_query_text(
        *,
        query_text: str,
        profile_name: str,
        intent_profile: RetrievalIntentProfile | None,
    ) -> str:
        if intent_profile is None:
            return query_text
        if profile_name == "embedding_b":
            return intent_profile.fit_query or intent_profile.normalized_query
        return intent_profile.discovery_query or query_text

    @staticmethod
    def _resolve_filter_mode(
        *,
        enable_filters: bool | None,
        filter_mode: str | None,
    ) -> str:
        resolved_filter_mode = filter_mode or settings.workflow.retrieval_filter_mode
        if resolved_filter_mode not in RETRIEVAL_FILTER_MODES:
            raise ValueError(
                f"Unsupported retrieval filter mode {resolved_filter_mode!r}. "
                f"Expected one of: {', '.join(sorted(RETRIEVAL_FILTER_MODES))}."
            )
        if enable_filters is False:
            return "none"
        if enable_filters is True and resolved_filter_mode == "none":
            return "all"
        if enable_filters is None and not settings.workflow.retrieval_filters_enabled:
            return "none"
        return resolved_filter_mode

    @staticmethod
    def _debug_point_summary(point: Any) -> dict[str, Any]:
        payload = point.payload or {}
        metadata = QdrantSchemeMetadata.model_validate(payload)
        return {
            "scheme_id": str(metadata.scheme_id or point.id),
            "name": metadata.name,
            "state": metadata.state,
            "level": metadata.level,
            "provider": metadata.provider,
            "topics": list(metadata.topics),
            "tags": list(metadata.tags),
            "embedding_profile": payload.get("embedding_profile"),
            "score": float(point.score or 0.0),
        }

    @staticmethod
    def _dedupe_hits(points: list[Any]) -> list[RetrievedScheme]:
        best_by_scheme: dict[str, RetrievedScheme] = {}

        for point in points:
            payload = point.payload or {}
            metadata = QdrantSchemeMetadata.model_validate(payload)
            scheme_id = str(metadata.scheme_id or point.id)
            profile_name = str(payload.get("embedding_profile") or "unknown")
            profile_score = float(point.score or 0.0)
            candidate = RetrievedScheme(
                scheme_id=scheme_id,
                name=metadata.name,
                url=metadata.url,
                level=metadata.level,
                provider=metadata.provider,
                provider_type=metadata.provider_type,
                state=metadata.state,
                ministry=metadata.ministry,
                tags=list(metadata.tags),
                topics=list(metadata.topics),
                application_modes=metadata.application_modes,
                selected_fields=dict(payload.get("selected_fields") or {}),
                mongo_ref=MongoReference.model_validate(payload.get("mongo_ref") or {}),
                match_profile=profile_name,
                match_score=profile_score,
                matched_profiles=[profile_name],
                profile_scores={profile_name: profile_score},
            )

            current = best_by_scheme.get(scheme_id)
            if current is None:
                best_by_scheme[scheme_id] = candidate
                continue

            current.profile_scores[profile_name] = max(
                current.profile_scores.get(profile_name, 0.0),
                profile_score,
            )
            if profile_name not in current.matched_profiles:
                current.matched_profiles.append(profile_name)
            if candidate.match_score > current.match_score:
                best_by_scheme[scheme_id] = candidate.model_copy(
                    update={
                        "matched_profiles": current.matched_profiles,
                        "profile_scores": current.profile_scores,
                        "selected_fields": {
                            **current.selected_fields,
                            **candidate.selected_fields,
                        },
                    }
                )
            else:
                current.selected_fields = {
                    **candidate.selected_fields,
                    **current.selected_fields,
                }

        return sorted(
            best_by_scheme.values(),
            key=lambda item: item.match_score,
            reverse=True,
        )

    @staticmethod
    def _rerank_hits(
        hits: list[RetrievedScheme],
        *,
        filter_mode: str,
        intent_profile: RetrievalIntentProfile | None,
    ) -> list[RetrievedScheme]:
        if filter_mode != "state_hard_topics_soft" or intent_profile is None:
            return hits

        query_topics = normalize_topics(intent_profile.query_topics)
        if not query_topics:
            return hits

        reranked: list[RetrievedScheme] = []
        query_topic_set = set(query_topics)
        for hit in hits:
            hit_topics = normalize_topics(hit.topics)
            matched_topics = [topic for topic in hit_topics if topic in query_topic_set]
            adjusted_score = hit.match_score
            match_reasons = list(hit.match_reasons)
            if matched_topics:
                adjusted_score += 0.06 * len(matched_topics)
                match_reasons.append(
                    "Soft topic boost: " + ", ".join(matched_topics)
                )
            else:
                adjusted_score -= 0.03
                match_reasons.append("Soft topic penalty: no topic overlap")
            reranked.append(
                hit.model_copy(
                    update={
                        "adjusted_score": adjusted_score,
                        "match_reasons": match_reasons,
                    }
                )
            )

        return sorted(
            reranked,
            key=lambda item: item.adjusted_score if item.adjusted_score is not None else item.match_score,
            reverse=True,
        )
