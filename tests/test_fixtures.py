"""Stage-0 acceptance: fixtures validate against the frozen models and
serialization is deterministic (spec §6.3 invariant 6 groundwork)."""
import json
from decimal import Decimal as D
from pathlib import Path

from dealhunter.core.enums import AccessTier, Carrier, Geo
from dealhunter.core.models import Receipt, Vendor, World, canonical_json, quote_hash

ROOT = Path(__file__).resolve().parent.parent


def load_world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


class TestMiniWorld:
    def test_validates(self):
        w = load_world()
        assert len(w.listings) == 8
        assert len(w.price_events) == 8 * 10
        assert len(w.traps) == 2

    def test_v1_listing_numbers(self):
        """The V1 golden-vector inputs exist verbatim: £59.00 sticker, £6.50 EU
        ship, courier, UK non-IOSS vendor (spec §11 V1)."""
        w = load_world()
        v = next(v for v in w.vendors if v.id == "v_003")
        assert v.currency == "GBP" and not v.ioss_registered
        cost, carrier = v.shipping_table["EU"]
        assert (cost, carrier) == (D("6.50"), Carrier.COURIER)
        pe = next(p for p in w.price_events if p.listing_id == "l_v003_DD1391-100" and p.tick == 0)
        assert pe.sticker == D("59.00")
        assert next(f for f in w.fx if f.pair == "EURGBP" and f.tick == 0).rate == D("0.860000")

    def test_v6_route_numbers(self):
        """V6 inputs: ¥9,900 storefront promo, ¥800 dom ship, mm €3.50 + 2%,
        1.2 kg → €14.00 bracket, POSTAL, JP vendor not shipping to PL."""
        w = load_world()
        v = next(v for v in w.vendors if v.id == "v_004")
        assert Geo.PL not in v.ships_to
        assert v.domestic_shipping == (D("800"), Carrier.POSTAL)
        promo = next(g for g in w.geo_promos if g.listing_id == "l_v004_DD1391-100")
        assert promo.promo_sticker == D("9900") and promo.access_tier == AccessTier.STOREFRONT
        mm = w.middlemen[0]
        assert (mm.fee_flat_eur, mm.fee_pct, mm.intl_carrier) == (D("3.50"), D("0.02"), Carrier.POSTAL)
        product = next(p for p in w.products if p.id == "p_DD1391-100")
        bracket = next(price for max_kg, price in mm.intl_shipping_eur if product.weight_kg <= max_kg)
        assert bracket == D("14.00")
        assert next(f for f in w.fx if f.pair == "EURJPY" and f.tick == 0).rate == D("165.000000")

    def test_trap_labels_present(self):
        w = load_world()
        assert any(listing.is_bait for listing in w.listings)
        assert {t.trap_type for t in w.traps} == {"bait", "colorway"}

    def test_coupon_shapes(self):
        w = load_world()
        expired = next(c for c in w.coupons if c.id == "c_l_v001_GW2288_0")
        assert expired.valid_to < 9  # attached beyond validity — the V8a(a) shape
        sale_excl = next(c for c in w.coupons if c.excludes_sale)
        drop = next(p for p in w.price_events
                    if p.listing_id == "l_v002_DD1391-100" and p.on_sale)
        assert drop.coupon_id == sale_excl.id  # excludes_sale ∧ on_sale collision exists


class TestDeterministicSerialization:
    def test_canonical_json_stable_across_set_construction(self):
        w = load_world()
        v = w.vendors[0]
        shuffled = Vendor(**{**v.model_dump(), "ships_to": set(reversed(sorted(v.ships_to)))})
        assert canonical_json(v) == canonical_json(shuffled)

    def test_world_roundtrip_identical(self):
        w = load_world()
        assert canonical_json(World.model_validate_json(w.model_dump_json())) == canonical_json(w)

    def test_quote_hash_stable(self):
        rows = (ROOT / "fixtures" / "receipts_demo.jsonl").read_text().splitlines()
        r = next(Receipt.model_validate_json(row) for row in rows
                 if json.loads(row)["action"] == "BUY")
        assert quote_hash(r.chosen.quote) == quote_hash(r.chosen.quote)


class TestReceiptsDemo:
    def test_all_rows_validate_and_cover_actions(self):
        rows = (ROOT / "fixtures" / "receipts_demo.jsonl").read_text().splitlines()
        receipts = [Receipt.model_validate_json(row) for row in rows]
        assert len(receipts) >= 20
        actions = {r.action for r in receipts}
        assert {"BUY", "ALERT", "ASK", "HOLD", "ESCALATE_NONE_FOUND"} <= {a.value for a in actions}
        ask_tiers = {r.escalation_tier for r in receipts if r.action == "ASK"}
        assert ask_tiers == {"E2", "E3"}  # both ask kinds represented for the UI
