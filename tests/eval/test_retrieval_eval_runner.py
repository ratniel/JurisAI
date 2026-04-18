from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from src.eval.retrieval_dataset import GenerationProvenance, GoldenRecord
from src.eval.retrieval_eval import (
    _select_records,
    default_run_output_path,
    write_run_artifact,
)


class RetrievalEvalRunnerTests(unittest.TestCase):
    def test_select_records_preserves_requested_order(self) -> None:
        records = [
            GoldenRecord(
                record_id="retrieval_eval_001",
                persona_id="p1",
                user_query="one",
                must_retrieve_scheme_ids=["a", "b"],
                must_not_retrieve_scheme_ids=["c"],
                generation_provenance=GenerationProvenance(
                    source="test",
                    method="manual",
                ),
            ),
            GoldenRecord(
                record_id="retrieval_eval_002",
                persona_id="p1",
                user_query="two",
                must_retrieve_scheme_ids=["a", "b"],
                must_not_retrieve_scheme_ids=["c"],
                generation_provenance=GenerationProvenance(
                    source="test",
                    method="manual",
                ),
            ),
        ]

        with patch("src.eval.retrieval_eval.load_golden_records", return_value=records):
            selected = _select_records(["retrieval_eval_002", "retrieval_eval_001"])

        self.assertEqual(
            [record.record_id for record in selected],
            ["retrieval_eval_002", "retrieval_eval_001"],
        )

    def test_select_records_raises_for_unknown_record_id(self) -> None:
        records = [
            GoldenRecord(
                record_id="retrieval_eval_001",
                persona_id="p1",
                user_query="one",
                must_retrieve_scheme_ids=["a", "b"],
                must_not_retrieve_scheme_ids=["c"],
                generation_provenance=GenerationProvenance(
                    source="test",
                    method="manual",
                ),
            )
        ]

        with patch("src.eval.retrieval_eval.load_golden_records", return_value=records):
            with self.assertRaises(ValueError):
                _select_records(["retrieval_eval_404"])

    def test_default_output_path_uses_evals_runs_directory(self) -> None:
        path = default_run_output_path(
            started_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)
        )

        self.assertTrue(
            str(path).endswith(
                "evals/retrieval/runs/retrieval_eval_20260401T120000Z.json"
            )
        )

    def test_write_run_artifact_updates_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "retrieval_eval_20260401T120000Z.json"
            summary = {"record_count": 1, "records": []}

            write_run_artifact(summary, output_path)

            written = json.loads(output_path.read_text(encoding="utf-8"))
            latest = json.loads(
                (output_path.parent / "latest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(written["output_path"], str(output_path))
            self.assertEqual(latest["output_path"], str(output_path))
            self.assertEqual(latest["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
