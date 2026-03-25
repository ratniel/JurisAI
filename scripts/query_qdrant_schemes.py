from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.llm import build_embedding_client


def build_filter(profile_name: str | None) -> models.Filter | None:
    if not profile_name:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="embedding_profile",
                match=models.MatchValue(value=profile_name),
            )
        ]
    )


def dedupe_hits(points: list[Any]) -> list[dict[str, Any]]:
    best_by_scheme: dict[str, dict[str, Any]] = {}
    for point in points:
        payload = point.payload or {}
        scheme_id = payload.get("scheme_id") or str(point.id)
        current = best_by_scheme.get(scheme_id)
        candidate = {
            "score": point.score,
            "name": payload.get("name"),
            "profile": payload.get("embedding_profile"),
            "profile_label": payload.get("embedding_profile_label"),
            "level": payload.get("level"),
            "provider": payload.get("provider"),
            "mongo_ref": payload.get("mongo_ref"),
            "url": payload.get("url"),
        }
        if current is None or candidate["score"] > current["score"]:
            best_by_scheme[scheme_id] = candidate

    return sorted(best_by_scheme.values(), key=lambda item: item["score"], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a semantic query against Qdrant scheme vectors."
    )
    parser.add_argument("--query", required=True, help="Query text to embed and search.")
    parser.add_argument(
        "--collection",
        default=settings.qdrant.default_collection,
        help="Qdrant collection name.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["local", "gemini"],
        default=settings.embeddings.backend,
        help="Embedding backend to use for the query.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Optional embedding model override.",
    )
    parser.add_argument(
        "--qdrant-url",
        default=settings.qdrant.url,
        help="Qdrant HTTP URL.",
    )
    parser.add_argument(
        "--profile",
        choices=["embedding_a", "embedding_b"],
        default=None,
        help="Optional filter to a single embedding profile.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Number of raw hits to request before dedupe.",
    )
    args = parser.parse_args()

    embedding_model = args.embedding_model or settings.embedding_model(
        args.embedding_backend
    )

    embedding_client = build_embedding_client(
        provider=args.embedding_backend,
        model=embedding_model,
    )
    query_vector = embedding_client.embed_text(
        args.query,
        model=embedding_model,
        task_type="RETRIEVAL_QUERY",
    )

    client = QdrantClient(url=args.qdrant_url, api_key=settings.qdrant.api_key)
    response = client.query_points(
        collection_name=args.collection,
        query=query_vector,
        query_filter=build_filter(args.profile),
        limit=args.limit,
        with_payload=True,
        with_vectors=False,
    )

    deduped = dedupe_hits(response.points)
    print(
        f"Query={args.query!r} collection={args.collection!r} profile={args.profile!r} "
        f"raw_hits={len(response.points)} deduped_hits={len(deduped)}"
    )
    for index, hit in enumerate(deduped, start=1):
        mongo_ref = hit["mongo_ref"] or {}
        print(
            f"{index}. score={hit['score']:.4f} profile={hit['profile']} "
            f"name={hit['name']!r} level={hit['level']!r} provider={hit['provider']!r}"
        )
        print(
            "   "
            f"mongo_ref={mongo_ref.get('database')}.{mongo_ref.get('collection')}"
            f":{mongo_ref.get('document_id')} url={mongo_ref.get('url')}"
        )


if __name__ == "__main__":
    main()
