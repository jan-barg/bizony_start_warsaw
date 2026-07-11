from decimal import Decimal as D
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import AccessTier, Geo
from dealhunter.core.models import RouteSpec, World
from dealhunter.engine.landed import assemble


ROOT = Path(__file__).resolve().parent.parent
CFG = Constants()


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def test_uk_direct_quote_matches_complete_vector_total():
    quote = assemble(
        "l_v003_DD1391-100",
        RouteSpec(kind="direct", observation_geo=Geo.PL, access_tier=AccessTier.BASE),
        0,
        world(),
        CFG,
    )
    assert quote.landed_eur == D("112.37")
    assert quote.eta_ticks == 5
    assert sum(line.amount_eur for line in quote.line_items) == quote.landed_eur


def test_eu_direct_quote_has_no_import_lines():
    quote = assemble(
        "l_v001_GW2288",
        RouteSpec(kind="direct", observation_geo=Geo.PL, access_tier=AccessTier.BASE),
        0,
        world(),
        CFG,
    )
    codes = [line.code for line in quote.line_items]
    assert codes == ["GOODS", "COUPON", "SHIP_DIRECT"]
    assert quote.landed_eur == D("100.00")


def test_promo_route_must_match_the_listing():
    with pytest.raises(ValueError, match="does not belong"):
        assemble(
            "l_v004_CW1590-100",
            RouteSpec(
                kind="middleman",
                middleman_id="m_01",
                observation_geo=Geo.JP,
                access_tier=AccessTier.STOREFRONT,
                promo_id="g_l_v004_DD1391-100_JP",
            ),
            0,
            world(),
            CFG,
        )


def test_direct_route_cannot_claim_promotional_access():
    with pytest.raises(ValueError, match="direct routes"):
        assemble(
            "l_v004_DD1391-100",
            RouteSpec(
                kind="direct",
                observation_geo=Geo.JP,
                access_tier=AccessTier.STOREFRONT,
                promo_id="g_l_v004_DD1391-100_JP",
            ),
            0,
            world(),
            CFG,
        )
