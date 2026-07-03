"""LLM observability — record every model call (tokens, latency, cost) to Postgres.

Fire-and-forget: writes must never break a request, so all failures are swallowed and logged.
Optionally mirrors to Langfuse when LANGFUSE_* env is set.
"""

from __future__ import annotations

import logging
import uuid

from ..config import settings
from .context import current_llm_context

logger = logging.getLogger("laboratree.llm")

_INSERT = (
    "INSERT INTO llm_calls "
    "(id, org_id, project_id, run_id, lab, operation, provider, model, role, "
    " prompt_tokens, completion_tokens, total_tokens, latency_ms, cost_usd, status, error) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)


def _as_uuid(v: str | None):
    if not v:
        return None
    try:
        return uuid.UUID(str(v))
    except (ValueError, TypeError):
        return None


def _estimate_cost(total_tokens: int) -> float | None:
    price = settings.llm_price_per_1k
    if price and total_tokens:
        return round(price * total_tokens / 1000.0, 6)
    return None


def record_llm_call(
    *,
    provider: str,
    model: str,
    role: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: float = 0.0,
    status: str = "ok",
    error: str | None = None,
) -> None:
    if not settings.llm_tracing:
        return
    ctx = current_llm_context()
    cost = _estimate_cost(total_tokens)
    row = (
        uuid.uuid4(),
        _as_uuid(ctx.org_id),
        _as_uuid(ctx.project_id),
        _as_uuid(ctx.run_id),
        ctx.lab,
        ctx.operation,
        provider,
        (model or "")[:120],
        (role or "")[:40],
        int(prompt_tokens or 0),
        int(completion_tokens or 0),
        int(total_tokens or 0),
        float(latency_ms or 0.0),
        cost,
        status,
        (error or "")[:500] or None,
    )
    try:
        import psycopg

        with psycopg.connect(settings.postgres_psycopg_dsn, connect_timeout=2) as conn:
            conn.execute(_INSERT, row)
            conn.commit()
    except Exception:
        logger.debug("llm trace write failed", exc_info=True)

    _mirror_langfuse(row)


def _mirror_langfuse(row) -> None:
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    try:
        from langfuse import Langfuse

        lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        lf.generation(
            name=f"{row[4]}:{row[5]}",  # lab:operation
            model=row[7],
            usage={"input": row[9], "output": row[10], "total": row[11]},
            metadata={"provider": row[6], "role": row[8], "latency_ms": row[12], "status": row[14]},
        )
    except Exception:
        logger.debug("langfuse mirror failed", exc_info=True)
