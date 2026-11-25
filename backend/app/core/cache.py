"""Redis connection management + small cache helpers.

Three client flavors are maintained:

* ``get_redis()``         — async, ``decode_responses=True``  (strings/JSON, rate limiting, Lua)
* ``get_redis_binary()``  — async, ``decode_responses=False`` (binary payloads, e.g. pickled indexes)
* ``get_sync_redis()``    — sync client for Celery workers / non-async contexts

The initializer accepts pre-built clients so tests can inject ``fakeredis``.
"""

from __future__ import annotations

import pickle
from typing import Any

import redis as sync_redis_lib
import redis.asyncio as aredis

from app.core.logging import get_logger

logger = get_logger("cache")

_client: aredis.Redis | None = None
_binary_client: aredis.Redis | None = None
_sync_client: sync_redis_lib.Redis | None = None


# ---------------------------------------------------------------------------
# Initialization / teardown
# ---------------------------------------------------------------------------


def init_redis(
    url: str | None = None,
    *,
    client: aredis.Redis | None = None,
    binary_client: aredis.Redis | None = None,
) -> None:
    """Create async Redis clients (or accept injected ones — used by tests)."""
    global _client, _binary_client
    if client is not None:
        _client = client
    else:
        _client = aredis.from_url(url or "redis://localhost:6379/0", decode_responses=True)
    if binary_client is not None:
        _binary_client = binary_client
    else:
        _binary_client = aredis.from_url(url or "redis://localhost:6379/0", decode_responses=False)


def init_sync_redis(url: str | None = None, *, client: sync_redis_lib.Redis | None = None) -> None:
    """Create the sync Redis client used by Celery tasks."""
    global _sync_client
    if client is not None:
        _sync_client = client
    else:
        _sync_client = sync_redis_lib.from_url(url or "redis://localhost:6379/0", decode_responses=False)


def reset_redis() -> None:
    """Drop all held clients (used between tests)."""
    global _client, _binary_client, _sync_client
    _client = None
    _binary_client = None
    _sync_client = None


async def close_redis() -> None:
    for client in (_client, _binary_client):
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # pragma: no cover - best effort
                pass
    if _sync_client is not None:
        try:
            _sync_client.close()
        except Exception:  # pragma: no cover
            pass
    reset_redis()


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_redis() -> aredis.Redis:
    if _client is None:
        raise RuntimeError("Redis is not initialized. Call init_redis() first.")
    return _client


def get_redis_binary() -> aredis.Redis:
    if _binary_client is None:
        raise RuntimeError("Redis is not initialized. Call init_redis() first.")
    return _binary_client


def get_sync_redis() -> sync_redis_lib.Redis:
    if _sync_client is None:
        raise RuntimeError("Sync Redis is not initialized. Call init_sync_redis() first.")
    return _sync_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def ping() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def cache_get_json(key: str) -> Any | None:
    raw = await get_redis().get(key)
    if raw is None:
        return None
    try:
        import json

        return json.loads(raw)
    except (ValueError, TypeError):
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    import json

    await get_redis().set(key, json.dumps(value), ex=ttl_seconds)


async def cache_get_pickle(key: str) -> Any | None:
    raw = await get_redis_binary().get(key)
    if raw is None:
        return None
    try:
        return pickle.loads(raw)
    except Exception:  # corrupted payload — treat as miss
        logger.warning("Corrupted pickle cache entry for %s", key)
        return None


async def cache_set_pickle(key: str, value: Any, ttl_seconds: int) -> None:
    """Raw pickle bytes go straight to the binary client (decode_responses=False).

    get/set must be symmetric: pickle.dumps here ↔ pickle.loads in ``cache_get_pickle``.
    """
    await get_redis_binary().set(
        key,
        pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL),
        ex=ttl_seconds,
    )


def cache_delete_sync(key: str) -> None:
    """Best-effort key deletion from sync contexts (Celery)."""
    try:
        get_sync_redis().delete(key)
    except Exception:
        logger.warning("Could not delete cache key %s (redis unavailable)", key)
