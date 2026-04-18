from __future__ import annotations

import unittest

from src.retrieval.rule_engine import build_qdrant_filter
from src.scheme_contracts import SchemeRuleFilters


class RuleEngineTests(unittest.TestCase):
    def test_state_filter_derives_provider_scope_and_central_fallback(self) -> None:
        query_filter, applied_filters, ignored_filters = build_qdrant_filter(
            SchemeRuleFilters(state="Maharashtra")
        )

        self.assertEqual(
            applied_filters,
            {
                "state": "Maharashtra",
                "level": "state",
                "provider": "Maharashtra",
            },
        )
        self.assertEqual(ignored_filters, {})
        self.assertIsNotNone(query_filter)
        self.assertIsNotNone(query_filter.min_should)
        self.assertEqual(query_filter.min_should.min_count, 1)
        self.assertEqual(len(query_filter.min_should.conditions), 2)
        state_scope = query_filter.min_should.conditions[0]
        central_scope = query_filter.min_should.conditions[1]
        self.assertIsNotNone(state_scope.must)
        self.assertEqual(len(state_scope.must or []), 2)
        self.assertEqual(state_scope.must[0].key, "level")
        self.assertEqual(state_scope.must[0].match.value, "state")
        self.assertEqual(state_scope.must[1].key, "provider")
        self.assertEqual(state_scope.must[1].match.value, "Maharashtra")
        self.assertEqual(central_scope.key, "level")
        self.assertEqual(central_scope.match.value, "central")

    def test_explicit_level_derives_provider_when_state_is_known(self) -> None:
        query_filter, applied_filters, ignored_filters = build_qdrant_filter(
            SchemeRuleFilters(state="Maharashtra", level="state")
        )

        self.assertIsNotNone(query_filter)
        self.assertEqual(len(query_filter.min_should.conditions), 2)
        self.assertEqual(
            applied_filters,
            {
                "state": "Maharashtra",
                "level": "state",
                "provider": "Maharashtra",
            },
        )
        self.assertEqual(ignored_filters, {"level": "state"})

    def test_non_state_topic_filters_are_ignored_by_rule_engine(self) -> None:
        _, applied_filters, ignored_filters = build_qdrant_filter(
            SchemeRuleFilters(
                state="Maharashtra",
                application_mode="offline",
                tags=["Farmer"],
                provider_type="state",
            )
        )

        self.assertEqual(
            applied_filters,
            {
                "state": "Maharashtra",
                "level": "state",
                "provider": "Maharashtra",
            },
        )
        self.assertEqual(
            ignored_filters,
            {
                "application_mode": "offline",
                "provider_type": "state",
                "tags": ["Farmer"],
            },
        )


if __name__ == "__main__":
    unittest.main()
