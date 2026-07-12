"""Acceptance tests for the streaming multi-seed evaluation and SVG outputs."""
from __future__ import annotations

import csv
import hashlib
import os
import tempfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.config import Constants
from dealhunter.core.enums import HuntStatus, Mode
from dealhunter.core.models import Brief, Hunt, Mandate, canonical_json
from dealhunter.engine.loop import run_immediate
from dealhunter.evalx.metrics import run_row
from dealhunter.evalx.plots import write_shopper_sensitivity
from dealhunter.evalx.policies import EvalTemplate, evaluation_world
from dealhunter.evalx.runner import evaluate_runs, write_artifacts
from dealhunter.llm.client import NullClient
from dealhunter.world.generate import generate_world


@pytest.fixture(scope="module")
def small_runs():
    return evaluate_runs(count=4, start_seed=1)


def test_four_seed_run_shape_and_full_timelines(small_runs) -> None:
    assert len(small_runs) == 4
    assert [run.seed for run in small_runs] == [1, 2, 3, 4]
    assert all(len(run.timeline) == 90 for run in small_runs)
    assert all(run.optimal.best_legitimate_eur <= run.template.cap_eur for run in small_runs)
    assert all(run.engine is not None for run in small_runs)
    assert all(run.engine.legitimate for run in small_runs)
    assert all(run.engine.actual_landed_eur <= run.template.cap_eur for run in small_runs)


def test_regular_shopper_only_buys_on_scheduled_checks(small_runs) -> None:
    for run in small_runs:
        if run.user is not None:
            assert run.user.tick % 3 == 0 or run.user.tick == 89
            assert run.user.perceived_eur <= run.template.cap_eur


def test_legitimate_regret_decomposes_exactly(small_runs) -> None:
    for run in small_runs:
        row = run_row(run)
        for prefix in ("engine", "user"):
            if row[f"{prefix}_legitimate_regret_eur"] == "":
                continue
            total = Decimal(row[f"{prefix}_legitimate_regret_eur"])
            selection = Decimal(row[f"{prefix}_selection_regret_eur"])
            timing = Decimal(row[f"{prefix}_timing_regret_eur"])
            assert total == selection + timing


def test_artifacts_are_parseable_and_have_expected_rows(tmp_path: Path, small_runs) -> None:
    output = tmp_path / "eval"
    summary = write_artifacts(output, small_runs)
    write_shopper_sensitivity(output / "plots/shopper-sensitivity.svg", summary, summary)
    with (output / "data/runs.csv").open(newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 4
    with (output / "data/timelines.csv").open(newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 4 * 90
    svgs = [
        output / "plots/all-runs.svg",
        output / "plots/buy-timing.svg",
        output / "plots/price-gap-comparison.svg",
        output / "plots/price-gap-cdf.svg",
        output / "plots/paired-outcomes.svg",
        output / "plots/outcomes.svg",
        output / "plots/shopper-sensitivity.svg",
        *sorted((output / "plots/timelines").glob("*.svg")),
    ]
    assert len(svgs) == 11
    for svg in svgs:
        assert ET.parse(svg).getroot().tag.endswith("svg")


def test_artifact_bytes_are_deterministic(tmp_path: Path, small_runs) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_artifacts(first, small_runs)
    write_artifacts(second, small_runs)
    first_hashes = {
        path.relative_to(first): hashlib.sha256(path.read_bytes()).digest()
        for path in first.rglob("*") if path.is_file()
    }
    second_hashes = {
        path.relative_to(second): hashlib.sha256(path.read_bytes()).digest()
        for path in second.rglob("*") if path.is_file()
    }
    assert first_hashes == second_hashes


def test_projected_world_preserves_immediate_buy_receipt() -> None:
    cfg = Constants()
    with tempfile.TemporaryDirectory() as temporary:
        old = os.getcwd()
        os.chdir(temporary)
        try:
            world = generate_world(42, cfg)
        finally:
            os.chdir(old)
    template = EvalTemplate(
        seed=42,
        index=1,
        key="projection-equivalence",
        style_code="DD1391-100",
        product_id="p_DD1391-100",
        size_eu=Decimal("42"),
        cap_eur=Decimal("150.00"),
        source_deadline=None,
    )
    projected = evaluation_world(world, template)
    hunt = Hunt(
        id="h_projection",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code=template.style_code,
            size_eu=template.size_eu,
        ),
        mandate=Mandate(
            mode=Mode.IMMEDIATE,
            cap_landed_eur=template.cap_eur,
            expires_tick=world.horizon,
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )
    full_receipt = run_immediate(hunt.model_copy(deep=True), world, cfg, NullClient())
    projected_receipt = run_immediate(
        hunt.model_copy(deep=True), projected, cfg, NullClient()
    )
    assert canonical_json(full_receipt) == canonical_json(projected_receipt)


def test_improved_monitor_uses_stable_policy_label(small_runs) -> None:
    assert all(
        run.engine is None or run.engine.policy == "SOLIDHUNT_IMPROVED_MONITOR"
        for run in small_runs
    )
