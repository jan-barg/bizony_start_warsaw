from __future__ import annotations

import socket
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.enums import AccessTier, AskKind, Geo
from dealhunter.core.models import Brief, LineItem, RouteQuote, World
from dealhunter.engine.matcher import match
from dealhunter.llm.cache import CacheMode, CachedClient, LLMCacheMiss
from dealhunter.llm.client import IntakeUnavailable, NullClient
from dealhunter.llm.intake import start_intake
from dealhunter.llm.narrate import AskFactSheet, narrate_ask


ROOT = Path(__file__).resolve().parent.parent


class NetworkAttemptClient:
    def complete(self, request: dict) -> dict:
        socket.create_connection(("api.openai.com", 443))
        return {"unexpected": True}


def test_all_null_and_replay_surfaces_work_with_sockets_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    world = World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())
    listing = world.listings[0].model_copy(update={"raw_title": "Nike Dunk Low"})
    brief = Brief(product_query="Nike Dunk Low", size_eu=Decimal("43"))
    result = match(listing, brief, world, NullClient())
    assert result.style_code is None

    with pytest.raises(IntakeUnavailable):
        start_intake("offline", "world_0", "Nike Dunk", world, NullClient())

    quote = RouteQuote(
        listing_id="l_offline",
        tick=0,
        kind="direct",
        observation_geo=Geo.PL,
        access_tier=AccessTier.BASE,
        line_items=[LineItem(code="GOODS", label="Goods", amount_eur=Decimal("80"))],
        landed_eur=Decimal("80"),
        eta_ticks=2,
    )
    narrative = narrate_ask(
        AskFactSheet(
            kind=AskKind.OVER_CAP,
            quote=quote,
            vendor_name="Offline vendor",
            listing_title="Offline listing",
            cap_landed_eur=Decimal("75"),
        ),
        NullClient(),
    )
    assert narrative.startswith("Over-cap facts.")

    replay = CachedClient(
        NetworkAttemptClient(),
        tmp_path / "absent.sqlite",
        "gpt-5.6-terra",
        CacheMode.REPLAY,
    )
    with pytest.raises(LLMCacheMiss):
        replay.complete(
            {"surface": "x", "schema": {}, "instructions": "x", "input": "x"}
        )
