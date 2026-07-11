"""Vendor, middleman, assortment, and messy-title generation (§4.2–§4.3)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from ..core.config import Constants
from ..core.enums import Carrier, Channel, Condition, Currency, Geo
from ..core.ids import listing_id, middleman_id, vendor_id
from ..core.models import ColorwayAlias, Listing, Middleman, Product, Vendor, WhitelistEntry
from ..core.rng import rng


_EU_GEOS = [Geo.DE, Geo.NL, Geo.FR, Geo.IT, Geo.ES, Geo.PL]


def _geo_plan(count: int) -> list[Geo]:
    if count >= 25:
        plan = [Geo.DE, Geo.NL, Geo.FR]
        plan += [_EU_GEOS[n % len(_EU_GEOS)] for n in range(12)]
        plan += [Geo.UK] * 4 + [Geo.US] * 3 + [Geo.JP] * 3
        return plan[:count]
    essential = [Geo.DE, Geo.NL, Geo.FR, Geo.PL, Geo.DE, Geo.UK, Geo.UK, Geo.US, Geo.JP, Geo.JP]
    cycle = [Geo.IT, Geo.ES, Geo.PL, Geo.UK, Geo.US, Geo.JP]
    return (essential + [cycle[n % len(cycle)] for n in range(max(0, count - len(essential)))])[:count]


def _currency(geo: Geo) -> Currency:
    return {Geo.UK: Currency.GBP, Geo.US: Currency.USD, Geo.JP: Currency.JPY}.get(geo, Currency.EUR)


def _money_in_currency(eur: Decimal, currency: Currency) -> Decimal:
    rate = {
        Currency.EUR: Decimal("1"),
        Currency.GBP: Decimal("0.86"),
        Currency.USD: Decimal("1.10"),
        Currency.JPY: Decimal("165"),
    }[currency]
    value = eur * rate
    quantum = Decimal("1") if currency is Currency.JPY else Decimal("0.01")
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def build_vendors(seed: int, cfg: Constants) -> tuple[list[Vendor], list[WhitelistEntry], list[Middleman]]:
    geos = _geo_plan(cfg.N_VENDORS)
    official = [
        ("Adidas Official", "adidas.com"),
        ("Nike Official", "nike.com"),
        ("New Balance Official", "newbalance.com"),
    ]
    geo_seen: dict[Geo, int] = {}
    vendors: list[Vendor] = []

    for index, geo in enumerate(geos, start=1):
        vid = vendor_id(index)
        stream = rng(seed, "vendor", vid)
        geo_seen[geo] = geo_seen.get(geo, 0) + 1
        currency = _currency(geo)
        is_official = index <= min(3, cfg.N_VENDORS)
        if is_official:
            name, domain = official[index - 1]
            channel = Channel.OFFICIAL
        else:
            label = stream.choice(["Kicks", "Sneaker House", "Sole Market", "Footwear Lab"])
            name = f"{geo.value} {label} {index:02d}"
            tld = {Geo.UK: "co.uk", Geo.US: "com", Geo.JP: "jp"}.get(geo, geo.value.lower())
            domain = f"{label.lower().replace(' ', '')}{index:02d}.{tld}"
            channel = Channel.RESELLER if index % 7 == 0 else Channel.AUTHORIZED_RETAILER

        if geo in _EU_GEOS:
            ships_to = set(_EU_GEOS)
        else:
            foreign_index = geo_seen[geo]
            blocked = (geo is Geo.JP and foreign_index <= 2) or (geo is Geo.US and foreign_index == 1)
            ships_to = {geo} if blocked else {geo, Geo.PL, Geo.DE}

        export_cost = _money_in_currency(
            Decimal(stream.randrange(550, 1801)) / 100,
            currency,
        )
        domestic_cost = _money_in_currency(
            Decimal(stream.randrange(300, 801)) / 100,
            currency,
        )
        carrier = Carrier.POSTAL if stream.random() < 0.40 else Carrier.COURIER
        return_days = 30 if is_official else stream.choice([0, 7, 14, 30])
        domain_age = stream.randrange(1200, 8001) if is_official else stream.randrange(180, 4501)
        review_count = stream.randrange(50000, 250001) if is_official else stream.randrange(40, 5001)
        reviews_30d = max(1, int(review_count * stream.uniform(0.005, 0.04)))
        review_avg = (Decimal(stream.randrange(370, 481)) / 100).quantize(Decimal("0.01"))
        ioss = geo not in _EU_GEOS and geo is not Geo.JP and stream.random() < 0.50
        vendors.append(
            Vendor(
                id=vid,
                name=name,
                domain=domain,
                geo=geo,
                currency=currency,
                channel=channel,
                ships_to=ships_to,
                shipping_table={"EU": (export_cost, carrier)},
                domestic_shipping=(domestic_cost, carrier),
                return_days=return_days,
                domain_age_days=domain_age,
                review_count=review_count,
                review_avg=review_avg,
                reviews_last_30d=reviews_30d,
                ioss_registered=ioss,
                is_fraudulent=False,
            )
        )

    whitelist = [WhitelistEntry(domain=v.domain, vendor_id=v.id) for v in vendors if v.channel is Channel.OFFICIAL]

    lanes = [Geo.JP, Geo.US, Geo.UK, Geo.JP]
    middlemen: list[Middleman] = []
    for index in range(1, cfg.N_MIDDLEMEN + 1):
        geo = lanes[(index - 1) % len(lanes)]
        stream = rng(seed, "vendor", middleman_id(index))
        middlemen.append(
            Middleman(
                id=middleman_id(index),
                name=f"{geo.value} Forward {index}",
                located_in=geo,
                forwards_to={Geo.PL, Geo.DE},
                fee_flat_eur=Decimal(stream.randrange(250, 401)) / 100,
                fee_pct=Decimal(stream.randrange(15, 31)) / 1000,
                intl_shipping_eur=[
                    (Decimal("0.5"), Decimal("9.00")),
                    (Decimal("1.0"), Decimal("12.00")),
                    (Decimal("2.0"), Decimal("16.00")),
                    (Decimal("5.0"), Decimal("24.00")),
                ],
                intl_carrier=Carrier.POSTAL if index % 2 else Carrier.COURIER,
                extra_ticks=stream.randrange(6, 13),
            )
        )
    return vendors, whitelist, middlemen


def _messy_title(
    seed: int,
    lid: str,
    product: Product,
    size_eu: Decimal,
    aliases_by_code: dict[str, list[str]],
) -> str:
    stream = rng(seed, "title", lid)
    colorway = product.colorway_name
    colorway_omitted = stream.random() < 0.20
    if colorway_omitted:
        colorway = ""
    elif aliases_by_code.get(product.style_code) and stream.random() < 0.30:
        colorway = stream.choice(aliases_by_code[product.style_code])

    size_text = f"EU {size_eu}"
    if stream.random() < 0.25:
        if size_eu == Decimal("43"):
            size_text = stream.choice(["US 9.5", "UK 8.5"])
        else:
            size_text = f"EU{size_eu}"
    pieces = [product.brand, product.model, colorway, size_text]
    if colorway_omitted or stream.random() < 0.45:
        pieces.append(product.style_code)
    if product.is_kids_version_of:
        pieces.append(stream.choice(["GS", "Kids", "Junior"]))
    if stream.random() < 0.35:
        pieces.append(stream.choice(["🔥", "new in box", "limited drop", "OVP"] ))
    if stream.random() < 0.15:
        pieces[stream.randrange(len(pieces))] = pieces[stream.randrange(len(pieces))].upper()
        if product.style_code not in pieces:
            pieces.append(product.style_code)
    return " ".join(piece for piece in pieces if piece).strip()


def build_listings(
    seed: int,
    cfg: Constants,
    products: list[Product],
    aliases: list[ColorwayAlias],
    vendors: list[Vendor],
) -> list[Listing]:
    aliases_by_code: dict[str, list[str]] = {}
    for alias in aliases:
        aliases_by_code.setdefault(alias.style_code, []).append(alias.alias)

    listings: list[Listing] = []
    for vendor_index, vendor in enumerate(vendors):
        stream = rng(seed, "assort", vendor.id)
        maximum = min(14, len(products))
        minimum = min(6, maximum)
        count = stream.randint(minimum, maximum)
        chosen = stream.sample(products, count)
        forced = products[vendor_index % len(products)]
        if forced not in chosen:
            chosen[-1] = forced
        chosen = sorted({p.style_code: p for p in chosen}.values(), key=lambda p: p.style_code)
        for product in chosen:
            lid = listing_id(vendor.id, product.style_code)
            title_stream = rng(seed, "title", lid)
            size = title_stream.choice(product.sizes_eu)
            listings.append(
                Listing(
                    id=lid,
                    vendor_id=vendor.id,
                    raw_title=_messy_title(seed, lid, product, size, aliases_by_code),
                    image_url=f"world://{seed}/images/{lid}.jpg",
                    condition=Condition.USED if title_stream.random() < 0.04 else Condition.NEW,
                    size_eu=size,
                    true_product_id=product.id,
                    is_bait=False,
                    is_counterfeit=False,
                )
            )
    return sorted(listings, key=lambda listing: listing.id)
