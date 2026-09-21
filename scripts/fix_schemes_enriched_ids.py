"""Normalize schemes_enriched/_id (and test_schemes_enriched) to match the
authoritative ObjectId already assigned in schemes/test_schemes, joined by url.

Mongo won't let you mutate _id in place, so this writes a corrected copy into
a scratch collection and atomically renames it over the original, moving the
original aside as a timestamped backup rather than deleting it.

Usage:
    python scripts/fix_schemes_enriched_ids.py                 # both pairs
    python scripts/fix_schemes_enriched_ids.py --dry-run
    python scripts/fix_schemes_enriched_ids.py --pair test     # test pair only
    python scripts/fix_schemes_enriched_ids.py --pair prod     # prod pair only
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings

PAIRS = {
    "prod": (settings.mongo.schemes_collection, settings.mongo.schemes_enriched_collection),
    "test": (
        settings.mongo.test_schemes_collection,
        settings.mongo.test_schemes_enriched_collection,
    ),
}


def fix_pair(db, raw_name: str, enriched_name: str, *, dry_run: bool) -> None:
    raw_ids_by_url = {
        d["url"]: d["_id"] for d in db[raw_name].find({}, {"url": 1, "_id": 1})
    }

    already_ok = 0
    fixed = 0
    orphaned = 0
    docs_to_insert: list[dict] = []

    for doc in db[enriched_name].find({}):
        raw_id = raw_ids_by_url.get(doc.get("url"))
        if raw_id is None:
            orphaned += 1
            docs_to_insert.append(doc)
            continue
        if isinstance(doc["_id"], ObjectId) and doc["_id"] == raw_id:
            already_ok += 1
            docs_to_insert.append(doc)
            continue
        fixed += 1
        docs_to_insert.append({**doc, "_id": raw_id})

    total = len(docs_to_insert)
    print(
        f"{enriched_name}: total={total} already_ok={already_ok} "
        f"fixed={fixed} orphaned(no raw url match, left as-is)={orphaned}"
    )

    if dry_run:
        print(f"  (dry-run, no changes written for {enriched_name})")
        return

    if fixed == 0 and orphaned == 0:
        print(f"  nothing to do for {enriched_name}")
        return

    scratch_name = f"{enriched_name}_id_fix_scratch"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"{enriched_name}_pre_id_fix_{timestamp}"

    db.drop_collection(scratch_name)
    if docs_to_insert:
        db[scratch_name].insert_many(docs_to_insert, ordered=True)

    scratch_count = db[scratch_name].count_documents({})
    original_count = db[enriched_name].count_documents({})
    if scratch_count != original_count:
        db.drop_collection(scratch_name)
        raise RuntimeError(
            f"Aborting: scratch collection count ({scratch_count}) does not "
            f"match original ({original_count}) for {enriched_name}."
        )

    db[enriched_name].rename(backup_name)
    db[scratch_name].rename(enriched_name)
    print(f"  wrote {scratch_count} docs, original backed up as '{backup_name}'")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=settings.mongodb_uri)
    parser.add_argument("--database", default=settings.database_name)
    parser.add_argument(
        "--pair",
        choices=["prod", "test", "both"],
        default="both",
        help="Which raw/enriched collection pair to fix.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing any changes.",
    )
    args = parser.parse_args()

    client = MongoClient(args.mongo_uri)
    db = client[args.database]

    pairs = PAIRS.values() if args.pair == "both" else [PAIRS[args.pair]]
    for raw_name, enriched_name in pairs:
        fix_pair(db, raw_name, enriched_name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
