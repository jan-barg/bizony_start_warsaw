# feat/engine handoff

## Completed in the immediate-engine slice

- Versioned Polish customs calculation for `EU_2026_07` and `EU_2025_LEGACY`.
- Exact landed-cost assembly for direct and middleman routes, including FX,
  coupon validity, shipping, forwarding fees, customs, VAT, and handling.
- Deterministic route enumeration for base, storefront, IP-gated, and
  verified-local access rules.
- Observable vendor trust, whitelist/impersonation behavior, and cap-referenced
  expected value.
- Immediate E0/E1/E5 policy with hard gates, purchase eligibility, argmax-EV
  selection, gray-route removal/reselection, deterministic near misses, and
  canonical receipts.
- Live S1 assertions and violation tests for invariants 1–5 and 7.
- `run_immediate` and an offline generated-world seed-42 demo.
- Focused customs, landed, route, trust, policy, and immediate integration tests.

## Work outside B's completed scope

- Person A owns the multi-seed evaluation harness and reports.
- Person C owns switching API/UI monitor SSE from fixtures to `run_monitor`.
- Person C and D own real intake/narration wiring and the final warmed cache.
- Judge View and the final 200-seed evaluation remain S3 work.

## Integration notes

- Person D's real matcher is integrated and memoized per hunt/listing. The
  temporary Stage-0 fallback has been removed.
- `run_monitor` is complete and is ready to replace C's fixture SSE source.
- No engine module reads eval-only hidden world labels.
- No file under `dealhunter/core/` or `fixtures/` was changed.

## Stage-0 discrepancy

The V8 fixture test required more than 100 routes, but the frozen mini world has
exactly 90 valid listing/tick/route combinations: 60 direct, 20 JP base via the
single JP middleman, and 10 JP storefront-promo routes. The threshold was
corrected to `>= 90`; the receipt-sum assertion runs on every one of them. No
golden monetary value was changed.

## Verification

```bash
uv sync --extra dev
.venv/bin/pytest -q -ra
.venv/bin/python scripts/demo_immediate.py
```

The original S1 handoff had 66 passing tests and one expected V9 xfail. The
completed S2 branch verification is recorded below.

## S1 integration on `develop`

- Person A's world branch was merged before the engine branch.
- The demo now uses `generate_world(42, Constants())` and a hardcoded seed-42
  catalog brief (Nike Dunk Low `DD1391-100`, EU 42).
- The generated-world result is an E1 BUY at €133.63 with exact line items.
- Two sequential demo runs produced identical SHA-256:
  `a81174631adb82ad39513d098f8d0c9602f6dcbcbf58b97261c54fae75d5f18c`.

## S2 engine continuation

- Added the documented Beta-Binomial finite-horizon stopping rule, explicit
  least-squares trend heuristic, warm-up, deadline horizon, and forcing day.
- Completed E0–E5 policy, unified interruption budget, gray-route and over-cap
  asks, decline/re-ask behavior, and quote-exact HUMAN approval consumption.
- Added monitor pause/resume, append-only orders, deterministic cancellation
  outcomes behind the world boundary, same-tick immediate retry, refunds,
  settlement epilogue, canonical JSONL writing, and invariants 1–8 coverage.
- Added `scripts/demo_monitor.py` for deterministic seed-42 monitor replay.
  The replay emits 84 HOLD, 4 ALERT, and 1 BUY receipt (tick 88); two runs have
  identical SHA-256
  `f26aa0d5010d17d5461d966c984cab9458bd184bc9602c0c830ff491d77ce825`
  with D's real matcher. The real-matcher immediate replay is also identical at
  `311ec121fc088227e464a1e7b0ccff7b9acd9185e97af39abbdbd3d4fba256e3`.

Person D's matcher is integrated and memoized by `(world, hunt, listing, brief,
client type)`; the temporary pinned-style fallback has been removed. Person A's
evaluation harness remains external to B.

Static integration note: B-owned engine modules pass mypy. The latest merged
`develop` still reports unrelated type errors in API/world files and six Ruff
unused-import findings already recorded by Person D's handoff; they are not
modified from this engine branch.

Matcher integration note: D's original alert-only policy test required E5, but
the governing §5.8 order permits ALERT before E5. The integrated assertion now
checks the actual safety contract: no BUY and `purchase_eligible=False`.

## Final S2 verification (2026-07-11)

- Default suite twice: `238 passed, 5 deselected, 0 xfailed` on each run.
- Real-matcher integration suite: `5 passed`.
- V10 is a normal acceptance test, not skipped or integration-deselected. It
  compares two fresh seed-42 worlds and full 90-tick monitor receipt streams as
  bytes.
- `ruff check` passes for B-owned engine paths and V10; `mypy
  dealhunter/engine` passes for all 12 engine modules.
- Hidden-label and dossier-import guards are clean.
- `build-plan.md`, frozen core contracts, fixtures, and the two governing specs
  are unchanged relative to `origin/develop`.
- Immediate demo twice: identical SHA-256
  `311ec121fc088227e464a1e7b0ccff7b9acd9185e97af39abbdbd3d4fba256e3`.
- Monitor demo twice: identical SHA-256
  `f26aa0d5010d17d5461d966c984cab9458bd184bc9602c0c830ff491d77ce825`.
