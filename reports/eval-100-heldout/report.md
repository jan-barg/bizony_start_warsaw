# SolidHunt 100-run held-out timing evaluation

## Held-out result

SolidHunt completed **79 legitimate purchases** with **0 invalid purchases** and **21.0% misses**.

Among its 79 legitimate purchases, SolidHunt's mean price gap from the full-horizon optimum was **€7.66**. The casual checkout shopper completed 82 legitimate purchases with a conditional mean gap of **€13.80**.

When both strategies purchased, the shopper paid an average **€7.36 more than SolidHunt** (positive means SolidHunt was cheaper).

| Strategy | Purchases | Legitimate | Invalid | Miss rate | Mean gap | Median gap | P90 gap | Mean absolute timing gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SolidHunt improved monitor | 79 | 79 | 0 | 21.0% | €7.66 | €1.96 | €22.06 | 15.0 days |
| Casual checkout shopper (3-day) | 82 | 82 | 0 | 18.0% | €13.80 | €4.02 | €28.95 | 17.8 days |

The casual shopper's visible checkout subtotal understated true landed cost by **€5.68 on average**. It produced 5 purchases whose actual landed cost exceeded the stated budget.

## Behavioral hypothesis

`CASUAL_CHECKOUT_3D` is a synthetic, deliberately attentive regular-shopper baseline—not a claim based on observed consumer research:

- Checks every 3 days and once on the final day.
- Is generously assumed to identify the correct target and size.
- Considers ordinary direct-to-Poland listings only.
- Compares goods, valid coupon, and quoted direct shipping in EUR.
- Does not calculate import VAT, customs duty, handling, forwarding, seller trust, or geo tactics.
- Buys the cheapest perceived subtotal at the first check where it fits the budget.

## SolidHunt policy status

`SOLIDHUNT_IMPROVED_MONITOR` uses the implemented production route enumeration, landed-cost math, customs, trust, and expected-value functions. The improved policy keeps hard mandate and trust gates, uses EV for ranking rather than as an uncalibrated probability gate, buys high-confidence under-cap deals or observed lows, and adds an explicit final-window fallback.

The production `engine.run_monitor()` entry point is still a stub at this repository checkpoint. These results must therefore be described as a **SolidHunt stopping-policy simulation**, not as production monitor-loop output. The plots and data use that label consistently.

## Cohort and benchmark

- Seeds 101–200; one deterministic hunt per seed.
- Policy parameters were fixed on seeds 1–100 before this held-out run.
- Full 90-day horizon for every run; source-template delivery deadlines are removed to isolate timing behavior.
- Geo arbitrage is `NEVER` for both strategies.
- The common optimum is the lowest legitimate fully landed price under the cap across all 90 days.
- Price gap is reported only for legitimate purchases. Invalid purchases and misses are separate outcomes, so a trap cannot appear as misleading “negative regret.”

## Files

- `data/runs.csv`: one row per paired run with purchases, prices, gaps, timing, validity, and traps.
- `data/timelines.csv`: all 9,000 daily market points and purchase markers.
- `data/summary.json`: machine-readable aggregates.
- `plots/all-runs.svg`: 10×10 contact sheet showing every complete timeline.
- `plots/timelines/run-001.svg` … `run-100.svg`: readable full timeline for every run.
- `plots/buy-timing.svg`: paired user-versus-SolidHunt purchase day.
- `plots/price-gap-comparison.svg`: Tukey box plots with sparse context points and explicit outlier counts.
- `plots/price-gap-cdf.svg`: cumulative share of purchases within each price gap.
- `plots/paired-outcomes.svg`: paired cheaper, tied, and more-expensive outcome counts.
- `plots/outcomes.svg`: legitimate purchases, invalid purchases, and misses.
- `plots/shopper-sensitivity.svg`: held-out comparison against 3-day and weekly shopper assumptions (when generated).

## Reproduce

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --start-seed 101 --user-check-interval 3 --output reports/eval-100-heldout
.venv/bin/pytest tests/test_eval.py
```
