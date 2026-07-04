"""Redis-backed result cache for expensive, deterministic-enough operations (evidence hunt, data
hunt) — so repeating a hypothesis doesn't re-pay for the searches + LLM calls.

Keys are hashed from the normalized inputs; values are JSON. **Fails open**: any Redis error (or
caching disabled) simply computes the result live. Only cache READ-ONLY work — never operations with
side effects (creating datasets/papers/runs).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .config import settings

log = logging.getLogger(__name__)


def cache_key(bucket: str, project_id: Any, *parts: Any) -> str:
    """Stable key from a bucket + project + the inputs that define the result."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"cache:{bucket}:{project_id}:{digest}"


async def cache_get(key: str) -> Any | None:
    if not settings.ideation_cache_enabled:
        return None
    try:
        from .db.redis import client

        raw = await client().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.info("cache read failed (%s); computing live", exc)
        return None


async def cache_set(key: str, value: Any, ttl_s: int) -> None:
    if not settings.ideation_cache_enabled:
        return
    try:
        from .db.redis import client

        await client().set(key, json.dumps(value, default=str), ex=ttl_s)
    except Exception as exc:
        log.info("cache write failed (%s); ignoring", exc)


async def cached_json(key: str, ttl_s: int, compute: Callable[[], Awaitable[Any]]) -> Any:
    """Return the cached value for `key`, else run `compute()`, cache it, and return it. Transparent —
    the caller gets the same shape whether hit or miss."""
    hit = await cache_get(key)
    if hit is not None:
        return hit
    result = await compute()
    await cache_set(key, result, ttl_s)
    return result


__all__ = ["cache_get", "cache_key", "cache_set", "cached_json"]
