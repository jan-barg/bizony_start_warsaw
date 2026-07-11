"""One-shot generator for the Stage-0 fixtures (committed artifacts, then FROZEN).

fixtures/mini_world.json  — hand-specified World: the shared test bed. Its numbers
deliberately match golden vectors V1 (UK £59 + £6.50 courier) and V6 (JP ¥9,900
storefront promo via middleman, ¥800 dom ship, 1.2 kg → €14.00 bracket, postal),
so the engine branch can assert spec §11 verbatim against real fixture objects.

fixtures/receipts_demo.jsonl — synthetic receipts covering every Action, for UI
development only (Work Order 4). Not a truth source.

Run once from repo root:  python scripts/make_fixtures.py
"""
from __future__ import annotations

import json
from decimal import Decimal as D
from pathlib import Path

from dealhunter.core.enums import (
    AccessTier, Action, AskKind, Carrier, Channel, Condition, Currency,
    DecidedBy, Eligibility, Geo, HuntStatus, MatchFlag, TrustFlag,
)
from dealhunter.core.models import (
    Ask, ColorwayAlias, Coupon, Evaluation, FxRate, GeoPromo, LineItem, Listing,
    MatchResult, Middleman, PriceEvent, Product, Receipt, RouteQuote,
    StoppingSnapshot, TrapRecord, Vendor, WhitelistEntry, World,
    canonical_json, quote_hash,
)

ROOT = Path(__file__).resolve().parent.parent
TICKS = 10

# --------------------------------------------------------------------------- products
products = [
    Product(id="p_DD1391-100", brand="Nike", model="Dunk Low", colorway_name="White/Black",
            style_code="DD1391-100", sizes_eu=[D("42"), D("43"), D("44")],
            fair_price_eur=D("110.00"), hs_category="FOOTWEAR_TEXTILE",
            origin_country="VN", weight_kg=D("1.20")),
    Product(id="p_CW1590-100", brand="Nike", model="Dunk Low GS", colorway_name="White/Black",
            style_code="CW1590-100", sizes_eu=[D("36"), D("37"), D("38")],
            fair_price_eur=D("60.00"), hs_category="FOOTWEAR_TEXTILE",
            origin_country="VN", weight_kg=D("0.90"), is_kids_version_of="DD1391-100"),
    Product(id="p_DZ5485-612", brand="Nike", model="Air Jordan 1 High", colorway_name="Varsity Red/Black",
            style_code="DZ5485-612", sizes_eu=[D("42"), D("43"), D("44")],
            fair_price_eur=D("180.00"), hs_category="FOOTWEAR_LEATHER",
            origin_country="CN", weight_kg=D("1.40")),
    Product(id="p_GW2288", brand="Adidas", model="Samba OG", colorway_name="Cloud White/Core Black",
            style_code="GW2288", sizes_eu=[D("42"), D("43"), D("44")],
            fair_price_eur=D("95.00"), hs_category="FOOTWEAR_LEATHER",
            origin_country="VN", weight_kg=D("1.10")),
    Product(id="p_M990GL6", brand="New Balance", model="990v6", colorway_name="Grey",
            style_code="M990GL6", sizes_eu=[D("42"), D("43"), D("44")],
            fair_price_eur=D("200.00"), hs_category="FOOTWEAR_TEXTILE",
            origin_country="US", weight_kg=D("1.30")),
]

aliases = [
    ColorwayAlias(style_code="DD1391-100", alias="Panda"),
    ColorwayAlias(style_code="DZ5485-612", alias="Lost and Found"),
]

# --------------------------------------------------------------------------- vendors
vendors = [
    Vendor(id="v_001", name="Adidas Official", domain="adidas.com", geo=Geo.DE,
           currency=Currency.EUR, channel=Channel.OFFICIAL,
           ships_to={Geo.DE, Geo.PL, Geo.FR, Geo.NL, Geo.IT, Geo.ES},
           shipping_table={"EU": (D("5.00"), Carrier.COURIER)},
           domestic_shipping=(D("4.00"), Carrier.COURIER),
           return_days=30, domain_age_days=4000, review_count=250000,
           review_avg=D("4.60"), reviews_last_30d=3000,
           ioss_registered=False, is_fraudulent=False),
    Vendor(id="v_002", name="SneakerHut", domain="sneakerhut.de", geo=Geo.DE,
           currency=Currency.EUR, channel=Channel.AUTHORIZED_RETAILER,
           ships_to={Geo.DE, Geo.PL, Geo.NL, Geo.FR},
           shipping_table={"EU": (D("6.90"), Carrier.COURIER)},
           domestic_shipping=(D("4.90"), Carrier.COURIER),
           return_days=14, domain_age_days=2200, review_count=1840,
           review_avg=D("4.40"), reviews_last_30d=25,
           ioss_registered=False, is_fraudulent=False),
    # V1 vendor: UK, non-IOSS, courier — £59 sticker + £6.50 ship
    Vendor(id="v_003", name="KickWorld UK", domain="kickworld.co.uk", geo=Geo.UK,
           currency=Currency.GBP, channel=Channel.AUTHORIZED_RETAILER,
           ships_to={Geo.UK, Geo.PL, Geo.DE},
           shipping_table={"EU": (D("6.50"), Carrier.COURIER)},
           domestic_shipping=(D("3.50"), Carrier.COURIER),
           return_days=14, domain_age_days=800, review_count=320,
           review_avg=D("4.10"), reviews_last_30d=8,
           ioss_registered=False, is_fraudulent=False),
    # V6 vendor: JP, does NOT ship to PL — middleman-only inventory
    Vendor(id="v_004", name="Tokyo Kicks", domain="tokyokicks.jp", geo=Geo.JP,
           currency=Currency.JPY, channel=Channel.AUTHORIZED_RETAILER,
           ships_to={Geo.JP},
           shipping_table={"JP": (D("800"), Carrier.POSTAL)},
           domestic_shipping=(D("800"), Carrier.POSTAL),
           return_days=7, domain_age_days=1500, review_count=900,
           review_avg=D("4.50"), reviews_last_30d=12,
           ioss_registered=False, is_fraudulent=False),
]

whitelist = [WhitelistEntry(domain="adidas.com", vendor_id="v_001")]

middlemen = [
    # V6 middleman: postal, 1.2 kg falls in the (2.0 → 14.00) bracket, flat €3.50, 2%
    Middleman(id="m_01", name="ZenForward", located_in=Geo.JP, forwards_to={Geo.PL, Geo.DE},
              fee_flat_eur=D("3.50"), fee_pct=D("0.02"),
              intl_shipping_eur=[(D("0.5"), D("9.00")), (D("1.0"), D("12.00")),
                                 (D("2.0"), D("14.00")), (D("5.0"), D("24.00"))],
              intl_carrier=Carrier.POSTAL, extra_ticks=8),
]

# --------------------------------------------------------------------------- listings
listings = [
    Listing(id="l_v001_GW2288", vendor_id="v_001",
            raw_title="adidas Samba OG Cloud White Core Black GW2288 EU 43",
            image_url="fixtures/img/gw2288.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_GW2288", is_bait=False, is_counterfeit=False),
    Listing(id="l_v001_DD1391-100", vendor_id="v_001",
            raw_title="Nike Dunk Low Retro White Black Panda DD1391-100 EU 43",
            image_url="fixtures/img/dd1391_official.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_DD1391-100", is_bait=False, is_counterfeit=False),
    Listing(id="l_v002_DD1391-100", vendor_id="v_002",
            raw_title="Nike Dunk Low Panda EU 43 brandneu OVP \U0001F525",
            image_url="fixtures/img/dd1391_hut.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_DD1391-100", is_bait=False, is_counterfeit=False),
    # wrong-colorway trap: title claims Black, true product is the Grey 990v6
    Listing(id="l_v002_M990GL6", vendor_id="v_002",
            raw_title="New Balance 990v6 Black EU 43 top deal",
            image_url="fixtures/img/m990.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_M990GL6", is_bait=False, is_counterfeit=False),
    # V1 listing
    Listing(id="l_v003_DD1391-100", vendor_id="v_003",
            raw_title="Nike Dunk Low White/Black DD1391-100 UK 8.5",
            image_url="fixtures/img/dd1391_uk.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_DD1391-100", is_bait=False, is_counterfeit=False),
    # bait trap
    Listing(id="l_v003_DZ5485-612", vendor_id="v_003",
            raw_title="Air Jordan 1 High Lost & Found UK 8.5 CHEAPEST ON THE NET!!",
            image_url="fixtures/img/aj1.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_DZ5485-612", is_bait=True, is_counterfeit=False),
    # V6 listing (storefront promo lives in geo_promos)
    Listing(id="l_v004_DD1391-100", vendor_id="v_004",
            raw_title="ナイキ ダンク LOW パンダ 27.5cm Dunk Low",
            image_url="fixtures/img/dd1391_jp.jpg", condition=Condition.NEW, size_eu=D("43"),
            true_product_id="p_DD1391-100", is_bait=False, is_counterfeit=False),
    # kids twin with adult-ambiguous title
    Listing(id="l_v004_CW1590-100", vendor_id="v_004",
            raw_title="Nike Dunk Low Panda 38 キッズ",
            image_url="fixtures/img/dd1391_gs.jpg", condition=Condition.NEW, size_eu=D("38"),
            true_product_id="p_CW1590-100", is_bait=False, is_counterfeit=False),
]

# --------------------------------------------------------------------------- coupons
coupons = [
    # expired-by-design: valid ticks 0..3, still attached to price events after
    Coupon(id="c_l_v001_GW2288_0", code="SAMBA5", kind="flat", value=D("5.00"),
           min_basket=None, excludes_sale=False, valid_from=0, valid_to=3),
    # valid mid-window, excludes_sale — pairs with the tick-5/6 flash drop below
    Coupon(id="c_l_v002_DD1391-100_2", code="PANDA10", kind="pct", value=D("10"),
           min_basket=D("50.00"), excludes_sale=True, valid_from=2, valid_to=8),
]

# --------------------------------------------------------------------------- price events
def steady(listing_id: str, sticker: str, stock: int, coupon_id: str | None = None,
           was: str | None = None) -> list[PriceEvent]:
    return [PriceEvent(listing_id=listing_id, tick=t, sticker=D(sticker), stock=stock,
                       on_sale=False, was_price_shown=D(was) if was else None,
                       coupon_id=coupon_id)
            for t in range(TICKS)]

price_events: list[PriceEvent] = []
price_events += steady("l_v001_GW2288", "100.00", 5, coupon_id="c_l_v001_GW2288_0")
price_events += steady("l_v001_DD1391-100", "119.00", 8)
# SneakerHut Panda: €105 with a flash drop to €94.90 on ticks 5–6 (on_sale=True)
for t in range(TICKS):
    drop = t in (5, 6)
    price_events.append(PriceEvent(
        listing_id="l_v002_DD1391-100", tick=t,
        sticker=D("94.90") if drop else D("105.00"),
        stock=4, on_sale=drop,
        was_price_shown=D("105.00") if drop else None,
        coupon_id="c_l_v002_DD1391-100_2" if 2 <= t <= 8 else None))
price_events += steady("l_v002_M990GL6", "185.00", 3)
price_events += steady("l_v003_DD1391-100", "59.00", 3)                       # V1
price_events += steady("l_v003_DZ5485-612", "99.00", 2, was="250.00")         # bait + fake anchor
price_events += steady("l_v004_DD1391-100", "14800", 6)                       # JP base; V6 promo below
price_events += steady("l_v004_CW1590-100", "8200", 4)

# --------------------------------------------------------------------------- fx (static)
fx = [FxRate(tick=t, pair=pair, rate=D(rate))
      for t in range(TICKS)
      for pair, rate in (("EURPLN", "4.250000"), ("EURGBP", "0.860000"),
                         ("EURUSD", "1.100000"), ("EURJPY", "165.000000"))]

# --------------------------------------------------------------------------- geo promos
geo_promos = [
    # V6: JP storefront promo ¥9,900, visible to anyone, domestic delivery only
    GeoPromo(id="g_l_v004_DD1391-100_JP", listing_id="l_v004_DD1391-100",
             viewer_geo=Geo.JP, promo_sticker=D("9900"), from_tick=0, to_tick=9,
             access_tier=AccessTier.STOREFRONT),
]

# --------------------------------------------------------------------------- traps
traps = [
    TrapRecord(trap_type="bait", listing_id="l_v003_DZ5485-612", vendor_id="v_003",
               ticks=(0, 9),
               explanation="AJ1 Lost & Found at £99 (~45% under market) with a fake £250 "
                           "'was' anchor never actually charged.",
               correct_behavior="Trust layer flags PRICE_TOO_GOOD; the agent never buys "
                                "and at most alerts with the flags stated."),
    TrapRecord(trap_type="colorway", listing_id="l_v002_M990GL6", vendor_id="v_002",
               ticks=(0, 9),
               explanation="Title says '990v6 Black'; the actual product is the Grey "
                           "colorway (M990GL6). Right model, wrong colorway claim.",
               correct_behavior="Matcher emits COLORWAY_CONFLICT (title tokens contradict "
                                "the style code); listing is alert-only, never auto-buy."),
]

world = World(seed=0, horizon=TICKS, products=products, aliases=aliases,
              vendors=vendors, whitelist=whitelist, middlemen=middlemen,
              listings=listings, price_events=price_events, coupons=coupons,
              fx=fx, geo_promos=geo_promos, traps=traps, oracle={})

# --------------------------------------------------------------------------- receipts demo
def demo_quote(listing_id: str, landed: str, tick: int, kind: str = "direct",
               mm: str | None = None, tier: AccessTier = AccessTier.BASE,
               geo: Geo = Geo.PL) -> RouteQuote:
    """UI-fixture quote: one GOODS line carrying the full landed value. Shape-valid,
    numerically trivial — receipts_demo is for component development only."""
    return RouteQuote(listing_id=listing_id, tick=tick, kind=kind, middleman_id=mm,
                      observation_geo=geo, access_tier=tier,
                      line_items=[LineItem(code="GOODS", label="demo goods", amount_eur=D(landed))],
                      landed_eur=D(landed), eta_ticks=2 if kind == "direct" else 9,
                      p_cancel_est=D("0.12") if tier == AccessTier.IP_GATED else D("0"))


def demo_eval(q: RouteQuote, trust: str, ev: str, elig: Eligibility = Eligibility.QUALIFYING,
              flags: list[MatchFlag] | None = None, gates: list[str] | None = None) -> Evaluation:
    return Evaluation(quote=q,
                      match=MatchResult(style_code="DD1391-100",
                                        colorway_confirmed=not flags, confidence=0.99,
                                        flags=flags or []),
                      trust=D(trust), trust_flags=set(), ev_eur=D(ev), eligibility=elig,
                      purchase_eligible=not flags, gate_failures=gates or [],
                      auto_buy_eligible=False)


HUNT = "h_0_1"
receipts: list[Receipt] = []
seq = 0

def rid() -> str:
    global seq
    seq += 1
    return f"r_{HUNT}_{seq}_{0}"

best = ["96.40", "95.10", "93.80", "92.20", "91.00", "89.60", "88.10", "86.90", "85.30", "84.20",
        "83.10", "82.40", "81.70", "81.00", "80.60"]
for i, landed in enumerate(best):
    q = demo_quote("l_v002_DD1391-100", landed, i)
    receipts.append(Receipt(
        id=rid(), hunt_id=HUNT, tick=i, action=Action.HOLD, decided_by=DecidedBy.CODE,
        chosen=None, considered=[demo_eval(q, "0.78", "-4.10")],
        reasons=[f"hold: best landed {landed} > p_better 0.62 at theta 0.25"],
        stopping=StoppingSnapshot(p_better=D("0.62"), horizon=90 - i, theta=D("0.25"), n_obs=i + 1)))

q_alert = demo_quote("l_v003_DD1391-100", "112.37", 15)
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=15, action=Action.ALERT,
                        decided_by=DecidedBy.CODE, chosen=demo_eval(q_alert, "0.71", "1.20"),
                        considered=[demo_eval(q_alert, "0.71", "1.20")],
                        reasons=["alert: new observed low 112.37, budget 1/2 left"]))

q_gray = demo_quote("l_v004_DD1391-100", "71.20", 22, kind="middleman", mm="m_01",
                    tier=AccessTier.IP_GATED, geo=Geo.JP)
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=22, action=Action.ASK,
                        decided_by=DecidedBy.CODE, escalation_tier="E2",
                        chosen=demo_eval(q_gray, "0.82", "6.40"),
                        considered=[demo_eval(q_gray, "0.82", "6.40")],
                        reasons=["gray route needs consent: IP_GATED under geo_arbitrage=ask",
                                 "landed 71.20 vs best non-gray 84.00, eta 9 ticks, est. cancel 12%"]))

q_overcap = demo_quote("l_v002_DD1391-100", "84.90", 31)
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=31, action=Action.ASK,
                        decided_by=DecidedBy.CODE, escalation_tier="E3",
                        chosen=demo_eval(q_overcap, "0.88", "-3.10", elig=Eligibility.OVER_CAP_BAND),
                        considered=[demo_eval(q_overcap, "0.88", "-3.10", elig=Eligibility.OVER_CAP_BAND)],
                        reasons=["over cap by 4.90 (cap 80.00, band 10%): best ever observed",
                                 "one-time cap extension requires approval"]))

receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=34, action=Action.HOLD,
                        decided_by=DecidedBy.CODE,
                        reasons=["order o_1 CANCELLED_BY_MERCHANT; refund due tick 37",
                                 "listing l_v004_DD1391-100 excluded; hunt resumes"]))
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=37, action=Action.HOLD,
                        decided_by=DecidedBy.CODE,
                        reasons=["refund settled for order o_1 (REFUNDED)"]))

q_buy = demo_quote("l_v002_DD1391-100", "76.40", 41)
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=41, action=Action.BUY,
                        decided_by=DecidedBy.CODE, escalation_tier="E1",
                        chosen=demo_eval(q_buy, "0.91", "5.80"),
                        considered=[demo_eval(q_buy, "0.91", "5.80")],
                        reasons=["stopping: p_better 0.18 < theta 0.25; landed 76.40 <= cap 80.00"],
                        stopping=StoppingSnapshot(p_better=D("0.18"), horizon=49, theta=D("0.25"), n_obs=40)))

q_none = demo_quote("l_v001_DD1391-100", "119.00", 0)
receipts.append(Receipt(id=rid(), hunt_id=HUNT, tick=0, action=Action.ESCALATE_NONE_FOUND,
                        decided_by=DecidedBy.CODE, escalation_tier="E5",
                        considered=[demo_eval(q_none, "0.97", "-14.00", elig=Eligibility.HARD_REJECT,
                                              gates=["over_cap_far: 119.00 > 88.00"])],
                        reasons=["immediate: nothing qualifies; top near-miss over cap by 39.00"]))

# --------------------------------------------------------------------------- write
fixtures = ROOT / "fixtures"
fixtures.mkdir(exist_ok=True)
(fixtures / "mini_world.json").write_text(
    json.dumps(json.loads(world.model_dump_json()), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
with (fixtures / "receipts_demo.jsonl").open("w") as f:
    for r in receipts:
        f.write(canonical_json(r) + "\n")

print(f"mini_world.json: {len(listings)} listings, {len(price_events)} price events, "
      f"{len(traps)} traps; receipts_demo.jsonl: {len(receipts)} rows")
print("sample quote_hash:", quote_hash(q_buy)[:16])
