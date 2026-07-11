"""Work Order 1 acceptance tests for deterministic world generation."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import Carrier, Channel, Currency, Geo
from dealhunter.core.models import World, canonical_json
from dealhunter.world.catalog import build_catalog
from dealhunter.world.generate import generate_world
from dealhunter.world.pricing import generate_pricing
from dealhunter.world.vendors import build_listings, build_vendors


@pytest.fixture()
def full_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    monkeypatch.chdir(tmp_path)
    return generate_world(42, Constants())


def test_full_market_shape(full_world: World) -> None:
    world = full_world
    assert len(world.products) == 40
    assert 6 <= len(world.aliases) <= 8
    assert len(world.vendors) == 25
    assert len(world.middlemen) == 4
    assert len(world.price_events) == len(world.listings) * world.horizon
    assert len(world.fx) == 4 * world.horizon
    assert {product.origin_country for product in world.products} <= {"VN", "CN", "ID"}
    assert sum(product.is_kids_version_of is not None for product in world.products) in {3, 4}

    counts = Counter(listing.vendor_id for listing in world.listings)
    assert all(6 <= counts[vendor.id] <= 14 for vendor in world.vendors)
    assert len(world.whitelist) == 3
    assert all(
        next(vendor for vendor in world.vendors if vendor.id == row.vendor_id).channel is Channel.OFFICIAL
        for row in world.whitelist
    )
    assert sum(vendor.geo is Geo.JP and Geo.PL not in vendor.ships_to for vendor in world.vendors) == 2
    assert sum(vendor.geo is Geo.US and Geo.PL not in vendor.ships_to for vendor in world.vendors) == 1
    assert {middleman.intl_carrier for middleman in world.middlemen} == {Carrier.POSTAL, Carrier.COURIER}


def test_prices_cross_float_boundary_once(full_world: World) -> None:
    vendors = {vendor.id: vendor for vendor in full_world.vendors}
    listings = {listing.id: listing for listing in full_world.listings}
    for event in full_world.price_events:
        currency = vendors[listings[event.listing_id].vendor_id].currency
        if currency is Currency.JPY:
            assert event.sticker == event.sticker.to_integral_value()
        else:
            assert event.sticker * 100 == (event.sticker * 100).to_integral_value()
        assert event.stock >= 0
    assert any(event.on_sale for event in full_world.price_events)
    assert any(event.coupon_id for event in full_world.price_events)


def test_trap_log_and_dossier_are_complete(full_world: World) -> None:
    cfg = Constants()
    assert Counter(trap.trap_type for trap in full_world.traps) == Counter(cfg.TRAP_COUNTS)
    assert len(full_world.traps) >= 18
    assert all(trap.explanation and trap.correct_behavior for trap in full_world.traps)
    dossier = Path("worlds/world_42.md").read_text()
    for trap in full_world.traps:
        assert f"`{trap.trap_type}`" in dossier
        assert trap.explanation in dossier


def test_generation_and_all_artifacts_are_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    first_world = generate_world(42, Constants())
    first = {
        path.name: hashlib.sha256(path.read_bytes()).digest()
        for path in Path("worlds").iterdir()
    }
    second_world = generate_world(42, Constants())
    second = {
        path.name: hashlib.sha256(path.read_bytes()).digest()
        for path in Path("worlds").iterdir()
    }
    assert canonical_json(first_world) == canonical_json(second_world)
    assert first == second

    database = sqlite3.connect("worlds/world_42.sqlite")
    try:
        payload = database.execute("SELECT canonical_json FROM world WHERE seed = 42").fetchone()[0]
    finally:
        database.close()
    assert canonical_json(World.model_validate_json(payload)) == canonical_json(first_world)


def test_mvp_world_has_one_of_every_trap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Constants().mvp_world()
    world = generate_world(7, cfg)
    assert (len(world.products), len(world.vendors), len(world.middlemen)) == (12, 10, 2)
    assert Counter(trap.trap_type for trap in world.traps) == Counter({key: 1 for key in cfg.TRAP_COUNTS})
    assert {promo.access_tier.value for promo in world.geo_promos} >= {
        "STOREFRONT", "IP_GATED", "VERIFIED_LOCAL",
    }


def test_namespace_isolation_when_vendor_is_added() -> None:
    cfg_ten = Constants().mvp_world()
    cfg_eleven = Constants(
        N_PRODUCTS_HANDCRAFTED=cfg_ten.N_PRODUCTS_HANDCRAFTED,
        N_PRODUCTS_GENERATED=cfg_ten.N_PRODUCTS_GENERATED,
        N_VENDORS=11,
        N_MIDDLEMEN=cfg_ten.N_MIDDLEMEN,
        TRAP_COUNTS=cfg_ten.TRAP_COUNTS,
    )
    products, aliases = build_catalog(19, cfg_ten)
    vendors_ten, _, _ = build_vendors(19, cfg_ten)
    vendors_eleven, _, _ = build_vendors(19, cfg_eleven)
    listings_ten = build_listings(19, cfg_ten, products, aliases, vendors_ten)
    listings_eleven = build_listings(19, cfg_eleven, products, aliases, vendors_eleven)
    prices_ten, _, _ = generate_pricing(19, cfg_ten, products, vendors_ten, listings_ten)
    prices_eleven, _, _ = generate_pricing(19, cfg_eleven, products, vendors_eleven, listings_eleven)
    shared = {listing.id for listing in listings_ten} & {listing.id for listing in listings_eleven}
    left = [row for row in prices_ten if row.listing_id in shared]
    right = [row for row in prices_eleven if row.listing_id in shared]
    assert left == right


def test_oracle_answers_at_least_ninety_percent_of_seed_sweep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Constants()
    answers = []
    for seed in range(1, 21):
        world = generate_world(seed, cfg)
        answers.extend(answer.allow is not None for answer in world.oracle.values())
    assert sum(answers) / len(answers) >= 0.90


def test_hidden_truth_and_dossier_never_leak_into_runtime_modules() -> None:
    root = Path(__file__).resolve().parent.parent
    forbidden_labels = ("is_" + "bait", "is_" + "counterfeit", "true_" + "product_id", "p_" + "cancel")
    for folder in (root / "dealhunter" / "engine", root / "dealhunter" / "llm"):
        for source in folder.glob("*.py"):
            text = source.read_text()
            # Hidden labels are forbidden as identifiers. The public
            # RouteQuote estimate ending in ``_est`` is intentionally legal.
            assert not any(
                re.search(rf"\b{re.escape(label)}\b", text)
                for label in forbidden_labels
            ), source
            assert "world.dossier" not in text and "world import dossier" not in text
