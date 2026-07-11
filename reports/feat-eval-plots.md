# `feat/eval-plots` handoff report

## Completed

- Added a streaming 100-seed evaluation runner under `dealhunter/evalx/`.
- Added the synthetic `CASUAL_CHECKOUT_3D` regular-shopper baseline plus the spec's daily greedy and landed-without-trust helpers.
- Added a projected target-world adapter so engine math can run across 90 ticks without repeatedly scanning unrelated listings; equivalence to the full immediate-engine receipt is tested.
- Added the full legitimate landed-price timeline and common full-horizon optimum for each run.
- Added exact price-gap decomposition: total = selection + timing.
- Added CSV, JSON, Markdown, and dependency-free SVG output using the presentation's SolidHunt green/black/white brand system and focus-mark lockup.
- Preserved the original strict-policy diagnostic on seeds 1–100, then used those seeds to select a safety-preserving improved policy.
- Generated untouched held-out seeds 101–200: 100 run rows, 9,000 timeline rows, one contact sheet, seven aggregate plots, and 100 detailed timeline plots.
- Added an outlier-resistant focused price-gap distribution, cumulative price-gap curve, and paired win/tie/loss view; all tail values remain explicitly reported.
- Added a weekly-shopper sensitivity run without weakening or replacing the primary attentive 3-day comparator.
- Added methodology documentation and deterministic artifact tests.

## Behavioral hypothesis

`CASUAL_CHECKOUT_3D` checks every three days, knows the correct target and size, considers direct-to-Poland offers, and buys the first cheapest visible checkout subtotal within budget. It counts goods, valid coupon, and direct shipping, but not customs/import VAT/handling, trust, forwarding, or geo tactics. It is explicitly a synthetic hypothesis, not measured consumer research.

## Algorithm improvement and held-out result

The original strict policy used `EV > 0` as a hard gate and forced on only the final day. It bought in 4 of 100 development runs. The improved policy:

- Keeps the hard cap and observable trust floor.
- Uses EV to rank safe candidates rather than treating an uncalibrated trust score as a literal probability gate.
- Buys high-confidence under-cap deals, observed lows, or a safe candidate in a declared final 14-day window.

Held-out seeds 101–200 against the attentive 3-day shopper:

- SolidHunt: 79 legitimate purchases, 0 invalid, 21 misses, 0 cap violations; mean gap €7.66.
- Shopper: 82 legitimate purchases, 0 invalid, 18 misses, 5 cap violations; mean gap €13.80.
- On 69 paired purchases, the shopper paid €7.36 more on average.

Against the weekly shopper, SolidHunt also wins coverage (79 versus 70) and mean gap (€7.66 versus €16.22).

`engine.run_monitor()` remains unimplemented, so this is still an evaluation policy using production route/money/customs/trust/EV components—not production monitor-loop output.

## Deviations and boundaries

- No frozen `core/` or fixture files were changed.
- No plotting dependency was added; SVG output uses the Python standard library.
- The evaluation removes source-template delivery deadlines to provide one comparable full 90-day timing horizon per seed.
- It uses one deterministic template per seed for exactly 100 paired runs. The runner can be extended to all three templates for 300 scenarios.
- Existing untracked `outputs/` and `presentation/` assets were not modified or staged.

## Files

- `docs/evaluation-strategy.md`
- `reports/eval-100/report.md`
- `reports/eval-100/data/{runs.csv,timelines.csv,summary.json}`
- `reports/eval-100/plots/{all-runs.svg,buy-timing.svg,price-gap-comparison.svg,outcomes.svg}`
- `reports/eval-100/plots/timelines/run-001.svg` … `run-100.svg`
- `reports/eval-100-heldout/` — primary held-out data, report, and plots
- `reports/eval-100-heldout-weekly/` — weekly sensitivity data and report
- `reports/eval-100-heldout/sensitivity.md`

## Acceptance commands

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --start-seed 101 --output reports/eval-100-heldout
.venv/bin/pytest tests/test_eval.py
.venv/bin/pytest
git diff --check
```

Handoff test result: `102 passed, 1 deselected, 1 xfailed`; the remaining xfail is the production monitor stopping vector.
