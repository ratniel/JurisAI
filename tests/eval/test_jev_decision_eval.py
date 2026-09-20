from __future__ import annotations

import csv
import json
import tempfile
import unittest
from copy import deepcopy
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from src.agentic.models import PrimaryIntent, UserIntentClassification
from src.eval import jev_decision_eval as evaluation
from src.eval.retrieval_dataset import GenerationProvenance, GoldenRecord


def golden_record(**labels) -> GoldenRecord:
    return GoldenRecord(
        record_id="test_farmer", persona_id="test", user_query="Crop insurance in Maharashtra?",
        must_retrieve_scheme_ids=["a", "b"], must_not_retrieve_scheme_ids=["c"],
        notes="Synthetic test fixture, not a benchmark case.",
        generation_provenance=GenerationProvenance(source="test", method="manual"), **labels,
    )


def jev_response() -> dict:
    return {
        "model": "jev-test", "usage": {"input_tokens": 100, "output_tokens": 10},
        "answers": {
            name: {
                "type": "choice", "choice": selected, "confidence": 1.0,
                "probabilities": {option: float(option == selected) for option in question["criteria"]},
            }
            for (name, question), selected in zip(
                evaluation.QUESTIONS.items(), ("scheme_discovery", "no"), strict=True
            )
        },
    }


class JevDecisionEvalTests(unittest.TestCase):
    def test_response_validation_rejects_unusable_decisions(self) -> None:
        valid = jev_response()
        self.assertEqual(evaluation.validate_jev_response(valid), valid)
        invalid_answers = [
            {"choice": "invented"}, {"confidence": float("nan")},
            {"probabilities": {"scheme_discovery": 1.0}},
            {"type": "noul"}, {"confidence": True},
            {"probabilities": {k: 0.0 for k in valid["answers"]["primary_intent"]["probabilities"]}},
            {"choice": "out_of_scope"},
        ]
        for changes in invalid_answers:
            with self.subTest(changes=changes):
                payload = deepcopy(valid)
                payload["answers"]["primary_intent"].update(changes)
                with self.assertRaises(ValueError):
                    evaluation.validate_jev_response(payload)
        del valid["answers"]["needs_clarification"]
        with self.assertRaises(ValueError):
            evaluation.validate_jev_response(valid)

    def test_dry_run_never_calls_models_and_persists_to_existing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(evaluation, "DEFAULT_RUNS_ROOT", Path(directory)), \
             patch.object(evaluation, "_select_records", return_value=[golden_record()]), \
             patch.object(evaluation, "build_generation_client") as baseline, \
             patch.object(evaluation, "call_jev") as jev:
            summary = evaluation.run_jev_decision_eval(dry_run=True)
            baseline.assert_not_called()
            jev.assert_not_called()
            self.assertEqual(summary["eval_mode"], "jev_decisions_dry_run")
            self.assertIsNone(summary["metrics"]["primary_intent"]["agreement_rate"])
            self.assertIsNone(summary["metrics"]["primary_intent"]["jev"]["accuracy"])
            self.assertEqual(json.loads(Path(summary["output_path"]).read_text()), json.loads((Path(directory) / "latest.json").read_text()))
            with (Path(directory) / "run_log.csv").open() as handle:
                ledger = list(csv.DictReader(handle))
            self.assertEqual(ledger[0]["eval_mode"], "jev_decisions_dry_run")

    def test_comparison_uses_same_context_and_distinguishes_accuracy_from_agreement(self) -> None:
        labeled = golden_record(expected_primary_intent="scheme_discovery", expected_needs_clarification=False)
        classifier = Mock()
        classifier.classify.return_value = UserIntentClassification(
            primary_intent=PrimaryIntent.OUT_OF_SCOPE, confidence=0.95,
            user_goal="test", needs_clarification=False, reasoning="test",
        )
        client = Mock(invocation_history=[])
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(evaluation, "DEFAULT_RUNS_ROOT", Path(directory)), \
             patch.object(evaluation, "_select_records", return_value=[labeled, golden_record()]), \
             patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), \
             patch.object(evaluation, "build_generation_client", return_value=client), \
             patch.object(evaluation, "UserIntentClassifier", return_value=classifier), \
             patch.object(evaluation, "call_jev", return_value=jev_response()):
            summary = evaluation.run_jev_decision_eval()
        metrics = summary["metrics"]["primary_intent"]
        self.assertEqual(metrics["agreement_rate"], 0)
        self.assertEqual(metrics["paired_count"], 2)
        self.assertEqual(metrics["jev"]["labeled_count"], 1)
        self.assertEqual(metrics["jev"]["accuracy"], 1)
        self.assertEqual(metrics["baseline"]["confident_wrong_count"], 1)
        self.assertIsNone(summary["metrics"]["needs_clarification"]["baseline"]["confident_wrong_count"])
        baseline_args = classifier.classify.call_args.kwargs
        baseline_state = evaluation._build_classifier_prompt(
            user_message=baseline_args["user_message"],
            session_memory=baseline_args["session_snapshot"].to_session_memory(),
        )
        self.assertEqual(summary["records"][1]["jev_request"]["state"], baseline_state)

    def test_provider_failure_is_recorded_without_counting_it_as_agreement(self) -> None:
        classifier = Mock()
        classifier.classify.side_effect = RuntimeError("secret should not be persisted")
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(evaluation, "DEFAULT_RUNS_ROOT", Path(directory)), \
             patch.object(evaluation, "_select_records", return_value=[golden_record()]), \
             patch.dict("os.environ", {"TYPESAFE_API_KEY": "test-only"}), \
             patch.object(evaluation, "build_generation_client", return_value=Mock(invocation_history=[])), \
             patch.object(evaluation, "UserIntentClassifier", return_value=classifier), \
             patch.object(evaluation, "call_jev", return_value=jev_response()):
            summary = evaluation.run_jev_decision_eval()
            artifact = Path(summary["output_path"]).read_text()
        self.assertEqual(summary["classifier_error_count"], 1)
        self.assertIsNone(summary["metrics"]["primary_intent"]["agreement_rate"])
        self.assertEqual(summary["metrics"]["jev"]["successful_count"], 1)
        self.assertNotIn("secret should not be persisted", artifact)

    def test_http_call_uses_documented_contract_and_propagates_status(self) -> None:
        payload = {"state": "test", "questions": evaluation.QUESTIONS, "model": "jev-latest"}
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(jev_response())
        with patch.object(evaluation, "urlopen", return_value=response) as transport:
            evaluation.call_jev(payload, "test-only")
        request = transport.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only")
        with patch.object(evaluation, "urlopen", side_effect=HTTPError(request.full_url, 429, "rate limited", Message(), None)):
            with self.assertRaises(HTTPError):
                evaluation.call_jev(payload, "test-only")


if __name__ == "__main__":
    unittest.main()
