# Deal Hunter

Agentic deal-hunting shopping assistant over a seeded, deterministic, simulated market — Solidgate hackathon case. No scraping, no real payments; the judgment, the landed-cost math (EU customs incl. the July 2026 reform), and the provably-obeyed spending mandate are the product.

## Documents

| File | What |
|---|---|
| `dealfinder-spec.md` | Product spec v2.2 — what & why |
| `implementation-spec.md` | **Implementation spec v1.3 — governs.** Adversarially reviewed (2 rounds vs Codex) |
| `build-plan.md` | Human overview: phases, branches, sync points |
| `agent-build-orders.md` | **Work orders for LLM build agents** — one self-contained brief per branch |

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                 # Stage-0 suite: core + fixtures green, golden vectors xfail
python scripts/make_fixtures.py  # regenerates fixtures/ (frozen — don't, unless told to)
```

## Repo state: Stage 0 (tag `stage0`)

`dealhunter/core/` (models, enums, money, RNG, IDs, config) and `fixtures/` are the **frozen contracts** every branch codes against — changes only via contract PR at sync points. Engine/world/LLM modules are typed stubs carrying their §-references; golden vectors (spec §11) are committed as `xfail` tests that flip green as `feat/engine` lands.

Branches to cut from `stage0`: `feat/world` · `feat/engine` · `feat/matcher-llm` · `feat/api-ui` (see `agent-build-orders.md`).
