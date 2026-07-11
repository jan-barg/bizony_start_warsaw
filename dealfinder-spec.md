# Deal Hunter — Project Spec (v2.2)

*An agentic shopping assistant that watches a simulated market, computes true landed cost — customs included — and spends real (simulated) money only inside a mandate it provably cannot break.*

**v2 changes:** real customs rule table (§8a) · middleman/forwarding routes (§8b) · colorway-aware matching (§7) · vendor whitelist (§9, Layer 2) · auto-generated world dossier (§4) · two operating modes on a universal time unit (§9a).
**v2.1 adds:** geo-differentiated pricing & local sales — regional storefronts, IP-gated ("VPN") promos, residency-locked traps, and a `geo_arbitrage` tactics-governance knob in the mandate (§8c).
**v2.2:** all open questions resolved (§15) — destination Poland/EUR confirmed; tick = 1 day confirmed; deadlines expressed as "need in N days"; under-declaring-middleman trap **removed**; `ask`-tier escalations rendered by the LLM from structured route data.

---

## 1. What we're building

A user describes a product and a price ceiling in one plain-language message (or a screenshot, or a voice note). From that moment, an agent evaluates a simulated market of shops, computes the **true landed cost** of every offer (sticker + shipping + FX + customs duty + import VAT + handling + coupons — including routes through forwarding middlemen), filters bait and fraud, and either **buys automatically** within a standing mandate, **alerts once** when a genuine deal appears, or **holds** — logging the full reasoning and arithmetic for every decision.

It runs in one of two modes:

- **Immediate execute** — buy the best legitimate offer available *right now*, or report that none qualifies.
- **Monitor** — watch the market over time and strike only when something satisfies the constraints *and* is judged a legitimately good deal.

The deliverable, in order of importance:

1. **A decision engine** that decides buy / alert / hold / escalate with defensible logic in both modes.
2. **A seeded world simulator** that generates realistic, adversarial price histories — and a human-readable dossier of every trap it planted.
3. **An eval harness** reporting strike precision, false-buy rate, regret, and the cost of impatience (immediate vs. monitor on identical worlds).
4. **A timeline demo** that compresses 90 simulated days into 30 seconds on screen.

No scraping, no PSP integration. The market is synthetic and deterministic per seed — a feature, not a shortcut (§2).

---

## 2. Why this shape

**Why a simulated world.** A live scrape is a demo hostage: it breaks on stage, can't be replayed, and has no ground truth. A seeded simulator gives us reproducibility (judges can re-run our exact scenario), counterfactuals (naive agent vs. ours on the *identical* price history), ground truth (hidden labels on every trap → real precision/recall), and scale (500 market histories overnight, metrics as distributions).

**Why the money path is deterministic code.** Landed-cost arithmetic, customs rules, cap enforcement, and mandate logic are plain, unit-tested functions — never an LLM. You can prove things about code. Our trust claim rests on this: *"we can't prove the agent is smart, but we can prove it's obedient."*

**Where the LLM lives.** Three places, all off the money path: (1) **intake** — parsing prompt/screenshot/voice-note transcript into a structured brief + mandate; (2) **fuzzy matching assist** — only when string heuristics fail; (3) **the judgment band** — ambiguous decisions get routed to LLM reasoning, logged in the receipt, and still bounded by the hard gates. We report the routing split ("94% code / 6% judgment / 0.4% human") as a first-class metric — it *is* the answer to "when may an agent act unattended."

---

## 3. System overview

One repository, one process, five modules with clean boundaries. No microservices — module boundaries are function signatures, not network calls.

```
brief.json ──►┌────────────┐
              │  INTAKE     │  LLM: prompt / screenshot / voice note → brief + mandate (incl. mode)
              └─────┬──────┘
                    ▼
┌───────────────────────────────────────────────────────────┐
│  ENGINE (tick-driven; immediate mode = single tick)        │
│                                                            │
│  WORLD SIM ──► MATCHER ──► LANDED COST ──► DECISION        │
│  (offers,      (product +   (FX + customs   (gates → trust │
│   events,       colorway     + middleman     → timing →    │
│   dossier)      identity)    routing)        judgment)     │
└──────────────────────────┬────────────────────────────────┘
                           ▼
                    ┌────────────┐      ┌────────────┐
                    │  LEDGER     │      │  EVAL       │
                    │ (receipts)  │      │ (metrics)   │
                    └────────────┘      └────────────┘
                           ▼
                    TIMELINE UI (demo)
```

**Universal time unit:** one **tick = one simulated day**. Every temporal quantity in the system is expressed in ticks: price history, coupon validity, mandate expiry, delivery ETAs, middleman processing time, the 90-day-low window (= 90 ticks). *Current offers* are defined as the price-event rows at the present tick with stock > 0. Immediate mode evaluates only current offers; monitor mode consumes ticks sequentially.

---

## 4. The world simulator

**What:** a generator that, given an integer seed, produces a complete 90-tick market history — shops, listings, daily price ticks, FX rates, stock, coupons, middlemen — including deliberately planted traps with hidden ground-truth labels. It also writes a **world dossier**: a markdown file explaining every trap in that world.

**How:**

- **Catalog:** ~40 canonical sneakers. Canonical identity = brand + model + **colorway** + size, keyed by **style code** (e.g., Nike `DD1391-100` = Dunk Low "Panda"). Same model in a different colorway is a *different product*. Include colorway **nickname aliases** ("Panda" ↔ "White/Black") in an alias table.
- **Vendors:** ~25 shops with country, currency, shipping table, `ships_to[]` list, return policy, domain age, review profile. Includes official brand stores (whitelisted, §9), honest independents, mediocre shops, and planted bad actors. Some attractive vendors deliberately **do not ship to Poland** — reachable only via middlemen (§8b).
- **Middlemen:** 3–5 forwarding companies (see table, §5) that receive domestically and forward internationally, at a cost and a delay.
- **Listings:** each vendor carries a subset of the catalog with a **raw messy title** plus hidden `true_product_id`. Titles may omit the colorway, use the nickname, or contradict the style code — all matcher traps.
- **Price process:** per listing per tick: baseline around fair price + noise + events — flash drops, fake anchor resets, drift, stock decay, coupon appearances/expiries. FX rates (EUR/GBP/USD/PLN/JPY) follow a small random walk. A subset of listings additionally carries **geo-differentiated prices or local promos** (§8c), visible only from certain observation geos.
- **Determinism:** everything derives from one seed. Same seed → identical world.
- **Trap injection (hidden labels):** every world plants a configurable number of:
  - bait listings (`is_bait`) — too-good price, young domain, thin/suspicious reviews, no returns
  - fake discounts (`is_fake_anchor`) — "was" price never actually charged
  - landed-cost inversions — lowest sticker ≠ lowest landed (FX, shipping, or a **customs cliff** flips the ranking)
  - **customs traps** — a UK or Japan shop whose sneakers are made in Vietnam: dispatch country has an FTA with the EU, but the goods don't qualify for preferential origin → full duty applies (§8a)
  - matching traps — kids (GS) sizing, **wrong colorway with the right model name**, colorway-nickname vs. code conflicts, near-miss counterfeit names, US-vs-EU size confusion
  - **whitelist impersonators** — typosquatted official domains (`adidas-outlet.shop`) that must not inherit whitelist trust
  - coupon traps — expired, min-basket, excludes-sale-items
  - stock races — stock hits 0 between alert and strike
  - anchor-reset manipulation — brief price spike to reset the "90-day low"
  - **geo traps** — fake "JP-only!" exclusives priced the same everywhere (scarcity theater); residency-verified promos that look orderable but aren't; an IP-gated promo whose cancellation risk and added days make it net-negative despite the lowest sticker; a Tokyo promo that flips back above the EU offer after consumption tax + forwarding + Polish import charges — cheaper on paper, illegal in practice; the agent must refuse the route
- **Ground-truth oracle:** after generation, compute per hunt the true best legitimate buy (tick + listing + route + landed price). Eval-only; invisible to the agent.

**The world dossier (`world_<seed>.md`):** auto-generated from the injection log. Contains: seed + config, catalog and vendor summary, one entry per planted trap (type, listing, ticks active, why it's a trap, what a correct agent should do), the ground-truth best buy per hunt, and a short FX/market narrative. Three uses: judge-facing transparency ("here is the answer key — check our agent against it"), team debugging, and the source the eval scores against. It is never placed in the agent's context.

---

## 5. Data model

Plain tables (SQLite or in-memory + JSON dumps — don't spend time on a database).

| Table | Key fields | Notes |
|---|---|---|
| `products` | id, brand, model, **colorway_name, style_code**, sizes, fair_price, **hs_category** (textile/leather upper), **origin_country** (manufacturing) | Canonical catalog. Style code is the unique colorway-level key. |
| `colorway_aliases` | style_code, alias | "Panda" ↔ "White/Black" etc. |
| `vendors` | id, name, domain, country, currency, shipping_table, **ships_to[]**, return_policy, domain_age_days, review_count, review_avg, review_velocity, **ioss_registered**, `is_fraudulent`* | *hidden label |
| `whitelist` | domain, vendor_id | Exact-domain matches only (§9). |
| `listings` | id, vendor_id, raw_title, image_url, `true_product_id`*, condition, `is_bait`*, `is_counterfeit`* | *hidden labels |
| `price_events` | listing_id, tick, sticker_price, currency, stock, was_price_shown, coupon_id | One row per listing per tick — the heart of the world. |
| `coupons` | id, code, discount, min_basket, excludes_sale, valid_from_tick, valid_to_tick | Traps live in the constraints. |
| `fx_rates` | tick, pair, rate | Daily random walk. |
| `customs_rules` | dispatch_zone, value_band, hs_category, preferential_origin?, duty_rate, vat_applies, handling_fee | ~10–15 rows; see §8a. |
| `middlemen` | id, name, located_in, forwards_to[], service_fee_flat, service_fee_pct, intl_shipping_by_weight, extra_ticks, insurance | §8b. All simulated forwarders declare full customs value (compliance modeling is out of scope). |
| `geo_promos` | listing_id, viewer_geo, promo_price, from_tick, to_tick, access_tier (storefront / ip_gated / verified_local), `p_cancel`* | §8c. *hidden — the agent estimates cancellation risk from observable mismatch signals. |
| `mandates` | id, brief_text, parsed_json, **mode**, status | The leash (§6). |
| `receipts` | tick, hunt_id, action, listing_id, **route_via** (direct/middleman_id), landed_math_json, reasons[], decided_by (code/LLM/human) | Append-only; the demo reads from here. |

---

## 6. Intake: the brief and the mandate

**What:** turn one plain-language message, a screenshot, or a voice-note transcript into a **brief** (what to hunt) and a **mandate** (when the agent may spend money without asking) — including the **operating mode**.

**How:** one LLM call with a strict JSON schema (vision-enabled for screenshots). The compiled mandate is shown back to the user before the hunt starts — the leash, made explicit.

```json
{
  "brief": {
    "product": "Nike Dunk Low",
    "colorway": "Panda",
    "style_code": "DD1391-100",        // if unknown, leave blank — matcher must earn it
    "size_eu": 43,
    "condition": "new",
    "exclude": ["resellers", "kids/GS versions"]
  },
  "mandate": {
    "mode": "monitor",                  // "immediate" | "monitor"
    "cap_landed_eur": 80.00,
    "need_within_ticks": 10,            // parsed from "need it in 10 days"; null = no deadline
    "auto_buy": { "enabled": true, "within_eur_of_target": 5.00,
                  "requires": ["stock_low", "trust>=high", "colorway_confirmed"] },
    "allow_middlemen": true,
    "geo_arbitrage": "ask",             // "never" | "ask" | "allow" — governs VPN-style tactics (§8c)
    "alert_budget_per_week": 2,
    "expires_tick": 90,
    "revocable": true
  }
}
```

Rules: the cap applies to **landed** cost via the chosen route, always. `auto_buy` conditions are ANDed — note `colorway_confirmed` is required: the agent never auto-buys a listing whose colorway it could not verify. Deadlines are relative: intake parses "need it in 10 days" → `need_within_ticks: 10`, and the absolute deadline is hunt-start tick + N; a route qualifies only if its total ETA (vendor dispatch + middleman processing + transit, in ticks) lands before it. Revocation takes effect the same tick.

---

## 7. The matcher

**What:** maps each raw listing to a canonical product **at colorway level** — or flags it as unmatchable/suspicious.

**Why:** the case calls same-product matching "the hard core," and buying the right model in the wrong colorway is a failed purchase. Our identity unit is the style code, not the model name.

**How — four tiers, cheap first:**

1. **Style-code extraction:** regex the raw title/description for a style code. An exact code match is decisive — it pins brand, model, *and* colorway in one token.
2. **Normalization + rules:** strip emoji/filler; extract brand/model/size tokens; map size systems (EU/US/UK table); detect GS/PS/TD kids markers and condition words; extract **colorway tokens** and resolve nicknames through the alias table ("Panda" → White/Black).
3. **Fuzzy scoring:** token-set similarity against the catalog at colorway granularity; accept above a high threshold, reject below a low one.
4. **LLM adjudication:** gray-zone cases only. The LLM sees the raw title, the image URL, and top-3 candidates, and picks or refuses.

**Conflict rule:** if the title's colorway tokens contradict an extracted style code, the listing is flagged `colorway_conflict` and can never qualify for auto-buy — at most an alert with the conflict stated. If colorway simply cannot be established, the listing gets `colorway_unconfirmed` with the same restriction.

Output per listing: `(style_code | none, confidence, flags[])`. Matching accuracy and **colorway error rate** (would-have-bought-wrong-colorway) are reported metrics.

---

## 8. The landed-cost engine

**What:** one pure function that turns a matched offer + route into a single comparable number, with a term-by-term breakdown.

```
landed(offer, route, tick) =
    sticker(converted at fx[tick])
  + shipping legs for the route (direct, or via middleman: domestic + forwarding)
  + middleman fees (if routed)
  + customs(dispatch_zone, customs_value, hs_category, preferential_origin)
  + import VAT (if applicable)
  + carrier handling fee (if applicable)
  − coupon (only if actually valid: ticks, min-basket, sale-exclusions)
```

Pure function, no I/O, no LLM. Unit-tested against hand-computed cases, including the PDF's £59 → €81.60 example and every customs branch below.

### 8a. Customs: yes, we can do the real thing

Real EU import rules are small enough to implement honestly as a rule table. Destination fixed: **Poland (EU), VAT 23%**.

| # | Dispatch | Intrinsic value | What applies |
|---|---|---|---|
| 1 | EU member state | any | Nothing at the border. Sticker is final (seller charges destination VAT via OSS). |
| 2 | Non-EU | ≤ €150 | **No customs duty** (de-minimis). **Import VAT 23%** on (goods + shipping) — *unless* the vendor is **IOSS-registered**, in which case VAT was already in the sticker. If not IOSS: **carrier handling fee** (postal ≈ €6, courier ≈ €15). |
| 3 | Non-EU | > €150 | **Customs duty** on customs value (goods + shipping + insurance), rate by HS category: **sneakers with textile uppers (HS 6404): 16.9%**; leather uppers (HS 6403): 8%. Then **VAT 23% on (customs value + duty)**. Plus handling fee. |
| 4 | UK or Japan (FTA partners) | > €150 | Duty is **0% only if the goods preferentially originate there** (EU–UK TCA / EU–Japan EPA). Sneakers made in Vietnam or China sold *from* a UK/JP shop **do not qualify** → rule 3 duty applies in full. |

Three implementation subtleties, stated openly in the pitch:
- The €150 **de-minimis threshold is on intrinsic goods value** (excluding shipping); the **VAT base includes shipping**. An item at €149 vs. €151 from the US crosses a genuine cost cliff — a planted trap.
- **IOSS** is a per-vendor boolean and materially changes sub-€150 comparisons (VAT-inclusive sticker vs. VAT-at-border + handling).
- Rule 4 is the demo's best "the agent knows Brexit" moment: a tempting London listing that a naive tracker prices at sticker + shipping, and our engine correctly loads with 16.9% duty + VAT.

What we deliberately *don't* do: the full TARIC database, quota codes, anti-dumping measures. One curated table, real rates, clearly scoped. That is defensible; pretending to full customs law is not.

### 8b. Middlemen (forwarding routes)

**What:** some shops don't ship to Poland. A middleman (think Buyee/ZenMarket for Japan, Shipito for the US) receives the parcel domestically and forwards it — for a fee, with a delay.

**How it changes the engine:**
- **Route enumeration:** for each offer, feasible routes = direct (if vendor `ships_to` includes PL) ∪ {via each middleman located in the vendor's country that forwards to PL, if `allow_middlemen`}. The engine prices *routes*, not offers, and picks the cheapest feasible one per offer.
- **Cost:** sticker + vendor's *domestic* shipping to the middleman + middleman fees (flat + % of value) + international leg (by weight bracket) + **customs computed on the true full value at the PL border** (rules 2–4 always apply — a forwarded parcel is a non-EU import with no IOSS, so border VAT + handling are unavoidable).
- **Time:** route ETA += middleman `extra_ticks` (processing + transit). Interacts with `deadline_tick` and, in monitor mode, with stock risk over the added days.
- **Risk:** forwarding adds a handling layer — a small trust haircut on the route, plus insurance as a feature.

### 8c. Geo-differentiated pricing & local sales

**What:** some prices only exist somewhere else. A Japanese shop runs a domestic promo; a regional storefront lists a lower price; a discount requires a local ID. Three tiers, modeled explicitly — because their statuses differ:

| Tier | Example | Access route | Status |
|---|---|---|---|
| `storefront` | jp-shop's regional site lists ¥9,900, visible to anyone, ships domestically only | Middleman (§8b) | Normal practice — proxy-buying services exist for exactly this. No gray area. |
| `ip_gated` | Promo shown/bookable only from a Japanese connection | "VPN" observation + middleman | ToS-gray — user-governed via the mandate knob. |
| `verified_local` | Requires local ID / residency / student status | None available to us | Unattainable — the agent must recognize it and skip. |

**Why the deterministic world makes this nearly free:** there is no real VPN. "Connecting from Japan" is an observation parameter — price becomes a function of *(listing, tick, viewer_geo)*, and the agent holds a set of observation geos = {home} ∪ permitted VPN geos. A consequential side effect: **permissions change what the agent can even see.** Under `geo_arbitrage: never`, the Tokyo promo is simply absent from the agent's observable market; flip to `allow` and the price surface expands. Same seed, two mandates, two visible worlds — a demo moment that makes "mandate" tangible.

**Governance — the tactics ladder.** v2 capped *money*; this caps *tactics*. One mandate knob: `geo_arbitrage: never | ask | allow`.
- `storefront` arbitrage is always permitted — it's ordinary §8b routing.
- `ip_gated` purchases follow the knob; on `ask`, the agent escalates once **with an LLM-written route summary**: the deterministic engine assembles the structured facts (route legs, fees, customs, ETA, cancellation estimate), and the LLM renders them as a plain-language card — *"Here's what I'd do: buy at shop X's Japan-only promo price via a JP observation point, ship to forwarder Y in Tokyo, forward to Warsaw (~9 days), clear Polish customs on the full value. Landed €71 vs €84 for the best EU option. Risk: ~12% chance the merchant cancels the order."* Every number in the card is injected from the route data, never generated by the LLM — the prose is the model's, the math is the engine's. One tap to approve or decline.
- `verified_local` is never attempted; counting one as available is an eval error.
- The pitch framing: caps on *money* (the ceiling) plus caps on *tactics* (the knob) — routine tactics just run, gray tactics run only with the user's informed, per-route consent, and everything is logged either way.

**Risk model:** `ip_gated` orders carry a merchant-side cancellation probability (foreign card + forwarding address + IP mismatch — the classic trigger trio), seeded per listing and hidden; the agent estimates it from observable signals. The EV gains a term: `− P(cancel) × (hassle + refund delay in ticks + deadline exposure)`. A cancelled purchase refunds after k ticks and the hunt continues — in immediate mode with a deadline this can flip the "cheapest" route to net-negative, which is precisely one of the planted traps.

**Arithmetic realism (one line):** JP stickers include 10% consumption tax, non-refundable through a forwarder (tax-free requires a physical tourist at the counter) — the Tokyo promo must beat the EU offer *after* that tax, middleman fees, and Polish import charges. Sometimes it genuinely does; sometimes the world plants the inversion.

---

## 9. The decision engine

**What:** for the hunted product, consume matched offers + routes + history + mandate, and output one action: `HOLD`, `ALERT`, `BUY`, or `ESCALATE` — with reasons.

**How — four layers, evaluated in order:**

**Layer 1 — Hard gates (deterministic, override nothing downstream can undo).**
- Landed (best feasible route) > cap → the offer cannot be bought this tick.
- Mandate expired/revoked → HOLD everything.
- Condition/exclusion violations (used, GS when excluded, reseller when excluded) → discard.
- `colorway_conflict` or `colorway_unconfirmed` → auto-buy ineligible (alert-only).
- Deadline set and route ETA misses it → route discarded.
- `verified_local` promo → unattainable, discarded. `ip_gated` route under `geo_arbitrage: never` → discarded; under `ask` → purchase blocked pending one human approval of the LLM-narrated route card (§8c).

**Layer 2 — Trust (deterministic).**
- **Whitelist short-circuit:** exact-domain match in `whitelist` → trust = 1.0, scoring skipped. Two caveats built in: (a) *exact* domain only — `adidas-outlet.shop` is not `adidas.com`; high string similarity to a whitelisted domain without an exact match is itself an **impersonation red flag** that *lowers* trust; (b) whitelist covers first-party storefronts, not third-party sellers on a whitelisted marketplace. And whitelist means *authentic and honest*, not *good value* — whitelisted offers still pass cap, colorway, and timing checks like everyone else.
- Everyone else: weighted score from observables — review count/average, review **velocity** (a burst of recent 5-stars on a young domain is a red flag), domain age, return policy, price deviation from market median (40% below everyone lowers trust). Routed offers inherit a small middleman haircut; `ip_gated` routes additionally carry the cancellation-risk EV term from §8c.
- Decide by **expected value, not blacklist**: `EV = P(legit) × savings_vs_next_best − P(scam) × (price + hassle)`. A 0.7-trust vendor saving €30 can legitimately beat a 0.99-trust vendor saving €2 — and the receipt says so.

**Layer 3 — Timing (mode-dependent).**
- **Monitor mode — optimal stopping.** Maintain the empirical distribution of daily best landed prices for this product; each tick estimate `P(better price within remaining horizon)` from distribution + trend. **Buy** when under cap AND that probability < threshold (~25%), or immediately when an auto-buy rule fires. **Hold** when under cap but a better price is still likely — and log that reasoning. The effective horizon is `min(mandate expiry, deadline − best feasible route ETA)` — so a "need it in 10 days" brief automatically makes the stopping rule more aggressive as feasible days run out, with no special-case code. A "LEGIT good deal" is precisely: passes Layers 1–2 with healthy EV, *and* Layer 3 says the price has genuinely broken (e.g., below the true 90-tick low, not a manipulated one — the anchor-reset trap is caught here, because our own observed history is the reference, not the vendor's claimed "was").
- **Immediate mode — Layer 3 is bypassed.** Candidate set = **current offers** (present tick only). The engine picks the best-EV route under cap among them and buys, or reports "nothing qualifies" with the near-misses and why (over cap by €X / trust too low / colorway unconfirmed / misses deadline). Same gates, same trust, same receipts — just no waiting. If nothing qualifies, immediate mode may hand off to monitor mode with one tap.

**Layer 4 — The judgment band (LLM, bounded).**
Offers surviving gates but ambiguous (decent EV + medium trust, or matcher flags) go to an LLM with structured context. It returns a recommendation + rationale — which still passes through Layer 1: the LLM can talk the engine out of a purchase, never into an over-cap one. `decided_by` is recorded per decision.

**Escalation:** unresolved-confidence cases produce one alert within the weekly budget. All escalations and alerts follow the §8c card pattern — engine assembles structured facts, LLM writes the narrative, numbers are injected from data. Escalate-everything is useless; decide-everything is scary; the alert budget makes the trade-off an explicit, tunable number.

### 9a. The two modes, side by side

| | Immediate execute | Monitor |
|---|---|---|
| Candidate set | Current offers (this tick, stock > 0) | Full timeline as it unfolds |
| Layers active | 1, 2, 4 | 1, 2, 3, 4 |
| Question answered | "What's the best legitimate buy *right now*?" | "When does a legitimately good deal appear?" |
| Failure output | Ranked near-misses + reasons; optional handoff to monitor | HOLD receipts explaining patience |
| Regret meaning | vs. best current offer (0 if engine is correct) | vs. true best in the world (timing skill) |

Both modes share every module; the mode flag only toggles Layer 3 and the candidate window. **Impatience cost** — mean(landed_immediate − landed_monitor) over identical seeds — becomes a headline metric: the measured price of "I want it now."

---

## 10. Receipts (the ledger)

Every action — including HOLDs on interesting offers — appends a receipt: tick, offer, route, full landed arithmetic term by term (sticker, FX@rate, shipping legs, middleman fees, duty rule applied, VAT, handling, coupon), trust factors with weights, stopping-probability estimate (monitor), which mandate rule fired, `decided_by`, action. Append-only JSON lines; the UI renders them as cards.

---

## 11. The eval harness

Run the agent over N seeded worlds (target 200–500), score against the dossier's ground truth, report mean ± spread:

- **Strike precision** — purchases that were legitimate good deals.
- **False-buy rate** — planted traps purchased ÷ traps encountered (target ≈ 0). Includes customs traps, whitelist impersonators, and net-negative geo baits.
- **Colorway error rate** — wrong-colorway purchases (target 0).
- **Geo-promo capture rate** — when arbitrage was permitted and a geo route was genuinely best, the agent took it.
- **Unattainable-promo errors** — `verified_local` offers counted as available (target 0).
- **Regret** — € paid minus true best legitimate landed price (monitor mode).
- **Impatience cost** — immediate vs. monitor on identical seeds.
- **Miss rate** — worlds where a legitimate under-cap deal existed but monitor never struck.
- **Alert efficiency** — alerts sent vs. budget vs. alerts a human would want.
- **Matching accuracy** — vs. `true_product_id` at colorway level.
- **Routing split** — % decided by code / LLM / human.
- **Mandate violations** — asserted **exactly 0** across every world: cap never exceeded, no purchase without consent, revocation honored, no `ip_gated` purchase without the `ask` approval when required. Run as an invariant test; it never fires.

**Baselines on identical worlds:** (a) *Greedy* — first sub-cap sticker; (b) *Sticker-only* — ignores landed cost (dies on customs and FX); (c) ours, immediate; (d) ours, monitor. The four-way table is the money slide.

---

## 12. The demo (5 minutes)

1. **Cold open (30s):** drop a screenshot. Brief + compiled mandate appear — "this JSON is the only authority under which this agent can spend money." Toggle shown: immediate / monitor.
2. **Immediate beat (30s):** run immediate mode → best legitimate current buy, receipt shows a Japan listing routed via a middleman beating the local shop *after* full customs math.
3. **Time machine (75s):** switch to monitor; 90 ticks scrub by. Annotations: *HELD — fake anchor (that "was €120" was never charged)* … *HELD — under cap, 60% chance of better price* … *HELD — London listing: +16.9% duty + VAT, over cap (goods don't qualify for TCA origin)* … *STRUCK — €76.40, receipt →*.
4. **Adversary moment (60s):** spawn live a whitelist-impersonator shop (`adidas-outlet.shop`, great price). Agent refuses; receipt explains exact-domain rule + impersonation flag. Then the `ask` tier fires — the LLM-written route card appears: *"Tokyo-only promo via forwarder: landed €71 vs €84 best-EU, ~9 days, est. 12% cancellation risk. Approve?"* — one tap, purchase, receipt.
5. **Proof (60s):** metrics over 500 worlds, four-policy table, impatience-cost number, and: *"tens of thousands of decisions, zero mandate violations, zero unauthorized euros, zero gray-zone purchases without explicit consent."*
6. **Close (15s):** routing split as the answer to the case's central question.

---

## 13. Build order

Dependency-ordered; cut from the bottom, never the top.

1. **World simulator + `price_events` + trap injection + ground-truth oracle + dossier writer** — the dossier is nearly free (it's the injection log, rendered).
2. **Landed-cost engine incl. the customs rule table** (pure function + unit tests per customs branch).
3. **Mandate schema + hard gates** (Layer 1) — the leash before the brain.
4. **Matcher** (tiers 1–3; style-code + colorway from day one — retrofitting identity granularity is painful).
5. **Trust + whitelist + EV** (Layer 2).
6. **Monitor timing** (Layer 3) → **immediate mode** falls out as the degenerate single-tick case (~an afternoon).
7. **Middleman routing** — extends the landed-cost engine with route enumeration; slot it here, after direct routes are solid. Then **geo pricing (§8c)** on top: the `storefront` tier is nearly free once routing exists; `ip_gated` + the governance knob + the cancellation model is the stretch layer (~half a day); `verified_local` traps take an hour.
8. **Eval harness + baselines** — start running the moment 1–3 exist; it will find your bugs.
9. **Receipts + timeline UI.**
10. **Intake LLM** (text → screenshot → voice-note transcript).
11. **Judgment band (Layer 4)** — an upgrade, not a dependency.
12. **Live adversary generator** — pure theater, only if everything above is done.

Split for 3–4 people: one owns world+dossier+eval, one owns landed-cost+customs+middlemen+decision engine, one owns UI+receipts, floater owns intake/LLM + pitch.

---

## 14. Explicitly out of scope

- Real scraping, real shops, real payments, PSP integration.
- **Full TARIC** — we implement a curated, real-rate rule table (§8a), not the customs database; quotas, anti-dumping, and per-material tariff splits stay out.
- Multi-item baskets, basket/consolidation optimization at the middleman.
- Price *forecasting* models — the stopping rule uses observed distribution + trend only.
- Real VPN/proxy infrastructure — observation geo is a simulation parameter, not networking.
- Middleman customs-compliance modeling — all simulated forwarders declare full value (decided in §15).
- Accounts, auth, persistence beyond JSON/SQLite.

---

## 15. Resolved decisions

1. **Destination & currency:** Poland; display currency **EUR** (world simulates EUR/PLN/GBP/USD/JPY).
2. **Time unit:** tick = 1 simulated day; "current offers" = this tick's rows with stock > 0.
3. **Deadlines:** relative, from the prompt — "need it in 10 days" / "need it in 25 days" → `need_within_ticks`. Deadline shortens the effective stopping horizon (§9, Layer 3).
4. **Under-declaring middleman trap: excluded.** All simulated forwarders declare full customs value; compliance modeling is out of scope (§14).
5. **`geo_arbitrage` default: `ask`.** Gray-zone routes are surfaced to the user as an LLM-written card explaining the route and every step to be taken, with all numbers injected from the engine's structured data; purchase proceeds only on explicit confirmation (§8c).