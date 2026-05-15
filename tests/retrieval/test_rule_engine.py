from __future__ import annotations

import unittest

from src.retrieval.rule_engine import build_qdrant_filter


class RuleEngineTests(unittest.TestCase):
    def test_topics_only_filter_accepts_legacy_topic_casing(self) -> None:
        query_filter, applied_filters, ignored_filters = build_qdrant_filter(
            {"topics": ["education"]},
            filter_mode="topics_only",
        )

        self.assertEqual(applied_filters, {"topics": ["education"]})
        self.assertEqual(ignored_filters, {})
        self.assertIsNotNone(query_filter)
        topic_condition = query_filter.must[0]
        self.assertEqual(sorted(topic_condition.match.any), ["Education", "education"])

    def test_state_hard_topics_soft_applies_only_state_filter(self) -> None:
        query_filter, applied_filters, ignored_filters = build_qdrant_filter(
            {"state": "Tamil Nadu", "topics": ["education"]},
            filter_mode="state_hard_topics_soft",
        )

        self.assertEqual(
            applied_filters,
            {
                "state": "Tamil Nadu",
                "level": "state",
                "provider": "Tamil Nadu",
            },
        )
        self.assertEqual(ignored_filters, {})
        self.assertIsNotNone(query_filter)
        self.assertEqual(query_filter.must, None)
        self.assertEqual(len(query_filter.should or []), 2)


if __name__ == "__main__":
    unittest.main()
