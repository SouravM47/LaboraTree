"""Human-in-the-loop gates — the approval inbox that pauses/resumes agent runs.

A gate is a `GateTask` row: a Lab or the agent graph raises one, the run pauses, a human
approves / edits / rejects it here, and the run resumes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import PrincipalDep, SessionDep
from ..projects.models import GateStatus, GateTask, Run

router = APIRouter(prefix="/api/gates", tags=["gates"])


async def create_gate_task(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    title: str,
    description: str = "",
    payload: dict[str, Any] | None = None,
) -> GateTask:
    """Raise a gate (pauses the run pending human approval). Returns the pending GateTask."""
    gate = GateTask(
        org_id=org_id,
        run_id=run_id,
        title=title,
        description=description,
        payload=payload or {},
        status=GateStatus.PENDING,
    )
    session.add(gate)
    await session.flush()
    return gate


class GateOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    title: str
    description: str
    payload: dict[str, Any]
    status: str
    response: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveIn(BaseModel):
    status: GateStatus
    response: dict[str, Any] = {}


@router.get("", response_model=list[GateOut])
async def list_gates(
    principal: PrincipalDep,
    session: SessionDep,
    status: GateStatus | None = None,
) -> list[GateTask]:
    stmt = select(GateTask).where(GateTask.org_id == principal.org_id)
    if status is not None:
        stmt = stmt.where(GateTask.status == status)
    rows = (await session.execute(stmt.order_by(GateTask.created_at.desc()))).scalars().all()
    return list(rows)


@router.post("/{gate_id}/resolve", response_model=GateOut)
async def resolve_gate(
    gate_id: uuid.UUID,
    body: ResolveIn,
    principal: PrincipalDep,
    session: SessionDep,
) -> GateTask:
    gate = await session.get(GateTask, gate_id)
    if gate is None or gate.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="gate not found")
    if gate.status != GateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"gate already {gate.status.value}")
    if body.status == GateStatus.PENDING:
        raise HTTPException(status_code=400, detail="cannot resolve to 'pending'")

    gate.status = body.status
    gate.response = body.response
    gate.resolved_by = principal.user.id
    await session.commit()
    await session.refresh(gate)
    return gate
