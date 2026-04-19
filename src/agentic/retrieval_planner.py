from __future__ import annotations

import json
from typing import Any

from src.agentic.models import (
    RetrievalPlan,
    SessionMemory,
    SessionSnapshot,
    UserIntentClassification,
)
from src.config.settings import settings
from src.llm import TextGenerationClient, build_generation_client

RETRIEVAL_TOOL_PLANNER_SYSTEM_PROMPT = """
You plan retrieval tool calls for JurisAI.

Available retrieval tools:
- semantic_search: broad semantic retrieval when no strong structured narrowing is needed.
- state_scoped_search: retrieval where state is an important constraint.
- topic_scoped_search: retrieval where a controlled topic focus is important.

Rules:
- Choose 1 to 3 tool calls in execution order.
- Only use `state` and `topics` as structured tool inputs.
- Do not use level, provider, provider_type, ministry, application_mode, tags, or beneficiary filters as structured inputs.
- Preserve any other important user constraints only inside the query text.
- Prefer short, grounded query text.
- If both state and topic matter, you may either compose multiple tool calls or include both on a single tool call when that is clearly useful.
- Do not invent topics or states that are not supported by the user message, classifier output, or session context.
- Return valid JSON only.
""".strip()


def _render_mapping(value: dict[str, Any]) -> str:
    if not value:
        return "none"
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _render_recent_scheme_refs(session_memory: SessionMemory) -> str:
    if not session_memory.recent_scheme_refs:
        return "none"
    labels: list[str] = []
    for scheme_ref in session_memory.recent_scheme_refs[:5]:
        parts = [scheme_ref.name or scheme_ref.scheme_id]
        qualifiers = [
            item for item in (scheme_ref.state, scheme_ref.level, scheme_ref.provider) if item
        ]
        if qualifiers:
            parts.append(f"({', '.join(qualifiers)})")
        labels.append(" ".join(parts))
    return "; ".join(labels)


def _build_planner_prompt(
    *,
    user_message: str,
    classification: UserIntentClassification,
    session_memory: SessionMemory,
) -> str:
    lines = [
        "User message:",
        user_message,
        "",
        "Compact classifier output:",
        f"- primary_intent: {classification.primary_intent}",
        f"- confidence: {classification.confidence:.2f}",
        f"- user_goal: {classification.user_goal}",
        f"- needs_clarification: {classification.needs_clarification}",
        f"- clarification_question: {classification.clarification_question or 'none'}",
        f"- is_followup: {classification.is_followup}",
        f"- retrieval_query: {classification.retrieval_query or 'none'}",
        (
            "- retrieval_filters: "
            f"{json.dumps([fact.model_dump(mode='json') for fact in classification.retrieval_filters], ensure_ascii=True)}"
        ),
        (
            "- extracted_profile_updates: "
            f"{json.dumps([fact.model_dump(mode='json') for fact in classification.extracted_profile_updates], ensure_ascii=True)}"
        ),
        f"- reasoning: {classification.reasoning}",
        "",
        "Minimal session facts:",
        f"- chat_session_id: {session_memory.chat_session_id}",
        f"- user_profile: {_render_mapping(session_memory.user_profile)}",
        f"- preferences: {_render_mapping(session_memory.preferences)}",
        f"- conversation_summary: {session_memory.conversation_summary or 'none'}",
        f"- last_user_goal: {session_memory.last_user_goal or 'none'}",
        f"- last_action: {session_memory.last_action or 'none'}",
        f"- active_constraints: {_render_mapping(session_memory.active_constraints)}",
        f"- recent_scheme_refs: {_render_recent_scheme_refs(session_memory)}",
        (
            "- selected_scheme_ref: "
            f"{session_memory.selected_scheme_ref.model_dump_json() if session_memory.selected_scheme_ref else 'none'}"
        ),
    ]
    return "\n".join(lines).strip()


class RetrievalToolPlanner:
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

    def plan(
        self,
        *,
        user_message: str,
        classification: UserIntentClassification,
        session_snapshot: SessionSnapshot,
    ) -> RetrievalPlan:
        session_memory = session_snapshot.to_session_memory()
        prompt = _build_planner_prompt(
            user_message=user_message,
            classification=classification,
            session_memory=session_memory,
        )

        return self._llm.generate_structured(
            prompt,
            RetrievalPlan,
            model=self._model,
            system_instruction=RETRIEVAL_TOOL_PLANNER_SYSTEM_PROMPT,
            temperature=0,
        )
