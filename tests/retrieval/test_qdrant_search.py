from __future__ import annotations

import unittest

from src.agentic.models import MongoReference, RetrievedScheme
from src.retrieval.qdrant_search import QdrantSchemeSearchClient
from src.scheme_contracts import FilterableApplicationModes


def make_retrieved_scheme(
    *,
    scheme_id: str,
    name: str,
    level: str,
    state: str | None,
    score: float,
    profile: str = "embedding_a",
) -> RetrievedScheme:
    return RetrievedScheme(
        scheme_id=scheme_id,
        name=name,
        url=f"https://example.com/{scheme_id}",
        level=level,
        provider="Example",
        provider_type="state" if level == "state" else "ministry",
        state=state,
        ministry=None,
        tags=[],
        topics=[],
        application_modes=FilterableApplicationModes(),
        selected_fields={},
        mongo_ref=MongoReference(),
        match_profile=profile,
        match_score=score,
        matched_profiles=[profile],
        profile_scores={profile: score},
    )


class QdrantSearchTests(unittest.TestCase):
    def test_dedupe_keeps_highest_scoring_profile_for_same_scheme(self) -> None:
        hits = [
            make_retrieved_scheme(
                scheme_id="scheme-a",
                name="Scheme A",
                level="central",
                state=None,
                score=0.41,
                profile="embedding_a",
            ).model_copy(update={"selected_fields": {"details": "Scheme purpose"}}),
            make_retrieved_scheme(
                scheme_id="scheme-a",
                name="Scheme A",
                level="central",
                state=None,
                score=0.73,
                profile="embedding_b",
            ).model_copy(
                update={
                    "selected_fields": {
                        "benefits": "Scheme benefit",
                        "eligibility": "Mandatory condition",
                    }
                }
            ),
        ]

        deduped = QdrantSchemeSearchClient._dedupe_hits(
            [self._to_point(hit) for hit in hits]
        )

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].scheme_id, "scheme-a")
        self.assertEqual(deduped[0].match_profile, "embedding_b")
        self.assertEqual(deduped[0].match_score, 0.73)
        self.assertEqual(sorted(deduped[0].matched_profiles), ["embedding_a", "embedding_b"])
        self.assertEqual(
            deduped[0].selected_fields,
            {
                "details": "Scheme purpose",
                "benefits": "Scheme benefit",
                "eligibility": "Mandatory condition",
            },
        )

    def test_dedupe_preserves_raw_score_order_without_reranking(self) -> None:
        hits = [
            make_retrieved_scheme(
                scheme_id="scheme-low",
                name="Scheme Low",
                level="central",
                state=None,
                score=0.42,
            ),
            make_retrieved_scheme(
                scheme_id="scheme-high",
                name="Scheme High",
                level="state",
                state="Maharashtra",
                score=0.91,
            ),
            make_retrieved_scheme(
                scheme_id="scheme-mid",
                name="Scheme Mid",
                level="central",
                state=None,
                score=0.57,
            ),
        ]

        deduped = QdrantSchemeSearchClient._dedupe_hits(
            [self._to_point(hit) for hit in hits]
        )

        self.assertEqual(
            [hit.scheme_id for hit in deduped],
            ["scheme-high", "scheme-mid", "scheme-low"],
        )
        self.assertTrue(all(hit.adjusted_score is None for hit in deduped))
        self.assertTrue(all(hit.match_reasons == [] for hit in deduped))

    @staticmethod
    def _to_point(hit: RetrievedScheme):
        class Point:
            def __init__(self, scheme: RetrievedScheme) -> None:
                self.id = scheme.scheme_id
                self.score = scheme.match_score
                self.payload = {
                    "scheme_id": scheme.scheme_id,
                    "name": scheme.name,
                    "url": scheme.url,
                    "level": scheme.level,
                    "provider": scheme.provider,
                    "provider_type": scheme.provider_type,
                    "state": scheme.state,
                    "ministry": scheme.ministry,
                    "tags": scheme.tags,
                    "topics": scheme.topics,
                    "application_modes": scheme.application_modes.model_dump(),
                    "selected_fields": scheme.selected_fields,
                    "mongo_ref": scheme.mongo_ref.model_dump(),
                    "embedding_profile": scheme.match_profile,
                }

        return Point(hit)


if __name__ == "__main__":
    unittest.main()
