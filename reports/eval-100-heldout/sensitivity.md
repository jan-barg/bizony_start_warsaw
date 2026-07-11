# Held-out strategy comparison

Policy parameters were selected using seeds 1–100. All figures below come from untouched held-out seeds 101–200.

## Primary comparison: attentive shopper checks every three days

| Metric | SolidHunt improved monitor | Casual shopper (3-day) |
|---|---:|---:|
| Legitimate purchases | 79 | 82 |
| Invalid purchases | 0 | 0 |
| Misses | 21 | 18 |
| Actual cap violations | 0 | 5 |
| Mean gap from full-horizon optimum | **€7.66** | €13.80 |
| Median gap | **€1.96** | €4.02 |
| P90 gap | **€22.06** | €28.95 |
| Mean absolute timing error | **14.97 days** | 17.76 days |

On the 69 runs where both purchased, the shopper paid **€7.36 more on average**. The attentive shopper completed three more purchases, but five exceeded the true landed-cost cap.

## Sensitivity: regular shopper checks weekly

| Metric | SolidHunt improved monitor | Casual shopper (weekly) |
|---|---:|---:|
| Legitimate purchases | **79** | 70 |
| Invalid purchases | 0 | 0 |
| Misses | **21** | 30 |
| Actual cap violations | **0** | 6 |
| Mean gap from full-horizon optimum | **€7.66** | €16.22 |
| Median gap | **€1.96** | €6.18 |
| P90 gap | **€22.06** | €32.57 |

On the 57 runs where both purchased, the weekly shopper paid **€9.98 more on average**.

## Interpretation

The favorable price and safety result does not depend on weakening the comparator: SolidHunt beats the deliberately attentive three-day shopper on mean, median, and tail price gap, timing error, and cap obedience. The three-day shopper retains a small purchase-coverage advantage (82 versus 79), which is reported rather than hidden.

Against the arguably more typical weekly-checking hypothesis, SolidHunt also wins purchase coverage.

The production `engine.run_monitor()` entry point remains incomplete. These are held-out results for `SOLIDHUNT_IMPROVED_MONITOR`, which uses production route, landed-cost, customs, trust, and EV components with the new evaluation timing policy.

## Recommended pitch visuals

- `plots/price-gap-comparison.svg`: focuses on €0–€30, where at least 90% of each policy's legitimate purchases fall; it separately reports every larger value and maximum.
- `plots/price-gap-cdf.svg`: shows the share of legitimate purchases that stay within each distance from the optimum, avoiding a maximum-driven axis.
- `plots/paired-outcomes.svg`: shows 29 SolidHunt wins, 28 ties, and 12 shopper wins across the 69 paired legitimate purchases.
- `plots/shopper-sensitivity.svg`: shows that the price-quality and budget-safety result persists under both attentive and weekly shopper assumptions.
