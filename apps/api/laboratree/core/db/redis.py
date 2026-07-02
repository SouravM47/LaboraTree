"""Redis — Celery broker/result backend, cache, and SSE/WS pub-sub for live agent traces."""

from __future__ import annotations

import redis.asyncio as aioredis

from ..config import settings

_client: aioredis.Redis | None = None


def client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def ping() -> None:
    await client().ping()


async def dispose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
