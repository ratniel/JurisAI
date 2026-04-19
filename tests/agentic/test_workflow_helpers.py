from __future__ import annotations

import unittest
from unittest.mock import Mock

from bson import ObjectId

from src.agentic.fact_utils import aggregate_intent_facts
from src.agentic.models import (
    IntentFact,
    MongoReference,
    RetrievedScheme,
    SchemeRef,
    SessionSnapshot,
    UserIntentClassification,
)
from src.agentic.workflow import (
    build_grounding_pack,
    build_relevant_scheme_from_lookup_document,
    build_top_schemes_artifact,
    fallback_retrieval_plan,
    merge_retrieved_scheme_results,
    BasicAgenticWorkflow,
    preferred_hydration_collections,
)
from src.agentic.models import RetrievalToolName
from src.scheme_contracts import FilterableApplicationModes


class WorkflowHelperTests(unittest.TestCase):
    @staticmethod
    def _make_retrieved_scheme(**overrides) -> RetrievedScheme:
        payload = {
            "scheme_id": "scheme-1",
            "name": "Test Scheme",
            "url": "https://example.com/scheme-1",
            "level": "state",
            "provider": "Maharashtra",
            "provider_type": "state",
            "state": "Maharashtra",
            "ministry": None,
            "tags": ["Student", "Higher Education"],
            "topics": ["Education"],
            "application_modes": {"online": True, "offline": False},
            "selected_fields": {
                "details": "Support for students in Maharashtra.",
                "benefits": "Scholarship support.",
                "eligibility": "Must be a student in Maharashtra.",
            },
            "mongo_ref": {},
            "match_profile": "embedding_a",
            "match_score": 0.5,
            "matched_profiles": ["embedding_a"],
            "profile_scores": {"embedding_a": 0.5},
            "match_reasons": ["Strong education topic match."],
        }
        payload.update(overrides)
        return RetrievedScheme.model_validate(payload)

    def test_aggregate_intent_facts_preserves_repeated_values(self) -> None:
        payload = aggregate_intent_facts(
            [
                IntentFact(key="tags", value="scholarship"),
                IntentFact(key="tags", value="engineering"),
                IntentFact(key="level", value="Central"),
                IntentFact(key="level", value="State"),
            ]
        )

        self.assertEqual(payload["tags"], ["scholarship", "engineering"])
        self.assertEqual(payload["level"], ["Central", "State"])

    def test_preferred_hydration_collections_prioritize_enriched_documents(self) -> None:
        self.assertEqual(
            preferred_hydration_collections("test_schemes"),
            ("test_schemes_enriched", "test_schemes"),
        )
        self.assertEqual(
            preferred_hydration_collections("schemes"),
            ("schemes_enriched", "schemes"),
        )

    def test_raw_document_hydration_builds_enriched_fields(self) -> None:
        scheme = RetrievedScheme(
            scheme_id="scheme-1",
            name="Test Scheme",
            url="https://example.com/scheme-1",
            level="state",
            provider="Maharashtra",
            provider_type="state",
            state="Maharashtra",
            ministry=None,
            tags=["Student", "Higher Education"],
            topics=["Education"],
            application_modes=FilterableApplicationModes(),
            selected_fields={},
            mongo_ref=MongoReference(),
            match_profile="embedding_a",
            match_score=0.5,
            matched_profiles=["embedding_a"],
            profile_scores={"embedding_a": 0.5},
        )
        raw_document = {
            "_id": "6999a539e00a48eb32037a47",
            "url": "https://example.com/scheme-1",
            "name": "Test Scheme",
            "level": "state",
            "provider": "Maharashtra",
            "tags": ["Student", "Higher Education"],
            "details": "Support for students in Maharashtra.",
            "benefits": "Scholarship support.",
            "eligibility": "Must be a student in Maharashtra.",
            "application_process": "Online\nApply through the state scholarship portal.",
        }

        relevant = build_relevant_scheme_from_lookup_document(
            document=raw_document,
            collection_name="test_schemes",
            scheme=scheme,
        )

        self.assertEqual(relevant.provider_type, "state")
        self.assertEqual(relevant.state, "Maharashtra")
        self.assertTrue(relevant.application_modes.online)
        self.assertIn("Education", relevant.topics)

    def test_session_snapshot_to_session_memory_prefers_scheme_refs(self) -> None:
        session_snapshot = SessionSnapshot(
            chat_session_id="chat-123",
            user_profile={"state": "Maharashtra"},
            conversation_summary="User is looking for education support.",
            relevant_schemes=[
                build_relevant_scheme_from_lookup_document(
                    document={
                        "_id": "6999a539e00a48eb32037a47",
                        "url": "https://example.com/scheme-1",
                        "name": "Test Scheme",
                        "level": "state",
                        "provider": "Maharashtra",
                        "tags": ["Student", "Higher Education"],
                        "details": "Support for students in Maharashtra.",
                        "benefits": "Scholarship support.",
                        "eligibility": "Must be a student in Maharashtra.",
                        "application_process": "Online\nApply through the portal.",
                    },
                    collection_name="test_schemes",
                    scheme=self._make_retrieved_scheme(),
                )
            ],
        )

        session_memory = session_snapshot.to_session_memory()

        self.assertEqual(session_memory.chat_session_id, "chat-123")
        self.assertEqual(session_memory.user_profile["state"], "Maharashtra")
        self.assertEqual(len(session_memory.recent_scheme_refs), 1)
        self.assertEqual(session_memory.recent_scheme_refs[0].name, "Test Scheme")

    def test_fallback_retrieval_plan_prefers_state_and_topic_tools(self) -> None:
        classification = UserIntentClassification.model_validate(
            {
                "primary_intent": "scheme_discovery",
                "confidence": 0.9,
                "user_goal": "Find help",
                "retrieval_query": "farmer support scheme",
                "retrieval_filters": [
                    {"key": "state", "value": "Maharashtra"},
                    {"key": "topics", "value": "Agriculture"},
                ],
                "reasoning": "Benefits lookup.",
            }
        )

        plan = fallback_retrieval_plan(
            user_message="Need a farmer support scheme in Maharashtra.",
            classification=classification,
            session_snapshot=SessionSnapshot(),
        )

        self.assertEqual(
            [call.tool_name for call in plan.tool_calls],
            [
                RetrievalToolName.STATE_SCOPED_SEARCH,
                RetrievalToolName.TOPIC_SCOPED_SEARCH,
            ],
        )

    def test_merge_retrieved_scheme_results_keeps_best_score_across_tool_calls(self) -> None:
        merged = merge_retrieved_scheme_results(
            [
                {
                    "output_payload": {
                        "retrieved_schemes": [
                            {
                                "scheme_id": "scheme-a",
                                "name": "Scheme A",
                                "url": "https://example.com/a",
                                "level": "state",
                                "provider": "Maharashtra",
                                "provider_type": "state",
                                "state": "Maharashtra",
                                "ministry": None,
                                "tags": [],
                                "topics": ["Agriculture"],
                                "application_modes": {"online": False, "offline": False},
                                "selected_fields": {},
                                "mongo_ref": {},
                                "match_profile": "embedding_a",
                                "match_score": 0.41,
                                "matched_profiles": ["embedding_a"],
                                "profile_scores": {"embedding_a": 0.41},
                                "match_reasons": [],
                            }
                        ]
                    }
                },
                {
                    "output_payload": {
                        "retrieved_schemes": [
                            {
                                "scheme_id": "scheme-a",
                                "name": "Scheme A",
                                "url": "https://example.com/a",
                                "level": "state",
                                "provider": "Maharashtra",
                                "provider_type": "state",
                                "state": "Maharashtra",
                                "ministry": None,
                                "tags": [],
                                "topics": ["Agriculture"],
                                "application_modes": {"online": False, "offline": False},
                                "selected_fields": {},
                                "mongo_ref": {},
                                "match_profile": "embedding_b",
                                "match_score": 0.77,
                                "matched_profiles": ["embedding_b"],
                                "profile_scores": {"embedding_b": 0.77},
                                "match_reasons": [],
                            }
                        ]
                    }
                },
            ],
            limit=5,
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["scheme_id"], "scheme-a")
        self.assertEqual(merged[0]["match_profile"], "embedding_b")
        self.assertEqual(merged[0]["match_score"], 0.77)

    def test_build_grounding_pack_creates_compact_cards(self) -> None:
        relevant_scheme = build_relevant_scheme_from_lookup_document(
            document={
                "_id": "6999a539e00a48eb32037a47",
                "url": "https://example.com/scheme-1",
                "name": "Test Scheme",
                "level": "state",
                "provider": "Maharashtra",
                "tags": ["Student", "Higher Education"],
                "details": "Support for students in Maharashtra.",
                "benefits": "Scholarship support for higher education students.",
                "eligibility": "Must be a student living in Maharashtra.",
                "documents_required": "Income certificate and domicile proof.",
                "application_process": "Online\nApply through the portal.",
            },
            collection_name="test_schemes",
            scheme=self._make_retrieved_scheme(),
        )

        grounding_pack = build_grounding_pack(
            chat_session_id="chat-123",
            turn_id="turn-123",
            user_message="Need scholarship help in Maharashtra.",
            retrieval_query="scholarship help maharashtra",
            relevant_schemes=[relevant_scheme],
            applied_filters={"state": "Maharashtra"},
            ignored_filters={"beneficiary": "girl student"},
            important_ignored_filters={"beneficiary": "girl student"},
            selected_scheme_ref=SchemeRef(
                scheme_id="scheme-1",
                name="Test Scheme",
                state="Maharashtra",
                level="state",
                provider="Maharashtra",
            ),
        )

        self.assertEqual(grounding_pack.chat_session_id, "chat-123")
        self.assertEqual(len(grounding_pack.top_scheme_cards), 1)
        self.assertIn("Test Scheme", grounding_pack.selection_hint or "")
        self.assertEqual(
            grounding_pack.important_ignored_filters["beneficiary"],
            "girl student",
        )
        self.assertTrue(grounding_pack.top_scheme_cards[0].evidence_snippets)

    def test_build_top_schemes_artifact_preserves_richer_fields(self) -> None:
        relevant_scheme = build_relevant_scheme_from_lookup_document(
            document={
                "_id": "6999a539e00a48eb32037a47",
                "url": "https://example.com/scheme-1",
                "name": "Test Scheme",
                "level": "state",
                "provider": "Maharashtra",
                "tags": ["Student", "Higher Education"],
                "details": "Support for students in Maharashtra.",
                "benefits": "Scholarship support.",
                "eligibility": "Must be a student in Maharashtra.",
                "documents_required": "Income certificate.",
                "application_process": "Online\nApply through the portal.",
            },
            collection_name="test_schemes",
            scheme=self._make_retrieved_scheme(),
        )

        artifact = build_top_schemes_artifact(
            chat_session_id="chat-123",
            turn_id="turn-123",
            relevant_schemes=[relevant_scheme],
        )

        self.assertEqual(artifact.chat_session_id, "chat-123")
        self.assertEqual(artifact.turn_id, "turn-123")
        self.assertEqual(artifact.artifact_type, "top_schemes")
        self.assertEqual(artifact.schemes[0].name, "Test Scheme")
        self.assertIn("Scholarship support", artifact.schemes[0].benefits or "")


class _FakeCursor:
    def __init__(self, documents):
        self._documents = documents

    async def to_list(self, *, length):
        return list(self._documents)


class _FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def find(self, query):
        self.queries.append(query)
        requested_ids = set(query["_id"]["$in"])
        matched = [document for document in self.documents if document["_id"] in requested_ids]
        return _FakeCursor(matched)


class _FakeDatabase:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, collection_name):
        return self._collections[collection_name]


class _FakeMongoClient:
    def __init__(self, databases):
        self._databases = databases
        self.closed = False

    def __getitem__(self, database_name):
        return self._databases[database_name]

    async def close(self):
        self.closed = True


class WorkflowMongoClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_hydration_reuses_injected_mongo_client_without_closing_it(self) -> None:
        document_id = ObjectId()
        enriched_collection = _FakeCollection(
            [
                {
                    "_id": document_id,
                    "url": "https://example.com/scheme-1",
                    "name": "Hydrated Scheme",
                    "level": "state",
                    "provider": "Maharashtra",
                    "tags": ["Student"],
                    "details": "Hydrated details from Mongo.",
                    "benefits": "Hydrated benefits.",
                    "eligibility": "Hydrated eligibility.",
                }
            ]
        )
        fake_client = _FakeMongoClient(
            {
                "jurisai": _FakeDatabase(
                    {
                        "schemes_enriched": enriched_collection,
                        "schemes": _FakeCollection([]),
                    }
                )
            }
        )
        workflow = BasicAgenticWorkflow(
            llm=Mock(),
            classifier=Mock(),
            retriever=Mock(),
            mongo_client=fake_client,
        )

        hydrated = await workflow._hydrate_relevant_schemes(
            [
                RetrievedScheme.model_validate(
                    {
                        "scheme_id": "scheme-1",
                        "name": "Scheme 1",
                        "url": "https://example.com/scheme-1",
                        "level": "state",
                        "provider": "Maharashtra",
                        "provider_type": "state",
                        "state": "Maharashtra",
                        "ministry": None,
                        "tags": ["Student"],
                        "topics": ["Education"],
                        "application_modes": {"online": False, "offline": False},
                        "selected_fields": {},
                        "mongo_ref": {
                            "database": "jurisai",
                            "collection": "schemes",
                            "document_id": str(document_id),
                        },
                        "match_profile": "embedding_a",
                        "match_score": 0.81,
                        "matched_profiles": ["embedding_a"],
                        "profile_scores": {"embedding_a": 0.81},
                        "match_reasons": ["Strong match."],
                    }
                ).model_dump()
            ]
        )

        self.assertEqual(len(hydrated), 1)
        self.assertEqual(hydrated[0].name, "Hydrated Scheme")
        self.assertEqual(
            enriched_collection.queries,
            [{"_id": {"$in": [document_id]}}],
        )
        self.assertFalse(fake_client.closed)
        await workflow.aclose()
        self.assertFalse(fake_client.closed)


if __name__ == "__main__":
    unittest.main()
