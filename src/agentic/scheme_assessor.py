from __future__ import annotations

import json
from typing import Any

from src.agentic.models import RelevantScheme, SchemeAssessmentBatch, SessionMemory
from src.config.settings import settings
from src.llm import TextGenerationClient, build_generation_client

SCHEME_ASSESSOR_SYSTEM_PROMPT = """
You assess government-scheme candidates against facts the user has actually supplied.

Retrieval score means only "worth inspecting". It never proves eligibility or fit.
For every candidate, return exactly one assessment:
- matches_known_facts: relevant and no stated condition conflicts with known facts
- potential_option: relevant, but at least one material user fact is unknown
- conflicts_with_known_facts: a stated condition conflicts with a known fact

Rules:
- Use the complete scheme evidence supplied in the prompt.
- Never infer a missing user fact. Missing information remains unknown.
- "Engineering student" does not establish undergraduate or postgraduate study.
- Name each conflict and cite the scheme condition that causes it.
- clarification_needs must contain every material missing user fact, ordered by impact.
- Use stable snake_case fact keys and one focused, non-sensitive question per fact.
- Do not ask for facts already present in the user profile.
- Choose targeted_search only when the candidate evidence/search is inadequate, not when a
  user fact is missing. Otherwise choose ask_question when a useful option needs one material
  fact, or respond.
- Return valid structured output only.
""".strip()


def _assessment_prompt(
    *,
    user_message: str,
    session_memory: SessionMemory,
    schemes: list[RelevantScheme],
) -> str:
    scheme_payloads: list[dict[str, Any]] = [
        scheme.model_dump(mode="json", exclude_none=True) for scheme in schemes
    ]
    return "\n".join(
        [
            "Current user message:",
            user_message,
            "",
            "Goal being continued:",
            session_memory.last_user_goal or user_message,
            "",
            "Known user facts:",
            json.dumps(session_memory.user_profile, ensure_ascii=True, sort_keys=True),
            "",
            "Active constraints:",
            json.dumps(
                session_memory.active_constraints, ensure_ascii=True, sort_keys=True
            ),
            "",
            "Previously asked fact keys:",
            json.dumps(
                [
                    key
                    for key, item in session_memory.pending_clarifications.items()
                    if item.asked
                ],
                ensure_ascii=True,
            ),
            "",
            "Complete hydrated candidate schemes:",
            json.dumps(scheme_payloads, ensure_ascii=True),
        ]
    ).strip()


class SchemeFitAssessor:
    def __init__(
        self,
        llm: TextGenerationClient | None = None,
        *,
        model: str | None = None,
    ) -> None:
        self._llm = llm or build_generation_client(
            provider=settings.workflow.generation_provider,
            model=model or settings.workflow.generation_model,
        )
        self._model = model or settings.workflow.generation_model

    def assess(
        self,
        *,
        user_message: str,
        session_memory: SessionMemory,
        schemes: list[RelevantScheme],
    ) -> SchemeAssessmentBatch:
        return self._llm.generate_structured(
            _assessment_prompt(
                user_message=user_message,
                session_memory=session_memory,
                schemes=schemes,
            ),
            SchemeAssessmentBatch,
            model=self._model,
            system_instruction=SCHEME_ASSESSOR_SYSTEM_PROMPT,
            temperature=0,
        )
