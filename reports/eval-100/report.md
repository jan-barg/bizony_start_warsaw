# SolidHunt 100-run timing evaluation

## Critical finding

The current SolidHunt stopping-policy simulation purchased in only **4 of 100 runs** and missed **96.0%**. This is not pitch-ready evidence of monitor performance; it is a concrete diagnostic showing that the incomplete S1 monitor path needs implementation/tuning before performance claims are made.

Among its 4 legitimate purchases, SolidHunt's mean price gap from the full-horizon optimum was **€14.02**. The casual checkout shopper completed 82 legitimate purchases with a conditional mean gap of **€10.53**.

When both strategies purchased, the shopper paid an average **€2.57 more than SolidHunt** (positive means SolidHunt was cheaper).

| Strategy | Purchases | Legitimate | Invalid | Miss rate | Mean gap | Median gap | P90 gap | Mean absolute timing gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SolidHunt eval monitor | 4 | 4 | 0 | 96.0% | €14.02 | €11.31 | €31.15 | 40.0 days |
| Casual checkout shopper | 83 | 82 | 1 | 17.0% | €10.53 | €3.34 | €29.89 | 20.5 days |

The casual shopper's visible checkout subtotal understated true landed cost by **€2.62 on average**. It produced 3 purchases whose actual landed cost exceeded the stated budget.

## Behavioral hypothesis

`CASUAL_CHECKOUT_3D` is a synthetic, deliberately attentive regular-shopper baseline—not a claim based on observed consumer research:

- Checks every three days and once on the final day.
- Is generously assumed to identify the correct target and size.
- Considers ordinary direct-to-Poland listings only.
- Compares goods, valid coupon, and quoted direct shipping in EUR.
- Does not calculate import VAT, customs duty, handling, forwarding, seller trust, or geo tactics.
- Buys the cheapest perceived subtotal at the first check where it fits the budget.

## SolidHunt policy status

`SOLIDHUNT_EVAL_MONITOR` uses the implemented production route enumeration, landed-cost math, customs, trust, and expected-value functions. Its timing decision is the normative stopping rule from implementation-spec §5.7, implemented in `evalx` for analysis.

The production `engine.run_monitor()` entry point is still a stub at this repository checkpoint. These results must therefore be described as a **SolidHunt stopping-policy simulation**, not as production monitor-loop output. The plots and data use that label consistently.

## Cohort and benchmark

- Seeds 1–100; one deterministic hunt per seed.
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
- `plots/price-gap-comparison.svg`: every legitimate price gap with mean and median.
- `plots/outcomes.svg`: legitimate purchases, invalid purchases, and misses.

## Reproduce

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --solid-policy spec --output reports/eval-100
.venv/bin/pytest tests/test_eval.py
```
