from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.retrieval_eval import (
    DEFAULT_RUNS_ROOT,
    RETRIEVAL_RUN_ARTIFACT_PREFIX,
    refresh_run_log,
)


def main() -> None:
    log_path = refresh_run_log(
        DEFAULT_RUNS_ROOT, artifact_prefix=RETRIEVAL_RUN_ARTIFACT_PREFIX,
    )
    print(log_path)


if __name__ == "__main__":
    main()
