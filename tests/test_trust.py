from decimal import Decimal as D
from pathlib import Path

from dealhunter.core.config import Constants
from dealhunter.core.enums import AccessTier, Channel, Currency, Geo, TrustFlag
from dealhunter.core.models import LineItem, RouteQuote, Vendor, World
from dealhunter.engine.trust import expected_value, trust_score


ROOT = Path(__file__).resolve().parent.parent
CFG = Constants()


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def quote(landed: str, *, kind="direct", access=AccessTier.BASE, cancel="0") -> RouteQuote:
    amount = D(landed)
    return RouteQuote(
        listing_id="l_v001_DD1391-100",
        tick=0,
        kind=kind,
        middleman_id="m_01" if kind == "middleman" else None,
        observation_geo=Geo.PL,
        access_tier=access,
        line_items=[LineItem(code="GOODS", label="goods", amount_eur=amount)],
        landed_eur=amount,
        eta_ticks=2,
        p_cancel_est=D(cancel),
    )


def vendor(domain: str, **updates) -> Vendor:
    values = {
        "id": "v_test",
        "name": "Test",
        "domain": domain,
        "geo": Geo.DE,
        "currency": Currency.EUR,
        "channel": Channel.AUTHORIZED_RETAILER,
        "ships_to": {Geo.PL},
        "shipping_table": {"EU": (D("5"), "COURIER")},
        "domestic_shipping": (D("4"), "COURIER"),
        "return_days": 14,
        "domain_age_days": 2000,
        "review_count": 1000,
        "review_avg": D("4.5"),
        "reviews_last_30d": 20,
        "ioss_registered": False,
        "is_fraudulent": False,
    }
    values.update(updates)
    return Vendor(**values)


def test_exact_whitelist_short_circuits():
    score, flags = trust_score(vendor("adidas.com"), quote("100"), world(), CFG)
    assert score == D("1.00")
    assert flags == set()


def test_whitelist_impersonator_is_flagged_and_capped():
    score, flags = trust_score(vendor("adidas.co"), quote("100"), world(), CFG)
    assert score <= D("0.15")
    assert TrustFlag.IMPERSONATION_SUSPECTED in flags


def test_observable_risk_flags_reduce_trust():
    risky = vendor(
        "new-no-returns.example",
        domain_age_days=20,
        return_days=0,
        review_count=20,
        reviews_last_30d=15,
    )
    score, flags = trust_score(risky, quote("100"), world(), CFG)
    assert score < D("0.50")
    assert {TrustFlag.YOUNG_DOMAIN, TrustFlag.NO_RETURNS, TrustFlag.REVIEW_BURST} <= flags


def test_expected_value_can_prefer_safety_over_lower_price():
    safer = expected_value(quote("78"), D("0.99"), D("80"), None, CFG)
    riskier = expected_value(quote("70"), D("0.70"), D("80"), None, CFG)
    assert safer > riskier


def test_ip_gated_cancellation_and_deadline_reduce_ev():
    gray = quote("70", access=AccessTier.IP_GATED, cancel="0.12")
    relaxed = expected_value(gray, D("0.90"), D("80"), 10, CFG)
    urgent = expected_value(gray, D("0.90"), D("80"), 4, CFG)
    assert urgent < relaxed
