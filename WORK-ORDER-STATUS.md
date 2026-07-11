# SolidHunt — Work Order Status

*Living status doc against `build-plan.md` / `agent-build-orders.md`. Updated: 2026-07-11 after final B acceptance and Person D's S2 integration correction. Verified suite: **239 passed, 0 xfailed**; extended matcher integration: **6 passed**; V10: **passed**.*

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
**Done:** WO-3 tasks 1–6 and the preliminary reviewed cache merged via PR #1 — matcher tiers 1–3 (57 tests), veto-only tier 4, OpenAI replay client + strict SQLite cache, deterministic intake gate + vision clarify loop, placeholder-safe narration, cache artifact + manifest tooling. **WO-3 task 7 remains open until the exact seed-42 S3 demo cache is warmed and committed.**
**Post-merge integration checklist (canonical remaining-work list; integrator-authorized status update; all implementation work stays on `feat/matcher-llm`):**

**S2 — B's monitor branch is merged; D integration verification in progress:**
- [x] Under this work order's explicit branch-sync consent, fetch and merge the latest `origin/develop`; B's completed engine slice arrived through `develop`, not a direct feature-branch merge.
- [x] Correct matcher memoization under `run_monitor`: a context-local cache stores `MatchResult` once per `(hunt.id, listing.id)` for one engine execution; no result leaks into another run with the same deterministic hunt ID.
- [x] Prove one matcher evaluation per listing across ticks, isolation between runs/hunts, deterministic `NullClient`/replay behavior, and tier-4 calls only for fuzzy gray cases (21 focused tests plus V10 green).
- [x] Verify B removed the Stage-0 matcher fallback from `policy.py`.
- [x] Re-run seeds 1–5 (96.952224% non-trap identity), every planted matcher trap (zero missed), and the four alert-only flags; none enters a BUY path.

**S3 — B's ask lifecycle is merged; blocked until C's API/UI wiring lands on `develop`:**
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
2. Positive-EV gray routes and bounded over-cap offers now use deterministic, quote-exact asks; real LLM narration remains C/D integration work.
3. Monitor SSE still replays `fixtures/receipts_demo.jsonl` even though B's real `run_monitor` is ready — `/config` remains `backend: "hybrid"` until C switches the source.

## Current integrated quality-gate blockers

These failures are present on `develop` before Person D's post-merge work. Person D does not absorb cross-owned fixes, but the final Person D PR cannot merge until the owners make the complete gate green.

- **Person A:** 5 Ruff failures (`world/oracle.py`, `world/traps.py`, `tests/test_world.py`) and 3 mypy failures (`world/pricing.py`, `world/oracle.py`).
- **Person B/D:** engine Ruff/mypy and run-isolation memo gates are green after D's S2 integration correction.
- **Person C:** 1 Ruff failure and 9 mypy failures in `api/app.py`.
- **Person D:** matcher/LLM-focused pytest, Ruff, and mypy gates are green on the synchronized branch.

## Order of operations from here

1. ✅ `feat/engine-s2` merged into `develop` at `481c409`; V1–V10 are green.
2. ✅ **B/D:** run-scoped `(hunt.id, listing.id)` memoization and D's extended integration gate are green.
3. **C/D:** wire real intake/narration and SSE → `run_monitor`; **A builds `evalx`** with the 20-seed S2 run.
4. **S2 close-out:** delete the fixture replayer, run a browser demo of a fully real monitor hunt, and turn failures from the 20-seed evaluation into the B/D bug queue.
5. **S3:** Judge View, warm demo cache, 200-seed four-policy evaluation, feature freeze, `demo` tag on `main`, and two rehearsals (`--no-llm` and warmed cache).

**Never cut** (from §13.1): invariants, golden vectors, escalation ladder, `--no-llm` full pass, the dossier.
