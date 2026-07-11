"""Product matcher, tiers 1–4 — STUB, contract only (spec §5.1).
Owner: feat/matcher-llm (Work Order 3). Signature is frozen; body is not.

Normative reminders:
- Tier 1 style-code exact hit is decisive (colorway_confirmed=True).
- Tier 4 (LLM) is VETO-ONLY: its matches always carry MatchFlag.LLM_MATCH_ONLY
  and can never set colorway_confirmed. NullClient ⇒ abstain ⇒ unmatched.
- SIZE gate evidence: structured listing.size_eu is authoritative; title-derived
  size never overrides it (SIZE_AMBIGUOUS at most).
- Results memoized on (hunt_id, listing_id) — titles are static.
"""
from __future__ import annotations

from ..core.models import Brief, Listing, MatchResult, World
from ..llm.client import LLMClient


def match(listing: Listing, brief: Brief, world: World, llm: LLMClient) -> MatchResult:
    raise NotImplementedError("feat/matcher-llm — spec §5.1")
