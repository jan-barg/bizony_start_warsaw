"""Finite-horizon monitor stopping mathematics (spec §5.7)."""

from decimal import Decimal

from ..core.config import Constants
from ..core.models import Hunt, StoppingSnapshot


PROBABILITY_QUANTUM = Decimal("0.0001")


def trend_slope(history: list[Decimal]) -> Decimal:
    """Least-squares slope over the latest seven observed prices."""
    values = history[-7:]
    count = len(values)
    if count < 2:
        return Decimal("0")
    mean_x = Decimal(count - 1) / Decimal("2")
    mean_y = sum(values, Decimal("0")) / Decimal(count)
    numerator = sum(
        (Decimal(index) - mean_x) * (value - mean_y)
        for index, value in enumerate(values)
    )
    denominator = sum(
        (Decimal(index) - mean_x) ** 2 for index in range(count)
    )
    return numerator / denominator if denominator else Decimal("0")


def daily_improvement_probability(
    history: list[Decimal], current_best: Decimal, cfg: Constants
) -> Decimal:
    """Beta(1,1) posterior mean with the configured trend heuristic."""
    successes = sum(
        value < current_best - cfg.DELTA_IMPROVE_EUR for value in history
    )
    probability = (Decimal(successes) + 1) / (Decimal(len(history)) + 2)
    slope = trend_slope(history)
    if slope < 0:
        probability *= cfg.TREND_FALLING_MULT
    elif slope > 0:
        probability *= cfg.TREND_RISING_MULT
    return min(max(probability, Decimal("0")), cfg.P_DAILY_CLAMP)


def p_better(
    history: list[Decimal],
    current_best: Decimal,
    horizon: int,
    cfg: Constants,
) -> Decimal:
    """Probability of at least one material improvement over ``horizon``."""
    days = max(horizon, 0)
    if days == 0:
        return Decimal("0.0000")
    daily = daily_improvement_probability(history, current_best, cfg)
    probability = Decimal("1") - (Decimal("1") - daily) ** days
    return probability.quantize(PROBABILITY_QUANTUM)


def final_buy_tick(hunt: Hunt, minimum_route_eta: int) -> int:
    """Last mandate-valid tick on which the fastest route can still arrive."""
    expiry_limit = hunt.mandate.expires_tick - 1
    if hunt.mandate.need_within_ticks is None:
        return expiry_limit
    deadline_tick = hunt.start_tick + hunt.mandate.need_within_ticks
    return min(expiry_limit, deadline_tick - minimum_route_eta)


def stopping_decision(
    history: list[Decimal],
    current_best: Decimal,
    tick: int,
    last_buy_tick: int,
    cfg: Constants,
) -> tuple[bool, StoppingSnapshot]:
    """Return the monitor BUY/HOLD decision and receipt-ready evidence."""
    horizon = last_buy_tick - tick
    probability = p_better(history, current_best, horizon, cfg)
    snapshot = StoppingSnapshot(
        p_better=probability,
        horizon=horizon,
        theta=cfg.THETA_STOP,
        n_obs=len(history),
    )
    if horizon < 0:
        return False, snapshot
    if horizon == 0:
        return True, snapshot
    if len(history) < cfg.MIN_OBS:
        return False, snapshot
    return probability < cfg.THETA_STOP, snapshot


def improved_stopping_decision(
    history: list[Decimal],
    current_best: Decimal,
    tick: int,
    last_buy_tick: int,
    high_confidence: bool,
    cfg: Constants,
) -> tuple[bool, StoppingSnapshot, str | None]:
    """Production form of the held-out validated monitoring strategy.

    Safety and mandate gates are applied before this function. This function
    controls timing only: a high-confidence under-cap deal can buy immediately,
    an empirically low observed price can buy after warmup, and the final
    window avoids depending on stock surviving until one forcing day.
    """
    horizon = last_buy_tick - tick
    observations = [*history, current_best]
    percentile = (
        Decimal(sum(value <= current_best for value in observations))
        / Decimal(len(observations))
    ).quantize(PROBABILITY_QUANTUM)
    snapshot = StoppingSnapshot(
        p_better=None,
        horizon=horizon,
        theta=cfg.OBSERVED_LOW_QUANTILE,
        n_obs=len(observations),
    )
    if horizon < 0:
        return False, snapshot, None

    observed_low = (
        len(observations) >= cfg.MIN_OBS
        and percentile <= cfg.OBSERVED_LOW_QUANTILE
        and current_best <= min(observations) + cfg.GOOD_DEAL_MARGIN_EUR
    )
    final_window_start = last_buy_tick - cfg.FINAL_WINDOW_TICKS + 1

    if high_confidence:
        return True, snapshot, "high_confidence_under_target"
    if observed_low:
        return True, snapshot, "observed_low"
    if tick >= final_window_start:
        return True, snapshot, "final_window_fallback"
    return False, snapshot, None


def deal_percentile(history: list[Decimal], current_best: Decimal) -> Decimal:
    """Smoothed empirical percentile; evidence only, never a purchase gate."""
    rank = 1 + sum(value <= current_best for value in history)
    return (Decimal(rank) / Decimal(len(history) + 1)).quantize(
        PROBABILITY_QUANTUM
    )
