"""Execution entry points; immediate mode is implemented (spec §6).
Owner: feat/engine (Work Order 2). Signatures are frozen; bodies are not.

Normative reminders:
- Monitor: for tick in start..expires−1: process_refunds(tick); evaluate_tick(...).
- ASK pauses the world clock; approval is quote-exact and single-use (CONSUMED).
- Settlement epilogue: after terminal status, keep ticking process_refunds only
  until no CANCELLED_BY_MERCHANT order awaits refund (invariant 8).
- Immediate: one evaluate_tick; on merchant cancellation re-run once same tick
  with the listing excluded, else ESCALATE_NONE_FOUND with monitor handoff.
"""
from __future__ import annotations

from ..core.config import Constants
from ..core.enums import Action, HuntStatus, Mode, OrderState
from ..core.ids import receipt_id
from ..core.models import Hunt, Receipt, World
from ..llm.client import LLMClient
from .invariants import assert_order_invariants
from .ledger import place_order, process_refunds, settle_outstanding_refunds
from .policy import _match_memo_scope, evaluate_tick


@_match_memo_scope()
def run_monitor(hunt: Hunt, world: World, cfg: Constants, llm: LLMClient) -> list[Receipt]:
    if hunt.mandate.mode != Mode.MONITOR:
        raise ValueError("run_monitor requires a MONITOR mandate")
    if hunt.pending_ask is not None and hunt.pending_ask.status == "PENDING":
        hunt.status = HuntStatus.PENDING_ASK
        return []

    resumed_ask = hunt.pending_ask
    if resumed_ask is not None and resumed_ask.status in {"APPROVED", "DECLINED"}:
        start_tick = resumed_ask.tick
        hunt.status = HuntStatus.RUNNING
    else:
        start_tick = hunt.start_tick
        hunt.status = HuntStatus.RUNNING

    receipts: list[Receipt] = []
    final_processed_tick = start_tick
    for tick in range(start_tick, hunt.mandate.expires_tick):
        final_processed_tick = tick
        receipts.extend(process_refunds(hunt, tick))
        if hunt.mandate.revoked:
            hunt.status = HuntStatus.REVOKED
            break

        receipt = evaluate_tick(hunt, tick, world, cfg, llm)
        receipts.append(receipt)

        if resumed_ask is not None and resumed_ask.status == "DECLINED":
            if hunt.pending_ask is resumed_ask:
                hunt.pending_ask = None
            resumed_ask = None

        if receipt.action == Action.ASK:
            hunt.status = HuntStatus.PENDING_ASK
            return receipts
        if receipt.action == Action.BUY:
            if receipt.chosen is None:
                raise AssertionError("BUY receipt has no chosen evaluation")
            order = place_order(hunt, receipt.chosen, tick, world, cfg)
            assert_order_invariants(hunt)
            if order.state == OrderState.CANCELLED_BY_MERCHANT:
                receipt.reasons.append(
                    f"merchant_cancelled:{order.quote.listing_id}:refund_at:{order.refund_at_tick}"
                )
                continue
            break
    else:
        if hunt.status == HuntStatus.RUNNING:
            hunt.status = HuntStatus.EXPIRED

    receipts.extend(settle_outstanding_refunds(hunt, final_processed_tick + 1))
    assert_order_invariants(hunt, complete=True)
    return receipts


@_match_memo_scope()
def run_immediate(hunt: Hunt, world: World, cfg: Constants, llm: LLMClient) -> Receipt:
    """Run one immediate decision, including cancellation retry and settlement."""
    if hunt.mandate.mode != Mode.IMMEDIATE:
        raise ValueError("run_immediate requires an IMMEDIATE mandate")
    tick = hunt.start_tick
    receipt = evaluate_tick(hunt, tick, world, cfg, llm)
    if receipt.action == Action.ASK:
        hunt.status = HuntStatus.PENDING_ASK
        return receipt
    if receipt.action != Action.BUY:
        settle_outstanding_refunds(hunt, tick)
        assert_order_invariants(hunt, complete=True)
        return receipt
    if receipt.chosen is None:
        raise AssertionError("BUY receipt has no chosen evaluation")

    order = place_order(hunt, receipt.chosen, tick, world, cfg)
    assert_order_invariants(hunt)
    if order.state != OrderState.CANCELLED_BY_MERCHANT:
        return receipt

    cancellation_reason = (
        f"merchant_cancelled:{order.quote.listing_id}:refund_at:{order.refund_at_tick}"
    )
    retry = evaluate_tick(hunt, tick, world, cfg, llm)
    retry.id = receipt_id(hunt.id, tick, 1)
    retry.reasons.insert(0, cancellation_reason)
    if retry.action == Action.BUY and retry.chosen is not None:
        replacement = place_order(hunt, retry.chosen, tick, world, cfg)
        if replacement.state == OrderState.CANCELLED_BY_MERCHANT:
            retry = retry.model_copy(
                update={
                    "action": Action.ESCALATE_NONE_FOUND,
                    "chosen": None,
                    "escalation_tier": "E5",
                    "reasons": [
                        cancellation_reason,
                        f"replacement_cancelled:{replacement.quote.listing_id}",
                        "switch_to_monitor",
                    ],
                }
            )
    elif retry.action != Action.ASK:
        retry.action = Action.ESCALATE_NONE_FOUND
        retry.escalation_tier = "E5"
        retry.reasons.append("switch_to_monitor")

    settle_outstanding_refunds(hunt, tick + 1)
    assert_order_invariants(hunt, complete=True)
    return retry
