from __future__ import annotations

import unittest

import gradio as gr
import pandas as pd

from src.eval.dashboard import (
    _build_live_record_payloads,
    _live_status_html,
    _render_run_snapshot,
)


class DashboardHelperTests(unittest.TestCase):
    def test_render_run_snapshot_only_autoselects_inspector_on_first_processed_record(self) -> None:
        run_data = {
            "started_at": "2026-04-11T10:00:00Z",
            "completed_at": None,
            "collection_name": "jurisai_eval",
            "eval_mode": "retrieval_core",
            "intent_provider": "local_openai",
            "intent_model": "test-intent",
            "generation_provider": "local_openai",
            "generation_model": "test-generation",
            "limit": 5,
            "output_path": None,
            "trace_project": "jurisai-retrieval-eval",
            "run_trace_id": None,
            "trace_status": {"enabled": False, "detail": "disabled for test"},
            "record_count": 1,
            "classifier_error_count": 0,
            "avg_recall_at_3": 1.0,
            "avg_recall_at_5": 1.0,
            "avg_mrr_at_5": 1.0,
            "distractor_pass_rate": 1.0,
            "expected_filter_match_rate": 1.0,
            "records": [
                {
                    "record_id": "retrieval_eval_001",
                    "persona_id": "p1",
                    "trace_id": "trace-001",
                    "user_query": "Need farmer support",
                    "expected_filters": {},
                    "required_query_terms": [],
                    "classification": {"retrieval_filters": []},
                    "retrieval_query": "farmer support",
                    "embed_query": "farmer support",
                    "query_topics": [],
                    "query_tags": [],
                    "query_terms": [],
                    "actual_filters": {},
                    "effective_eval_filters": {},
                    "applied_filters": {},
                    "ignored_filters": {},
                    "raw_hit_count": 2,
                    "recall_at_3": 1.0,
                    "recall_at_5": 1.0,
                    "mrr_at_5": 1.0,
                    "distractor_pass": True,
                    "expected_filter_match": True,
                    "used_classifier": True,
                    "classifier_error": None,
                    "must_retrieve_scheme_ids": ["scheme-a"],
                    "must_not_retrieve_scheme_ids": [],
                    "results": [
                        {
                            "scheme_id": "scheme-a",
                            "name": "Scheme A",
                            "state": "Maharashtra",
                            "level": "state",
                            "match_profile": "semantic",
                            "match_score": 0.95,
                            "adjusted_score": 0.95,
                            "match_reasons": ["semantic"],
                        }
                    ],
                    "debug": {"profiles": []},
                    "scheme_catalog": {},
                }
            ]
        }

        first_snapshot = _render_run_snapshot(
            run_data=run_data,
            sidebar_md="sidebar",
            sidebar_df=pd.DataFrame(),
            current_record_id="retrieval_eval_001",
            processed_count=1,
            total_count=3,
            is_running=True,
        )
        later_snapshot = _render_run_snapshot(
            run_data=run_data,
            sidebar_md="sidebar",
            sidebar_df=pd.DataFrame(),
            current_record_id="retrieval_eval_001",
            processed_count=2,
            total_count=3,
            is_running=True,
        )

        self.assertEqual(first_snapshot[6]["value"], "retrieval_eval_001")
        self.assertIn("retrieval_eval_001", first_snapshot[7])
        self.assertEqual(later_snapshot[7], gr.skip())
        self.assertEqual(later_snapshot[8], gr.skip())

    def test_live_record_payloads_include_current_inputs_and_outputs(self) -> None:
        run_data = {
            "avg_recall_at_5": 0.5,
            "distractor_pass_rate": 1.0,
            "expected_filter_match_rate": 1.0,
            "records": [
                {
                    "record_id": "retrieval_eval_005",
                    "persona_id": "p2_tamilnadu_sc_student",
                    "trace_id": "trace-123",
                    "user_query": "Any scholarship help?",
                    "expected_filters": {"state": "Tamil Nadu", "topics": ["Education"]},
                    "required_query_terms": ["Tamil Nadu", "scholarship"],
                    "classification": {
                        "retrieval_filters": [
                            {"key": "state", "value": "Tamil Nadu"},
                            {"key": "tags", "value": "SC"},
                        ]
                    },
                    "retrieval_query": "scholarship help",
                    "embed_query": "scholarship help Education",
                    "query_topics": ["Education"],
                    "query_tags": ["Student"],
                    "query_terms": ["student", "education"],
                    "actual_filters": {"state": "Tamil Nadu"},
                    "effective_eval_filters": {
                        "state": "Tamil Nadu",
                        "topics": ["Education"],
                        "tags": ["Student"],
                    },
                    "applied_filters": {"state": "Tamil Nadu"},
                    "ignored_filters": {},
                    "raw_hit_count": 8,
                    "recall_at_3": 0.5,
                    "recall_at_5": 0.5,
                    "mrr_at_5": 0.5,
                    "distractor_pass": True,
                    "expected_filter_match": True,
                    "used_classifier": True,
                    "classifier_error": None,
                    "must_retrieve_scheme_ids": ["scheme-a"],
                    "must_not_retrieve_scheme_ids": ["scheme-z"],
                    "results": [
                        {
                            "scheme_id": "scheme-a",
                            "name": "Scholarship A",
                            "state": "Tamil Nadu",
                            "level": "state",
                            "match_profile": "embedding_a",
                            "adjusted_score": 0.92,
                            "match_reasons": ["state_match", "topic:education"],
                        }
                    ],
                }
            ],
        }

        inputs, outputs = _build_live_record_payloads(run_data, "retrieval_eval_005")

        self.assertEqual(inputs["record_id"], "retrieval_eval_005")
        self.assertEqual(inputs["effective_eval_filters"]["topics"], ["Education"])
        self.assertEqual(outputs["trace_id"], "trace-123")
        self.assertEqual(outputs["retrieved_schemes"][0]["scheme_id"], "scheme-a")

    def test_live_status_html_shows_running_progress(self) -> None:
        run_data = {
            "avg_recall_at_5": 0.667,
            "distractor_pass_rate": 0.5,
            "expected_filter_match_rate": 0.333,
            "records": [
                {"record_id": "retrieval_eval_005", "persona_id": "p2_tamilnadu_sc_student"}
            ],
        }

        html = _live_status_html(
            run_data,
            current_record_id="retrieval_eval_005",
            processed_count=3,
            total_count=15,
            is_running=True,
        )

        self.assertIn("Running", html)
        self.assertIn("3/15", html)
        self.assertIn("retrieval_eval_005", html)
        self.assertIn("67%", html)
        self.assertIn("50%", html)
        self.assertIn("33%", html)


if __name__ == "__main__":
    unittest.main()
