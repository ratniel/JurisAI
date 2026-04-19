from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agentic.debug_ui import create_agentic_debug_ui


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch the JurisAI agentic workflow debug UI."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=7861, type=int)
    parser.add_argument("--share", action="store_true")
    args = parser.parse_args()

    demo = create_agentic_debug_ui()
    demo.launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
