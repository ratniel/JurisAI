from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.eval import refresh_retrieval_run_log


def main() -> None:
    log_path = refresh_retrieval_run_log()
    print(log_path)


if __name__ == "__main__":
    main()
