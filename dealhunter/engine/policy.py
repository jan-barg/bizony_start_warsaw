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

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import (
    ALERT_ONLY_FLAGS,
    AccessTier,
    Action,
    Channel,
    DecidedBy,
    Eligibility,
    GeoArb,
    MatchFlag,
    Mode,
)
from ..core.ids import receipt_id
from ..core.models import Evaluation, Hunt, MatchResult, Receipt, World
from ..llm.client import LLMClient
from .landed import assemble
from .matcher import match
from .routes import enumerate_routes
from .trust import expected_value, trust_score
from .invariants import assert_s1_invariants


def _one(items, predicate, description: str):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise ValueError(f"expected one {description}, found {len(matches)}")
    return matches[0]


def _match_listing(listing, hunt: Hunt, world: World, llm: LLMClient) -> MatchResult:
    """Use D's matcher, with a narrow Stage-0 fallback for pinned style codes."""
    try:
        return match(listing, hunt.brief, world, llm)
    except NotImplementedError:
        pinned = hunt.brief.style_code
        if pinned is not None and listing.id.endswith(f"_{pinned}"):
            return MatchResult(
                style_code=pinned,
                colorway_confirmed=True,
                confidence=0.99,
            )
        return MatchResult()


def _evaluation_sort_key(evaluation: Evaluation):
    quote = evaluation.quote
    return (-evaluation.ev_eur, quote.listing_id, quote.kind, quote.middleman_id or "")


def _considered_sort_key(evaluation: Evaluation):
    quote = evaluation.quote
    return (quote.landed_eur, quote.listing_id, quote.kind, quote.middleman_id or "")


def evaluate_tick(hunt: Hunt, tick: int, world: World, cfg: Constants, llm: LLMClient) -> Receipt:
    """Evaluate one immediate-mode tick through deterministic Layers 1–2.

    Monitor stopping and E2/E3 human ask lifecycles intentionally land in the
    next checkpoint. Gray ASK routes are therefore unavailable, never bought.
    """
    if hunt.mandate.mode != Mode.IMMEDIATE:
        raise NotImplementedError("monitor policy requires engine/stopping.py")

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

    qualifying = [
        evaluation
        for evaluation in evaluations
        if evaluation.eligibility == Eligibility.QUALIFYING
        and evaluation.trust >= cfg.TRUST_FLOOR
        and evaluation.ev_eur > 0
        and evaluation.purchase_eligible
    ]
    selection: list[Evaluation] = []
    for evaluation in qualifying:
        if (
            evaluation.quote.access_tier == AccessTier.IP_GATED
            and hunt.mandate.geo_arbitrage == GeoArb.ASK
        ):
            policy_notes.append(f"gray_route_deferred:{evaluation.quote.listing_id}")
            continue
        selection.append(evaluation)

    auto_selection = [evaluation for evaluation in selection if evaluation.auto_buy_eligible]
    if auto_selection:
        chosen = sorted(auto_selection, key=_evaluation_sort_key)[0]
        action = Action.BUY
        tier = "E0"
        reasons = ["auto_buy_conditions_satisfied", *policy_notes]
    elif selection:
        chosen = sorted(selection, key=_evaluation_sort_key)[0]
        action = Action.BUY
        tier = "E1"
        reasons = ["immediate_best_ev", *policy_notes]
    else:
        chosen = None
        action = Action.ESCALATE_NONE_FOUND
        tier = "E5"
        reasons = ["immediate_nothing_qualifies", *policy_notes]
        near_misses = sorted(evaluations, key=_considered_sort_key)[:5]
        reasons.extend(
            f"near_miss:{item.quote.listing_id}:{','.join(item.gate_failures) or item.eligibility.value}"
            for item in near_misses
        )

    considered = sorted(
        [item for item in evaluations if item.eligibility != Eligibility.HARD_REJECT],
        key=_considered_sort_key,
    )[:5]
    receipt = Receipt(
        id=receipt_id(hunt.id, tick, 0),
        hunt_id=hunt.id,
        tick=tick,
        action=action,
        decided_by=DecidedBy.CODE,
        escalation_tier=tier,
        chosen=chosen,
        considered=considered,
        reasons=reasons,
    )
    assert_s1_invariants(receipt, hunt)
    return receipt
