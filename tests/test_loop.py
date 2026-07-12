from decimal import Decimal as D

from dealhunter.core.enums import AccessTier, Action, Geo, GeoArb, HuntStatus, OrderState
from dealhunter.core.models import GeoPromo, MatchResult
from dealhunter.engine.loop import run_immediate, run_monitor
from dealhunter.llm.client import NullClient
from tests.test_policy import CFG, hunt, monitor_hunt, world


def test_immediate_buy_creates_confirmed_order():
    current = hunt()
    receipt = run_immediate(current, world(), CFG, NullClient())
    assert receipt.action == Action.BUY
    assert current.status == HuntStatus.PURCHASED
    assert len(current.orders) == 1
    assert current.orders[0].state == OrderState.CONFIRMED


def test_monitor_uses_improved_high_confidence_strategy():
    current = monitor_hunt(expires=3)
    receipts = run_monitor(current, world(), CFG, NullClient())
    primary = [receipt.action for receipt in receipts if not receipt.reasons[0].startswith("refund_")]
    assert primary == [Action.BUY]
    assert receipts[0].reasons[0] == "high_confidence_under_target"
    assert current.status == HuntStatus.PURCHASED
    assert current.orders[-1].state == OrderState.CONFIRMED


def test_monitor_rejects_immediate_mandate():
    current = hunt()
    try:
        run_monitor(current, world(), CFG, NullClient())
    except ValueError as error:
        assert "MONITOR" in str(error)
    else:
        raise AssertionError("run_monitor accepted an immediate mandate")


def test_monitor_receipts_are_byte_deterministic():
    from dealhunter.core.models import canonical_json

    first = run_monitor(monitor_hunt(expires=3), world(), CFG, NullClient())
    second = run_monitor(monitor_hunt(expires=3), world(), CFG, NullClient())
    assert [canonical_json(item) for item in first] == [
        canonical_json(item) for item in second
    ]


def test_monitor_prefers_safe_legal_route_over_gray_ask(monkeypatch):
    w = world()
    promo = GeoPromo(
        id="g_ip_loop",
        listing_id="l_v004_DD1391-100",
        viewer_geo=Geo.JP,
        promo_sticker=D("1000"),
        from_tick=0,
        to_tick=0,
        access_tier=AccessTier.IP_GATED,
        p_cancel=D("0"),
    )
    w = w.model_copy(update={"geo_promos": [*w.geo_promos, promo]})

    def only_jp_listing(listing, *args, **kwargs):
        if listing.id == "l_v004_DD1391-100":
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", only_jp_listing)
    current = monitor_hunt(cap="160", expires=1)
    current.mandate.geo_arbitrage = GeoArb.ASK
    receipts = run_monitor(current, w, CFG, NullClient())
    assert receipts[-1].action == Action.BUY
    assert receipts[-1].chosen is not None
    assert receipts[-1].chosen.quote.access_tier != AccessTier.IP_GATED
    assert current.pending_ask is None
    assert current.status == HuntStatus.PURCHASED


def test_immediate_cancellation_retries_once_and_settles_refund(monkeypatch):
    outcomes = iter([True, False])
    monkeypatch.setattr(
        "dealhunter.engine.ledger.merchant_cancels",
        lambda *args, **kwargs: next(outcomes),
    )
    current = hunt()
    receipt = run_immediate(current, world(), CFG, NullClient())
    assert receipt.id.endswith("_1")
    assert receipt.action == Action.BUY
    assert len(current.orders) == 2
    assert current.orders[0].state == OrderState.REFUNDED
    assert current.orders[1].state == OrderState.CONFIRMED
