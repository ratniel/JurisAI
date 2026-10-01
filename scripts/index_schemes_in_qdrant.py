from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ValidationError
from pymongo import AsyncMongoClient
from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.llm import build_embedding_client
from src.llm.embedding_text_formatter import NOMIC_TEXT_MODELS_REQUIRING_PREFIXES
from src.retrieval.embedding_profiles import embedding_profiles_for_version
from src.retrieval.sparse_keyword import build_sparse_keyword_vector
from src.scheme_contracts import EnrichedSchemeData, QdrantSchemeMetadata


def available_embed_fields() -> list[str]:
    return sorted(
        field_name
        for field_name in EnrichedSchemeData.model_fields
        if field_name != "document_id"
    )


def serialize_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(
            f"{key}: {rendered}"
            for key, item in value.items()
            if (rendered := stringify_value(item))
        )
    if isinstance(value, list):
        return "\n".join(
            rendered for item in value if (rendered := stringify_value(item))
        )
    return str(value).strip()


def build_embedding_document(
    scheme: EnrichedSchemeData,
    fields: list[str],
) -> tuple[str, dict[str, Any]]:
    selected_payload: dict[str, Any] = {}
    sections: list[str] = []
    for field in fields:
        serialized_value = serialize_value(getattr(scheme, field, None))
        selected_payload[field] = serialized_value
        rendered_value = stringify_value(serialized_value)
        if rendered_value:
            sections.append(f"{field}: {rendered_value}")
    return "\n\n".join(sections).strip(), selected_payload


def truncate_embedding_text(
    text: str,
    *,
    max_characters: int | None,
) -> tuple[str, int, bool]:
    original_length = len(text)
    if max_characters is None or original_length <= max_characters:
        return text, original_length, False
    return text[:max_characters].rstrip(), original_length, True


def qdrant_point_id_for_scheme(url: str, profile_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{url}#{profile_name}"))


def build_payload(
    *,
    scheme: EnrichedSchemeData,
    selected_fields: dict[str, Any],
    profile: dict[str, Any],
    profile_name: str,
    profile_version: str,
    embedded_text_length: int,
    embedded_text_original_length: int,
    embedded_text_truncated: bool,
    embedding_backend: str,
    embedding_model: str,
    database_name: str,
    source_collection: str,
) -> dict[str, Any]:
    metadata = QdrantSchemeMetadata.from_mongo_document(scheme)
    return {
        "mongo_ref": {
            "database": database_name,
            "collection": source_collection,
            "document_id": metadata.scheme_id,
            "url": metadata.url,
        },
        **metadata.model_dump(),
        "embedding_profile": profile_name,
        "embedding_profile_version": profile_version,
        "embedding_profile_label": profile["label"],
        "embedding_profile_purpose": profile["purpose"],
        "embedded_fields": profile["fields"],
        "embedded_text_length": embedded_text_length,
        "embedded_text_original_length": embedded_text_original_length,
        "embedded_text_truncated": embedded_text_truncated,
        "embedding_backend": embedding_backend,
        "embedding_model": embedding_model,
        "selected_fields": selected_fields,
    }


def build_point_vectors(
    *,
    dense_vector: list[float],
    keyword_text: str,
) -> models.VectorStruct:
    return {
        settings.qdrant.dense_vector_name: dense_vector,
        settings.qdrant.sparse_vector_name: build_sparse_keyword_vector(keyword_text),
    }


def validate_collection_schema(collection_info: Any, expected_dimension: int) -> None:
    params = collection_info.config.params
    vectors_config = getattr(params, "vectors", None)
    sparse_config = getattr(params, "sparse_vectors", None)
    dense_params = (
        vectors_config.get(settings.qdrant.dense_vector_name)
        if isinstance(vectors_config, dict)
        else None
    )
    sparse_params = (
        sparse_config.get(settings.qdrant.sparse_vector_name)
        if isinstance(sparse_config, dict)
        else None
    )

    if dense_params is None or sparse_params is None:
        raise ValueError(
            "Target collection must use named vectors "
            f"{settings.qdrant.dense_vector_name!r} and "
            f"{settings.qdrant.sparse_vector_name!r}. Choose a fresh collection "
            "with the required hybrid schema."
        )
    actual_dimension = getattr(dense_params, "size", None)
    if actual_dimension != expected_dimension:
        raise ValueError(
            f"Target collection dense vector {settings.qdrant.dense_vector_name!r} "
            f"has dimension {actual_dimension}; model {expected_dimension} produces. "
            "Choose a fresh collection with the matching embedding schema."
        )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream enriched scheme documents into Qdrant in bounded batches."
    )
    parser.add_argument(
        "--list-fields",
        action="store_true",
        help="Print available top-level fields and exit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional positive maximum number of source schemes to index.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Positive number of source schemes held for each embedding/upsert batch.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["local", "gemini"],
        default=settings.embeddings.backend,
        help="Embedding backend. Local runs Sentence Transformers in this process.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Override the canonical model selected for the backend.",
    )
    parser.add_argument(
        "--collection",
        default=settings.qdrant.default_collection,
        help="Qdrant collection name.",
    )
    parser.add_argument(
        "--profile-version",
        choices=["v1", "v2"],
        default="v1",
        help="Embedding field-set version to index.",
    )
    parser.add_argument(
        "--qdrant-url",
        default=settings.qdrant.url,
        help="Qdrant HTTP URL.",
    )
    parser.add_argument(
        "--database",
        default=settings.mongo.database_name,
        help="Mongo database name.",
    )
    parser.add_argument(
        "--source-collection",
        default=settings.mongo.schemes_enriched_collection,
        help="Mongo collection containing enriched scheme documents.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=settings.mongodb_uri,
        help="MongoDB URI.",
    )
    parser.add_argument(
        "--output-dimensionality",
        type=int,
        default=None,
        help="Optional embedding dimensionality override for Gemini embeddings.",
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Delete and recreate only the selected target collection before indexing.",
    )
    parser.add_argument(
        "--max-text-characters",
        type=int,
        default=None,
        help="Optional positive character cap for each embedding document.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Optional path for a JSON record of model, schema, profiles, and counts.",
    )
    args = parser.parse_args()

    if args.list_fields:
        print("\n".join(available_embed_fields()))
        return
    if args.batch_size <= 0:
        parser.error("--batch-size must be a positive integer")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer")
    if args.max_text_characters is not None and args.max_text_characters <= 0:
        parser.error("--max-text-characters must be a positive integer")
    if args.embedding_backend == "local" and args.output_dimensionality is not None:
        parser.error("--output-dimensionality is only supported for Gemini embeddings")

    embedding_model = args.embedding_model or settings.embedding_model(
        args.embedding_backend
    )
    uses_nomic_prefixes = (
        args.embedding_backend == "local"
        and embedding_model.lower().startswith(
            tuple(prefix.lower() for prefix in NOMIC_TEXT_MODELS_REQUIRING_PREFIXES)
        )
    )
    profiles = embedding_profiles_for_version(args.profile_version)
    stats: dict[str, Any] = {
        "batches_completed": 0,
        "schemes_read": 0,
        "processed_schemes": 0,
        "points_indexed": 0,
        "skipped_schemes": 0,
        "skipped_profiles": 0,
        "failed_schemes": 0,
        "points_by_profile": {name: 0 for name in profiles},
    }
    mongo: AsyncMongoClient[dict[str, Any]] | None = None
    cursor: Any = None
    qdrant: QdrantClient | None = None
    embedding_client: Any = None
    collection_prepared = False
    embedding_dimension: int | None = None
    run_status = "failed"
    run_error: str | None = None

    def write_manifest() -> None:
        if args.manifest_path is None:
            return
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": run_status,
            "error": run_error,
            "source": {
                "database": args.database,
                "collection": args.source_collection,
                "limit": args.limit,
            },
            "target": {
                "collection": args.collection,
                "dense_vector": settings.qdrant.dense_vector_name,
                "dense_dimension": embedding_dimension,
                "distance": "Cosine",
                "sparse_vector": settings.qdrant.sparse_vector_name,
                "sparse_hash_dimensions": settings.qdrant.sparse_keyword_dimensions,
                "sparse_modifier": "IDF",
            },
            "embedding": {
                "backend": args.embedding_backend,
                "model": embedding_model,
                "document_task_type": "RETRIEVAL_DOCUMENT",
                "normalized": args.embedding_backend == "local",
                "nomic_task_prefixes": uses_nomic_prefixes,
                "query_task_type": "RETRIEVAL_QUERY",
                "nomic_document_prefix": (
                    "search_document: " if uses_nomic_prefixes else None
                ),
                "nomic_query_prefix": "search_query: " if uses_nomic_prefixes else None,
                "trust_remote_code": uses_nomic_prefixes,
                "profile_version": args.profile_version,
                "profiles": profiles,
                "batch_size_schemes": args.batch_size,
                "max_text_characters": args.max_text_characters,
            },
            "counts": stats,
        }
        args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    async def flush_batch(raw_batch: list[dict[str, Any]]) -> None:
        nonlocal embedding_client, collection_prepared, embedding_dimension
        qdrant_client = qdrant
        if qdrant_client is None:
            raise RuntimeError("Qdrant client is not initialized.")
        batch_number = stats["batches_completed"] + 1
        print(
            f"Batch {batch_number}: preparing {len(raw_batch)} schemes "
            f"after reading {stats['schemes_read']} source records.",
            flush=True,
        )
        batch_texts: list[str] = []
        batch_payloads: list[dict[str, Any]] = []
        batch_point_ids: list[str] = []
        batch_profiles: list[str] = []
        eligible_schemes: set[int] = set()

        for scheme_index, raw_scheme in enumerate(raw_batch):
            try:
                scheme = EnrichedSchemeData.model_validate(raw_scheme)
            except ValidationError as exc:
                stats["failed_schemes"] += 1
                print(
                    "Skipping invalid source document "
                    f"{raw_scheme.get('_id', '<unknown>')}: {exc.__class__.__name__}",
                    file=sys.stderr,
                )
                continue

            scheme_points = 0
            for profile_name, profile in profiles.items():
                document_text, selected_payload = build_embedding_document(
                    scheme,
                    profile["fields"],
                )
                if not document_text:
                    stats["skipped_profiles"] += 1
                    continue
                document_text, original_length, truncated = truncate_embedding_text(
                    document_text,
                    max_characters=args.max_text_characters,
                )
                batch_texts.append(document_text)
                batch_point_ids.append(
                    qdrant_point_id_for_scheme(scheme.url, profile_name)
                )
                batch_profiles.append(profile_name)
                batch_payloads.append(
                    build_payload(
                        scheme=scheme,
                        selected_fields=selected_payload,
                        profile=profile,
                        profile_name=profile_name,
                        profile_version=args.profile_version,
                        embedded_text_length=len(document_text),
                        embedded_text_original_length=original_length,
                        embedded_text_truncated=truncated,
                        embedding_backend=args.embedding_backend,
                        embedding_model=embedding_model,
                        database_name=args.database,
                        source_collection=args.source_collection,
                    )
                )
                scheme_points += 1
            if scheme_points:
                eligible_schemes.add(scheme_index)
            else:
                stats["skipped_schemes"] += 1

        if not batch_texts:
            stats["batches_completed"] += 1
            print(
                f"Batch {batch_number}: no embed-able profile text; "
                f"skipped_schemes={stats['skipped_schemes']} "
                f"failed_schemes={stats['failed_schemes']}.",
                flush=True,
            )
            return

        try:
            if embedding_client is None:
                print(
                    f"Loading embedding backend={args.embedding_backend!r}, "
                    f"model={embedding_model!r}.",
                    flush=True,
                )
                embedding_client = build_embedding_client(
                    provider=args.embedding_backend,
                    model=embedding_model,
                )
            print(
                f"Batch {batch_number}: embedding {len(batch_texts)} profile texts.",
                flush=True,
            )
            vectors = embedding_client.embed_texts(
                batch_texts,
                model=embedding_model,
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=args.output_dimensionality,
            )
            if len(vectors) != len(batch_texts) or not vectors:
                raise ValueError(
                    "Embedding client returned a different number of vectors "
                    "than texts."
                )
            batch_dimension = len(vectors[0])
            if any(len(vector) != batch_dimension for vector in vectors):
                raise ValueError(
                    "Embedding client returned inconsistent vector dimensions."
                )

            if not collection_prepared:
                if args.recreate_collection and qdrant_client.collection_exists(
                    args.collection
                ):
                    qdrant_client.delete_collection(args.collection)
                if not qdrant_client.collection_exists(args.collection):
                    qdrant_client.create_collection(
                        collection_name=args.collection,
                        vectors_config={
                            settings.qdrant.dense_vector_name: models.VectorParams(
                                size=batch_dimension,
                                distance=models.Distance.COSINE,
                            )
                        },
                        sparse_vectors_config={
                            settings.qdrant.sparse_vector_name: (
                                models.SparseVectorParams(modifier=models.Modifier.IDF)
                            )
                        },
                    )
                embedding_dimension = batch_dimension
                validate_collection_schema(
                    qdrant_client.get_collection(args.collection),
                    expected_dimension=batch_dimension,
                )
                collection_prepared = True
                print(
                    f"Qdrant schema verified: "
                    f"{settings.qdrant.dense_vector_name}={batch_dimension}, "
                    f"{settings.qdrant.sparse_vector_name}.",
                    flush=True,
                )
            elif batch_dimension != embedding_dimension:
                raise ValueError(
                    f"Embedding dimension changed from {embedding_dimension} "
                    f"to {batch_dimension} between batches."
                )

            qdrant_client.upsert(
                collection_name=args.collection,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=build_point_vectors(
                            dense_vector=vector,
                            keyword_text=text,
                        ),
                        payload=payload,
                    )
                    for point_id, vector, payload, text in zip(
                        batch_point_ids,
                        vectors,
                        batch_payloads,
                        batch_texts,
                        strict=True,
                    )
                ],
            )
            stats["processed_schemes"] += len(eligible_schemes)
            stats["points_indexed"] += len(batch_point_ids)
            for profile_name in batch_profiles:
                stats["points_by_profile"][profile_name] += 1
            stats["batches_completed"] += 1
            print(
                f"Batch {batch_number} complete: "
                f"processed_schemes={stats['processed_schemes']} "
                f"points_indexed={stats['points_indexed']} "
                f"skipped_schemes={stats['skipped_schemes']} "
                f"failed_schemes={stats['failed_schemes']}.",
                flush=True,
            )
        except Exception:
            stats["failed_schemes"] += len(eligible_schemes)
            raise

    try:
        print(
            f"Starting stream: source={args.database}.{args.source_collection}, "
            f"target={args.collection!r}, backend={args.embedding_backend!r}, "
            f"model={embedding_model!r}, profile_version={args.profile_version!r}, "
            f"batch_size={args.batch_size} schemes.",
            flush=True,
        )
        mongo = AsyncMongoClient(args.mongo_uri)
        qdrant = QdrantClient(url=args.qdrant_url, api_key=settings.qdrant.api_key)
        cursor = mongo[args.database][args.source_collection].find({}).batch_size(
            args.batch_size
        )
        if args.limit is not None:
            cursor = cursor.limit(args.limit)

        pending: list[dict[str, Any]] = []
        async for scheme in cursor:
            stats["schemes_read"] += 1
            pending.append(scheme)
            if len(pending) == args.batch_size:
                await flush_batch(pending)
                pending.clear()
        if pending:
            await flush_batch(pending)
        if stats["schemes_read"] == 0:
            print("No schemes found in MongoDB; nothing to index.")
        elif stats["points_indexed"] == 0:
            print("Selected fields produced no embed-able text.")
        run_status = (
            "complete_with_failures" if stats["failed_schemes"] else "complete"
        )
    except BaseException as exc:
        run_error = type(exc).__name__
        raise
    finally:
        try:
            if cursor is not None:
                await cursor.close()
        finally:
            try:
                if mongo is not None:
                    await mongo.close()
            finally:
                if qdrant is not None:
                    qdrant.close()
        print(
            "Indexing summary: "
            f"schemes_read={stats['schemes_read']} "
            f"processed_schemes={stats['processed_schemes']} "
            f"points_indexed={stats['points_indexed']} "
            f"skipped_schemes={stats['skipped_schemes']} "
            f"skipped_profiles={stats['skipped_profiles']} "
            f"failed_schemes={stats['failed_schemes']}"
        )
        if args.manifest_path is not None:
            try:
                write_manifest()
            except OSError as exc:
                print(f"Could not write manifest: {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
