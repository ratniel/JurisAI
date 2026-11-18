from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from src.llm.local_openai_client import LocalOpenAICompatibleClient
from src.llm.openrouter_client import OpenRouterClient


class SampleStructuredResponse(BaseModel):
    answer: str


def _response(content: str, model: str) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
    )


def test_text_generation_retries_two_empty_responses() -> None:
    client = OpenRouterClient(api_key="test", model="openrouter/free")
    responses = iter(
        [
            _response("", "free/model-a"),
            _response("  ", "free/model-b"),
            _response("Grounded answer", "free/model-c"),
        ]
    )
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return next(responses)

    with patch("src.llm.local_openai_client.litellm.completion", fake_completion):
        assert client.generate_text("Answer") == "Grounded answer"
    assert len(calls) == 3
    assert {call["max_retries"] for call in calls} == {2}
    assert [item["outcome"] for item in client.invocation_history] == [
        "empty_response",
        "empty_response",
        "success",
    ]
    assert client.last_invocation_metadata is not None
    assert client.last_invocation_metadata["provider"] == "openrouter"
    assert client.last_invocation_metadata["response_model"] == "free/model-c"


def test_structured_generation_retries_two_invalid_responses() -> None:
    client = LocalOpenAICompatibleClient(model="test-model")
    responses = iter(
        [
            _response("not json", "model-a"),
            _response('{"wrong":"shape"}', "model-b"),
            _response('{"answer":"valid"}', "model-c"),
        ]
    )
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return next(responses)

    with patch("src.llm.local_openai_client.litellm.completion", fake_completion):
        result = client.generate_structured("Classify", SampleStructuredResponse)

    assert result.answer == "valid"
    assert len(calls) == 3
    assert [item["attempt"] for item in client.invocation_history] == [1, 2, 3]
    assert client.invocation_history[-1]["inference_max_retries"] == 2


def test_transport_error_is_not_retried_by_the_inference_layer() -> None:
    client = LocalOpenAICompatibleClient(model="test-model")
    call_count = 0

    def fake_completion(**_):
        nonlocal call_count
        call_count += 1
        raise PermissionError("permanent failure")

    with patch("src.llm.local_openai_client.litellm.completion", fake_completion):
        try:
            client.generate_text("Answer")
        except PermissionError as exc:
            assert str(exc) == "permanent failure"
        else:
            raise AssertionError("Expected the permanent error to propagate.")

    assert call_count == 1
