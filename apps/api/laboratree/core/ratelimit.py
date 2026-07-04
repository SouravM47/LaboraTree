"""Per-user rate limiting for expensive endpoints (external HTTP + LLM calls).

A fixed-window counter in Redis (INCR + EXPIRE) keyed per user + bucket. **Fails open**: if Redis is
unavailable or rate limiting is disabled, requests are allowed — a limiter outage must never take the
API down. Attach to a route with ``dependencies=[Depends(rate_limited("evidence", limit=20))]``.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException

from .config import settings
from .deps import Principal, PrincipalDep

log = logging.getLogger(__name__)


async def check_rate_limit(key: str, limit: int, window_s: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_s). Fixed-window counter; fails open on any Redis error."""
    if not settings.rate_limit_enabled or limit <= 0:
        return True, 0
    try:
        from .db.redis import client

        r = client()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_s)
        if count > limit:
            ttl = await r.ttl(key)
            return False, max(int(ttl), 1)
        return True, 0
    except Exception as exc:  # Redis down / misconfigured — never block the request on the limiter
        log.info("rate limiter unavailable (%s); allowing request", exc)
        return True, 0


def rate_limited(bucket: str, *, limit: int, window_s: int = 60):
    """FastAPI dependency: allow at most `limit` calls to `bucket` per user per `window_s` seconds."""

    async def _dep(principal: PrincipalDep) -> None:  # reuses the request's already-resolved Principal
        key = f"rl:{bucket}:{principal.org_id}:{principal.user.id}"
        allowed, retry = await check_rate_limit(key, limit, window_s)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded for '{bucket}' — retry in {retry}s",
                headers={"Retry-After": str(retry)},
            )

    return Depends(_dep)


__all__ = ["Principal", "check_rate_limit", "rate_limited"]
