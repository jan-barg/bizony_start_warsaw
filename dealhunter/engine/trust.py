"""Trust score + EV — STUB, contract only (spec §5.6).
Owner: feat/engine (Work Order 2). Signatures are frozen; bodies are not.

Normative reminders:
- Whitelist exact-domain ⇒ 1.00 short-circuit; impersonation similarity ≥ 0.80
  ⇒ IMPERSONATION_SUSPECTED and final score capped at 0.15.
- EV uses ONE common reference — the cap: savings = cap − landed. Never score a
  candidate against its cheapest rival. Selection among qualifying = argmax EV.
- Engine code must NOT read hidden labels (is_fraudulent etc.) — observables only.
"""
from __future__ import annotations

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import TrustFlag
from ..core.models import RouteQuote, Vendor, World


def trust_score(vendor: Vendor, quote: RouteQuote, world: World, cfg: Constants) -> tuple[Decimal, set[TrustFlag]]:
    raise NotImplementedError("feat/engine — spec §5.6")


def expected_value(
    quote: RouteQuote,
    trust: Decimal,
    cap: Decimal,
    deadline_ticks_left: int | None,
    cfg: Constants,
) -> Decimal:
    raise NotImplementedError("feat/engine — spec §5.6")
