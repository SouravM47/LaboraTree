"""Health endpoint — verifies connectivity to every datastore and reports readiness."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from ..core.db import mongo, neo4j, postgres, redis
from ..core.llm import get_llm
from ..core.storage import get_blob_store

router = APIRouter(tags=["health"])


async def _check(name: str, coro) -> tuple[str, dict[str, Any]]:
    try:
        await coro
        return name, {"ok": True}
    except Exception as exc:  # report, don't raise — health should always answer
        return name, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@router.get("/health")
async def health() -> dict[str, Any]:
    results = await asyncio.gather(
        _check("postgres", postgres.ping()),
        _check("redis", redis.ping()),
        _check("neo4j", neo4j.ping()),
        _check("mongodb", mongo.ping()),
    )
    stores = dict(results)

    blob = get_blob_store()
    stores["blob"] = {"ok": blob.writable(), "backend": "local", "root": str(blob.root)}

    stores["llm"] = {"ok": get_llm().configured(), "provider": get_llm().provider}

    all_ok = all(v.get("ok") for k, v in stores.items() if k != "llm")
    return {"status": "ok" if all_ok else "degraded", "services": stores}
