from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.data_ingestion.topic_taxonomy import (
    CONTROLLED_TOPICS,
    TOPIC_COUNT_NOTE,
    infer_topics_from_tags,
    map_tag_to_topics,
)

DEFAULT_SOURCE_COLLECTION = settings.mongo.test_schemes_collection
DEFAULT_UNIQUE_TAGS_FILE = PROJECT_ROOT / "unique_tags.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "topic_mapping_experiment"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Map scheme tags into the controlled topic taxonomy and optionally "
            "write a `topics` field back to MongoDB."
        )
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
        help="Mongo collection to enrich.",
    )
    parser.add_argument(
        "--target-collection",
        default=None,
        help=(
            "Optional target collection. If set, enriched documents are copied there "
            "instead of updating the source collection in place."
        ),
    )
    parser.add_argument(
        "--target-field",
        default="topics",
        help=(
            "Field name to write on each document. Defaults to `topics`. "
            "A dotted path like `eligibility_entities.topics` is also supported."
        ),
    )
    parser.add_argument(
        "--unique-tags-file",
        default=str(DEFAULT_UNIQUE_TAGS_FILE),
        help="JSON file containing the exported unique tag list.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory where mapping reports will be written.",
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
        help="Write the computed topic field to MongoDB.",
    )
    return parser.parse_args()


def read_unique_tags(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Unique tags file not found: {path}")

    payload = json.loads(path.read_text())
    unique_tags = payload.get("unique_tags", [])
    if not isinstance(unique_tags, list):
        raise ValueError("unique_tags.json is missing `unique_tags` as a list.")
    return [tag for tag in unique_tags if isinstance(tag, str) and tag.strip()]


def set_nested_field(document: dict[str, Any], dotted_path: str, value: Any) -> None:
    cursor = document
    path_parts = dotted_path.split(".")
    for part in path_parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[path_parts[-1]] = value


def write_reports(unique_tags: list[str], report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)

    tag_mappings = [map_tag_to_topics(tag).to_dict() for tag in unique_tags]
    summary = Counter(result["status"] for result in tag_mappings)
    unresolved_reasons = Counter(
        result["review_reason"]
        for result in tag_mappings
        if result["status"] == "unmapped"
    )

    topic_counts = Counter()
    for result in tag_mappings:
        for topic in result["topics"]:
            topic_counts[topic] += 1

    summary_payload = {
        "controlled_topics": list(CONTROLLED_TOPICS),
        "topic_count_note": TOPIC_COUNT_NOTE,
        "unique_tag_count": len(unique_tags),
        "status_counts": dict(summary),
        "topic_hit_counts": dict(topic_counts),
        "unmapped_reason_counts": dict(unresolved_reasons),
        "multi_topic_tags": [
            result for result in tag_mappings if result["status"] == "multi_topic"
        ],
        "unmapped_tags": [
            result for result in tag_mappings if result["status"] == "unmapped"
        ],
    }

    (report_dir / "tag_topic_mapping.json").write_text(
        json.dumps(tag_mappings, indent=2, ensure_ascii=True)
    )
    (report_dir / "summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=True)
    )
    (report_dir / "summary.md").write_text(render_markdown_summary(summary_payload))

    return summary_payload


def render_markdown_summary(summary_payload: dict[str, Any]) -> str:
    lines = [
        "# Topic Mapping Experiment Summary",
        "",
        summary_payload["topic_count_note"],
        "",
        f"- Unique tags reviewed: {summary_payload['unique_tag_count']}",
        f"- Single-topic mappings: {summary_payload['status_counts'].get('mapped', 0)}",
        f"- Multi-topic mappings: {summary_payload['status_counts'].get('multi_topic', 0)}",
        f"- Unmapped tags: {summary_payload['status_counts'].get('unmapped', 0)}",
        "",
        "## Controlled Topics",
        "",
    ]
    lines.extend(f"- {topic}" for topic in summary_payload["controlled_topics"])
    lines.extend(
        [
            "",
            "## Unmapped Reason Counts",
            "",
        ]
    )
    if summary_payload["unmapped_reason_counts"]:
        lines.extend(
            f"- {reason}: {count}"
            for reason, count in sorted(summary_payload["unmapped_reason_counts"].items())
        )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Multi-topic Samples",
            "",
        ]
    )
    multi_topic_tags = summary_payload["multi_topic_tags"][:20]
    if multi_topic_tags:
        lines.extend(
            f"- {entry['tag']}: {', '.join(entry['topics'])}" for entry in multi_topic_tags
        )
    else:
        lines.append("- none")

    return "\n".join(lines).strip() + "\n"


def enrich_documents(
    documents: list[dict[str, Any]],
    target_field: str,
) -> list[tuple[Any, list[str]]]:
    updates: list[tuple[Any, list[str]]] = []
    for document in documents:
        topics = infer_topics_from_tags(document.get("tags") or [])
        updates.append((document["_id"], topics))
    return updates


def print_scheme_summary(
    documents: list[dict[str, Any]],
    updates: list[tuple[Any, list[str]]],
) -> None:
    by_id = {document["_id"]: document for document in documents}
    zero_topic_docs = 0
    topic_distribution = Counter()

    for document_id, topics in updates:
        if not topics:
            zero_topic_docs += 1
        for topic in topics:
            topic_distribution[topic] += 1

    print("scheme_topic_counts", dict(topic_distribution))
    print("documents_with_no_topics", zero_topic_docs)
    print("\nverification samples:")

    for document_id, topics in updates[:10]:
        document = by_id[document_id]
        print("---")
        print(document.get("name"))
        print(f"tags={document.get('tags')}")
        print(f"topics={topics}")


def main() -> None:
    args = parse_args()
    unique_tags_path = Path(args.unique_tags_file)
    report_dir = Path(args.report_dir)
    unique_tags = read_unique_tags(unique_tags_path)
    report_summary = write_reports(unique_tags, report_dir)

    client = MongoClient(args.mongo_uri)
    try:
        source_collection = client[args.database][args.source_collection]
        cursor = source_collection.find({})
        if args.limit is not None:
            cursor = cursor.limit(args.limit)
        documents = list(cursor)

        if not documents:
            print("No documents found; only mapping reports were generated.")
            return

        updates = enrich_documents(documents, args.target_field)

        if args.apply:
            if args.target_collection:
                target_collection = client[args.database][args.target_collection]
                target_collection.drop()
                enriched_documents: list[dict[str, Any]] = []
                updates_by_id = {document_id: topics for document_id, topics in updates}
                for document in documents:
                    enriched_document = dict(document)
                    set_nested_field(
                        enriched_document,
                        args.target_field,
                        updates_by_id[document["_id"]],
                    )
                    enriched_documents.append(enriched_document)
                if enriched_documents:
                    target_collection.insert_many(enriched_documents, ordered=True)
                print(
                    f"Applied topic enrichment to {len(enriched_documents)} documents from "
                    f"{args.database}.{args.source_collection} into "
                    f"{args.database}.{args.target_collection}."
                )
            else:
                for document_id, topics in updates:
                    source_collection.update_one(
                        {"_id": document_id},
                        {"$set": {args.target_field: topics}},
                    )
                print(
                    f"Applied topic enrichment to {len(updates)} documents in "
                    f"{args.database}.{args.source_collection}."
                )
        else:
            print(
                f"Dry run prepared topic enrichment for {len(updates)} documents in "
                f"{args.database}.{args.source_collection}."
            )

        print(
            "unique_tag_status_counts",
            report_summary["status_counts"],
        )
        print(
            "unique_tag_unmapped_reason_counts",
            report_summary["unmapped_reason_counts"],
        )
        print_scheme_summary(documents, updates)
        print(f"\nReports written to: {report_dir}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
