from __future__ import annotations

from src.config.settings import settings
from src.llm.local_openai_client import LocalOpenAICompatibleClient


class OpenRouterClient(LocalOpenAICompatibleClient):
    """OpenRouter client using its OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        app_name: str | None = None,
        http_referer: str | None = None,
        enable_thinking: bool | None = None,
    ) -> None:
        config = settings.openrouter
        resolved_api_key = api_key or config.api_key
        if not resolved_api_key:
            raise ValueError(
                "Missing OpenRouter API key. Set OPENROUTER_API_KEY in the environment or .env."
            )

        extra_headers: dict[str, str] = {}
        resolved_referer = http_referer or config.http_referer
        resolved_app_name = app_name or config.app_name
        if resolved_referer:
            extra_headers["HTTP-Referer"] = resolved_referer
        if resolved_app_name:
            extra_headers["X-OpenRouter-Title"] = resolved_app_name

        super().__init__(
            base_url=base_url or config.base_url,
            api_key=resolved_api_key,
            model=model or config.model,
            timeout_seconds=timeout_seconds or config.timeout_seconds,
            enable_thinking=(
                config.enable_thinking if enable_thinking is None else enable_thinking
            ),
            extra_headers=extra_headers,
            disable_thinking_via_extra_body=False,
        )
