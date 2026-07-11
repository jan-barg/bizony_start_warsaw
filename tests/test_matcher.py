from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.enums import Condition, MatchFlag
from dealhunter.core.models import Brief, Listing, World
from dealhunter.engine.matcher import match
from dealhunter.llm.client import NullClient


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


@pytest.fixture(scope="module")
def listing(world: World) -> Listing:
    return world.listings[0]


@pytest.fixture(scope="module")
def brief() -> Brief:
    return Brief(product_query="Nike Dunk Low", size_eu=Decimal("43"))


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Nike Dunk DD1391-100", "DD1391-100"),
        ("Nike Dunk DD 1391 100", "DD1391-100"),
        ("Nike Dunk DD-1391-100", "DD1391-100"),
        ("Nike Dunk DD–1391–100", "DD1391-100"),
        ("Nike Dunk DD—1391—100", "DD1391-100"),
        ("Nike Dunk DD‑1391‑100", "DD1391-100"),
        ("Nike Dunk DD‐1391‐100", "DD1391-100"),
        ("Nike Dunk [DD1391/100]", "DD1391-100"),
        ("sku:xxDD1391100yy", "DD1391-100"),
        ("Ｎｉｋｅ ＤＤ１３９１－１００", "DD1391-100"),
        ("🔥 NIKE DUNK LOW PANDA dd1391-100 🔥", "DD1391-100"),
        ("DD1391.100 authentic", "DD1391-100"),
        ("adidas Samba OG GW2288", "GW2288"),
        ("adidas Samba OG GW-2288", "GW2288"),
        ("adidas Samba OG G W 2 2 8 8", "GW2288"),
        ("New Balance 990v6 M990GL6", "M990GL6"),
        ("New-Balance 990 v6 m 990 gl 6", "M990GL6"),
        ("Nike Jordan DZ5485-612", "DZ5485-612"),
        ("Nike Jordan DZ 5485 612", "DZ5485-612"),
        ("Nike Dunk GS CW1590-100", "CW1590-100"),
        ("Nike Dunk Low White Black", "DD1391-100"),
        ("Nike Dunk Low biały czarny", "DD1391-100"),
        ("Nike Dunk Low weiss schwarz", "DD1391-100"),
        ("Nike Dunk Low ホワイト ブラック", "DD1391-100"),
        ("Nike Dunk Low Panda", "DD1391-100"),
        ("Nike Air Jordan 1 High Varsity Red Black", "DZ5485-612"),
        ("Air Jordan One High varsity-red by Nike", "DZ5485-612"),
        ("adidas cloud white core black Samba OG", "GW2288"),
        ("New Balance Made 990 v6 Grey", "M990GL6"),
        ("NB 990v6 szary", "M990GL6"),
        ("アディダス サンバ OG クラウドホワイト コアブラック", "GW2288"),
        ("Nike Dunk Low 🐼 EU43 brand new", "DD1391-100"),
    ],
)
def test_nasty_titles_resolve_identity(
    world: World,
    listing: Listing,
    brief: Brief,
    title: str,
    expected: str,
) -> None:
    result = match(listing.model_copy(update={"raw_title": title}), brief, world, NullClient())
    assert result.style_code == expected


def test_style_code_brand_conflict_is_unconfirmed(
    world: World, listing: Listing, brief: Brief
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Adidas Samba DD1391-100"}),
        brief,
        world,
        NullClient(),
    )
    assert result.style_code == "DD1391-100"
    assert result.confidence == 0.40
    assert not result.colorway_confirmed
    assert MatchFlag.BRAND_CODE_CONFLICT in result.flags


def test_style_code_color_conflict_beats_confirmation(
    world: World, listing: Listing, brief: Brief
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Nike DD1391-100 Varsity Red"}),
        brief,
        world,
        NullClient(),
    )
    assert result.style_code == "DD1391-100"
    assert not result.colorway_confirmed
    assert MatchFlag.COLORWAY_CONFLICT in result.flags


@pytest.mark.parametrize("marker", ["GS", "PS", "TD", "GG", "BG", "kids", "dziecięce"])
def test_kids_markers_are_flagged(
    world: World, listing: Listing, brief: Brief, marker: str
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": f"Nike Dunk Low Panda {marker}"}),
        brief,
        world,
        NullClient(),
    )
    assert MatchFlag.KIDS_SIZING in result.flags


@pytest.mark.parametrize("used", ["used", "pre-owned", "gebraucht", "używane", "中古"])
def test_used_condition_markers_conflict_with_new_brief(
    world: World, listing: Listing, brief: Brief, used: str
) -> None:
    result = match(
        listing.model_copy(
            update={"raw_title": f"Nike DD1391-100 {used}", "condition": Condition.USED}
        ),
        brief,
        world,
        NullClient(),
    )
    assert MatchFlag.CONDITION_MISMATCH in result.flags


def test_structured_size_is_authoritative(
    world: World, listing: Listing, brief: Brief
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Nike DD1391-100 EU 43", "size_eu": Decimal("44")}),
        brief,
        world,
        NullClient(),
    )
    assert MatchFlag.SIZE_MISMATCH in result.flags


def test_explicit_converted_size_can_confirm_structured_size(
    world: World, listing: Listing, brief: Brief
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Nike DD1391-100 US 9.5"}),
        brief,
        world,
        NullClient(),
    )
    assert MatchFlag.SIZE_AMBIGUOUS not in result.flags


@pytest.mark.parametrize("title", ["Nike DD1391-100 9.5", "Nike DD1391-100 UK 9.5"])
def test_ambiguous_or_conflicting_title_size_is_flagged(
    world: World, listing: Listing, brief: Brief, title: str
) -> None:
    result = match(listing.model_copy(update={"raw_title": title}), brief, world, NullClient())
    assert MatchFlag.SIZE_AMBIGUOUS in result.flags


def test_fuzzy_accept_without_color_evidence_is_unconfirmed(
    world: World, listing: Listing, brief: Brief
) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Nike Air Jordan One High"}),
        brief,
        world,
        NullClient(),
    )
    assert result.style_code == "DZ5485-612"
    assert MatchFlag.COLORWAY_UNCONFIRMED in result.flags
    assert not result.colorway_confirmed


def test_unrelated_title_is_rejected(world: World, listing: Listing, brief: Brief) -> None:
    result = match(
        listing.model_copy(update={"raw_title": "Vintage wool hiking boot brown"}),
        brief,
        world,
        NullClient(),
    )
    assert result.style_code is None
    assert result.confidence == 0.0


def test_mini_world_identity_is_perfect_and_color_trap_is_flagged(world: World) -> None:
    predictions: dict[str, str | None] = {}
    for candidate_listing in world.listings:
        candidate_brief = Brief(product_query="catalog", size_eu=candidate_listing.size_eu)
        result = match(candidate_listing, candidate_brief, world, NullClient())
        predictions[candidate_listing.id] = result.style_code

    expected = {
        candidate_listing.id: next(
            product.style_code
            for product in world.products
            if product.id == candidate_listing.true_product_id
        )
        for candidate_listing in world.listings
    }
    assert predictions == expected

    trap_listing = next(item for item in world.listings if item.id == "l_v002_M990GL6")
    trap_result = match(
        trap_listing,
        Brief(product_query="New Balance 990v6", size_eu=trap_listing.size_eu),
        world,
        NullClient(),
    )
    assert MatchFlag.COLORWAY_CONFLICT in trap_result.flags


def test_engine_matcher_does_not_reference_generator_truth_fields() -> None:
    source = (ROOT / "dealhunter" / "engine" / "matcher.py").read_text()
    forbidden = ("true_" + "product_id", "is_" + "bait", "is_" + "counterfeit", "p_" + "cancel")
    assert not any(name in source for name in forbidden)
