"""API contract tests — branch feat/api-ui (Work Order 4).

These pin the §8 endpoint shapes and the SSE envelope the UI consumes. They run
against the FixtureEngine; at S2 the same tests must pass against the real
engine (only fixture-specific *values* may change, never shapes).
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import dealhunter.api.app as api


@pytest.fixture(autouse=True)
def fresh_engine():
    """Each test gets a clean in-memory engine (fixtures reload is cheap)."""
    api.ENGINE = api.FixtureEngine()
    yield


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_confirmed_hunt(client: TestClient, text: str = "nike dunk panda size 43 under €80") -> str:
    r = client.post("/intake", json={"input": {"text": text}})
    assert r.status_code == 200 and r.json()["status"] == "OK"
    hunt_id = r.json()["hunt_id"]
    assert client.post(f"/hunts/{hunt_id}/confirm").json()["status"] == "CONFIRMED"
    return hunt_id


# ---------------------------------------------------------------- intake loop

class TestIntake:
    def test_insufficient_input_needs_info(self, client):
        r = client.post("/intake", json={"input": {"text": "i want sneakers"}})
        body = r.json()
        assert body["status"] == "NEEDS_INFO"
        assert set(body["missing"]) == {"product_query", "size_eu", "cap_landed_eur"}
        assert 1 <= len(body["questions"]) <= 3
        assert "hunt_id" not in body

    def test_clarify_loop_reaches_ok(self, client):
        r = client.post("/intake", json={"input": {"text": "hunting nike dunks panda"}})
        intake_id = r.json()["intake_id"]
        assert r.json()["status"] == "NEEDS_INFO"
        assert "size_eu" in r.json()["missing"]

        r = client.post(f"/intake/{intake_id}/clarify", json={"text": "size 43, max €80"})
        body = r.json()
        assert body["status"] == "OK"
        assert body["brief"]["size_eu"] == "43"
        assert body["mandate"]["cap_landed_eur"] == "80"
        assert body["mandate"]["mode"] == "MONITOR"
        assert body["hunt_id"].startswith("h_")

    def test_cap_and_size_never_defaulted(self, client):
        r = client.post("/intake", json={"input": {"text": "adidas samba size 43"}})
        assert r.json()["status"] == "NEEDS_INFO"
        assert r.json()["missing"] == ["cap_landed_eur"]

    def test_bare_number_clarify_reply_fills_cap(self, client):
        """Regression: 'Nike Dunk Low Panda, Size 44 now' → asked for cap →
        user answers a bare '75' → must resolve, not re-ask forever."""
        r = client.post("/intake", json={"input": {"text": "Nike Dunk Low Panda, Size 44 now"}})
        assert r.json()["status"] == "NEEDS_INFO"
        assert r.json()["missing"] == ["cap_landed_eur"]
        r = client.post(f"/intake/{r.json()['intake_id']}/clarify", json={"text": "75"})
        body = r.json()
        assert body["status"] == "OK"
        assert body["mandate"]["cap_landed_eur"] == "75"
        assert body["mandate"]["mode"] == "IMMEDIATE"
        assert body["brief"]["size_eu"] == "44"

    def test_bare_number_not_misread_as_cap(self, client):
        """Sizes, style codes, '990' product token, and deadlines never
        become the cap via the bare-number fallback."""
        r = client.post("/intake", json={"input": {"text": "new balance 990 DD1391-100 size 44, need in 10 days"}})
        assert r.json()["status"] == "NEEDS_INFO"
        assert r.json()["missing"] == ["cap_landed_eur"]

    def test_immediate_mode_and_deadline_parsed(self, client):
        r = client.post("/intake", json={"input": {"text": "jordan 1 size 44 under €300 now, need in 10 days"}})
        m = r.json()["mandate"]
        assert m["mode"] == "IMMEDIATE" and m["need_within_ticks"] == 10

    def test_clarify_after_promotion_conflicts(self, client):
        r = client.post("/intake", json={"input": {"text": "nike dunk 43 under €80"}})
        intake_id = r.json()["intake_id"]
        assert client.post(f"/intake/{intake_id}/clarify", json={"text": "x"}).status_code == 409


# ---------------------------------------------------------------- hunt lifecycle

class TestHuntLifecycle:
    def test_mandate_editable_pre_confirm_only(self, client):
        r = client.post("/intake", json={"input": {"text": "nike dunk 43 under €80"}})
        hunt_id = r.json()["hunt_id"]
        r = client.patch(f"/hunts/{hunt_id}/mandate", json={"mandate": {"alert_budget_per_week": 3}})
        assert r.status_code == 200 and r.json()["alert_budget_per_week"] == 3
        client.post(f"/hunts/{hunt_id}/confirm")
        r = client.patch(f"/hunts/{hunt_id}/mandate", json={"mandate": {"alert_budget_per_week": 5}})
        assert r.status_code == 409

    def test_immediate_requires_confirm(self, client):
        r = client.post("/intake", json={"input": {"text": "nike dunk 43 under €80"}})
        assert client.post(f"/hunts/{r.json()['hunt_id']}/run_immediate").status_code == 409

    def test_run_immediate_fixture_path_shape(self, client):
        r = client.post("/intake", json={"world_id": "w_fixture",
                                         "input": {"text": "nike dunk panda size 43 under €80"}})
        hunt_id = r.json()["hunt_id"]
        client.post(f"/hunts/{hunt_id}/confirm")
        body = client.post(f"/hunts/{hunt_id}/run_immediate").json()
        assert body["action"] == "ESCALATE_NONE_FOUND"
        assert body["handoff"] == "switch_to_monitor"
        assert body["near_misses"], "ranked near-misses must be present"
        nm = body["near_misses"][0]
        assert {"listing_id", "landed_eur", "reasons", "eligibility", "approvable"} <= set(nm)
        # the receipt landed in the paged store too
        assert client.get(f"/hunts/{hunt_id}/receipts").json()

    def test_run_immediate_real_engine_buy(self, client):
        """Post-S1 hybrid: default world is the REAL generated seed-42 world and
        run_immediate is the REAL engine (mirrors scripts/demo_immediate.py)."""
        r = client.post("/intake", json={"input": {"text": "nike dunk panda size 42 under €150 now"}})
        assert r.json()["status"] == "OK"
        hunt_id = r.json()["hunt_id"]
        client.post(f"/hunts/{hunt_id}/confirm")
        body = client.post(f"/hunts/{hunt_id}/run_immediate").json()
        assert body["action"] == "BUY"
        assert body["handoff"] is None
        chosen = body["chosen"]
        assert chosen is not None and chosen["purchase_eligible"] is True
        lines = chosen["quote"]["line_items"]
        from decimal import Decimal as D
        assert sum(D(li["amount_eur"]) for li in lines) == D(chosen["quote"]["landed_eur"])
        assert client.get(f"/hunts/{hunt_id}").json()["status"] == "PURCHASED"

    def test_revoke(self, client):
        hunt_id = make_confirmed_hunt(client)
        assert client.post(f"/hunts/{hunt_id}/revoke").json()["status"] == "REVOKED"

    def test_unknown_hunt_404(self, client):
        assert client.get("/hunts/h_nope").status_code == 404


# ---------------------------------------------------------------- SSE + asks
#
# NOTE: httpx.ASGITransport buffers the whole response body (no true streaming),
# and the server generator PAUSES at each ask (§6.2). So the events request only
# completes if a concurrent task resolves asks as they appear. That concurrent
# resolver is also exactly what the browser does, so the shape is faithful.

def parse_sse(text: str) -> list[dict]:
    return [json.loads(line[len("data:"):].strip())
            for line in text.splitlines() if line.startswith("data:")]


async def resolve_asks_as_they_appear(ac: httpx.AsyncClient, plan: dict[str, str], n: int) -> list[str]:
    """Poll for PENDING asks and resolve each by its kind per `plan`
    ({kind: "approve"|"decline"}); returns resolved ids."""
    resolved: list[str] = []
    while len(resolved) < n:
        for ask in list(api.ENGINE.asks.values()):
            if ask.status == "PENDING" and ask.id not in resolved:
                resolution = plan[ask.kind.value]
                res = await ac.post(f"/asks/{ask.id}/{resolution}")
                assert res.json()["status"] == resolution.upper() + "D"  # APPROVED / DECLINED
                resolved.append(ask.id)
        await asyncio.sleep(0.005)
    return resolved


async def run_monitor_stream(ac: httpx.AsyncClient, plan: dict[str, str], n_asks: int):
    # w_fixture pins the SCRIPTED replay these story-arc tests encode; hunts on
    # generated worlds stream the real engine loop (S2 swap) instead.
    r = await ac.post("/intake", json={"world_id": "w_fixture",
                                       "input": {"text": "nike dunk panda size 43 under €80"}})
    hunt_id = r.json()["hunt_id"]
    await ac.post(f"/hunts/{hunt_id}/confirm")
    await ac.post(f"/hunts/{hunt_id}/start")
    resolver = asyncio.create_task(resolve_asks_as_they_appear(ac, plan, n_asks))
    resp = await asyncio.wait_for(
        ac.get(f"/hunts/{hunt_id}/events", params={"tick_ms": 0}), timeout=30)
    resolved = await asyncio.wait_for(resolver, timeout=5)
    return hunt_id, parse_sse(resp.text), resolved


def order_states(seen: list[dict]) -> list[str]:
    return [e["payload"]["state"] for e in seen if e["type"] == "order"]


@pytest.mark.anyio
async def test_sse_approve_gray_plays_cancellation_arc_and_skips_overcap():
    """Approving the E2 gray ask: order PLACED → merchant cancels → refund;
    the E3 over-cap ask is incoherent while an order is pending and never fires;
    the scripted BUY still ends the hunt."""
    api.ENGINE = api.FixtureEngine()
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # events before start → 409
        r = await ac.post("/intake", json={"input": {"text": "nike dunk panda size 43 under €80"}})
        pre = r.json()["hunt_id"]
        await ac.post(f"/hunts/{pre}/confirm")
        assert (await ac.get(f"/hunts/{pre}/events")).status_code == 409

        hunt_id, seen, resolved = await run_monitor_stream(
            ac, {"GRAY_ROUTE": "approve", "OVER_CAP": "approve"}, n_asks=1)
        for env in seen:
            assert {"type", "tick", "payload"} <= set(env), "envelope shape (§8)"
        assert [e["payload"]["kind"] for e in seen if e["type"] == "ask"] == ["GRAY_ROUTE"]
        assert order_states(seen) == ["PLACED", "CANCELLED_BY_MERCHANT", "REFUNDED",
                                      "PLACED", "CONFIRMED"]
        assert seen[-1]["type"] == "done" and seen[-1]["payload"]["final_status"] == "PURCHASED"

        # single-use consent: re-approving a resolved ask must 409 (§6.3)
        assert (await ac.post(f"/asks/{resolved[0]}/approve")).status_code == 409
        got = (await ac.get(f"/hunts/{hunt_id}/receipts", params={"from_tick": 40})).json()
        assert any(r["action"] == "BUY" for r in got)


@pytest.mark.anyio
async def test_sse_decline_gray_no_phantom_cancellation():
    """User-reported bug: declining the gray ask must NOT show a merchant
    cancelling an order that was never placed."""
    api.ENGINE = api.FixtureEngine()
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        _, seen, _ = await run_monitor_stream(
            ac, {"GRAY_ROUTE": "decline", "OVER_CAP": "decline"}, n_asks=2)
        states = order_states(seen)
        assert "CANCELLED_BY_MERCHANT" not in states and "REFUNDED" not in states
        assert states == ["PLACED", "CONFIRMED"]        # only the final scripted BUY
        assert {a["payload"]["kind"] for a in seen if a["type"] == "ask"} == \
            {"GRAY_ROUTE", "OVER_CAP"}
        resolutions = [e["payload"].get("ask_resolution") for e in seen
                       if e["type"] == "status" and "ask_resolution" in e["payload"]]
        assert resolutions == ["DECLINED", "DECLINED"]
        assert seen[-1]["payload"]["final_status"] == "PURCHASED"


@pytest.mark.anyio
async def test_sse_approve_overcap_buys_at_ask_tick():
    """§5.9: approving an OVER_CAP ask executes the purchase at the ask's tick,
    decided_by HUMAN — the hunt ends there instead of watching on."""
    api.ENGINE = api.FixtureEngine()
    transport = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        hunt_id, seen, _ = await run_monitor_stream(
            ac, {"GRAY_ROUTE": "decline", "OVER_CAP": "approve"}, n_asks=2)
        assert order_states(seen) == ["PLACED", "CONFIRMED"]
        done = seen[-1]
        assert done["payload"]["final_status"] == "PURCHASED"
        assert done["tick"] == 31, "hunt ends at the over-cap ask's tick, not the scripted BUY"
        buys = [e for e in seen if e["type"] == "receipt" and e["payload"]["action"] == "BUY"]
        assert len(buys) == 1
        assert buys[0]["payload"]["decided_by"] == "HUMAN"
        assert any(r.startswith("cap_extended_once:") for r in buys[0]["payload"]["reasons"])


# ---------------------------------------------------------------- misc surface

class TestMisc:
    def test_real_world_and_dossier(self, client):
        w = client.post("/worlds", json={"seed": 42}).json()
        assert w["world_id"] == "w_42" and w["trap_count"] > 10
        md = client.get(f"/worlds/{w['world_id']}/dossier").json()["markdown"]
        assert len(md) > 1000, "the real generated dossier, not the stub"

    def test_fixture_dossier_still_served(self, client):
        md = client.get("/worlds/w_fixture/dossier").json()["markdown"]
        assert "Trap: bait" in md and "Correct behavior" in md

    def test_unknown_world_404(self, client):
        assert client.get("/worlds/w_nope/dossier").status_code == 404

    def test_eval_roundtrip(self, client):
        run = client.post("/eval/run", json={}).json()
        report = client.get(f"/eval/{run['run_id']}/report").json()["markdown"]
        assert "OURS_MONITOR" in report and "Mandate violations" in report

    def test_config(self, client):
        body = client.get("/config").json()
        assert body["backend"] == "hybrid" and body["tick_ms"] == 300
        assert {"run_immediate", "intake", "narration"} <= set(body["real"])
        assert body["fixture"] == ["monitor_events:w_fixture"]
        assert "monitor_events" in body["real"]
