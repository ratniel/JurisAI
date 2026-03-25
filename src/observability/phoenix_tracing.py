from __future__ import annotations

import os
from dataclasses import dataclass

from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

from src.config.settings import settings

_TRACING_CONFIGURED = False


@dataclass(frozen=True)
class PhoenixTracingStatus:
    enabled: bool
    detail: str


def configure_phoenix_tracing(
    *,
    project_name: str | None = None,
    endpoint: str | None = None,
) -> PhoenixTracingStatus:
    global _TRACING_CONFIGURED

    if _TRACING_CONFIGURED:
        return PhoenixTracingStatus(
            enabled=True,
            detail="Phoenix tracing already configured for this process.",
        )

    api_key = settings.phoenix.api_key or os.getenv("PHOENIX_API_KEY")
    collector_endpoint = (
        endpoint
        or settings.phoenix.collector_endpoint
        or os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    )
    resolved_project_name = project_name or settings.phoenix.project_name

    if not api_key and not collector_endpoint:
        return PhoenixTracingStatus(
            enabled=False,
            detail=(
                "Phoenix tracing is disabled. Set PHOENIX_COLLECTOR_ENDPOINT for a local "
                "or remote collector, or set PHOENIX_API_KEY plus PHOENIX_COLLECTOR_ENDPOINT "
                "for Phoenix cloud."
            ),
        )

    if api_key and not collector_endpoint:
        return PhoenixTracingStatus(
            enabled=False,
            detail=(
                "PHOENIX_API_KEY is set but PHOENIX_COLLECTOR_ENDPOINT is missing. "
                "Skipping tracing so spans are not accidentally sent to a local default collector."
            ),
        )

    tracer_provider = register(
        endpoint=collector_endpoint,
        project_name=resolved_project_name,
        batch=True,
        auto_instrument=False,
        api_key=api_key,
        verbose=False,
    )
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
    GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    _TRACING_CONFIGURED = True
    return PhoenixTracingStatus(
        enabled=True,
        detail=(
            f"Phoenix tracing enabled for project={resolved_project_name!r} "
            f"endpoint={collector_endpoint!r}."
        ),
    )
