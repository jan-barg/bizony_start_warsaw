# `feat/eval-plots` handoff report

## Completed

- Added a streaming 100-seed evaluation runner under `dealhunter/evalx/`.
- Added the synthetic `CASUAL_CHECKOUT_3D` regular-shopper baseline plus the spec's daily greedy and landed-without-trust helpers.
- Added a projected target-world adapter so engine math can run across 90 ticks without repeatedly scanning unrelated listings; equivalence to the full immediate-engine receipt is tested.
- Added the full legitimate landed-price timeline and common full-horizon optimum for each run.
- Added exact price-gap decomposition: total = selection + timing.
- Added CSV, JSON, Markdown, and dependency-free branded SVG output.
- Generated and committed seeds 1–100: 100 run rows, 9,000 timeline rows, one contact sheet, four aggregate plots, and 100 detailed timeline plots.
- Added methodology documentation and deterministic artifact tests.

## Behavioral hypothesis

`CASUAL_CHECKOUT_3D` checks every three days, knows the correct target and size, considers direct-to-Poland offers, and buys the first cheapest visible checkout subtotal within budget. It counts goods, valid coupon, and direct shipping, but not customs/import VAT/handling, trust, forwarding, or geo tactics. It is explicitly a synthetic hypothesis, not measured consumer research.

## Critical finding

The 100-run result is diagnostic rather than positive pitch evidence:

- SolidHunt stopping-policy simulation: 4 legitimate purchases, 96 misses, 0 invalid purchases; conditional mean gap €14.02.
- Casual shopper: 82 legitimate purchases, 1 invalid purchase, 17 misses; conditional mean gap €10.53.
- Casual checkout understated actual landed cost by €2.62 on average and caused 3 actual cap overruns.

The high SolidHunt miss rate is consistent with the present checkpoint: `engine.run_monitor()` is still unimplemented, while the analysis combines implemented engine money/trust/EV layers with §5.7 timing inside `evalx`. Do not present these results as production monitor performance. They identify the next tuning/integration problem.

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

## Acceptance commands

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --output reports/eval-100
.venv/bin/pytest tests/test_eval.py
.venv/bin/pytest
git diff --check
```

Handoff test result: `101 passed, 1 deselected, 1 xfailed`; the remaining xfail is the production monitor stopping vector.
