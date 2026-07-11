"""Live safety assertions for the S1 immediate engine (spec §6.3)."""

from decimal import Decimal

from ..core.enums import AccessTier, Action, AskKind, GeoArb
from ..core.models import Hunt, Receipt, canonical_json, quote_hash


def _require(condition: bool, number: int, message: str) -> None:
    if not condition:
        raise AssertionError(f"invariant {number}: {message}")


def _matching_consumed_ask(hunt: Hunt, kind: AskKind, receipt: Receipt) -> bool:
    ask = hunt.pending_ask
    return bool(
        ask is not None
        and ask.kind == kind
        and ask.status == "CONSUMED"
        and receipt.chosen is not None
        and ask.quote_hash == quote_hash(receipt.chosen.quote)
    )


def assert_s1_invariants(receipt: Receipt, hunt: Hunt) -> None:
    """Assert invariants 1–5 and 7 on an emitted immediate receipt.

    S1 does not create asks, but quote-exact consumed-ask checks are included so
    later E2/E3 work cannot weaken the purchase boundary accidentally.
    """
    cap = hunt.mandate.cap_landed_eur
    band_limit = cap * (Decimal("1") + hunt.mandate.overcap_ask_band_pct)

    if receipt.action == Action.BUY:
        _require(receipt.chosen is not None, 1, "BUY has no chosen evaluation")
        chosen = receipt.chosen
        assert chosen is not None
        landed = chosen.quote.landed_eur

        if landed > cap:
            _require(
                landed <= band_limit
                and _matching_consumed_ask(hunt, AskKind.OVER_CAP, receipt),
                1,
                "over-cap BUY lacks an exact consumed OVER_CAP approval",
            )

        _require(
            not hunt.mandate.revoked and receipt.tick < hunt.mandate.expires_tick,
            2,
            "BUY occurred after revocation or expiry",
        )

        if chosen.quote.access_tier == AccessTier.IP_GATED:
            permitted = hunt.mandate.geo_arbitrage == GeoArb.ALLOW or (
                hunt.mandate.geo_arbitrage == GeoArb.ASK
                and _matching_consumed_ask(hunt, AskKind.GRAY_ROUTE, receipt)
            )
            _require(permitted, 3, "IP_GATED BUY lacks tactics permission")

        _require(
            chosen.quote.access_tier != AccessTier.VERIFIED_LOCAL,
            4,
            "VERIFIED_LOCAL quote was purchased",
        )
        _require(
            sum(
                (line.amount_eur for line in chosen.quote.line_items),
                Decimal("0"),
            )
            == landed,
            5,
            "BUY receipt lines do not sum to landed total",
        )

        if receipt.escalation_tier == "E0":
            _require(landed <= cap, 7, "automatic buy exceeded the cap")

    if receipt.action == Action.ASK and hunt.pending_ask is not None:
        if hunt.pending_ask.kind == AskKind.OVER_CAP:
            _require(
                hunt.pending_ask.quote.landed_eur <= band_limit,
                7,
                "OVER_CAP ask exceeded the configured band",
            )

    # Exercise canonical serialization at the assertion boundary. If a future
    # receipt contains an unsorted or unserializable field, fail during the run.
    canonical_json(receipt)
