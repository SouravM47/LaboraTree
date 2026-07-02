"""Ideation Lab API — run the Co-Scientist and store the ranked hypotheses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..core.deps import PrincipalDep, SessionDep
from ..labs.ideation import llm as ideation_llm
from ..labs.ideation.coscientist import run_ideation
from ..projects.models import IdeationSession, IdeationStatus, Project

router = APIRouter(prefix="/api", tags=["ideation"])


class IdeationIn(BaseModel):
    goal: str = Field(min_length=4)
    n: int = Field(default=4, ge=2, le=8)
    evolve_n: int = Field(default=2, ge=0, le=4)


class SessionOut(BaseModel):
    id: uuid.UUID
    goal: str
    status: str
    hypotheses: list[dict[str, Any]]
    meta_review: str
    created_at: datetime

    model_config = {"from_attributes": True}


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post("/projects/{project_id}/ideation", response_model=SessionOut, status_code=201)
async def run(
    project_id: uuid.UUID, body: IdeationIn, principal: PrincipalDep, session: SessionDep
) -> IdeationSession:
    await _require_project(session, principal, project_id)
    result = run_ideation(
        body.goal, ideation_llm.default_complete, n=body.n, evolve_n=body.evolve_n
    )
    record = IdeationSession(
        org_id=principal.org_id,
        project_id=project_id,
        goal=body.goal,
        status=IdeationStatus.COMPLETE,
        hypotheses=result["hypotheses"],
        meta_review=result["meta_review"],
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.get("/projects/{project_id}/ideation", response_model=list[SessionOut])
async def list_sessions(
    project_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> list[IdeationSession]:
    await _require_project(session, principal, project_id)
    rows = (
        await session.execute(
            select(IdeationSession)
            .where(IdeationSession.project_id == project_id,
                   IdeationSession.org_id == principal.org_id)
            .order_by(IdeationSession.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.get("/ideation/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> IdeationSession:
    rec = await session.get(IdeationSession, session_id)
    if rec is None or rec.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="session not found")
    return rec
