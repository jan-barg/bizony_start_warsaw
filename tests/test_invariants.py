from decimal import Decimal as D

import pytest

from dealhunter.core.enums import AccessTier, Action, AskKind, GeoArb
from dealhunter.core.models import Ask, quote_hash
from dealhunter.engine.invariants import assert_s1_invariants
from dealhunter.engine.policy import evaluate_tick
from dealhunter.llm.client import NullClient
from tests.test_policy import CFG, hunt, world


def valid_pair():
    current_hunt = hunt()
    receipt = evaluate_tick(current_hunt, 0, world(), CFG, NullClient())
    assert receipt.action == Action.BUY
    return current_hunt, receipt


def test_valid_immediate_buy_satisfies_live_invariants():
    current_hunt, receipt = valid_pair()
    assert_s1_invariants(receipt, current_hunt)


def test_invariant_1_rejects_unapproved_over_cap_buy():
    current_hunt, receipt = valid_pair()
    chosen = receipt.chosen.model_copy(deep=True)
    assert chosen is not None
    over = current_hunt.mandate.cap_landed_eur + D("1.00")
    chosen.quote.line_items[0].amount_eur += over - chosen.quote.landed_eur
    chosen.quote.landed_eur = over
    bad = receipt.model_copy(update={"chosen": chosen})
    with pytest.raises(AssertionError, match="invariant 1"):
        assert_s1_invariants(bad, current_hunt)


def test_invariant_2_rejects_revoked_buy():
    current_hunt, receipt = valid_pair()
    current_hunt.mandate.revoked = True
    with pytest.raises(AssertionError, match="invariant 2"):
        assert_s1_invariants(receipt, current_hunt)


def test_invariant_3_rejects_unapproved_gray_buy():
    current_hunt, receipt = valid_pair()
    chosen = receipt.chosen.model_copy(deep=True)
    assert chosen is not None
    chosen.quote.access_tier = AccessTier.IP_GATED
    current_hunt.mandate.geo_arbitrage = GeoArb.ASK
    bad = receipt.model_copy(update={"chosen": chosen})
    with pytest.raises(AssertionError, match="invariant 3"):
        assert_s1_invariants(bad, current_hunt)


def test_invariant_4_rejects_verified_local_buy():
    current_hunt, receipt = valid_pair()
    chosen = receipt.chosen.model_copy(deep=True)
    assert chosen is not None
    chosen.quote.access_tier = AccessTier.VERIFIED_LOCAL
    bad = receipt.model_copy(update={"chosen": chosen})
    with pytest.raises(AssertionError, match="invariant 4"):
        assert_s1_invariants(bad, current_hunt)


def test_invariant_5_rejects_receipt_sum_mismatch():
    current_hunt, receipt = valid_pair()
    chosen = receipt.chosen.model_copy(deep=True)
    assert chosen is not None
    chosen.quote.landed_eur += D("0.01")
    bad = receipt.model_copy(update={"chosen": chosen})
    with pytest.raises(AssertionError, match="invariant 5"):
        assert_s1_invariants(bad, current_hunt)


def test_invariant_7_rejects_over_cap_ask_outside_band():
    current_hunt, receipt = valid_pair()
    chosen = receipt.chosen.model_copy(deep=True)
    assert chosen is not None
    chosen.quote.landed_eur = D("200.00")
    ask = Ask(
        id="a_h_42_1_0_0",
        hunt_id=current_hunt.id,
        tick=0,
        kind=AskKind.OVER_CAP,
        quote=chosen.quote,
        quote_hash=quote_hash(chosen.quote),
        narrative="test",
        status="PENDING",
    )
    current_hunt.pending_ask = ask
    ask_receipt = receipt.model_copy(
        update={"action": Action.ASK, "chosen": chosen, "escalation_tier": "E3"}
    )
    with pytest.raises(AssertionError, match="invariant 7"):
        assert_s1_invariants(ask_receipt, current_hunt)
