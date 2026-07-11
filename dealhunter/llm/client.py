"""LLM client protocol + NullClient — WORKING contract (spec §7.3).
Owner: feat/matcher-llm extends this (OpenAIClient, cache); the protocol and
NullClient semantics are frozen at Stage 0 so every branch can run --no-llm.
"""
from __future__ import annotations

from typing import Protocol


class IntakeUnavailable(Exception):
    """Raised by intake when no LLM is available (--no-llm). The API layer maps
    this to HTTP 503; the UI falls back to the structured form (§7.1/§7.3)."""


class LLMClient(Protocol):
    def complete(self, request: dict) -> dict:
        """Single entry point. `request` is a canonical-JSON-able dict (it is the
        cache key, §7.3). Returns a schema-validated dict; shapes are defined by
        the calling module (intake / adjudicate / narrate)."""
        ...


class NullClient:
    """The --no-llm client. Deterministic, offline, always available.

    Semantics (frozen): every call reports abstention. Callers interpret it:
    - intake: raise IntakeUnavailable (UI falls back to a form),
    - adjudication: abstain ⇒ listing unmatched,
    - narration: fall back to the deterministic template.
    """

    def complete(self, request: dict) -> dict:  # noqa: ARG002 — contract signature
        return {"abstain": True}
