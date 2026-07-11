"""Route enumeration (spec §5.2, §5.4).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Normative reminders:
- The BASE PL quote always exists; promos are ADDITIONAL RouteSpecs.
- VERIFIED_LOCAL is never purchasable; IP_GATED filtered under GeoArb.NEVER.
- STOREFRONT/IP_GATED promos require a middleman route (domestic delivery).
- Feasibility / DEADLINE_MISSED are computed over route CLASSES ignoring
  current stock (§5.7, §6.1).
"""
from __future__ import annotations

from ..core.enums import AccessTier, Geo, GeoArb
from ..core.models import Mandate, RouteSpec, World


def enumerate_routes(listing_id: str, tick: int, mandate: Mandate, world: World) -> list[RouteSpec]:
    """Enumerate every route whose price is visible and operationally usable.

    Stock is intentionally not considered here: policy filters current stock,
    while stopping and deadline logic need stable route-class feasibility.
    """
    listings = [item for item in world.listings if item.id == listing_id]
    if len(listings) != 1:
        raise ValueError(f"expected one listing {listing_id}, found {len(listings)}")
    listing = listings[0]
    vendors = [item for item in world.vendors if item.id == listing.vendor_id]
    if len(vendors) != 1:
        raise ValueError(f"expected one vendor for {listing_id}, found {len(vendors)}")
    vendor = vendors[0]

    routes: list[RouteSpec] = []
    if Geo.PL in vendor.ships_to:
        routes.append(
            RouteSpec(
                kind="direct",
                observation_geo=Geo.PL,
                access_tier=AccessTier.BASE,
            )
        )
    elif mandate.allow_middlemen:
        routes.extend(_middleman_routes(vendor, world, AccessTier.BASE, Geo.PL, None))

    active_promos = sorted(
        (
            promo
            for promo in world.geo_promos
            if promo.listing_id == listing_id and promo.from_tick <= tick <= promo.to_tick
        ),
        key=lambda promo: promo.id,
    )
    for promo in active_promos:
        if promo.access_tier == AccessTier.VERIFIED_LOCAL:
            continue
        if promo.access_tier == AccessTier.IP_GATED and mandate.geo_arbitrage == GeoArb.NEVER:
            continue
        if not mandate.allow_middlemen:
            continue
        routes.extend(
            _middleman_routes(
                vendor,
                world,
                promo.access_tier,
                promo.viewer_geo,
                promo.id,
            )
        )

    return sorted(
        routes,
        key=lambda route: (
            0 if route.kind == "direct" else 1,
            route.middleman_id or "",
            route.access_tier.value,
            route.promo_id or "",
        ),
    )


def _middleman_routes(vendor, world: World, access_tier, observation_geo, promo_id):
    return [
        RouteSpec(
            kind="middleman",
            middleman_id=middleman.id,
            observation_geo=observation_geo,
            access_tier=access_tier,
            promo_id=promo_id,
        )
        for middleman in sorted(world.middlemen, key=lambda item: item.id)
        if middleman.located_in == vendor.geo and Geo.PL in middleman.forwards_to
    ]
