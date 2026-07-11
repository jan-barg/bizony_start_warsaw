"""Landed-cost assembly — STUB, contract only (spec §5.5).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Order of operations (normative): GOODS → COUPON (validity incl. on_sale flag)
→ shipping legs → MM fees (MM_PCT on GOODS+COUPON) → import_charges with
intrinsic = GOODS + COUPON and transport per §5.3. Line items quantized at
finalization; landed_eur = exact sum of quantized lines, never re-rounded.
"""
from __future__ import annotations

from ..core.config import Constants
from ..core.models import RouteQuote, RouteSpec, World


def assemble(listing_id: str, route: RouteSpec, tick: int, world: World, cfg: Constants) -> RouteQuote:
    raise NotImplementedError("feat/engine — spec §5.5")
