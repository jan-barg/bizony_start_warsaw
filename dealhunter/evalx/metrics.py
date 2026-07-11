"""Paired evaluation records and aggregate metrics for pitch analysis."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, median, pstdev

from .policies import DailyMarketPoint, EvalTemplate, PurchaseDecision


@dataclass(frozen=True)
class RunEvaluation:
    run_id: str
    seed: int
    template: EvalTemplate
    timeline: list[DailyMarketPoint]
    optimal: DailyMarketPoint
    engine: PurchaseDecision | None
    user: PurchaseDecision | None


def _daily_at(run: RunEvaluation, tick: int) -> Decimal | None:
    return run.timeline[tick].best_legitimate_eur


def _d(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def decision_columns(
    run: RunEvaluation,
    decision: PurchaseDecision | None,
    prefix: str,
) -> dict[str, str | int | bool]:
    if decision is None:
        return {
            f"{prefix}_bought": False,
            f"{prefix}_tick": "",
            f"{prefix}_listing_id": "",
            f"{prefix}_route": "",
            f"{prefix}_actual_landed_eur": "",
            f"{prefix}_perceived_eur": "",
            f"{prefix}_raw_gap_eur": "",
            f"{prefix}_legitimate_regret_eur": "",
            f"{prefix}_selection_regret_eur": "",
            f"{prefix}_timing_regret_eur": "",
            f"{prefix}_timing_delta_ticks": "",
            f"{prefix}_legitimate": False,
            f"{prefix}_trap_types": "",
            f"{prefix}_reason": "miss",
            f"{prefix}_p_better": "",
        }
    optimal_price = run.optimal.best_legitimate_eur
    assert optimal_price is not None
    raw_gap = decision.actual_landed_eur - optimal_price
    daily_best = _daily_at(run, decision.tick)
    legitimate_regret = raw_gap if decision.legitimate else None
    selection_regret = (
        decision.actual_landed_eur - daily_best
        if decision.legitimate and daily_best is not None
        else None
    )
    timing_regret = (
        daily_best - optimal_price
        if decision.legitimate and daily_best is not None
        else None
    )
    return {
        f"{prefix}_bought": True,
        f"{prefix}_tick": decision.tick,
        f"{prefix}_listing_id": decision.listing_id,
        f"{prefix}_route": decision.route_kind + (
            f":{decision.middleman_id}" if decision.middleman_id else ""
        ),
        f"{prefix}_actual_landed_eur": _d(decision.actual_landed_eur),
        f"{prefix}_perceived_eur": _d(decision.perceived_eur),
        f"{prefix}_raw_gap_eur": _d(raw_gap),
        f"{prefix}_legitimate_regret_eur": _d(legitimate_regret),
        f"{prefix}_selection_regret_eur": _d(selection_regret),
        f"{prefix}_timing_regret_eur": _d(timing_regret),
        f"{prefix}_timing_delta_ticks": decision.tick - run.optimal.tick,
        f"{prefix}_legitimate": decision.legitimate,
        f"{prefix}_trap_types": "|".join(decision.trap_types),
        f"{prefix}_reason": decision.reason,
        f"{prefix}_p_better": _d(decision.p_better),
    }


def run_row(run: RunEvaluation) -> dict[str, str | int | bool]:
    optimal_price = run.optimal.best_legitimate_eur
    assert optimal_price is not None
    row: dict[str, str | int | bool] = {
        "run_id": run.run_id,
        "seed": run.seed,
        "source_template_key": run.template.key,
        "style_code": run.template.style_code,
        "size_eu": _d(run.template.size_eu),
        "cap_eur": _d(run.template.cap_eur),
        "source_deadline": run.template.source_deadline or "",
        "analysis_horizon_ticks": len(run.timeline),
        "optimal_tick": run.optimal.tick,
        "optimal_landed_eur": _d(optimal_price),
        "optimal_listing_id": run.optimal.listing_id or "",
        "optimal_route": (run.optimal.route_kind or "") + (
            f":{run.optimal.middleman_id}" if run.optimal.middleman_id else ""
        ),
    }
    row.update(decision_columns(run, run.engine, "engine"))
    row.update(decision_columns(run, run.user, "user"))
    return row


def _quantile(values: list[Decimal], probability: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int((Decimal(len(ordered) - 1) * probability).to_integral_value())
    return ordered[index]


def _aggregate_policy(runs: list[RunEvaluation], attribute: str) -> dict[str, object]:
    decisions = [getattr(run, attribute) for run in runs]
    purchases = [decision for decision in decisions if decision is not None]
    legitimate_pairs = [
        (run, decision)
        for run, decision in zip(runs, decisions)
        if decision is not None and decision.legitimate
    ]
    regrets = [
        decision.actual_landed_eur - run.optimal.best_legitimate_eur
        for run, decision in legitimate_pairs
        if run.optimal.best_legitimate_eur is not None
    ]
    timing = [Decimal(abs(decision.tick - run.optimal.tick)) for run, decision in legitimate_pairs]
    signed_timing = [Decimal(decision.tick - run.optimal.tick) for run, decision in legitimate_pairs]
    cap_violations = [
        decision for run, decision in zip(runs, decisions)
        if decision is not None and decision.actual_landed_eur > run.template.cap_eur
    ]
    perceived_understatement = [
        decision.actual_landed_eur - decision.perceived_eur
        for decision in purchases
        if decision.perceived_eur is not None
    ]

    return {
        "runs": len(runs),
        "purchases": len(purchases),
        "purchase_rate": len(purchases) / len(runs),
        "misses": len(runs) - len(purchases),
        "miss_rate": (len(runs) - len(purchases)) / len(runs),
        "legitimate_purchases": len(legitimate_pairs),
        "invalid_purchases": len(purchases) - len(legitimate_pairs),
        "purchase_legitimacy": len(legitimate_pairs) / len(purchases) if purchases else None,
        "actual_cap_violations": len(cap_violations),
        "mean_legitimate_regret_eur": float(mean(regrets)) if regrets else None,
        "median_legitimate_regret_eur": float(median(regrets)) if regrets else None,
        "p90_legitimate_regret_eur": float(_quantile(regrets, Decimal("0.90"))) if regrets else None,
        "std_legitimate_regret_eur": float(pstdev(regrets)) if len(regrets) > 1 else 0.0 if regrets else None,
        "mean_abs_timing_delta_ticks": float(mean(timing)) if timing else None,
        "mean_signed_timing_delta_ticks": float(mean(signed_timing)) if signed_timing else None,
        "mean_checkout_understatement_eur": (
            float(mean(perceived_understatement)) if perceived_understatement else None
        ),
    }


def summarize(runs: list[RunEvaluation]) -> dict[str, object]:
    engine = _aggregate_policy(runs, "engine")
    user = _aggregate_policy(runs, "user")
    both = [
        (run.engine, run.user)
        for run in runs
        if run.engine is not None and run.user is not None
    ]
    paired_savings = [
        user_decision.actual_landed_eur - engine_decision.actual_landed_eur
        for engine_decision, user_decision in both
    ]
    return {
        "methodology": {
            "runs": len(runs),
            "seeds": [runs[0].seed, runs[-1].seed] if runs else [],
            "templates_per_seed": 1,
            "horizon_ticks": len(runs[0].timeline) if runs else 0,
            "geo_arbitrage": "NEVER",
            "solid_hunt_policy": "implemented engine money/trust layers + eval implementation of spec §5.7",
            "regular_user_policy": "CASUAL_CHECKOUT_3D",
        },
        "policies": {
            "SOLIDHUNT_EVAL_MONITOR": engine,
            "CASUAL_CHECKOUT_3D": user,
        },
        "paired": {
            "both_purchased": len(both),
            "mean_user_minus_engine_landed_eur": (
                float(mean(paired_savings)) if paired_savings else None
            ),
            "median_user_minus_engine_landed_eur": (
                float(median(paired_savings)) if paired_savings else None
            ),
        },
    }
