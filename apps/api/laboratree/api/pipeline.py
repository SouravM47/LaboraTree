"""Pipeline API — run a composed sequence of components across Labs on one dataset."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agents.pipeline import run_pipeline
from ..core.deps import PrincipalDep, SessionDep
from ..projects.models import Project

router = APIRouter(prefix="/api", tags=["pipeline"])


class Step(BaseModel):
    component_id: str
    params: dict[str, Any] = {}


class PipelineRunIn(BaseModel):
    steps: list[Step]
    dataset: list[dict[str, Any]] | None = None


@router.post("/projects/{project_id}/pipeline/run", status_code=201)
async def run(
    project_id: uuid.UUID, body: PipelineRunIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    if not body.steps:
        raise HTTPException(status_code=400, detail="pipeline has no steps")

    return await run_pipeline(
        session,
        org_id=principal.org_id,
        project_id=project_id,
        steps=[s.model_dump() for s in body.steps],
        dataset_records=body.dataset,
    )
