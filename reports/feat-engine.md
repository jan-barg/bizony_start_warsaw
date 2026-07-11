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

## Intentionally deferred

- Monitor stopping and V9.
- E2 gray-route and E3 over-cap ask creation/approval/decline lifecycle.
- Alerts and the unified interruption budget.
- Order cancellation, refund processing, and settlement epilogue.
- Full monitor-loop determinism V10 and invariants tied to asks/orders.

The immediate policy treats a positive-EV IP-gated route under `GeoArb.ASK` as
unavailable, records `gray_route_deferred`, and reselects a legal route. It never
silently buys the gray route.

## Integration notes

- `engine/matcher.py` is owned by Person D and remains a Stage-0 stub. Policy
  calls it normally and temporarily falls back only when it raises
  `NotImplementedError`, and only for a brief with a pinned style code matching
  the deterministic listing-id suffix. Remove that fallback after D's matcher
  is integrated at S2.
- `run_monitor` remains a typed stub and immediate policy rejects monitor mode
  explicitly.
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

At branch handoff, 66 tests passed and only V9 was xfailed because monitor
stopping is the next planned slice.

## S1 integration on `develop`

- Person A's world branch was merged before the engine branch.
- The demo now uses `generate_world(42, Constants())` and a hardcoded seed-42
  catalog brief (Nike Dunk Low `DD1391-100`, EU 42).
- The generated-world result is an E1 BUY at €133.63 with exact line items.
- Two sequential demo runs produced identical SHA-256:
  `a81174631adb82ad39513d098f8d0c9602f6dcbcbf58b97261c54fae75d5f18c`.
