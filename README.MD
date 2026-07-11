<p align="center">
  <img src="assets/brand/solidhunt-logo.svg" alt="SolidHunt" width="560">
</p>

<p align="center"><strong>The deal hunter never sleeps.</strong></p>

SolidHunt is an agentic shopping assistant that watches a simulated market, compares true landed cost (EU customs incl. the July 2026 reform), rejects misleading offers, and buys only within a user-approved mandate. Solidgate hackathon case — no scraping, no real payments; the judgment and the provably-obeyed mandate are the product.

## Project documents

- [Product specification](dealfinder-spec.md) — what & why (v2.2)
- [Implementation specification](implementation-spec.md) — **governs** (v1.3, adversarially reviewed: 2 rounds vs Codex)
- [Build plan](build-plan.md) — human overview: phases, branches, sync points
- [Agent build orders](agent-build-orders.md) — **work orders for LLM build agents**, one self-contained brief per branch
- [Brand guidelines](BRAND_GUIDELINES.md)

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                 # Stage-0 suite: core + fixtures green, golden vectors xfail
python scripts/make_fixtures.py  # regenerates fixtures/ (frozen — don't, unless told to)
```

## Repo state: Stage 0 (tag `stage0`)

`dealhunter/core/` (models, enums, money, RNG, IDs, config) and `fixtures/` are the **frozen contracts** every branch codes against — changes only via contract PR at sync points. Engine/world/LLM modules are typed stubs carrying their §-references; golden vectors (spec §11) are committed as `xfail` tests that flip green as `feat/engine` lands.

Branches to cut from `stage0`: `feat/world` · `feat/engine` · `feat/matcher-llm` · `feat/api-ui` (see [agent-build-orders.md](agent-build-orders.md)).

## Brand assets

- `assets/brand/solidhunt-logo.svg` — primary scalable logo
- `assets/brand/solidhunt-logo.png` — presentation-ready logo on white
- `assets/brand/solidhunt-logo-transparent.png` — transparent raster logo

The product name is **SolidHunt**. The internal package and CLI namespace remains `dealhunter` until a dedicated code migration is completed.
