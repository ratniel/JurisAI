"""Patch existing Qdrant points with extra scheme fields from Mongo, joined by url.

Works around broken mongo_ref.document_id hydration (schemes_enriched/_id is
stored as a string, not ObjectId, so ObjectId-based lookups in
RelevantScheme.from_mongo_document always miss) without touching Mongo at all.
Adds sources/documents_required/faq into each point's selected_fields so
RelevantScheme.from_retrieved_scheme can read them directly, the same way it
already reads details/benefits/eligibility.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient
from qdrant_client import QdrantClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings

FIELDS_TO_BACKFILL = ("sources", "documents_required", "faq")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge sources/documents_required/faq from a Mongo enriched "
            "collection into an existing Qdrant collection's selected_fields, "
            "joined by url."
        )
    )
    parser.add_argument("--collection", default=settings.qdrant.default_collection)
    parser.add_argument("--qdrant-url", default=settings.qdrant.url)
    parser.add_argument("--mongo-uri", default=settings.mongodb_uri)
    parser.add_argument("--database", default=settings.database_name)
    parser.add_argument(
        "--source-collection",
        default=settings.mongo.test_schemes_enriched_collection,
    )
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    mongo = MongoClient(args.mongo_uri)
    mongo_collection = mongo[args.database][args.source_collection]
    qdrant = QdrantClient(url=args.qdrant_url)

    url_cache: dict[str, dict | None] = {}
    updated = 0
    skipped_no_match = 0
    total = 0

    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=args.collection,
            limit=args.batch_size,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break

        for point in points:
            total += 1
            payload = point.payload or {}
            url = payload.get("url")
            if not url:
                skipped_no_match += 1
                continue

            if url not in url_cache:
                url_cache[url] = mongo_collection.find_one(
                    {"url": url},
                    {field: 1 for field in FIELDS_TO_BACKFILL},
                )
            doc = url_cache[url]
            if doc is None:
                skipped_no_match += 1
                continue

            selected_fields = dict(payload.get("selected_fields") or {})
            selected_fields.update(
                {field: doc.get(field) for field in FIELDS_TO_BACKFILL}
            )

            qdrant.set_payload(
                collection_name=args.collection,
                payload={"selected_fields": selected_fields},
                points=[point.id],
            )
            updated += 1

        if offset is None:
            break

    print(
        f"Scanned {total} points in '{args.collection}': "
        f"updated={updated}, skipped(no url match)={skipped_no_match}, "
        f"source=jurisai.{args.source_collection}"
    )


if __name__ == "__main__":
    main()
