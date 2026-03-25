from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.data_ingestion.enrichment_pipeline import (
    build_enriched_scheme,
    normalize_whitespace,
)
from src.scheme_contracts import EnrichedApplicationModes, EnrichedSchemeData

DEFAULT_SOURCE_COLLECTION = settings.mongo.test_schemes_collection
DEFAULT_TARGET_COLLECTION = settings.mongo.test_schemes_enriched_collection


def print_summary(documents: list[EnrichedSchemeData]) -> None:
    provider_type_counts = Counter()
    mode_counts = Counter()
    faq_non_empty = 0

    for document in documents:
        provider_type_counts[document.provider_type or "missing"] += 1

        application_modes = document.application_modes
        if isinstance(application_modes, EnrichedApplicationModes):
            application_modes = application_modes.model_dump()

        mode_counts[
            f"online={bool(normalize_whitespace(application_modes.get('online')))} "
            f"offline={bool(normalize_whitespace(application_modes.get('offline')))}"
        ] += 1

        if normalize_whitespace(document.faq):
            faq_non_empty += 1

    print("provider_type_counts", dict(provider_type_counts))
    print("application_mode_counts", dict(mode_counts))
    print("faq_non_empty", faq_non_empty)
    print("\nverification samples:")

    for document in documents[:8]:
        print("---")
        print(document.name)
        print(
            f"level={document.level} provider={document.provider} "
            f"provider_type={document.provider_type}"
        )
        print(
            f"state={document.state} ministry={document.ministry} "
            f"application_modes={document.application_modes.model_dump()}"
        )
        print(f"topics={document.topics}")
        faq_preview = normalize_whitespace(document.faq)[:240]
        print(f"faq_preview={faq_preview}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform raw scheme documents into enriched scheme documents."
    )
    parser.add_argument(
        "--mongo-uri",
        default=settings.mongodb_uri,
        help="MongoDB URI.",
    )
    parser.add_argument(
        "--database",
        default=settings.database_name,
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--source-collection",
        default=DEFAULT_SOURCE_COLLECTION,
        help="Raw Mongo collection to read from.",
    )
    parser.add_argument(
        "--target-collection",
        default=DEFAULT_TARGET_COLLECTION,
        help="Enriched Mongo collection to write to when --apply is used.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of documents to process.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the enriched documents into the target collection.",
    )
    args = parser.parse_args()

    client = MongoClient(args.mongo_uri)
    try:
        source_collection = client[args.database][args.source_collection]
        cursor = source_collection.find({})
        if args.limit is not None:
            cursor = cursor.limit(args.limit)
        raw_documents = list(cursor)

        if not raw_documents:
            print("No documents found; nothing to enrich.")
            return

        enriched_documents = [
            build_enriched_scheme(document) for document in raw_documents
        ]

        if args.apply:
            target_collection = client[args.database][args.target_collection]
            target_collection.drop()
            target_collection.insert_many(
                [
                    document.model_dump(by_alias=True, exclude_none=True)
                    for document in enriched_documents
                ],
                ordered=True,
            )
            print(
                f"Applied enrichment to {len(enriched_documents)} documents from "
                f"{args.database}.{args.source_collection} into "
                f"{args.database}.{args.target_collection}."
            )
        else:
            print(
                f"Dry run prepared {len(enriched_documents)} enriched documents from "
                f"{args.database}.{args.source_collection}."
            )

        print_summary(enriched_documents)
    finally:
        client.close()


if __name__ == "__main__":
    main()
