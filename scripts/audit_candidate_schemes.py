from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.data_ingestion.candidate_scheme_intake import (
    CandidateSchemeAuditResult,
    audit_candidate_schemes,
    load_candidate_schemes,
)
from src.data_ingestion.scrape_schemes import ScrapeSchemes


def _summarize(results: list[CandidateSchemeAuditResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary


async def _import_supported_missing(results: list[CandidateSchemeAuditResult]) -> list[dict[str, str]]:
    pending = [
        result
        for result in results
        if result.status == "missing_supported_scrape_target"
    ]
    if not pending:
        return []

    imported: list[dict[str, str]] = []
    async with ScrapeSchemes() as scraper:
        for result in pending:
            scheme = await scraper.scrape_scheme(
                result.candidate.name,
                result.canonical_url,
            )
            await scraper._bulk_upsert_schemes([scheme])
            imported.append(
                {
                    "name": scheme.name,
                    "url": scheme.url,
                }
            )
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit externally sourced scheme candidates against jurisai.schemes and "
            "optionally scrape any missing myScheme scheme URLs into the main collections."
        )
    )
    parser.add_argument(
        "--candidate-file",
        required=True,
        help="Path to JSON file containing a list of {name, url, ...} candidates.",
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
        "--raw-collection",
        default=settings.mongo.schemes_collection,
        help="Raw source collection to audit against.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Scrape and upsert missing supported myScheme scheme URLs into the main collections.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path for the JSON audit report.",
    )
    args = parser.parse_args()

    candidates = load_candidate_schemes(args.candidate_file)
    results = audit_candidate_schemes(
        candidates=candidates,
        mongo_uri=args.mongo_uri,
        database_name=args.database,
        raw_collection=args.raw_collection,
    )
    imported: list[dict[str, str]] = []
    if args.apply:
        imported = asyncio.run(_import_supported_missing(results))
        results = audit_candidate_schemes(
            candidates=candidates,
            mongo_uri=args.mongo_uri,
            database_name=args.database,
            raw_collection=args.raw_collection,
        )

    report = {
        "candidate_file": str(Path(args.candidate_file).resolve()),
        "database": args.database,
        "raw_collection": args.raw_collection,
        "applied": bool(args.apply),
        "imported": imported,
        "summary": _summarize(results),
        "results": [result.model_dump(mode="json", exclude_none=True) for result in results],
    }

    serialized = json.dumps(report, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
        print(f"Wrote audit report to {output_path}")

    print(serialized)


if __name__ == "__main__":
    main()
