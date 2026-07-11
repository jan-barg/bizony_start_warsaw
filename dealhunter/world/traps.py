"""Adversarial market injection with a complete ground-truth log (§4.5)."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ..core.config import Constants
from ..core.enums import AccessTier, Currency, Geo
from ..core.ids import coupon_id, geo_promo_id
from ..core.models import (
    ColorwayAlias,
    Coupon,
    FxRate,
    GeoPromo,
    Listing,
    Middleman,
    PriceEvent,
    Product,
    TrapRecord,
    Vendor,
    WhitelistEntry,
)
from ..core.rng import rng
from .geo import quantize_sticker


def _take(stream, rows: list, count: int) -> list:
    if not rows or count <= 0:
        return []
    shuffled = list(rows)
    stream.shuffle(shuffled)
    return [shuffled[index % len(shuffled)] for index in range(count)]


def _rate(currency: Currency, fx: list[FxRate]) -> Decimal:
    if currency is Currency.EUR:
        return Decimal("1")
    pair = f"EUR{currency.value}"
    return next(row.rate for row in fx if row.tick == 0 and row.pair == pair)


def _vendor_sticker(eur: Decimal, vendor: Vendor, fx: list[FxRate]) -> Decimal:
    return quantize_sticker(eur * _rate(vendor.currency, fx), vendor.currency)


def _record(
    trap_type: str,
    listing: Listing | None,
    vendor: Vendor | None,
    ticks: tuple[int, int] | None,
    explanation: str,
    correct_behavior: str,
) -> TrapRecord:
    return TrapRecord(
        trap_type=trap_type,
        listing_id=listing.id if listing else None,
        vendor_id=vendor.id if vendor else None,
        ticks=ticks,
        explanation=explanation,
        correct_behavior=correct_behavior,
    )


def inject_traps(
    seed: int,
    cfg: Constants,
    products: list[Product],
    aliases: list[ColorwayAlias],
    vendors: list[Vendor],
    whitelist: list[WhitelistEntry],
    middlemen: list[Middleman],
    listings: list[Listing],
    events: list[PriceEvent],
    coupons: list[Coupon],
    fx: list[FxRate],
    geo_promos: list[GeoPromo],
) -> tuple[list[Vendor], list[Listing], list[PriceEvent], list[Coupon], list[GeoPromo], list[TrapRecord]]:
    """Plant configured traps using only the single ``("traps",)`` stream."""
    stream = rng(seed, "traps")
    vendors = [vendor.model_copy(deep=True) for vendor in vendors]
    listings = [listing.model_copy(deep=True) for listing in listings]
    events = [event.model_copy(deep=True) for event in events]
    coupons = [coupon.model_copy(deep=True) for coupon in coupons]
    geo_promos = [promo.model_copy(deep=True) for promo in geo_promos]
    products_by_id = {product.id: product for product in products}
    vendors_by_id = {vendor.id: vendor for vendor in vendors}
    whitelist_ids = {row.vendor_id for row in whitelist}
    events_by_listing: dict[str, list[PriceEvent]] = defaultdict(list)
    for event in events:
        events_by_listing[event.listing_id].append(event)
    for rows in events_by_listing.values():
        rows.sort(key=lambda row: row.tick)
    records: list[TrapRecord] = []
    whole_horizon = (0, cfg.HORIZON - 1)

    # Bait listings and observable bad-actor signals.
    bait_pool = [row for row in listings if row.vendor_id not in whitelist_ids]
    for listing in _take(stream, bait_pool, cfg.TRAP_COUNTS.get("bait", 0)):
        vendor = vendors_by_id[listing.vendor_id]
        product = products_by_id[listing.true_product_id]
        listing.is_bait = True
        vendor.is_fraudulent = True
        vendor.domain_age_days = stream.randint(5, 30)
        vendor.review_count = stream.randint(1, 8)
        vendor.reviews_last_30d = vendor.review_count
        vendor.return_days = 0
        ratio = Decimal(stream.randint(55, 65)) / 100
        sticker = _vendor_sticker(product.fair_price_eur * ratio, vendor, fx)
        for event in events_by_listing[listing.id]:
            event.sticker = sticker
            event.on_sale = True
        records.append(_record(
            "bait", listing, vendor, whole_horizon,
            f"Sticker is {ratio * 100}% of fair value at a young, review-thin, no-returns vendor.",
            "Reject through observable trust signals; never use the hidden bait label.",
        ))

    # Fake anchors claim a price materially above anything ever charged.
    for listing in _take(stream, listings, cfg.TRAP_COUNTS.get("fake_anchor", 0)):
        rows = events_by_listing[listing.id]
        actual_max = max(row.sticker for row in rows)
        multiplier = Decimal(stream.randint(135, 160)) / 100
        fake = quantize_sticker(actual_max * multiplier, vendors_by_id[listing.vendor_id].currency)
        for row in rows:
            row.was_price_shown = fake
        records.append(_record(
            "fake_anchor", listing, vendors_by_id[listing.vendor_id], whole_horizon,
            f"The displayed anchor {fake} was never charged; actual observed maximum is {actual_max}.",
            "Ignore the vendor anchor and use SolidHunt's own observed landed-price history.",
        ))

    # Anchor reset: a short spike followed by a cosmetic discount.
    anchor_candidates = [row for row in listings if cfg.HORIZON >= 6]
    for listing in _take(stream, anchor_candidates, cfg.TRAP_COUNTS.get("anchor_reset", 0)):
        rows = events_by_listing[listing.id]
        start = stream.randint(1, cfg.HORIZON - 5)
        pre = rows[start - 1].sticker
        currency = vendors_by_id[listing.vendor_id].currency
        spike = quantize_sticker(pre * Decimal("1.20"), currency)
        after = quantize_sticker(pre * Decimal("0.99"), currency)
        for tick in range(start, start + 3):
            rows[tick].sticker = spike
            rows[tick].was_price_shown = spike
        rows[start + 3].sticker = after
        rows[start + 3].was_price_shown = spike
        records.append(_record(
            "anchor_reset", listing, vendors_by_id[listing.vendor_id], (start, start + 3),
            "A three-day 20% spike resets the claimed anchor, followed by a 1% cosmetic discount.",
            "Treat the claimed discount as irrelevant; compare against observed qualifying landed prices.",
        ))

    foreign_direct = [
        row for row in listings
        if vendors_by_id[row.vendor_id].geo in {Geo.UK, Geo.US, Geo.JP}
        and Geo.PL in vendors_by_id[row.vendor_id].ships_to
    ]
    for listing in _take(stream, foreign_direct, cfg.TRAP_COUNTS.get("landed_inversion", 0)):
        vendor = vendors_by_id[listing.vendor_id]
        product = products_by_id[listing.true_product_id]
        sticker = _vendor_sticker(product.fair_price_eur * Decimal("0.78"), vendor, fx)
        for row in events_by_listing[listing.id]:
            row.sticker = sticker
        records.append(_record(
            "landed_inversion", listing, vendor, whole_horizon,
            "The foreign sticker is deliberately lowest before freight, import duty, VAT, and handling.",
            "Rank complete landed route quotes, not sticker-plus-shipping shortcuts.",
        ))

    # Current-law €150 cliff pair. In the compact preset the siblings may be different catalog rows.
    us_rows = [row for row in listings if vendors_by_id[row.vendor_id].geo is Geo.US]
    cliff_count = cfg.TRAP_COUNTS.get("customs_cliff_pair", 0)
    for pair_index in range(cliff_count):
        selected = _take(stream, us_rows, 2)
        if not selected:
            break
        low, high = selected[0], selected[-1]
        for listing, intrinsic in ((low, Decimal("146.00")), (high, Decimal("154.00"))):
            vendor = vendors_by_id[listing.vendor_id]
            for row in events_by_listing[listing.id]:
                row.sticker = _vendor_sticker(intrinsic, vendor, fx)
        records.append(_record(
            "customs_cliff_pair", low, vendors_by_id[low.vendor_id], whole_horizon,
            f"Paired with {high.id}: intrinsic values straddle €150 (€146 versus €154).",
            "Apply €3 low-value duty at €146 and full HS duty above €150 before comparing landed totals.",
        ))

    uk_rows = [row for row in listings if vendors_by_id[row.vendor_id].geo is Geo.UK]
    for listing in _take(stream, uk_rows, cfg.TRAP_COUNTS.get("fta_origin", 0)):
        vendor = vendors_by_id[listing.vendor_id]
        product = products_by_id[listing.true_product_id]
        for row in events_by_listing[listing.id]:
            row.sticker = _vendor_sticker(Decimal("165.00"), vendor, fx)
        records.append(_record(
            "fta_origin", listing, vendor, whole_horizon,
            f"Dispatched from the UK, but manufactured in {product.origin_country}; intrinsic value exceeds €150.",
            "Use manufacturing origin, not dispatch country: full footwear duty applies.",
        ))

    impersonator_pool = [row for row in listings if row.vendor_id not in whitelist_ids]
    for listing in _take(stream, impersonator_pool, cfg.TRAP_COUNTS.get("whitelist_impersonator", 0)):
        vendor = vendors_by_id[listing.vendor_id]
        vendor.domain = stream.choice(["adidass.com", "nikke.com", "newbalancce.com"])
        vendor.name = f"Official Outlet {vendor.name}"
        vendor.is_fraudulent = True
        product = products_by_id[listing.true_product_id]
        for row in events_by_listing[listing.id]:
            row.sticker = _vendor_sticker(product.fair_price_eur * Decimal("0.70"), vendor, fx)
        records.append(_record(
            "whitelist_impersonator", listing, vendor, whole_horizon,
            f"Typosquatted domain {vendor.domain} resembles an official domain but is not an exact whitelist match.",
            "Do not whitelist; emit impersonation suspicion and cap trust.",
        ))

    kids_pool = [row for row in listings if products_by_id[row.true_product_id].is_kids_version_of]
    for listing in _take(stream, kids_pool, cfg.TRAP_COUNTS.get("gs_kids", 0)):
        product = products_by_id[listing.true_product_id]
        adult = products_by_id[product_id] if (product_id := f"p_{product.is_kids_version_of}") in products_by_id else product
        listing.raw_title = (
            f"{adult.brand} {adult.model} {adult.colorway_name} GS size 43 special price"
        )
        listing.size_eu = Decimal("43")
        records.append(_record(
            "gs_kids", listing, vendors_by_id[listing.vendor_id], whole_horizon,
            "A kids twin is presented with an adult-ambiguous bare size and the lower kids price.",
            "Resolve the kids twin and enforce the size/kids gates before purchase.",
        ))

    adult_pool = [row for row in listings if not products_by_id[row.true_product_id].is_kids_version_of]
    alias_by_code = defaultdict(list)
    for alias in aliases:
        alias_by_code[alias.style_code].append(alias.alias)
    color_count = cfg.TRAP_COUNTS.get("colorway", 0)
    for index, listing in enumerate(_take(stream, adult_pool, color_count)):
        product = products_by_id[listing.true_product_id]
        same_model = [p for p in products if p.model == product.model and p.id != product.id and not p.is_kids_version_of]
        conflict = stream.choice(same_model) if same_model else stream.choice(products)
        if index % 2 == 0:
            listing.raw_title = f"{product.brand} {product.model} {listing.size_eu} new release"
            explanation = f"The true {product.colorway_name} listing omits its colorway while resembling another variant."
        else:
            nickname = (alias_by_code.get(conflict.style_code) or [conflict.colorway_name])[0]
            listing.raw_title = f"{product.brand} {product.model} {nickname} {product.style_code} EU {listing.size_eu}"
            explanation = f"Nickname {nickname!r} contradicts embedded style code {product.style_code}."
        records.append(_record(
            "colorway", listing, vendors_by_id[listing.vendor_id], whole_horizon,
            explanation,
            "Flag unconfirmed/conflicting colorway evidence and keep the quote out of every buy path.",
        ))

    coupon_count = cfg.TRAP_COUNTS.get("coupon", 0)
    coupon_targets = _take(stream, listings, coupon_count)
    for index, listing in enumerate(coupon_targets):
        rows = events_by_listing[listing.id]
        tick = min(cfg.HORIZON - 1, max(1, cfg.HORIZON // 3 + index))
        cid = coupon_id(listing.id, tick)
        if index % 2 == 0:
            coupon = Coupon(
                id=cid, code="JUSTEXPIRED", kind="pct", value=Decimal("15"),
                min_basket=None, excludes_sale=False, valid_from=max(0, tick - 5), valid_to=tick - 1,
            )
            reason = "The coupon expired exactly one tick before it remains advertised."
            behavior = "Omit the coupon and record coupon_invalid:expired."
        else:
            coupon = Coupon(
                id=cid, code="NOSALE", kind="pct", value=Decimal("15"),
                min_basket=None, excludes_sale=True, valid_from=max(0, tick - 1), valid_to=min(cfg.HORIZON - 1, tick + 5),
            )
            rows[tick].on_sale = True
            reason = "An excludes-sale coupon is attached to a row explicitly marked on_sale."
            behavior = "Omit the coupon and record coupon_invalid:excludes_sale."
        coupons = [existing for existing in coupons if existing.id != cid]
        coupons.append(coupon)
        rows[tick].coupon_id = cid
        records.append(_record("coupon", listing, vendors_by_id[listing.vendor_id], (tick, tick), reason, behavior))

    for listing in _take(stream, listings, cfg.TRAP_COUNTS.get("stock_race", 0)):
        rows = events_by_listing[listing.id]
        tick = stream.randint(1, max(1, cfg.HORIZON - 2))
        currency = vendors_by_id[listing.vendor_id].currency
        rows[tick].sticker = quantize_sticker(rows[tick].sticker * Decimal("0.80"), currency)
        rows[tick].stock = max(1, rows[tick].stock)
        rows[min(cfg.HORIZON - 1, tick + 1)].stock = 0
        records.append(_record(
            "stock_race", listing, vendors_by_id[listing.vendor_id], (tick, min(cfg.HORIZON - 1, tick + 1)),
            "Stock disappears one tick after the scripted price crossing.",
            "Re-read current stock at execution and never buy the following zero-stock row.",
        ))

    eligible_geo = [
        row for row in listings
        if vendors_by_id[row.vendor_id].geo in {Geo.JP, Geo.US, Geo.UK}
        and any(mm.located_in == vendors_by_id[row.vendor_id].geo for mm in middlemen)
    ]

    geo_used: set[str] = set()

    def add_geo_traps(trap_type: str, count: int, tier: AccessTier, ratio: Decimal, p_cancel: Decimal | None, message: str, behavior: str) -> None:
        nonlocal geo_promos
        available = [listing for listing in eligible_geo if listing.id not in geo_used]
        for listing in _take(stream, available or eligible_geo, count):
            geo_used.add(listing.id)
            vendor = vendors_by_id[listing.vendor_id]
            rows = events_by_listing[listing.id]
            start = stream.randint(0, max(0, cfg.HORIZON - 8))
            end = min(cfg.HORIZON - 1, start + stream.randint(4, 8))
            sticker = quantize_sticker(rows[start].sticker * ratio, vendor.currency)
            geo_promos = [promo for promo in geo_promos if promo.listing_id != listing.id]
            geo_promos.append(GeoPromo(
                id=geo_promo_id(listing.id, vendor.geo.value),
                listing_id=listing.id,
                viewer_geo=vendor.geo,
                promo_sticker=sticker,
                from_tick=start,
                to_tick=end,
                access_tier=tier,
                p_cancel=p_cancel,
            ))
            records.append(_record(trap_type, listing, vendor, (start, end), message, behavior))

    add_geo_traps(
        "fake_geo_exclusive", cfg.TRAP_COUNTS.get("fake_geo_exclusive", 0),
        AccessTier.STOREFRONT, Decimal("1.03"), None,
        "A loudly advertised foreign exclusive is actually priced above the ordinary base quote.",
        "Compare landed totals and ignore scarcity theater.",
    )
    add_geo_traps(
        "verified_local", cfg.TRAP_COUNTS.get("verified_local", 0),
        AccessTier.VERIFIED_LOCAL, Decimal("0.55"), None,
        "A deep local discount requires residency verification and only looks orderable.",
        "Treat VERIFIED_LOCAL as unattainable and never enumerate a purchase route.",
    )
    add_geo_traps(
        "net_negative_ip_gated", cfg.TRAP_COUNTS.get("net_negative_ip_gated", 0),
        AccessTier.IP_GATED, Decimal("0.66"), Decimal("0.35"),
        "The lowest IP-gated sticker carries high cancellation risk and a forwarding delay sized to defeat a short deadline.",
        "Apply the tactics mandate, full landed cost, ETA, and cancellation-risk EV before asking or buying.",
    )
    add_geo_traps(
        "genuine_geo", cfg.TRAP_COUNTS.get("genuine_geo", 0),
        AccessTier.IP_GATED, Decimal("0.52"), Decimal("0.08"),
        "A genuine foreign promo remains competitive after forwarding and Polish import charges.",
        "Capture it only when geo tactics are ALLOWed or a quote-exact gray-route ask is approved.",
    )

    return (
        sorted(vendors, key=lambda row: row.id),
        sorted(listings, key=lambda row: row.id),
        sorted(events, key=lambda row: (row.listing_id, row.tick)),
        sorted(coupons, key=lambda row: row.id),
        sorted(geo_promos, key=lambda row: row.id),
        records,
    )
