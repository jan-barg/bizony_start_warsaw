"""Deterministic canonical product catalog (implementation spec §4.1)."""
from __future__ import annotations

from decimal import Decimal

from ..core.config import Constants
from ..core.enums import HsCategory
from ..core.ids import product_id
from ..core.models import ColorwayAlias, Product
from ..core.rng import rng


def _product(
    style_code: str,
    brand: str,
    model: str,
    colorway: str,
    fair_price: str,
    hs: HsCategory,
    origin: str,
    weight: str,
    *,
    kids_of: str | None = None,
) -> Product:
    sizes = (
        [Decimal("35"), Decimal("36"), Decimal("37"), Decimal("38"), Decimal("39"), Decimal("40")]
        if kids_of
        else [Decimal("40"), Decimal("41"), Decimal("42"), Decimal("43"), Decimal("44"), Decimal("45")]
    )
    return Product(
        id=product_id(style_code),
        brand=brand,
        model=model,
        colorway_name=colorway,
        style_code=style_code,
        sizes_eu=sizes,
        fair_price_eur=Decimal(fair_price),
        hs_category=hs,
        origin_country=origin,
        weight_kg=Decimal(weight),
        is_kids_version_of=kids_of,
    )


def _handcrafted() -> list[Product]:
    textile = HsCategory.FOOTWEAR_TEXTILE
    leather = HsCategory.FOOTWEAR_LEATHER
    return [
        _product("DD1391-100", "Nike", "Dunk Low", "White/Black", "110.00", textile, "VN", "1.20"),
        _product("DD1503-101", "Nike", "Dunk Low", "Photon Dust/Grey", "110.00", textile, "VN", "1.20"),
        _product("CW1590-100", "Nike", "Dunk Low GS", "White/Black", "60.50", textile, "VN", "0.90", kids_of="DD1391-100"),
        _product("DZ5485-612", "Nike", "Air Jordan 1 High", "Varsity Red/Black", "180.00", leather, "CN", "1.40"),
        _product("DH3097-100", "Nike", "Air Jordan 1 High", "University Blue/White", "180.00", leather, "CN", "1.40"),
        _product("FD1437-612", "Nike", "Air Jordan 1 High GS", "Varsity Red/Black", "99.00", leather, "CN", "1.05", kids_of="DZ5485-612"),
        _product("GW2288", "Adidas", "Samba OG", "Cloud White/Core Black", "95.00", leather, "VN", "1.10"),
        _product("IE3675", "Adidas", "Samba OG Kids", "Cloud White/Core Black", "52.25", leather, "VN", "0.82", kids_of="GW2288"),
        _product("M990GL6", "New Balance", "990v6", "Grey", "200.00", textile, "ID", "1.30"),
        _product("1201A019-200", "Asics", "Gel-Kayano 14", "Cream/Black", "155.00", textile, "ID", "1.15"),
    ]


def build_catalog(seed: int, cfg: Constants) -> tuple[list[Product], list[ColorwayAlias]]:
    """Build the configured catalog using only the ``("catalog",)`` stream."""
    stream = rng(seed, "catalog")
    products = _handcrafted()[: cfg.N_PRODUCTS_HANDCRAFTED]

    brands = ["Nike", "Adidas", "New Balance", "Asics", "Puma", "Reebok"]
    models = ["Runner Pro", "Court Classic", "Street One", "Trail Nova", "Retro Pace"]
    colorways = [
        "Black/White", "Sail/Gum", "Navy/Cream", "Forest/White", "Silver/Blue",
        "Burgundy/Grey", "Sand/Olive", "White/Red",
    ]
    origins = ["VN", "CN", "ID"]

    for n in range(cfg.N_PRODUCTS_GENERATED):
        brand = brands[stream.randrange(len(brands))]
        model = models[(n + stream.randrange(len(models))) % len(models)]
        colorway = colorways[(n * 3 + stream.randrange(len(colorways))) % len(colorways)]
        style_code = f"SH{n + 1:03d}{stream.randrange(100, 1000)}"
        fair_cents = stream.randrange(8500, 21001, 50)
        hs = HsCategory.FOOTWEAR_LEATHER if stream.random() < 0.28 else HsCategory.FOOTWEAR_TEXTILE
        products.append(
            _product(
                style_code,
                brand,
                model,
                colorway,
                str(Decimal(fair_cents) / 100),
                hs,
                origins[stream.randrange(len(origins))],
                str(Decimal(stream.randrange(95, 151)) / 100),
            )
        )

    alias_rows = [
        ("DD1391-100", "Panda"),
        ("DD1503-101", "Photon Dust"),
        ("DZ5485-612", "Lost and Found"),
        ("DH3097-100", "University Blue"),
        ("GW2288", "Classic Samba"),
        ("M990GL6", "Castlerock"),
        ("1201A019-200", "Cream Black"),
        ("DD1391-100", "White Black"),
    ]
    present_codes = {p.style_code for p in products}
    aliases = [ColorwayAlias(style_code=code, alias=alias) for code, alias in alias_rows if code in present_codes]
    return products, aliases
