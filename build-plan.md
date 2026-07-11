# Deal Hunter — Build Flow & Branch Plan

*Companion to implementation-spec.md v1.3 (§ references point there). Four people, one weekend. The ordering rule: **contracts first, world and money-math in parallel, judgment on top, chrome last.***

---

## 0. The insight that makes 4-way parallelism work

Nothing downstream depends on the *world simulator being finished* — it depends on the **models in `core/` and the module signatures** (§1, §3). A hand-written 10-listing fixture world satisfies every consumer of `World` just as well as the generator does. So:

1. Freeze `core/` + fixtures together first (Phase 0).
2. Branch four ways against those contracts.
3. Merge only at sync points, where integration is a wiring task, not a negotiation.

```
Phase 0 (all 4, ~3h)          Phase 1 (parallel branches)            Sync points
┌─────────────────┐   ┌── feat/world        (A) ──────────┐
│ core/ models    │   ├── feat/engine       (B) ──────────┤──► S1: immediate mode E2E (CLI)
│ enums, config   ├──►├── feat/matcher-llm  (D) ──────────┤──► S2: monitor E2E + eval + real UI
│ rng, ids, money │   └── feat/api-ui       (C) ──────────┘──► S3: asks/geo/judge + 200-seed eval
│ stubs, fixtures │                                            then: freeze, rehearse, tag demo
└─────────────────┘
```

---

## Phase 0 — contracts on `main` (all four, first ~3 hours, no branches yet)

One commit series everyone watches land. Nothing here is speculative — it is §2/§3 of the spec typed out.

| Task | Owner | Content |
|---|---|---|
| Scaffold | C | `pyproject.toml`, pytest, ruff, `README` run instructions, `pytest -q` as the merge gate |
| `core/enums.py` + `core/models.py` | D | Every enum and Pydantic model from §3, **verbatim** — this is the API between all four branches |
| `core/money.py` + `core/config.py` | B | `Money`, quantization policy (§2.1), `Constants` dataclass with every §12 value |
| `core/rng.py` + `core/ids.py` | A | Seed derivation (§2.3), deterministic IDs (§2.4, incl. ask `<seq>`) |
| Module stubs | B | Empty-but-typed signatures: `generate_world(seed, cfg) -> World` · `import_charges(...)` · `routes(...)` · `assemble(...) -> RouteQuote` · `match(listing, brief) -> MatchResult` · `trust_score(...)` · `evaluate_tick(hunt, tick, world) -> Receipt` · `LLMClient` protocol + `NullClient` |
| Fixtures | C+A | `fixtures/mini_world.json` — handcrafted: 5 products, 4 vendors (1 UK non-IOSS, 1 JP that doesn't ship to PL, 1 whitelisted official), 1 middleman, ~8 listings incl. one bait + one wrong-colorway, 10 ticks of price events, static FX. Plus `fixtures/receipts_demo.jsonl` — ~30 fake receipts covering every Action, for UI dev |
| Golden-vector test file | B | §11 V1–V8a numbers as `xfail` tests — they flip to green as the engine lands |

**Rule from here on: `core/` is frozen.** A model change is a "contract PR" — posted in the group chat, reviewed by all four within the hour, rebased by everyone immediately. Anything else in `core/` after Phase 0 is a bug.

---

## Phase 1 — the four branches

Branch from the Phase-0 tip. Merge to `main` only at sync points (plus unblocker cherry-picks if someone is stuck waiting). Every merge keeps `pytest -q` green.

### `feat/world` — Person A (world + eval owner)

Build order (each step is testable without anyone else's code):

1. `world/catalog.py` + `world/vendors.py` — products, aliases, kids twins; vendors with `channel`, whitelist, middlemen with `intl_carrier` (§4.1–4.2)
2. `world/pricing.py` — mean-reverting walk, Bernoulli flash drops, `on_sale` flag, stock, coupons, FX walk; **float→integer-cents boundary** (§4.4). First determinism test: same seed twice ⇒ identical rows
3. `world/geo.py` + `world/traps.py` — geo promos (JP/US/UK vendors only), all §4.5 trap types, every trap appends a `TrapRecord`
4. `world/oracle.py` + `world/dossier.py` — ground-truth best buys (both `geo_arbitrage` variants), dossier renderer
5. **M1 gate:** `generate_world(42)` twice ⇒ byte-identical dump; dossier lists every planted trap
6. *(after S1, on this branch)* `evalx/` — runner + invariant assertions, `GREEDY_STICKER` / `LANDED_NO_TRUST` baselines, metric formulas (§10.3 as revised: visibility-based encounters, `strike_quality`, paired regret/miss), `report.md` generator

### `feat/engine` — Person B (the money path; owns `core/` arbitration)

Strict order — money before policy before timing, because each layer is the test harness for the next:

1. `engine/customs.py` — **both rulesets** (§5.3: `EU_2026_07` flat €3 *inside* the VAT base; `EU_2025_LEGACY`), `engine/landed.py` line-item assembly (§5.5) → **V1–V8a green** (M2). Works entirely off `mini_world.json`
2. `engine/routes.py` — route enumeration, base-quote-always-present, ETAs, feasibility by route *class* (§5.2, §5.4)
3. `engine/trust.py` — whitelist short-circuit, impersonation cap, additive score, **EV vs the cap reference** (§5.6)
4. `engine/policy.py` — Layer-1 gates in §5.8 order (incl. size gate, `OVER_CAP_FAR` / `OVER_CAP_BAND`), `purchase_eligible`, selection set S with gray-route removal, escalation ladder E0–E5 (§5.9), **immediate mode** + `ESCALATE_NONE_FOUND` → invariants 1–5, 7 green (M3)
5. `engine/stopping.py` + `engine/loop.py` — stopping rule with `last_buy_tick = expires−1`, forcing day, ask lifecycle with clock pause, order ledger + `process_refunds` + settlement epilogue, immediate-cancellation retry (§5.7, §6) → V9, V10, invariants 6, 8 (M6 core)
6. `engine/alerts.py` + `engine/ledger.py` — unified interruption budget, per-(listing, kind) dedupe, `declined_asks` re-ask rule; JSONL receipts

### `feat/matcher-llm` — Person D (floater)

Front-load the deterministic 80%; LLM calls are the last 20%:

1. `engine/matcher.py` tiers 1–2 — style-code extraction, normalization, size-system table, kids/condition markers, colorway tokens + aliases (§5.1). Pure functions, tested on `mini_world.json` titles
2. Tier 3 fuzzy + thresholds + `COLORWAY_CONFLICT`/`UNCONFIRMED` logic → M4 accuracy harness vs hidden labels
3. `llm/client.py` + `llm/cache.py` — `LLMClient`/`NullClient`, sqlite read-through cache keyed on pinned model version (§7.3). **Everything must pass with `NullClient` before any real API call is made**
4. `llm/intake.py` — deterministic sufficiency gate first (catalog dry-run, `INTAKE_MAX_CANDIDATES`), then the LLM parse + clarify loop on `IntakeSession`, mandate diff (§7.1)
5. `llm/adjudicate.py` (veto-only, `LLM_MATCH_ONLY`) + `llm/narrate.py` (placeholders for all untrusted strings, digit/imperative post-checks) (§7.2, §7.4)
6. *(at S2)* pair with B to wire matcher memoization into `evaluate_tick`

### `feat/api-ui` — Person C

Runs against fixtures until S2; swaps the data source, not the components:

1. `api/app.py` skeleton — all §8 endpoints returning fixture data; SSE stream that replays `receipts_demo.jsonl` on a timer
2. Screens ① + ② — intake box with NEEDS_INFO question chat, mandate-confirm card with diff rendering (§9)
3. Screen ③a immediate result (winner card, line-item receipt table, near-miss list) + ③b monitor dashboard (price chart w/ cap line + markers, event feed) — all from fixture receipts
4. Ask modal (both kinds: gray-route card, over-cap card with overage highlighted), clock-paused indicator, approve/decline; order/cancellation/refund cards
5. *(S2)* point at the real engine SSE; delete the fixture replayer
6. *(S3)* Screen ⑤ Judge View — dossier-vs-receipts side-by-side, NEVER-vs-ALLOW split-screen replay

---

## Sync points (merges to `main`, in this order)

**S1 — "it buys something real" (target: end of day 1).**
Merge order: `feat/world` → `feat/engine`. Then a 30-minute all-hands wiring session: CLI script `python -m dealhunter demo --seed 42 --immediate` runs intake-less (hardcoded brief) immediate mode on a *generated* world and prints a receipt with full landed math. This is the earliest possible proof the architecture holds; everything after is additive.

**S2 — "it watches and judges" (target: mid-day 2).**
Merge `feat/matcher-llm` (tiers 1–3 + NullClient minimum), then `feat/engine` monitor loop, then `feat/api-ui` pointed at real SSE. Gate: full monitor happy path in the browser on seed 42 — holds, one alert, a strike, receipts rendering. A starts `evalx` runs on 20 seeds the moment this merges; its failures are B's bug queue for the evening.

**S3 — "asks, geo, and proof" (target: mid-day 3 / Sunday noon).**
Merge asks/geo/cancellation UI, LLM narration + intake with real API + committed cache artifact, Judge View. Gate: the §12 demo script executes end-to-end **twice, identically** — once `--no-llm`, once from the warmed cache. A runs the 200-seed eval; the four-policy table goes in the deck.

**After S3: feature freeze.** Only bug fixes, dossier prose, and demo rehearsal. Tag `demo` on the rehearsed commit; the laptop that presents runs from that tag, offline, cache committed.

---

## Standing rules

- **Merge gate:** `pytest -q` green, including determinism tests. No red merges, no exceptions — a broken `main` stalls three people.
- **`core/` changes** = contract PR + all-hands ping + everyone rebases within the hour.
- **Unblockers:** if a branch needs one function from another branch early (e.g. engine needs `visible_quotes`), cherry-pick or pair for 20 minutes — don't merge whole branches off-schedule and don't copy-paste-fork the logic.
- **LLM spend:** nothing calls the real API until its `NullClient` path passes. All real calls go through the cache; the cache file is committed at S3 and is the demo's replay input (§7.3).
- **Behind schedule?** Pull the §13.1 descope ladder top-down. It's pre-agreed; nobody re-debates scope on Sunday.
- **Milestone map:** S1 ≈ M1+M2+M3 · S2 ≈ M4+M5+M6 (+M8 started) · S3 ≈ M7+M8+M9+M10.
