from __future__ import annotations

from typing import Any

from opentelemetry import trace
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import QueryResponse

from src.agentic.models import MongoReference, RetrievedScheme
from src.config.settings import settings
from src.llm import EmbeddingClient, build_embedding_client
from src.llm.providers import EmbeddingProviderName
from src.retrieval.query_intent import RetrievalIntentProfile
from src.retrieval.rule_engine import RETRIEVAL_FILTER_MODES, build_qdrant_filter
from src.retrieval.sparse_keyword import build_sparse_keyword_vector
from src.scheme_contracts import (
    QdrantSchemeMetadata,
    SchemeRuleFilters,
    coerce_rule_filters,
)
from src.scheme_contracts import normalize_topics

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
        self._collection_capabilities: dict[str, bool] | None = None

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
        retrieval_strategy: str | None = None,
    ) -> dict[str, Any]:
        with TRACER.start_as_current_span("jurisai.qdrant_search") as span:
            span.set_attribute("jurisai.collection", self._collection_name)
            span.set_attribute("jurisai.embedding_model", self._embedding_model)
            span.set_attribute("jurisai.limit", limit)
            span.set_attribute("jurisai.profile_count", len(profiles))
            span.set_attribute("jurisai.query_text_length", len(query_text))
            resolved_retrieval_strategy = self._resolve_retrieval_strategy(
                retrieval_strategy=retrieval_strategy
            )
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
            span.set_attribute(
                "jurisai.retrieval_strategy",
                resolved_retrieval_strategy,
            )

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
                sparse_query_vector = build_sparse_keyword_vector(profile_query_text)
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
                    profile_span.set_attribute(
                        "jurisai.retrieval_strategy",
                        resolved_retrieval_strategy,
                    )
                    response = self._query_profile_points(
                        profile_name=profile_name,
                        query_filter=query_filter,
                        dense_query_vector=query_vector,
                        sparse_query_vector=sparse_query_vector,
                        limit=per_profile_limit,
                        retrieval_strategy=resolved_retrieval_strategy,
                    )
                    profile_span.set_attribute("jurisai.raw_hits", len(response.points))
                    raw_points.extend(response.points)
                    if include_debug:
                        profile_debug.append(
                            {
                                "embedding_profile": profile_name,
                                "retrieval_strategy": resolved_retrieval_strategy,
                                "query_text": profile_query_text,
                                "keyword_query_terms": len(sparse_query_vector.indices),
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
                "retrieval_strategy": resolved_retrieval_strategy,
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

    def _query_profile_points(
        self,
        *,
        profile_name: str,
        query_filter: models.Filter | None,
        dense_query_vector: list[float],
        sparse_query_vector: models.SparseVector,
        limit: int,
        retrieval_strategy: str,
    ) -> QueryResponse:
        merged_filter = _merge_filters(query_filter, profile_name)
        collection_capabilities = self._collection_schema_capabilities()
        dense_using = (
            settings.qdrant.dense_vector_name
            if collection_capabilities["named_dense"]
            else None
        )
        sparse_using = settings.qdrant.sparse_vector_name

        if retrieval_strategy == "dense":
            return self._client.query_points(
                collection_name=self._collection_name,
                query=dense_query_vector,
                using=dense_using,
                query_filter=merged_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

        if not collection_capabilities["sparse"]:
            raise ValueError(
                f"Collection {self._collection_name!r} does not expose sparse vectors. "
                "Re-index it with keyword sparse vectors before using sparse or hybrid retrieval."
            )

        if not sparse_query_vector.indices:
            return self._client.query_points(
                collection_name=self._collection_name,
                query=dense_query_vector,
                using=dense_using,
                query_filter=merged_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

        if retrieval_strategy == "sparse":
            return self._client.query_points(
                collection_name=self._collection_name,
                query=sparse_query_vector,
                using=sparse_using,
                query_filter=merged_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

        return self._client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query_vector,
                    using=dense_using,
                    filter=merged_filter,
                    limit=limit,
                ),
                models.Prefetch(
                    query=sparse_query_vector,
                    using=sparse_using,
                    filter=merged_filter,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

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
    def _resolve_retrieval_strategy(
        *,
        retrieval_strategy: str | None,
    ) -> str:
        resolved_strategy = retrieval_strategy or settings.workflow.retrieval_strategy
        if resolved_strategy not in {"dense", "hybrid", "sparse"}:
            raise ValueError(
                f"Unsupported retrieval strategy {resolved_strategy!r}. "
                "Expected one of: dense, hybrid, sparse."
            )
        return resolved_strategy

    def _collection_schema_capabilities(self) -> dict[str, bool]:
        if self._collection_capabilities is not None:
            return self._collection_capabilities

        collection_info = self._client.get_collection(self._collection_name)
        params = collection_info.config.params
        vectors_config = getattr(params, "vectors", None)
        sparse_config = getattr(params, "sparse_vectors", None)
        named_dense = isinstance(vectors_config, dict) and (
            settings.qdrant.dense_vector_name in vectors_config
        )
        sparse_enabled = isinstance(sparse_config, dict) and (
            settings.qdrant.sparse_vector_name in sparse_config
        )
        self._collection_capabilities = {
            "named_dense": named_dense,
            "sparse": sparse_enabled,
        }
        return self._collection_capabilities

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
