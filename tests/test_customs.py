from decimal import Decimal as D

from dealhunter.core.config import Constants
from dealhunter.core.enums import Carrier, HsCategory, Ruleset, Zone
from dealhunter.engine.customs import import_charges, preferential


CFG = Constants()


def amounts(lines):
    return {line.code: line.amount_eur for line in lines}


def test_eu_dispatch_has_no_border_charges():
    assert import_charges(
        Ruleset.EU_2026_07,
        Zone.EU,
        D("500.00"),
        D("25.00"),
        HsCategory.FOOTWEAR_TEXTILE,
        "VN",
        False,
        Carrier.COURIER,
        CFG,
    ) == []


def test_exactly_150_is_low_value_and_postal_handling_applies():
    got = amounts(
        import_charges(
            Ruleset.EU_2026_07,
            Zone.JP,
            D("150.00"),
            D("10.00"),
            HsCategory.FOOTWEAR_TEXTILE,
            "VN",
            False,
            Carrier.POSTAL,
            CFG,
        )
    )
    assert got == {
        "DUTY_FLAT": D("3.00"),
        "VAT_IMPORT": D("37.49"),
        "HANDLING": D("6.00"),
    }


def test_leather_rate_and_half_up_quantization():
    got = amounts(
        import_charges(
            Ruleset.EU_2026_07,
            Zone.US,
            D("151.00"),
            D("10.00"),
            HsCategory.FOOTWEAR_LEATHER,
            "CN",
            False,
            Carrier.COURIER,
            CFG,
        )
    )
    assert got["DUTY"] == D("12.88")
    assert got["VAT_IMPORT"] == D("39.99")


def test_preferential_origin_depends_on_origin_not_dispatch_only():
    assert preferential(Zone.UK, "GB")
    assert preferential(Zone.JP, "JP")
    assert not preferential(Zone.UK, "VN")
    assert not preferential(Zone.US, "US")
