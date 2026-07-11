from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import Action, HuntStatus, MatchFlag, Mode
from dealhunter.core.models import Brief, Hunt, Mandate, MatchResult, World
from dealhunter.engine.matcher import match
from dealhunter.engine.policy import evaluate_tick
from dealhunter.llm.client import NullClient
from dealhunter.world.generate import generate_world


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
