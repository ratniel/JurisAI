from __future__ import annotations

import json
from typing import Any

from src.config.settings import settings
from src.llm import TextGenerationClient, build_generation_client
from src.llm.providers import GenerationProviderName
from src.agentic.models import SessionMemory, SessionSnapshot, UserIntentClassification

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
If scheme retrieval would be useful, fill discovery_query, fit_query, and retrieval_filters using only facts present in the user message or session snapshot.
Prefer canonical retrieval filter keys when possible: `state`, `level`, `provider`, `provider_type`, `ministry`, `application_mode`, `tags`, `topics`.
For discovery_query, write a short grounded query that best matches scheme name and details text.
For fit_query, write a compact query that best matches eligibility and benefits text, using at most:
- one `eligibility:` line
- one `benefits:` line
Do not repeat the same key multiple times inside fit_query.
Preserve important user constraints such as geography, beneficiary type, student status, and channel in the query text even if you are not sure they belong in a structured filter.
Keep reasoning short.
""".strip()


def _render_mapping(value: dict[str, Any]) -> str:
    if not value:
        return "none"
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _render_recent_scheme_refs(session_memory: SessionMemory) -> str:
    if not session_memory.recent_scheme_refs:
        return "none"

    items: list[str] = []
    for scheme_ref in session_memory.recent_scheme_refs[:5]:
        parts = [scheme_ref.name or scheme_ref.scheme_id]
        qualifiers = [
            item for item in (scheme_ref.state, scheme_ref.level, scheme_ref.provider) if item
        ]
        if qualifiers:
            parts.append(f"({', '.join(qualifiers)})")
        items.append(" ".join(parts))
    return "; ".join(items)


def _render_selected_scheme(session_memory: SessionMemory) -> str:
    selected = session_memory.selected_scheme_ref
    if selected is None:
        return "none"

    parts = [selected.name or selected.scheme_id]
    qualifiers = [item for item in (selected.state, selected.level, selected.provider) if item]
    if qualifiers:
        parts.append(f"({', '.join(qualifiers)})")
    return " ".join(parts)


def _build_classifier_prompt(
    *,
    user_message: str,
    session_memory: SessionMemory,
) -> str:
    lines = [
        "User message:",
        user_message,
        "",
        "Compact session memory:",
        f"- chat_session_id: {session_memory.chat_session_id}",
        f"- user_profile: {_render_mapping(session_memory.user_profile)}",
        f"- preferences: {_render_mapping(session_memory.preferences)}",
        f"- conversation_summary: {session_memory.conversation_summary or 'none'}",
        f"- last_user_goal: {session_memory.last_user_goal or 'none'}",
        f"- last_action: {session_memory.last_action or 'none'}",
        f"- active_constraints: {_render_mapping(session_memory.active_constraints)}",
        f"- recent_scheme_refs: {_render_recent_scheme_refs(session_memory)}",
        f"- selected_scheme_ref: {_render_selected_scheme(session_memory)}",
    ]
    return "\n".join(lines).strip()


class UserIntentClassifier:
    def __init__(
        self,
        llm: TextGenerationClient | None = None,
        *,
        provider: GenerationProviderName | None = None,
        model: str | None = None,
    ) -> None:
        self._llm = llm or build_generation_client(
            provider=provider or settings.workflow.intent_provider,
            model=model or settings.workflow.intent_model,
        )
        self._model = model or settings.workflow.intent_model

    def classify(
        self,
        *,
        user_message: str,
        session_snapshot: SessionSnapshot | None = None,
        session_memory: SessionMemory | None = None,
    ) -> UserIntentClassification:
        snapshot = session_snapshot or SessionSnapshot()
        memory = session_memory or snapshot.to_session_memory()
        prompt = _build_classifier_prompt(
            user_message=user_message,
            session_memory=memory,
        )

        return self._llm.generate_structured(
            prompt,
            UserIntentClassification,
            model=self._model,
            system_instruction=INTENT_CLASSIFIER_SYSTEM_PROMPT,
            temperature=0,
        )
