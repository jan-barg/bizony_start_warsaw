from decimal import Decimal as D
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import Action, HuntStatus, Mode
from dealhunter.core.models import Brief, Hunt, Mandate, World, canonical_json
from dealhunter.engine.loop import run_immediate
from dealhunter.llm.client import NullClient
from dealhunter.world.generate import generate_world


ROOT = Path(__file__).resolve().parent.parent


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def immediate_hunt(mode=Mode.IMMEDIATE) -> Hunt:
    return Hunt(
        id="h_42_1",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=D("43"),
        ),
        mandate=Mandate(
            mode=mode,
            # 200: tick-0 prices carry the launch-hype premium since the §4.4
            # demo retune (LAUNCH_PREMIUM_*); seed-42 dunk-42 lands ~172.74
            cap_landed_eur=D("200"),
            expires_tick=10,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )


def test_run_immediate_returns_deterministic_buy():
    first = run_immediate(immediate_hunt(), world(), Constants(), NullClient())
    second = run_immediate(immediate_hunt(), world(), Constants(), NullClient())
    assert first.action == Action.BUY
    assert canonical_json(first) == canonical_json(second)


def test_run_immediate_rejects_monitor_mandate():
    with pytest.raises(ValueError, match="IMMEDIATE"):
        run_immediate(immediate_hunt(Mode.MONITOR), world(), Constants(), NullClient())


def test_generated_seed_42_buys_with_exact_deterministic_receipt(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    cfg = Constants()
    generated = generate_world(42, cfg)
    current_hunt = immediate_hunt()
    current_hunt.brief.size_eu = D("42")

    first = run_immediate(current_hunt, generated, cfg, NullClient())
    second = run_immediate(immediate_hunt().model_copy(
        update={"brief": current_hunt.brief}
    ), generate_world(42, cfg), cfg, NullClient())

    assert first.action == Action.BUY
    assert first.chosen is not None
    assert sum(
        line.amount_eur for line in first.chosen.quote.line_items
    ) == first.chosen.quote.landed_eur
    assert canonical_json(first) == canonical_json(second)
