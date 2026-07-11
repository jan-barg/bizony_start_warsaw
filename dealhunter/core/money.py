"""Money primitives — implementation-spec.md §2.1. Frozen after Stage 0.

The three rules, mechanized:
- intermediate arithmetic at full Decimal precision (default context, prec=28);
- a line item is quantized to its currency exponent with ROUND_HALF_UP the
  moment it is finalized;
- a landed total is the arithmetic sum of already-quantized line items — a
  separately-computed total is never re-quantized.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .enums import Currency

CURRENCY_EXPONENT: dict[Currency, int] = {
    Currency.EUR: 2,
    Currency.PLN: 2,
    Currency.GBP: 2,
    Currency.USD: 2,
    Currency.JPY: 0,
}

_QUANTA: dict[int, Decimal] = {0: Decimal("1"), 2: Decimal("0.01")}


@dataclass(frozen=True)
class Money:
    amount: Decimal          # full precision until quantized
    currency: Currency


def quantize(amount: Decimal, currency: Currency = Currency.EUR) -> Decimal:
    """Quantize to the currency's exponent, ROUND_HALF_UP."""
    return amount.quantize(_QUANTA[CURRENCY_EXPONENT[currency]], rounding=ROUND_HALF_UP)


def q2(amount: Decimal) -> Decimal:
    """EUR line-item quantizer (2 dp, HALF_UP) — the workhorse."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_eur(amount_ccy: Decimal, currency: Currency, rate_eur_to_ccy: Decimal) -> Decimal:
    """Convert a vendor-currency amount to a quantized EUR value (§5.5):
    eur = q2(amount_ccy / rate), where rate is 'EUR{CCY}' (1 EUR = rate × ccy).
    """
    if currency == Currency.EUR:
        return q2(amount_ccy)
    return q2(amount_ccy / rate_eur_to_ccy)
