"""Trust score and expected-value model (spec §5.6).
Owner: feat/engine (Work Order 2). Signatures are frozen; bodies are not.

Normative reminders:
- Whitelist exact-domain ⇒ 1.00 short-circuit; impersonation similarity ≥ 0.80
  ⇒ IMPERSONATION_SUSPECTED and final score capped at 0.15.
- EV uses ONE common reference — the cap: savings = cap − landed. Never score a
  candidate against its cheapest rival. Selection among qualifying = argmax EV.
- Engine code must NOT read hidden labels (is_fraudulent etc.) — observables only.
"""
from __future__ import annotations

from decimal import Decimal
from statistics import median

from rapidfuzz.fuzz import ratio

from ..core.config import Constants
from ..core.enums import Currency, TrustFlag
from ..core.money import q2, to_eur
from ..core.models import RouteQuote, Vendor, World


def _normalized_domain(domain: str) -> str:
    return domain.casefold().removeprefix("www.").rstrip(".")


def _product_style_from_listing_id(listing_id: str, world: World) -> str:
    matches = [p.style_code for p in world.products if listing_id.endswith(f"_{p.style_code}")]
    if len(matches) != 1:
        raise ValueError(f"listing id does not identify one style code: {listing_id}")
    return matches[0]


def _base_goods_eur(listing_id: str, tick: int, world: World) -> Decimal | None:
    listings = [item for item in world.listings if item.id == listing_id]
    if len(listings) != 1:
        return None
    vendors = [item for item in world.vendors if item.id == listings[0].vendor_id]
    events = [
        item for item in world.price_events
        if item.listing_id == listing_id and item.tick == tick
    ]
    if len(vendors) != 1 or len(events) != 1:
        return None
    vendor = vendors[0]
    if vendor.currency == Currency.EUR:
        rate = Decimal("1")
    else:
        pair = f"EUR{vendor.currency.value}"
        rates = [item.rate for item in world.fx if item.tick == tick and item.pair == pair]
        if len(rates) != 1:
            return None
        rate = rates[0]
    return to_eur(events[0].sticker, vendor.currency, rate)


def _market_median(quote: RouteQuote, world: World) -> Decimal | None:
    style_code = _product_style_from_listing_id(quote.listing_id, world)
    values = [
        value
        for listing in world.listings
        if listing.id.endswith(f"_{style_code}")
        if (value := _base_goods_eur(listing.id, quote.tick, world)) is not None
    ]
    return median(values) if values else None


def trust_score(vendor: Vendor, quote: RouteQuote, world: World, cfg: Constants) -> tuple[Decimal, set[TrustFlag]]:
    """Score a vendor/route using observables only."""
    domain = _normalized_domain(vendor.domain)
    whitelist_domains = {_normalized_domain(entry.domain) for entry in world.whitelist}
    if domain in whitelist_domains:
        return Decimal("1.00"), set()

    flags: set[TrustFlag] = set()
    impersonation = any(
        Decimal(str(ratio(domain, trusted))) / Decimal("100") >= Decimal(str(cfg.IMPERSONATION_SIM))
        for trusted in whitelist_domains
    )
    if impersonation:
        flags.add(TrustFlag.IMPERSONATION_SUSPECTED)

    score = Decimal("0.50")
    score += Decimal("0.10") * (vendor.review_avg - Decimal("3.0"))
    volume = min(Decimal(vendor.review_count + 1).log10(), Decimal("3"))
    score += Decimal("0.04") * volume

    if vendor.domain_age_days >= 3 * 365:
        score += Decimal("0.05")
    elif vendor.domain_age_days < 90:
        score -= Decimal("0.15")
        flags.add(TrustFlag.YOUNG_DOMAIN)

    if vendor.return_days >= 14:
        score += Decimal("0.05")
    elif vendor.return_days == 0:
        score -= Decimal("0.10")
        flags.add(TrustFlag.NO_RETURNS)

    if (
        vendor.domain_age_days < 180
        and vendor.reviews_last_30d > Decimal("0.5") * vendor.review_count
    ):
        score -= Decimal("0.20")
        flags.add(TrustFlag.REVIEW_BURST)

    market_median = _market_median(quote, world)
    effective_goods = sum(
        (line.amount_eur for line in quote.line_items if line.code in {"GOODS", "COUPON"}),
        Decimal("0"),
    )
    if market_median is not None and effective_goods < cfg.PRICE_TOO_GOOD_RATIO * market_median:
        score -= Decimal("0.25")
        flags.add(TrustFlag.PRICE_TOO_GOOD)

    if quote.kind == "middleman":
        score -= cfg.MIDDLEMAN_HAIRCUT

    score = min(max(score, Decimal("0.02")), Decimal("0.99"))
    if impersonation:
        score = min(score, cfg.IMPERSONATION_CAP)
    return q2(score), flags


def expected_value(
    quote: RouteQuote,
    trust: Decimal,
    cap: Decimal,
    deadline_ticks_left: int | None,
    cfg: Constants,
) -> Decimal:
    savings = cap - quote.landed_eur
    loss = quote.landed_eur + cfg.HASSLE_EUR
    deadline_exposure = Decimal("0")
    if deadline_ticks_left is not None and deadline_ticks_left - quote.eta_ticks < 3:
        deadline_exposure = cfg.DEADLINE_EXPOSURE_EUR
    cancellation_cost = quote.p_cancel_est * (
        cfg.CANCEL_HASSLE_EUR + deadline_exposure
    )
    return q2(
        trust * savings
        - (Decimal("1") - trust) * loss
        - cancellation_cost
    )
