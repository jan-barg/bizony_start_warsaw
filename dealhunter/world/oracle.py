"""Omniscient ground-truth best buys for evaluation only (§4.6)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..core.config import Constants
from ..core.enums import AccessTier, Carrier, Condition, Currency, GEO_TO_ZONE, Geo, HsCategory, Ruleset, Zone
from ..core.models import Coupon, GeoPromo, Middleman, OracleAnswer, OracleBest, PriceEvent, Product, Vendor, World
from ..core.money import q2
from ..core.rng import rng


@dataclass(frozen=True)
class HuntTemplate:
    key: str
    product_id: str
    size_eu: Decimal
    cap_eur: Decimal
    deadline_tick: int | None


def _fx(world: World, tick: int, currency: Currency) -> Decimal:
    if currency is Currency.EUR:
        return Decimal("1")
    pair = f"EUR{currency.value}"
    return next(row.rate for row in world.fx if row.tick == tick and row.pair == pair)


def _coupon_discount(goods: Decimal, event: PriceEvent, coupon: Coupon | None) -> Decimal:
    if coupon is None or not (coupon.valid_from <= event.tick <= coupon.valid_to):
        return Decimal("0")
    if coupon.min_basket is not None and event.sticker < coupon.min_basket:
        return Decimal("0")
    if coupon.excludes_sale and event.on_sale:
        return Decimal("0")
    if coupon.kind == "pct":
        return -q2(goods * coupon.value / Decimal("100"))
    return Decimal("NaN")  # flat coupons are converted with FX by the caller


def _import_lines(
    cfg: Constants,
    zone: Zone,
    intrinsic: Decimal,
    transport: Decimal,
    product: Product,
    ioss: bool,
    carrier: Carrier,
) -> list[Decimal]:
    if zone is Zone.EU:
        return []
    if intrinsic <= cfg.LOW_VALUE_EUR:
        if ioss:
            return []
        duty = cfg.DUTY_FLAT_EUR if cfg.RULESET is Ruleset.EU_2026_07 else Decimal("0")
        values = [q2(duty)] if duty else []
        values.append(q2(cfg.VAT_PL * (intrinsic + transport + duty)))
        values.append(cfg.HANDLING_POSTAL_EUR if carrier is Carrier.POSTAL else cfg.HANDLING_COURIER_EUR)
        return values
    customs_value = intrinsic + transport
    preferential = (zone is Zone.UK and product.origin_country == "GB") or (zone is Zone.JP and product.origin_country == "JP")
    duty = Decimal("0") if preferential else q2(cfg.HS_RATE[product.hs_category] * customs_value)
    values = [] if duty == 0 else [duty]
    values.append(q2(cfg.VAT_PL * (customs_value + duty)))
    values.append(cfg.HANDLING_POSTAL_EUR if carrier is Carrier.POSTAL else cfg.HANDLING_COURIER_EUR)
    return values


def _shipping_to_pl(vendor: Vendor) -> tuple[Decimal, Carrier]:
    if Geo.PL.value in vendor.shipping_table:
        return vendor.shipping_table[Geo.PL.value]
    return vendor.shipping_table[Zone.EU.value]


def _landed(
    world: World,
    cfg: Constants,
    listing_id: str,
    event: PriceEvent,
    vendor: Vendor,
    product: Product,
    sticker: Decimal,
    route_kind: str,
    middleman: Middleman | None,
) -> Decimal:
    rate = _fx(world, event.tick, vendor.currency)
    goods = q2(sticker / rate)
    coupons = {coupon.id: coupon for coupon in world.coupons}
    coupon = coupons.get(event.coupon_id) if event.coupon_id else None
    discount = _coupon_discount(goods, event, coupon)
    if discount.is_nan():
        discount = -q2(coupon.value / rate) if coupon else Decimal("0")
    intrinsic = goods + discount
    lines = [goods, discount] if discount else [goods]
    zone = GEO_TO_ZONE[vendor.geo]

    if route_kind == "direct":
        ship_ccy, carrier = _shipping_to_pl(vendor)
        ship = q2(ship_ccy / rate)
        lines.append(ship)
        lines.extend(_import_lines(cfg, zone, intrinsic, ship, product, vendor.ioss_registered, carrier))
    else:
        assert middleman is not None
        domestic = q2(vendor.domestic_shipping[0] / rate)
        flat = q2(middleman.fee_flat_eur)
        percent = q2(middleman.fee_pct * intrinsic)
        international = next(price for max_kg, price in middleman.intl_shipping_eur if product.weight_kg <= max_kg)
        international = q2(international)
        lines.extend([domestic, flat, percent, international])
        lines.extend(
            _import_lines(
                cfg,
                zone,
                intrinsic,
                domestic + international,
                product,
                False,
                middleman.intl_carrier,
            )
        )
    return sum(lines, Decimal("0"))


def _templates(world: World, cfg: Constants) -> list[HuntTemplate]:
    stream = rng(world.seed, "eval", world.seed)
    products = {product.id: product for product in world.products}
    vendors = {vendor.id: vendor for vendor in world.vendors}
    event_rows: dict[str, list[PriceEvent]] = {}
    for event in world.price_events:
        event_rows.setdefault(event.listing_id, []).append(event)

    def viable_options(cap_ratio: Decimal, deadline: int | None) -> list[tuple[Product, Decimal]]:
        options: set[tuple[str, Decimal]] = set()
        for listing in world.listings:
            product = products[listing.true_product_id]
            vendor = vendors[listing.vendor_id]
            if (
                product.is_kids_version_of is not None
                or listing.condition is not Condition.NEW
                or listing.is_bait
                or listing.is_counterfeit
                or Geo.PL not in vendor.ships_to
            ):
                continue
            cap = q2(product.fair_price_eur * cap_ratio)
            eta = cfg.ETA_DIRECT[GEO_TO_ZONE[vendor.geo]]
            for event in event_rows[listing.id]:
                if event.stock <= 0 or (deadline is not None and event.tick + eta > deadline):
                    continue
                total = _landed(world, cfg, listing.id, event, vendor, product, event.sticker, "direct", None)
                if total <= cap:
                    options.add((product.id, listing.size_eu))
                    break
        return [(products[product_id], size) for product_id, size in sorted(options)]

    templates: list[HuntTemplate] = []
    for index in range(cfg.EVAL_TEMPLATES_PER_SEED):
        cap_ratio = Decimal(stream.randint(85, 110)) / 100
        deadline = stream.choice([None, 10, 25])
        options = viable_options(cap_ratio, deadline)
        if not options:
            cap_ratio = Decimal("1.10")
            options = viable_options(cap_ratio, deadline)
        if not options:
            deadline = None
            options = viable_options(cap_ratio, deadline)
        if not options:
            raise ValueError("world generation produced no legitimate oracle template")
        product, size = stream.choice(options)
        cap = q2(product.fair_price_eur * cap_ratio)
        key = f"h_{world.seed}_{index + 1}:{product.style_code}:EU{size}:cap{cap}:deadline{deadline or 'none'}"
        templates.append(HuntTemplate(key, product.id, size, cap, deadline))
    return templates


def _best(world: World, cfg: Constants, template: HuntTemplate, allow_gray: bool) -> OracleBest | None:
    products = {product.id: product for product in world.products}
    vendors = {vendor.id: vendor for vendor in world.vendors}
    listings = {listing.id: listing for listing in world.listings}
    events = {(event.listing_id, event.tick): event for event in world.price_events}
    promos_by_listing: dict[str, list[GeoPromo]] = {}
    for promo in world.geo_promos:
        promos_by_listing.setdefault(promo.listing_id, []).append(promo)
    candidates: list[tuple[Decimal, int, str, str, str, OracleBest]] = []

    for listing in world.listings:
        if (
            listing.true_product_id != template.product_id
            or listing.condition is not Condition.NEW
            or listing.size_eu != template.size_eu
            or listing.is_bait
            or listing.is_counterfeit
        ):
            continue
        product = products[listing.true_product_id]
        if product.is_kids_version_of is not None:
            continue
        vendor = vendors[listing.vendor_id]
        lane_middlemen = sorted(
            [middleman for middleman in world.middlemen if middleman.located_in is vendor.geo and Geo.PL in middleman.forwards_to],
            key=lambda row: row.id,
        )
        for tick in range(world.horizon):
            event = events[(listing.id, tick)]
            if event.stock <= 0:
                continue
            route_inputs: list[tuple[Decimal, AccessTier, str, Middleman | None, int]] = []
            if Geo.PL in vendor.ships_to:
                eta = cfg.ETA_DIRECT[GEO_TO_ZONE[vendor.geo]]
                route_inputs.append((event.sticker, AccessTier.BASE, "direct", None, eta))
            else:
                for middleman in lane_middlemen:
                    route_inputs.append((event.sticker, AccessTier.BASE, "middleman", middleman, cfg.ETA_DOMESTIC_LEG + middleman.extra_ticks))
            for promo in promos_by_listing.get(listing.id, []):
                if not (promo.from_tick <= tick <= promo.to_tick):
                    continue
                if promo.access_tier is AccessTier.VERIFIED_LOCAL:
                    continue
                if promo.access_tier is AccessTier.IP_GATED and not allow_gray:
                    continue
                for middleman in lane_middlemen:
                    route_inputs.append((promo.promo_sticker, promo.access_tier, "middleman", middleman, cfg.ETA_DOMESTIC_LEG + middleman.extra_ticks))

            for sticker, _tier, kind, middleman, eta in route_inputs:
                if template.deadline_tick is not None and tick + eta > template.deadline_tick:
                    continue
                total = _landed(world, cfg, listing.id, event, vendor, product, sticker, kind, middleman)
                if total > template.cap_eur:
                    continue
                answer = OracleBest(
                    tick=tick,
                    listing_id=listing.id,
                    route_kind=kind,
                    middleman_id=middleman.id if middleman else None,
                    landed_eur=total,
                )
                candidates.append((total, tick, listing.id, kind, middleman.id if middleman else "", answer))
    return min(candidates, key=lambda row: row[:-1])[-1] if candidates else None


def compute_oracle(world: World, cfg: Constants) -> dict[str, OracleAnswer]:
    """Return policy-consistent omniscient answers without importing engine code."""
    answers: dict[str, OracleAnswer] = {}
    for template in _templates(world, cfg):
        answers[template.key] = OracleAnswer(
            allow=_best(world, cfg, template, allow_gray=True),
            never=_best(world, cfg, template, allow_gray=False),
        )
    return answers
