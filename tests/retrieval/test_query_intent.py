from __future__ import annotations

import unittest

from src.retrieval.query_intent import build_retrieval_intent_profile


class RetrievalIntentProfileTests(unittest.TestCase):
    def test_build_profile_infers_state_but_not_topics_from_query_text(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="maharashtra vidarbha kisan hu crop loss hua kuch govt insurance subsidy scheme batao",
            retrieval_query=None,
            raw_filters={},
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.topics, [])
        self.assertEqual(profile.query_topics, [])
        self.assertEqual(
            profile.normalized_query,
            "maharashtra vidarbha kisan hu crop loss hua kuch govt insurance subsidy scheme batao",
        )

    def test_build_profile_preserves_state_without_softening_free_text_filters(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="I am a minority student in Maharashtra. What schemes can help me?",
            retrieval_query="schemes for minority students",
            raw_filters={
                "demographic": "minority",
                "occupation": "student",
                "location": "Maharashtra",
            },
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.tags, ["Student"])
        self.assertEqual(profile.query_tags, ["Student"])
        self.assertEqual(profile.query_topics, ["Education"])
        self.assertEqual(
            profile.ignored_filters,
            {
                "demographic": "minority",
            },
        )

    def test_unknown_filter_is_preserved_as_ignored(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need a scholarship.",
            retrieval_query="scholarship",
            raw_filters={"mystery_key": "mystery_value"},
        )

        self.assertEqual(profile.ignored_filters, {"mystery_key": "mystery_value"})

    def test_free_text_tags_are_ignored_instead_of_becoming_soft_intent(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need a farmer support scheme in Maharashtra.",
            retrieval_query="farmer support scheme",
            raw_filters={"state": "Maharashtra", "tags": ["farmer"]},
        )

        self.assertEqual(profile.filters.tags, ["Farmer"])
        self.assertEqual(profile.query_tags, ["Farmer"])
        self.assertEqual(profile.query_topics, ["Agriculture"])
        self.assertEqual(profile.query_terms, [])

    def test_conflicting_scalar_filters_are_ignored_without_dropping_tag_lists(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Tamil Nadu SC student needs engineering scholarship help.",
            retrieval_query="scholarship help for engineering fees for SC category student in Tamil Nadu",
            raw_filters={
                "state": "Tamil Nadu",
                "level": ["Central", "State"],
                "tags": ["scholarship", "engineering", "SC"],
            },
        )

        self.assertEqual(profile.filters.state, "Tamil Nadu")
        self.assertIsNone(profile.filters.level)
        self.assertEqual(profile.filters.tags, ["SC", "Student"])
        self.assertEqual(
            profile.ignored_filters,
            {
                "level": ["Central", "State"],
                "tags": ["scholarship", "engineering", "SC"],
            },
        )
        self.assertEqual(profile.query_topics, ["Education"])

    def test_invalid_literal_filters_are_ignored_instead_of_crashing(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need agriculture support in Maharashtra.",
            retrieval_query="agriculture support in Maharashtra",
            raw_filters={
                "state": "Maharashtra",
                "level": "agriculture support",
                "provider_type": "government",
            },
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertIsNone(profile.filters.level)
        self.assertIsNone(profile.filters.provider_type)
        self.assertEqual(
            profile.ignored_filters,
            {
                "level": "agriculture support",
                "provider_type": "government",
            },
        )

    def test_noncanonical_topic_filter_is_ignored(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need help to learn computers in Maharashtra.",
            retrieval_query="computer training schemes for women in Maharashtra",
            raw_filters={
                "state": "Maharashtra",
                "topics": ["computer training"],
                "tags": ["women"],
            },
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.topics, [])
        self.assertEqual(profile.filters.tags, ["Women"])
        self.assertEqual(profile.query_topics, ["Women Welfare"])
        self.assertEqual(
            profile.ignored_filters,
            {"topics": ["computer training"]},
        )

    def test_build_profile_infers_women_tag_from_query_text(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="I am a woman entrepreneur in Maharashtra. Which schemes can help me start and grow?",
            retrieval_query="government schemes for women entrepreneurs in Maharashtra",
            raw_filters={"state": "Maharashtra"},
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.tags, ["Women"])
        self.assertEqual(profile.query_tags, ["Women"])
        self.assertEqual(profile.query_topics, ["Women Welfare"])


if __name__ == "__main__":
    unittest.main()
