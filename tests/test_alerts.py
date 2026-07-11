from decimal import Decimal as D

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import AskKind
from dealhunter.core.models import declined_key
from dealhunter.engine.alerts import (
    approve_pending_ask,
    can_interrupt,
    consume_approved_ask,
    create_ask,
    decline_pending_ask,
)
from tests.test_policy import hunt


CFG = Constants()


def evaluation():
    from tests.test_policy import world
    from dealhunter.engine.policy import evaluate_tick
    from dealhunter.llm.client import NullClient

    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert receipt.chosen is not None
    return receipt.chosen


def test_unified_budget_and_dedupe():
    current = hunt()
    current.interruptions = [(0, "listing-a", "ALERT"), (1, "listing-b", "OVER_CAP")]
    allowed, reason = can_interrupt(current, 2, "listing-c", "GRAY_ROUTE", CFG, D("80"))
    assert not allowed and reason == "interrupt_budget_exhausted"

    current.mandate.alert_budget_per_week = 5
    allowed, reason = can_interrupt(current, 3, "listing-a", "ALERT", CFG)
    assert not allowed and reason == "interrupt_deduped"


def test_decline_requires_material_improvement_before_reask():
    current = hunt()
    key = declined_key("listing-a", AskKind.GRAY_ROUTE)
    current.declined_asks[key] = D("80")
    assert can_interrupt(
        current, 10, "listing-a", AskKind.GRAY_ROUTE.value, CFG, D("76")
    ) == (False, "ask_declined_standing")
    assert can_interrupt(
        current, 10, "listing-a", AskKind.GRAY_ROUTE.value, CFG, D("75")
    ) == (True, None)


def test_ask_is_quote_exact_and_single_use():
    current = hunt()
    chosen = evaluation()
    ask = create_ask(current, 0, AskKind.GRAY_ROUTE, chosen, D("140"))
    with pytest.raises(ValueError, match="does not match"):
        approve_pending_ask(current, "wrong")
    approve_pending_ask(current, ask.quote_hash)
    consume_approved_ask(current, chosen.quote, AskKind.GRAY_ROUTE)
    assert ask.status == "CONSUMED"
    with pytest.raises(ValueError, match="lacks an approved"):
        consume_approved_ask(current, chosen.quote, AskKind.GRAY_ROUTE)


def test_decline_records_standing_price():
    current = hunt()
    chosen = evaluation()
    ask = create_ask(current, 0, AskKind.OVER_CAP, chosen, None)
    decline_pending_ask(current)
    assert ask.status == "DECLINED"
    assert current.declined_asks[
        declined_key(chosen.quote.listing_id, AskKind.OVER_CAP)
    ] == chosen.quote.landed_eur
