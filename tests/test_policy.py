from decimal import Decimal as D
from pathlib import Path

from dealhunter.core.config import Constants
from dealhunter.core.enums import (
    AccessTier,
    Action,
    Channel,
    DecidedBy,
    Geo,
    GeoArb,
    HuntStatus,
    MatchFlag,
    Mode,
)
from dealhunter.core.models import (
    AutoBuy,
    Brief,
    GeoPromo,
    Hunt,
    Mandate,
    MatchResult,
    World,
    canonical_json,
)
from dealhunter.engine.policy import evaluate_tick
from dealhunter.engine.alerts import approve_pending_ask
from dealhunter.llm.client import NullClient


ROOT = Path(__file__).resolve().parent.parent
CFG = Constants()


def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


def hunt(*, cap="150", size="43", revoked=False, expires=10, auto=None, geo=GeoArb.ASK):
    return Hunt(
        id="h_42_1",
        brief=Brief(
            product_query="Nike Dunk Low",
            colorway="Panda",
            style_code="DD1391-100",
            size_eu=D(size),
        ),
        mandate=Mandate(
            mode=Mode.IMMEDIATE,
            cap_landed_eur=D(cap),
            expires_tick=expires,
            revoked=revoked,
            geo_arbitrage=geo,
            auto_buy=auto or AutoBuy(),
        ),
        status=HuntStatus.RUNNING,
        start_tick=0,
    )


def monitor_hunt(*, cap="150", expires=10, size="43"):
    current = hunt(cap=cap, expires=expires, size=size)
    current.mandate.mode = Mode.MONITOR
    return current


def test_immediate_buys_max_ev_not_lowest_landed():
    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert receipt.action == Action.BUY
    assert receipt.escalation_tier == "E1"
    assert receipt.chosen is not None
    assert receipt.chosen.quote.listing_id == "l_v001_DD1391-100"
    assert any(
        item.quote.landed_eur < receipt.chosen.quote.landed_eur
        for item in receipt.considered
    )


def test_auto_buy_uses_e0_when_configured_conditions_pass():
    auto = AutoBuy(
        enabled=True,
        within_eur_of_target=D("100"),
        require_stock_low=False,
        require_trust_high=False,
    )
    receipt = evaluate_tick(hunt(auto=auto), 0, world(), CFG, NullClient())
    assert receipt.action == Action.BUY
    assert receipt.escalation_tier == "E0"


def test_far_over_cap_returns_ranked_none_found():
    receipt = evaluate_tick(hunt(cap="50"), 0, world(), CFG, NullClient())
    assert receipt.action == Action.ESCALATE_NONE_FOUND
    assert receipt.escalation_tier == "E5"
    assert receipt.chosen is None
    assert any(reason.startswith("near_miss:") for reason in receipt.reasons)


def test_high_trust_best_ever_offer_inside_band_emits_e3(monkeypatch):
    def only_official(listing, *args, **kwargs):
        if listing.id == "l_v001_DD1391-100":
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", only_official)
    receipt = evaluate_tick(hunt(cap="120"), 0, world(), CFG, NullClient())
    assert receipt.action == Action.ASK
    assert receipt.escalation_tier == "E3"
    assert receipt.chosen is not None
    assert receipt.chosen.quote.landed_eur == D("124.00")


def test_revoked_expired_and_wrong_size_mandates_never_buy():
    revoked = evaluate_tick(hunt(revoked=True), 0, world(), CFG, NullClient())
    expired = evaluate_tick(hunt(expires=0), 0, world(), CFG, NullClient())
    wrong_size = evaluate_tick(hunt(size="44"), 0, world(), CFG, NullClient())
    assert {revoked.action, expired.action, wrong_size.action} == {
        Action.ESCALATE_NONE_FOUND
    }


def test_alert_only_match_flag_blocks_every_purchase(monkeypatch):
    def conflicted(*args, **kwargs):
        return MatchResult(
            style_code="DD1391-100",
            colorway_confirmed=False,
            confidence=0.90,
            flags=[MatchFlag.COLORWAY_CONFLICT],
        )

    monkeypatch.setattr("dealhunter.engine.policy.match", conflicted)
    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert receipt.action == Action.ALERT
    assert all(not item.purchase_eligible for item in receipt.considered)


def test_matcher_reported_condition_mismatch_is_a_hard_gate(monkeypatch):
    def mismatched(*args, **kwargs):
        return MatchResult(
            style_code="DD1391-100",
            colorway_confirmed=True,
            confidence=0.99,
            flags=[MatchFlag.CONDITION_MISMATCH],
        )

    monkeypatch.setattr("dealhunter.engine.policy.match", mismatched)
    receipt = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert receipt.action == Action.ESCALATE_NONE_FOUND
    assert any("condition_mismatch" in reason for reason in receipt.reasons)


def test_reseller_exclusion_is_a_hard_gate(monkeypatch):
    w = world()
    vendors = [
        vendor.model_copy(update={"channel": Channel.RESELLER})
        if vendor.id == "v_001"
        else vendor
        for vendor in w.vendors
    ]
    w = w.model_copy(update={"vendors": vendors})

    def only_official_listing(listing, *args, **kwargs):
        if listing.id == "l_v001_DD1391-100":
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", only_official_listing)
    h = hunt()
    h.brief.exclude_resellers = True
    receipt = evaluate_tick(h, 0, w, CFG, NullClient())
    assert receipt.action == Action.ESCALATE_NONE_FOUND
    assert any("reseller_excluded" in reason for reason in receipt.reasons)


def test_best_gray_route_under_ask_emits_e2(monkeypatch):
    w = world()
    promo = GeoPromo(
        id="g_ip_cheap",
        listing_id="l_v004_DD1391-100",
        viewer_geo=Geo.JP,
        promo_sticker=D("1000"),
        from_tick=0,
        to_tick=1,
        access_tier=AccessTier.IP_GATED,
        p_cancel=D("0.40"),
    )
    w = w.model_copy(update={"geo_promos": [*w.geo_promos, promo]})

    def only_jp_listing(listing, *args, **kwargs):
        if listing.id == "l_v004_DD1391-100":
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", only_jp_listing)
    current = hunt(cap="160", geo=GeoArb.ASK)
    receipt = evaluate_tick(current, 0, w, CFG, NullClient())
    assert receipt.action == Action.ASK
    assert receipt.escalation_tier == "E2"
    assert receipt.chosen is not None
    assert receipt.chosen.quote.access_tier == AccessTier.IP_GATED
    assert receipt.reasons[0] == "gray_route_consent_required"
    assert current.pending_ask is not None
    approve_pending_ask(current, current.pending_ask.quote_hash)
    purchase = evaluate_tick(current, 0, w, CFG, NullClient())
    assert purchase.action == Action.BUY
    assert purchase.decided_by == DecidedBy.HUMAN
    assert current.pending_ask.status == "CONSUMED"


def test_blocked_gray_route_reselects_legal_offer(monkeypatch):
    w = world()
    promo = GeoPromo(
        id="g_ip_cheap",
        listing_id="l_v004_DD1391-100",
        viewer_geo=Geo.JP,
        promo_sticker=D("1000"),
        from_tick=0,
        to_tick=1,
        access_tier=AccessTier.IP_GATED,
        p_cancel=D("0.40"),
    )
    w = w.model_copy(update={"geo_promos": [*w.geo_promos, promo]})

    def only_jp_listing(listing, *args, **kwargs):
        if listing.id == "l_v004_DD1391-100":
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", only_jp_listing)
    current = hunt(cap="160", geo=GeoArb.ASK)
    current.interruptions = [(0, "x", "ALERT"), (0, "y", "ALERT")]
    receipt = evaluate_tick(current, 0, w, CFG, NullClient())
    assert receipt.action == Action.BUY
    assert receipt.chosen is not None
    assert receipt.chosen.quote.access_tier != AccessTier.IP_GATED
    assert "interrupt_budget_exhausted:l_v004_DD1391-100" in receipt.reasons


def test_immediate_receipt_is_byte_deterministic_and_sums_lines():
    first = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    second = evaluate_tick(hunt(), 0, world(), CFG, NullClient())
    assert canonical_json(first) == canonical_json(second)
    assert first.chosen is not None
    assert sum(
        line.amount_eur for line in first.chosen.quote.line_items
    ) == first.chosen.quote.landed_eur


def test_matcher_is_memoized_per_hunt_and_listing(monkeypatch):
    calls = 0

    def counted(listing, *args, **kwargs):
        nonlocal calls
        calls += 1
        if listing.id.endswith("_DD1391-100"):
            return MatchResult(
                style_code="DD1391-100", colorway_confirmed=True, confidence=0.99
            )
        return MatchResult()

    monkeypatch.setattr("dealhunter.engine.policy.match", counted)
    current = monitor_hunt(expires=3)
    evaluate_tick(current, 0, world(), CFG, NullClient())
    first_tick_calls = calls
    evaluate_tick(current, 1, world(), CFG, NullClient())
    assert calls == first_tick_calls


def test_monitor_warmup_alerts_then_holds_with_stopping_evidence():
    current = monitor_hunt()
    first = evaluate_tick(current, 0, world(), CFG, NullClient())
    second = evaluate_tick(current, 1, world(), CFG, NullClient())
    assert first.action == Action.ALERT
    assert second.action == Action.HOLD
    assert second.stopping is not None
    assert second.stopping.n_obs == 1


def test_monitor_forces_buy_on_last_mandate_tick():
    receipt = evaluate_tick(monitor_hunt(expires=1), 0, world(), CFG, NullClient())
    assert receipt.action == Action.BUY
    assert receipt.escalation_tier == "E1"
    assert receipt.stopping is not None
    assert receipt.stopping.horizon == 0
