"""Rate limiter + result cache — fixed-window counting, transparent caching, and fail-open."""

from __future__ import annotations

import asyncio

from laboratree.core import cache as cache_mod
from laboratree.core import ratelimit
from laboratree.core.db import redis as redis_mod


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict = {}

    async def incr(self, k):
        self.store[k] = self.store.get(k, 0) + 1
        return self.store[k]

    async def expire(self, k, s):
        return True

    async def ttl(self, k):
        return 42

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v, ex=None):
        self.store[k] = v


def test_rate_limit_blocks_after_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_mod, "client", lambda: fake)

    async def go():
        return [await ratelimit.check_rate_limit("rl:x", limit=3, window_s=60) for _ in range(5)]

    allowed = [a for a, _ in asyncio.run(go())]
    assert allowed == [True, True, True, False, False]


def test_rate_limit_fails_open_when_redis_down(monkeypatch):
    def boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(redis_mod, "client", boom)
    allowed, retry = asyncio.run(ratelimit.check_rate_limit("rl:y", limit=1, window_s=60))
    assert allowed is True and retry == 0            # a limiter outage must never block requests


def test_cached_json_computes_once_then_serves_cache(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_mod, "client", lambda: fake)
    calls = {"n": 0}

    async def compute():
        calls["n"] += 1
        return {"value": calls["n"]}

    async def go():
        key = cache_mod.cache_key("evidence", "proj1", "hypothesis")
        first = await cache_mod.cached_json(key, 60, compute)
        second = await cache_mod.cached_json(key, 60, compute)
        return first, second

    first, second = asyncio.run(go())
    assert first == {"value": 1} and second == {"value": 1}   # served from cache, compute ran once
    assert calls["n"] == 1
