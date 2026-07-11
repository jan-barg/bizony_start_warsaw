from decimal import Decimal as D
from pathlib import Path

from dealhunter.core.enums import AccessTier, Geo, GeoArb, Mode
from dealhunter.core.models import GeoPromo, Mandate, World
from dealhunter.engine.routes import enumerate_routes


ROOT = Path(__file__).resolve().parent.parent


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def mandate(**updates) -> Mandate:
    values = {
        "mode": Mode.IMMEDIATE,
        "cap_landed_eur": D("200"),
        "expires_tick": 10,
    }
    values.update(updates)
    return Mandate(**values)


def test_direct_vendor_has_one_base_route():
    routes = enumerate_routes("l_v003_DD1391-100", 0, mandate(), world())
    assert [(r.kind, r.access_tier, r.observation_geo) for r in routes] == [
        ("direct", AccessTier.BASE, Geo.PL)
    ]


def test_domestic_only_vendor_has_base_and_storefront_middleman_routes():
    routes = enumerate_routes("l_v004_DD1391-100", 0, mandate(), world())
    assert [(r.kind, r.access_tier, r.promo_id) for r in routes] == [
        ("middleman", AccessTier.BASE, None),
        ("middleman", AccessTier.STOREFRONT, "g_l_v004_DD1391-100_JP"),
    ]


def test_disabling_middlemen_removes_domestic_only_routes():
    assert enumerate_routes(
        "l_v004_DD1391-100", 0, mandate(allow_middlemen=False), world()
    ) == []


def test_ip_gated_visibility_follows_geo_mandate_and_verified_is_never_routed():
    w = world()
    promos = [
        *w.geo_promos,
        GeoPromo(
            id="g_ip",
            listing_id="l_v004_DD1391-100",
            viewer_geo=Geo.JP,
            promo_sticker=D("9000"),
            from_tick=0,
            to_tick=2,
            access_tier=AccessTier.IP_GATED,
            p_cancel=D("0.25"),
        ),
        GeoPromo(
            id="g_local",
            listing_id="l_v004_DD1391-100",
            viewer_geo=Geo.JP,
            promo_sticker=D("8000"),
            from_tick=0,
            to_tick=2,
            access_tier=AccessTier.VERIFIED_LOCAL,
        ),
    ]
    w = w.model_copy(update={"geo_promos": promos})

    never = enumerate_routes(
        "l_v004_DD1391-100", 0, mandate(geo_arbitrage=GeoArb.NEVER), w
    )
    ask = enumerate_routes(
        "l_v004_DD1391-100", 0, mandate(geo_arbitrage=GeoArb.ASK), w
    )
    assert AccessTier.IP_GATED not in {r.access_tier for r in never}
    assert AccessTier.IP_GATED in {r.access_tier for r in ask}
    assert AccessTier.VERIFIED_LOCAL not in {r.access_tier for r in ask}


def test_expired_promo_disappears_but_base_route_remains():
    routes = enumerate_routes("l_v004_DD1391-100", 10, mandate(), world())
    assert len(routes) == 1
    assert routes[0].access_tier == AccessTier.BASE
