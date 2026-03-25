from __future__ import annotations

import argparse
import asyncio
import sys
from itertools import islice
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel
from pymongo import AsyncMongoClient
from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.llm import build_embedding_client
from src.scheme_contracts import EnrichedSchemeData, QdrantSchemeMetadata

EMBEDDING_PROFILES: dict[str, dict[str, Any]] = {
    "embedding_a": {
        "label": "name + details",
        "fields": ["name", "details"],
        "purpose": "what the scheme is",
    },
    "embedding_b": {
        "label": "eligibility + benefits",
        "fields": ["eligibility", "benefits"],
        "purpose": "who qualifies and what they get",
    },
}


def batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def available_embed_fields() -> list[str]:
    return sorted(
        field_name
        for field_name in EnrichedSchemeData.model_fields.keys()
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
        lines = [
            f"{key}: {stringify_value(item)}"
            for key, item in value.items()
            if stringify_value(item)
        ]
        return "\n".join(lines)
    if isinstance(value, list):
        lines = [stringify_value(item) for item in value if stringify_value(item)]
        return "\n".join(lines)
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


async def fetch_schemes(
    *,
    mongo_uri: str,
    database_name: str,
    source_collection: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(mongo_uri)
    try:
        database = client[database_name]
        cursor = database[source_collection].find({})
        if limit is not None:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit)
    finally:
        await client.close()


def qdrant_point_id_for_scheme(url: str, profile_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{url}#{profile_name}"))


def build_payload(
    *,
    scheme: EnrichedSchemeData,
    selected_fields: dict[str, Any],
    profile_name: str,
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
        "embedding_profile_label": EMBEDDING_PROFILES[profile_name]["label"],
        "embedding_profile_purpose": EMBEDDING_PROFILES[profile_name]["purpose"],
        "embedded_fields": EMBEDDING_PROFILES[profile_name]["fields"],
        "embedding_backend": embedding_backend,
        "embedding_model": embedding_model,
        "selected_fields": selected_fields,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed scheme sections and upsert them into Qdrant."
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
        help="Optional max number of schemes to index.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Embedding and upsert batch size.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["local", "gemini"],
        default=settings.embeddings.backend,
        help="Embedding backend to use. Local is the default.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Override the embedding model name for the selected backend.",
    )
    parser.add_argument(
        "--collection",
        default=settings.qdrant.default_collection,
        help="Qdrant collection name.",
    )
    parser.add_argument(
        "--qdrant-url",
        default=settings.qdrant.url,
        help="Qdrant HTTP URL.",
    )
    parser.add_argument(
        "--database",
        default=settings.database_name,
        help="Mongo database name.",
    )
    parser.add_argument(
        "--source-collection",
        default=settings.mongo.test_schemes_enriched_collection,
        help="Mongo collection to read enriched scheme documents from.",
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
        help="Delete and recreate the target Qdrant collection before indexing.",
    )
    args = parser.parse_args()

    if args.list_fields:
        print("\n".join(available_embed_fields()))
        return

    if args.embedding_backend == "local" and args.output_dimensionality is not None:
        raise ValueError("output-dimensionality is only supported for Gemini embeddings.")

    schemes = await fetch_schemes(
        mongo_uri=args.mongo_uri,
        database_name=args.database,
        source_collection=args.source_collection,
        limit=args.limit,
    )

    if not schemes:
        print("No schemes found in MongoDB; nothing to index.")
        return

    documents: list[str] = []
    payloads: list[dict[str, Any]] = []
    point_ids: list[str] = []

    embedding_model = args.embedding_model or settings.embedding_model(
        args.embedding_backend
    )

    for scheme in schemes:
        scheme_document = EnrichedSchemeData.model_validate(scheme)
        for profile_name, profile in EMBEDDING_PROFILES.items():
            document_text, selected_payload = build_embedding_document(
                scheme_document,
                profile["fields"],
            )
            if not document_text:
                continue

            documents.append(document_text)
            point_ids.append(
                qdrant_point_id_for_scheme(
                    url=scheme_document.url,
                    profile_name=profile_name,
                )
            )
            payloads.append(
                build_payload(
                    scheme=scheme_document,
                    selected_fields=selected_payload,
                    profile_name=profile_name,
                    embedding_backend=args.embedding_backend,
                    embedding_model=embedding_model,
                    database_name=args.database,
                    source_collection=args.source_collection,
                )
            )

    if not documents:
        print("Selected fields produced no embed-able text.")
        return

    qdrant = QdrantClient(url=args.qdrant_url, api_key=settings.qdrant.api_key)
    if args.recreate_collection and qdrant.collection_exists(args.collection):
        qdrant.delete_collection(args.collection)

    embedding_client = build_embedding_client(
        provider=args.embedding_backend,
        model=embedding_model,
    )
    collection_created = False

    for batch_indexes in batched(list(range(len(documents))), args.batch_size):
        batch_texts = [documents[index] for index in batch_indexes]
        batch_payloads = [payloads[index] for index in batch_indexes]
        batch_point_ids = [point_ids[index] for index in batch_indexes]

        vectors = embedding_client.embed_texts(
            batch_texts,
            model=embedding_model,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=args.output_dimensionality,
        )

        if not collection_created:
            if not qdrant.collection_exists(args.collection):
                qdrant.create_collection(
                    collection_name=args.collection,
                    vectors_config=models.VectorParams(
                        size=len(vectors[0]),
                        distance=models.Distance.COSINE,
                    ),
                )
            collection_created = True

        qdrant.upsert(
            collection_name=args.collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
                for point_id, vector, payload in zip(
                    batch_point_ids, vectors, batch_payloads, strict=True
                )
            ],
        )

    print(
        f"Indexed {len(documents)} vectors from {len(schemes)} Mongo scheme documents "
        f"into Qdrant collection {args.collection!r} using backend={args.embedding_backend!r}, "
        f"model={embedding_model!r}, source={args.database}.{args.source_collection}."
    )


if __name__ == "__main__":
    asyncio.run(main())
