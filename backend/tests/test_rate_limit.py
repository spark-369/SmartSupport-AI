"""Sliding-window rate limiter tests (against fakeredis)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fakeredis import aioredis as fakeredis_aio

from app.core import cache
from app.core.cache import init_redis
from app.core.errors import RateLimitError
from app.core.rate_limit import SlidingWindowRateLimiter


@pytest.fixture()
def limiter() -> Iterator[SlidingWindowRateLimiter]:
    init_redis(
        client=fakeredis_aio.FakeRedis(decode_responses=True),
        binary_client=fakeredis_aio.FakeRedis(decode_responses=False),
    )
    yield SlidingWindowRateLimiter()
    # Leak-free: without this reset the fakeredis would survive into later
    # tests, making their rate limiters count across the whole run.
    cache.reset_redis()


async def test_allows_under_limit(limiter: SlidingWindowRateLimiter):
    for i in range(3):
        result = await limiter.hit("rl:test", limit=3, window_seconds=60)
        assert result.allowed, f"hit {i} should pass"
        assert result.remaining == 2 - i


async def test_blocks_over_limit(limiter: SlidingWindowRateLimiter):
    for _ in range(2):
        await limiter.hit("rl:test", limit=2, window_seconds=60)
    result = await limiter.hit("rl:test", limit=2, window_seconds=60)
    assert not result.allowed
    assert 1 <= result.retry_after_seconds <= 60


async def test_keys_are_isolated(limiter: SlidingWindowRateLimiter):
    await limiter.hit("rl:a", limit=1, window_seconds=60)
    result = await limiter.hit("rl:b", limit=1, window_seconds=60)
    assert result.allowed


async def test_fail_open_when_redis_unreachable():
    class ExplodingClient:
        def eval(self, *args, **kwargs):
            raise ConnectionError("redis down")

    explosive = SlidingWindowRateLimiter(lambda: ExplodingClient())
    result = await explosive.hit("rl:x", limit=1, window_seconds=60)
    assert result.allowed  # availability over strict enforcement


async def test_check_only_does_not_consume(limiter: SlidingWindowRateLimiter):
    await limiter.hit("rl:peek", limit=2, window_seconds=60)
    peek = await limiter.check_only("rl:peek", limit=2, window_seconds=60)
    assert peek.allowed
    assert peek.remaining == 1
