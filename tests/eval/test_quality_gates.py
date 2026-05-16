from __future__ import annotations

import unittest

from src.eval.quality_gates import (
    ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS,
    evaluate_summary_against_thresholds,
    record_passes_absolute_gate,
    record_passes_min_recall,
)


class RetrievalQualityGateTests(unittest.TestCase):
    def test_record_passes_min_recall_when_hits_meet_floor(self) -> None:
        self.assertTrue(record_passes_min_recall(hits_at_k=2, min_recall_at_k=2))
        self.assertFalse(record_passes_min_recall(hits_at_k=1, min_recall_at_k=2))

    def test_absolute_gate_fails_zero_hit_record(self) -> None:
        self.assertFalse(
            record_passes_absolute_gate(
                raw_hit_count=0,
                hits_at_k=2,
                min_recall_at_k=2,
                distractor_pass=True,
                filter_match=True,
            )
        )

    def test_absolute_gate_requires_all_components(self) -> None:
        self.assertTrue(
            record_passes_absolute_gate(
                raw_hit_count=4,
                hits_at_k=2,
                min_recall_at_k=2,
                distractor_pass=True,
                filter_match=True,
            )
        )
        self.assertFalse(
            record_passes_absolute_gate(
                raw_hit_count=4,
                hits_at_k=2,
                min_recall_at_k=2,
                distractor_pass=False,
                filter_match=True,
            )
        )

    def test_summary_thresholds_report_failures(self) -> None:
        summary = {
            "strict_record_pass_rate": 0.8,
            "per_record_min_recall_pass_rate": 1.0,
            "expected_filter_match_rate": 1.0,
            "zero_raw_hit_rate": 0.2,
        }

        failures = evaluate_summary_against_thresholds(
            summary=summary,
            thresholds=ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS,
        )

        self.assertEqual(len(failures), 2)
        self.assertIn("strict_record_pass_rate=0.800 is below 1.000", failures)
        self.assertIn("zero_raw_hit_rate=0.200 exceeds 0.000", failures)


if __name__ == "__main__":
    unittest.main()
