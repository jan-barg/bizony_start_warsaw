# SolidHunt — Work Order Status

*Living status doc against `build-plan.md` / `agent-build-orders.md`. Updated: 2026-07-11 after final B acceptance audit. Verified suite: **239 passed, 0 xfailed**; matcher integration: **5 passed**.*

---

## Sync-point scoreboard

| Sync | Definition | Status |
|---|---|---|
| Stage 0 | Frozen contracts, fixtures, golden vectors | ✅ done (3-agent verified) |
| **S1** — "it buys something real" | world + engine(immediate) merged; generated-world BUY | ✅ done — real €133.63 receipt on seed 42 through API **and** UI |
| **S2** — "it watches and judges" | matcher merged · monitor loop real · UI on real SSE | 🟡 **engine complete** — real matcher and deterministic monitor are ready; **real monitor SSE + 20-seed evaluation remain** |
| S3 — "asks, geo, and proof" | narration live, Judge View, 200-seed eval, demo tag | ⬜ not started (narration module exists, unwired) |

---

## Per-person: done vs remaining

### Person A — world + eval
**Done:** WO-1 steps 1–8 — full simulator (catalog/vendors/pricing/geo/traps), ALLOW/NEVER oracle, dossier, determinism + hidden-label-guard tests, world-simulation docs.
**Remaining (unblocked NOW):**
- [ ] **WO-1 step 9 — `evalx/`** (still an empty `__init__.py`): runner with live invariant assertions, `GREEDY_STICKER` / `LANDED_NO_TRUST` baselines, §10.3 metric formulas (visibility-based encounters, `strike_quality`, paired regret/miss), `report.md` + CSV. *Immediate-mode evals can run against the real engine today; monitor rows slot in when B lands.*

### Person B — engine ✅ COMPLETE
**Done:** WO-2 end to end — exact customs/landed cost (V1–V8a), routes, observable trust/EV, stopping mathematics (V9), immediate and monitor policies, E0–E5 escalation, interruption budget, quote-exact asks (including approved within-band E3 purchase), alerts, orders, cancellation/retry/refunds, settlement epilogue, invariants 1–8, and byte-identical seed-42 replay (V10).

The Stage-0 matcher fallback is deleted; the real matcher is memoized per hunt/listing. Canonical seed-42 proof hashes and verification commands are in `reports/feat-engine.md`.

### Person C — api/ui
**Done:** WO-4 complete + beyond — §8 API + SSE, screens ①–④, hybrid backend (real worlds/dossier/`run_immediate`), coherent fixture story arcs, 3 user-reported bugs fixed (clarify loop convergence, dead navigation, phantom cancellation).
**In progress:** `origin/personc` adds the new aurora/composer homepage and animations; it still needs a clean rebase/build before merge and does not yet include the real S2 monitor wiring.
**Remaining:**
- [ ] **Unblocked NOW: real intake behind `POST /intake`** — swap the regex fake for D's `llm/intake.py` (warm-cache replay; regex parser demoted to `--no-llm` fallback); screenshot intake + real mandate diffs in the UI
- [ ] Wire D's `narrate.py` into ask/alert cards (replace API-side template strings)
- [ ] **S2 close-out:** point SSE at `run_monitor`, delete the fixture replayer — endpoint shapes don't change, 21 API contract tests are the safety net
- [ ] **S3:** Judge View (dossier vs receipts side-by-side, NEVER-vs-ALLOW split-screen), speed controls (server already supports `?tick_ms=`)

### Person D — matcher + LLM
**Done:** WO-3 complete, merged via PR #1 — matcher tiers 1–3 (57 tests), veto-only tier 4, OpenAI replay client + strict SQLite cache, deterministic intake gate + vision clarify loop, placeholder-safe narration, warmed cache artifact + manifest tooling.
**Remaining:**
- [x] Matcher memoization under `run_monitor` (per-hunt, per-listing; titles are static)
- [ ] **S3:** warm + commit the demo-seed cache for the final demo script (`scripts/warm_llm_cache.py` exists; needs the S3 sign-off pass)

---

## Sanctioned deviations on record

1. **LLM provider = OpenAI `gpt-5.6-terra`** (spec said Anthropic; `anthropic` dep removed) — accepted by merging PR #1.
2. Positive-EV gray routes and bounded over-cap offers now use deterministic, quote-exact asks; real LLM narration remains C/D integration work.
3. Monitor SSE still replays `fixtures/receipts_demo.jsonl` even though B's real `run_monitor` is ready — `/config` remains `backend: "hybrid"` until C switches the source.

## Order of operations from here

1. ✅ `feat/engine-s2` merged into `develop` at `481c409`; V1–V10 are green.
2. In parallel: **C wires real intake/narration and SSE → `run_monitor`**; **A builds `evalx`** with the 20-seed S2 run.
3. **S2 close-out:** delete the fixture replayer, run a browser demo of a fully real monitor hunt, and turn failures from the 20-seed evaluation into the B/D bug queue.
4. **S3:** Judge View, warm demo cache, 200-seed four-policy evaluation, feature freeze, `demo` tag on `main`, and two rehearsals (`--no-llm` and warmed cache).

**Never cut** (from §13.1): invariants, golden vectors, escalation ladder, `--no-llm` full pass, the dossier.
