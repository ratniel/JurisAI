from __future__ import annotations

import unittest

from src.agentic.models import (
    ClarificationNeed,
    IntentFact,
    NextAction,
    PendingClarification,
    PrimaryIntent,
    RelevantScheme,
    SchemeAssessmentBatch,
    SchemeFitAssessment,
    SchemeFitStatus,
    SessionMemory,
    SessionSnapshot,
    UserIntentClassification,
)
from src.agentic.scheme_assessor import SchemeFitAssessor
from src.agentic.workflow import (
    BasicAgenticWorkflow,
    build_session_memory,
    merge_pending_clarifications,
)


def _scheme(*, eligibility: str) -> RelevantScheme:
    return RelevantScheme(
        scheme_id="tn-engineering",
        name="Tamil Nadu Engineering Scholarship",
        state="Tamil Nadu",
        level="state",
        details="Fee support for professional courses.",
        benefits="Tuition and compulsory fee support.",
        eligibility=eligibility,
        documents_required="Community and income certificates.",
        match_profile="embedding_b",
        match_score=0.91,
    )


class _AssessmentLLM:
    default_model = "test"

    def __init__(self, result: SchemeAssessmentBatch) -> None:
        self.result = result
        self.prompt = ""

    def generate_structured(self, prompt, response_model, **kwargs):
        self.prompt = prompt
        return self.result

    def generate_text(self, prompt, **kwargs):
        return ""


class SchemeAssessmentTests(unittest.TestCase):
    def test_assessor_receives_complete_untruncated_scheme(self) -> None:
        eligibility = "Undergraduate professional-course admission required. " * 20
        result = SchemeAssessmentBatch(
            assessments=[
                SchemeFitAssessment(
                    scheme_id="tn-engineering",
                    status=SchemeFitStatus.POTENTIAL_OPTION,
                    summary="Course level is not known.",
                    unknown_conditions=["Undergraduate study"],
                    evidence=[eligibility],
                )
            ]
        )
        llm = _AssessmentLLM(result)

        actual = SchemeFitAssessor(llm=llm).assess(
            user_message="I am an SC engineering student in Tamil Nadu.",
            session_memory=SessionMemory(
                user_profile={
                    "state": "Tamil Nadu",
                    "social_category": "SC",
                    "student_status": "engineering student",
                }
            ),
            schemes=[_scheme(eligibility=eligibility)],
        )

        self.assertEqual(actual, result)
        self.assertIn(eligibility.strip(), llm.prompt)
        self.assertIn("Community and income certificates", llm.prompt)

    def test_pending_clarifications_merge_by_key_and_resolve_only_answered_fact(
        self,
    ) -> None:
        existing = {
            "course_level": PendingClarification(
                fact_key="course_level",
                question="Are you studying at undergraduate or postgraduate level?",
                reason="The scheme is undergraduate-only.",
                scheme_ids=["tn-engineering"],
                goal="Find Tamil Nadu scholarships",
            ),
            "household_income_range": PendingClarification(
                fact_key="household_income_range",
                question="Which income range applies to your household?",
                reason="The scheme has an income ceiling.",
                scheme_ids=["tn-engineering"],
                goal="Find Tamil Nadu scholarships",
                asked=True,
            ),
        }

        pending = merge_pending_clarifications(
            existing=existing,
            proposed=[
                ClarificationNeed(
                    fact_key="institution_type",
                    question="What type of institution admitted you?",
                    reason="Institution type is material.",
                    scheme_ids=["tn-engineering"],
                )
            ],
            user_profile={"course_level": "undergraduate"},
            goal="Find Tamil Nadu scholarships",
            active_scheme_ids={"tn-engineering"},
        )

        self.assertNotIn("course_level", pending)
        self.assertIn("household_income_range", pending)
        self.assertIn("institution_type", pending)
        self.assertEqual(
            pending["household_income_range"].question,
            existing["household_income_range"].question,
        )
        self.assertTrue(pending["household_income_range"].asked)

        still_pending = merge_pending_clarifications(
            existing=existing,
            proposed=[],
            user_profile={"course_level": ""},
            goal="Find Tamil Nadu scholarships",
        )
        self.assertIn("course_level", still_pending)

    def test_answered_pending_fact_reassesses_stored_schemes_without_retrieval(
        self,
    ) -> None:
        scheme = _scheme(eligibility="Undergraduate engineering students are eligible.")
        snapshot = SessionSnapshot(
            last_user_goal="Find Tamil Nadu scholarships",
            last_action=NextAction.ASK_CLARIFYING_QUESTION.value,
            pending_clarifications={
                "course_level": PendingClarification(
                    fact_key="course_level",
                    question="Are you an undergraduate or postgraduate student?",
                    reason="Course level changes fit.",
                    scheme_ids=[scheme.scheme_id],
                    goal="Find Tamil Nadu scholarships",
                )
            },
            relevant_schemes=[scheme],
        )
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.PROFILE_UPDATE,
            confidence=0.98,
            user_goal="Answer course level",
            extracted_profile_updates=[
                IntentFact(key="course_level", value="undergraduate")
            ],
            reasoning="User answered the pending clarification.",
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            snapshot,
        )
        memory = build_session_memory(
            user_message="Undergraduate",
            session_snapshot=snapshot,
            classification=classification,
            decision=decision,
            relevant_schemes=[scheme],
            last_action="schemes_assessed",
        )

        self.assertEqual(decision.next_action, NextAction.ASSESS_SCHEMES)
        self.assertEqual(memory.user_profile["course_level"], "undergraduate")
        self.assertNotIn("course_level", memory.pending_clarifications)

    def test_already_asked_clarification_is_not_repeated(self) -> None:
        scheme = _scheme(eligibility="Undergraduate engineering students are eligible.")
        snapshot = SessionSnapshot(
            last_user_goal="Find Tamil Nadu scholarships",
            last_action=NextAction.ASK_CLARIFYING_QUESTION.value,
            pending_clarifications={
                "course_level": PendingClarification(
                    fact_key="course_level",
                    question="Are you an undergraduate or postgraduate student?",
                    reason="Course level changes fit.",
                    scheme_ids=[scheme.scheme_id],
                    goal="Find Tamil Nadu scholarships",
                    asked=True,
                )
            },
            relevant_schemes=[scheme],
        )
        classification = UserIntentClassification(
            primary_intent=PrimaryIntent.PROFILE_UPDATE,
            confidence=0.8,
            user_goal="Continue the scholarship search",
            needs_clarification=True,
            clarification_question="Are you an undergraduate or postgraduate student?",
            clarification_fact_key="course_level",
            reasoning="The user did not supply the requested fact.",
        )

        decision = BasicAgenticWorkflow._decide_next_action(
            classification,
            snapshot,
        )

        self.assertEqual(decision.next_action, NextAction.ASSESS_SCHEMES)
        self.assertEqual(
            decision.tool_payload["avoid_repeating_clarification"],
            "course_level",
        )


if __name__ == "__main__":
    unittest.main()
