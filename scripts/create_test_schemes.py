#!/usr/bin/env python3
"""Create a deterministic test subset in MongoDB.

Target distribution in `test_schemes`:
- 13 schemes with level == "central"
- 12 schemes with level == "state"
  - 3 from Maharashtra
  - 3 each from 3 additional states (auto-selected)
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from pathlib import Path
from typing import Any, Iterable

from loguru import logger
from pymongo import AsyncMongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings

INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


async def sample_docs(
    collection: Any,
    match_query: dict[str, Any],
    sample_size: int,
    exclude_ids: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    """Sample documents with optional _id exclusion guard."""
    guarded_query = dict(match_query)
    if exclude_ids:
        guarded_query["_id"] = {"$nin": list(exclude_ids)}

    pipeline = [
        {"$match": guarded_query},
        {"$sample": {"size": sample_size}},
    ]
    cursor = await collection.aggregate(pipeline)
    return await cursor.to_list(length=sample_size)


async def count_for_state(collection: Any, state_name: str) -> int:
    """Count state-level records where provider contains the state name."""
    query = {
        "level": "state",
        "provider": {"$regex": state_name, "$options": "i"},
    }
    return await collection.count_documents(query)


async def create_subset(
    mongo_uri: str,
    database_name: str,
    source_collection_name: str,
    target_collection_name: str,
) -> None:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(mongo_uri)
    try:
        db = client[database_name]
        source = db[source_collection_name]
        target = db[target_collection_name]

        selected_docs: list[dict[str, Any]] = []
        selected_ids: set[Any] = set()

        central_docs = await sample_docs(
            collection=source,
            match_query={"level": "central"},
            sample_size=13,
        )
        if len(central_docs) < 13:
            raise RuntimeError(
                f"Not enough central schemes. Needed 13, found {len(central_docs)}."
            )

        selected_docs.extend(central_docs)
        selected_ids.update(doc["_id"] for doc in central_docs if "_id" in doc)

        maharashtra_docs = await sample_docs(
            collection=source,
            match_query={
                "level": "state",
                "provider": {"$regex": "Maharashtra", "$options": "i"},
            },
            sample_size=3,
            exclude_ids=selected_ids,
        )
        if len(maharashtra_docs) < 3:
            raise RuntimeError(
                "Not enough Maharashtra state schemes in provider. "
                f"Needed 3, found {len(maharashtra_docs)}."
            )

        selected_docs.extend(maharashtra_docs)
        selected_ids.update(doc["_id"] for doc in maharashtra_docs if "_id" in doc)

        state_counts: list[tuple[str, int]] = []
        for state in INDIAN_STATES:
            if state.lower() == "maharashtra":
                continue
            count = await count_for_state(source, state)
            if count >= 3:
                state_counts.append((state, count))

        if len(state_counts) < 3:
            raise RuntimeError(
                "Could not find 3 additional states with at least 3 records each. "
                f"Eligible states found: {len(state_counts)}"
            )

        state_counts.sort(key=lambda item: (-item[1], item[0]))
        chosen_states = [name for name, _ in state_counts[:3]]
        logger.info(
            "Chosen additional states: {}",
            ", ".join(chosen_states),
        )

        for state in chosen_states:
            state_docs = await sample_docs(
                collection=source,
                match_query={
                    "level": "state",
                    "provider": {"$regex": state, "$options": "i"},
                },
                sample_size=3,
                exclude_ids=selected_ids,
            )
            if len(state_docs) < 3:
                raise RuntimeError(
                    f"Could not sample 3 unique schemes for {state}. "
                    f"Found {len(state_docs)} after dedupe guard."
                )

            selected_docs.extend(state_docs)
            selected_ids.update(doc["_id"] for doc in state_docs if "_id" in doc)

        if len(selected_docs) != 25:
            raise RuntimeError(
                f"Selection invariant failed. Expected 25 docs, got {len(selected_docs)}"
            )

        random.shuffle(selected_docs)

        await target.drop()
        await target.insert_many(selected_docs, ordered=True)

        logger.success(
            "Inserted {} documents into {}.{} from {}.{}",
            len(selected_docs),
            database_name,
            target_collection_name,
            database_name,
            source_collection_name,
        )
    finally:
        await client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create 25-scheme test subset in MongoDB collection `test_schemes`."
    )
    parser.add_argument(
        "--mongo-uri",
        default=settings.mongodb_uri,
        help="MongoDB URI (default from settings)",
    )
    parser.add_argument(
        "--database",
        default=settings.database_name,
        help="Database name (default from settings)",
    )
    parser.add_argument(
        "--source-collection",
        default=settings.schemes_collection,
        help="Source collection name (default from settings)",
    )
    parser.add_argument(
        "--target-collection",
        default="test_schemes",
        help="Target collection name (default: test_schemes)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        create_subset(
            mongo_uri=args.mongo_uri,
            database_name=args.database,
            source_collection_name=args.source_collection,
            target_collection_name=args.target_collection,
        )
    )


if __name__ == "__main__":
    main()
