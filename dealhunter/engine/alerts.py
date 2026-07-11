"""Unified interruption budget and quote-exact ask lifecycle (spec §5.9)."""

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import AskKind
from ..core.ids import ask_id
from ..core.models import (
    Ask,
    Evaluation,
    Hunt,
    RouteQuote,
    declined_key,
    quote_hash,
)


def _recent_interruptions(hunt: Hunt, tick: int, window: int):
    return [entry for entry in hunt.interruptions if 0 <= tick - entry[0] < window]


def can_interrupt(
    hunt: Hunt,
    tick: int,
    listing_id: str,
    kind: str,
    cfg: Constants,
    landed_eur: Decimal | None = None,
) -> tuple[bool, str | None]:
    recent = _recent_interruptions(hunt, tick, cfg.ALERT_WINDOW_TICKS)
    if len(recent) >= hunt.mandate.alert_budget_per_week:
        return False, "interrupt_budget_exhausted"
    if any(
        previous_listing == listing_id
        and previous_kind == kind
        and 0 <= tick - previous_tick < cfg.INTERRUPT_DEDUPE_TICKS
        for previous_tick, previous_listing, previous_kind in hunt.interruptions
    ):
        return False, "interrupt_deduped"

    if kind in {AskKind.GRAY_ROUTE.value, AskKind.OVER_CAP.value}:
        declined = hunt.declined_asks.get(declined_key(listing_id, AskKind(kind)))
        if declined is not None and landed_eur is not None:
            required = max(
                cfg.REASK_IMPROVEMENT_ABS,
                declined * cfg.REASK_IMPROVEMENT_PCT,
            )
            if landed_eur > declined - required:
                return False, "ask_declined_standing"
    return True, None


def record_interruption(hunt: Hunt, tick: int, listing_id: str, kind: str) -> None:
    hunt.interruptions.append((tick, listing_id, kind))


def deterministic_ask_narrative(
    kind: AskKind,
    evaluation: Evaluation,
    comparison_landed_eur: Decimal | None,
) -> str:
    quote = evaluation.quote
    if kind == AskKind.GRAY_ROUTE:
        comparison = (
            f"; best legal alternative €{comparison_landed_eur}"
            if comparison_landed_eur is not None
            else ""
        )
        return (
            f"Gray route consent required: landed €{quote.landed_eur}, "
            f"ETA {quote.eta_ticks} days, estimated cancellation "
            f"{quote.p_cancel_est * 100}%{comparison}."
        )
    return (
        f"One-time cap extension requested: landed €{quote.landed_eur}; "
        f"observable trust {evaluation.trust}; colorway confirmed."
    )


def create_ask(
    hunt: Hunt,
    tick: int,
    kind: AskKind,
    evaluation: Evaluation,
    comparison_landed_eur: Decimal | None,
    sequence: int = 0,
) -> Ask:
    if hunt.pending_ask is not None and hunt.pending_ask.status in {
        "PENDING",
        "APPROVED",
    }:
        raise ValueError("an unresolved ask already exists")
    ask = Ask(
        id=ask_id(hunt.id, tick, sequence),
        hunt_id=hunt.id,
        tick=tick,
        kind=kind,
        quote=evaluation.quote,
        comparison_landed_eur=comparison_landed_eur,
        quote_hash=quote_hash(evaluation.quote),
        narrative=deterministic_ask_narrative(
            kind, evaluation, comparison_landed_eur
        ),
        status="PENDING",
    )
    hunt.pending_ask = ask
    record_interruption(hunt, tick, evaluation.quote.listing_id, kind.value)
    return ask


def approve_pending_ask(hunt: Hunt, supplied_quote_hash: str) -> Ask:
    ask = hunt.pending_ask
    if ask is None or ask.status != "PENDING":
        raise ValueError("no pending ask to approve")
    if ask.quote_hash != supplied_quote_hash:
        raise ValueError("ask approval does not match the quoted route")
    ask.status = "APPROVED"
    return ask


def decline_pending_ask(hunt: Hunt) -> Ask:
    ask = hunt.pending_ask
    if ask is None or ask.status != "PENDING":
        raise ValueError("no pending ask to decline")
    ask.status = "DECLINED"
    hunt.declined_asks[declined_key(ask.quote.listing_id, ask.kind)] = (
        ask.quote.landed_eur
    )
    return ask


def consume_approved_ask(hunt: Hunt, quote: RouteQuote, kind: AskKind) -> Ask:
    ask = hunt.pending_ask
    if ask is None or ask.status != "APPROVED":
        raise ValueError("purchase lacks an approved ask")
    if ask.kind != kind or ask.quote_hash != quote_hash(quote):
        raise ValueError("approved ask does not authorize this quote")
    ask.status = "CONSUMED"
    return ask
