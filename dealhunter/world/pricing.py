"""Namespaced price, stock, coupon, and FX processes (§4.4)."""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Literal

from ..core.config import Constants
from ..core.enums import Currency
from ..core.ids import coupon_id
from ..core.models import Coupon, FxRate, Listing, PriceEvent, Product, Vendor
from ..core.rng import rng


def _price_boundary(value: float, currency: Currency) -> Decimal:
    """The single float-to-money boundary: integer minor units, then Decimal."""
    if currency is Currency.JPY:
        return Decimal(round(value))
    return Decimal(round(value * 100)) / 100


def _rate_boundary(value: float) -> Decimal:
    return Decimal(round(value * 1_000_000)) / 1_000_000


def generate_fx(seed: int, cfg: Constants) -> list[FxRate]:
    initial = {
        "EURPLN": 4.25,
        "EURGBP": 0.86,
        "EURUSD": 1.10,
        "EURJPY": 165.00,
    }
    rows: list[FxRate] = []
    for pair in sorted(initial):
        stream = rng(seed, "fx", pair)
        rate = initial[pair]
        for tick in range(cfg.HORIZON):
            if tick:
                rate *= 1.0 + stream.gauss(0.0, 0.003)
            rows.append(FxRate(tick=tick, pair=pair, rate=_rate_boundary(rate)))
    return sorted(rows, key=lambda row: (row.tick, row.pair))


def _sale_probability(base: float, price: float) -> float:
    signal = 4.0 * (base - price) / base
    return (1.0 / (1.0 + math.exp(-signal))) * 0.35


def generate_pricing(
    seed: int,
    cfg: Constants,
    products: list[Product],
    vendors: list[Vendor],
    listings: list[Listing],
) -> tuple[list[PriceEvent], list[Coupon], list[FxRate]]:
    fx = generate_fx(seed, cfg)
    rate_at_zero = {row.pair: float(row.rate) for row in fx if row.tick == 0}
    products_by_id = {product.id: product for product in products}
    vendors_by_id = {vendor.id: vendor for vendor in vendors}
    events: list[PriceEvent] = []
    coupons: list[Coupon] = []

    for listing in listings:
        product = products_by_id[listing.true_product_id]
        vendor = vendors_by_id[listing.vendor_id]
        stream = rng(seed, "price", listing.id)
        fx_pair = f"EUR{vendor.currency.value}"
        rate = 1.0 if vendor.currency is Currency.EUR else rate_at_zero[fx_pair]
        base = float(product.fair_price_eur) * stream.uniform(0.92, 1.15) * rate
        price = base
        initial_stock = stream.randint(1, 12)
        stock = initial_stock
        flash_remaining = 0
        flash_depth = 0.0

        coupon: Coupon | None = None
        if stream.random() < 0.25:
            valid_from = stream.randrange(0, max(1, cfg.HORIZON - 4))
            duration = stream.randint(5, min(15, max(5, cfg.HORIZON - valid_from)))
            valid_to = min(cfg.HORIZON - 1, valid_from + duration - 1)
            kind: Literal["pct", "flat"] = "pct" if stream.random() < 0.70 else "flat"
            value = Decimal(stream.randint(10, 15)) if kind == "pct" else _price_boundary(10.0 * rate, vendor.currency)
            coupon = Coupon(
                id=coupon_id(listing.id, valid_from),
                code=f"SAVE{stream.randint(10, 99)}",
                kind=kind,
                value=value,
                min_basket=_price_boundary(base * 0.70, vendor.currency) if stream.random() < 0.40 else None,
                excludes_sale=stream.random() < 0.35,
                valid_from=valid_from,
                valid_to=valid_to,
            )
            coupons.append(coupon)

        history_max = 0.0
        tick_zero_sticker: Decimal | None = None
        for tick in range(cfg.HORIZON):
            if tick:
                price += 0.10 * (base - price) + stream.gauss(0.0, 0.012 * base)
                price = max(0.55 * base, price)
            if flash_remaining == 0 and stream.random() < 0.35 / 30.0:
                flash_depth = stream.uniform(0.12, 0.25)
                flash_remaining = stream.randint(1, 3)
            in_flash = flash_remaining > 0
            effective = price * (1.0 - flash_depth) if in_flash else price
            sticker = _price_boundary(effective, vendor.currency)
            if tick_zero_sticker is None:
                tick_zero_sticker = sticker
            on_sale = in_flash or sticker < tick_zero_sticker * Decimal("0.97")
            history_max = max(history_max, effective)

            if tick and stock > 0 and stream.random() < _sale_probability(base, effective):
                stock -= 1
            elif tick and stock == 0 and stream.random() < 0.03:
                stock = initial_stock

            events.append(
                PriceEvent(
                    listing_id=listing.id,
                    tick=tick,
                    sticker=sticker,
                    stock=stock,
                    on_sale=on_sale,
                    was_price_shown=_price_boundary(history_max, vendor.currency),
                    coupon_id=coupon.id if coupon and coupon.valid_from <= tick <= coupon.valid_to else None,
                )
            )
            if flash_remaining:
                flash_remaining -= 1

    return (
        sorted(events, key=lambda row: (row.listing_id, row.tick)),
        sorted(coupons, key=lambda coupon: coupon.id),
        fx,
    )
