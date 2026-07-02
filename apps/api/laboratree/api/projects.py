"""Projects — always scoped to the caller's active organization."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..core.deps import Principal, PrincipalDep, SessionDep, require_role
from ..projects.models import Project
from ..tenancy.models import Role

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreateIn(BaseModel):
    name: str
    description: str = ""


@router.get("", response_model=list[ProjectOut])
async def list_projects(principal: PrincipalDep, session: SessionDep) -> list[Project]:
    rows = (
        await session.execute(
            select(Project).where(Project.org_id == principal.org_id).order_by(Project.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreateIn,
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_role(Role.ANALYST))],
) -> Project:
    project = Project(
        org_id=principal.org_id,
        name=body.name,
        description=body.description,
        created_by=principal.user.id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project
