"""Deterministic comparison policies for evaluation (spec §10.2)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..core.config import Constants
from ..core.enums import AccessTier, Condition
from ..core.models import RouteQuote, World
from ..engine.landed import assemble
from ..engine.routes import enumerate_routes
from .policies import (
    EvalTemplate,
    PurchaseDecision,
    _is_legitimate,
    _trap_types,
    evaluation_mandate,
    evaluation_world,
)


@dataclass(frozen=True)
class CasualShopperHypothesis:
    """A generous but behaviorally simple non-expert shopper model.

    The shopper checks every three days, has correct product/size discovery,
    considers only ordinary direct-to-Poland checkout offers, and buys the
    cheapest perceived subtotal as soon as it fits the budget.  They account
    for goods, an applicable coupon, and quoted shipping, but do not calculate
    border VAT/duty/handling, trust, forwarding, or geo tactics.
    """

    check_interval_ticks: int = 3


def _perceived_checkout(quote: RouteQuote) -> Decimal:
    visible_codes = {"GOODS", "COUPON", "SHIP_DIRECT"}
    return sum(
        (line.amount_eur for line in quote.line_items if line.code in visible_codes),
        Decimal("0"),
    )


def casual_checkout_shopper(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
    hypothesis: CasualShopperHypothesis = CasualShopperHypothesis(),
) -> PurchaseDecision | None:
    """Buy the first three-day-check subtotal that appears within budget."""
    if hypothesis.check_interval_ticks <= 0:
        raise ValueError("check interval must be positive")
    reduced = evaluation_world(world, template)
    mandate = evaluation_mandate(template, world.horizon)
    events = {(row.listing_id, row.tick): row for row in reduced.price_events}
    check_ticks = list(range(0, world.horizon, hypothesis.check_interval_ticks))
    if check_ticks[-1] != world.horizon - 1:
        check_ticks.append(world.horizon - 1)

    for tick in check_ticks:
        candidates: list[tuple[Decimal, RouteQuote]] = []
        for listing in reduced.listings:
            event = events[(listing.id, tick)]
            if (
                event.stock <= 0
                or listing.size_eu != template.size_eu
                or listing.condition != Condition.NEW
            ):
                continue
            for route in enumerate_routes(listing.id, tick, mandate, reduced):
                if route.kind != "direct" or route.access_tier != AccessTier.BASE:
                    continue
                quote = assemble(listing.id, route, tick, reduced, cfg)
                perceived = _perceived_checkout(quote)
                if perceived <= template.cap_eur:
                    candidates.append((perceived, quote))
        if not candidates:
            continue
        perceived, quote = min(
            candidates,
            key=lambda item: (
                item[0], item[1].listing_id, item[1].kind,
            ),
        )
        return PurchaseDecision(
            policy=f"CASUAL_CHECKOUT_{hypothesis.check_interval_ticks}D",
            tick=tick,
            listing_id=quote.listing_id,
            route_kind=quote.kind,
            middleman_id=quote.middleman_id,
            actual_landed_eur=quote.landed_eur,
            perceived_eur=perceived,
            legitimate=_is_legitimate(world, template, quote.listing_id),
            trap_types=_trap_types(world, quote.listing_id),
            reason="first_perceived_checkout_within_budget",
        )
    return None


def greedy_sticker(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
) -> PurchaseDecision | None:
    """Spec §10 GREEDY_STICKER, represented as a daily casual checkout."""
    return casual_checkout_shopper(
        world,
        template,
        cfg,
        CasualShopperHypothesis(check_interval_ticks=1),
    )


def landed_no_trust(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
) -> PurchaseDecision | None:
    """Buy the first daily minimum complete landed quote, without trust/timing."""
    reduced = evaluation_world(world, template)
    mandate = evaluation_mandate(template, world.horizon)
    events = {(row.listing_id, row.tick): row for row in reduced.price_events}
    for tick in range(world.horizon):
        quotes: list[RouteQuote] = []
        for listing in reduced.listings:
            event = events[(listing.id, tick)]
            if (
                event.stock <= 0
                or listing.size_eu != template.size_eu
                or listing.condition != Condition.NEW
            ):
                continue
            quotes.extend(
                assemble(listing.id, route, tick, reduced, cfg)
                for route in enumerate_routes(listing.id, tick, mandate, reduced)
            )
        eligible = [quote for quote in quotes if quote.landed_eur <= template.cap_eur]
        if not eligible:
            continue
        quote = min(
            eligible,
            key=lambda item: (
                item.landed_eur, item.listing_id, item.kind, item.middleman_id or "",
            ),
        )
        return PurchaseDecision(
            policy="LANDED_NO_TRUST",
            tick=tick,
            listing_id=quote.listing_id,
            route_kind=quote.kind,
            middleman_id=quote.middleman_id,
            actual_landed_eur=quote.landed_eur,
            perceived_eur=quote.landed_eur,
            legitimate=_is_legitimate(world, template, quote.listing_id),
            trap_types=_trap_types(world, quote.listing_id),
            reason="first_complete_landed_quote_within_budget",
        )
    return None
