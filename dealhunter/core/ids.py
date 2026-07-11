"""Deterministic, human-readable, sortable identifiers — spec §2.4.
No UUIDs anywhere in the engine. Frozen after Stage 0."""
from __future__ import annotations


def product_id(style_code: str) -> str:
    return f"p_{style_code}"


def vendor_id(n: int) -> str:
    return f"v_{n:03d}"


def middleman_id(n: int) -> str:
    return f"m_{n:02d}"


def listing_id(vendor: str, style_code: str) -> str:
    return f"l_{vendor}_{style_code}"


def coupon_id(listing: str, from_tick: int) -> str:
    return f"c_{listing}_{from_tick}"


def geo_promo_id(listing: str, geo: str) -> str:
    return f"g_{listing}_{geo}"


def hunt_id(seed: int, n: int) -> str:
    return f"h_{seed}_{n}"


def ask_id(hunt: str, tick: int, seq: int) -> str:
    """Ask ids carry a sequence: same-tick re-evaluation after a cancellation
    can mint a second ask — ids must never collide (§2.4, round-2 finding 6)."""
    return f"a_{hunt}_{tick}_{seq}"


def receipt_id(hunt: str, tick: int, seq: int) -> str:
    return f"r_{hunt}_{tick}_{seq}"
