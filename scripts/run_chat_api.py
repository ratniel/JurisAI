from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import create_app
from src.config.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JurisAI FastAPI chat server.")
    parser.add_argument("--host", default=settings.api.host)
    parser.add_argument("--port", type=int, default=settings.api.port)
    parser.add_argument(
        "--reload",
        action="store_true",
        default=settings.api.reload,
        help="Enable autoreload for local development.",
    )
    args = parser.parse_args()

    uvicorn.run(
        "src.api.app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
