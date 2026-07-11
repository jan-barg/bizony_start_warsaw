"""Deterministic world orchestration and portable artifact export (§4)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from ..core.config import Constants
from ..core.models import World, canonical_json
from .catalog import build_catalog
from .dossier import write_dossier
from .geo import generate_geo_promos
from .oracle import compute_oracle
from .pricing import generate_pricing
from .traps import inject_traps
from .vendors import build_listings, build_vendors


def write_world_artifacts(world: World, cfg: Constants, directory: Path | str = "worlds") -> dict[str, Path]:
    """Write canonical JSON, deterministic SQLite, and the judge dossier."""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"world_{world.seed}"
    json_path = stem.with_suffix(".json")
    sqlite_path = stem.with_suffix(".sqlite")
    dossier_path = stem.with_suffix(".md")
    payload = canonical_json(world) + "\n"
    json_path.write_text(payload, encoding="utf-8")

    temporary = sqlite_path.with_suffix(".sqlite.tmp")
    if temporary.exists():
        temporary.unlink()
    database = sqlite3.connect(temporary)
    try:
        database.execute("PRAGMA page_size=4096")
        database.execute("PRAGMA journal_mode=OFF")
        database.execute("PRAGMA synchronous=OFF")
        database.execute("CREATE TABLE world (seed INTEGER PRIMARY KEY, canonical_json TEXT NOT NULL)")
        database.execute("INSERT INTO world(seed, canonical_json) VALUES (?, ?)", (world.seed, payload.rstrip("\n")))
        database.commit()
    finally:
        database.close()
    os.replace(temporary, sqlite_path)
    write_dossier(world, cfg, dossier_path)
    return {"json": json_path, "sqlite": sqlite_path, "dossier": dossier_path}


def generate_world(seed: int, cfg: Constants) -> World:
    """Given an integer seed, produce the complete deterministic market history:
    catalog, vendors, middlemen, listings, price events, FX, coupons, geo promos,
    traps (with TrapRecords), and the oracle. Same (seed, cfg) ⇒ identical World.
    """
    products, aliases = build_catalog(seed, cfg)
    vendors, whitelist, middlemen = build_vendors(seed, cfg)
    listings = build_listings(seed, cfg, products, aliases, vendors)
    price_events, coupons, fx = generate_pricing(seed, cfg, products, vendors, listings)
    geo_promos = generate_geo_promos(seed, cfg, vendors, middlemen, listings, price_events)
    vendors, listings, price_events, coupons, geo_promos, traps = inject_traps(
        seed,
        cfg,
        products,
        aliases,
        vendors,
        whitelist,
        middlemen,
        listings,
        price_events,
        coupons,
        fx,
        geo_promos,
    )
    world = World(
        seed=seed,
        horizon=cfg.HORIZON,
        products=products,
        aliases=aliases,
        vendors=vendors,
        whitelist=whitelist,
        middlemen=middlemen,
        listings=listings,
        price_events=price_events,
        coupons=coupons,
        fx=fx,
        geo_promos=geo_promos,
        traps=traps,
        oracle={},
    )
    world = world.model_copy(update={"oracle": compute_oracle(world, cfg)})
    write_world_artifacts(world, cfg)
    return world
