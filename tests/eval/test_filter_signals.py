from __future__ import annotations

import unittest

from src.eval.filter_signals import (
    build_effective_filter_signals,
    filters_match_expected,
)


class FilterSignalTests(unittest.TestCase):
    def test_effective_filter_signals_only_include_applied_filters(self) -> None:
        effective = build_effective_filter_signals(
            actual_filters={"state": "Tamil Nadu", "tags": ["SC"], "topics": []},
            query_tags=["Student"],
            query_topics=["Education"],
        )

        self.assertEqual(effective["state"], "Tamil Nadu")
        self.assertEqual(effective["tags"], ["SC"])
        self.assertNotIn("topics", effective)

    def test_filter_match_does_not_credit_soft_topic_signals(self) -> None:
        self.assertFalse(
            filters_match_expected(
                expected_filters={"state": "Tamil Nadu", "topics": ["Education"]},
                actual_filters={"state": "Tamil Nadu", "tags": ["SC"], "topics": []},
                query_tags=["Student"],
                query_topics=["Education"],
            )
        )


if __name__ == "__main__":
    unittest.main()
