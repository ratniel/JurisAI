from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.eval.agentic_workflow_eval import (
    default_agentic_workflow_output_path,
    run_agentic_workflow_eval,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score the golden dataset against the live agentic workflow."
    )
    parser.add_argument(
        "--collection",
        default=settings.eval.qdrant_collection,
        help="Qdrant collection name to score against.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Top-k retrieval depth to score.",
    )
    parser.add_argument(
        "--fail-on-classifier-error",
        action="store_true",
        help="Abort the run if workflow classification fails for any record.",
    )
    parser.add_argument(
        "--include-debug",
        action="store_true",
        help="Include raw retrieval/debug payloads in the saved output.",
    )
    parser.add_argument(
        "--enforce-absolute-gate",
        action="store_true",
        help="Exit non-zero unless the strict curated retrieval gate passes.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help=(
            "Optional JSON artifact path. Defaults to "
            "evals/agentic_workflow/runs/agentic_workflow_eval_<timestamp>.json"
        ),
    )
    parser.add_argument(
        "--record-ids",
        default=None,
        help="Optional comma-separated record IDs to evaluate.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["local", "gemini"],
        default=None,
        help="Override the query embedding backend used during retrieval scoring.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Override the query embedding model used during retrieval scoring.",
    )
    parser.add_argument(
        "--retrieval-filter-mode",
        choices=[
            "all",
            "none",
            "state_only",
            "topics_only",
            "state_hard_topics_soft",
        ],
        default=None,
        help="Shared retrieval filter policy to apply during scoring.",
    )
    parser.add_argument(
        "--disable-retrieval-filters",
        action="store_true",
        help="Disable hard retrieval filters and rely on the agent's queries only.",
    )
    args = parser.parse_args()

    output_path = (
        Path(args.output_path)
        if args.output_path
        else default_agentic_workflow_output_path()
    )
    record_ids = (
        [record_id.strip() for record_id in args.record_ids.split(",") if record_id.strip()]
        if args.record_ids
        else None
    )
    summary = run_agentic_workflow_eval(
        limit=args.limit,
        collection_name=args.collection,
        include_debug=args.include_debug,
        fail_on_classifier_error=args.fail_on_classifier_error,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
        trace_project=settings.phoenix.project_name,
        phoenix_endpoint=settings.phoenix.collector_endpoint,
        output_path=output_path,
        persist_artifact=True,
        record_ids=record_ids,
        retrieval_filters_enabled=not args.disable_retrieval_filters,
        retrieval_filter_mode=("none" if args.disable_retrieval_filters else args.retrieval_filter_mode),
    )
    print(json.dumps(summary, indent=2))
    if args.enforce_absolute_gate and summary["absolute_gate_failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
