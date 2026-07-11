from decimal import Decimal as D
from pathlib import Path

import pytest

from dealhunter.core.enums import AccessTier, Action, OrderState
from dealhunter.core.models import GeoPromo, canonical_json
from dealhunter.engine.invariants import assert_order_invariants
from dealhunter.engine.ledger import (
    append_receipts,
    place_order,
    process_refunds,
    settle_outstanding_refunds,
)
from dealhunter.engine.policy import evaluate_tick
from dealhunter.llm.client import NullClient
from tests.test_policy import CFG, hunt, world


def chosen_evaluation():
    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert receipt.chosen is not None
    return receipt.chosen


def test_ordinary_order_confirms_and_sets_delivery():
    current = hunt()
    order = place_order(current, chosen_evaluation(), 0, world(), CFG)
    assert order.state == OrderState.CONFIRMED
    assert order.delivery_at_tick == order.quote.eta_ticks
    assert_order_invariants(current)


def test_ip_gated_cancellation_refunds_and_excludes_listing():
    current = hunt()
    selected = chosen_evaluation().model_copy(deep=True)
    selected.quote.access_tier = AccessTier.IP_GATED
    selected.quote.observation_geo = next(
        promo.viewer_geo
        for promo in world().geo_promos
        if promo.access_tier == AccessTier.STOREFRONT
    )
    w = world()
    promo = GeoPromo(
        id="g_cancel",
        listing_id=selected.quote.listing_id,
        viewer_geo=selected.quote.observation_geo,
        promo_sticker=D("1"),
        from_tick=0,
        to_tick=0,
        access_tier=AccessTier.IP_GATED,
        p_cancel=D("1"),
    )
    w = w.model_copy(update={"geo_promos": [*w.geo_promos, promo]})
    order = place_order(current, selected, 0, w, CFG)
    assert order.state == OrderState.CANCELLED_BY_MERCHANT
    assert selected.quote.listing_id in current.excluded_listings
    assert process_refunds(current, 2) == []
    receipts = process_refunds(current, 3)
    assert order.state == OrderState.REFUNDED
    assert receipts[0].action == Action.HOLD
    assert_order_invariants(current, complete=True)


def test_settlement_epilogue_handles_cancel_then_replacement():
    current = hunt()
    cancelled = chosen_evaluation().model_copy(deep=True)
    cancelled.quote.access_tier = AccessTier.IP_GATED
    cancelled.quote.observation_geo = next(
        promo.viewer_geo
        for promo in world().geo_promos
        if promo.access_tier == AccessTier.STOREFRONT
    )
    w = world()
    forced = GeoPromo(
        id="g_forced",
        listing_id=cancelled.quote.listing_id,
        viewer_geo=cancelled.quote.observation_geo,
        promo_sticker=D("1"),
        from_tick=5,
        to_tick=5,
        access_tier=AccessTier.IP_GATED,
        p_cancel=D("1"),
    )
    cancelled.quote.tick = 5
    w = w.model_copy(update={"geo_promos": [*w.geo_promos, forced]})
    first = place_order(current, cancelled, 5, w, CFG)
    assert first.refund_at_tick == 8
    candidate_receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    replacement = next(
        item
        for item in candidate_receipt.considered
        if item.quote.listing_id != cancelled.quote.listing_id
        and item.purchase_eligible
    )
    second = place_order(current, replacement, 6, w, CFG)
    assert second.state == OrderState.CONFIRMED
    receipts = settle_outstanding_refunds(current, 6)
    assert first.state == OrderState.REFUNDED
    assert receipts[-1].tick == 8
    assert_order_invariants(current, complete=True)


def test_jsonl_writer_uses_canonical_receipts(tmp_path: Path):
    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    path = tmp_path / "receipts.jsonl"
    append_receipts(path, [receipt])
    assert path.read_text().strip() == canonical_json(receipt)


def test_second_active_order_is_rejected():
    current = hunt()
    selected = chosen_evaluation()
    place_order(current, selected, 0, world(), CFG)
    with pytest.raises(AssertionError, match="invariant 8"):
        place_order(current, selected, 1, world(), CFG)
