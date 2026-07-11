"""Hierarchical seed derivation — implementation-spec.md §2.3. Frozen after Stage 0.

Fixed namespaces (exhaustive — add here first, then use):

    ("catalog",)                 generated products
    ("vendor", vendor_id)        vendor attributes
    ("assort", vendor_id)        which products a vendor lists
    ("title", listing_id)        messy-title noise ops
    ("price", listing_id)        that listing's entire price/stock/coupon stream
    ("fx", pair)                 one FX pair's walk
    ("traps",)                   trap placement choices
    ("geo", listing_id)          geo-promo parameters
    ("cancel", listing_id, tick) ip-gated cancellation draw at purchase
    ("eval", seed)               eval hunt templates

Stable under content changes: adding vendor #26 must not shift vendor #7's
prices, because every consumer derives its own stream from (master, namespace).
"""
from __future__ import annotations

import hashlib
import random


def derive(master: int, *namespace: str | int) -> int:
    h = hashlib.sha256(":".join(map(str, (master, *namespace))).encode()).digest()
    return int.from_bytes(h[:8], "big")


def rng(master: int, *namespace: str | int) -> random.Random:
    return random.Random(derive(master, *namespace))
