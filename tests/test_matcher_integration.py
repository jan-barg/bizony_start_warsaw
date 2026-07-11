from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import Action, GeoArb, HuntStatus, MatchFlag, Mode
from dealhunter.core.models import Brief, Hunt, Listing, Mandate, MatchResult, World
from dealhunter.engine.loop import run_monitor
from dealhunter.engine.matcher import match
from dealhunter.engine.policy import evaluate_tick
from dealhunter.llm.client import LLMClient, NullClient
from dealhunter.world.generate import generate_world


def _monitor_hunt(hunt_id: str) -> Hunt:
    return Hunt(
        id=hunt_id,
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=Decimal("43"),
        ),
        mandate=Mandate(
            mode=Mode.MONITOR,
            cap_landed_eur=Decimal("150"),
            geo_arbitrage=GeoArb.NEVER,
            expires_tick=3,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )


@pytest.mark.integration
def test_generated_worlds_meet_identity_and_matcher_trap_gate() -> None:
    correct = 0
    eligible = 0
    unflagged_traps: list[tuple[int, str, str]] = []
    expected_trap_flags = {
        "colorway": {MatchFlag.COLORWAY_CONFLICT, MatchFlag.COLORWAY_UNCONFIRMED},
        "gs_kids": {MatchFlag.KIDS_SIZING, MatchFlag.SIZE_AMBIGUOUS},
    }

    for seed in range(1, 6):
        world = generate_world(seed, Constants())
        products = {product.id: product for product in world.products}
        matcher_traps = {
            trap.listing_id: expected_trap_flags[trap.trap_type]
            for trap in world.traps
            if trap.trap_type in expected_trap_flags and trap.listing_id is not None
        }
        for listing in world.listings:
            result = match(
                listing,
                Brief(product_query="generated catalog", size_eu=listing.size_eu),
                world,
                NullClient(),
            )
            if listing.id in matcher_traps:
                if not matcher_traps[listing.id].intersection(result.flags):
                    trap_type = next(
                        trap.trap_type
                        for trap in world.traps
                        if trap.listing_id == listing.id and trap.trap_type in expected_trap_flags
                    )
                    unflagged_traps.append((seed, listing.id, trap_type))
                continue
            eligible += 1
            correct += result.style_code == products[listing.true_product_id].style_code

    assert eligible > 0
    accuracy = correct / eligible
    assert accuracy >= 0.95 and not unflagged_traps, (
        f"accuracy={accuracy:.4%}; unflagged_traps={unflagged_traps}"
    )


@pytest.mark.integration
def test_monitor_match_memo_is_scoped_to_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parent.parent
    world = World.model_validate_json((root / "fixtures" / "mini_world.json").read_text())
    calls: Counter[str] = Counter()

    def counted_match(
        listing: Listing,
        brief: Brief,
        candidate_world: World,
        llm: LLMClient,
    ) -> MatchResult:
        calls[listing.id] += 1
        return match(listing, brief, candidate_world, llm)

    monkeypatch.setattr("dealhunter.engine.policy.match", counted_match)

    run_monitor(_monitor_hunt("h_reused"), world, Constants(), NullClient())
    first_run_calls = calls.copy()
    assert first_run_calls
    assert set(first_run_calls.values()) == {1}

    # A restored/recreated run may reuse its deterministic hunt ID. Memoized
    # matcher results must not leak from the previous in-memory run.
    run_monitor(_monitor_hunt("h_reused"), world, Constants(), NullClient())
    assert calls == Counter({key: 2 for key in first_run_calls})


@pytest.mark.integration
@pytest.mark.parametrize(
    "flag",
    [
        MatchFlag.COLORWAY_CONFLICT,
        MatchFlag.COLORWAY_UNCONFIRMED,
        MatchFlag.LLM_MATCH_ONLY,
        MatchFlag.SIZE_AMBIGUOUS,
    ],
)
def test_every_alert_only_match_flag_blocks_policy_purchase(
    monkeypatch: pytest.MonkeyPatch, flag: MatchFlag
) -> None:
    root = Path(__file__).resolve().parent.parent
    world = World.model_validate_json((root / "fixtures" / "mini_world.json").read_text())
    hunt = Hunt(
        id="h_matcher_safety",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=Decimal("43"),
        ),
        mandate=Mandate(
            mode=Mode.IMMEDIATE,
            cap_landed_eur=Decimal("150"),
            expires_tick=10,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )

    def flagged_match(*args: object, **kwargs: object) -> MatchResult:
        return MatchResult(
            style_code="DD1391-100",
            colorway_confirmed=False,
            confidence=0.95,
            flags=[flag],
        )

    monkeypatch.setattr("dealhunter.engine.policy.match", flagged_match)
    receipt = evaluate_tick(hunt, 0, world, Constants(), NullClient())
    assert receipt.action != Action.BUY
    assert all(not item.purchase_eligible for item in receipt.considered)
