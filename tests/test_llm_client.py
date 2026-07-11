from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from dealhunter.core.config import Constants
from dealhunter.llm.cache import (
    CacheMode,
    CachedClient,
    LLMCacheCorrupt,
    LLMCacheMiss,
)
from dealhunter.llm.client import LLMProtocolError, OpenAIClient


REQUEST = {
    "surface": "unit_test",
    "schema": {
        "type": "object",
        "properties": {"choice": {"type": ["string", "null"]}},
        "required": ["choice"],
        "additionalProperties": False,
    },
    "instructions": "Choose only from the supplied allowlist.",
    "input": "<untrusted>candidate A</untrusted>",
}


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeSDK:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class CountingClient:
    def __init__(self, response: dict | Exception) -> None:
        self.response = response
        self.calls = 0

    def complete(self, request: dict) -> dict:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_openai_client_translates_canonical_envelope() -> None:
    sdk = FakeSDK('{"choice":"A"}')
    cfg = Constants(LLM_MAX_OUTPUT_TOKENS=321)
    client = OpenAIClient(cfg, sdk_client=sdk)

    assert client.complete(REQUEST) == {"choice": "A"}
    assert sdk.responses.calls == [
        {
            "model": "gpt-5.6-terra",
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 321,
            "instructions": REQUEST["instructions"],
            "input": REQUEST["input"],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "unit_test",
                    "strict": True,
                    "schema": REQUEST["schema"],
                }
            },
        }
    ]


def test_openai_client_canonicalizes_mapping_input_for_responses_api() -> None:
    sdk = FakeSDK('{"choice":"A"}')
    request = {**REQUEST, "input": {"z": 1, "a": "value"}}
    OpenAIClient(Constants(), sdk_client=sdk).complete(request)
    assert sdk.responses.calls[0]["input"] == '{"a":"value","z":1}'


@pytest.mark.parametrize("output", ["", "not json", "[]", '{"abstain":true} trailing'])
def test_openai_client_rejects_refusal_or_malformed_output(output: str) -> None:
    with pytest.raises(LLMProtocolError):
        OpenAIClient(Constants(), sdk_client=FakeSDK(output)).complete(REQUEST)


def test_cache_warm_then_replay_with_stable_key(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    upstream = CountingClient({"choice": "A", "reason": "ok"})
    warm = CachedClient(upstream, path, "model-a", CacheMode.WARM)
    assert warm.complete(REQUEST) == {"choice": "A", "reason": "ok"}
    assert upstream.calls == 1

    reordered = {key: REQUEST[key] for key in reversed(REQUEST)}
    replay_upstream = CountingClient(AssertionError("network attempted"))
    replay = CachedClient(replay_upstream, path, "model-a", CacheMode.REPLAY)
    assert replay.complete(reordered) == {"choice": "A", "reason": "ok"}
    assert replay_upstream.calls == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT DISTINCT created FROM llm_cache").fetchall() == [
            ("1970-01-01T00:00:00+00:00",)
        ]


def test_replay_miss_never_calls_upstream_or_creates_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"
    upstream = CountingClient(AssertionError("network attempted"))
    replay = CachedClient(upstream, path, "model-a", CacheMode.REPLAY)
    with pytest.raises(LLMCacheMiss):
        replay.complete(REQUEST)
    assert upstream.calls == 0
    assert not path.exists()


def test_cache_key_isolated_by_model(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    CachedClient(CountingClient({"choice": "A"}), path, "model-a", CacheMode.WARM).complete(
        REQUEST
    )
    replay = CachedClient(None, path, "model-b", CacheMode.REPLAY)
    with pytest.raises(LLMCacheMiss):
        replay.complete(REQUEST)


def test_corrupt_cache_row_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    CachedClient(CountingClient({"choice": "A"}), path, "model-a", CacheMode.WARM).complete(
        REQUEST
    )
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE llm_cache SET response = 'not-json'")

    with pytest.raises(LLMCacheCorrupt):
        CachedClient(None, path, "model-a", CacheMode.REPLAY).complete(REQUEST)


def test_transient_upstream_error_is_not_cached(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    upstream = CountingClient(RuntimeError("temporary"))
    warm = CachedClient(upstream, path, "model-a", CacheMode.WARM)
    with pytest.raises(RuntimeError, match="temporary"):
        warm.complete(REQUEST)
    with pytest.raises(RuntimeError, match="temporary"):
        warm.complete(REQUEST)
    assert upstream.calls == 2
