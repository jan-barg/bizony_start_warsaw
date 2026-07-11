"""Offline immediate-engine smoke demo over the frozen mini world."""

from decimal import Decimal
from pathlib import Path

from dealhunter.core.config import Constants
from dealhunter.core.enums import HuntStatus, Mode
from dealhunter.core.models import Brief, Hunt, Mandate, World, canonical_json
from dealhunter.engine.loop import run_immediate
from dealhunter.llm.client import NullClient


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    world = World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())
    hunt = Hunt(
        id="h_42_1",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=Decimal("43"),
        ),
        mandate=Mandate(
            mode=Mode.IMMEDIATE,
            cap_landed_eur=Decimal("150.00"),
            expires_tick=10,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )
    receipt = run_immediate(hunt, world, Constants(), NullClient())
    print(canonical_json(receipt))


if __name__ == "__main__":
    main()
