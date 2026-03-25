from __future__ import annotations

from src.config.settings import settings
from src.llm import TextGenerationClient, build_generation_client
from src.agentic.models import SessionSnapshot, UserIntentClassification

INTENT_CLASSIFIER_SYSTEM_PROMPT = """
You classify user turns for a public-benefits and government-schemes assistant.

Return a structured decision for routing.
Be conservative and cheap:
- prefer scheme_discovery when the user is asking about benefits, subsidies, scholarships, aid, welfare, or eligibility
- prefer follow_up when the user is continuing a prior scheme conversation
- prefer profile_update when the main purpose is sharing or correcting profile details
- prefer general_question only for broad product/help questions
- prefer out_of_scope when the request is unrelated to the assistant's domain

Set needs_clarification=true only when routing would be materially better with one more question.
If scheme retrieval would be useful, fill retrieval_query and retrieval_filters using only facts present in the user message or session snapshot.
Keep reasoning short.
""".strip()


class UserIntentClassifier:
    def __init__(
        self,
        llm: TextGenerationClient | None = None,
        *,
        model: str | None = None,
    ) -> None:
        self._llm = llm or build_generation_client(
            provider=settings.workflow.intent_provider,
            model=model or settings.workflow.intent_model,
        )
        self._model = model or settings.workflow.intent_model

    def classify(
        self,
        *,
        user_message: str,
        session_snapshot: SessionSnapshot | None = None,
    ) -> UserIntentClassification:
        snapshot = session_snapshot or SessionSnapshot()
        prompt = f"""
User message:
{user_message}

Session snapshot:
{snapshot.model_dump_json(indent=2)}
""".strip()

        return self._llm.generate_structured(
            prompt,
            UserIntentClassification,
            model=self._model,
            system_instruction=INTENT_CLASSIFIER_SYSTEM_PROMPT,
            temperature=0,
        )
