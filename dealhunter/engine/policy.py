"""Immediate policy — gates, EV selection, and E0/E1/E5 actions (spec §5.8–§5.9).
Owner: feat/engine (Work Order 2). Signature is frozen; body is not.

Normative reminders:
- Exactly ONE Receipt per tick; considered = top-5 by landed among
  eligibility ≠ HARD_REJECT, ties broken (listing_id, route kind, middleman_id).
- Selection set S = qualifying ∧ purchase_eligible, minus gray quotes that
  cannot ask this tick (each removal receipted). Reselect from what remains.
- Escalation ladder E0–E5 (§5.9): E4 auto-reject > cap·(1+band) silently;
  E3 over-cap ask inside the band on the deal-quality test; E2 gray-route ask.
- Invariants §6.3 are asserted live here and in loop.py.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal

from ..core.config import Constants
from ..core.enums import (
    ALERT_ONLY_FLAGS,
    AccessTier,
    Action,
    AskKind,
    Channel,
    DecidedBy,
    Eligibility,
    GeoArb,
    MatchFlag,
    Mode,
)
from ..core.ids import receipt_id
from ..core.models import (
    Evaluation,
    Hunt,
    MatchResult,
    Receipt,
    World,
    quote_hash,
)
from ..llm.client import LLMClient
from .landed import assemble
from .matcher import match
from .routes import enumerate_routes
from .trust import expected_value, trust_score
from .invariants import assert_s1_invariants
from .alerts import (
    can_interrupt,
    consume_approved_ask,
    create_ask,
    record_interruption,
)
from .stopping import (
    deal_percentile,
    final_buy_tick,
    improved_stopping_decision,
    p_better,
)


_MATCH_MEMO: ContextVar[dict[tuple[str, str], MatchResult] | None] = ContextVar(
    "match_memo", default=None
)


@contextmanager
def _match_memo_scope() -> Iterator[None]:
    """Keep static-title matcher results inside one engine execution."""
    token = _MATCH_MEMO.set({})
    try:
        yield
    finally:
        _MATCH_MEMO.reset(token)


def _one(items, predicate, description: str):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise ValueError(f"expected one {description}, found {len(matches)}")
    return matches[0]


def _match_listing(listing, hunt: Hunt, world: World, llm: LLMClient) -> MatchResult:
    """Memoize D's static-title matcher once per hunt and listing."""
    memo = _MATCH_MEMO.get()
    if memo is None:
        return match(listing, hunt.brief, world, llm)
    key = (hunt.id, listing.id)
    if key not in memo:
        memo[key] = match(listing, hunt.brief, world, llm)
    return memo[key]


def _evaluation_sort_key(evaluation: Evaluation):
    quote = evaluation.quote
    return (-evaluation.ev_eur, quote.listing_id, quote.kind, quote.middleman_id or "")


def _improved_monitor_sort_key(evaluation: Evaluation):
    quote = evaluation.quote
    return (
        -evaluation.ev_eur,
        quote.landed_eur,
        quote.listing_id,
        quote.kind,
        quote.middleman_id or "",
    )


def _considered_sort_key(evaluation: Evaluation):
    quote = evaluation.quote
    return (quote.landed_eur, quote.listing_id, quote.kind, quote.middleman_id or "")


def _minimum_feasible_eta(
    hunt: Hunt, tick: int, world: World, cfg: Constants, llm: LLMClient
) -> int | None:
    """Fastest matching route class, deliberately ignoring current stock."""
    etas: list[int] = []
    for listing in world.listings:
        if listing.id in hunt.excluded_listings:
            continue
        result = _match_listing(listing, hunt, world, llm)
        if result.style_code != hunt.brief.style_code:
            continue
        if listing.size_eu != hunt.brief.size_eu or listing.condition != hunt.brief.condition:
            continue
        vendor = _one(world.vendors, lambda item: item.id == listing.vendor_id, "listing vendor")
        if hunt.brief.exclude_resellers and vendor.channel == Channel.RESELLER:
            continue
        if hunt.brief.exclude_kids and MatchFlag.KIDS_SIZING in result.flags:
            continue
        for route in enumerate_routes(listing.id, tick, hunt.mandate, world):
            if route.kind == "direct":
                from ..core.enums import GEO_TO_ZONE

                etas.append(cfg.ETA_DIRECT[GEO_TO_ZONE[vendor.geo]])
            else:
                middleman = _one(
                    world.middlemen,
                    lambda item: item.id == route.middleman_id,
                    "route middleman",
                )
                etas.append(cfg.ETA_DOMESTIC_LEG + middleman.extra_ticks)
    return min(etas) if etas else None


def evaluate_tick(hunt: Hunt, tick: int, world: World, cfg: Constants, llm: LLMClient) -> Receipt:
    """Evaluate one tick through gates, EV, stopping, and escalation E0–E5."""

    evaluations: list[Evaluation] = []
    policy_notes: list[str] = []
    for listing in sorted(world.listings, key=lambda item: item.id):
        if listing.id in hunt.excluded_listings:
            continue
        events = [
            event for event in world.price_events
            if event.listing_id == listing.id and event.tick == tick
        ]
        if len(events) != 1 or events[0].stock <= 0:
            continue
        vendor = _one(world.vendors, lambda item: item.id == listing.vendor_id, "listing vendor")
        match_result = _match_listing(listing, hunt, world, llm)

        for route in enumerate_routes(listing.id, tick, hunt.mandate, world):
            quote = assemble(listing.id, route, tick, world, cfg)
            failures: list[str] = []
            alert_flags = set(match_result.flags) & ALERT_ONLY_FLAGS

            if hunt.brief.style_code is not None and match_result.style_code != hunt.brief.style_code:
                failures.append("style_code_mismatch")
            elif match_result.style_code is None:
                failures.append("product_unmatched")
            if (
                listing.size_eu != hunt.brief.size_eu
                or MatchFlag.SIZE_MISMATCH in match_result.flags
            ):
                failures.append("size_mismatch")
            if (
                listing.condition != hunt.brief.condition
                or MatchFlag.CONDITION_MISMATCH in match_result.flags
            ):
                failures.append("condition_mismatch")
            if hunt.brief.exclude_kids and MatchFlag.KIDS_SIZING in match_result.flags:
                failures.append("kids_excluded")
            if hunt.brief.exclude_resellers and vendor.channel == Channel.RESELLER:
                failures.append("reseller_excluded")

            band_limit = hunt.mandate.cap_landed_eur * (
                Decimal("1") + hunt.mandate.overcap_ask_band_pct
            )
            over_cap_band = False
            if quote.landed_eur > band_limit:
                failures.append(
                    f"over_cap_far:{quote.landed_eur}>{band_limit.quantize(Decimal('0.01'))}"
                )
            elif quote.landed_eur > hunt.mandate.cap_landed_eur:
                over_cap_band = True

            if hunt.mandate.revoked:
                failures.append("mandate_revoked")
            if tick >= hunt.mandate.expires_tick:
                failures.append("mandate_expired")
            if hunt.mandate.need_within_ticks is not None:
                deadline_tick = hunt.start_tick + hunt.mandate.need_within_ticks
                if tick + quote.eta_ticks > deadline_tick:
                    failures.append("deadline_missed")
            if quote.access_tier == AccessTier.VERIFIED_LOCAL:
                failures.append("verified_local_unattainable")
            if (
                quote.access_tier == AccessTier.IP_GATED
                and hunt.mandate.geo_arbitrage == GeoArb.NEVER
            ):
                failures.append("ip_gated_forbidden")

            if failures:
                eligibility = Eligibility.HARD_REJECT
            elif over_cap_band:
                eligibility = Eligibility.OVER_CAP_BAND
            else:
                eligibility = Eligibility.QUALIFYING

            trust, trust_flags = trust_score(vendor, quote, world, cfg)
            deadline_left = (
                hunt.start_tick + hunt.mandate.need_within_ticks - tick
                if hunt.mandate.need_within_ticks is not None
                else None
            )
            ev = expected_value(
                quote,
                trust,
                hunt.mandate.cap_landed_eur,
                deadline_left,
                cfg,
            )
            purchase_eligible = not alert_flags
            event = events[0]
            auto = hunt.mandate.auto_buy
            auto_buy_eligible = (
                auto.enabled
                and eligibility == Eligibility.QUALIFYING
                and purchase_eligible
                and quote.landed_eur
                >= hunt.mandate.cap_landed_eur - auto.within_eur_of_target
                and (not auto.require_stock_low or event.stock <= cfg.STOCK_LOW)
                and (not auto.require_trust_high or trust >= cfg.TRUST_HIGH)
                and match_result.colorway_confirmed
                and MatchFlag.KIDS_SIZING not in match_result.flags
                and MatchFlag.CONDITION_MISMATCH not in match_result.flags
            )
            evaluations.append(
                Evaluation(
                    quote=quote,
                    match=match_result,
                    trust=trust,
                    trust_flags=trust_flags,
                    ev_eur=ev,
                    eligibility=eligibility,
                    purchase_eligible=purchase_eligible,
                    gate_failures=failures,
                    auto_buy_eligible=auto_buy_eligible,
                )
            )

    qualifying_all = [
        evaluation
        for evaluation in evaluations
        if evaluation.eligibility == Eligibility.QUALIFYING
        and evaluation.trust >= cfg.TRUST_FLOOR
        and (
            hunt.mandate.mode == Mode.MONITOR
            or evaluation.ev_eur > 0
        )
    ]
    qualifying = [item for item in qualifying_all if item.purchase_eligible]
    selection: list[Evaluation] = []
    for evaluation in qualifying:
        if (
            evaluation.quote.access_tier == AccessTier.IP_GATED
            and hunt.mandate.geo_arbitrage == GeoArb.ASK
        ):
            allowed, reason = can_interrupt(
                hunt,
                tick,
                evaluation.quote.listing_id,
                AskKind.GRAY_ROUTE.value,
                cfg,
                evaluation.quote.landed_eur,
            )
            if not allowed:
                policy_notes.append(f"{reason}:{evaluation.quote.listing_id}")
                continue
        selection.append(evaluation)

    previous_best = list(hunt.history_best)
    previous_best_any = list(hunt.history_best_any)
    current_history_best = min(
        (item.quote.landed_eur for item in qualifying_all), default=None
    )
    current_history_any = min(
        (
            item.quote.landed_eur
            for item in evaluations
            if item.eligibility in {Eligibility.QUALIFYING, Eligibility.OVER_CAP_BAND}
        ),
        default=None,
    )
    stopping = None
    monitor_trigger = None
    strong_selection: list[Evaluation] = []
    should_stop = hunt.mandate.mode == Mode.IMMEDIATE
    if hunt.mandate.mode == Mode.MONITOR and selection and current_history_best is not None:
        minimum_eta = _minimum_feasible_eta(hunt, tick, world, cfg, llm)
        if minimum_eta is not None:
            calibrated_floor = (cfg.TRUST_FLOOR + cfg.TRUST_HIGH) / Decimal("2")
            strong_selection = [
                evaluation
                for evaluation in selection
                if evaluation.trust >= cfg.TRUST_HIGH
                or (
                    evaluation.trust >= calibrated_floor
                    and evaluation.quote.landed_eur
                    <= hunt.mandate.cap_landed_eur - cfg.GOOD_DEAL_MARGIN_EUR
                )
            ]
            should_stop, stopping, monitor_trigger = improved_stopping_decision(
                previous_best,
                current_history_best,
                tick,
                final_buy_tick(hunt, minimum_eta),
                bool(strong_selection),
                cfg,
            )

    approved_ask = (
        hunt.pending_ask
        if hunt.pending_ask is not None
        and hunt.pending_ask.status == "APPROVED"
        and hunt.pending_ask.tick == tick
        else None
    )
    approved_evaluation = None
    if approved_ask is not None:
        approved_evaluation = next(
            (
                item
                for item in evaluations
                if quote_hash(item.quote) == approved_ask.quote_hash
                and item.purchase_eligible
                and item.eligibility
                in {Eligibility.QUALIFYING, Eligibility.OVER_CAP_BAND}
            ),
            None,
        )
        if approved_evaluation is None:
            raise ValueError("approved quote is no longer executable")

    auto_selection = [
        evaluation
        for evaluation in selection
        if evaluation.auto_buy_eligible
        and not (
            evaluation.quote.access_tier == AccessTier.IP_GATED
            and hunt.mandate.geo_arbitrage == GeoArb.ASK
        )
    ]
    decided_by = DecidedBy.CODE
    if approved_evaluation is not None and approved_ask is not None:
        consume_approved_ask(hunt, approved_evaluation.quote, approved_ask.kind)
        chosen = approved_evaluation
        action = Action.BUY
        tier = "E2" if approved_ask.kind == AskKind.GRAY_ROUTE else "E3"
        decided_by = DecidedBy.HUMAN
        reasons = [f"approved_ask_consumed:{approved_ask.id}"]
    elif auto_selection:
        chosen = sorted(auto_selection, key=_evaluation_sort_key)[0]
        action = Action.BUY
        tier = "E0"
        reasons = ["auto_buy_conditions_satisfied", *policy_notes]
        stopping = stopping if hunt.mandate.mode == Mode.MONITOR else None
    elif selection and should_stop:
        monitor_selection = (
            strong_selection
            if hunt.mandate.mode == Mode.MONITOR
            and monitor_trigger == "high_confidence_under_target"
            and strong_selection
            else selection
        )
        chosen = sorted(
            monitor_selection,
            key=(
                _improved_monitor_sort_key
                if hunt.mandate.mode == Mode.MONITOR
                else _evaluation_sort_key
            ),
        )[0]
        if (
            chosen.quote.access_tier == AccessTier.IP_GATED
            and hunt.mandate.geo_arbitrage == GeoArb.ASK
        ):
            legal = [
                item.quote.landed_eur
                for item in selection
                if item.quote.access_tier != AccessTier.IP_GATED
            ]
            sequence = (
                1
                if hunt.pending_ask is not None and hunt.pending_ask.tick == tick
                else 0
            )
            create_ask(
                hunt,
                tick,
                AskKind.GRAY_ROUTE,
                chosen,
                min(legal) if legal else None,
                sequence,
            )
            action = Action.ASK
            tier = "E2"
            reasons = ["gray_route_consent_required", *policy_notes]
        else:
            action = Action.BUY
            tier = "E1"
            reasons = [
                "immediate_best_ev"
                if hunt.mandate.mode == Mode.IMMEDIATE
                else monitor_trigger or "improved_monitor_buy",
                *policy_notes,
            ]
    else:
        chosen = None
        band_candidates = [
            item
            for item in evaluations
            if item.eligibility == Eligibility.OVER_CAP_BAND
            and item.purchase_eligible
            and item.trust >= cfg.TRUST_HIGH
            and item.match.colorway_confirmed
            and not item.match.flags
            and not (
                item.quote.access_tier == AccessTier.IP_GATED
                and hunt.mandate.geo_arbitrage == GeoArb.ASK
            )
        ]
        over_cap = min(band_candidates, key=_considered_sort_key) if band_candidates else None
        e3_quality = False
        if over_cap is not None and not selection:
            best_ever = not previous_best_any or (
                over_cap.quote.landed_eur <= min(previous_best_any)
            )
            if hunt.mandate.mode == Mode.IMMEDIATE:
                argmin_any = min(
                    (
                        item
                        for item in evaluations
                        if item.eligibility
                        in {Eligibility.QUALIFYING, Eligibility.OVER_CAP_BAND}
                    ),
                    key=_considered_sort_key,
                    default=None,
                )
                timing_good = argmin_any is over_cap
            else:
                horizon = stopping.horizon if stopping is not None else 0
                timing_good = (
                    len(previous_best_any) >= cfg.MIN_OBS
                    and p_better(
                        previous_best_any,
                        over_cap.quote.landed_eur,
                        horizon,
                        cfg,
                    )
                    < cfg.THETA_STOP
                )
            e3_quality = best_ever and timing_good

        if over_cap is not None and e3_quality:
            allowed, reason = can_interrupt(
                hunt,
                tick,
                over_cap.quote.listing_id,
                AskKind.OVER_CAP.value,
                cfg,
                over_cap.quote.landed_eur,
            )
            if allowed:
                sequence = (
                    1
                    if hunt.pending_ask is not None and hunt.pending_ask.tick == tick
                    else 0
                )
                create_ask(
                    hunt,
                    tick,
                    AskKind.OVER_CAP,
                    over_cap,
                    None,
                    sequence,
                )
                chosen = over_cap
                action = Action.ASK
                tier = "E3"
                reasons = ["over_cap_exception_earned", *policy_notes]
            else:
                policy_notes.append(f"{reason}:{over_cap.quote.listing_id}")

        if chosen is None:
            previous_low = min(previous_best) if previous_best else None
            alert_candidate = (
                sorted(qualifying_all, key=_evaluation_sort_key)[0]
                if qualifying_all
                else None
            )
            new_low = (
                alert_candidate is not None
                and (
                    previous_low is None
                    or alert_candidate.quote.landed_eur < previous_low
                )
            )
            alert_allowed = False
            alert_reason = None
            if alert_candidate is not None and new_low:
                alert_allowed, alert_reason = can_interrupt(
                    hunt,
                    tick,
                    alert_candidate.quote.listing_id,
                    "ALERT",
                    cfg,
                )
            if alert_candidate is not None and new_low and alert_allowed:
                chosen = alert_candidate
                action = Action.ALERT
                tier = None
                record_interruption(
                    hunt, tick, alert_candidate.quote.listing_id, "ALERT"
                )
                reasons = ["new_observed_low"]
            elif hunt.mandate.mode == Mode.IMMEDIATE:
                action = Action.ESCALATE_NONE_FOUND
                tier = "E5"
                reasons = ["immediate_nothing_qualifies", *policy_notes]
                near_misses = sorted(evaluations, key=_considered_sort_key)[:5]
                reasons.extend(
                    f"near_miss:{item.quote.listing_id}:{','.join(item.gate_failures) or item.eligibility.value}"
                    for item in near_misses
                )
            else:
                action = Action.HOLD
                tier = None
                reasons = ["monitor_wait", *policy_notes]
                if alert_reason:
                    reasons.append(f"{alert_reason}:ALERT")
                if current_history_best is not None:
                    reasons.append(
                        f"deal_percentile:{deal_percentile(previous_best, current_history_best)}"
                    )

    if approved_ask is None and current_history_best is not None:
        hunt.history_best.append(current_history_best)
    if approved_ask is None and current_history_any is not None:
        hunt.history_best_any.append(current_history_any)

    considered = sorted(
        [item for item in evaluations if item.eligibility != Eligibility.HARD_REJECT],
        key=_considered_sort_key,
    )[:5]
    receipt = Receipt(
        id=receipt_id(hunt.id, tick, 0),
        hunt_id=hunt.id,
        tick=tick,
        action=action,
        decided_by=decided_by,
        escalation_tier=tier,
        chosen=chosen,
        considered=considered,
        reasons=reasons,
        stopping=stopping,
    )
    assert_s1_invariants(receipt, hunt)
    return receipt
