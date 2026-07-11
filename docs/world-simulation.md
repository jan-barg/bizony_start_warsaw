# SolidHunt world simulation

This document explains how SolidHunt generates its synthetic sneaker market, including the mathematics, deterministic randomness, planted traps, output artifacts, and intended use in large evaluation runs.

The implementation lives in [`dealhunter/world/`](../dealhunter/world/). The governing technical requirements remain in [`implementation-spec.md`](../implementation-spec.md), especially §2.3 and §4.

## 1. What one simulated world contains

A world is a complete market history for a fixed number of simulated days. With the default configuration it contains:

- 40 canonical products: 10 handcrafted and 30 generated.
- 25 vendors across the EU, UK, US, and Japan.
- 4 forwarding middlemen in Japan, the US, and the UK.
- 6–14 listings per vendor.
- 90 daily price and stock rows for every listing.
- Daily EUR/PLN, EUR/GBP, EUR/USD, and EUR/JPY exchange rates.
- Coupons and geographically restricted promotions.
- Deliberately planted adversarial traps.
- An omniscient oracle containing the best legitimate purchase for each evaluation hunt.
- A human-readable dossier describing every trap and the correct behavior.

One tick represents one simulated day.

## 2. Is the world random?

Yes, but it uses **seeded pseudorandomness**.

```python
from dealhunter.core.config import Constants
from dealhunter.world.generate import generate_world

world = generate_world(42, Constants())
```

Seed `42` always produces the same world. A different seed produces a different, but still reproducible, world.

This gives the project both variation and an exact answer key:

- Hundreds of different seeds can test many market conditions.
- A failed seed can be replayed exactly during debugging.
- Multiple policies can be compared on identical market histories.
- Demo runs do not depend on network access or live shops.

### 2.1 Hierarchical seed derivation

SolidHunt does not use one shared sequence of random numbers. It derives independent streams by hashing the master seed together with a namespace:

```python
def derive(master: int, *namespace: str | int) -> int:
    message = ":".join(map(str, (master, *namespace)))
    digest = sha256(message.encode()).digest()
    return int.from_bytes(digest[:8], "big")
```

Examples of namespaces are:

```text
("catalog",)
("vendor", "v_001")
("assort", "v_001")
("title", "l_v_001_DD1391-100")
("price", "l_v_001_DD1391-100")
("fx", "EURGBP")
("geo", "l_v_001_DD1391-100")
("traps",)
("eval", 42)
```

This isolation prevents accidental ripple effects. For example, adding vendor 26 does not change vendor 7's price history, because their random streams are independent.

No unseeded randomness, UUIDs, or wall-clock values are used in world generation.

## 3. Generation pipeline

`generate_world(seed, cfg)` executes these stages in order:

1. Generate the canonical product catalog and aliases.
2. Generate vendors, the whitelist, and forwarding middlemen.
3. Generate vendor assortments and messy listing titles.
4. Generate FX, prices, stock, and coupons.
5. Generate ordinary foreign storefront promotions.
6. Plant adversarial traps and append a `TrapRecord` for each one.
7. Compute omniscient oracle answers.
8. Write canonical JSON, SQLite, and Markdown dossier artifacts.

The orchestrator is [`dealhunter/world/generate.py`](../dealhunter/world/generate.py).

## 4. Product and listing generation

### 4.1 Catalog

The handcrafted portion includes recognizable, real-shaped examples such as the Dunk Low Panda, alongside invented generated style codes. Each canonical product has:

- Brand, model, and colorway.
- A unique style code.
- Available EU sizes.
- Fair price in EUR.
- Textile or leather footwear customs category.
- Manufacturing origin.
- Weight.
- Optional link to an adult product when it is a kids twin.

Generated products draw from seeded brand, model, colorway, origin, fair-price, material, and weight pools. Kids twins are priced at approximately 55% of the corresponding adult fair price.

Implementation: [`dealhunter/world/catalog.py`](../dealhunter/world/catalog.py).

### 4.2 Vendors and middlemen

Vendor attributes include geography, currency, channel, destinations, shipping prices, returns, domain age, reviews, and IOSS registration.

The default world guarantees important structural cases:

- Three exact-domain official whitelist entries.
- EU vendors that ship to Poland.
- Two Japanese and one US vendor that do not ship to Poland.
- Two Japanese, one US, and one UK forwarding lanes.
- Both postal and courier international forwarding.

Each vendor lists a seeded sample of 6–14 products.

Implementation: [`dealhunter/world/vendors.py`](../dealhunter/world/vendors.py).

### 4.3 Messy titles

Listings start from a canonical title and independently receive noise operations:

- Drop the colorway with probability 20%.
- Replace the colorway with an alias with probability 30% when an alias exists.
- Append the style code with probability 45%.
- Add emoji or filler with probability 35%.
- Rewrite the size system with probability 25%.
- Capitalize fragments with probability 15%.

Kids listings also receive a kids marker such as `GS`, `Kids`, or `Junior` before trap injection potentially makes the title adversarial.

## 5. Price mathematics

Price generation is implemented in [`dealhunter/world/pricing.py`](../dealhunter/world/pricing.py).

### 5.1 Starting price

For a product with fair price `F`, the listing's mean-reversion target is:

```text
base = F × U(0.92, 1.15) × FX₀
```

where `U(a, b)` is a uniform random draw and `FX₀` converts EUR into the vendor's currency at tick 0.

For example, a product with a fair price of €100 receives an initial target between approximately €92 and €115 before conversion into the vendor currency.

### 5.2 Mean-reverting walk

Ignoring a flash sale, the next price is:

```text
p(t+1) = p(t) + 0.10 × (base − p(t)) + ε(t)
```

with:

```text
ε(t) ~ Normal(0, 0.012 × base)
```

The first term pulls the price 10% of the way back toward its normal level each day. The Gaussian noise adds day-to-day movement with a standard deviation equal to 1.2% of the base price.

The walk is floored at:

```text
p(t) ≥ 0.55 × base
```

This is a synthetic mean-reverting process, not a price forecasting model.

### 5.3 Flash drops

On each tick, a listing that is not already in a flash window has probability:

```text
P(flash starts) = 0.35 / 30 ≈ 0.01167
```

of starting a flash sale. A flash sale:

- Reduces the current price by a uniformly drawn 12–25%.
- Lasts 1–3 ticks.
- Sets `on_sale=True`.

The stored sale predicate is:

```text
on_sale = inside_flash_window OR sticker < 0.97 × tick_0_sticker
```

The engine later uses this stored flag when checking coupons that exclude sale items.

### 5.4 Float-to-money boundary

Random distributions operate in floating-point space only inside the world generator. At the output boundary, each price becomes an integer number of minor currency units and then a `Decimal`:

```python
cents = round(float_price * 100)
price = Decimal(cents) / 100
```

JPY is rounded to whole yen. The decision engine never receives floating-point money.

## 6. FX mathematics

The fixed starting rates are fictional simulation inputs:

```text
EURPLN = 4.25
EURGBP = 0.86
EURUSD = 1.10
EURJPY = 165.00
```

Each pair follows an independent multiplicative random walk:

```text
r(t+1) = r(t) × (1 + η(t))
η(t) ~ Normal(0, 0.003)
```

The daily movement therefore has a standard deviation of approximately 0.3%. Rates are stored as six-decimal `Decimal` values.

## 7. Stock mathematics

Each listing starts with a uniformly drawn stock count from 1 through 12.

The daily probability of selling one unit is:

```text
x = 4 × (base − current_price) / base
sale_probability = sigmoid(x) × 0.35
sigmoid(x) = 1 / (1 + exp(−x))
```

Consequences:

- A price near its base has a sale probability near 17.5%.
- A price below its base sells faster.
- A price above its base sells more slowly.
- At most one unit is removed from a listing per tick.

When stock reaches zero, the listing has a 3% chance of restocking to its initial stock level on each following tick.

## 8. Coupons

Each listing has a 25% chance of receiving one ordinary generated coupon.

A generated coupon has:

- A lifetime of 5–15 ticks.
- Either a 10–15% discount or a flat discount.
- An optional minimum basket.
- A chance of excluding sale items.

Trap injection additionally creates coupons that are advertised one tick after expiry or attached to an excluded sale row.

## 9. Geo promotions

Geo promotions are generated only for vendors in Japan, the US, and the UK when a forwarding middleman exists in the same country.

The three access tiers are:

- `STOREFRONT`: visible foreign storefront price; usable through a middleman.
- `IP_GATED`: gray-route promotion controlled by the mandate's geo-arbitrage setting.
- `VERIFIED_LOCAL`: advertised but impossible for the simulated user to purchase.

An ordinary storefront promotion applies a seeded discount of 5–14% for a short window. Trap injection adds fake exclusives, verified-local offers, risky IP-gated offers, and genuinely advantageous foreign promotions.

Implementation: [`dealhunter/world/geo.py`](../dealhunter/world/geo.py).

## 10. Adversarial trap injection

Trap placement uses the independent `("traps",)` random stream. It does not use fixed listing positions.

The default configuration plants 27 trap records across these categories:

| Trap type | Default count | Purpose |
|---|---:|---|
| Bait listing | 3 | Unrealistically cheap offer with observable trust failures |
| Fake anchor | 4 | Claimed previous price was never charged |
| Anchor reset | 2 | Short spike creates a misleading later discount |
| Landed inversion | 3 | Lowest sticker is not lowest after import costs |
| Customs cliff pair | 1 | Values on opposite sides of the €150 threshold |
| FTA-origin trap | 1 | UK dispatch incorrectly suggests preferential origin |
| Whitelist impersonator | 1 | Typosquatted domain resembles an official domain |
| GS/kids trap | 2 | Kids product presented with adult-ambiguous sizing |
| Colorway trap | 2 | Missing or contradictory colorway evidence |
| Coupon trap | 2 | Expired or sale-excluded coupon |
| Stock race | 1 | Stock disappears after the attractive price appears |
| Fake geo exclusive | 1 | Foreign promotion is not actually cheaper |
| Verified-local promo | 1 | Attractive but unattainable promotion |
| Net-negative IP-gated | 1 | Low sticker loses after risk, time, and landed cost |
| Genuine geo promo | 2 | Foreign route is truly competitive |

Every instance appends a `TrapRecord` containing its type, listing, vendor, active ticks, explanation, and expected correct behavior.

Implementation: [`dealhunter/world/traps.py`](../dealhunter/world/traps.py).

### 10.1 Compact MVP world

`Constants().mvp_world()` reduces the simulation to:

- 12 products.
- 10 vendors.
- 2 middlemen.
- One instance of every configured trap category.

The formulas and safety rules do not change.

## 11. Oracle mathematics

The oracle is an evaluation-only, omniscient search. It may use hidden ground-truth labels that the decision engine is forbidden to read.

For each deterministic hunt template, the oracle enumerates candidate tuples:

```text
(tick, listing, route)
```

It keeps only candidates satisfying the true requirements:

- Exact product and colorway identity.
- Correct size.
- New condition.
- Adult version.
- Not bait or counterfeit.
- Stock greater than zero.
- Feasible direct or middleman route.
- Delivery before the deadline, when present.
- Full landed total at or below the generated cap.

It independently computes complete landed cost with coupons, shipping legs, forwarding fees, the configured customs ruleset, import VAT, and handling.

The result is the minimum tuple ordered by:

```text
(landed_eur, tick, listing_id, route_kind, middleman_id)
```

Two answers are stored per hunt:

- `allow`: IP-gated geo routes are reachable.
- `never`: IP-gated geo routes are invisible.

The oracle does not import decision-engine code. This keeps the truth calculation independent from the policy being evaluated.

Implementation: [`dealhunter/world/oracle.py`](../dealhunter/world/oracle.py).

## 12. Generated artifacts

Generating seed 42 writes:

```text
worlds/world_42.json
worlds/world_42.sqlite
worlds/world_42.md
```

- JSON is the canonical serialized `World`.
- SQLite stores the same canonical payload as a portable database artifact.
- Markdown is the judge-facing dossier with market summary, traps, oracle answers, and a world fingerprint.

All three files are byte-identical when regenerated with the same seed and configuration. The `worlds/` directory is ignored by Git.

## 13. Running many worlds

A simple generation sweep is:

```python
from dealhunter.core.config import Constants
from dealhunter.world.generate import generate_world

cfg = Constants()
worlds = [generate_world(seed, cfg) for seed in range(1, 201)]
```

Because `generate_world` writes three artifacts per seed, a large sweep also creates files under `worlds/`. Evaluation code should normally generate, evaluate, and release one world at a time rather than retain all worlds in memory.

Conceptually:

```python
for seed in range(1, 201):
    world = generate_world(seed, cfg)
    for policy in policies:
        for hunt in world.oracle:
            result = run_policy(world, hunt, policy)
            collect_metrics(result, world.oracle[hunt], world.traps)
```

With 200 seeds, 3 hunts per seed, and 4 policies, this gives 2,400 primary policy runs before expanding ask-approval variants.

## 14. Intended metrics and charts

The post-S1 `evalx` layer will run after the real engine is available. It is designed to calculate:

- Purchase legitimacy.
- Strike quality.
- False-buy rate and outcomes by trap type.
- Colorway error rate.
- Regret relative to the policy-consistent oracle.
- Miss rate.
- Immediate-versus-monitor impatience cost.
- Geo-promotion capture rate.
- Unattainable-promotion errors.
- Alert efficiency.
- Code/LLM/human routing split.
- Cancellation counts.
- Mandate violations, asserted to be exactly zero.

Useful visualizations include:

- Regret box plots by policy.
- False-buy outcomes grouped by trap type.
- Purchase legitimacy and strike quality by policy.
- Immediate versus monitor landed-price distributions.
- Paired per-seed impatience-cost plots.
- Geo `ALLOW` versus `NEVER` comparisons.
- Purchase, miss, and cancellation counts.
- Selected price timelines with cap, promotion, trap, and purchase markers.

Metrics must always compare policies on the same seeds and hunt templates. Otherwise world difficulty could be mistaken for policy quality.

## 15. Verification

The world acceptance tests cover full and MVP shapes, namespace isolation, the money boundary, all trap records, dossier completeness, artifact determinism, SQLite round-tripping, hidden-label separation, and the seeds 1–20 oracle gate.

```bash
.venv/bin/pytest tests/test_world.py
```

The complete repository suite is:

```bash
.venv/bin/pytest
```
