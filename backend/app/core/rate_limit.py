"""Redis-backed sliding-window rate limiter (atomic via Lua) + FastAPI dependency factories.

Design notes:

* Window = sorted-set of per-request timestamps (ms). Expired members are pruned
  inside the Lua script, which performs prune→count→insert atomically.
* **Fail-open**: if Redis is unreachable, requests are allowed and a warning is
  logged — availability is preferred over strict enforcement.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import Request

from app.core.cache import get_redis
from app.core.errors import RateLimitError
from app.core.logging import get_logger

logger = get_logger("rate_limit")

SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)

if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after_ms = 1000
    if oldest[2] then
        retry_after_ms = math.ceil(tonumber(oldest[2]) + window_ms - now_ms)
    end
    if retry_after_ms < 1 then retry_after_ms = 1 end
    return {0, math.ceil(retry_after_ms / 1000)}
end

redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms + 60000)
return {1, limit - count - 1}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Sliding-window counter stored in a Redis sorted set."""

    def __init__(self, redis_client_provider: Callable[[], Any] | None = None) -> None:
        self._provider = redis_client_provider

    def _client(self) -> Any:
        return self._provider() if self._provider else get_redis()

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Record one hit and decide whether it is within budget."""
        try:
            client = self._client()
            now_ms = int(time.time() * 1000)
            result = await client.eval(
                SLIDING_WINDOW_LUA,
                1,
                key,
                now_ms,
                window_seconds * 1000,
                limit,
                uuid.uuid4().hex,
            )
            allowed, value = int(result[0]), int(result[1])
            if allowed:
                return RateLimitResult(allowed=True, remaining=value, retry_after_seconds=0)
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(1, value))
        except RateLimitError:
            raise
        except Exception as exc:  # Redis down → fail-open
            logger.warning("Rate limiter unavailable (%s); failing open for key=%s", exc, key)
            return RateLimitResult(allowed=True, remaining=-1, retry_after_seconds=0)

    async def check_only(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Peek without recording a hit."""
        try:
            client = self._client()
            now_ms = int(time.time() * 1000)
            count = await client.zcard(key)
            pruned = await client.zremrangebyscore(key, "-inf", now_ms - window_seconds * 1000)
            if pruned:
                count = await client.zcard(key)
            if count >= limit:
                oldest = await client.zrange(key, 0, 0, withscores=True)
                retry_after = 1
                if oldest:
                    retry_after = max(1, int(oldest[0][1] + window_seconds * 1000 - now_ms) // 1000)
                return RateLimitResult(False, 0, retry_after)
            return RateLimitResult(True, limit - count, 0)
        except Exception as exc:
            logger.warning("Rate limiter unavailable (%s); failing open for key=%s", exc, key)
            return RateLimitResult(True, -1, 0)


limiter = SlidingWindowRateLimiter()


def raise_if_blocked(result: RateLimitResult) -> None:
    """Convert a blocked result into a 429 with a Retry-After header."""
    if not result.allowed:
        raise RateLimitError(
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


def client_ip(request: Request) -> str:
    """Best-effort client IP (honors the first X-Forwarded-For hop)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_rate_limit(scope: str, limit: int, window_seconds: int) -> Callable[[Request], Awaitable[None]]:
    """Rate limit by client IP (for unauthenticated endpoints such as login)."""

    async def dependency(request: Request) -> None:
        result = await limiter.hit(f"rl:{scope}:ip:{client_ip(request)}", limit, window_seconds)
        raise_if_blocked(result)

    return dependency

