"""Route enumeration — STUB, contract only (spec §5.2, §5.4).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Normative reminders:
- The BASE PL quote always exists; promos are ADDITIONAL RouteSpecs.
- VERIFIED_LOCAL is never purchasable; IP_GATED filtered under GeoArb.NEVER.
- STOREFRONT/IP_GATED promos require a middleman route (domestic delivery).
- Feasibility / DEADLINE_MISSED are computed over route CLASSES ignoring
  current stock (§5.7, §6.1).
"""
from __future__ import annotations

from ..core.models import Mandate, RouteSpec, World


def enumerate_routes(listing_id: str, tick: int, mandate: Mandate, world: World) -> list[RouteSpec]:
    raise NotImplementedError("feat/engine — spec §5.4")
