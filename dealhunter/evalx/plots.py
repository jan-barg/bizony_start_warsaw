"""Dependency-free, deterministic SVG plots for evaluation reports."""
from __future__ import annotations

from html import escape
from math import ceil
from pathlib import Path
from statistics import mean, median

from .metrics import RunEvaluation


PAPER = "#FFFFFF"
SOFT = "#F4F6F3"
INK = "#080808"
MUTED = "#59615B"
BORDER = "#D8DDD9"
ENGINE = "#137A3D"
USER = "#A76100"
OPTIMAL = "#2859C5"
CAP = "#C52A22"


def _policy_label(runs: list[RunEvaluation], attribute: str) -> str:
    name = next(
        (
            decision.policy
            for run in runs
            if (decision := getattr(run, attribute)) is not None
        ),
        "SOLIDHUNT_IMPROVED_MONITOR" if attribute == "engine" else "CASUAL_CHECKOUT_3D",
    )
    if name == "SOLIDHUNT_IMPROVED_MONITOR":
        return "SolidHunt improved monitor"
    if name == "SOLIDHUNT_EVAL_MONITOR":
        return "SolidHunt spec monitor"
    if name.startswith("CASUAL_CHECKOUT_"):
        interval = name.removeprefix("CASUAL_CHECKOUT_").removesuffix("D")
        return f"Casual checkout shopper ({interval}-day)"
    return name.replace("_", " ").title()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _svg_start(width: int, height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(title)}</title>",
        f"<desc id=\"desc\">{escape(description)}</desc>",
        f'<rect width="{width}" height="{height}" fill="{PAPER}"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#080808} .small{font-size:11px} .label{font-size:13px;font-weight:600} .title{font-size:22px;font-weight:700}</style>',
    ]


def _coords(
    tick: int,
    price: float,
    left: float,
    top: float,
    width: float,
    height: float,
    low: float,
    high: float,
    horizon: int,
) -> tuple[float, float]:
    x = left + (tick / max(horizon - 1, 1)) * width
    y = top + (high - price) / max(high - low, 0.01) * height
    return x, y


def _line_paths(run: RunEvaluation, left: float, top: float, width: float, height: float, low: float, high: float) -> list[str]:
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for point in run.timeline:
        if point.best_legitimate_eur is None:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(_coords(
            point.tick, float(point.best_legitimate_eur), left, top, width, height,
            low, high, len(run.timeline),
        ))
    if current:
        segments.append(current)
    return [
        '<path d="' + " ".join(
            ("M" if index == 0 else "L") + f"{x:.1f},{y:.1f}"
            for index, (x, y) in enumerate(segment)
        ) + f'" fill="none" stroke="{MUTED}" stroke-width="1.5"/>'
        for segment in segments
    ]


def _marker(x: float, y: float, kind: str, compact: bool = False) -> str:
    size = 3.5 if compact else 6
    if kind == "optimal":
        points = f"{x:.1f},{y-size:.1f} {x+size:.1f},{y:.1f} {x:.1f},{y+size:.1f} {x-size:.1f},{y:.1f}"
        return f'<polygon points="{points}" fill="{OPTIMAL}" stroke="{PAPER}" stroke-width="1"/>'
    if kind == "engine":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size}" fill="{ENGINE}" stroke="{PAPER}" stroke-width="1"/>'
    return f'<rect x="{x-size:.1f}" y="{y-size:.1f}" width="{2*size:.1f}" height="{2*size:.1f}" fill="{USER}" stroke="{PAPER}" stroke-width="1"/>'


def _plot_bounds(run: RunEvaluation) -> tuple[float, float]:
    values = [float(point.best_legitimate_eur) for point in run.timeline if point.best_legitimate_eur is not None]
    values.append(float(run.template.cap_eur))
    if run.engine:
        values.append(float(run.engine.actual_landed_eur))
    if run.user:
        values.append(float(run.user.actual_landed_eur))
    spread = max(max(values) - min(values), 10.0)
    return min(values) - spread * 0.08, max(values) + spread * 0.08


def _draw_timeline(
    lines: list[str],
    run: RunEvaluation,
    left: float,
    top: float,
    width: float,
    height: float,
    compact: bool,
) -> None:
    low, high = _plot_bounds(run)
    lines.append(f'<rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{SOFT}" stroke="{BORDER}"/>')
    cap_y = _coords(0, float(run.template.cap_eur), left, top, width, height, low, high, len(run.timeline))[1]
    lines.append(f'<line x1="{left:.1f}" y1="{cap_y:.1f}" x2="{left+width:.1f}" y2="{cap_y:.1f}" stroke="{CAP}" stroke-width="1" stroke-dasharray="4 3"/>')
    lines.extend(_line_paths(run, left, top, width, height, low, high))
    optimum = run.optimal
    assert optimum.best_legitimate_eur is not None
    ox, oy = _coords(optimum.tick, float(optimum.best_legitimate_eur), left, top, width, height, low, high, len(run.timeline))
    lines.append(_marker(ox, oy, "optimal", compact))
    if run.engine:
        ex, ey = _coords(run.engine.tick, float(run.engine.actual_landed_eur), left, top, width, height, low, high, len(run.timeline))
        lines.append(_marker(ex, ey, "engine", compact))
    if run.user:
        ux, uy = _coords(run.user.tick, float(run.user.actual_landed_eur), left, top, width, height, low, high, len(run.timeline))
        lines.append(_marker(ux, uy, "user", compact))


def write_all_run_timelines(path: Path, runs: list[RunEvaluation]) -> None:
    columns = 10 if len(runs) >= 50 else 5
    rows = ceil(len(runs) / columns)
    cell_width, cell_height = 228, 154
    width, height = columns * cell_width + 40, rows * cell_height + 100
    lines = _svg_start(
        width, height,
        "SolidHunt 100-run purchase timeline comparison",
        "Each panel shows the full legitimate landed-price timeline, budget cap, optimal price, SolidHunt evaluation-monitor purchase, and casual shopper purchase.",
    )
    lines.append('<text x="20" y="30" class="title">100 paired market timelines</text>')
    legend = [
        (OPTIMAL, "diamond", "Optimal legitimate price"),
        (ENGINE, "circle", _policy_label(runs, "engine")),
        (USER, "square", _policy_label(runs, "user")),
        (CAP, "line", "Budget cap"),
    ]
    x = 20
    for color, shape, label in legend:
        if shape == "line":
            lines.append(f'<line x1="{x}" y1="57" x2="{x+18}" y2="57" stroke="{color}" stroke-dasharray="4 3"/>')
        elif shape == "circle":
            lines.append(f'<circle cx="{x+8}" cy="57" r="5" fill="{color}"/>')
        elif shape == "square":
            lines.append(f'<rect x="{x+3}" y="52" width="10" height="10" fill="{color}"/>')
        else:
            lines.append(f'<polygon points="{x+8},51 {x+14},57 {x+8},63 {x+2},57" fill="{color}"/>')
        lines.append(f'<text x="{x+22}" y="61" class="small">{escape(label)}</text>')
        x += 205

    for index, run in enumerate(runs):
        column, row = index % columns, index // columns
        left = 20 + column * cell_width
        top = 86 + row * cell_height
        lines.append(f'<text x="{left}" y="{top+11}" class="small">{escape(run.run_id)} · {escape(run.template.style_code)}</text>')
        _draw_timeline(lines, run, left, top + 17, cell_width - 16, cell_height - 38, True)
        lines.append(f'<text x="{left}" y="{top+cell_height-5}" class="small" fill="{MUTED}">0</text>')
        lines.append(f'<text x="{left+cell_width-34}" y="{top+cell_height-5}" class="small" fill="{MUTED}">day 89</text>')
    lines.append("</svg>")
    _write(path, "\n".join(lines) + "\n")


def write_detailed_timelines(directory: Path, runs: list[RunEvaluation]) -> None:
    for run in runs:
        width, height = 1200, 480
        lines = _svg_start(
            width, height,
            f"Timeline {run.run_id}",
            "Full 90-day legitimate landed-price curve with cap and purchase markers.",
        )
        optimal = run.optimal.best_legitimate_eur
        assert optimal is not None
        lines.append(f'<text x="48" y="40" class="title">{escape(run.run_id)} · {escape(run.template.style_code)} · EU {run.template.size_eu}</text>')
        lines.append(f'<text x="48" y="66" class="label">Cap €{run.template.cap_eur} · optimum €{optimal} on day {run.optimal.tick}</text>')
        _draw_timeline(lines, run, 70, 95, 1080, 310, False)
        for tick in (0, 30, 60, 89):
            x = 70 + tick / 89 * 1080
            lines.append(f'<text x="{x:.1f}" y="430" text-anchor="middle" class="small">day {tick}</text>')
        engine_text = "miss" if run.engine is None else f"day {run.engine.tick}, €{run.engine.actual_landed_eur}"
        user_text = "miss" if run.user is None else f"day {run.user.tick}, €{run.user.actual_landed_eur}"
        lines.append(f'<text x="70" y="460" class="small" fill="{ENGINE}">● {escape(_policy_label(runs, "engine"))}: {escape(engine_text)}</text>')
        lines.append(f'<text x="380" y="460" class="small" fill="{USER}">■ {escape(_policy_label(runs, "user"))}: {escape(user_text)}</text>')
        lines.append(f'<text x="850" y="460" class="small" fill="{OPTIMAL}">◆ Optimal: day {run.optimal.tick}, €{optimal}</text>')
        lines.append("</svg>")
        _write(directory / f"{run.run_id}.svg", "\n".join(lines) + "\n")


def write_buy_timing(path: Path, runs: list[RunEvaluation]) -> None:
    width, height = 980, 760
    left, top, plot = 100, 90, 600
    lines = _svg_start(
        width, height,
        "SolidHunt versus casual shopper purchase timing",
        "Scatter plot of casual shopper buy day against SolidHunt evaluation-monitor buy day, with a line of equal timing.",
    )
    lines.append('<text x="40" y="38" class="title">Who buys first?</text>')
    lines.append(f'<rect x="{left}" y="{top}" width="{plot}" height="{plot}" fill="{SOFT}" stroke="{BORDER}"/>')
    for tick in (0, 30, 60, 89):
        offset = tick / 89 * plot
        x, y = left + offset, top + plot - offset
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot}" stroke="{BORDER}"/>')
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot}" y2="{y:.1f}" stroke="{BORDER}"/>')
        lines.append(f'<text x="{x:.1f}" y="{top+plot+24}" text-anchor="middle" class="small">{tick}</text>')
        lines.append(f'<text x="{left-16}" y="{y+4:.1f}" text-anchor="end" class="small">{tick}</text>')
    lines.append(f'<line x1="{left}" y1="{top+plot}" x2="{left+plot}" y2="{top}" stroke="{INK}" stroke-width="1.5"/>')
    both = [run for run in runs if run.engine is not None and run.user is not None]
    for run in both:
        x = left + run.user.tick / 89 * plot
        y = top + plot - run.engine.tick / 89 * plot
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{ENGINE}" fill-opacity="0.58" stroke="{USER}" stroke-width="1.2"/>')
    lines.append(f'<text x="{left+plot/2}" y="{top+plot+58}" text-anchor="middle" class="label">{escape(_policy_label(runs, "user"))} buy day</text>')
    lines.append(f'<text x="28" y="{top+plot/2}" text-anchor="middle" class="label" transform="rotate(-90 28 {top+plot/2})">{escape(_policy_label(runs, "engine"))} buy day</text>')
    lines.append(f'<text x="750" y="130" class="label">{len(both)} paired purchases</text>')
    lines.append('<text x="750" y="162" class="small">Above diagonal: SolidHunt buys earlier</text>')
    lines.append('<text x="750" y="184" class="small">Below diagonal: SolidHunt waits longer</text>')
    lines.append("</svg>")
    _write(path, "\n".join(lines) + "\n")


def write_regret_comparison(path: Path, runs: list[RunEvaluation]) -> None:
    series: list[tuple[str, str, list[float]]] = []
    for label, color, attribute in (
        (_policy_label(runs, "engine"), ENGINE, "engine"),
        (_policy_label(runs, "user"), USER, "user"),
    ):
        values = []
        for run in runs:
            decision = getattr(run, attribute)
            optimum = run.optimal.best_legitimate_eur
            if decision is not None and decision.legitimate and optimum is not None:
                values.append(float(decision.actual_landed_eur - optimum))
        series.append((label, color, values))
    all_values = [value for _, _, values in series for value in values]
    maximum = max(all_values or [1.0])
    width, height = 1100, 520
    left, top, plot_width = 230, 105, 800
    lines = _svg_start(
        width, height,
        "Price gap from optimal by strategy",
        "All legitimate purchase gaps from the full-horizon optimum, with means and medians for both strategies.",
    )
    lines.append('<text x="40" y="38" class="title">How far was each purchase from the best possible price?</text>')
    for tick_index in range(6):
        value = maximum * tick_index / 5
        x = left + plot_width * tick_index / 5
        lines.append(f'<line x1="{x:.1f}" y1="{top-20}" x2="{x:.1f}" y2="{top+250}" stroke="{BORDER}"/>')
        lines.append(f'<text x="{x:.1f}" y="{top+285}" text-anchor="middle" class="small">€{value:.0f}</text>')
    for lane, (label, color, values) in enumerate(series):
        y = top + lane * 150
        lines.append(f'<text x="{left-18}" y="{y+6}" text-anchor="end" class="label">{escape(label)}</text>')
        for index, value in enumerate(values):
            x = left + value / max(maximum, 0.01) * plot_width
            jitter = ((index * 17) % 31 - 15) * 0.65
            lines.append(f'<circle cx="{x:.1f}" cy="{y+jitter:.1f}" r="4" fill="{color}" fill-opacity="0.48"/>')
        if values:
            avg, med = mean(values), median(values)
            avg_x = left + avg / maximum * plot_width
            med_x = left + med / maximum * plot_width
            lines.append(f'<line x1="{med_x:.1f}" y1="{y-27}" x2="{med_x:.1f}" y2="{y+27}" stroke="{INK}" stroke-width="3"/>')
            points = f"{avg_x:.1f},{y-9:.1f} {avg_x+9:.1f},{y:.1f} {avg_x:.1f},{y+9:.1f} {avg_x-9:.1f},{y:.1f}"
            lines.append(f'<polygon points="{points}" fill="{color}" stroke="{PAPER}"/>')
            lines.append(f'<text x="{left+plot_width}" y="{y+48}" text-anchor="end" class="small">mean €{avg:.2f} · median €{med:.2f} · n={len(values)}</text>')
    lines.append(f'<text x="{left+plot_width/2}" y="{height-45}" text-anchor="middle" class="label">Actual landed purchase price − full-horizon optimum</text>')
    lines.append("</svg>")
    _write(path, "\n".join(lines) + "\n")


def write_outcomes(path: Path, runs: list[RunEvaluation]) -> None:
    width, height = 1100, 430
    left, top, plot_width = 260, 115, 760
    lines = _svg_start(
        width, height,
        "Purchase outcomes across 100 runs",
        "Stacked outcome bars show legitimate purchases, invalid purchases, and misses for SolidHunt and the casual shopper.",
    )
    lines.append('<text x="40" y="38" class="title">Did each strategy complete a legitimate purchase?</text>')
    for lane, (label, attribute) in enumerate((
        (_policy_label(runs, "engine"), "engine"),
        (_policy_label(runs, "user"), "user"),
    )):
        decisions = [getattr(run, attribute) for run in runs]
        legitimate = sum(decision is not None and decision.legitimate for decision in decisions)
        invalid = sum(decision is not None and not decision.legitimate for decision in decisions)
        missed = len(runs) - legitimate - invalid
        y = top + lane * 120
        lines.append(f'<text x="{left-18}" y="{y+30}" text-anchor="end" class="label">{escape(label)}</text>')
        cursor = left
        for count, color, name in (
            (legitimate, ENGINE, "legitimate"),
            (invalid, CAP, "invalid"),
            (missed, BORDER, "miss"),
        ):
            segment = plot_width * count / max(len(runs), 1)
            lines.append(f'<rect x="{cursor:.1f}" y="{y}" width="{segment:.1f}" height="52" fill="{color}"/>')
            if count and segment >= 38:
                text_color = PAPER if color != BORDER else INK
                lines.append(f'<text x="{cursor+segment/2:.1f}" y="{y+32}" text-anchor="middle" class="label" style="fill:{text_color}">{count}</text>')
            cursor += segment
        lines.append(f'<text x="{left+plot_width}" y="{y+76}" text-anchor="end" class="small">{legitimate} legitimate · {invalid} invalid · {missed} missed</text>')
    legend_x = left
    for color, label in ((ENGINE, "Legitimate purchase"), (CAP, "Invalid purchase"), (BORDER, "Miss")):
        lines.append(f'<rect x="{legend_x}" y="365" width="14" height="14" fill="{color}"/>')
        lines.append(f'<text x="{legend_x+22}" y="377" class="small">{label}</text>')
        legend_x += 220
    lines.append("</svg>")
    _write(path, "\n".join(lines) + "\n")


def write_shopper_sensitivity(
    path: Path,
    three_day_summary: dict[str, object],
    weekly_summary: dict[str, object],
) -> None:
    """Compare SolidHunt with attentive and weekly shopper hypotheses."""
    engine_name = three_day_summary["methodology"]["solid_hunt_policy"]
    three_name = three_day_summary["methodology"]["regular_user_policy"]
    weekly_name = weekly_summary["methodology"]["regular_user_policy"]
    rows = [
        ("SolidHunt improved", ENGINE, three_day_summary["policies"][engine_name]),
        ("Shopper · every 3 days", USER, three_day_summary["policies"][three_name]),
        ("Shopper · weekly", "#D49A4A", weekly_summary["policies"][weekly_name]),
    ]
    metrics = [
        ("Legitimate purchase rate", "%", lambda item: 100 * item["legitimate_purchases"] / item["runs"]),
        ("Mean gap from optimum", "€", lambda item: item["mean_legitimate_regret_eur"]),
        ("Actual cap violations", "", lambda item: item["actual_cap_violations"]),
    ]
    width, height = 1280, 610
    lines = _svg_start(
        width,
        height,
        "Held-out shopper sensitivity comparison",
        "Small multiples compare legitimate purchase rate, mean price gap, and cap violations for SolidHunt, an attentive three-day shopper, and a weekly shopper.",
    )
    lines.append('<text x="40" y="38" class="title">Held-out trade-off across attentive and weekly shoppers</text>')
    panel_width = 390
    for panel, (title, unit, accessor) in enumerate(metrics):
        left = 40 + panel * 410
        top = 100
        values = [float(accessor(item)) for _, _, item in rows]
        maximum = max(values + [1.0]) * 1.12
        lines.append(f'<text x="{left}" y="{top-20}" class="label">{escape(title)}</text>')
        for index, (label, color, item) in enumerate(rows):
            value = float(accessor(item))
            y = top + index * 115
            bar = panel_width * value / maximum
            lines.append(f'<text x="{left}" y="{y+17}" class="small">{escape(label)}</text>')
            lines.append(f'<rect x="{left}" y="{y+30}" width="{panel_width}" height="34" fill="{SOFT}"/>')
            lines.append(f'<rect x="{left}" y="{y+30}" width="{bar:.1f}" height="34" fill="{color}"/>')
            formatted = f"{value:.0f}%" if unit == "%" else f"€{value:.2f}" if unit == "€" else f"{value:.0f}"
            lines.append(f'<text x="{left+min(bar+8, panel_width-2):.1f}" y="{y+53}" class="label">{formatted}</text>')
        lower = "higher is better" if panel == 0 else "lower is better"
        lines.append(f'<text x="{left}" y="{top+365}" class="small">{lower}</text>')
    lines.append("</svg>")
    _write(path, "\n".join(lines) + "\n")


def write_all_plots(output: Path, runs: list[RunEvaluation]) -> None:
    plots = output / "plots"
    write_all_run_timelines(plots / "all-runs.svg", runs)
    write_detailed_timelines(plots / "timelines", runs)
    write_buy_timing(plots / "buy-timing.svg", runs)
    write_regret_comparison(plots / "price-gap-comparison.svg", runs)
    write_outcomes(plots / "outcomes.svg", runs)
