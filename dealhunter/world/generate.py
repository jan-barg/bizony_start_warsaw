"""World generation orchestrator — STUB, contract only (spec §4).
Owner: feat/world (Work Order 1). Signature is frozen; body is not."""
from __future__ import annotations

from ..core.config import Constants
from ..core.models import World


def generate_world(seed: int, cfg: Constants) -> World:
    """Given an integer seed, produce the complete deterministic market history:
    catalog, vendors, middlemen, listings, price events, FX, coupons, geo promos,
    traps (with TrapRecords), and the oracle. Same (seed, cfg) ⇒ identical World.
    """
    raise NotImplementedError("feat/world — spec §4")
