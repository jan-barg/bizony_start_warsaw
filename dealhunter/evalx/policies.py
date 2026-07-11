"""Evaluation-only market curves and SolidHunt timing policy.

The production monitor loop is not available at S1.  This module therefore
combines the *implemented* engine primitives (routes, landed cost, trust, and
EV) with the normative stopping rule from implementation-spec §5.7.  Reports
label it ``SOLIDHUNT_EVAL_MONITOR`` so it cannot be confused with the still-
stubbed production ``run_monitor`` entry point.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..core.config import Constants
from ..core.enums import Condition, Eligibility, GeoArb, Mode
from ..core.models import AutoBuy, Mandate, Product, RouteQuote, World
from ..engine.landed import assemble
from ..engine.routes import enumerate_routes
from ..engine.trust import expected_value, trust_score


_TEMPLATE_RE = re.compile(
    r"^h_(?P<seed>\d+)_(?P<index>\d+):(?P<style>[^:]+):EU(?P<size>[^:]+):"
    r"cap(?P<cap>[^:]+):deadline(?P<deadline>.+)$"
)


@dataclass(frozen=True)
class EvalTemplate:
    seed: int
    index: int
    key: str
    style_code: str
    product_id: str
    size_eu: Decimal
    cap_eur: Decimal
    source_deadline: int | None


@dataclass(frozen=True)
class DailyMarketPoint:
    tick: int
    best_legitimate_eur: Decimal | None
    listing_id: str | None
    route_kind: str | None
    middleman_id: str | None


@dataclass(frozen=True)
class PurchaseDecision:
    policy: str
    tick: int
    listing_id: str
    route_kind: str
    middleman_id: str | None
    actual_landed_eur: Decimal
    perceived_eur: Decimal | None
    legitimate: bool
    trap_types: tuple[str, ...]
    reason: str
    p_better: Decimal | None = None


@dataclass(frozen=True)
class _EngineCandidate:
    quote: RouteQuote
    trust: Decimal
    ev_eur: Decimal


def template_from_world(world: World, index: int = 1) -> EvalTemplate:
    """Read one deterministic eval template encoded by world/oracle.py.

    The analytics cohort deliberately removes the source template's delivery
    deadline.  Every run therefore observes the same complete 90-day horizon,
    which isolates buying-timing skill for the pitch comparison.
    """
    keys = sorted(world.oracle, key=lambda key: int(_TEMPLATE_RE.match(key).group("index")))
    if not 1 <= index <= len(keys):
        raise ValueError(f"template index {index} outside 1..{len(keys)}")
    key = keys[index - 1]
    match = _TEMPLATE_RE.match(key)
    if match is None:
        raise ValueError(f"unrecognized oracle template key: {key}")
    style_code = match.group("style")
    products = [product for product in world.products if product.style_code == style_code]
    if len(products) != 1:
        raise ValueError(f"expected one product for {style_code}, found {len(products)}")
    deadline_text = match.group("deadline")
    return EvalTemplate(
        seed=int(match.group("seed")),
        index=int(match.group("index")),
        key=key,
        style_code=style_code,
        product_id=products[0].id,
        size_eu=Decimal(match.group("size")),
        cap_eur=Decimal(match.group("cap")),
        source_deadline=None if deadline_text == "none" else int(deadline_text),
    )


def evaluation_world(world: World, template: EvalTemplate) -> World:
    """Make an indexed-size world containing only public target listings.

    Engine primitives currently use linear model scans.  Reducing the world to
    the searched style code preserves their behavior while making a 100×90
    evaluation practical.  Hidden labels are retained solely for scoring.
    """
    listings = [
        listing for listing in world.listings
        if listing.id.endswith(f"_{template.style_code}")
    ]
    listing_ids = {listing.id for listing in listings}
    vendor_ids = {listing.vendor_id for listing in listings}
    price_events = [row for row in world.price_events if row.listing_id in listing_ids]
    coupon_ids = {row.coupon_id for row in price_events if row.coupon_id is not None}
    product = next(product for product in world.products if product.id == template.product_id)
    return world.model_copy(update={
        "products": [product],
        "vendors": [vendor for vendor in world.vendors if vendor.id in vendor_ids],
        "listings": listings,
        "price_events": price_events,
        "coupons": [coupon for coupon in world.coupons if coupon.id in coupon_ids],
        "geo_promos": [promo for promo in world.geo_promos if promo.listing_id in listing_ids],
    })


def evaluation_mandate(template: EvalTemplate, horizon: int) -> Mandate:
    return Mandate(
        mode=Mode.IMMEDIATE,
        cap_landed_eur=template.cap_eur,
        need_within_ticks=None,
        auto_buy=AutoBuy(enabled=False),
        allow_middlemen=True,
        geo_arbitrage=GeoArb.NEVER,
        expires_tick=horizon,
    )


def _event_index(world: World) -> dict[tuple[str, int], object]:
    return {(event.listing_id, event.tick): event for event in world.price_events}


def _is_legitimate(world: World, template: EvalTemplate, listing_id: str) -> bool:
    listing = next(listing for listing in world.listings if listing.id == listing_id)
    product = next(product for product in world.products if product.id == template.product_id)
    return (
        listing.true_product_id == template.product_id
        and listing.size_eu == template.size_eu
        and listing.condition == Condition.NEW
        and not listing.is_bait
        and not listing.is_counterfeit
        and product.is_kids_version_of is None
    )


def _trap_types(world: World, listing_id: str) -> tuple[str, ...]:
    return tuple(sorted({trap.trap_type for trap in world.traps if trap.listing_id == listing_id}))


def legitimate_market_timeline(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
) -> list[DailyMarketPoint]:
    """Return the true daily lowest landed price over a full flexible horizon."""
    reduced = evaluation_world(world, template)
    mandate = evaluation_mandate(template, world.horizon)
    events = _event_index(reduced)
    legitimate_ids = {
        listing.id for listing in reduced.listings
        if _is_legitimate(world, template, listing.id)
    }
    points: list[DailyMarketPoint] = []
    for tick in range(world.horizon):
        quotes: list[RouteQuote] = []
        for listing in reduced.listings:
            event = events[(listing.id, tick)]
            if listing.id not in legitimate_ids or event.stock <= 0:
                continue
            for route in enumerate_routes(listing.id, tick, mandate, reduced):
                quotes.append(assemble(listing.id, route, tick, reduced, cfg))
        if not quotes:
            points.append(DailyMarketPoint(tick, None, None, None, None))
            continue
        quote = min(
            quotes,
            key=lambda item: (
                item.landed_eur,
                item.listing_id,
                item.kind,
                item.middleman_id or "",
            ),
        )
        points.append(DailyMarketPoint(
            tick=tick,
            best_legitimate_eur=quote.landed_eur,
            listing_id=quote.listing_id,
            route_kind=quote.kind,
            middleman_id=quote.middleman_id,
        ))
    return points


def optimal_purchase(
    timeline: list[DailyMarketPoint],
    template: EvalTemplate,
) -> DailyMarketPoint | None:
    eligible = [
        point for point in timeline
        if point.best_legitimate_eur is not None
        and point.best_legitimate_eur <= template.cap_eur
    ]
    return min(
        eligible,
        key=lambda point: (point.best_legitimate_eur, point.tick, point.listing_id or ""),
    ) if eligible else None


def _engine_candidates(
    world: World,
    original_world: World,
    template: EvalTemplate,
    tick: int,
    cfg: Constants,
    mandate: Mandate,
    events: dict[tuple[str, int], object],
    require_positive_ev: bool = True,
) -> list[_EngineCandidate]:
    candidates: list[_EngineCandidate] = []
    vendors = {vendor.id: vendor for vendor in world.vendors}
    for listing in world.listings:
        event = events[(listing.id, tick)]
        if (
            event.stock <= 0
            or listing.size_eu != template.size_eu
            or listing.condition != Condition.NEW
        ):
            continue
        vendor = vendors[listing.vendor_id]
        for route in enumerate_routes(listing.id, tick, mandate, world):
            quote = assemble(listing.id, route, tick, world, cfg)
            if quote.landed_eur > template.cap_eur:
                continue
            trust, _flags = trust_score(vendor, quote, world, cfg)
            ev = expected_value(quote, trust, template.cap_eur, None, cfg)
            if trust < cfg.TRUST_FLOOR or (require_positive_ev and ev <= 0):
                continue
            candidates.append(_EngineCandidate(quote=quote, trust=trust, ev_eur=ev))
    return candidates


def _trend_slope(values: list[Decimal]) -> Decimal:
    if len(values) < 2:
        return Decimal("0")
    ys = values[-7:]
    xs = [Decimal(index) for index in range(len(ys))]
    mean_x = sum(xs, Decimal("0")) / Decimal(len(xs))
    mean_y = sum(ys, Decimal("0")) / Decimal(len(ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return Decimal("0")
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def solidhunt_spec_monitor(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
) -> PurchaseDecision | None:
    """Run implemented money/trust layers plus the normative §5.7 timing rule."""
    reduced = evaluation_world(world, template)
    mandate = evaluation_mandate(template, world.horizon)
    events = _event_index(reduced)
    history: list[Decimal] = []
    last_buy_tick = world.horizon - 1

    for tick in range(world.horizon):
        candidates = _engine_candidates(
            reduced, world, template, tick, cfg, mandate, events,
            require_positive_ev=True,
        )
        if not candidates:
            continue
        best_landed = min(candidate.quote.landed_eur for candidate in candidates)
        history.append(best_landed)
        horizon = last_buy_tick - tick
        better_count = sum(
            value < best_landed - cfg.DELTA_IMPROVE_EUR for value in history
        )
        p_daily = Decimal(better_count + 1) / Decimal(len(history) + 2)
        slope = _trend_slope(history)
        if slope < 0:
            p_daily *= cfg.TREND_FALLING_MULT
        elif slope > 0:
            p_daily *= cfg.TREND_RISING_MULT
        p_daily = min(p_daily, cfg.P_DAILY_CLAMP)
        p_better = Decimal("1") - (Decimal("1") - p_daily) ** max(horizon, 0)

        should_buy = (
            horizon == 0
            or (len(history) >= cfg.MIN_OBS and p_better < cfg.THETA_STOP)
        )
        if not should_buy:
            continue
        chosen = min(
            candidates,
            key=lambda candidate: (
                -candidate.ev_eur,
                candidate.quote.listing_id,
                candidate.quote.kind,
                candidate.quote.middleman_id or "",
            ),
        )
        quote = chosen.quote
        return PurchaseDecision(
            policy="SOLIDHUNT_EVAL_MONITOR",
            tick=tick,
            listing_id=quote.listing_id,
            route_kind=quote.kind,
            middleman_id=quote.middleman_id,
            actual_landed_eur=quote.landed_eur,
            perceived_eur=None,
            legitimate=_is_legitimate(world, template, quote.listing_id),
            trap_types=_trap_types(world, quote.listing_id),
            reason="forcing_day" if horizon == 0 else "p_better_below_theta",
            p_better=p_better,
        )
    return None


def solidhunt_improved_monitor(
    world: World,
    template: EvalTemplate,
    cfg: Constants,
    *,
    final_window_ticks: int = 14,
    observed_low_quantile: Decimal = Decimal("0.25"),
) -> PurchaseDecision | None:
    """Safety-preserving monitor tuned for purchase coverage.

    Hard mandate gates and the observable trust floor remain mandatory.  EV is
    used to rank safe candidates instead of suppressing every negative-EV
    quote, because the additive trust score is not a calibrated probability.
    The timing rule buys an observed-low quote after the minimum observation
    period, with a declared final-window fallback that avoids a single-day
    stock lottery at tick 89.
    """
    if not 1 <= final_window_ticks <= world.horizon:
        raise ValueError("final_window_ticks outside world horizon")
    if not Decimal("0") < observed_low_quantile <= Decimal("1"):
        raise ValueError("observed_low_quantile must be in (0, 1]")
    reduced = evaluation_world(world, template)
    mandate = evaluation_mandate(template, world.horizon)
    events = _event_index(reduced)
    history: list[Decimal] = []
    final_window_start = world.horizon - final_window_ticks

    for tick in range(world.horizon):
        candidates = _engine_candidates(
            reduced,
            world,
            template,
            tick,
            cfg,
            mandate,
            events,
            require_positive_ev=False,
        )
        if not candidates:
            continue
        best_landed = min(candidate.quote.landed_eur for candidate in candidates)
        history.append(best_landed)
        rank = Decimal(sum(value <= best_landed for value in history)) / Decimal(len(history))
        observed_low = (
            len(history) >= cfg.MIN_OBS
            and rank <= observed_low_quantile
            and best_landed <= min(history) + cfg.GOOD_DEAL_MARGIN_EUR
        )
        calibrated_floor = (cfg.TRUST_FLOOR + cfg.TRUST_HIGH) / Decimal("2")
        strong_candidates = [
            candidate for candidate in candidates
            if candidate.trust >= cfg.TRUST_HIGH
            or (
                candidate.trust >= calibrated_floor
                and candidate.quote.landed_eur
                <= template.cap_eur - cfg.GOOD_DEAL_MARGIN_EUR
            )
        ]
        high_confidence_deal = bool(strong_candidates)
        final_window = tick >= final_window_start
        if not observed_low and not high_confidence_deal and not final_window:
            continue
        selection_pool = strong_candidates if high_confidence_deal else candidates
        chosen = min(
            selection_pool,
            key=lambda candidate: (
                -candidate.ev_eur,
                candidate.quote.landed_eur,
                candidate.quote.listing_id,
                candidate.quote.kind,
                candidate.quote.middleman_id or "",
            ),
        )
        quote = chosen.quote
        return PurchaseDecision(
            policy="SOLIDHUNT_IMPROVED_MONITOR",
            tick=tick,
            listing_id=quote.listing_id,
            route_kind=quote.kind,
            middleman_id=quote.middleman_id,
            actual_landed_eur=quote.landed_eur,
            perceived_eur=None,
            legitimate=_is_legitimate(world, template, quote.listing_id),
            trap_types=_trap_types(world, quote.listing_id),
            reason=(
                "high_confidence_under_target"
                if high_confidence_deal
                else "observed_low" if observed_low
                else "final_window_fallback"
            ),
            p_better=None,
        )
    return None


# Backwards-compatible name used by the first diagnostic report.
solidhunt_eval_monitor = solidhunt_spec_monitor
