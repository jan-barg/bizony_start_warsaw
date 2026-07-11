from __future__ import annotations

from dealhunter.core.config import Constants
from dealhunter.core.enums import MatchFlag
from dealhunter.core.models import Brief
from dealhunter.engine.matcher import match
from dealhunter.llm.client import NullClient
from dealhunter.world.generate import generate_world

import pytest


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
