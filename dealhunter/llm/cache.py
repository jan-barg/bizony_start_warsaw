"""Strict SQLite replay cache for normalized successful LLM responses."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from enum import StrEnum
from pathlib import Path

from .client import LLMClient, LLMProtocolError


_DETERMINISTIC_CREATED = "1970-01-01T00:00:00+00:00"


class CacheMode(StrEnum):
    WARM = "WARM"
    REPLAY = "REPLAY"


class LLMCacheMiss(KeyError):
    """Replay input has no reviewed response in the cache artifact."""


class LLMCacheCorrupt(RuntimeError):
    """A cache row exists but is not a normalized JSON object."""


def _canonical(value: dict) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise LLMProtocolError("request is not canonical-JSON-compatible") from error


def cache_key(model_pin: str, request: dict) -> str:
    material = f"{model_pin}\0{_canonical(request)}".encode()
    return hashlib.sha256(material).hexdigest()


class CachedClient:
    """Read-through in WARM mode; immutable, network-free lookup in REPLAY."""

    def __init__(
        self,
        upstream: LLMClient | None,
        path: str | Path,
        model_pin: str,
        mode: CacheMode,
    ) -> None:
        if mode == CacheMode.WARM and upstream is None:
            raise ValueError("WARM cache requires an upstream client")
        self._upstream = upstream
        self._path = Path(path)
        self._model_pin = model_pin
        self._mode = mode

    def _connect(self) -> sqlite3.Connection:
        if self._mode == CacheMode.REPLAY:
            if not self._path.is_file():
                raise LLMCacheMiss(str(self._path))
            return sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS llm_cache (
                key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                created TEXT NOT NULL
            )"""
        )
        return connection

    def _read(self, key: str) -> dict | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT response FROM llm_cache WHERE key = ?", (key,)
                ).fetchone()
        except sqlite3.DatabaseError as error:
            if self._mode == CacheMode.REPLAY:
                raise LLMCacheCorrupt("cache database is unreadable") from error
            raise
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
        except (json.JSONDecodeError, TypeError) as error:
            raise LLMCacheCorrupt("cache row is not valid JSON") from error
        if not isinstance(payload, dict):
            raise LLMCacheCorrupt("cache row is not a JSON object")
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if normalized != row[0]:
            raise LLMCacheCorrupt("cache row is not normalized")
        return payload

    def complete(self, request: dict) -> dict:
        key = cache_key(self._model_pin, request)
        cached = self._read(key)
        if cached is not None:
            return cached
        if self._mode == CacheMode.REPLAY:
            raise LLMCacheMiss(key)
        assert self._upstream is not None
        response = self._upstream.complete(request)
        if not isinstance(response, dict):
            raise LLMProtocolError("only successful JSON objects may be cached")
        normalized = _canonical(response)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO llm_cache(key, response, created) VALUES (?, ?, ?)",
                (key, normalized, _DETERMINISTIC_CREATED),
            )
        return json.loads(normalized)
