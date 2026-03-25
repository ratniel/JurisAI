#!/usr/bin/env python3
"""Export unique scheme tags from MongoDB to a file."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import AsyncMongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings


async def fetch_unique_tags(
    mongo_uri: str,
    database_name: str,
    collection_name: str,
) -> list[str]:
    """Return a sorted list of unique, non-empty scheme tags."""
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(mongo_uri)
    try:
        collection = client[database_name][collection_name]
        pipeline: list[dict[str, Any]] = [
            {"$match": {"tags": {"$type": "array"}}},
            {"$unwind": "$tags"},
            {"$match": {"tags": {"$type": "string"}}},
            {"$project": {"tag": {"$trim": {"input": "$tags"}}}},
            {"$match": {"tag": {"$ne": ""}}},
            # ensures uniqueness of tags by grouping them using tag as id
            # mongodb groups documents with the same tag into a single document
            {"$group": {"_id": "$tag"}},
            {"$sort": {"_id": 1}},
        ]

        cursor = await collection.aggregate(pipeline)
        rows = await cursor.to_list(length=None)
        return [row["_id"] for row in rows if isinstance(row.get("_id"), str)]
    finally:
        await client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect all unique tags from schemes and write to a JSON file."
    )
    parser.add_argument(
        "--mongo-uri",
        default=settings.mongodb_uri,
        help="MongoDB URI (default from settings).",
    )
    parser.add_argument(
        "--database",
        default=settings.database_name,
        help="Database name (default from settings).",
    )
    parser.add_argument(
        "--collection",
        default=settings.schemes_collection,
        help="Collection name (default from settings).",
    )
    parser.add_argument(
        "--output",
        default="unique_tags.json",
        help="Output JSON path (default: unique_tags.json).",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    tags = await fetch_unique_tags(
        mongo_uri=args.mongo_uri,
        database_name=args.database,
        collection_name=args.collection,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": args.database,
        "collection": args.collection,
        "unique_tags_count": len(tags),
        "unique_tags": tags,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Unique tags: {len(tags)}")
    print(f"Output written to: {output_path.resolve()}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
