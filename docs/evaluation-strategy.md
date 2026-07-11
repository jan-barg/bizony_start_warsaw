# Multi-run buying-strategy evaluation

This document specifies the reproducible evaluation used to compare SolidHunt's timing policy with a synthetic regular-shopper baseline. The executable implementation is in [`dealhunter/evalx/`](../dealhunter/evalx/).

## Purpose

For each seeded 90-day market, the evaluation answers:

1. What was the lowest legitimate, fully landed price available during the complete horizon?
2. On which day did each strategy buy?
3. What did each strategy actually pay after shipping, customs, VAT, handling, forwarding, and valid coupons?
4. How much higher was that price than the best possible price?
5. Did the strategy buy a legitimate product, buy a trap, exceed the actual budget, or miss entirely?

Policy development uses seeds 1–100. The default pitch cohort uses untouched seeds 101–200 and one deterministic hunt per seed, producing 100 paired held-out runs and 9,000 daily timeline points.

## Important status boundary

At the S1 repository checkpoint, the production immediate engine is implemented but `engine.run_monitor()` is still a stub.

The evaluation strategy called `SOLIDHUNT_IMPROVED_MONITOR` combines:

- Production route enumeration.
- Production landed-cost and customs calculations.
- Production trust scoring.
- Production cap-referenced expected value for ranking safe candidates.
- An evaluation timing policy selected on seeds 1–100 and frozen before running seeds 101–200.

It must still be described as a **SolidHunt monitoring-policy simulation**, not production monitor-loop output. The original strict §5.7 simulation is preserved as `SOLIDHUNT_EVAL_MONITOR` for diagnostic reproduction.

## Shared cohort

Each seed generates three hunt templates. The primary comparison selects template 1 to keep exactly one paired case per world.

The template supplies:

- Target style code.
- EU size.
- Landed-price cap.

The source template's delivery deadline is recorded but removed from the analysis. Both strategies receive the complete 90-day horizon, isolating buying-timing behavior rather than deadline differences.

Both policies use `geo_arbitrage=NEVER`. Ordinary storefront and direct routes remain available according to engine rules; IP-gated tactics are excluded.

## Common optimal benchmark

For target product and size, define the daily market curve:

```text
L(t) = lowest legitimate fully landed price available on day t
```

A quote is legitimate when:

- Hidden true product and colorway equal the target.
- Size and condition are correct.
- It is not a kids version.
- It is neither bait nor counterfeit.
- Stock is positive.
- Its route is operationally feasible.

The common full-horizon optimum is:

```text
P* = min L(t), over ticks where L(t) ≤ cap
```

This is an omniscient evaluation benchmark. Neither buying strategy can see future values of `L(t)`.

## Regular-shopper hypothesis

`CASUAL_CHECKOUT_3D` models a budget-conscious, attentive, non-expert shopper.

This is a synthetic hypothesis, not a claim based on measured consumer research. Its assumptions are intentionally explicit and reasonably generous:

1. The shopper checks prices every three days and once on the final day.
2. Product and size discovery are assumed correct, isolating buying behavior from search skill.
3. Only ordinary direct-to-Poland listings are considered.
4. The shopper compares a perceived checkout subtotal:

   ```text
   perceived = goods − valid coupon + quoted direct shipping
   ```

5. The shopper does not calculate import VAT, customs duty, carrier handling, forwarding fees, seller trust, or geo tactics.
6. At the first check where at least one perceived subtotal fits the cap, the shopper buys the cheapest one and stops.

The actual landed cost and hidden legitimacy are calculated only after the simulated decision. They do not influence selection.

The check interval is configurable through `CasualShopperHypothesis`; daily and weekly sensitivity runs can use intervals 1 and 7 without changing policy code.

## SolidHunt improved monitoring-policy simulation

Each day, the evaluation considers public target listings with correct structured size and condition. Every route passes through the implemented engine's:

- Full landed-cost assembly.
- Cap gate.
- Observable trust floor.
- Expected-value calculation.

The initial diagnostic treated `EV > 0` as a hard eligibility condition. This rejected most under-cap offers because the additive trust score is not a calibrated probability. The improved policy keeps the hard cap and trust floor, but uses EV to rank candidates rather than suppress them.

It buys through three declared paths:

1. **High-confidence deal:** buy when trust is at least `TRUST_HIGH`; or when trust is at least the midpoint of `TRUST_FLOOR` and `TRUST_HIGH` and landed price beats the cap by at least `GOOD_DEAL_MARGIN` (€5).
2. **Observed low:** after at least five qualifying observations, buy when the current daily best is in the lowest 25% of observed values and within €5 of the observed minimum.
3. **Final-window fallback:** during the final 14 days, buy the first safe under-cap candidate rather than relying on stock being present on exactly day 89.

On a buy tick, candidates are ranked by expected value, then landed price, with deterministic identifier tie-breaks.

The original diagnostic policy remains available with `--solid-policy spec`. It uses:

```text
p_daily = (number of observations below current − €1 + 1) / (n + 2)
```

It is adjusted by the slope of the last seven observations:

- Falling price trend: multiply by 1.25.
- Rising price trend: multiply by 0.80.
- Clamp to 0.95.

For remaining horizon `H`:

```text
p_better = 1 − (1 − p_daily)^H
```

The original diagnostic buys when:

- At least five qualifying observations exist and `p_better < 0.25`; or
- The final permitted tick has a qualifying quote.

This strict version produced a 96% miss rate on seeds 1–100 and motivated the improved policy above.

## Price-gap and timing metrics

For a legitimate purchase at tick `b` and actual landed price `P`:

```text
total regret    = P − P*
selection gap   = P − L(b)
timing gap      = L(b) − P*

total regret = selection gap + timing gap
```

The decomposition distinguishes choosing the wrong route on the purchase day from choosing the wrong purchase day.

Price regret is calculated only for legitimate purchases. Invalid purchases are reported separately so a suspiciously cheap trap cannot appear as negative regret.

Every conditional price statistic is accompanied by:

- Purchase count.
- Legitimate-purchase count.
- Invalid-purchase count.
- Miss rate.
- Actual cap violations.

The regular shopper also reports:

```text
checkout understatement = actual landed − perceived checkout
```

## Generated plots

The standard-library SVG renderer produces:

- `all-runs.svg`: a 10×10 contact sheet containing every complete market timeline.
- `timelines/run-001.svg` through `run-100.svg`: one readable full timeline per seed.
- `buy-timing.svg`: shopper buy day against SolidHunt buy day for paired purchases.
- `price-gap-comparison.svg`: horizontal Tukey box plots using all legitimate purchases, with a sparse percentile-spaced point sample and explicit outlier counts/maxima.
- `price-gap-cdf.svg`: cumulative share of legitimate purchases within each price gap, which remains readable despite large tail values.
- `paired-outcomes.svg`: run-by-run counts where SolidHunt was cheaper, tied, or more expensive among paired legitimate purchases.
- `outcomes.svg`: legitimate purchase, invalid purchase, and miss counts.
- `shopper-sensitivity.svg`: held-out comparison with both 3-day and weekly shopper assumptions.

SVG is used because it is scalable for slides and requires no NumPy, pandas, or plotting-library dependency.

## Reproduction

```bash
.venv/bin/python -m dealhunter.evalx.runner \
  --runs 100 \
  --start-seed 101 \
  --solid-policy improved \
  --user-check-interval 3 \
  --output reports/eval-100-heldout
```

The runner generates one world at a time inside temporary storage. This avoids retaining all worlds in memory and discards approximately 6 MB of generated JSON/SQLite/dossier artifacts per seed after evaluation.

Tests:

```bash
.venv/bin/pytest tests/test_eval.py
.venv/bin/pytest
```

## Output data

`reports/eval-100-heldout/data/runs.csv` contains one row per paired run, including:

- Seed, target, size, and cap.
- Optimal tick, listing, route, and landed price.
- Each policy's buy/miss outcome.
- Actual and perceived prices.
- Raw gap, legitimate regret, selection gap, and timing gap.
- Purchase legitimacy and encountered trap types.
- Actual purchase route and decision reason.

`reports/eval-100-heldout/data/timelines.csv` contains one row per run and tick with the complete legitimate market curve and all marker flags.

`reports/eval-100-heldout/data/summary.json` contains machine-readable aggregate metrics. Weekly sensitivity results are stored under `reports/eval-100-heldout-weekly/`.
