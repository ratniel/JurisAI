from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Literal
from urllib.parse import urlparse

from opentelemetry import context, trace
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    is_instrumentation_enabled,
)
from openinference.instrumentation import suppress_tracing
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor, get_current_span
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from phoenix.otel import register
from wrapt import wrap_function_wrapper

from src.config.settings import settings

_TRACING_CONFIGURED = False
_GOOGLE_SDK_ONLY: ContextVar[bool] = ContextVar("jurisai.google_sdk_only", default=False)
_LLM_PROVIDER: ContextVar[str | None] = ContextVar("jurisai.llm_provider", default=None)


@contextmanager
def using_llm_provider(provider: str):
    """Distinguish our serving provider from LiteLLM's OpenAI wire protocol."""
    token = _LLM_PROVIDER.set(provider)
    try:
        yield
    finally:
        _LLM_PROVIDER.reset(token)


@contextmanager
def google_sdk_tracing():
    """Let the Google SDK own LLM spans, not duplicate LlamaIndex wrappers."""
    if not is_instrumentation_enabled():
        yield
        return
    token = _GOOGLE_SDK_ONLY.set(True)
    try:
        with suppress_tracing():
            yield
    finally:
        _GOOGLE_SDK_ONLY.reset(token)


def _restore_google_sdk_tracing(wrapped, instance, args, kwargs):
    if not _GOOGLE_SDK_ONLY.get():
        return wrapped(*args, **kwargs)
    # Use the same OTel suppression key as both official instrumentors.
    token = context.attach(context.set_value(_SUPPRESS_INSTRUMENTATION_KEY, False))
    try:
        return wrapped(*args, **kwargs)
    finally:
        context.detach(token)


def trace_workflow_step(fn):
    """Expose LlamaIndex's active step span to SDK and manual OTel spans."""
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        span = get_current_span() or trace.get_current_span()
        with trace.use_span(span, end_on_exit=False):
            return await fn(*args, **kwargs)

    return wrapped


def _set_llm_request_attributes(model: str | None, provider: str | None):
    span = trace.get_current_span()
    # Do not label a workflow or caller span when SDK tracing is suppressed.
    if not is_instrumentation_enabled() or not span.is_recording():
        return None
    if provider:
        span.set_attribute("llm.provider", provider)
    if model:
        span.set_attribute("llm.request.model_name", model)
        span.set_attribute("llm.model_name", model)
    return span


def _set_llm_response_attributes(span, model: str | None) -> None:
    if span is not None and model:
        span.set_attribute("llm.response.model_name", model)
        span.set_attribute("llm.model_name", model)


def _enrich_litellm_completion(wrapped, instance, args, kwargs):
    span = _set_llm_request_attributes(kwargs.get("model"), _LLM_PROVIDER.get())
    response = wrapped(*args, **kwargs)
    _set_llm_response_attributes(span, getattr(response, "model", None))
    return response


def _enrich_google_call(wrapped, instance, args, kwargs):
    span = _set_llm_request_attributes(kwargs.get("model"), "google")
    response = wrapped(*args, **kwargs)
    _set_llm_response_attributes(span, getattr(response, "model_version", None))
    return response


async def _enrich_async_google_call(wrapped, instance, args, kwargs):
    span = _set_llm_request_attributes(kwargs.get("model"), "google")
    response = await wrapped(*args, **kwargs)
    _set_llm_response_attributes(span, getattr(response, "model_version", None))
    return response



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


def _infer_protocol(endpoint: str | None) -> Literal["http/protobuf", "grpc"] | None:
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
    # Enrichment runs INSIDE the SDK instrumentor's span, before it ends.
    # The official instrumentors own payloads, usage, errors and stream lifetime.
    wrap_function_wrapper("litellm", "completion", _enrich_litellm_completion)
    LiteLLMInstrumentor().instrument(tracer_provider=tracer_provider)
    for method in ("generate_content", "generate_content_stream"):
        wrap_function_wrapper("google.genai.models", f"Models.{method}", _enrich_google_call)
        wrap_function_wrapper(
            "google.genai.models", f"AsyncModels.{method}", _enrich_async_google_call
        )
    GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    # This outer wrapper re-enables only SDK calls inside the suppressed adapter.
    for method in ("generate_content", "generate_content_stream"):
        wrap_function_wrapper(
            "google.genai.models", f"Models.{method}", _restore_google_sdk_tracing
        )
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
