"""Golden test vectors — implementation-spec.md §11. THE acceptance suite.

Every assertion here is real and hand-computed. All tests are xfail(strict=False)
at Stage 0 because the engine is a stub (NotImplementedError ⇒ expected failure);
as feat/engine lands each function, the vectors flip to XPASS and then the marks
are removed at sync point S1. Do NOT weaken the numbers to make tests pass —
the numbers are the spec.

Primary figures: Ruleset.EU_2026_07 (flat €3 low-value duty INSIDE the VAT base).
Bracketed figures: Ruleset.EU_2025_LEGACY.
"""
from decimal import Decimal as D
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import AccessTier, Carrier, Geo, HsCategory, Mode, Ruleset, Zone
from dealhunter.core.models import Coupon, Mandate, RouteSpec, World
from dealhunter.engine.customs import import_charges
from dealhunter.engine.landed import assemble

ROOT = Path(__file__).resolve().parent.parent
CFG = Constants()
engine_pending = pytest.mark.xfail(
    reason="engine not implemented yet (Stage 0) — flips green on feat/engine merge",
    strict=False,
)


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def by_code(lines) -> dict[str, D]:
    return {li.code: li.amount_eur for li in lines}


# --------------------------------------------------------------------- V1/V2
@engine_pending
def test_v1_uk_direct_sub150_non_ioss_courier():
    lines = import_charges(Ruleset.EU_2026_07, Zone.UK, D("68.60"), D("7.56"),
                           HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=False,
                           carrier=Carrier.COURIER, cfg=CFG)
    got = by_code(lines)
    assert got["DUTY_FLAT"] == D("3.00")
    assert got["VAT_IMPORT"] == D("18.21")   # 0.23 × (68.60 + 7.56 + 3.00)
    assert got["HANDLING"] == D("15.00")
    assert D("68.60") + D("7.56") + sum(li.amount_eur for li in lines) == D("112.37")


@engine_pending
def test_v1_legacy_ruleset():
    lines = import_charges(Ruleset.EU_2025_LEGACY, Zone.UK, D("68.60"), D("7.56"),
                           HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=False,
                           carrier=Carrier.COURIER, cfg=CFG)
    got = by_code(lines)
    assert "DUTY_FLAT" not in got
    assert got["VAT_IMPORT"] == D("17.52")   # 0.23 × 76.16
    assert D("68.60") + D("7.56") + sum(li.amount_eur for li in lines) == D("108.68")


@engine_pending
def test_v2_ioss_no_border_charges():
    for rs in (Ruleset.EU_2026_07, Ruleset.EU_2025_LEGACY):
        assert import_charges(rs, Zone.UK, D("68.60"), D("7.56"),
                              HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=True,
                              carrier=Carrier.COURIER, cfg=CFG) == []
    # landed = 68.60 + 7.56 = 76.16 — the IOSS demo pair with V1


# --------------------------------------------------------------------- V3/V4/V5
@engine_pending
def test_v3_us_cliff_low_side():
    lines = import_charges(Ruleset.EU_2026_07, Zone.US, D("135.45"), D("16.36"),
                           HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=False,
                           carrier=Carrier.COURIER, cfg=CFG)
    got = by_code(lines)
    assert got["DUTY_FLAT"] == D("3.00")
    assert got["VAT_IMPORT"] == D("35.61")   # 0.23 × 154.81
    assert D("135.45") + D("16.36") + sum(li.amount_eur for li in lines) == D("205.42")


@engine_pending
def test_v4_us_cliff_high_side():
    lines = import_charges(Ruleset.EU_2026_07, Zone.US, D("153.64"), D("16.36"),
                           HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=False,
                           carrier=Carrier.COURIER, cfg=CFG)
    got = by_code(lines)
    assert got["DUTY"] == D("28.73")         # 16.9% × 170.00
    assert got["VAT_IMPORT"] == D("45.71")   # 0.23 × 198.73
    assert got["HANDLING"] == D("15.00")
    assert D("153.64") + D("16.36") + sum(li.amount_eur for li in lines) == D("259.44")


@engine_pending
def test_v5_fta_origin_trap():
    vn = import_charges(Ruleset.EU_2026_07, Zone.UK, D("153.64"), D("16.36"),
                        HsCategory.FOOTWEAR_TEXTILE, "VN", ioss=False,
                        carrier=Carrier.COURIER, cfg=CFG)
    gb = import_charges(Ruleset.EU_2026_07, Zone.UK, D("153.64"), D("16.36"),
                        HsCategory.FOOTWEAR_TEXTILE, "GB", ioss=False,
                        carrier=Carrier.COURIER, cfg=CFG)
    assert by_code(vn)["DUTY"] == D("28.73")      # VN origin from UK: full duty
    assert "DUTY" not in by_code(gb)              # GB preferential origin: duty zeroed


# --------------------------------------------------------------------- V6/V7 (fixture-integrated)
def _v6_route() -> RouteSpec:
    return RouteSpec(kind="middleman", middleman_id="m_01", observation_geo=Geo.JP,
                     access_tier=AccessTier.STOREFRONT, promo_id="g_l_v004_DD1391-100_JP")


@engine_pending
def test_v6_jp_storefront_promo_via_middleman():
    q = assemble("l_v004_DD1391-100", _v6_route(), tick=0, world=world(), cfg=CFG)
    got = by_code(q.line_items)
    assert got["GOODS"] == D("60.00")
    assert got["SHIP_DOM"] == D("4.85")
    assert got["MM_FLAT"] == D("3.50")
    assert got["MM_PCT"] == D("1.20")
    assert got["SHIP_INTL"] == D("14.00")
    assert got["DUTY_FLAT"] == D("3.00")
    assert got["VAT_IMPORT"] == D("18.83")   # 0.23 × (60 + 4.85 + 14 + 3) — dom leg IN the base
    assert got["HANDLING"] == D("6.00")      # middleman intl_carrier = POSTAL
    assert q.landed_eur == D("111.38")       # [legacy: 107.69]


@engine_pending
def test_v7_coupon_ordering():
    w = world()
    coupon = Coupon(id="c_l_v004_DD1391-100_0", code="TOKYO10", kind="pct", value=D("10"),
                    min_basket=None, excludes_sale=False, valid_from=0, valid_to=9)
    w = w.model_copy(update={"coupons": [*w.coupons, coupon]})
    for pe in w.price_events:
        if pe.listing_id == "l_v004_DD1391-100":
            pe.coupon_id = coupon.id
    q = assemble("l_v004_DD1391-100", _v6_route(), tick=0, world=w, cfg=CFG)
    got = by_code(q.line_items)
    assert got["COUPON"] == D("-6.00")
    assert got["MM_PCT"] == D("1.08")        # 2% of 54.00 — coupon reduces the % fee
    assert got["DUTY_FLAT"] == D("3.00")
    assert got["VAT_IMPORT"] == D("17.45")   # 0.23 × (54 + 18.85 + 3)
    assert q.landed_eur == D("103.88")       # [legacy: 100.19]


# --------------------------------------------------------------------- V8/V8a
@engine_pending
def test_v8_receipt_sum_property():
    """Every assembled quote's lines sum exactly to landed_eur (§2.1)."""
    from dealhunter.engine.routes import enumerate_routes
    w = world()
    mandate = Mandate(mode=Mode.IMMEDIATE, cap_landed_eur=D("500"), expires_tick=10)
    checked = 0
    for listing in w.listings:
        for tick in range(w.horizon):
            for route in enumerate_routes(listing.id, tick, mandate, w):
                q = assemble(listing.id, route, tick, w, CFG)
                assert sum(li.amount_eur for li in q.line_items) == q.landed_eur
                checked += 1
    assert checked > 100


@engine_pending
def test_v8a_coupon_boundary_trio():
    w = world()
    route = RouteSpec(kind="direct", observation_geo=Geo.PL, access_tier=AccessTier.BASE)
    # (a) expired-by-one: coupon valid 0..3, attached at tick 4 ⇒ omitted + reason
    q = assemble("l_v001_GW2288", route, tick=4, world=w, cfg=CFG)
    assert "COUPON" not in by_code(q.line_items)
    # (c) excludes_sale on an on_sale tick ⇒ omitted
    q = assemble("l_v002_DD1391-100", route, tick=5, world=w, cfg=CFG)
    assert "COUPON" not in by_code(q.line_items)
    # (b) min_basket exactly == sticker ⇒ applies (≤ inclusive): tick 0, sticker 105 ≥ 50
    q = assemble("l_v002_DD1391-100", route, tick=2, world=w, cfg=CFG)
    assert by_code(q.line_items)["COUPON"] == D("-10.50")


# --------------------------------------------------------------------- V9/V10
@engine_pending
def test_v9_stopping_sanity():
    from dealhunter.engine.stopping import p_better  # module lands with feat/engine
    hist = [D("100")] * 12 + [D("90")] * 8            # 8 of 20 beat current−δ
    assert abs(p_better(hist, current_best=D("95"), horizon=10, cfg=CFG) - D("0.9948")) < D("0.001")
    assert abs(p_better(hist, current_best=D("95"), horizon=1, cfg=CFG) - D("0.409")) < D("0.001")


@pytest.mark.integration
def test_v10_determinism_byte_identical():
    """Same (seed, template, NullClient) ⇒ byte-identical receipts. Runs at S2
    when world gen + engine + matcher are merged."""
    pytest.skip("sync-point S2 test — needs generate_world + run_monitor")
