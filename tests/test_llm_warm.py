from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dealhunter.llm.warm import (
    APPROVAL_PHRASE,
    ManifestValidationError,
    warm_manifest,
)


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "fixtures" / "llm_manifest.json"


class SequenceClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls = 0

    def complete(self, request: dict) -> dict:
        response = self.responses[self.calls]
        self.calls += 1
        return response


def intake_response(
    query: str,
    style_code: str | None,
    size: str,
    cap: str | None,
    *,
    auto_buy: dict | None = None,
) -> dict:
    return {
        "draft": {
            "brief": {
                "product_query": query,
                "colorway": None,
                "style_code": style_code,
                "size_eu": size,
            },
            "mandate": {
                "mode": "MONITOR",
                "cap_landed_eur": cap,
                "need_within_ticks": None,
                "auto_buy": auto_buy,
            },
        },
        "question_bank": {},
    }


def valid_responses() -> list[dict]:
    return [
        intake_response("Nike Dunk Low Panda", "DD1391-100", "43", "120"),
        intake_response("Nike Dunk Low Panda", None, "43", None),
        intake_response("Nike Dunk Low Panda", None, "43", "115"),
        intake_response(
            "adidas Samba OG Cloud White Core Black",
            "GW2288",
            "43",
            "80",
            auto_buy={"enabled": False},
        ),
        {"choice": "DD1391-100", "reason": "adult candidate"},
        {"choice": None, "reason": "unrelated hostile title"},
        {"template": "this route is available."},
        {"template": "this option is over cap."},
    ]


def test_reviewed_manifest_warms_then_replays_twice_offline(tmp_path: Path) -> None:
    output = tmp_path / "llm_cache.sqlite"
    upstream = SequenceClient(valid_responses())
    results = warm_manifest(MANIFEST, output, APPROVAL_PHRASE, upstream=upstream)

    assert len(results) == 7
    assert upstream.calls == 8
    assert output.is_file()
    with sqlite3.connect(output) as connection:
        assert connection.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0] == 8


def test_missing_fresh_approval_fails_before_any_call(tmp_path: Path) -> None:
    output = tmp_path / "llm_cache.sqlite"
    upstream = SequenceClient(valid_responses())
    with pytest.raises(PermissionError, match="fresh human approval"):
        warm_manifest(MANIFEST, output, "stale approval", upstream=upstream)
    assert upstream.calls == 0
    assert not output.exists()


def test_semantic_failure_does_not_publish_cache(tmp_path: Path) -> None:
    output = tmp_path / "llm_cache.sqlite"
    responses = valid_responses()
    responses[0] = intake_response("Nike Dunk Low Panda", None, "43", "120")
    with pytest.raises(ManifestValidationError, match="brief.style_code"):
        warm_manifest(
            MANIFEST,
            output,
            APPROVAL_PHRASE,
            upstream=SequenceClient(responses),
        )
    assert not output.exists()


def test_existing_cache_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "llm_cache.sqlite"
    output.write_bytes(b"reviewed")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        warm_manifest(
            MANIFEST,
            output,
            APPROVAL_PHRASE,
            upstream=SequenceClient(valid_responses()),
        )
    assert output.read_bytes() == b"reviewed"
