from decimal import Decimal as D

from dealhunter.core.config import Constants
from dealhunter.core.enums import HuntStatus, Mode
from dealhunter.core.models import Brief, Hunt, Mandate
from dealhunter.engine.stopping import (
    daily_improvement_probability,
    deal_percentile,
    final_buy_tick,
    p_better,
    stopping_decision,
    trend_slope,
)


CFG = Constants()


def hunt(*, expires=90, need=None, start=0):
    return Hunt(
        id="h_stop",
        brief=Brief(product_query="shoe", style_code="TEST", size_eu=D("43")),
        mandate=Mandate(
            mode=Mode.MONITOR,
            cap_landed_eur=D("100"),
            need_within_ticks=need,
            expires_tick=expires,
        ),
        status=HuntStatus.RUNNING,
        start_tick=start,
    )


def test_v9_probability_vector():
    history = [D("100")] * 12 + [D("90")] * 8
    assert p_better(history, D("95"), 10, CFG) == D("0.9948")
    assert p_better(history, D("95"), 1, CFG) == D("0.4091")


def test_least_squares_trend_and_multipliers():
    falling = [D("100"), D("99"), D("98"), D("97"), D("96")]
    rising = list(reversed(falling))
    assert trend_slope(falling) < 0
    assert trend_slope(rising) > 0
    assert daily_improvement_probability(falling, D("101"), CFG) > (
        D("6") / D("7")
    )
    assert daily_improvement_probability(rising, D("101"), CFG) < (
        D("6") / D("7")
    )


def test_warmup_holds_but_last_feasible_day_forces_buy():
    buy, warmup = stopping_decision([D("100")] * 4, D("90"), 5, 10, CFG)
    assert not buy
    assert warmup.n_obs == 4
    buy, forcing = stopping_decision([D("100")] * 4, D("90"), 10, 10, CFG)
    assert buy
    assert forcing.horizon == 0


def test_expiry_and_deadline_define_last_buy_tick():
    assert final_buy_tick(hunt(expires=90), minimum_route_eta=8) == 89
    assert final_buy_tick(hunt(expires=90, need=10), minimum_route_eta=8) == 2
    assert final_buy_tick(hunt(expires=20, need=30, start=5), minimum_route_eta=2) == 19


def test_past_last_buy_tick_never_buys():
    buy, snapshot = stopping_decision([D("100")] * 10, D("80"), 6, 5, CFG)
    assert not buy
    assert snapshot.horizon == -1


def test_deal_percentile_is_smoothed_and_distribution_free():
    assert deal_percentile([D("80"), D("90"), D("100")], D("85")) == D("0.5000")
