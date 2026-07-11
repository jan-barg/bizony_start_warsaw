"""Placeholder-safe ask narration; facts remain code-owned quoted data."""
from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from ..core.enums import AskKind
from ..core.models import RouteQuote
from .client import LLMClient, LLMProtocolError


_PLACEHOLDERS = frozenset(
    {
        "cap",
        "comparison",
        "eta",
        "items",
        "landed",
        "listing_title",
        "overage",
        "cancellation_risk",
        "route",
        "vendor_name",
    }
)
_IMPERATIVE = re.compile(r"\b(?:approve|buy|click|confirm|ignore|proceed)\b", re.IGNORECASE)
_SAFE_WORDS = frozenset(
    {
        "a",
        "alternative",
        "an",
        "and",
        "at",
        "available",
        "cap",
        "comparison",
        "delivery",
        "estimated",
        "facts",
        "for",
        "from",
        "has",
        "is",
        "option",
        "over",
        "route",
        "the",
        "this",
        "to",
        "uses",
        "with",
        "without",
    }
)
_NARRATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"template": {"type": "string"}},
    "required": ["template"],
    "additionalProperties": False,
}


class AskFactSheet(BaseModel):
    kind: AskKind
    quote: RouteQuote
    vendor_name: str
    listing_title: str
    comparison_landed_eur: Decimal | None = None
    cap_landed_eur: Decimal | None = None


def _money(value: Decimal | None) -> str:
    return "none" if value is None else f"€{value:.2f}"


def _values(facts: AskFactSheet) -> dict[str, str]:
    quote = facts.quote
    route: str = quote.kind
    if quote.middleman_id:
        route = f"{route} via {quote.middleman_id}"
    route = f"{route} from {quote.observation_geo.value}"
    items = "; ".join(
        f"{item.code} ({item.label}): {_money(item.amount_eur)}" for item in quote.line_items
    )
    overage = None
    if facts.cap_landed_eur is not None:
        overage = max(Decimal("0"), quote.landed_eur - facts.cap_landed_eur)
    return {
        "vendor_name": facts.vendor_name,
        "listing_title": facts.listing_title,
        "landed": _money(quote.landed_eur),
        "eta": f"{quote.eta_ticks} ticks",
        "route": route,
        "items": items,
        "cancellation_risk": f"{quote.p_cancel_est * 100:.0f}%",
        "comparison": _money(facts.comparison_landed_eur),
        "cap": _money(facts.cap_landed_eur),
        "overage": _money(overage),
    }


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _fallback(facts: AskFactSheet, values: dict[str, str]) -> str:
    heading = "Gray-route facts." if facts.kind == AskKind.GRAY_ROUTE else "Over-cap facts."
    keys = [
        "vendor_name",
        "listing_title",
        "landed",
        "eta",
        "route",
        "items",
        "cancellation_risk",
    ]
    if facts.comparison_landed_eur is not None:
        keys.append("comparison")
    if facts.kind == AskKind.OVER_CAP:
        keys.extend(["cap", "overage"])
    fields = " | ".join(f"{_label(key)}: {_quoted(values[key])}" for key in keys)
    return f"{heading} {fields}"


def _valid_template(template: str) -> tuple[bool, set[str]]:
    if re.search(r"\d", template) or _IMPERATIVE.search(template):
        return False, set()
    placeholders = set(re.findall(r"{([^{}]+)}", template))
    if placeholders - _PLACEHOLDERS:
        return False, set()
    stripped = re.sub(r"{[^{}]+}", " ", template)
    if "{" in stripped or "}" in stripped:
        return False, set()
    words = set(re.findall(r"[A-Za-z]+", stripped.casefold()))
    return words <= _SAFE_WORDS, placeholders


def narrate_ask(facts: AskFactSheet, llm: LLMClient) -> str:
    """Render LLM connective prose only after strict validation."""
    values = _values(facts)
    fallback = _fallback(facts, values)
    try:
        response = llm.complete(
            {
                "surface": "narrate_ask",
                "schema": _NARRATION_SCHEMA,
                "instructions": (
                    "Write one neutral factual sentence using only the supplied placeholders "
                    "and ordinary connective words. Do not add names, numbers, or imperatives."
                ),
                "input": {
                    "ask_kind": facts.kind.value,
                    "allowed_placeholders": [f"{{{name}}}" for name in sorted(_PLACEHOLDERS)],
                },
            }
        )
    except LLMProtocolError:
        return fallback
    if set(response) != {"template"} or not isinstance(response.get("template"), str):
        return fallback
    template = response["template"]
    valid, used = _valid_template(template)
    if not valid:
        return fallback
    rendered = template
    for name in used:
        rendered = rendered.replace(f"{{{name}}}", _quoted(values[name]))
    remaining = [
        name
        for name in (
            "vendor_name",
            "listing_title",
            "landed",
            "eta",
            "route",
            "items",
            "cancellation_risk",
            "comparison",
        )
        if name not in used and (name != "comparison" or facts.comparison_landed_eur is not None)
    ]
    if facts.kind == AskKind.OVER_CAP:
        remaining.extend(name for name in ("cap", "overage") if name not in used)
    fixed_fields = " | ".join(
        f"{_label(name)}: {_quoted(values[name])}" for name in remaining
    )
    return f"{rendered} {fixed_fields}".strip()
