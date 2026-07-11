"""Simulation outcomes that keep hidden truth outside runtime engine modules."""

from decimal import Decimal

from ..core.enums import AccessTier
from ..core.models import RouteQuote, World
from ..core.rng import rng


def merchant_cancels(world: World, quote: RouteQuote) -> bool:
    """Draw the seeded true merchant outcome for an IP-gated purchase."""
    if quote.access_tier != AccessTier.IP_GATED:
        return False
    matches = [
        promo
        for promo in world.geo_promos
        if promo.listing_id == quote.listing_id
        and promo.access_tier == AccessTier.IP_GATED
        and promo.viewer_geo == quote.observation_geo
        and promo.from_tick <= quote.tick <= promo.to_tick
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one IP-gated outcome source for {quote.listing_id}, "
            f"found {len(matches)}"
        )
    probability = matches[0].p_cancel or Decimal("0")
    draw = Decimal(
        str(rng(world.seed, "cancel", quote.listing_id, quote.tick).random())
    )
    return draw < probability
