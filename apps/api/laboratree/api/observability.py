"""LLM observability API — recent calls + per-Lab usage summary for a project."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..core.deps import PrincipalDep, SessionDep
from ..projects.models import LLMCall, Project

router = APIRouter(prefix="/api", tags=["observability"])


class LLMCallOut(BaseModel):
    id: uuid.UUID
    lab: str
    operation: str
    provider: str
    model: str
    role: str
    total_tokens: int
    latency_ms: float
    cost_usd: float | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("/projects/{project_id}/llm/calls", response_model=list[LLMCallOut])
async def list_calls(
    project_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    lab: str | None = None,
    limit: int = 100,
) -> list[LLMCall]:
    await _require_project(session, principal, project_id)
    stmt = select(LLMCall).where(LLMCall.project_id == project_id)
    if lab:
        stmt = stmt.where(LLMCall.lab == lab)
    rows = (
        await session.execute(stmt.order_by(LLMCall.created_at.desc()).limit(limit))
    ).scalars().all()
    return list(rows)


@router.get("/projects/{project_id}/llm/summary")
async def summary(
    project_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    rows = (
        await session.execute(
            select(
                LLMCall.lab,
                func.count().label("calls"),
                func.coalesce(func.sum(LLMCall.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(LLMCall.cost_usd), 0.0).label("cost"),
                func.coalesce(func.avg(LLMCall.latency_ms), 0.0).label("avg_latency"),
            )
            .where(LLMCall.project_id == project_id)
            .group_by(LLMCall.lab)
            .order_by(func.count().desc())
        )
    ).all()
    by_lab = [
        {"lab": r.lab or "unknown", "calls": int(r.calls), "tokens": int(r.tokens),
         "cost_usd": round(float(r.cost), 6), "avg_latency_ms": round(float(r.avg_latency), 1)}
        for r in rows
    ]
    return {
        "by_lab": by_lab,
        "totals": {
            "calls": sum(x["calls"] for x in by_lab),
            "tokens": sum(x["tokens"] for x in by_lab),
            "cost_usd": round(sum(x["cost_usd"] for x in by_lab), 6),
        },
    }
