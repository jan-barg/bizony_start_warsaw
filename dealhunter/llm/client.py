"""Frozen LLM protocol plus OpenAI Responses and offline clients."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..core.config import Constants


class IntakeUnavailable(Exception):
    """Raised by intake when no LLM is available (--no-llm). The API layer maps
    this to HTTP 503; the UI falls back to the structured form (§7.1/§7.3)."""


class LLMProtocolError(RuntimeError):
    """Provider output did not satisfy the caller-owned structured contract."""


class LLMClient(Protocol):
    def complete(self, request: dict) -> dict:
        """Single entry point. `request` is a canonical-JSON-able dict (it is the
        cache key, §7.3). Returns a schema-validated dict; shapes are defined by
        the calling module (intake / adjudicate / narrate)."""
        ...


@dataclass(frozen=True)
class _LLMRequest:
    surface: str
    schema: dict[str, Any]
    instructions: str
    input: Any

    @classmethod
    def parse(cls, request: dict) -> "_LLMRequest":
        required = {"surface", "schema", "instructions", "input"}
        if set(request) != required:
            raise LLMProtocolError(f"request envelope keys must be {sorted(required)}")
        if not isinstance(request["surface"], str) or not request["surface"]:
            raise LLMProtocolError("surface must be a non-empty string")
        if not isinstance(request["schema"], dict):
            raise LLMProtocolError("schema must be an object")
        if not isinstance(request["instructions"], str):
            raise LLMProtocolError("instructions must be a string")
        try:
            json.dumps(request["input"], allow_nan=False)
        except (TypeError, ValueError) as error:
            raise LLMProtocolError("input must be canonical-JSON-compatible") from error
        return cls(
            surface=request["surface"],
            schema=request["schema"],
            instructions=request["instructions"],
            input=request["input"],
        )


def _validate_top_level(payload: object, schema: dict[str, Any]) -> dict:
    if not isinstance(payload, dict):
        raise LLMProtocolError("structured response must be an object")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(key not in payload for key in required):
        raise LLMProtocolError("structured response is missing required fields")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False and isinstance(properties, dict):
        if set(payload) - set(properties):
            raise LLMProtocolError("structured response has unknown fields")
    return payload


class OpenAIClient:
    """Thin Responses API adapter; callers own schemas and untrusted delimiters."""

    def __init__(self, cfg: Constants, sdk_client: Any | None = None) -> None:
        if sdk_client is None:
            from openai import OpenAI

            sdk_client = OpenAI()
        self._sdk: Any = sdk_client
        self.model_pin = cfg.LLM_MODEL_PIN
        self._reasoning_effort = cfg.LLM_REASONING_EFFORT
        self._max_output_tokens = cfg.LLM_MAX_OUTPUT_TOKENS

    def complete(self, request: dict) -> dict:
        envelope = _LLMRequest.parse(request)
        schema_name = re.sub(r"[^A-Za-z0-9_-]", "_", envelope.surface)
        api_input = envelope.input
        if not isinstance(api_input, (str, list)):
            api_input = json.dumps(
                api_input,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        response = self._sdk.responses.create(
            model=self.model_pin,
            store=False,
            reasoning={"effort": self._reasoning_effort},
            max_output_tokens=self._max_output_tokens,
            instructions=envelope.instructions,
            input=api_input,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": envelope.schema,
                }
            },
        )
        output_text = getattr(response, "output_text", "")
        if not isinstance(output_text, str) or not output_text:
            raise LLMProtocolError("provider refused or returned no structured output")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise LLMProtocolError("provider returned malformed JSON") from error
        return _validate_top_level(payload, envelope.schema)


class NullClient:
    """The --no-llm client. Deterministic, offline, always available.

    Semantics (frozen): every call reports abstention. Callers interpret it:
    - intake: raise IntakeUnavailable (UI falls back to a form),
    - adjudication: abstain ⇒ listing unmatched,
    - narration: fall back to the deterministic template.
    """

    def complete(self, request: dict) -> dict:  # noqa: ARG002 — contract signature
        return {"abstain": True}
