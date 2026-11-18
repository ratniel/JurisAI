from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

from src.eval.retrieval_eval import DEFAULT_RUNS_ROOT, RETRIEVAL_RUN_ARTIFACT_PREFIX


class LedgerExportCLITests(unittest.TestCase):
    def test_export_entrypoint_uses_the_shared_writer(self) -> None:
        output = StringIO()
        with patch("src.eval.retrieval_eval.refresh_run_log", return_value=Path("test-run-log.csv")) as refresh:
            with redirect_stdout(output):
                runpy.run_path("scripts/export_retrieval_run_log.py", run_name="__main__")
        refresh.assert_called_once_with(DEFAULT_RUNS_ROOT, artifact_prefix=RETRIEVAL_RUN_ARTIFACT_PREFIX)
        self.assertEqual(output.getvalue().strip(), "test-run-log.csv")
