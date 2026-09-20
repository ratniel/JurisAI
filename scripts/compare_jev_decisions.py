from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.jev_decision_eval import run_jev_decision_eval


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Jev routing decisions with the agentic classifier; no retrieval is run.")
    parser.add_argument("--dry-run", action="store_true", help="Save requests without calling either model.")
    parser.add_argument("--record-ids", help="Comma-separated IDs from the shared golden corpus.")
    parser.add_argument("--intent-provider", choices=["gemini", "llamaindex_google", "local_openai", "openrouter"])
    parser.add_argument("--intent-model")
    parser.add_argument("--jev-model", default="jev-latest")
    parser.add_argument("--confidence-threshold", type=float, default=0.8)
    args = vars(parser.parse_args())
    if args["record_ids"] is not None:
        args["record_ids"] = [item.strip() for item in args["record_ids"].split(",") if item.strip()]
        if not args["record_ids"]:
            parser.error("--record-ids must contain at least one ID")
    try:
        summary = run_jev_decision_eval(**args)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: value for key, value in summary.items() if key not in ("records", "questions")}, indent=2))
    if summary["classifier_error_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
