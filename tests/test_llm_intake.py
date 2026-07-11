from __future__ import annotations

import base64
import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter.core.enums import IntakeStatus, Mode
from dealhunter.core.models import World
from dealhunter.llm.client import IntakeUnavailable, NullClient
from dealhunter.llm.intake import (
    ImageResolutionError,
    IntakeState,
    clarify_intake,
    start_intake,
)


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def world() -> World:
    return World.model_validate_json((ROOT / "fixtures" / "mini_world.json").read_text())


class SequenceClient:
    def __init__(self, *responses: dict) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def complete(self, request: dict) -> dict:
        self.requests.append(request)
        return self.responses.pop(0)


class MappingResolver:
    def __init__(self, images: dict[str, bytes]) -> None:
        self.images = images
        self.references: list[str] = []

    def resolve(self, reference: str) -> bytes:
        self.references.append(reference)
        if reference not in self.images:
            raise KeyError(reference)
        return self.images[reference]


def provider_response(
    *,
    product_query: str | None = "Nike Dunk Low Panda",
    size_eu: str | None = "43",
    cap: str | None = "120",
    style_code: str | None = None,
    mode: str | None = None,
    need_within_ticks: int | None = None,
    auto_buy: dict | None = None,
    questions: dict[str, str] | None = None,
) -> dict:
    return {
        "draft": {
            "brief": {
                "product_query": product_query,
                "colorway": "Panda" if product_query else None,
                "style_code": style_code,
                "size_eu": size_eu,
            },
            "mandate": {
                "mode": mode,
                "cap_landed_eur": cap,
                "need_within_ticks": need_within_ticks,
                "auto_buy": auto_buy,
            },
        },
        "question_bank": questions or {},
    }


def test_missing_size_and_cap_are_selected_by_code(world: World) -> None:
    client = SequenceClient(
        provider_response(
            size_eu=None,
            cap=None,
            questions={
                "size_eu": "Which EU size do you need?",
                "cap_landed_eur": "What is your landed cap?",
                "invented": "Enable auto-buy?",
            },
        )
    )
    state = start_intake("i_1", "world_0", "Nike Dunk Panda", world, client)
    assert state.session.last_result.status == IntakeStatus.NEEDS_INFO
    assert state.session.last_result.missing == ["size_eu", "cap_landed_eur"]
    assert state.session.last_result.questions == [
        "Which EU size do you need?",
        "What is your landed cap?",
    ]
    assert state.hunt is None


def test_zero_catalog_candidates_requires_product(world: World) -> None:
    state = start_intake(
        "i_2",
        "world_0",
        "antique hiking boot",
        world,
        SequenceClient(provider_response(product_query="antique hiking boot")),
    )
    assert "product_query" in state.session.last_result.missing
    assert state.session.last_result.status == IntakeStatus.NEEDS_INFO


def test_more_than_eight_candidates_is_ambiguous(world: World) -> None:
    template = world.products[0]
    extras = [
        template.model_copy(
            update={
                "id": f"p_extra_{index}",
                "model": f"Runner {index}",
                "style_code": f"RUN{index:03d}",
            }
        )
        for index in range(10)
    ]
    broad_world = world.model_copy(update={"products": extras})
    state = start_intake(
        "i_3",
        "world_0",
        "Nike",
        broad_world,
        SequenceClient(provider_response(product_query="Nike")),
    )
    assert state.session.last_result.missing[0] == "product_query"
    assert "Runner" in state.session.last_result.questions[0]


@pytest.mark.parametrize(
    ("cap", "deadline", "missing"),
    [("0", None, "cap_landed_eur"), ("-1", None, "cap_landed_eur"), ("120", 0, "need_within_ticks"), ("120", 91, "need_within_ticks")],
)
def test_invalid_cap_or_deadline_never_constructs_hunt(
    world: World, cap: str, deadline: int | None, missing: str
) -> None:
    state = start_intake(
        "i_invalid",
        "world_0",
        "Nike Dunk Panda",
        world,
        SequenceClient(provider_response(cap=cap, need_within_ticks=deadline)),
    )
    assert missing in state.session.last_result.missing
    assert state.hunt is None


def test_unknown_or_unseen_style_code_is_cleared(world: World) -> None:
    unknown = start_intake(
        "i_unknown",
        "world_0",
        "Nike Dunk Panda code ZX999",
        world,
        SequenceClient(provider_response(style_code="ZX999")),
    )
    unseen = start_intake(
        "i_unseen",
        "world_0",
        "Nike Dunk Panda",
        world,
        SequenceClient(provider_response(style_code="DD1391-100")),
    )
    assert unknown.partial_draft["brief"]["style_code"] is None
    assert unseen.partial_draft["brief"]["style_code"] is None


def test_complete_draft_defaults_only_mode_and_creates_hunt(world: World) -> None:
    state = start_intake(
        "i_ok",
        "world_0",
        "Nike Dunk Panda size 43 under 120 euro",
        world,
        SequenceClient(provider_response()),
    )
    result = state.session.last_result
    assert result.status == IntakeStatus.OK
    assert result.brief is not None and result.brief.size_eu == Decimal("43")
    assert result.mandate is not None and result.mandate.mode == Mode.MONITOR
    assert result.mandate.cap_landed_eur == Decimal("120")
    assert state.hunt is not None
    assert state.session.hunt_id == state.hunt.id


def test_questions_are_capped_and_invalid_model_wording_falls_back(world: World) -> None:
    state = start_intake(
        "i_questions",
        "world_0",
        "",
        world,
        SequenceClient(
            provider_response(
                product_query=None,
                size_eu=None,
                cap=None,
                need_within_ticks=0,
                questions={
                    "product_query": "Buy {unknown} now",
                    "size_eu": "Size?",
                    "cap_landed_eur": "Cap?",
                    "need_within_ticks": "Deadline?",
                },
            )
        ),
    )
    assert len(state.session.last_result.questions) == 3
    assert state.session.last_result.questions[0] == "Which brand and model should I look for?"


def test_null_client_makes_intake_unavailable(world: World) -> None:
    with pytest.raises(IntakeUnavailable):
        start_intake("i_null", "world_0", "Nike", world, NullClient())


def test_screenshot_clarify_reparses_all_text_and_exposes_sensitive_diff(world: World) -> None:
    image = b"\x89PNG\r\n\x1a\ntrusted-test-image"
    digest = hashlib.sha256(image).hexdigest()
    reference = f"image:sha256:{digest}"
    resolver = MappingResolver({reference: image})
    client = SequenceClient(
        provider_response(cap=None, auto_buy={"enabled": False}),
        provider_response(size_eu="44", cap="500", auto_buy={"enabled": True}),
    )

    first = start_intake(
        "i_image",
        "world_0",
        "Screenshot details",
        world,
        client,
        image_ref=reference,
        image_resolver=resolver,
    )
    second = clarify_intake(first, "Actually cap is 500", world, client, image_resolver=resolver)

    assert first.session.last_result.status == IntakeStatus.NEEDS_INFO
    assert second.session.last_result.status == IntakeStatus.OK
    assert second.session.transcript == ["Screenshot details", reference, "Actually cap is 500"]
    assert resolver.references == [reference, reference]
    assert "Actually cap is 500" in str(client.requests[1]["input"])
    image_url = client.requests[1]["input"][0]["content"][1]["image_url"]
    assert image_url == "data:image/png;base64," + base64.b64encode(image).decode()
    changed = {entry.path: entry for entry in second.diff}
    assert [entry.path for entry in second.diff] == sorted(entry.path for entry in second.diff)
    assert changed["brief.size_eu"].sensitive
    assert changed["mandate.cap_landed_eur"].sensitive
    assert changed["mandate.auto_buy.enabled"].sensitive


def test_image_reference_must_be_well_formed_and_resolvable(world: World) -> None:
    client = SequenceClient(provider_response())
    with pytest.raises(ImageResolutionError, match="malformed"):
        start_intake(
            "i_bad_ref",
            "world_0",
            "x",
            world,
            client,
            image_ref="image:sha256:nope",
            image_resolver=MappingResolver({}),
        )
    missing = "image:sha256:" + "0" * 64
    with pytest.raises(ImageResolutionError, match="not found"):
        start_intake(
            "i_missing",
            "world_0",
            "x",
            world,
            client,
            image_ref=missing,
            image_resolver=MappingResolver({}),
        )


def test_clarify_requires_existing_needs_info_state(world: World) -> None:
    complete = start_intake(
        "i_done", "world_0", "Nike Dunk", world, SequenceClient(provider_response())
    )
    with pytest.raises(ValueError, match="NEEDS_INFO"):
        clarify_intake(complete, "more", world, SequenceClient(provider_response()))


def test_state_type_retains_private_draft(world: World) -> None:
    state = start_intake(
        "i_state", "world_0", "Nike Dunk", world, SequenceClient(provider_response(cap=None))
    )
    assert isinstance(state, IntakeState)
    assert state.partial_draft["brief"]["product_query"] == "Nike Dunk Low Panda"
