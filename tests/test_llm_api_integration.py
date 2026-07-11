from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import dealhunter.api.app as api
from dealhunter.core.config import Constants
from dealhunter.llm.cache import CacheMode, CachedClient
from dealhunter.llm.client import NullClient


ROOT = Path(__file__).resolve().parent.parent
CFG = Constants()


@pytest.fixture
def client() -> TestClient:
    previous = api.ENGINE
    api.ENGINE = api.FixtureEngine(
        llm=CachedClient(None, ROOT / CFG.LLM_CACHE_PATH, CFG.LLM_MODEL_PIN, CacheMode.REPLAY),
        real_intake=True,
    )
    try:
        yield TestClient(api.app)
    finally:
        api.ENGINE = previous


def test_real_intake_replays_reviewed_text_case(client: TestClient) -> None:
    response = client.post(
        "/intake",
        json={
            "world_id": "w_fixture",
            "input": {
                "text": (
                    "Find Nike Dunk Low Panda DD1391-100 in EU 43, landed cap EUR 120, "
                    "monitor mode."
                )
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["brief"]["style_code"] == "DD1391-100"
    assert payload["mandate"]["cap_landed_eur"] == "120"
    assert payload["hunt_id"].startswith("h_")
    assert [item["path"] for item in payload["diff"]] == [
        item["field"] for item in payload["mandate_diff"]
    ]


def test_screenshot_clarification_replays_with_sensitive_diff(client: TestClient) -> None:
    image_b64 = base64.b64encode((ROOT / "fixtures/adversarial_intake.png").read_bytes()).decode()
    first = client.post(
        "/intake",
        json={
            "world_id": "w_fixture",
            "input": {
                "text": (
                    "This screenshot describes a Nike Dunk Low Panda in EU 43. "
                    "The landed cap is missing."
                ),
                "image_b64": image_b64,
            },
        },
    )
    assert first.status_code == 200
    assert first.json()["status"] == "NEEDS_INFO"

    second = client.post(
        f"/intake/{first.json()['intake_id']}/clarify",
        json={"text": "Use a landed cap of EUR 115 and monitor mode."},
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["status"] == "OK"
    assert payload["mandate"]["cap_landed_eur"] == "115"
    cap_change = next(item for item in payload["diff"] if item["path"] == "mandate.cap_landed_eur")
    assert cap_change["sensitive"] is True
    transcript = api.ENGINE.real_intakes[first.json()["intake_id"]].session.transcript
    assert any(item.startswith("image:sha256:") for item in transcript)
    assert image_b64 not in transcript


def test_null_client_intake_returns_503() -> None:
    previous = api.ENGINE
    api.ENGINE = api.FixtureEngine(llm=NullClient(), real_intake=True)
    try:
        response = TestClient(api.app).post(
            "/intake",
            json={"world_id": "w_fixture", "input": {"text": "Nike Dunk size 43 under EUR 80"}},
        )
    finally:
        api.ENGINE = previous
    assert response.status_code == 503
    assert "structured form" in response.json()["detail"]


def test_replay_cache_miss_returns_503(client: TestClient) -> None:
    response = client.post(
        "/intake",
        json={"world_id": "w_fixture", "input": {"text": "an uncached hunt request"}},
    )
    assert response.status_code == 503
    assert "reviewed replay cache" in response.json()["detail"]


def test_structured_form_compiles_without_llm() -> None:
    previous = api.ENGINE
    api.ENGINE = api.FixtureEngine(llm=NullClient(), real_intake=True)
    try:
        response = TestClient(api.app).post(
            "/intake/structured",
            json={
                "world_id": "w_fixture",
                "product_query": "Nike Dunk Low Panda",
                "style_code": "DD1391-100",
                "size_eu": "43",
                "cap_landed_eur": "120",
                "mode": "MONITOR",
            },
        )
    finally:
        api.ENGINE = previous

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OK"
    assert payload["brief"]["style_code"] == "DD1391-100"
    assert payload["mandate"]["cap_landed_eur"] == "120"
