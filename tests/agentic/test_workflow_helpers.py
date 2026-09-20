from __future__ import annotations

import unittest
from unittest.mock import Mock

from bson import ObjectId

from src.agentic.fact_utils import aggregate_intent_facts
from src.agentic.models import (
    AgenticTurnResult,
    GroundingPack,
    IntentFact,
    MongoReference,
    NextAction,
    OrchestratorDecision,
    PrimaryIntent,
    RelevantScheme,
    RetrievalToolCall,
    RetrievalToolName,
    RetrievedScheme,
    SchemeRef,
    SessionSnapshot,
    UserIntentClassification,
)
from src.agentic.workflow import (
    _build_reply_prompt,
    build_grounding_pack,
    build_relevant_scheme_from_lookup_document,
    build_session_memory,
    build_top_schemes_artifact,
    fallback_retrieval_plan,
    merge_retrieved_scheme_results,
    BasicAgenticWorkflow,
    preferred_hydration_collections,
)
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
        self.assertIn("education", relevant.topics)

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
                "discovery_query": "farmer support scheme",
                "fit_query": "eligibility: farmer in maharashtra benefits: support or subsidy",
                "retrieval_filters": [
                    {"key": "state", "value": "Maharashtra"},
                    {"key": "topics", "value": "agriculture"},
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
        self.assertEqual(
            plan.tool_calls[0].fit_query,
            "eligibility: farmer in maharashtra benefits: support or subsidy",
        )

    def test_fallback_retrieval_plan_uses_clarification_profile_update(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.PROFILE_UPDATE,
            confidence=0.95,
            user_goal="Share state",
            extracted_profile_updates=[
                IntentFact(key="state", value="Maharashtra")
            ],
            discovery_query="engineering scholarships",
            reasoning="User answered the state clarification.",
        )

        plan = fallback_retrieval_plan(
            user_message="Maharashtra",
            classification=classification,
            session_snapshot=SessionSnapshot(),
        )

        self.assertEqual(plan.tool_calls[0].tool_name, RetrievalToolName.STATE_SCOPED_SEARCH)
        self.assertEqual(plan.tool_calls[0].state, "Maharashtra")

    def test_decision_preserves_exact_clarification_question(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.SCHEME_DISCOVERY,
            confidence=0.9,
            user_goal="Find student scholarships",
            needs_clarification=True,
            clarification_question="Which state or Union Territory do you live in?",
            reasoning="State has the highest impact on the search.",
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            SessionSnapshot(),
        )

        self.assertEqual(decision.next_action, NextAction.ASK_CLARIFYING_QUESTION)
        self.assertEqual(
            decision.tool_payload["question"],
            "Which state or Union Territory do you live in?",
        )

    def test_blank_clarification_question_falls_through_to_retrieval(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.SCHEME_DISCOVERY,
            confidence=0.9,
            user_goal="Find student scholarships",
            needs_clarification=True,
            reasoning="Classifier did not supply a usable question.",
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            SessionSnapshot(),
        )

        self.assertEqual(decision.next_action, NextAction.CALL_SCHEME_RETRIEVAL)

    def test_clarification_answer_resumes_prior_goal_with_profile_fact(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.PROFILE_UPDATE,
            confidence=0.96,
            user_goal="Share state",
            extracted_profile_updates=[
                IntentFact(key="state", value="Maharashtra")
            ],
            reasoning="User answered the pending clarification.",
        )
        snapshot = SessionSnapshot(
            last_user_goal="Find engineering scholarships",
            last_action=NextAction.ASK_CLARIFYING_QUESTION.value,
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            snapshot,
        )

        self.assertEqual(decision.next_action, NextAction.CALL_SCHEME_RETRIEVAL)
        self.assertEqual(decision.tool_payload["query"], "Find engineering scholarships")
        self.assertEqual(decision.tool_payload["filters"]["state"], "Maharashtra")
        self.assertIn("state: Maharashtra", decision.tool_payload["fit_query"])

        memory = build_session_memory(
            user_message="Maharashtra",
            session_snapshot=snapshot,
            classification=classification,
            decision=decision,
            relevant_schemes=[],
            last_action="retrieval_completed",
        )
        self.assertEqual(memory.last_user_goal, "Find engineering scholarships")

    def test_followup_reuses_grounding_when_no_new_search_is_requested(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.FOLLOW_UP,
            confidence=0.93,
            user_goal="Explain the benefits of the first result",
            reasoning="Existing grounded results can answer the question.",
        )
        snapshot = SessionSnapshot(
            latest_grounding_pack=GroundingPack(
                chat_session_id="chat-123",
                turn_id="turn-123",
                user_message="Find scholarships in Maharashtra",
            )
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            snapshot,
        )

        self.assertEqual(decision.next_action, NextAction.RESPOND_DIRECTLY)

    def test_followup_retrieves_when_classifier_requests_revised_search(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.FOLLOW_UP,
            confidence=0.93,
            user_goal="Find alternatives for diploma students",
            discovery_query="diploma student scholarships Maharashtra",
            reasoning="The user requested a materially revised search.",
        )
        snapshot = SessionSnapshot(
            latest_grounding_pack=GroundingPack(
                chat_session_id="chat-123",
                turn_id="turn-123",
                user_message="Find engineering scholarships in Maharashtra",
            )
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            snapshot,
        )

        self.assertEqual(decision.next_action, NextAction.CALL_SCHEME_RETRIEVAL)
        self.assertEqual(
            decision.tool_payload["query"],
            "diploma student scholarships Maharashtra",
        )

    def test_followup_retrieves_when_no_prior_grounding_is_available(self) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.FOLLOW_UP,
            confidence=0.9,
            user_goal="Explain the scheme benefits",
            reasoning="Follow-up has no reusable grounding.",
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            SessionSnapshot(),
        )

        self.assertEqual(decision.next_action, NextAction.CALL_SCHEME_RETRIEVAL)
        self.assertEqual(decision.tool_payload["query"], "Explain the scheme benefits")

    def test_retrieval_tool_call_backfills_fit_query_from_discovery_query(self) -> None:
        tool_call = RetrievalToolCall.model_validate(
            {
                "tool_name": "semantic_search",
                "query": "student scholarship tamil nadu",
            }
        )

        self.assertEqual(tool_call.fit_query, "student scholarship tamil nadu")

    def test_execute_retrieval_tool_call_can_disable_hard_filters(self) -> None:
        retriever = Mock()
        retriever.search.return_value = {
            "results": [],
            "retrieval_filters_enabled": False,
            "retrieval_filter_mode": "none",
            "candidate_filters": {"state": "Maharashtra", "topics": ["agriculture"]},
            "applied_filters": {},
            "ignored_filters": {},
            "raw_hit_count": 0,
        }
        workflow = BasicAgenticWorkflow(
            classifier=Mock(),
            llm=Mock(),
            retriever=retriever,
            mongo_client=Mock(),
            retrieval_filters_enabled=False,
        )

        result = workflow._execute_retrieval_tool_call(
            user_message="Need crop insurance in Maharashtra.",
            tool_call=RetrievalToolCall(
                tool_name=RetrievalToolName.STATE_SCOPED_SEARCH,
                query="crop insurance for farmers",
                fit_query="eligibility: farmer benefits: crop insurance",
                state="Maharashtra",
                topics=["agriculture"],
            ),
        )

        retriever.search.assert_called_once()
        self.assertFalse(retriever.search.call_args.kwargs["enable_filters"])
        self.assertFalse(result["output_payload"]["retrieval_filters_enabled"])
        self.assertEqual(
            result["output_payload"]["candidate_filters"],
            {"state": "Maharashtra", "topics": ["agriculture"]},
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
                                "topics": ["agriculture"],
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
                                "topics": ["agriculture"],
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

    def test_grounding_pack_does_not_endorse_first_hit_or_truncate_conditions(self) -> None:
        long_condition = "Existing businesses are not eligible. " + ("Required condition. " * 20)
        scheme = RelevantScheme.from_retrieved_scheme(
            self._make_retrieved_scheme(
                selected_fields={
                    "details": "A one-time marriage gift, not a recurring pension.",
                    "benefits": long_condition,
                    "eligibility": long_condition,
                }
            )
        )

        grounding_pack = build_grounding_pack(
            chat_session_id="chat-123",
            turn_id="turn-123",
            user_message="Need a widow pension.",
            retrieval_query="widow pension",
            relevant_schemes=[scheme],
            applied_filters={},
            ignored_filters={},
            important_ignored_filters={},
            selected_scheme_ref=None,
        )

        card = grounding_pack.top_scheme_cards[0]
        self.assertIsNone(grounding_pack.selection_hint)
        self.assertEqual(card.benefits_summary, long_condition.strip())
        self.assertEqual(card.eligibility_summary, long_condition.strip())
        self.assertEqual(
            card.evidence_snippets,
            ["A one-time marriage gift, not a recurring pension."],
        )

    def test_session_memory_and_reply_prompt_keep_original_request_authoritative(
        self,
    ) -> None:
        classification = UserIntentClassification.model_validate(
            {
                "primary_intent": "scheme_discovery",
                "confidence": 0.9,
                "user_goal": "Find information about an exact named scheme",
                "reasoning": "Benefits lookup.",
            }
        )
        decision = OrchestratorDecision(
            next_action=NextAction.CALL_SCHEME_RETRIEVAL,
            selected_agent="retrieval_planner",
        )
        user_message = "meghalaya st micro business loan subsidy artisan scheme"

        memory = build_session_memory(
            user_message=user_message,
            session_snapshot=SessionSnapshot(chat_session_id="chat-123"),
            classification=classification,
            decision=decision,
            relevant_schemes=[],
            last_action="retrieval_completed",
        )
        prompt = _build_reply_prompt(
            user_message=user_message,
            session_memory=memory,
            grounding_pack=None,
        )

        self.assertEqual(memory.last_user_goal, user_message)
        self.assertIn(
            f"Current request: {user_message}",
            memory.conversation_summary or "",
        )
        self.assertTrue(prompt.startswith("Original user message (authoritative):"))

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
    async def test_clarification_reply_uses_routed_question_without_generation_call(
        self,
    ) -> None:
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.SCHEME_DISCOVERY,
            confidence=0.9,
            user_goal="Find scholarships",
            needs_clarification=True,
            clarification_question="Which state or Union Territory do you live in?",
            reasoning="State has the highest impact on retrieval.",
        )
        classifier = Mock()
        classifier.classify.return_value = classification
        llm = Mock()
        workflow = BasicAgenticWorkflow(
            llm=llm,
            classifier=classifier,
            retriever=Mock(),
            mongo_client=Mock(),
        )

        result = AgenticTurnResult.model_validate(
            await workflow.run(
                user_message="Can you find scholarships for me?",
                session_snapshot={},
            )
        )

        self.assertEqual(
            result.decision.response,
            "Which state or Union Territory do you live in?",
        )
        self.assertEqual(
            result.session_memory.last_action,
            NextAction.ASK_CLARIFYING_QUESTION.value,
        )
        llm.generate_text.assert_not_called()

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
