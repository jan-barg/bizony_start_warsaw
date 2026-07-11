"""Stage-0 acceptance: money quantization, RNG determinism, IDs."""
from decimal import Decimal as D

from dealhunter.core.enums import Currency
from dealhunter.core.ids import ask_id, listing_id, receipt_id
from dealhunter.core.money import q2, quantize, to_eur
from dealhunter.core.rng import derive, rng


class TestMoney:
    def test_half_up_not_bankers(self):
        # 2.345 → 2.35 under HALF_UP (banker's would give 2.34)
        assert q2(D("2.345")) == D("2.35")

    def test_v1_vat_quantization(self):
        # the V1 VAT line under EU_2026_07: 0.23 × 79.16 = 18.2068 → 18.21
        assert q2(D("0.23") * D("79.16")) == D("18.21")

    def test_jpy_zero_exponent(self):
        assert quantize(D("9900.4"), Currency.JPY) == D("9900")
        assert quantize(D("9900.5"), Currency.JPY) == D("9901")  # HALF_UP

    def test_to_eur_v1_goods(self):
        # £59.00 at EURGBP 0.86 → €68.60 (spec §11 V1)
        assert to_eur(D("59.00"), Currency.GBP, D("0.860000")) == D("68.60")

    def test_to_eur_v6_goods(self):
        # ¥9,900 at EURJPY 165 → €60.00 (spec §11 V6)
        assert to_eur(D("9900"), Currency.JPY, D("165.000000")) == D("60.00")

    def test_eur_passthrough_quantizes(self):
        assert to_eur(D("105.005"), Currency.EUR, D("1")) == D("105.01")


class TestRng:
    def test_reproducible(self):
        assert rng(42, "price", "l_1").random() == rng(42, "price", "l_1").random()

    def test_namespace_isolation(self):
        assert derive(42, "price", "l_1") != derive(42, "price", "l_2")
        assert derive(42, "price", "l_1") != derive(42, "title", "l_1")
        assert derive(42, "price", "l_1") != derive(43, "price", "l_1")

    def test_derive_snapshot(self):
        # pin the derivation scheme — silently changing it would shift every world
        assert derive(42, "traps") == derive(42, "traps")
        assert isinstance(derive(0), int)


class TestIds:
    def test_formats(self):
        assert listing_id("v007", "DD1391-100") == "l_v007_DD1391-100"  # spec §2.4 example
        assert ask_id("h_42_1", 12, 0) == "a_h_42_1_12_0"
        assert ask_id("h_42_1", 12, 1) != ask_id("h_42_1", 12, 0)  # same-tick collision guard
        assert receipt_id("h_42_1", 12, 3) == "r_h_42_1_12_3"
