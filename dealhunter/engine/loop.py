"""Tick loop & hunt state machine — STUB, contract only (spec §6).
Owner: feat/engine (Work Order 2). Signatures are frozen; bodies are not.

Normative reminders:
- Monitor: for tick in start..expires−1: process_refunds(tick); evaluate_tick(...).
- ASK pauses the world clock; approval is quote-exact and single-use (CONSUMED).
- Settlement epilogue: after terminal status, keep ticking process_refunds only
  until no CANCELLED_BY_MERCHANT order awaits refund (invariant 8).
- Immediate: one evaluate_tick; on merchant cancellation re-run once same tick
  with the listing excluded, else ESCALATE_NONE_FOUND with monitor handoff.
"""
from __future__ import annotations

from ..core.config import Constants
from ..core.models import Hunt, Receipt, World
from ..llm.client import LLMClient


def run_monitor(hunt: Hunt, world: World, cfg: Constants, llm: LLMClient) -> list[Receipt]:
    raise NotImplementedError("feat/engine — spec §6")


def run_immediate(hunt: Hunt, world: World, cfg: Constants, llm: LLMClient) -> Receipt:
    raise NotImplementedError("feat/engine — spec §6")
