# SolidHunt — Work Order Status

*Living status doc against `build-plan.md` / `agent-build-orders.md`. Updated: 2026-07-11, after PR #1 (matcher-llm) merged. Suite on `develop`: **210 passed, 1 xfailed** (V9 — stopping rule, expected), 6 integration tests deselected in branch CI.*

---

## Sync-point scoreboard

| Sync | Definition | Status |
|---|---|---|
| Stage 0 | Frozen contracts, fixtures, golden vectors | ✅ done (3-agent verified) |
| **S1** — "it buys something real" | world + engine(immediate) merged; generated-world BUY | ✅ done — real €133.63 receipt on seed 42 through API **and** UI |
| **S2** — "it watches and judges" | matcher merged · monitor loop real · UI on real SSE | 🟡 **~⅔ done** — matcher merged (PR #1), hybrid API serves real worlds + real immediate; **monitor loop missing** |
| S3 — "asks, geo, and proof" | narration live, Judge View, 200-seed eval, demo tag | ⬜ not started (narration module exists, unwired) |

---

## Per-person: done vs remaining

### Person A — world + eval
**Done:** WO-1 steps 1–8 — full simulator (catalog/vendors/pricing/geo/traps), ALLOW/NEVER oracle, dossier, determinism + hidden-label-guard tests, world-simulation docs.
**Remaining (unblocked NOW):**
- [ ] **WO-1 step 9 — `evalx/`** (still an empty `__init__.py`): runner with live invariant assertions, `GREEDY_STICKER` / `LANDED_NO_TRUST` baselines, §10.3 metric formulas (visibility-based encounters, `strike_quality`, paired regret/miss), `report.md` + CSV. *Immediate-mode evals can run against the real engine today; monitor rows slot in when B lands.*

### Person B — engine ⚠️ CRITICAL PATH
**Done:** WO-2 steps 1–4 + immediate mode — customs (both rulesets, V1–V8a green), landed assembly, routes, trust/EV, Layer-1 gates + escalation ladder E0/E1/E4/E5, invariants 1–5 & 7, `run_immediate`.
**Remaining (everything else queues behind this):**
- [ ] `engine/stopping.py` — §5.7 stopping rule, `last_buy_tick = expires−1`, forcing day → **flips the last xfail (V9)**
- [ ] `engine/loop.py::run_monitor` — tick loop `start..expires−1`, `process_refunds` before each tick
- [ ] Real ask lifecycle — E2/E3 ask creation, quote-hash-bound single-use consent, clock pause (§6.2)
- [ ] Order ledger + cancellation draw + refunds + **settlement epilogue** (invariant 8)
- [ ] Unified interruption budget (ALERT + both ask kinds, one pool, per-(listing, kind) dedupe, `REASK_IMPROVEMENT`)
- [ ] Invariant 6 (V10 byte-identical determinism — currently skipped)
- [ ] Cleanup owed from PR #1: **delete the Stage-0 matcher fallback** in `policy.py` (dead code since the real matcher landed)

### Person C — api/ui
**Done:** WO-4 complete + beyond — §8 API + SSE, screens ①–④, hybrid backend (real worlds/dossier/`run_immediate`), coherent fixture story arcs, 3 user-reported bugs fixed (clarify loop convergence, dead navigation, phantom cancellation).
**Remaining:**
- [ ] **Unblocked NOW: real intake behind `POST /intake`** — swap the regex fake for D's `llm/intake.py` (warm-cache replay; regex parser demoted to `--no-llm` fallback); screenshot intake + real mandate diffs in the UI
- [ ] Wire D's `narrate.py` into ask/alert cards (replace API-side template strings)
- [ ] **At S2 (needs B):** point SSE at `run_monitor`, delete the fixture replayer — endpoint shapes don't change, 21 API contract tests are the safety net
- [ ] **S3:** Judge View (dossier vs receipts side-by-side, NEVER-vs-ALLOW split-screen), speed controls (server already supports `?tick_ms=`)

### Person D — matcher + LLM
**Done:** WO-3 complete, merged via PR #1 — matcher tiers 1–3 (57 tests), veto-only tier 4, OpenAI replay client + strict SQLite cache, deterministic intake gate + vision clarify loop, placeholder-safe narration, warmed cache artifact + manifest tooling.
**Post-merge integration checklist (integrator-authorized status update; all implementation work stays on `feat/matcher-llm`):**

**S2 — blocked until B's monitor branch lands on `develop`:**
- [ ] Under this work order's explicit branch-sync consent, fetch and merge the latest `origin/develop`; never merge B's feature branch directly or rebase shared history.
- [ ] Pair with B on matcher memoization under `run_monitor`: cache `MatchResult` once per `(hunt.id, listing.id)` for that monitor run; no module-global or cross-hunt state. B owns the engine implementation; D owns the behavioral gate.
- [ ] Prove one matcher/LLM evaluation per listing across ticks, isolation between hunts, deterministic `NullClient`/replay receipts, and tier-4 calls only for fuzzy gray cases.
- [ ] Verify B removed the Stage-0 matcher fallback from `policy.py`.
- [ ] Re-run seeds 1–5 (≥95% non-trap identity), every planted matcher trap, and the four alert-only flags; none may enter a BUY path.

**S3 — blocked until B's asks and C's API/UI wiring land on `develop`:**
- [ ] Verify real cached intake behind `POST /intake`, full accumulated-transcript clarify reparsing, digest-only screenshot storage/resolution, and sorted sensitive `brief.*`/`mandate.*` diffs. C owns API/UI implementation; D owns LLM contract verification.
- [ ] Preserve the governing `--no-llm` contract: intake returns 503 and the UI offers a structured form whose output still passes the deterministic sufficiency gate.
- [ ] Verify `narrate.py` supplies gray-route and over-cap ask/alert cards; hostile names, foreign numbers/placeholders, and imperative prose must fall back deterministically.
- [ ] Freeze seed 42 as the final demo story, then extend the reviewed manifest with every exact demo request plus text/screenshot sentinels, tier-4 choice/abstention, and both narration kinds.
- [ ] Obtain fresh human approval immediately before live OpenAI calls. Warm a temporary candidate, enforce semantic/post-validation checks, replay twice with sockets blocked, then replace `fixtures/llm_cache.sqlite` only after success.
- [ ] Rehearse seed 42 in the real browser once with `--no-llm` and once from the committed replay cache.

**Person D completion gate:**
- [ ] Latest `origin/develop` merged; full `pytest -q`, Ruff, and mypy green; hidden-label/dossier guards clean; cache replay byte-identical twice; browser story green.
- [ ] `reports/feat-matcher-llm.md` maps WO-3 tasks 1–7 plus these S2/S3 duties to code, tests, commands, results, cache hash, deviations, and commits.
- [ ] Audit `implementation-spec.md`, `build-plan.md`, `agent-build-orders.md`, and this file. Mark Person D done only when every row has passing evidence; otherwise leave the exact owner/blocker unchecked.
- [ ] Fetch and merge `origin/develop` once more, rerun every gate, review the final diff, then push exactly one `feat/matcher-llm` PR into `develop` when the user authorizes publication.

---

## Sanctioned deviations on record

1. **LLM provider = OpenAI `gpt-5.6-terra`** (spec said Anthropic; `anthropic` dep removed) — accepted by merging PR #1.
2. Engine treats positive-EV gray routes under `ASK` as unavailable-with-receipt (`gray_route_deferred`) until the real ask lifecycle lands — correct per §5.9, noted so nobody mistakes it for a bug.
3. Monitor SSE replays `fixtures/receipts_demo.jsonl` until B's slice lands — `/config` reports `backend: "hybrid"` with explicit real/fixture lists.

## Current integrated quality-gate blockers

These failures are present on `develop` before Person D's post-merge work. Person D does not absorb cross-owned fixes, but the final Person D PR cannot merge until the owners make the complete gate green.

- **Person A:** 5 Ruff failures (`world/oracle.py`, `world/traps.py`, `tests/test_world.py`) and 3 mypy failures (`world/pricing.py`, `world/oracle.py`).
- **Person B:** 3 mypy failures (`engine/customs.py`, `engine/landed.py`).
- **Person C:** 1 Ruff failure and 9 mypy failures in `api/app.py`.
- **Person D:** matcher/LLM-focused pytest, Ruff, and mypy gates are green on the synchronized branch.

## Order of operations from here

1. **B ships the monitor slice** (rescue option: launch it as a build agent from `agent-build-orders.md` WO-2 steps 5–7 if B is blocked).
2. In parallel: **C wires real intake**, **A builds `evalx`** on immediate mode.
3. **S2 close-out** (half-day, B+C+D together): SSE → `run_monitor`, delete fixture replayer + matcher fallback, unskip V10, 20-seed eval, browser demo of a fully real monitor hunt.
4. **S3:** narration on cards, Judge View, 200-seed eval + four-policy table, feature freeze, `demo` tag on `main`, rehearse twice (once `--no-llm`, once from warmed cache).

**Never cut** (from §13.1): invariants, golden vectors, escalation ladder, `--no-llm` full pass, the dossier.
