"""Redis pickle-cache regression tests (set/get symmetry)."""

from __future__ import annotations

import pytest

from app.core import cache
from app.core.cache import get_redis_binary


async def test_pickle_roundtrip(fake_redis):
    payload = {
        "chunk_ids": ["a", "b"],
        "contents": ["one", "two"],
        "pages": [1, None],
        "matrix": [[0.5, 0.5], [0.1, 0.9]],
    }
    await cache.cache_set_pickle("t:roundtrip", payload, ttl_seconds=60)
    assert await cache.cache_get_pickle("t:roundtrip") == payload


async def test_pickle_missing_key_is_none(fake_redis):
    assert await cache.cache_get_pickle("t:absent") is None


async def test_pickle_corrupted_entry_returns_none(fake_redis):
    # A garbled value must be treated as a cache miss (and logged), never crash.
    await get_redis_binary().set("t:corrupted", b"definitely-not-a-pickle")
    assert await cache.cache_get_pickle("t:corrupted") is None
