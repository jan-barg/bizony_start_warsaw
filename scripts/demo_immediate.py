"""Offline S1 immediate-engine demo over generated world seed 42."""

from decimal import Decimal
from dealhunter.core.config import Constants
from dealhunter.core.enums import HuntStatus, Mode
from dealhunter.core.models import Brief, Hunt, Mandate, canonical_json
from dealhunter.engine.loop import run_immediate
from dealhunter.llm.client import NullClient
from dealhunter.world.generate import generate_world


def main() -> None:
    cfg = Constants()
    world = generate_world(42, cfg)
    hunt = Hunt(
        id="h_42_1",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=Decimal("42"),
        ),
        mandate=Mandate(
            mode=Mode.IMMEDIATE,
            cap_landed_eur=Decimal("150.00"),
            expires_tick=10,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )
    receipt = run_immediate(hunt, world, cfg, NullClient())
    print(canonical_json(receipt))


if __name__ == "__main__":
    main()
