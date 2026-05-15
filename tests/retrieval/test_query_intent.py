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
        self.assertEqual(profile.discovery_query, profile.normalized_query)
        self.assertEqual(profile.fit_query, profile.normalized_query)

    def test_build_profile_preserves_separate_fit_query(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need SC scholarship help in Tamil Nadu.",
            retrieval_query="tamil nadu sc scholarship support",
            fit_query="eligibility: sc student in tamil nadu\nbenefits: scholarship or fee support",
            raw_filters={"state": "Tamil Nadu", "tags": ["SC", "student"]},
        )

        self.assertEqual(profile.discovery_query, "tamil nadu sc scholarship support")
        self.assertEqual(
            profile.fit_query,
            "eligibility: sc student in tamil nadu benefits: scholarship or fee support",
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
        self.assertEqual(profile.query_topics, ["education"])
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
        self.assertEqual(profile.query_topics, ["agriculture"])
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
        self.assertEqual(profile.filters.tags, ["SC"])
        self.assertEqual(
            profile.ignored_filters,
            {
                "level": ["Central", "State"],
                "tags": ["scholarship", "engineering", "SC"],
            },
        )
        self.assertEqual(profile.query_topics, [])

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

    def test_indicative_topic_filter_maps_to_lowercase_canonical_topic(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need scholarship help in Maharashtra.",
            retrieval_query="scholarship schemes for women in Maharashtra",
            raw_filters={
                "state": "Maharashtra",
                "topics": ["scholarship"],
                "tags": ["women"],
            },
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.topics, ["education"])
        self.assertEqual(profile.filters.tags, ["Women"])
        self.assertEqual(profile.query_topics, ["education"])
        self.assertEqual(profile.ignored_filters, {})

    def test_lowercase_and_indicative_topic_filters_are_preserved(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Need irrigation help for farming in Maharashtra.",
            retrieval_query="agriculture and irrigation support",
            raw_filters={
                "state": "Maharashtra",
                "topics": ["agriculture", "irrigation"],
            },
        )

        self.assertEqual(profile.filters.state, "Maharashtra")
        self.assertEqual(profile.filters.topics, ["agriculture"])
        self.assertEqual(profile.query_topics, ["agriculture"])
        self.assertEqual(profile.ignored_filters, {})

    def test_engineering_topic_filter_maps_to_education_and_science(self) -> None:
        profile = build_retrieval_intent_profile(
            user_message="Engineering fees are too high for me in Tamil Nadu.",
            retrieval_query="engineering scholarship support",
            raw_filters={
                "state": "Tamil Nadu",
                "topics": ["engineering"],
            },
        )

        self.assertEqual(
            profile.filters.topics,
            ["education", "science & research"],
        )
        self.assertEqual(
            profile.query_topics,
            ["education", "science & research"],
        )


if __name__ == "__main__":
    unittest.main()
