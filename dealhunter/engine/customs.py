"""Customs rule table — STUB, contract only (spec §5.3).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Normative reminders for the implementer:
- Ruleset.EU_2026_07 (default): low-value (intrinsic ≤ 150) pays DUTY_FLAT €3,
  and that €3 is INSIDE the import-VAT base. IOSS returns [] (deemed-importer
  remits VAT + the €3 in-sticker — stated simplification, §14.9).
- Ruleset.EU_2025_LEGACY: classic de-minimis, no flat duty.
- transport_eur = SHIP_DIRECT (direct) or SHIP_DOM + SHIP_INTL (middleman).
- Rules 3/4 (> 150): duty_rate 0 only if preferential(zone, origin);
  VAT on (customs_value + duty). Handling fee by carrier.
- ZERO-AMOUNT LINES ARE OMITTED from the returned list (a preferential-origin
  import has no DUTY line at all, not DUTY 0.00 — V5 asserts absence).
"""
from __future__ import annotations

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import Carrier, HsCategory, Ruleset, Zone
from ..core.models import LineItem


def preferential(zone: Zone, origin: str) -> bool:
    """EU–UK TCA / EU–Japan EPA preferential origin (§5.3). Pure, tested both ways."""
    return (zone == Zone.UK and origin == "GB") or (zone == Zone.JP and origin == "JP")


def import_charges(
    rs: Ruleset,
    zone: Zone,
    intrinsic_eur: Decimal,
    transport_eur: Decimal,
    hs: HsCategory,
    origin: str,
    ioss: bool,
    carrier: Carrier,
    cfg: Constants,
) -> list[LineItem]:
    raise NotImplementedError("feat/engine — spec §5.3")
