from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.eval.dashboard import create_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch the Gradio retrieval evaluation dashboard."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind the dashboard server to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to bind the dashboard server to.",
    )
    parser.add_argument(
        "--collection",
        default=settings.eval.qdrant_collection,
        help="Default Qdrant collection to inspect and score.",
    )
    parser.add_argument(
        "--trace-project",
        default=settings.phoenix.project_name,
        help="Phoenix project name to use for dashboard-triggered runs.",
    )
    parser.add_argument(
        "--phoenix-endpoint",
        default=settings.phoenix.collector_endpoint,
        help="Optional Phoenix collector endpoint override.",
    )
    args = parser.parse_args()

    demo = create_dashboard(
        default_collection_name=args.collection,
        default_trace_project=args.trace_project,
        default_phoenix_endpoint=args.phoenix_endpoint,
    )
    demo.launch(server_name=args.host, server_port=args.port, share=False)


if __name__ == "__main__":
    main()
