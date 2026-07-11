# `feat/world` handoff report

## Work-order status

Completed Work Order 1 steps 1–8:

- `world/catalog.py`: 10 handcrafted and 30 generated products, kids twins, and aliases.
- `world/vendors.py`: configured vendor/middleman populations, exact-domain whitelist, assortments, and namespaced messy titles.
- `world/pricing.py`: per-listing mean-reverting price/stock/coupon streams, Bernoulli flash drops, stored `on_sale`, and per-pair FX walks with one float-to-Decimal boundary.
- `world/geo.py`: foreign storefront promo generation restricted to JP/US/UK lanes with an available middleman.
- `world/traps.py`: every configured §4.5 trap construction and one `TrapRecord` per instance; `MVP_WORLD` produces one record per configured type.
- `world/oracle.py`: policy-specific `ALLOW`/`NEVER` omniscient best buys without importing engine code.
- `world/dossier.py`: complete judge-facing trap log, market narrative, oracle table, and canonical fingerprint.
- `world/generate.py`: deterministic orchestration plus canonical JSON, deterministic SQLite, and dossier artifacts under `worlds/`.

Added `tests/test_world.py` for full/MVP shapes, namespace isolation, money-boundary checks, artifact determinism, SQLite round-trip, trap/dossier completeness, hidden-label guards, and the seeds 1–20 oracle gate.

Work Order 1 step 9 (`evalx`) is intentionally not started. The work order explicitly schedules it after S1, when the real engine branch is available.

## Deviations and contract findings

- No frozen `core/` or fixture files were changed.
- No governing spec deviation was required.
- No frozen-contract bug was found.
- The oracle implements an independent truth-side landed calculation so `dealhunter/world/` does not import `dealhunter/engine/`, as required by the ownership boundary.

## Sync-integrator notes

- `generate_world(seed, cfg)` writes `worlds/world_<seed>.json`, `.sqlite`, and `.md` as deterministic generated artifacts; `worlds/` is ignored by Git.
- Seed 42 full-world shape at handoff: 40 products, 25 vendors, 4 middlemen, 266 listings, 23,940 price rows, and 27 trap records.
- Existing untracked brand concept assets were present before this branch work and were not modified.
- `.gitignore` now excludes `.env` and `.env.*` while allowing a shareable `.env.example`.

## Acceptance commands

```bash
.venv/bin/pytest
.venv/bin/pytest tests/test_world.py
.venv/bin/python -c "from dealhunter.core.config import Constants; from dealhunter.world.generate import generate_world; generate_world(42, Constants())"
git diff --check
```

Handoff result: `27 passed, 1 deselected, 12 xfailed` (the xfails are the Stage-0 engine golden vectors and are expected until `feat/engine` lands).
