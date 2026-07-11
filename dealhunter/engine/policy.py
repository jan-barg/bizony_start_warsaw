"""Policy — Layer 1–4 orchestration and action selection — STUB (spec §5.8–§5.9).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Normative reminders:
- Exactly ONE Receipt per tick; considered = top-5 by landed among
  eligibility ≠ HARD_REJECT, ties broken (listing_id, route kind, middleman_id).
- Selection set S = qualifying ∧ purchase_eligible, minus gray quotes that
  cannot ask this tick (each removal receipted). Reselect from what remains.
- Escalation ladder E0–E5 (§5.9): E4 auto-reject > cap·(1+band) silently;
  E3 over-cap ask inside the band on the deal-quality test; E2 gray-route ask.
- Invariants §6.3 are asserted live here and in loop.py.
"""
from __future__ import annotations

from ..core.config import Constants
from ..core.models import Hunt, Receipt, World
from ..llm.client import LLMClient


def evaluate_tick(hunt: Hunt, tick: int, world: World, cfg: Constants, llm: LLMClient) -> Receipt:
    raise NotImplementedError("feat/engine — spec §5.8/§5.9")
