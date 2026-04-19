from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.eval.retrieval_dataset import GenerationProvenance, GoldenRecord
from src.eval.agentic_workflow_eval import iter_agentic_workflow_eval
from src.eval.retrieval_eval import (
    _select_records,
    default_run_output_path,
    iter_retrieval_eval,
    write_run_artifact,
)


class RetrievalEvalRunnerTests(unittest.TestCase):
    @staticmethod
    def _record(record_id: str = "retrieval_eval_001") -> GoldenRecord:
        return GoldenRecord(
            record_id=record_id,
            persona_id="p1",
            user_query="one",
            must_retrieve_scheme_ids=["scheme-a", "scheme-c"],
            must_not_retrieve_scheme_ids=["scheme-b"],
            generation_provenance=GenerationProvenance(
                source="test",
                method="manual",
            ),
        )

    def test_select_records_preserves_requested_order(self) -> None:
        records = [
            self._record("retrieval_eval_001"),
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
        records = [self._record("retrieval_eval_001")]

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

    def test_iter_retrieval_eval_persists_partial_artifact_on_close(self) -> None:
        record = self._record()
        output_path = Path("/tmp/retrieval_eval_partial.json")
        fake_profile = SimpleNamespace(
            normalized_query="one",
            filters=SimpleNamespace(model_dump=lambda exclude_none=True: {"state": "Maharashtra"}),
            query_tags=[],
            query_topics=[],
            query_terms=[],
            ignored_filters={},
        )
        fake_classification = SimpleNamespace(
            retrieval_query="one",
            retrieval_filters=[],
            model_dump=lambda mode="json", exclude_none=True: {"retrieval_query": "one"},
        )
        fake_retriever = SimpleNamespace(
            search=lambda **kwargs: {
                "results": [{"scheme_id": "scheme-a"}],
                "raw_hit_count": 1,
                "applied_filters": {},
                "ignored_filters": {},
                "debug": {},
            }
        )

        with (
            patch(
                "src.eval.retrieval_eval.configure_phoenix_tracing",
                return_value=SimpleNamespace(enabled=False, detail="disabled"),
            ),
            patch("src.eval.retrieval_eval.load_golden_records", return_value=[record]),
            patch("src.eval.retrieval_eval.build_generation_client", return_value=object()),
            patch("src.eval.retrieval_eval.UserIntentClassifier") as classifier_cls,
            patch(
                "src.eval.retrieval_eval.build_retrieval_intent_profile",
                return_value=fake_profile,
            ),
            patch(
                "src.eval.retrieval_eval.QdrantSchemeSearchClient",
                return_value=fake_retriever,
            ),
            patch("src.eval.retrieval_eval.write_run_artifact") as write_artifact,
        ):
            classifier_cls.return_value.classify.return_value = fake_classification

            iterator = iter_retrieval_eval(
                limit=5,
                collection_name="schemes",
                output_path=output_path,
                persist_artifact=True,
            )

            next(iterator)
            iterator.close()

        write_artifact.assert_called_once()
        summary, written_path = write_artifact.call_args.args
        self.assertEqual(written_path, output_path)
        self.assertEqual(len(summary["records"]), 1)
        self.assertEqual(summary["records"][0]["record_id"], record.record_id)
        self.assertIsNotNone(summary["completed_at"])

    def test_iter_agentic_eval_persists_partial_artifact_on_close(self) -> None:
        record = self._record()
        output_path = Path("/tmp/agentic_eval_partial.json")
        fake_workflow_result = SimpleNamespace(
            classification=SimpleNamespace(
                retrieval_query="one",
                model_dump=lambda mode="json", exclude_none=True: {"retrieval_query": "one"},
            ),
            decision=SimpleNamespace(
                tool_payload={
                    "tool_calls": [],
                    "retrieved_schemes": [{"scheme_id": "scheme-a"}],
                    "query_topics": [],
                    "query_tags": [],
                    "query_terms": [],
                    "applied_filters": {},
                    "ignored_filters": {},
                    "raw_hit_count": 1,
                },
                response="answer",
            ),
            workflow_trace=[],
        )

        with (
            patch(
                "src.observability.configure_phoenix_tracing",
                return_value=SimpleNamespace(enabled=False, detail="disabled"),
            ),
            patch(
                "src.eval.agentic_workflow_eval._select_records",
                return_value=[record],
            ),
            patch(
                "src.eval.agentic_workflow_eval._run_agentic_turn",
                return_value=fake_workflow_result,
            ),
            patch("src.eval.agentic_workflow_eval.write_run_artifact") as write_artifact,
        ):
            iterator = iter_agentic_workflow_eval(
                limit=5,
                collection_name="schemes",
                output_path=output_path,
                persist_artifact=True,
            )

            next(iterator)
            iterator.close()

        write_artifact.assert_called_once()
        summary, written_path = write_artifact.call_args.args
        self.assertEqual(written_path, output_path)
        self.assertEqual(summary["eval_mode"], "agentic_workflow")
        self.assertEqual(len(summary["records"]), 1)
        self.assertEqual(summary["records"][0]["record_id"], record.record_id)
        self.assertIsNotNone(summary["completed_at"])


if __name__ == "__main__":
    unittest.main()
