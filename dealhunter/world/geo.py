"""Geo-differentiated price generation (implementation spec §4.5)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from ..core.config import Constants
from ..core.enums import AccessTier, Currency, Geo
from ..core.ids import geo_promo_id
from ..core.models import GeoPromo, Listing, Middleman, PriceEvent, Vendor
from ..core.rng import rng


def quantize_sticker(value: Decimal, currency: Currency) -> Decimal:
    quantum = Decimal("1") if currency is Currency.JPY else Decimal("0.01")
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def generate_geo_promos(
    seed: int,
    cfg: Constants,
    vendors: list[Vendor],
    middlemen: list[Middleman],
    listings: list[Listing],
    events: list[PriceEvent],
) -> list[GeoPromo]:
    """Generate ordinary foreign storefront promos; adversarial promos live in traps.py."""
    vendors_by_id = {vendor.id: vendor for vendor in vendors}
    event_by_key = {(event.listing_id, event.tick): event for event in events}
    middleman_geos = {middleman.located_in for middleman in middlemen}
    promos: list[GeoPromo] = []
    for listing in listings:
        vendor = vendors_by_id[listing.vendor_id]
        if vendor.geo not in {Geo.JP, Geo.US, Geo.UK} or vendor.geo not in middleman_geos:
            continue
        stream = rng(seed, "geo", listing.id)
        if stream.random() >= 0.06:
            continue
        from_tick = stream.randrange(0, max(1, cfg.HORIZON - 5))
        to_tick = min(cfg.HORIZON - 1, from_tick + stream.randint(3, 9))
        base = event_by_key[(listing.id, from_tick)].sticker
        discount_bp = stream.randint(500, 1400)
        sticker = quantize_sticker(base * (Decimal(10_000 - discount_bp) / Decimal(10_000)), vendor.currency)
        promos.append(
            GeoPromo(
                id=geo_promo_id(listing.id, vendor.geo.value),
                listing_id=listing.id,
                viewer_geo=vendor.geo,
                promo_sticker=sticker,
                from_tick=from_tick,
                to_tick=to_tick,
                access_tier=AccessTier.STOREFRONT,
            )
        )
    return sorted(promos, key=lambda promo: promo.id)
