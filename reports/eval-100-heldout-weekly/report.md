# SolidHunt 100-run held-out timing evaluation

## Held-out result

SolidHunt completed **79 legitimate purchases** with **0 invalid purchases** and **21.0% misses**.

Among its 79 legitimate purchases, SolidHunt's mean price gap from the full-horizon optimum was **€7.66**. The casual checkout shopper completed 70 legitimate purchases with a conditional mean gap of **€16.22**.

When both strategies purchased, the shopper paid an average **€9.98 more than SolidHunt** (positive means SolidHunt was cheaper).

| Strategy | Purchases | Legitimate | Invalid | Miss rate | Mean gap | Median gap | P90 gap | Mean absolute timing gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SolidHunt improved monitor | 79 | 79 | 0 | 21.0% | €7.66 | €1.96 | €22.06 | 15.0 days |
| Casual checkout shopper (7-day) | 70 | 70 | 0 | 30.0% | €16.22 | €6.17 | €32.57 | 22.7 days |

The casual shopper's visible checkout subtotal understated true landed cost by **€7.30 on average**. It produced 6 purchases whose actual landed cost exceeded the stated budget.

## Behavioral hypothesis

`CASUAL_CHECKOUT_7D` is a synthetic, deliberately attentive regular-shopper baseline—not a claim based on observed consumer research:

- Checks every 7 days and once on the final day.
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

This sensitivity cohort stores data only; its comparison plot is generated in the primary held-out report.

## Reproduce

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --start-seed 101 --user-check-interval 7 --no-plots --output reports/eval-100-heldout-weekly
.venv/bin/pytest tests/test_eval.py
```
