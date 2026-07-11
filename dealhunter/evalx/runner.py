"""Streaming multi-seed evaluation runner and artifact writer."""
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..core.config import Constants
from ..world.generate import generate_world
from .baselines import CasualShopperHypothesis, casual_checkout_shopper
from .metrics import RunEvaluation, run_row, summarize
from .plots import write_all_plots
from .policies import (
    legitimate_market_timeline,
    optimal_purchase,
    solidhunt_improved_monitor,
    solidhunt_spec_monitor,
    template_from_world,
)


@contextmanager
def _discarded_world_artifacts() -> Iterator[None]:
    """Generate each world's ~6 MB artifacts in temporary storage."""
    original = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="solidhunt-eval-") as temporary:
        os.chdir(temporary)
        try:
            yield
        finally:
            os.chdir(original)


def evaluate_runs(
    count: int = 100,
    start_seed: int = 1,
    cfg: Constants | None = None,
    progress: bool = False,
    solid_policy: str = "improved",
    user_check_interval: int = 3,
) -> list[RunEvaluation]:
    if count <= 0:
        raise ValueError("count must be positive")
    cfg = cfg or Constants()
    if solid_policy not in {"improved", "spec"}:
        raise ValueError("solid_policy must be 'improved' or 'spec'")
    engine_policy = (
        solidhunt_improved_monitor if solid_policy == "improved"
        else solidhunt_spec_monitor
    )
    shopper = CasualShopperHypothesis(check_interval_ticks=user_check_interval)
    runs: list[RunEvaluation] = []
    for offset, seed in enumerate(range(start_seed, start_seed + count), start=1):
        with _discarded_world_artifacts():
            world = generate_world(seed, cfg)
        template = template_from_world(world, index=1)
        timeline = legitimate_market_timeline(world, template, cfg)
        optimal = optimal_purchase(timeline, template)
        if optimal is None:
            raise AssertionError(f"seed {seed} has no under-cap full-horizon optimum")
        runs.append(RunEvaluation(
            run_id=f"run-{offset:03d}",
            seed=seed,
            template=template,
            timeline=timeline,
            optimal=optimal,
            engine=engine_policy(world, template, cfg),
            user=casual_checkout_shopper(world, template, cfg, shopper),
        ))
        if progress and (offset == 1 or offset % 10 == 0 or offset == count):
            print(f"evaluated {offset}/{count} seeds")
    return runs


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot write an empty CSV")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _timeline_rows(runs: list[RunEvaluation]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs:
        for point in run.timeline:
            rows.append({
                "run_id": run.run_id,
                "seed": run.seed,
                "style_code": run.template.style_code,
                "tick": point.tick,
                "cap_eur": format(run.template.cap_eur, "f"),
                "best_legitimate_landed_eur": (
                    "" if point.best_legitimate_eur is None
                    else format(point.best_legitimate_eur, "f")
                ),
                "best_listing_id": point.listing_id or "",
                "best_route": (point.route_kind or "") + (
                    f":{point.middleman_id}" if point.middleman_id else ""
                ),
                "is_optimal_tick": point.tick == run.optimal.tick,
                "is_engine_buy_tick": run.engine is not None and point.tick == run.engine.tick,
                "is_user_buy_tick": run.user is not None and point.tick == run.user.tick,
            })
    return rows


def _fmt(value: object, digits: int = 2) -> str:
    return "n/a" if value is None else f"{float(value):.{digits}f}"


def _report_markdown(summary: dict[str, object], *, include_plots: bool = True) -> str:
    policies = summary["policies"]
    engine_name = summary["methodology"]["solid_hunt_policy"]
    user_name = summary["methodology"]["regular_user_policy"]
    engine = policies[engine_name]
    user = policies[user_name]
    paired = summary["paired"]
    seed_start, seed_end = summary["methodology"]["seeds"]
    held_out = seed_start > 1
    interval = user_name.removeprefix("CASUAL_CHECKOUT_").removesuffix("D")
    engine_display = (
        "SolidHunt improved monitor"
        if engine_name == "SOLIDHUNT_IMPROVED_MONITOR"
        else "SolidHunt spec monitor"
    )
    user_display = f"Casual checkout shopper ({interval}-day)"
    policy_description = (
        "The improved policy keeps hard mandate and trust gates, uses EV for ranking rather than as an uncalibrated probability gate, buys high-confidence under-cap deals or observed lows, and adds an explicit final-window fallback."
        if engine_name == "SOLIDHUNT_IMPROVED_MONITOR"
        else "The diagnostic policy requires positive EV and uses the normative §5.7 horizon-wide stopping probability with a single final forcing day."
    )
    output_name = "reports/eval-100-heldout" + ("-weekly" if interval == "7" else "")
    critical = engine["miss_rate"] >= 0.50
    heading = "Critical finding" if critical else "Held-out result"
    interpretation = (
        f"The current policy missed **{_fmt(100 * engine['miss_rate'], 1)}%** of runs and needs further work before performance claims are made."
        if critical
        else f"SolidHunt completed **{engine['legitimate_purchases']} legitimate purchases** with **{engine['invalid_purchases']} invalid purchases** and **{_fmt(100 * engine['miss_rate'], 1)}% misses**."
    )
    plot_files = """- `plots/all-runs.svg`: 10×10 contact sheet showing every complete timeline.
- `plots/timelines/run-001.svg` … `run-100.svg`: readable full timeline for every run.
- `plots/buy-timing.svg`: paired user-versus-SolidHunt purchase day.
- `plots/price-gap-comparison.svg`: focused distribution with quartiles and explicit tail counts.
- `plots/price-gap-cdf.svg`: cumulative share of purchases within each price gap.
- `plots/paired-outcomes.svg`: paired cheaper, tied, and more-expensive outcome counts.
- `plots/outcomes.svg`: legitimate purchases, invalid purchases, and misses.
- `plots/shopper-sensitivity.svg`: held-out comparison against 3-day and weekly shopper assumptions (when generated).""" if include_plots else "\nThis sensitivity cohort stores data only; its comparison plot is generated in the primary held-out report."
    no_plots_flag = "" if include_plots else " --no-plots"
    return f"""# SolidHunt 100-run {'held-out ' if held_out else ''}timing evaluation

## {heading}

{interpretation}

Among its {engine['legitimate_purchases']} legitimate purchases, SolidHunt's mean price gap from the full-horizon optimum was **€{_fmt(engine['mean_legitimate_regret_eur'])}**. The casual checkout shopper completed {user['legitimate_purchases']} legitimate purchases with a conditional mean gap of **€{_fmt(user['mean_legitimate_regret_eur'])}**.

When both strategies purchased, the shopper paid an average **€{_fmt(paired['mean_user_minus_engine_landed_eur'])} more than SolidHunt** (positive means SolidHunt was cheaper).

| Strategy | Purchases | Legitimate | Invalid | Miss rate | Mean gap | Median gap | P90 gap | Mean absolute timing gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| {engine_display} | {engine['purchases']} | {engine['legitimate_purchases']} | {engine['invalid_purchases']} | {_fmt(100 * engine['miss_rate'], 1)}% | €{_fmt(engine['mean_legitimate_regret_eur'])} | €{_fmt(engine['median_legitimate_regret_eur'])} | €{_fmt(engine['p90_legitimate_regret_eur'])} | {_fmt(engine['mean_abs_timing_delta_ticks'], 1)} days |
| {user_display} | {user['purchases']} | {user['legitimate_purchases']} | {user['invalid_purchases']} | {_fmt(100 * user['miss_rate'], 1)}% | €{_fmt(user['mean_legitimate_regret_eur'])} | €{_fmt(user['median_legitimate_regret_eur'])} | €{_fmt(user['p90_legitimate_regret_eur'])} | {_fmt(user['mean_abs_timing_delta_ticks'], 1)} days |

The casual shopper's visible checkout subtotal understated true landed cost by **€{_fmt(user['mean_checkout_understatement_eur'])} on average**. It produced {user['actual_cap_violations']} purchases whose actual landed cost exceeded the stated budget.

## Behavioral hypothesis

`{user_name}` is a synthetic, deliberately attentive regular-shopper baseline—not a claim based on observed consumer research:

- Checks every {interval} days and once on the final day.
- Is generously assumed to identify the correct target and size.
- Considers ordinary direct-to-Poland listings only.
- Compares goods, valid coupon, and quoted direct shipping in EUR.
- Does not calculate import VAT, customs duty, handling, forwarding, seller trust, or geo tactics.
- Buys the cheapest perceived subtotal at the first check where it fits the budget.

## SolidHunt policy status

`{engine_name}` uses the implemented production route enumeration, landed-cost math, customs, trust, and expected-value functions. {policy_description}

The production `engine.run_monitor()` entry point is still a stub at this repository checkpoint. These results must therefore be described as a **SolidHunt stopping-policy simulation**, not as production monitor-loop output. The plots and data use that label consistently.

## Cohort and benchmark

- Seeds {seed_start}–{seed_end}; one deterministic hunt per seed.
- {'Policy parameters were fixed on seeds 1–100 before this held-out run.' if held_out else 'This cohort is the policy-development/tuning set.'}
- Full 90-day horizon for every run; source-template delivery deadlines are removed to isolate timing behavior.
- Geo arbitrage is `NEVER` for both strategies.
- The common optimum is the lowest legitimate fully landed price under the cap across all 90 days.
- Price gap is reported only for legitimate purchases. Invalid purchases and misses are separate outcomes, so a trap cannot appear as misleading “negative regret.”

## Files

- `data/runs.csv`: one row per paired run with purchases, prices, gaps, timing, validity, and traps.
- `data/timelines.csv`: all 9,000 daily market points and purchase markers.
- `data/summary.json`: machine-readable aggregates.
{plot_files}

## Reproduce

```bash
.venv/bin/python -m dealhunter.evalx.runner --runs 100 --start-seed {seed_start} --user-check-interval {interval}{no_plots_flag} --output {output_name}
.venv/bin/pytest tests/test_eval.py
```
"""


def write_artifacts(output: Path, runs: list[RunEvaluation], plots: bool = True) -> dict[str, object]:
    output = output.resolve()
    data = output / "data"
    summary = summarize(runs)
    _write_csv(data / "runs.csv", [run_row(run) for run in runs])
    _write_csv(data / "timelines.csv", _timeline_rows(runs))
    (data / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        _report_markdown(summary, include_plots=plots),
        encoding="utf-8",
    )
    if plots:
        write_all_plots(output, runs)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired SolidHunt timing evaluation")
    parser.add_argument("--runs", type=int, default=100, help="number of consecutive seeds")
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("reports/eval-100"))
    parser.add_argument("--solid-policy", choices=("improved", "spec"), default="improved")
    parser.add_argument("--user-check-interval", type=int, default=3)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    runs = evaluate_runs(
        args.runs,
        args.start_seed,
        progress=True,
        solid_policy=args.solid_policy,
        user_check_interval=args.user_check_interval,
    )
    summary = write_artifacts(args.output, runs, plots=not args.no_plots)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
