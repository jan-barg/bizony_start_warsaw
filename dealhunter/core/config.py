"""Configuration constants — implementation-spec.md §12, single source of truth.

Every tunable number in the system lives HERE and only here. Modules receive a
`Constants` instance explicitly (no module-level globals), so eval can sweep
θ or the alert budget without code edits. Frozen after Stage 0 — additions via
contract PR only.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from decimal import Decimal

from .enums import HsCategory, Ruleset, Zone


def _default_hs_rate() -> dict[HsCategory, Decimal]:
    return {
        HsCategory.FOOTWEAR_TEXTILE: Decimal("0.169"),
        HsCategory.FOOTWEAR_LEATHER: Decimal("0.08"),
    }


def _default_eta_direct() -> dict[Zone, int]:
    return {Zone.EU: 2, Zone.UK: 5, Zone.US: 5, Zone.JP: 8}


def _default_trap_counts() -> dict[str, int]:
    # spec §4.5 defaults
    return {
        "bait": 3,
        "fake_anchor": 4,
        "anchor_reset": 2,
        "landed_inversion": 3,
        "customs_cliff_pair": 1,
        "fta_origin": 1,
        "whitelist_impersonator": 1,
        "gs_kids": 2,
        "colorway": 2,
        "coupon": 2,
        "stock_race": 1,
        "fake_geo_exclusive": 1,
        "verified_local": 1,
        "net_negative_ip_gated": 1,
        "genuine_geo": 2,
    }


@dataclass(frozen=True)
class Constants:
    # --- world ---
    HORIZON: int = 90
    N_PRODUCTS_HANDCRAFTED: int = 10
    N_PRODUCTS_GENERATED: int = 30
    N_VENDORS: int = 25
    N_MIDDLEMEN: int = 4
    TRAP_COUNTS: dict[str, int] = field(default_factory=_default_trap_counts)

    # --- customs (§5.3) ---
    RULESET: Ruleset = Ruleset.EU_2026_07
    VAT_PL: Decimal = Decimal("0.23")
    LOW_VALUE_EUR: Decimal = Decimal("150.00")     # low-value band boundary, <= inclusive
    DUTY_FLAT_EUR: Decimal = Decimal("3.00")       # EU_2026_07 flat low-value duty; IN the VAT base
    HS_RATE: dict[HsCategory, Decimal] = field(default_factory=_default_hs_rate)
    HANDLING_POSTAL_EUR: Decimal = Decimal("6.00")
    HANDLING_COURIER_EUR: Decimal = Decimal("15.00")

    # --- stopping (§5.7) ---
    THETA_STOP: Decimal = Decimal("0.25")
    DELTA_IMPROVE_EUR: Decimal = Decimal("1.00")
    MIN_OBS: int = 5
    TREND_FALLING_MULT: Decimal = Decimal("1.25")
    TREND_RISING_MULT: Decimal = Decimal("0.80")
    P_DAILY_CLAMP: Decimal = Decimal("0.95")

    # --- trust (§5.6) ---
    TRUST_HIGH: Decimal = Decimal("0.80")
    TRUST_FLOOR: Decimal = Decimal("0.30")
    IMPERSONATION_SIM: float = 0.80                # normalized Levenshtein similarity threshold
    IMPERSONATION_CAP: Decimal = Decimal("0.15")
    PRICE_TOO_GOOD_RATIO: Decimal = Decimal("0.60")
    MIDDLEMAN_HAIRCUT: Decimal = Decimal("0.03")

    # --- EV (§5.6) ---
    HASSLE_EUR: Decimal = Decimal("15")
    CANCEL_HASSLE_EUR: Decimal = Decimal("5")
    P_CANCEL_EST: Decimal = Decimal("0.12")        # documented heuristic for IP_GATED
    DEADLINE_EXPOSURE_EUR: Decimal = Decimal("10")

    # --- auto-buy / escalation (§5.8–§5.9) ---
    STOCK_LOW: int = 2
    OVERCAP_ASK_BAND: Decimal = Decimal("0.10")    # mandate-overridable default
    REASK_IMPROVEMENT_ABS: Decimal = Decimal("5.00")
    REASK_IMPROVEMENT_PCT: Decimal = Decimal("0.05")
    GOOD_DEAL_MARGIN_EUR: Decimal = Decimal("5.00")

    # --- interruptions (one pool: ALERT + GRAY_ROUTE + OVER_CAP, §5.9) ---
    ALERT_BUDGET: int = 2
    ALERT_WINDOW_TICKS: int = 7
    INTERRUPT_DEDUPE_TICKS: int = 7

    # --- intake (§7.1) ---
    INTAKE_MAX_CANDIDATES: int = 8
    INTAKE_MAX_QUESTIONS: int = 3

    # --- matcher (§5.1) ---
    FUZZY_ACCEPT: int = 90
    FUZZY_REJECT: int = 60
    FUZZY_MARGIN: int = 5

    # --- orders (§6.2) ---
    REFUND_TICKS: int = 3

    # --- routes (§5.4) ---
    ETA_DIRECT: dict[Zone, int] = field(default_factory=_default_eta_direct)
    ETA_DOMESTIC_LEG: int = 1

    # --- UI / eval ---
    TICK_MS: int = 300                              # UI concern only; engine never reads it
    EVAL_SEEDS: int = 200
    EVAL_TEMPLATES_PER_SEED: int = 3

    def mvp_world(self) -> "Constants":
        """§13.1 rung-1 preset: 12 products / 10 vendors / 2 middlemen; exactly
        one instance per trap type (compound traps may share a listing)."""
        return dataclasses.replace(
            self,
            N_PRODUCTS_HANDCRAFTED=6,
            N_PRODUCTS_GENERATED=6,
            N_VENDORS=10,
            N_MIDDLEMEN=2,
            TRAP_COUNTS={k: 1 for k in self.TRAP_COUNTS},
        )
