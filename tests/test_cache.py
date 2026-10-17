"""Tests de la cache TTL."""

from __future__ import annotations

import time

from autocad_mcp.cache import TTLCache


def test_get_set_roundtrip() -> None:
    cache = TTLCache(ttl=10.0)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}


def test_ttl_expiry() -> None:
    cache = TTLCache(ttl=0.01)
    cache.set("k", 1)
    time.sleep(0.02)
    assert cache.get("k") is None


def test_invalidate_prefix() -> None:
    cache = TTLCache(ttl=10.0)
    cache.set("entities:1", 1)
    cache.set("entities:2", 2)
    cache.set("drawing_info", 3)
    cache.invalidate_prefix("entities:")
    assert cache.get("entities:1") is None
    assert cache.get("entities:2") is None
    assert cache.get("drawing_info") == 3


def test_maxsize_evicts_oldest() -> None:
    cache = TTLCache(ttl=10.0, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
