"""Append-only receipt and order ledger behavior (spec §6.2)."""

from pathlib import Path

from ..core.config import Constants
from ..core.enums import Action, DecidedBy, HuntStatus, OrderState
from ..core.ids import receipt_id
from ..core.models import Evaluation, Hunt, Order, Receipt, World, canonical_json
from ..world.outcomes import merchant_cancels


ACTIVE_ORDER_STATES = {OrderState.PLACED, OrderState.CONFIRMED}


def append_receipts(path: Path, receipts: list[Receipt]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for receipt in receipts:
            handle.write(canonical_json(receipt))
            handle.write("\n")


def place_order(
    hunt: Hunt,
    evaluation: Evaluation,
    tick: int,
    world: World,
    cfg: Constants,
) -> Order:
    if evaluation.quote.listing_id in hunt.excluded_listings:
        raise ValueError("merchant-cancelled listing cannot be repurchased")
    if any(order.state in ACTIVE_ORDER_STATES for order in hunt.orders):
        raise AssertionError("invariant 8: a hunt already has an active order")
    order = Order(
        hunt_id=hunt.id,
        tick=tick,
        quote=evaluation.quote,
        state=OrderState.PLACED,
    )
    hunt.orders.append(order)
    if merchant_cancels(world, evaluation.quote):
        order.state = OrderState.CANCELLED_BY_MERCHANT
        order.refund_at_tick = tick + cfg.REFUND_TICKS
        hunt.excluded_listings.add(evaluation.quote.listing_id)
        hunt.status = HuntStatus.RUNNING
    else:
        order.state = OrderState.CONFIRMED
        order.delivery_at_tick = tick + evaluation.quote.eta_ticks
        hunt.status = HuntStatus.PURCHASED
    return order


def process_refunds(hunt: Hunt, tick: int) -> list[Receipt]:
    receipts: list[Receipt] = []
    due = sorted(
        (
            order
            for order in hunt.orders
            if order.state == OrderState.CANCELLED_BY_MERCHANT
            and order.refund_at_tick is not None
            and order.refund_at_tick <= tick
        ),
        key=lambda order: (order.refund_at_tick or 0, order.tick, order.quote.listing_id),
    )
    for sequence, order in enumerate(due):
        order.state = OrderState.REFUNDED
        receipts.append(
            Receipt(
                id=receipt_id(hunt.id, tick, 900 + sequence),
                hunt_id=hunt.id,
                tick=tick,
                action=Action.HOLD,
                decided_by=DecidedBy.CODE,
                reasons=[
                    f"refund_settled:{order.quote.listing_id}:{order.refund_at_tick}"
                ],
            )
        )
    return receipts


def settle_outstanding_refunds(hunt: Hunt, start_tick: int) -> list[Receipt]:
    receipts: list[Receipt] = []
    outstanding = [
        order
        for order in hunt.orders
        if order.state == OrderState.CANCELLED_BY_MERCHANT
        and order.refund_at_tick is not None
    ]
    if not outstanding:
        return receipts
    final_tick = max(order.refund_at_tick or start_tick for order in outstanding)
    for tick in range(start_tick, final_tick + 1):
        receipts.extend(process_refunds(hunt, tick))
    return receipts
