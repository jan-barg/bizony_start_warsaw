"""Landed-cost assembly (spec §5.5).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Order of operations (normative): GOODS → COUPON (validity incl. on_sale flag)
→ shipping legs → MM fees (MM_PCT on GOODS+COUPON) → import_charges with
intrinsic = GOODS + COUPON and transport per §5.3. Line items quantized at
finalization; landed_eur = exact sum of quantized lines, never re-rounded.
"""
from __future__ import annotations

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import AccessTier, Currency, GEO_TO_ZONE, Geo
from ..core.money import q2, to_eur
from ..core.models import LineItem, RouteQuote, RouteSpec, World
from .customs import import_charges


def _one(items, predicate, description: str):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise ValueError(f"expected one {description}, found {len(matches)}")
    return matches[0]


def _line(code: str, label: str, amount: Decimal) -> LineItem:
    return LineItem(code=code, label=label, amount_eur=q2(amount))


def _product_for_listing(listing_id: str, world: World):
    """Resolve public product attributes from the deterministic listing id.

    The eval-only product label must never be read by engine code. Stage-0
    listing ids end in the canonical style code.
    """
    matches = [p for p in world.products if listing_id.endswith(f"_{p.style_code}")]
    if len(matches) != 1:
        raise ValueError(f"listing id does not identify one product: {listing_id}")
    return matches[0]


def _fx_rate(world: World, tick: int, currency: Currency) -> Decimal:
    if currency == Currency.EUR:
        return Decimal("1")
    pair = f"EUR{currency.value}"
    return _one(
        world.fx,
        lambda fx: fx.tick == tick and fx.pair == pair,
        f"FX rate {pair} at tick {tick}",
    ).rate


def _shipping_to_pl(vendor):
    for key in (Geo.PL.value, GEO_TO_ZONE[Geo.PL].value):
        if key in vendor.shipping_table:
            return vendor.shipping_table[key]
    raise ValueError(f"vendor {vendor.id} has no shipping rate to Poland")


def _coupon_line(coupon, sticker: Decimal, rate: Decimal) -> LineItem:
    discount_ccy = (
        sticker * coupon.value / Decimal("100")
        if coupon.kind == "pct"
        else coupon.value
    )
    return _line("COUPON", f"Coupon {coupon.code}", -q2(discount_ccy / rate))


def assemble(listing_id: str, route: RouteSpec, tick: int, world: World, cfg: Constants) -> RouteQuote:
    """Price one exact route and return its receipt-ready landed breakdown."""
    listing = _one(world.listings, lambda item: item.id == listing_id, f"listing {listing_id}")
    vendor = _one(world.vendors, lambda item: item.id == listing.vendor_id, "listing vendor")
    event = _one(
        world.price_events,
        lambda item: item.listing_id == listing_id and item.tick == tick,
        f"price event for {listing_id} at tick {tick}",
    )
    product = _product_for_listing(listing_id, world)
    rate = _fx_rate(world, tick, vendor.currency)
    notes: list[str] = []

    if route.promo_id is None:
        if route.access_tier != AccessTier.BASE:
            raise ValueError("non-base route must reference a promo")
        sticker = event.sticker
    else:
        promo = _one(world.geo_promos, lambda item: item.id == route.promo_id, "route promo")
        if promo.listing_id != listing_id:
            raise ValueError("promo does not belong to listing")
        if not promo.from_tick <= tick <= promo.to_tick:
            raise ValueError("promo is inactive at this tick")
        if promo.access_tier != route.access_tier or promo.viewer_geo != route.observation_geo:
            raise ValueError("route does not match promo visibility")
        sticker = promo.promo_sticker

    goods = to_eur(sticker, vendor.currency, rate)
    lines = [_line("GOODS", "Goods", goods)]

    if event.coupon_id is not None:
        coupon = _one(world.coupons, lambda item: item.id == event.coupon_id, "attached coupon")
        invalid_reason = None
        if tick < coupon.valid_from:
            invalid_reason = "not_yet_valid"
        elif tick > coupon.valid_to:
            invalid_reason = "expired"
        elif coupon.min_basket is not None and sticker < coupon.min_basket:
            invalid_reason = "min_basket"
        elif coupon.excludes_sale and event.on_sale:
            invalid_reason = "excludes_sale"
        if invalid_reason:
            notes.append(f"coupon_invalid:{invalid_reason}")
        else:
            lines.append(_coupon_line(coupon, sticker, rate))

    intrinsic = sum(
        line.amount_eur for line in lines if line.code in {"GOODS", "COUPON"}
    )

    if route.kind == "direct":
        if route.middleman_id is not None or route.access_tier != AccessTier.BASE:
            raise ValueError("direct routes must be ordinary base quotes")
        shipping_ccy, carrier = _shipping_to_pl(vendor)
        ship_direct = to_eur(shipping_ccy, vendor.currency, rate)
        lines.append(_line("SHIP_DIRECT", "Direct shipping to Poland", ship_direct))
        transport = ship_direct
        eta_ticks = cfg.ETA_DIRECT[GEO_TO_ZONE[vendor.geo]]
        ioss = vendor.ioss_registered
    else:
        if route.middleman_id is None:
            raise ValueError("middleman route requires middleman_id")
        middleman = _one(
            world.middlemen,
            lambda item: item.id == route.middleman_id,
            "route middleman",
        )
        if middleman.located_in != vendor.geo or Geo.PL not in middleman.forwards_to:
            raise ValueError("middleman lane cannot serve this vendor and destination")
        ship_dom = to_eur(vendor.domestic_shipping[0], vendor.currency, rate)
        lines.append(_line("SHIP_DOM", "Domestic shipping to forwarder", ship_dom))
        lines.append(_line("MM_FLAT", f"{middleman.name} flat fee", middleman.fee_flat_eur))
        lines.append(_line("MM_PCT", f"{middleman.name} percentage fee", middleman.fee_pct * intrinsic))
        bracket = next(
            (price for max_weight, price in middleman.intl_shipping_eur if product.weight_kg <= max_weight),
            None,
        )
        if bracket is None:
            raise ValueError(f"no middleman shipping bracket for {product.weight_kg} kg")
        ship_intl = q2(bracket)
        lines.append(_line("SHIP_INTL", "International forwarding", ship_intl))
        transport = ship_dom + ship_intl
        carrier = middleman.intl_carrier
        eta_ticks = cfg.ETA_DOMESTIC_LEG + middleman.extra_ticks
        ioss = False

    lines.extend(
        import_charges(
            cfg.RULESET,
            GEO_TO_ZONE[vendor.geo],
            intrinsic,
            transport,
            product.hs_category,
            product.origin_country,
            ioss,
            carrier,
            cfg,
        )
    )
    landed = sum((line.amount_eur for line in lines), Decimal("0"))
    return RouteQuote(
        listing_id=listing_id,
        tick=tick,
        kind=route.kind,
        middleman_id=route.middleman_id,
        observation_geo=route.observation_geo,
        access_tier=route.access_tier,
        line_items=lines,
        landed_eur=landed,
        eta_ticks=eta_ticks,
        p_cancel_est=cfg.P_CANCEL_EST if route.access_tier == AccessTier.IP_GATED else Decimal("0"),
        notes=notes,
    )
