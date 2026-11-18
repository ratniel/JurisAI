from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from litellm import BadRequestError, UnsupportedParamsError, completion
from pydantic import BaseModel

from src.config.settings import settings

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)

_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL)
_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE)
LOGGER = logging.getLogger(__name__)


class LocalOpenAICompatibleClient:
    """Chat client for local OpenAI-compatible inference servers."""

    TRANSPORT_MAX_RETRIES = 2
    INFERENCE_MAX_RETRIES = 2

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        enable_thinking: bool | None = None,
        extra_headers: dict[str, str] | None = None,
        disable_thinking_via_extra_body: bool = True,
    ) -> None:
        config = settings.local_generation
        self.default_model = model or config.model
        self.provider_name = "local_openai"
        self.last_invocation_metadata: dict[str, Any] | None = None
        self.invocation_history: list[dict[str, Any]] = []
        self._base_url = base_url or config.base_url
        self._api_key = api_key or config.api_key
        self._timeout_seconds = timeout_seconds or config.timeout_seconds
        self._enable_thinking = (
            config.enable_thinking if enable_thinking is None else enable_thinking
        )
        self._extra_headers = dict(extra_headers or {})
        self._disable_thinking_via_extra_body = disable_thinking_via_extra_body

    def _resolve_model_name(self, model: str | None) -> str:
        if model is None or model.startswith("models/gemini-"):
            return self.default_model
        return model

    def generate_text(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0.2,
        **config_overrides: Any,
    ) -> str:
        for attempt in range(1, self.INFERENCE_MAX_RETRIES + 2):
            response = self._completion(
                messages=self._build_messages(
                    prompt=prompt,
                    system_instruction=system_instruction,
                ),
                model=model,
                temperature=temperature,
                **config_overrides,
            )
            text = self._extract_text(response)
            if not self._enable_thinking:
                text = self._strip_thinking_content(text)
            if text.strip():
                self._record_invocation(
                    response=response,
                    model=model,
                    operation="text_generation",
                    attempt=attempt,
                    outcome="success",
                )
                return text

            self._record_invocation(
                response=response,
                model=model,
                operation="text_generation",
                attempt=attempt,
                outcome="empty_response",
            )
            if attempt <= self.INFERENCE_MAX_RETRIES:
                LOGGER.warning(
                    "Retrying empty model response (%s/%s).",
                    attempt,
                    self.INFERENCE_MAX_RETRIES + 1,
                )

        raise ValueError(
            "Model returned an empty answer after "
            f"{self.INFERENCE_MAX_RETRIES + 1} inference attempts."
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[StructuredModelT],
        *,
        model: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = 0,
        **config_overrides: Any,
    ) -> StructuredModelT:
        schema = response_model.model_json_schema()
        response_format = config_overrides.pop(
            "response_format",
            self._build_json_schema_response_format(schema=schema, schema_name=response_model.__name__),
        )
        structured_prompt = self._build_structured_prompt(prompt, schema)
        structured_system_instruction = self._build_structured_system_instruction(
            system_instruction=system_instruction,
        )

        messages = self._build_messages(
            prompt=structured_prompt,
            system_instruction=structured_system_instruction,
        )
        use_response_format = True
        response_format_fallback_used = False
        last_error: ValueError | None = None

        for attempt in range(1, self.INFERENCE_MAX_RETRIES + 2):
            try:
                response = self._completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    **({"response_format": response_format} if use_response_format else {}),
                    **config_overrides,
                )
            except (BadRequestError, UnsupportedParamsError, TypeError) as exc:
                if not use_response_format or not self._should_retry_without_response_format(exc):
                    raise
                LOGGER.warning(
                    "Retrying structured completion without response_format after %s: %s",
                    type(exc).__name__,
                    exc,
                )
                use_response_format = False
                response_format_fallback_used = True
                response = self._completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    **config_overrides,
                )

            try:
                content = self._extract_structured_text(
                    response, model=self._resolve_model_name(model),
                )
                payload = self._extract_json_payload(content)
                result = response_model.model_validate(payload)
            except ValueError as exc:
                last_error = exc
                self._record_invocation(
                    response=response,
                    model=model,
                    operation="structured_generation",
                    attempt=attempt,
                    outcome="invalid_structured_response",
                    response_format_fallback_used=response_format_fallback_used,
                    error=str(exc)[:500],
                )
                if attempt <= self.INFERENCE_MAX_RETRIES:
                    LOGGER.warning(
                        "Retrying invalid structured model response (%s/%s): %s",
                        attempt,
                        self.INFERENCE_MAX_RETRIES + 1,
                        exc,
                    )
                    continue
                break

            self._record_invocation(
                response=response,
                model=model,
                operation="structured_generation",
                attempt=attempt,
                outcome="success",
                response_format_fallback_used=response_format_fallback_used,
            )
            return result

        raise ValueError(
            "Model did not return valid structured JSON after "
            f"{self.INFERENCE_MAX_RETRIES + 1} inference attempts."
        ) from last_error

    def _completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float | None,
        **config_overrides: Any,
    ) -> Any:
        completion_kwargs = dict(config_overrides)
        completion_kwargs.setdefault("drop_params", True)
        completion_kwargs.setdefault("max_retries", self.TRANSPORT_MAX_RETRIES)
        if self._extra_headers:
            completion_kwargs["extra_headers"] = {
                **self._extra_headers,
                **completion_kwargs.get("extra_headers", {}),
            }
        if (
            self._disable_thinking_via_extra_body
            and "extra_body" not in completion_kwargs
            and not self._enable_thinking
        ):
            completion_kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False}
            }
        return completion(
            model=self._resolve_model_name(model),
            custom_llm_provider="openai",
            messages=messages,
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            temperature=temperature,
            **completion_kwargs,
        )

    def _record_invocation(
        self,
        *,
        response: Any,
        model: str | None,
        operation: str,
        attempt: int,
        outcome: str,
        response_format_fallback_used: bool = False,
        error: str | None = None,
    ) -> None:
        finish_reason = None
        try:
            finish_reason = response.choices[0].finish_reason
        except (AttributeError, IndexError, KeyError, TypeError):
            pass
        metadata = {
            "provider": self.provider_name,
            "operation": operation,
            "requested_model": self._resolve_model_name(model),
            "response_model": str(getattr(response, "model", "") or "") or None,
            "attempt": attempt,
            "outcome": outcome,
            "transport_max_retries": self.TRANSPORT_MAX_RETRIES,
            "inference_max_retries": self.INFERENCE_MAX_RETRIES,
            "response_format_fallback_used": response_format_fallback_used,
            "finish_reason": finish_reason,
            "usage": self._usage_to_dict(getattr(response, "usage", None)),
            "error": error,
        }
        self.last_invocation_metadata = metadata
        self.invocation_history.append(metadata)

    @staticmethod
    def _usage_to_dict(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, dict):
            return dict(usage)
        model_dump = getattr(usage, "model_dump", None)
        if callable(model_dump):
            payload = model_dump()
            return payload if isinstance(payload, dict) else {}
        return {
            key: value
            for key, value in vars(usage).items()
            if not key.startswith("_")
        } if hasattr(usage, "__dict__") else {}

    @staticmethod
    def _build_messages(
        *,
        prompt: str,
        system_instruction: str | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _build_structured_prompt(prompt: str, schema: dict[str, Any]) -> str:
        return (
            f"{prompt}\n\n"
            "Return only valid JSON matching this schema exactly:\n"
            f"{json.dumps(schema, indent=2, sort_keys=True)}"
        )

    @staticmethod
    def _build_structured_system_instruction(
        *,
        system_instruction: str | None,
    ) -> str:
        suffix = (
            "Return JSON only. Do not wrap it in markdown. "
            "Do not include commentary before or after the JSON object."
        )
        if not system_instruction:
            return suffix
        return f"{system_instruction}\n\n{suffix}"

    @staticmethod
    def _build_json_schema_response_format(
        *,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }


    @staticmethod
    def _should_retry_without_response_format(exc: Exception) -> bool:
        message = str(exc).lower()
        if isinstance(exc, (BadRequestError, UnsupportedParamsError)):
            return (
                "response_format" in message
                or "json_object" in message
                or "unsupported" in message
            )
        return "response_format" in message

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise ValueError("Local model response did not include a chat message.") from exc

        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content or "")

    @classmethod
    def _extract_structured_text(
        cls,
        response: Any,
        *,
        model: str,
    ) -> str:
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise ValueError("Local model response did not include a chat message.") from exc

        content = cls._coerce_message_field_to_text(getattr(message, "content", ""))
        if content.strip():
            return content

        if model == "qwen3.5-4b-mlx":
            reasoning_content = cls._coerce_message_field_to_text(
                getattr(message, "reasoning_content", "")
            )
            if reasoning_content.strip():
                return reasoning_content

        return content


    @staticmethod
    def _coerce_message_field_to_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in value
            )
        return str(value or "")


    @classmethod
    def _extract_json_payload(cls, text: str) -> Any:
        cleaned = cls._clean_response_text(text)
        decoder = json.JSONDecoder()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        for index, char in enumerate(cleaned):
            if char not in "{[":
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[index:])
                return payload
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Could not parse structured JSON from local model output: {text!r}")

    @classmethod
    def _clean_response_text(cls, text: str) -> str:
        without_thinking = cls._strip_thinking_content(text)
        if without_thinking.startswith("```"):
            without_thinking = _CODE_FENCE_PATTERN.sub("", without_thinking).strip()
        return without_thinking

    @staticmethod
    def _strip_thinking_content(text: str) -> str:
        return _THINK_BLOCK_PATTERN.sub("", text).strip()
