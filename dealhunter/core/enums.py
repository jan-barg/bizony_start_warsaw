"""Every enum in the system — implementation-spec.md §3.1. Frozen after Stage 0."""
from enum import StrEnum


class Currency(StrEnum):
    EUR = "EUR"
    PLN = "PLN"
    GBP = "GBP"
    USD = "USD"
    JPY = "JPY"


class Geo(StrEnum):
    """Vendor / observation geos."""
    PL = "PL"
    DE = "DE"
    NL = "NL"
    FR = "FR"
    IT = "IT"
    ES = "ES"
    UK = "UK"
    US = "US"
    JP = "JP"


class Zone(StrEnum):
    """Customs dispatch zones."""
    EU = "EU"
    UK = "UK"
    US = "US"
    JP = "JP"


class HsCategory(StrEnum):
    FOOTWEAR_TEXTILE = "FOOTWEAR_TEXTILE"   # HS 6404 — 16.9%
    FOOTWEAR_LEATHER = "FOOTWEAR_LEATHER"   # HS 6403 — 8%


class Carrier(StrEnum):
    POSTAL = "POSTAL"
    COURIER = "COURIER"


class Condition(StrEnum):
    NEW = "NEW"
    USED = "USED"


class Channel(StrEnum):
    """Vendor sales channel — exclude_resellers gates on RESELLER (§5.8)."""
    OFFICIAL = "OFFICIAL"
    AUTHORIZED_RETAILER = "AUTHORIZED_RETAILER"
    RESELLER = "RESELLER"


class AccessTier(StrEnum):
    BASE = "BASE"
    STOREFRONT = "STOREFRONT"
    IP_GATED = "IP_GATED"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"


class Mode(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    MONITOR = "MONITOR"


class GeoArb(StrEnum):
    NEVER = "NEVER"
    ASK = "ASK"
    ALLOW = "ALLOW"


class Ruleset(StrEnum):
    """Customs law snapshot (§5.3). EU_2026_07 = post-reform default: flat €3
    low-value duty inside the VAT base. EU_2025_LEGACY = €150 de-minimis."""
    EU_2026_07 = "EU_2026_07"
    EU_2025_LEGACY = "EU_2025_LEGACY"


class Action(StrEnum):
    BUY = "BUY"
    ALERT = "ALERT"
    ASK = "ASK"
    HOLD = "HOLD"
    ESCALATE_NONE_FOUND = "ESCALATE_NONE_FOUND"


class AskKind(StrEnum):
    GRAY_ROUTE = "GRAY_ROUTE"   # §8c geo trick — E2
    OVER_CAP = "OVER_CAP"       # §5.9 E3 — one-time cap extension


class DecidedBy(StrEnum):
    CODE = "CODE"
    LLM = "LLM"
    HUMAN = "HUMAN"


class Eligibility(StrEnum):
    """Evaluation status (§5.8)."""
    QUALIFYING = "QUALIFYING"
    OVER_CAP_BAND = "OVER_CAP_BAND"
    HARD_REJECT = "HARD_REJECT"


class IntakeStatus(StrEnum):
    NEEDS_INFO = "NEEDS_INFO"
    OK = "OK"


class HuntStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    RUNNING = "RUNNING"
    PENDING_ASK = "PENDING_ASK"
    PURCHASED = "PURCHASED"
    EXPIRED = "EXPIRED"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    REVOKED = "REVOKED"


class OrderState(StrEnum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    CANCELLED_BY_MERCHANT = "CANCELLED_BY_MERCHANT"
    REFUNDED = "REFUNDED"


class MatchFlag(StrEnum):
    KIDS_SIZING = "KIDS_SIZING"
    SIZE_AMBIGUOUS = "SIZE_AMBIGUOUS"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    COLORWAY_CONFLICT = "COLORWAY_CONFLICT"
    COLORWAY_UNCONFIRMED = "COLORWAY_UNCONFIRMED"
    NAME_NEAR_MISS = "NAME_NEAR_MISS"
    BRAND_CODE_CONFLICT = "BRAND_CODE_CONFLICT"
    CONDITION_MISMATCH = "CONDITION_MISMATCH"
    LLM_MATCH_ONLY = "LLM_MATCH_ONLY"


class TrustFlag(StrEnum):
    IMPERSONATION_SUSPECTED = "IMPERSONATION_SUSPECTED"
    PRICE_TOO_GOOD = "PRICE_TOO_GOOD"
    REVIEW_BURST = "REVIEW_BURST"
    YOUNG_DOMAIN = "YOUNG_DOMAIN"
    NO_RETURNS = "NO_RETURNS"


GEO_TO_ZONE: dict[Geo, Zone] = {
    Geo.PL: Zone.EU,
    Geo.DE: Zone.EU,
    Geo.NL: Zone.EU,
    Geo.FR: Zone.EU,
    Geo.IT: Zone.EU,
    Geo.ES: Zone.EU,
    Geo.UK: Zone.UK,
    Geo.US: Zone.US,
    Geo.JP: Zone.JP,
}

# Alert-only flags: presence of any ⇒ purchase_eligible = False (§5.8).
ALERT_ONLY_FLAGS: frozenset[MatchFlag] = frozenset({
    MatchFlag.COLORWAY_CONFLICT,
    MatchFlag.COLORWAY_UNCONFIRMED,
    MatchFlag.LLM_MATCH_ONLY,
    MatchFlag.SIZE_AMBIGUOUS,
})
