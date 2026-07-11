# SolidHunt engine modeling

This document is the mathematical source of truth for SolidHunt's decision
engine. It distinguishes behavior that exists in code from behavior planned for
the next build. The governing engineering specification remains
[`implementation-spec.md`](../implementation-spec.md); if this explanation and
that specification disagree, the implementation specification wins.

Status labels used below:

- **IMPLEMENTED** — present in the current engine and covered by tests.
- **PLANNED** — accepted by the build plan but not yet complete.
- **EXPERIMENTAL** — worth evaluating, but not a product dependency.
- **REJECTED FOR V1** — deliberately excluded from the hackathon build.

## 1. Objective and boundaries

For a requested product and a user mandate, the engine selects at most one
acquisition route. It minimizes neither sticker price nor landed price in
isolation. It first enforces identity, consent, cap, deadline, and access rules,
then ranks the remaining routes by a transparent risk-adjusted score.

One observation tick is one simulated day. Monetary quantities inside the
engine are `Decimal` EUR values. Random outcomes use namespaced pseudorandom
streams derived from the world seed. The runtime engine may use only observable
world fields; hidden truth is restricted to the simulator and evaluation
harness.

The data-generating process is documented separately in
[`world-simulation.md`](world-simulation.md). In particular, synthetic prices
are mean-reverting, but the engine is not allowed to read or fit the generator's
known parameters. Doing so would be answer-key leakage rather than forecasting.

## 2. Exact money model — IMPLEMENTED

### 2.1 Quantization

Every displayed receipt line is quantized with `ROUND_HALF_UP` when finalized.
Intermediate `Decimal` arithmetic uses full precision. For finalized lines
\(\ell_1,\ldots,\ell_m\), the landed total is defined as

\[
L=\sum_{j=1}^{m}\ell_j.
\]

The engine never computes and rounds a second independent total. Therefore the
receipt identity \(\sum_j\ell_j=L\) is exact, not approximate.

For a vendor amount \(a\) in currency `CCY`, with rate \(r\) defined as
`1 EUR = r CCY`, conversion is

\[
\operatorname{EUR}(a)=q_2\!\left(\frac{a}{r}\right).
\]

### 2.2 Coupon and route order

Let \(G\) be converted goods and \(Q\le 0\) a valid coupon. A coupon is valid
only when its tick window contains the current tick, its minimum basket is no
greater than the sticker, and it does not exclude the stored `on_sale` state.
The customs intrinsic value is

\[
I=G+Q.
\]

For a direct route,

\[
L=G+Q+S_d+\operatorname{Import}(I,S_d).
\]

For a middleman route,

\[
L=G+Q+S_{dom}+F_{flat}+q_2(f_{pct}I)+S_{intl}
  +\operatorname{Import}(I,S_{dom}+S_{intl}).
\]

Middleman service fees are deliberately outside the customs transport base;
both freight legs are inside it.

### 2.3 Polish import model

EU dispatch has no border lines. For non-EU intrinsic value \(I\le €150\):

- IOSS returns no additional border lines under the stated deemed-importer
  simplification.
- `EU_2026_07` applies flat duty \(D_f=€3\); legacy rules use \(D_f=0\).
- Import VAT is
  \[
  V=q_2(0.23(I+T+D_f)).
  \]

For \(I>€150\), with transport \(T\), HS rate \(h\), and preferential-origin
indicator \(P\),

\[
D=q_2((1-P)h(I+T)),\qquad
V=q_2(0.23(I+T+D)).
\]

Textile footwear uses \(h=0.169\), leather footwear \(h=0.08\). Handling is
€6 postal or €15 courier. Dispatch from the UK or Japan is insufficient for
preference: manufacturing origin must respectively be GB or JP.

Golden vectors V1–V8a are the executable acceptance examples for these rules.

## 3. Identity, feasibility, and dominance — IMPLEMENTED

An evaluated object is a route quote, not merely a listing. The same listing may
produce a direct quote, a legal storefront-middleman quote, or an IP-gated
middleman quote.

The engine assigns each quote one eligibility state:

\[
E\in\{\text{QUALIFYING},\text{OVER\_CAP\_BAND},\text{HARD\_REJECT}\}.
\]

Hard rejections include product mismatch, structured size mismatch, excluded
condition/kids/reseller channel, far-over-cap cost, revocation, expiry, missed
deadline, verified-local access, and forbidden IP-gated access.

Separately, `purchase_eligible=False` for colorway conflict, unconfirmed
colorway, LLM-only identity, or ambiguous size. These quotes may eventually be
reported or alerted, but they cannot enter any purchase path.

**EXPERIMENTAL:** Pareto pruning may later remove route \(a\) when another route
\(b\) is no more expensive, no slower, no less trusted, and no more tactically
restricted, with at least one strict improvement. This is safe and explainable,
but it is not required for S2 because maximum-utility selection already handles
the candidate set.

## 4. Observable trust model — IMPLEMENTED HEURISTIC

Trust begins at 0.50 and receives additive observable adjustments:

\[
\begin{aligned}
s={}&0.50+0.10(\text{review average}-3)\\
  &+0.04\min(\log_{10}(\text{review count}+1),3)\\
  &+A_{age}+A_{returns}+A_{burst}+A_{price}+A_{route}.
\end{aligned}
\]

Adjustments are:

| Observable condition | Adjustment |
|---|---:|
| Domain age at least three years | +0.05 |
| Domain age below 90 days | -0.15 |
| Returns at least 14 days | +0.05 |
| No returns | -0.10 |
| Young-domain review burst | -0.20 |
| Effective goods below 60% of market median | -0.25 |
| Middleman route | -0.03 |

Ordinary scores are clamped to \([0.02,0.99]\). An exact whitelisted domain
short-circuits to 1.00. A domain at least 0.80 similar to a whitelist domain but
not exactly equal is flagged as a possible impersonator and capped at 0.15.

### 4.1 Critical interpretation

The current score is not calibrated against real fraud outcomes. It must be
called an **observable trust score**, not a verified probability of legitimacy.
Consequently, the field currently named `ev_eur` is a risk-adjusted decision
score expressed on a euro-like scale, not a demonstrated real-world expected
profit.

**EXPERIMENTAL:** on held-out synthetic seeds, measure reliability bins and the
Brier score

\[
\operatorname{BS}=\frac1N\sum_{i=1}^{N}(s_i-y_i)^2.
\]

This can diagnose simulator calibration, but it cannot establish real-commerce
calibration. Reliability diagrams should be presented with that limitation.

## 5. Risk-adjusted route utility — IMPLEMENTED

Let

- \(C\): user landed-cost cap in EUR,
- \(L\): quote landed cost in EUR,
- \(s\): observable trust score,
- \(H=€15\): hassle loss,
- \(p_c\): observable cancellation estimate (0.12 for IP-gated, otherwise 0),
- \(K=€5+D_e\): cancellation cost,
- \(D_e=€10\) when deadline slack after ETA is below three ticks, otherwise 0.

The implemented score is

\[
U=s(C-L)-(1-s)(L+H)-p_cK.
\]

Algebraically,

\[
U=s(C+H)-(L+H)-p_cK.
\]

Thus \(U>0\) is equivalent to

\[
s>\frac{L+H+p_cK}{C+H}.
\]

This explains useful behavior: the required trust rises as landed cost rises,
the quote approaches the cap, or cancellation exposure grows. Among qualifying
routes the engine selects maximum \(U\), not minimum \(L\).

### 5.1 Seed-42 S1 example

The generated demo uses cap \(C=€150\). The selected official EU route has
goods €125.18, shipping €8.45, landed \(L=€133.63\), and whitelist trust
\(s=1.00\). With no cancellation term,

\[
U=1(150-133.63)-0(133.63+15)=€16.37.
\]

This reproduces the deterministic S1 receipt exactly.

## 6. Bayesian finite-horizon stopping — PLANNED

Monitor mode observes the best qualifying landed cost on each informative tick.
Let \(x_t\) be the current best cost, \(\delta=€1\), and let the previous
history contain \(n\) observations. Define an improvement as

\[
I_i=\mathbf 1[x_i<x_t-\delta],\qquad k=\sum_{i=1}^{n}I_i.
\]

With a Beta(1,1) prior for the daily improvement probability, the posterior is

\[
p\mid\text{history}\sim\operatorname{Beta}(k+1,n-k+1),
\]

whose posterior mean is

\[
\hat p=\frac{k+1}{n+2}.
\]

For effective remaining horizon \(H_t\), the working independence
approximation gives

\[
P(\text{at least one better day})=1-(1-\hat p)^{\max(H_t,0)}.
\]

The last feasible purchase tick is

\[
t_{last}=\min(t_{expiry}-1,\ t_{deadline}-\min\operatorname{ETA}),
\qquad H_t=t_{last}-t.
\]

Route-class ETA ignores current stock, because a temporary stockout does not
make a future route structurally impossible.

For the most recent \(m=\min(7,n)\) prices, trend is the ordinary least-squares
slope

\[
\beta=\frac{\sum_i(i-\bar i)(x_i-\bar x)}{\sum_i(i-\bar i)^2}.
\]

Before the horizon calculation, multiply \(\hat p\) by 1.25 when \(\beta<0\)
(falling prices) or 0.80 when \(\beta>0\) (rising prices), then clamp it to 0.95.
This multiplier is a documented heuristic, not part of the Beta posterior.

Decision rule:

1. With fewer than five observations and \(H_t>0\), HOLD unless auto-buy fires.
2. BUY when the improvement probability is below \(\theta=0.25\).
3. BUY on \(H_t=0\) when a qualifying under-cap offer exists.
4. Otherwise HOLD and receipt the probability, horizon, threshold, and sample
   size.

The model assumes daily improvement indicators are approximately stationary and
independent over the short decision horizon. E-commerce prices violate both
assumptions during promotions, so this is an explainable stopping heuristic—not
a claim of globally optimal forecasting.

An empirical deal percentile may be included as receipt evidence:

\[
q_t=\frac{1+\sum_{i=1}^{n}\mathbf1[x_i\le x_t]}{n+1}.
\]

It does not authorize a purchase and does not use vendor-claimed anchors.

## 7. Escalation and constrained attention — PARTLY IMPLEMENTED

The policy is a top-down ladder:

- E0: auto-buy under explicit mandate implications.
- E1: ordinary immediate or stopping-rule buy.
- E2 (**PLANNED**): ask for an IP-gated tactic.
- E3 (**PLANNED**): ask for a rare high-quality quote slightly above cap.
- E4: silently reject beyond the over-cap band.
- E5: report no immediate qualifying route.

Alerts and both ask kinds share one seven-tick rolling interruption budget.
Approvals are bound to the canonical quote hash, single-use, and consumed during
execution. A declined route may ask again only after improving by at least
\(\max(€5,5\%)\). Money permission and tactics permission are separate.

## 8. Evaluation mathematics — PLANNED

Policies are evaluated on identical `(seed, hunt template)` pairs:

- `GREEDY_STICKER`
- `LANDED_NO_TRUST`
- `OURS_IMMEDIATE`
- `OURS_MONITOR`

Paired worlds remove much of the variance caused by different market histories.
For a continuous metric, define paired differences
\(d_i=m_i^{A}-m_i^{B}\). Report

\[
\bar d=\frac1N\sum_i d_i,
\qquad
CI_{95}\approx \bar d\pm1.96\frac{s_d}{\sqrt N}.
\]

For a rate with \(x\) successes in \(n\) trials, use the Wilson interval with
\(z=1.96\):

\[
\operatorname{center}=\frac{\hat p+z^2/(2n)}{1+z^2/n},
\]

\[
\operatorname{half}=\frac{z}{1+z^2/n}
\sqrt{\frac{\hat p(1-\hat p)}n+\frac{z^2}{4n^2}}.
\]

Every conditional metric prints its denominator. Regret is always displayed
beside miss rate and cancellations; impatience cost prints `n_both`,
`n_immediate_only`, and `n_monitor_only`.

Use 20 development seeds for debugging. Lock code and parameters before a
disjoint 200-seed final run. The report may claim deterministic performance on
this benchmark, never expected performance on real shops.

## 9. Models rejected for v1

| Idea | Decision | Reason |
|---|---|---|
| Black–Scholes/option pricing | Rejected | No tradable replication, continuous market, or volatility interpretation |
| ARIMA/LSTM price forecast | Rejected | Too little per-product history; complexity exceeds evidence |
| Reinforcement learning | Rejected | Simulator-policy overfitting and poor auditability |
| Portfolio optimization | Rejected | One required item, not a basket of risk-return assets |
| Fit the generator's mean reversion | Rejected | Leaks synthetic answer-key structure into the agent |
| Unbounded parameter sweep | Rejected | Encourages benchmark overfitting and weakens reproducibility |

Financial-market inspiration is used only where the decision structure matches:
finite-horizon stopping, risk-adjusted comparison, paired counterfactuals, and
uncertainty reporting.

## 10. Demo claims

We may say:

- Every euro in a receipt follows tested deterministic arithmetic.
- The engine chooses by transparent risk-adjusted score rather than sticker.
- Monitor timing uses an explicit finite-horizon stopping rule.
- Policies are compared on identical seeded markets with oracle ground truth.
- Mandate violations are live assertions, not an average metric.

We may not say:

- The current trust score is a real-world fraud probability.
- Synthetic evaluation proves production fraud or savings performance.
- The stopping rule predicts markets or is globally optimal.
- The simulator's hidden labels are available to the runtime agent.

## 11. Research basis

- Dourban and Yedidsion, *Optimal Purchasing Policy For Mean-Reverting Items in
  a Finite Horizon*: finite-horizon purchasing admits time-varying threshold
  structure. <https://arxiv.org/abs/1711.03188>
- Dimitriadis, Gneiting, and Jordan, *Evaluating probabilistic classifiers:
  Reliability diagrams and score decompositions revisited*: calibration and
  reliability diagnostics. <https://arxiv.org/abs/2008.03033>
- Brown, Cai, and DasGupta, *Interval Estimation for a Binomial Proportion*:
  Wilson and other intervals behave better than the naive Wald interval,
  especially for small samples.
  <https://projecteuclid.org/journals/statistical-science/volume-16/issue-2/Interval-Estimation-for-a-Binomial-Proportion/10.1214/ss/1009213286.pdf>
- Kohler and Walk, *On data-based optimal stopping under stationarity and
  ergodicity*: context for nonparametric stopping from observed histories.
  <https://arxiv.org/abs/1307.5976>
