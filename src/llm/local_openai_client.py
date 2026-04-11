from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from litellm import completion
from pydantic import BaseModel

from src.config.settings import settings

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)

_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL)
_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE)


class LocalOpenAICompatibleClient:
    """Chat client for local OpenAI-compatible inference servers."""

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
            return self._strip_thinking_content(text)
        return text

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
        response_format = config_overrides.pop("response_format", {"type": "json_object"})
        structured_prompt = self._build_structured_prompt(prompt, schema)
        structured_system_instruction = self._build_structured_system_instruction(
            system_instruction=system_instruction,
        )

        try:
            response = self._completion(
                messages=self._build_messages(
                    prompt=structured_prompt,
                    system_instruction=structured_system_instruction,
                ),
                model=model,
                temperature=temperature,
                response_format=response_format,
                **config_overrides,
            )
        except Exception:
            response = self._completion(
                messages=self._build_messages(
                    prompt=structured_prompt,
                    system_instruction=structured_system_instruction,
                ),
                model=model,
                temperature=temperature,
                **config_overrides,
            )

        content = self._extract_text(response)
        payload = self._extract_json_payload(content)
        return response_model.model_validate(payload)

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
