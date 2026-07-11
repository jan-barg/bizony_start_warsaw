"""FastAPI surface — spec §8. Branch feat/api-ui (Work Order 4).

HYBRID backend (post-S1): worlds and IMMEDIATE mode run on the REAL engine
(`generate_world` + `run_immediate` on generated worlds); intake remains the
deterministic regex fake (real LLM intake is Work Order 3) and the MONITOR
SSE stream still replays `fixtures/receipts_demo.jsonl` — the real monitor
loop (stopping + asks + orders) is feat/engine's next slice. The endpoint
signatures and event envelopes never change across these swaps (§8).

The UI is a pure consumer of receipts + events: no decision logic client-side.
"""
from __future__ import annotations

import asyncio
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..core.config import Constants
from ..core.enums import Action, AskKind, DecidedBy, GeoArb, HuntStatus, IntakeStatus, Mode
from ..core.ids import ask_id as make_ask_id
from ..core.ids import hunt_id as make_hunt_id
from ..core.models import (
    Ask, AutoBuy, Brief, Hunt, IntakeResult, Mandate, Receipt, World,
    canonical_json, quote_hash,
)
from ..engine.loop import run_immediate as engine_run_immediate
from ..llm.client import NullClient
from ..world.dossier import render_dossier
from ..world.generate import generate_world

# Generated worlds are deterministic and expensive-ish (~24k rows) — cache them
# at module level so tests resetting FixtureEngine don't regenerate per test.
_GEN_WORLDS: dict[int, World] = {}
DEFAULT_WORLD_ID = "w_42"


def _generated_world(seed: int) -> World:
    if seed not in _GEN_WORLDS:
        _GEN_WORLDS[seed] = generate_world(seed, CFG)
    return _GEN_WORLDS[seed]

ROOT = Path(__file__).resolve().parent.parent.parent
CFG = Constants()

app = FastAPI(title="SolidHunt API", version="0.1.0-fixture")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # vite dev
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# FixtureEngine — replaced by the real engine at sync point S2
# ---------------------------------------------------------------------------

class FixtureEngine:
    """Deterministic fake backend. Loads the committed fixtures once; fakes
    intake with regexes (the real LLM intake is Work Order 3); replays the
    demo receipts as the monitor timeline, pausing on asks."""

    PRODUCTS = [  # token → (query, style_code)
        ("dunk", ("Nike Dunk Low", "DD1391-100")),
        ("panda", ("Nike Dunk Low", "DD1391-100")),
        ("samba", ("Adidas Samba OG", "GW2288")),
        ("jordan", ("Air Jordan 1 High", "DZ5485-612")),
        ("990", ("New Balance 990v6", "M990GL6")),
    ]
    QUESTIONS = {
        "product_query": "Which product are you hunting — brand and model?",
        "size_eu": "What EU size do you need?",
        "cap_landed_eur": "What's your maximum all-in (landed) price, in EUR?",
    }

    def __init__(self) -> None:
        self.world = World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())
        rows = (ROOT / "fixtures" / "receipts_demo.jsonl").read_text().splitlines()
        receipts = [Receipt.model_validate_json(r) for r in rows]
        self.timeline = sorted(
            (r for r in receipts if r.action != Action.ESCALATE_NONE_FOUND),
            key=lambda r: (r.tick, r.id),
        )
        self.immediate_receipt = next(r for r in receipts if r.action == Action.ESCALATE_NONE_FOUND)
        self.intakes: dict[str, dict[str, Any]] = {}
        self.hunts: dict[str, Hunt] = {}
        self.hunt_world: dict[str, str] = {}   # hunt_id → world_id (Hunt model is frozen core)
        self.asks: dict[str, Ask] = {}
        self.ask_events: dict[str, asyncio.Event] = {}
        self.receipts_by_hunt: dict[str, list[Receipt]] = {}
        self.eval_runs: dict[str, str] = {}
        self._n_intake = 0
        self._n_hunt = 0
        self._n_eval = 0

    # ---- fake intake (deterministic; the sufficiency gate is REAL logic §7.1) ----

    def parse(self, transcript: list[str]) -> IntakeResult:
        text = " ".join(transcript).lower()
        product = next((q for tok, q in self.PRODUCTS if tok in text), None)

        cap: Decimal | None = None
        m = re.search(r"(?:€|eur\s?|under\s|below\s|max\s)\s*(\d{2,4})(?!\d)", text)
        if m:
            cap = Decimal(m.group(1))

        size: Decimal | None = None
        m = re.search(r"(?:size|rozmiar|eu)\s*(\d{2}(?:\.5)?)", text)
        if m:
            size = Decimal(m.group(1))
        else:
            for n in re.findall(r"\b(\d{2}(?:\.5)?)\b", text):
                if Decimal("35") <= Decimal(n) <= Decimal("50") and Decimal(n) != cap:
                    size = Decimal(n)
                    break

        # Cap fallback: a clarify reply is usually a bare number ("75") with no
        # currency marker, which the regex above misses — the loop would re-ask
        # forever. Treat leftover bare numbers as cap candidates; the LATEST
        # wins (the whole transcript is re-parsed, so the newest answer is last).
        if cap is None:
            scrubbed = re.sub(r"\b[a-z]{1,3}\d{3,5}-\d{2,4}\b", " ", text)   # style codes
            scrubbed = re.sub(r"in \d+ days", " ", scrubbed)                  # deadlines
            consumed = [size] if size is not None else []
            candidates: list[Decimal] = []
            for n in re.findall(r"\b(\d{2,4}(?:\.\d{1,2})?)\b", scrubbed):
                v = Decimal(n)
                if v < 20 or any(n == tok for tok, _ in self.PRODUCTS):
                    continue                                                  # too small / "990"
                if v in consumed:
                    consumed.remove(v)                                        # the size, once
                    continue
                candidates.append(v)
            if candidates:
                cap = candidates[-1]

        missing = [k for k, v in (("product_query", product), ("size_eu", size),
                                  ("cap_landed_eur", cap)) if v is None]
        if missing:
            return IntakeResult(status=IntakeStatus.NEEDS_INFO, missing=missing,
                                questions=[self.QUESTIONS[k] for k in missing[:CFG.INTAKE_MAX_QUESTIONS]])

        mode = Mode.IMMEDIATE if re.search(r"\b(now|immediately|today|right away)\b", text) else Mode.MONITOR
        deadline = re.search(r"in (\d+) days", text)
        auto = bool(re.search(r"(just buy|don'?t ask|auto[- ]?buy)", text))
        brief = Brief(product_query=product[0], style_code=product[1], size_eu=size,
                      exclude_resellers="resell" in text)
        mandate = Mandate(mode=mode, cap_landed_eur=cap,
                          need_within_ticks=int(deadline.group(1)) if deadline else None,
                          auto_buy=AutoBuy(enabled=auto),
                          geo_arbitrage=GeoArb.ASK,
                          expires_tick=CFG.HORIZON)
        return IntakeResult(status=IntakeStatus.OK, brief=brief, mandate=mandate)

    @staticmethod
    def mandate_diff(old: IntakeResult | None, new: IntakeResult) -> list[dict[str, str]]:
        """Deterministic field-level diff across clarify rounds (§7.1) — the UI
        renders changed authority in red on the confirm card."""
        if old is None or old.mandate is None or new.mandate is None:
            return []
        diff = []
        for prefix, o, n in (("brief", old.brief, new.brief), ("mandate", old.mandate, new.mandate)):
            if o is None or n is None:
                continue
            od, nd = o.model_dump(mode="json"), n.model_dump(mode="json")
            for key in nd:
                if od.get(key) != nd[key]:
                    diff.append({"field": f"{prefix}.{key}", "old": json.dumps(od.get(key)),
                                 "new": json.dumps(nd[key])})
        return diff


ENGINE = FixtureEngine()


def _intake_payload(intake_id: str) -> dict[str, Any]:
    s = ENGINE.intakes[intake_id]
    r: IntakeResult = s["result"]
    out: dict[str, Any] = {"intake_id": intake_id, "status": r.status.value,
                           "missing": r.missing, "questions": r.questions,
                           "mandate_diff": s["diff"]}
    if r.status == IntakeStatus.OK:
        out |= {"hunt_id": s["hunt_id"],
                "brief": json.loads(r.brief.model_dump_json()),
                "mandate": json.loads(r.mandate.model_dump_json())}
    return out


def _hunt(hunt_id: str) -> Hunt:
    h = ENGINE.hunts.get(hunt_id)
    if h is None:
        raise HTTPException(404, f"unknown hunt {hunt_id}")
    return h


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class IntakeBody(BaseModel):
    world_id: str = DEFAULT_WORLD_ID   # generated seed-42 world; "w_fixture" still accepted
    input: dict[str, str]              # {"text": ...} (image_b64 at S2+)
    mode: str | None = None


class ClarifyBody(BaseModel):
    text: str


class MandatePatch(BaseModel):
    mandate: dict[str, Any]


class EvalBody(BaseModel):
    seeds: list[int] = [42]
    policies: list[str] = ["GREEDY_STICKER", "LANDED_NO_TRUST", "OURS_IMMEDIATE", "OURS_MONITOR"]
    ask_policy: str = "approve"


# ---------------------------------------------------------------------------
# Worlds
# ---------------------------------------------------------------------------

def _resolve_world(world_id: str) -> World:
    if world_id == "w_fixture":
        return ENGINE.world
    if world_id.startswith("w_") and world_id[2:].isdigit():
        return _generated_world(int(world_id[2:]))
    raise HTTPException(404, f"unknown world {world_id}")


@app.post("/worlds")
def create_world(body: dict | None = None) -> dict[str, Any]:
    seed = (body or {}).get("seed", 42)
    w = _generated_world(int(seed))
    world_id = f"w_{seed}"
    return {"world_id": world_id, "dossier_url": f"/worlds/{world_id}/dossier",
            "trap_count": len(w.traps)}


@app.get("/worlds/{world_id}/dossier")
def dossier(world_id: str) -> dict[str, str]:
    w = _resolve_world(world_id)
    if world_id != "w_fixture":
        return {"markdown": render_dossier(w, CFG)}     # the real judge-facing dossier
    lines = [f"# World dossier — fixture (seed {w.seed})", "",
             f"{len(w.listings)} listings · {len(w.vendors)} vendors · {len(w.traps)} planted traps", ""]
    for t in w.traps:
        lines += [f"## Trap: {t.trap_type} — `{t.listing_id}`", "",
                  f"**What:** {t.explanation}", "",
                  f"**Correct behavior:** {t.correct_behavior}", ""]
    return {"markdown": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Intake (§7.1 flow over the fixture parser)
# ---------------------------------------------------------------------------

@app.post("/intake")
def intake(body: IntakeBody) -> dict[str, Any]:
    _resolve_world(body.world_id)      # validate early; generates + caches if needed
    ENGINE._n_intake += 1
    intake_id = f"i_{ENGINE._n_intake:03d}"
    transcript = [body.input.get("text", "")]
    result = ENGINE.parse(transcript)
    session = {"transcript": transcript, "result": result, "diff": [], "hunt_id": None,
               "world_id": body.world_id}
    ENGINE.intakes[intake_id] = session
    if result.status == IntakeStatus.OK:
        session["hunt_id"] = _create_hunt(result, body.world_id)
    return _intake_payload(intake_id)


@app.post("/intake/{intake_id}/clarify")
def clarify(intake_id: str, body: ClarifyBody) -> dict[str, Any]:
    s = ENGINE.intakes.get(intake_id)
    if s is None:
        raise HTTPException(404, "unknown intake session")
    if s["hunt_id"]:
        raise HTTPException(409, "intake already promoted to a hunt")
    prev: IntakeResult = s["result"]
    s["transcript"].append(body.text)
    s["result"] = ENGINE.parse(s["transcript"])          # full re-parse (§7.1)
    s["diff"] = FixtureEngine.mandate_diff(prev, s["result"])
    if s["result"].status == IntakeStatus.OK:
        s["hunt_id"] = _create_hunt(s["result"], s.get("world_id", DEFAULT_WORLD_ID))
    return _intake_payload(intake_id)


def _create_hunt(result: IntakeResult, world_id: str) -> str:
    ENGINE._n_hunt += 1
    hid = make_hunt_id(0, ENGINE._n_hunt)
    ENGINE.hunts[hid] = Hunt(id=hid, brief=result.brief, mandate=result.mandate,
                             status=HuntStatus.DRAFT, start_tick=0)
    ENGINE.hunt_world[hid] = world_id
    ENGINE.receipts_by_hunt[hid] = []
    return hid


# ---------------------------------------------------------------------------
# Hunts
# ---------------------------------------------------------------------------

@app.get("/hunts/{hunt_id}")
def get_hunt(hunt_id: str) -> dict[str, Any]:
    return json.loads(_hunt(hunt_id).model_dump_json())


@app.patch("/hunts/{hunt_id}/mandate")
def patch_mandate(hunt_id: str, body: MandatePatch) -> dict[str, Any]:
    h = _hunt(hunt_id)
    if h.status != HuntStatus.DRAFT:
        raise HTTPException(409, "mandate is editable pre-confirm only")
    merged = h.mandate.model_dump() | body.mandate
    h.mandate = Mandate.model_validate(merged)
    return json.loads(h.mandate.model_dump_json())


@app.post("/hunts/{hunt_id}/confirm")
def confirm(hunt_id: str) -> dict[str, str]:
    h = _hunt(hunt_id)
    if h.status != HuntStatus.DRAFT:
        raise HTTPException(409, f"cannot confirm from {h.status}")
    h.status = HuntStatus.CONFIRMED
    return {"status": h.status.value}


@app.post("/hunts/{hunt_id}/run_immediate")
def run_immediate(hunt_id: str) -> dict[str, Any]:
    h = _hunt(hunt_id)
    if h.status != HuntStatus.CONFIRMED:
        raise HTTPException(409, "confirm the mandate first")

    world_id = ENGINE.hunt_world.get(hunt_id, DEFAULT_WORLD_ID)
    if world_id == "w_fixture":
        r = ENGINE.immediate_receipt.model_copy(update={"hunt_id": hunt_id})
    else:
        # REAL engine on a generated world. The endpoint IS immediate execution,
        # so the run copy carries an IMMEDIATE mandate regardless of how the
        # hunt was parsed; the stored hunt is not mutated.
        run_hunt = h.model_copy(update={
            "status": HuntStatus.RUNNING,
            "mandate": h.mandate.model_copy(update={"mode": Mode.IMMEDIATE}),
        })
        r = engine_run_immediate(run_hunt, _resolve_world(world_id), CFG, NullClient())
        r = r.model_copy(update={"hunt_id": hunt_id})

    ENGINE.receipts_by_hunt[hunt_id].append(r)
    chosen = json.loads(r.chosen.model_dump_json()) if r.action == Action.BUY and r.chosen else None
    if r.action == Action.BUY:
        h.status = HuntStatus.PURCHASED
    near = [{"listing_id": e.quote.listing_id, "landed_eur": str(e.quote.landed_eur),
             "reasons": e.gate_failures or ["qualifies"], "eligibility": e.eligibility.value,
             "approvable": e.eligibility.value == "OVER_CAP_BAND"}
            for e in r.considered]
    return {"action": r.action.value, "chosen": chosen, "near_misses": near,
            "receipt_id": r.id, "receipt": json.loads(r.model_dump_json()),
            "handoff": None if r.action == Action.BUY else "switch_to_monitor"}


@app.post("/hunts/{hunt_id}/start")
def start(hunt_id: str) -> dict[str, str]:
    h = _hunt(hunt_id)
    if h.status != HuntStatus.CONFIRMED:
        raise HTTPException(409, "confirm the mandate first")
    h.status = HuntStatus.RUNNING
    return {"status": h.status.value}


@app.post("/hunts/{hunt_id}/revoke")
def revoke(hunt_id: str) -> dict[str, str]:
    h = _hunt(hunt_id)
    h.mandate.revoked = True
    h.status = HuntStatus.REVOKED       # effective same tick (§6.1)
    if h.pending_ask and h.pending_ask.id in ENGINE.ask_events:
        ENGINE.ask_events[h.pending_ask.id].set()
    return {"status": h.status.value}


@app.get("/hunts/{hunt_id}/receipts")
def receipts(hunt_id: str, from_tick: int = 0) -> list[dict[str, Any]]:
    _hunt(hunt_id)
    return [json.loads(r.model_dump_json())
            for r in ENGINE.receipts_by_hunt.get(hunt_id, []) if r.tick >= from_tick]


# ---------------------------------------------------------------------------
# SSE — the monitor timeline (envelope: {type, tick, payload}, §8)
# ---------------------------------------------------------------------------

ASK_NARRATIVE = {
    AskKind.GRAY_ROUTE: (
        "Tokyo storefront promo via forwarder ZenForward: landed {landed} vs {cmp} for the "
        "best non-gray option, ETA {eta} ticks, estimated {cancel}% chance the merchant "
        "cancels (foreign card + forwarding address). Approve this route?"),
    AskKind.OVER_CAP: (
        "Best price ever observed: {landed}, which is over your {cap} cap but within the "
        "10% band. High-trust vendor, colorway confirmed. Approve a one-time cap "
        "extension for exactly this quote?"),
}


def _make_ask(hunt: Hunt, receipt: Receipt, seq: int) -> Ask:
    kind = AskKind.GRAY_ROUTE if receipt.escalation_tier == "E2" else AskKind.OVER_CAP
    q = receipt.chosen.quote
    narrative = ASK_NARRATIVE[kind].format(
        landed=f"€{q.landed_eur}", cmp="€84.00", eta=q.eta_ticks,
        cancel=int(Decimal("100") * q.p_cancel_est), cap=f"€{hunt.mandate.cap_landed_eur}")
    return Ask(id=make_ask_id(hunt.id, receipt.tick, seq), hunt_id=hunt.id, tick=receipt.tick,
               kind=kind, quote=q, comparison_landed_eur=Decimal("84.00"),
               quote_hash=quote_hash(q), narrative=narrative, status="PENDING")


@app.get("/hunts/{hunt_id}/events")
async def events(hunt_id: str, tick_ms: int | None = None) -> EventSourceResponse:
    h = _hunt(hunt_id)
    if h.status != HuntStatus.RUNNING:
        raise HTTPException(409, "hunt is not RUNNING — POST /start first")
    delay = (tick_ms if tick_ms is not None else CFG.TICK_MS) / 1000.0

    async def stream():
        def env(type_: str, tick: int, payload: Any) -> dict[str, str]:
            return {"event": type_,
                    "data": json.dumps({"type": type_, "tick": tick, "payload": payload})}

        # Scripted-arc coherence: the cancellation/refund receipts belong to the
        # gray order's story. They play ONLY if that order was actually placed
        # (user approved the E2 ask) — declining must never show a merchant
        # cancelling an order that never existed (user-reported bug).
        gray_placed = False
        seq = 0
        last_tick = -1
        for r in ENGINE.timeline:
            if h.status == HuntStatus.REVOKED:
                break
            joined = " ".join(r.reasons).lower()
            is_cancel = "cancelled_by_merchant" in joined
            is_refund = "refund settled" in joined
            if (is_cancel or is_refund) and not gray_placed:
                continue                       # no order → no cancellation sub-arc
            if r.action == Action.ASK and r.escalation_tier == "E3" and gray_placed:
                continue                       # order pending → over-cap ask is incoherent

            for t in range(last_tick + 1, r.tick + 1):
                yield env("tick", t, {})
                await asyncio.sleep(delay)
            last_tick = r.tick
            row = r.model_copy(update={"hunt_id": hunt_id})
            ENGINE.receipts_by_hunt[hunt_id].append(row)
            yield env("receipt", r.tick, json.loads(row.model_dump_json()))

            if r.action == Action.ASK:
                ask = _make_ask(h, row, seq)
                seq += 1
                ENGINE.asks[ask.id] = ask
                ENGINE.ask_events[ask.id] = asyncio.Event()
                h.pending_ask = ask
                h.status = HuntStatus.PENDING_ASK
                yield env("ask", r.tick, json.loads(ask.model_dump_json()))
                yield env("status", r.tick, {"status": h.status.value, "clock": "paused"})
                await ENGINE.ask_events[ask.id].wait()      # world clock pauses (§6.2)
                h.pending_ask = None
                if h.status == HuntStatus.REVOKED:
                    break
                h.status = HuntStatus.RUNNING
                yield env("status", r.tick, {"status": h.status.value, "clock": "running",
                                             "ask_resolution": ENGINE.asks[ask.id].status})
                if ENGINE.asks[ask.id].status == "APPROVED":
                    if ask.kind == AskKind.GRAY_ROUTE:
                        # gray order placed → the merchant-cancellation arc will play
                        gray_placed = True
                        yield env("order", r.tick, {"state": "PLACED", "quote_hash": ask.quote_hash})
                    else:
                        # OVER_CAP approval = the purchase executes AT THE ASK'S TICK,
                        # quote-exact, decided_by HUMAN (§5.9) — the hunt ends here,
                        # it does not keep watching.
                        buy = row.model_copy(update={
                            "id": f"{row.id}b", "action": Action.BUY,
                            "decided_by": DecidedBy.HUMAN,
                            "reasons": [f"cap_extended_once:{ask.id}",
                                        "one-time cap extension approved by user"],
                        })
                        ENGINE.receipts_by_hunt[hunt_id].append(buy)
                        yield env("receipt", r.tick, json.loads(buy.model_dump_json()))
                        yield env("order", r.tick, {"state": "PLACED",
                                                    "listing_id": buy.chosen.quote.listing_id})
                        yield env("order", r.tick, {"state": "CONFIRMED",
                                                    "delivery_at_tick": r.tick + buy.chosen.quote.eta_ticks})
                        h.status = HuntStatus.PURCHASED
                        yield env("status", r.tick, {"status": h.status.value})
                        break

            if r.action == Action.BUY:
                yield env("order", r.tick, {"state": "PLACED", "listing_id": row.chosen.quote.listing_id})
                yield env("order", r.tick, {"state": "CONFIRMED",
                                            "delivery_at_tick": r.tick + row.chosen.quote.eta_ticks})
                h.status = HuntStatus.PURCHASED
                yield env("status", r.tick, {"status": h.status.value})
                break

            if is_cancel:
                yield env("order", r.tick, {"state": "CANCELLED_BY_MERCHANT",
                                            "refund_at_tick": r.tick + CFG.REFUND_TICKS})
            if is_refund:
                yield env("order", r.tick, {"state": "REFUNDED"})

        if h.status == HuntStatus.REVOKED:
            yield env("status", last_tick, {"status": "REVOKED"})
        yield env("done", last_tick, {"final_status": h.status.value})

    return EventSourceResponse(stream())


# ---------------------------------------------------------------------------
# Asks
# ---------------------------------------------------------------------------

def _resolve_ask(ask_id: str, resolution: str) -> dict[str, str]:
    ask = ENGINE.asks.get(ask_id)
    if ask is None:
        raise HTTPException(404, "unknown ask")
    if ask.status != "PENDING":
        raise HTTPException(409, f"ask already {ask.status} — asks are single-use (§6.3)")
    ask.status = resolution
    ENGINE.asks[ask_id] = ask
    ENGINE.ask_events[ask_id].set()
    return {"ask_id": ask_id, "status": resolution}


@app.post("/asks/{ask_id}/approve")
def approve_ask(ask_id: str) -> dict[str, str]:
    return _resolve_ask(ask_id, "APPROVED")


@app.post("/asks/{ask_id}/decline")
def decline_ask(ask_id: str) -> dict[str, str]:
    return _resolve_ask(ask_id, "DECLINED")


# ---------------------------------------------------------------------------
# Eval (canned report until S3)
# ---------------------------------------------------------------------------

EVAL_REPORT = """# Eval report — fixture placeholder (real numbers at M8)

| policy | purchase_legitimacy | strike_quality | false_buy_rate | regret p50 | miss_rate |
|---|---|---|---|---|---|
| GREEDY_STICKER | 0.62 | 0.31 | 0.44 | — | 0.05 |
| LANDED_NO_TRUST | 0.81 | 0.58 | 0.21 | €9.40 | 0.08 |
| OURS_IMMEDIATE | 0.99 | 0.74 | 0.00 | €6.10 | 0.12 |
| OURS_MONITOR | 0.99 | 0.91 | 0.00 | €2.30 | 0.06 |

Mandate violations: **0** (invariant, not a metric).
"""


@app.post("/eval/run")
def eval_run(body: EvalBody) -> dict[str, str]:
    ENGINE._n_eval += 1
    run_id = f"e_{ENGINE._n_eval:03d}"
    ENGINE.eval_runs[run_id] = EVAL_REPORT
    return {"run_id": run_id}


@app.get("/eval/{run_id}/report")
def eval_report(run_id: str) -> dict[str, str]:
    if run_id not in ENGINE.eval_runs:
        raise HTTPException(404, "unknown eval run")
    return {"markdown": ENGINE.eval_runs[run_id]}


@app.get("/config")
def config() -> dict[str, Any]:
    return {"tick_ms": CFG.TICK_MS, "horizon": CFG.HORIZON, "backend": "hybrid",
            "real": ["worlds", "dossier", "run_immediate"],
            "fixture": ["intake_parser", "monitor_events"],
            "default_world": DEFAULT_WORLD_ID}
