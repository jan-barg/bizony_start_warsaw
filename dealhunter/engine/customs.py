"""Versioned customs rule table (spec §5.3).
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


def _line(code: str, label: str, amount: Decimal) -> LineItem:
    """Finalize one EUR receipt line using the shared money policy."""
    from ..core.money import q2

    return LineItem(code=code, label=label, amount_eur=q2(amount))


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
    """Return quantized Polish import-charge lines for a single-item parcel.

    ``intrinsic_eur`` is discounted goods value and ``transport_eur`` is all
    freight to the Polish border. Service fees are deliberately excluded from
    the customs base by the v1.3 project simplification.
    """
    from ..core.money import q2

    if zone == Zone.EU:
        return []

    handling = (
        cfg.HANDLING_POSTAL_EUR
        if carrier == Carrier.POSTAL
        else cfg.HANDLING_COURIER_EUR
    )

    if intrinsic_eur <= cfg.LOW_VALUE_EUR:
        if ioss:
            return []

        lines: list[LineItem] = []
        duty_flat = (
            cfg.DUTY_FLAT_EUR
            if rs == Ruleset.EU_2026_07
            else Decimal("0")
        )
        if duty_flat:
            lines.append(_line("DUTY_FLAT", "Flat low-value import duty", duty_flat))

        vat_base = intrinsic_eur + transport_eur + duty_flat
        lines.append(_line("VAT_IMPORT", "Polish import VAT", cfg.VAT_PL * vat_base))
        lines.append(_line("HANDLING", "Carrier customs handling", handling))
        return lines

    customs_value = intrinsic_eur + transport_eur
    duty_rate = Decimal("0") if preferential(zone, origin) else cfg.HS_RATE[hs]
    duty = q2(duty_rate * customs_value)
    vat = q2(cfg.VAT_PL * (customs_value + duty))

    lines = []
    if duty:
        lines.append(_line("DUTY", "Ad-valorem customs duty", duty))
    lines.append(_line("VAT_IMPORT", "Polish import VAT", vat))
    lines.append(_line("HANDLING", "Carrier customs handling", handling))
    return lines
