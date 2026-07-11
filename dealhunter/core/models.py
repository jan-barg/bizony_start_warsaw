"""Every Pydantic model in the system — implementation-spec.md §3.2/§3.3.
This file IS the contract between the four branches. Frozen after Stage 0;
changes only via contract PR at a sync point.

Serialization rules (normative, §6.3 invariant 6):
- Decimals serialize as exact strings (pydantic v2 JSON mode default).
- Set-typed fields serialize as SORTED lists (field serializers below) so the
  same object always produces the same bytes.
- `canonical_json()` is the one true serializer for hashing (Ask.quote_hash,
  LLM cache keys) and JSONL receipts.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer, field_validator

from .enums import (
    AccessTier,
    Action,
    AskKind,
    Carrier,
    Channel,
    Condition,
    Currency,
    DecidedBy,
    Eligibility,
    Geo,
    GeoArb,
    HsCategory,
    HuntStatus,
    IntakeStatus,
    MatchFlag,
    Mode,
    OrderState,
    TrustFlag,
)


def canonical_json(model: BaseModel) -> str:
    """Deterministic JSON: sorted keys, no whitespace, Decimals as strings,
    sets pre-sorted by their field serializers."""
    data = model.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def quote_hash(quote: "RouteQuote") -> str:
    """sha256 of the canonical quote — asks bind approval to this (§3.3)."""
    return hashlib.sha256(canonical_json(quote).encode()).hexdigest()


# ---------------------------------------------------------------------------
# §3.2 World models (generated once per seed, immutable thereafter)
# ---------------------------------------------------------------------------

class Product(BaseModel):
    id: str
    brand: str
    model: str
    colorway_name: str                  # "White/Black"
    style_code: str                     # "DD1391-100" — canonical identity
    sizes_eu: list[Decimal]             # includes .5 sizes
    fair_price_eur: Decimal
    hs_category: HsCategory
    origin_country: str                 # "VN", "CN", "ID" — manufacturing origin
    weight_kg: Decimal
    is_kids_version_of: str | None = None   # style_code of adult version

    @field_validator("sizes_eu")
    @classmethod
    def _sizes_in_range(cls, v: list[Decimal]) -> list[Decimal]:
        for s in v:
            if not (Decimal("35") <= s <= Decimal("50")):
                raise ValueError(f"size_eu {s} outside [35, 50]")
        return v


class ColorwayAlias(BaseModel):
    style_code: str
    alias: str                          # ("DD1391-100", "Panda")


class Vendor(BaseModel):
    id: str
    name: str
    domain: str
    geo: Geo
    currency: Currency
    channel: Channel
    ships_to: set[Geo]                  # PL ∈ ships_to ⇔ direct route exists
    shipping_table: dict[str, tuple[Decimal, Carrier]]  # dest Zone/Geo value → (cost in vendor ccy, carrier)
    domestic_shipping: tuple[Decimal, Carrier]
    return_days: int                    # 0 = no returns
    domain_age_days: int
    review_count: int
    review_avg: Decimal                 # 1.00–5.00
    reviews_last_30d: int               # velocity signal
    ioss_registered: bool               # meaningful for non-EU vendors only
    is_fraudulent: bool                 # HIDDEN label — engine code must never read

    @field_serializer("ships_to")
    def _sorted_ships_to(self, v: set[Geo]) -> list[str]:
        return sorted(g.value for g in v)


class WhitelistEntry(BaseModel):
    domain: str                         # exact-match semantics only (§5.6)
    vendor_id: str


class Middleman(BaseModel):
    id: str
    name: str
    located_in: Geo                     # JP | US | UK
    forwards_to: set[Geo]               # must include PL to be usable
    fee_flat_eur: Decimal
    fee_pct: Decimal                    # of discounted goods value, e.g. 0.02
    intl_shipping_eur: list[tuple[Decimal, Decimal]]  # [(max_kg, price)] ascending
    intl_carrier: Carrier               # drives the border handling fee (§5.3)
    extra_ticks: int                    # processing + transit
    # insurance modeling removed in v1.2 (spec §14.8)

    @field_serializer("forwards_to")
    def _sorted_forwards_to(self, v: set[Geo]) -> list[str]:
        return sorted(g.value for g in v)


class Listing(BaseModel):
    id: str
    vendor_id: str
    raw_title: str                      # the messy string the matcher must earn
    image_url: str
    condition: Condition
    size_eu: Decimal
    true_product_id: str                # HIDDEN
    is_bait: bool                       # HIDDEN
    is_counterfeit: bool                # HIDDEN


class PriceEvent(BaseModel):            # one row per (listing, tick)
    listing_id: str
    tick: int
    sticker: Decimal                    # vendor currency; VAT-inclusive per §5.3 preamble
    stock: int
    on_sale: bool                       # generator-set; the ONLY sale predicate (§5.5)
    was_price_shown: Decimal | None = None   # the vendor's *claimed* anchor
    coupon_id: str | None = None


class Coupon(BaseModel):
    id: str
    code: str
    kind: Literal["pct", "flat"]
    value: Decimal
    min_basket: Decimal | None = None   # vendor currency
    excludes_sale: bool = False
    valid_from: int = 0                 # inclusive ticks
    valid_to: int = 0


class FxRate(BaseModel):
    tick: int
    pair: str                           # "EURGBP" etc., EUR always base
    rate: Decimal                       # 6 dp; 1 EUR = rate × quote ccy


class GeoPromo(BaseModel):
    id: str
    listing_id: str
    viewer_geo: Geo
    promo_sticker: Decimal              # an ADDITIONAL quote, never a replacement (§5.2)
    from_tick: int
    to_tick: int
    access_tier: AccessTier             # STOREFRONT | IP_GATED | VERIFIED_LOCAL
    p_cancel: Decimal | None = None     # HIDDEN; only for IP_GATED


class TrapRecord(BaseModel):            # injection log → dossier + eval
    trap_type: str
    listing_id: str | None = None
    vendor_id: str | None = None
    ticks: tuple[int, int] | None = None
    explanation: str
    correct_behavior: str


class OracleBest(BaseModel):
    tick: int
    listing_id: str
    route_kind: Literal["direct", "middleman"]
    middleman_id: str | None = None
    landed_eur: Decimal


class OracleAnswer(BaseModel):          # per hunt template (§4.6)
    allow: OracleBest | None = None     # best under geo_arbitrage=ALLOW
    never: OracleBest | None = None     # best under geo_arbitrage=NEVER


class World(BaseModel):
    seed: int
    horizon: int
    products: list[Product]
    aliases: list[ColorwayAlias]
    vendors: list[Vendor]
    whitelist: list[WhitelistEntry]
    middlemen: list[Middleman]
    listings: list[Listing]
    price_events: list[PriceEvent]
    coupons: list[Coupon]
    fx: list[FxRate]
    geo_promos: list[GeoPromo]
    traps: list[TrapRecord]
    oracle: dict[str, OracleAnswer]     # hunt-template key → answers


# ---------------------------------------------------------------------------
# §3.3 Hunt-side models
# ---------------------------------------------------------------------------

class Brief(BaseModel):
    product_query: str                  # "Nike Dunk Low"
    colorway: str | None = None
    style_code: str | None = None       # never guessed by intake
    size_eu: Decimal
    condition: Condition = Condition.NEW
    exclude_kids: bool = True
    exclude_resellers: bool = False


class AutoBuy(BaseModel):
    enabled: bool = False
    within_eur_of_target: Decimal = Decimal("5.00")
    require_stock_low: bool = True      # honored as implication (§5.8)
    require_trust_high: bool = True     # honored as implication (§5.8)
    require_colorway_confirmed: bool = True   # NOT user-disablable; kept for receipt clarity


class Mandate(BaseModel):
    mode: Mode
    cap_landed_eur: Decimal
    need_within_ticks: int | None = None      # "need it in 10 days" → 10
    auto_buy: AutoBuy = AutoBuy()
    allow_middlemen: bool = True
    geo_arbitrage: GeoArb = GeoArb.ASK
    overcap_ask_band_pct: Decimal = Decimal("0.10")   # §5.9; 0 disables over-cap asks
    alert_budget_per_week: int = 2
    expires_tick: int = 90              # absolute; loop runs to expires−1 (§6.2)
    revoked: bool = False


class IntakeResult(BaseModel):          # §7.1 — outcome of one intake parse
    status: IntakeStatus
    brief: Brief | None = None          # None unless status == OK
    mandate: Mandate | None = None
    missing: list[str] = []             # machine keys: "size_eu", "cap_landed_eur", …
    questions: list[str] = []           # LLM-worded, ≤ INTAKE_MAX_QUESTIONS


class IntakeSession(BaseModel):         # §7.1 — holds the clarification loop.
    id: str                             # A Hunt is created ONLY when sufficiency
    world_id: str                       # passes, so Hunt.brief/mandate are never None.
    transcript: list[str]               # accumulated user inputs (text; image refs by hash)
    last_result: IntakeResult
    hunt_id: str | None = None          # set once promoted to a DRAFT hunt


class RouteSpec(BaseModel):             # one enumerable way to obtain a listing (§5.4)
    kind: Literal["direct", "middleman"]
    middleman_id: str | None = None
    observation_geo: Geo                # PL, or the "VPN" geo used to see the price
    access_tier: AccessTier
    promo_id: str | None = None         # GeoPromo id when the price is a promo


class LineItem(BaseModel):
    code: Literal[
        "GOODS", "COUPON", "SHIP_DIRECT", "SHIP_DOM", "MM_FLAT", "MM_PCT",
        "SHIP_INTL", "DUTY", "DUTY_FLAT", "VAT_IMPORT", "HANDLING",
    ]
    label: str
    amount_eur: Decimal                 # quantized at finalization; COUPON is negative


class RouteQuote(BaseModel):            # one PRICED way to obtain one listing at one tick
    listing_id: str
    tick: int
    kind: Literal["direct", "middleman"]
    middleman_id: str | None = None
    observation_geo: Geo
    access_tier: AccessTier
    line_items: list[LineItem]
    landed_eur: Decimal                 # = exact sum of line_items (§2.1)
    eta_ticks: int
    p_cancel_est: Decimal = Decimal("0")   # agent's estimate; 0 unless IP_GATED


class MatchResult(BaseModel):           # §5.1 output
    style_code: str | None = None
    colorway_confirmed: bool = False    # ONLY deterministic evidence may set this
    confidence: float = 0.0
    flags: list[MatchFlag] = []

    @field_serializer("flags")
    def _sorted_flags(self, v: list[MatchFlag]) -> list[str]:
        return sorted(f.value for f in v)


class Evaluation(BaseModel):            # decision-engine verdict on one RouteQuote
    quote: RouteQuote
    match: MatchResult
    trust: Decimal
    trust_flags: set[TrustFlag]
    ev_eur: Decimal
    eligibility: Eligibility            # QUALIFYING | OVER_CAP_BAND | HARD_REJECT (§5.8)
    purchase_eligible: bool             # False ⇔ any ALERT_ONLY_FLAGS present
    gate_failures: list[str]            # reasons; non-empty ⇔ HARD_REJECT
    auto_buy_eligible: bool

    @field_serializer("trust_flags")
    def _sorted_trust_flags(self, v: set[TrustFlag]) -> list[str]:
        return sorted(f.value for f in v)


class StoppingSnapshot(BaseModel):      # monitor-mode receipt annotation (§5.7)
    p_better: Decimal | None = None
    horizon: int
    theta: Decimal
    n_obs: int


class Ask(BaseModel):
    id: str
    hunt_id: str
    tick: int
    kind: AskKind                       # GRAY_ROUTE (E2) | OVER_CAP (E3)
    quote: RouteQuote
    comparison_landed_eur: Decimal | None = None   # best non-gray alternative
    quote_hash: str                     # sha256(canonical_json(quote)) — approval binds to it
    narrative: str                      # LLM prose, ALL untrusted strings injected (§7.4)
    status: Literal["PENDING", "APPROVED", "DECLINED", "CONSUMED"]
    # Approval: quote-exact, single-use, consumed atomically at execution (§6.3 inv. 3/7).


class Order(BaseModel):
    hunt_id: str
    tick: int
    quote: RouteQuote
    state: OrderState
    refund_at_tick: int | None = None
    delivery_at_tick: int | None = None


class Hunt(BaseModel):
    id: str
    brief: Brief                        # never None — IntakeSession gates creation (§7.1)
    mandate: Mandate
    status: HuntStatus
    start_tick: int
    matched_product: str | None = None  # resolved style_code the hunt targets
    history_best: list[Decimal] = []    # per-tick best QUALIFYING landed (§5.7)
    history_best_any: list[Decimal] = []  # per-tick best over QUALIFYING ∪ OVER_CAP_BAND (§5.9 E3)
    interruptions: list[tuple[int, str, str]] = []  # (tick, listing_id, kind∈{ALERT,GRAY_ROUTE,OVER_CAP})
    pending_ask: Ask | None = None      # ≤ 1 at any time; clock paused while pending
    declined_asks: dict[str, Decimal] = {}  # key "{listing_id}:{ask_kind}" → landed at decline;
                                        # re-ask only on REASK_IMPROVEMENT (§5.9)
    orders: list[Order] = []            # append-only ledger; ≤1 in PLACED/CONFIRMED (inv. 8)
    excluded_listings: set[str] = set() # merchant-cancelled listings — never re-bought this hunt

    @field_serializer("excluded_listings")
    def _sorted_excluded(self, v: set[str]) -> list[str]:
        return sorted(v)


class Receipt(BaseModel):               # one JSONL row; append-only
    id: str
    hunt_id: str
    tick: int
    action: Action
    decided_by: DecidedBy
    escalation_tier: str | None = None  # "E0".."E5" (§5.9)
    chosen: Evaluation | None = None    # the acted-on quote
    considered: list[Evaluation] = []   # top-5 by landed among eligibility ≠ HARD_REJECT,
                                        # ties broken (listing_id, route kind, middleman_id)
    reasons: list[str] = []             # ordered, machine-generated strings
    stopping: StoppingSnapshot | None = None   # monitor only
