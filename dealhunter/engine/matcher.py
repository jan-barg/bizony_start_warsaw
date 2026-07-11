"""Deterministic product matcher with a bounded veto-only LLM gray tier."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz.fuzz import token_set_ratio

from ..core.config import Constants
from ..core.enums import Condition, MatchFlag
from ..core.models import Brief, Listing, MatchResult, Product, World
from ..llm.client import LLMClient


_PHRASE_ALIASES = {
    "🐼": " panda ",
    "アディダス": " adidas ",
    "ナイキ": " nike ",
    "ダンク": " dunk ",
    "パンダ": " panda ",
    "サンバ": " samba ",
    "クラウドホワイト": " cloud white ",
    "コアブラック": " core black ",
    "ホワイト": " white ",
    "ブラック": " black ",
    "ニューバランス": " new balance ",
    "biały": " white ",
    "bialy": " white ",
    "czarny": " black ",
    "szary": " grey ",
    "weiß": " white ",
    "weiss": " white ",
    "schwarz": " black ",
    "one": " 1 ",
}

_BRAND_ALIASES = {
    "adidas": ("adidas",),
    "new balance": ("new balance", "nb"),
    "nike": ("nike", "jordan"),
}

_KIDS_MARKERS = (
    "gs",
    "ps",
    "td",
    "gg",
    "bg",
    "kids",
    "kid",
    "junior",
    "dziecięce",
    "dzieciece",
    "kinder",
    "キッズ",
)
_USED_MARKERS = ("used", "pre owned", "gebraucht", "używane", "uzywane", "中古")
_NEW_MARKERS = ("brand new", "new", "neu", "nowe", "新品")
_COLOR_WORDS = frozenset(
    {
        "beige",
        "black",
        "blue",
        "brown",
        "cream",
        "gold",
        "green",
        "grey",
        "gray",
        "orange",
        "pink",
        "purple",
        "red",
        "silver",
        "white",
        "yellow",
    }
)


# Exhaustive project table. Values are evidence labels, never interpolated.
_SIZE_ROWS = (
    ("35", "3", "2"),
    ("35.5", "3.5", "2.5"),
    ("36", "4", "3"),
    ("36.5", "4.5", "3.5"),
    ("37", "4.5", "3.5"),
    ("37.5", "5", "4"),
    ("38", "5.5", "4.5"),
    ("38.5", "6", "5"),
    ("39", "6.5", "5.5"),
    ("39.5", "6.5", "5.5"),
    ("40", "7", "6"),
    ("40.5", "7.5", "6.5"),
    ("41", "8", "7"),
    ("41.5", "8.5", "7.5"),
    ("42", "8.5", "7.5"),
    ("42.5", "9", "8"),
    ("43", "9.5", "8.5"),
    ("43.5", "9.5", "8.5"),
    ("44", "10", "9"),
    ("44.5", "10.5", "9.5"),
    ("45", "11", "10"),
    ("45.5", "11.5", "10.5"),
    ("46", "12", "11"),
    ("46.5", "12", "11"),
    ("47", "12.5", "11.5"),
    ("47.5", "13", "12"),
    ("48", "13.5", "12.5"),
    ("48.5", "14", "13"),
    ("49", "14.5", "13.5"),
    ("49.5", "15", "14"),
    ("50", "15.5", "14.5"),
)
_SIZE_TO_EU: dict[str, dict[Decimal, Decimal]] = {"EU": {}, "US": {}, "UK": {}}
for eu_value, us_value, uk_value in _SIZE_ROWS:
    for system, raw_value in (("EU", eu_value), ("US", us_value), ("UK", uk_value)):
        _SIZE_TO_EU[system].setdefault(Decimal(raw_value), Decimal(eu_value))


@dataclass(frozen=True)
class CandidateScore:
    product: Product
    score: float


def normalize_text(value: str) -> str:
    """Normalize user/catalog text without letting symbols join word tokens."""
    value = unicodedata.normalize("NFKC", value).casefold()
    for source, target in _PHRASE_ALIASES.items():
        value = value.replace(source, target)
    chars = [" " if unicodedata.category(char)[0] in {"P", "S"} else char for char in value]
    return " ".join("".join(chars).split())


def _compact(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", value).upper() if char.isalnum())


def _has_phrase(text: str, phrase: str) -> bool:
    return f" {normalize_text(phrase)} " in f" {text} "


def _detected_brands(text: str, world: World) -> set[str]:
    known = {normalize_text(product.brand) for product in world.products}
    found: set[str] = set()
    for brand in known:
        aliases = _BRAND_ALIASES.get(brand, (brand,))
        if any(_has_phrase(text, alias) for alias in aliases):
            found.add(brand)
    return found


def _model_present(text: str, product: Product) -> bool:
    compact_title = _compact(text)
    compact_model = _compact(normalize_text(product.model))
    if compact_model in compact_title:
        return True
    # Generated catalogs sometimes append edition markers; require every word.
    return all(_has_phrase(text, token) for token in normalize_text(product.model).split())


def _alias_phrases(product: Product, world: World) -> tuple[str, ...]:
    style_codes = {product.style_code}
    if product.is_kids_version_of:
        style_codes.add(product.is_kids_version_of)
    return tuple(alias.alias for alias in world.aliases if alias.style_code in style_codes)


def _color_evidence(text: str, product: Product, world: World) -> bool:
    title_tokens = set(text.split())
    for alias in _alias_phrases(product, world):
        alias_tokens = set(normalize_text(alias).split()) - {"and"}
        if _has_phrase(text, alias) or (alias_tokens and alias_tokens <= title_tokens):
            return True
    tokens = set(normalize_text(product.colorway_name).split())
    required = min(2, len(tokens))
    return bool(required) and len(tokens & title_tokens) >= required


def _color_words(value: str) -> set[str]:
    words = set(normalize_text(value).split()) & _COLOR_WORDS
    if "gray" in words:
        words.remove("gray")
        words.add("grey")
    return words


def _color_conflict(text: str, chosen: Product, world: World) -> bool:
    if _color_evidence(text, chosen, world):
        return False
    title_colors = _color_words(text)
    chosen_colors = _color_words(chosen.colorway_name)
    if title_colors and not title_colors <= chosen_colors:
        return True
    return any(
        product.style_code != chosen.style_code and _color_evidence(text, product, world)
        for product in world.products
    )


def _title_size_flags(title: str, structured_eu: Decimal) -> set[MatchFlag]:
    flags: set[MatchFlag] = set()
    normalized = unicodedata.normalize("NFKC", title).upper().replace(",", ".")
    explicit = re.findall(r"(?<![A-Z])(EU|US|UK)\s*[:\-/]?\s*(\d{1,2}(?:\.5)?)(?!\d)", normalized)
    for system, raw_size in explicit:
        converted = _SIZE_TO_EU[system].get(Decimal(raw_size))
        if converted is None or converted != structured_eu:
            flags.add(MatchFlag.SIZE_AMBIGUOUS)

    without_explicit = re.sub(
        r"(?<![A-Z])(EU|US|UK)\s*[:\-/]?\s*\d{1,2}(?:\.5)?(?!\d)", " ", normalized
    )
    without_codes = re.sub(r"[A-Z]{1,4}[\s\-–—‑‐]*\d{3,}(?:[\s\-–—‑‐]*\d{2,})?", " ", without_explicit)
    without_codes = re.sub(r"\b(?=\w*[A-Z])(?=\w*\d)\w+\b", " ", without_codes)
    for raw_size in re.findall(r"(?<![\d.])(\d{1,2}(?:\.5)?)(?![\d.])", without_codes):
        size = Decimal(raw_size)
        if Decimal("35") <= size <= Decimal("50"):
            if size != structured_eu:
                flags.add(MatchFlag.SIZE_AMBIGUOUS)
        elif Decimal("3.5") <= size <= Decimal("15"):
            flags.add(MatchFlag.SIZE_AMBIGUOUS)
    return flags


def _safety_flags(listing: Listing, brief: Brief) -> set[MatchFlag]:
    text = normalize_text(listing.raw_title)
    flags = _title_size_flags(listing.raw_title, listing.size_eu)
    if listing.size_eu != brief.size_eu:
        flags.add(MatchFlag.SIZE_MISMATCH)
    if any(_has_phrase(text, marker) for marker in _KIDS_MARKERS):
        flags.add(MatchFlag.KIDS_SIZING)
    title_used = any(_has_phrase(text, marker) for marker in _USED_MARKERS)
    title_new = any(_has_phrase(text, marker) for marker in _NEW_MARKERS)
    if listing.condition != brief.condition:
        flags.add(MatchFlag.CONDITION_MISMATCH)
    elif brief.condition == Condition.NEW and title_used:
        flags.add(MatchFlag.CONDITION_MISMATCH)
    elif brief.condition == Condition.USED and title_new:
        flags.add(MatchFlag.CONDITION_MISMATCH)
    return flags


def _model_evidence(text: str, product: Product, world: World, kids: bool) -> bool:
    if _model_present(text, product):
        return True
    if not kids or product.is_kids_version_of is None:
        return False
    adult = next(
        (candidate for candidate in world.products if candidate.style_code == product.is_kids_version_of),
        None,
    )
    return adult is not None and _model_present(text, adult)


def rank_catalog(query: str, world: World) -> list[CandidateScore]:
    """Rank canonical catalog rows for intake and matcher tier 3."""
    text = normalize_text(query)
    ranked = [
        CandidateScore(
            product=product,
            score=float(
                token_set_ratio(
                    text,
                    normalize_text(f"{product.brand} {product.model} {product.colorway_name}"),
                )
            ),
        )
        for product in world.products
    ]
    return sorted(ranked, key=lambda item: (-item.score, item.product.style_code))


def _exact_code_product(title: str, world: World) -> Product | None:
    compact_title = _compact(title)
    hits = [product for product in world.products if _compact(product.style_code) in compact_title]
    if not hits:
        return None
    return sorted(hits, key=lambda product: (-len(_compact(product.style_code)), product.style_code))[0]


def _result(
    product: Product,
    confidence: float,
    flags: set[MatchFlag],
    confirmed: bool,
) -> MatchResult:
    return MatchResult(
        style_code=product.style_code,
        confidence=confidence,
        colorway_confirmed=confirmed,
        flags=sorted(flags, key=lambda flag: flag.value),
    )


def match(listing: Listing, brief: Brief, world: World, llm: LLMClient) -> MatchResult:
    """Resolve observable listing evidence without reading generator truth labels."""
    del llm  # Tier 4 is wired by the bounded adjudication module in the next slice.
    cfg = Constants()
    text = normalize_text(listing.raw_title)
    flags = _safety_flags(listing, brief)

    code_product = _exact_code_product(listing.raw_title, world)
    if code_product is not None:
        detected_brands = _detected_brands(text, world)
        brand_conflict = bool(detected_brands) and normalize_text(code_product.brand) not in detected_brands
        color_conflict = _color_conflict(text, code_product, world)
        if brand_conflict:
            flags.add(MatchFlag.BRAND_CODE_CONFLICT)
        if color_conflict:
            flags.add(MatchFlag.COLORWAY_CONFLICT)
        confirmed = not brand_conflict and not color_conflict
        return _result(code_product, 0.40 if brand_conflict else 0.99, flags, confirmed)

    detected_brands = _detected_brands(text, world)
    model_candidates = [
        product
        for product in world.products
        if normalize_text(product.brand) in detected_brands
        and _model_evidence(text, product, world, MatchFlag.KIDS_SIZING in flags)
    ]
    if MatchFlag.KIDS_SIZING in flags:
        kids_candidates = [product for product in model_candidates if product.is_kids_version_of]
        if kids_candidates:
            model_candidates = kids_candidates
    tier2 = [product for product in model_candidates if _color_evidence(text, product, world)]
    if len(tier2) == 1:
        return _result(tier2[0], 0.95, flags, True)
    if len(model_candidates) == 1 and _color_conflict(text, model_candidates[0], world):
        flags.add(MatchFlag.COLORWAY_CONFLICT)
        return _result(model_candidates[0], 0.95, flags, False)

    ranked = rank_catalog(listing.raw_title, world)
    if not ranked or ranked[0].score < cfg.FUZZY_REJECT:
        return MatchResult(flags=sorted(flags, key=lambda flag: flag.value))
    top = ranked[0]
    runner_score = ranked[1].score if len(ranked) > 1 else 0.0
    if top.score >= cfg.FUZZY_ACCEPT and top.score - runner_score >= cfg.FUZZY_MARGIN:
        confirmed = _color_evidence(text, top.product, world)
        if _color_conflict(text, top.product, world):
            flags.add(MatchFlag.COLORWAY_CONFLICT)
            confirmed = False
        elif not confirmed:
            flags.add(MatchFlag.COLORWAY_UNCONFIRMED)
        return _result(top.product, top.score / 100.0, flags, confirmed)

    flags.add(MatchFlag.NAME_NEAR_MISS)
    return MatchResult(flags=sorted(flags, key=lambda flag: flag.value))
