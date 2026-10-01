from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from opentelemetry import trace
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from phoenix.otel import register

from src.config.settings import settings

_TRACING_CONFIGURED = False


@dataclass(frozen=True)
class PhoenixTracingStatus:
    enabled: bool
    detail: str


def _normalize_collector_endpoint(endpoint: str | None) -> str | None:
    if not endpoint or "://" not in endpoint:
        return endpoint

    parsed = urlparse(endpoint)
    if parsed.hostname != "app.phoenix.arize.com":
        return endpoint

    if parsed.path.endswith("/v1/traces"):
        return endpoint

    match = re.match(r"^/s/([a-zA-Z0-9_-]+)", parsed.path)
    if match:
        space_id = match.group(1)
        return parsed._replace(path=f"/s/{space_id}/v1/traces").geturl()

    return parsed._replace(path="/v1/traces").geturl()


def _infer_protocol(endpoint: str | None) -> str | None:
    if not endpoint or "://" not in endpoint:
        return None

    parsed = urlparse(endpoint)
    if parsed.scheme in {"http", "https"} and parsed.path.endswith("/v1/traces"):
        return "http/protobuf"
    return None


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
    normalized_endpoint = _normalize_collector_endpoint(collector_endpoint)
    protocol = _infer_protocol(normalized_endpoint)

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
        endpoint=normalized_endpoint,
        project_name=resolved_project_name,
        batch=True,
        auto_instrument=False,
        api_key=api_key,
        protocol=protocol,
        verbose=False,
    )
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
    GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    _TRACING_CONFIGURED = True
    endpoint_detail = normalized_endpoint or collector_endpoint
    if normalized_endpoint and normalized_endpoint != collector_endpoint:
        endpoint_detail = f"{normalized_endpoint!r} (normalized from {collector_endpoint!r})"
    return PhoenixTracingStatus(
        enabled=True,
        detail=(
            f"Phoenix tracing enabled for project={resolved_project_name!r} "
            f"endpoint={endpoint_detail}."
        ),
    )


def flush_phoenix_tracing() -> None:
    """Best-effort flush for long-running processes before shutdown."""

    tracer_provider = trace.get_tracer_provider()
    for method_name in ("force_flush", "shutdown"):
        method = getattr(tracer_provider, method_name, None)
        if callable(method):
            method()
            break
