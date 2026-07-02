"""Collection Lab API — AI-assisted questionnaire design, bias audit, sample size, pilots."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.deps import PrincipalDep, SessionDep
from ..labs.collection import llm as collection_llm
from ..labs.collection.survey import (
    design_questionnaire,
    detect_bias,
    sample_size,
    synthetic_pilot,
)
from ..projects.models import Project

router = APIRouter(prefix="/api", tags=["collection"])


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


class QuestionnaireIn(BaseModel):
    goal: str = Field(min_length=4)
    audience: str = ""
    n: int = Field(default=6, ge=2, le=20)


class BiasIn(BaseModel):
    questions: list[str]


class SampleIn(BaseModel):
    confidence: float = 0.95
    margin: float = Field(default=0.05, gt=0, lt=1)
    population: int | None = None
    proportion: float = Field(default=0.5, gt=0, lt=1)


class PilotIn(BaseModel):
    questions: list[str]
    persona: str
    n: int = Field(default=3, ge=1, le=10)


@router.post("/projects/{project_id}/collection/questionnaire")
async def questionnaire(
    project_id: uuid.UUID, body: QuestionnaireIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    return {"questions": design_questionnaire(
        body.goal, body.audience, body.n, collection_llm.default_complete)}


@router.post("/projects/{project_id}/collection/bias-check")
async def bias_check(
    project_id: uuid.UUID, body: BiasIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    if not body.questions:
        raise HTTPException(status_code=400, detail="no questions provided")
    return {"findings": detect_bias(body.questions, collection_llm.default_complete)}


@router.post("/projects/{project_id}/collection/sample-size")
async def sample(
    project_id: uuid.UUID, body: SampleIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    return sample_size(body.confidence, body.margin, body.population, body.proportion)


@router.post("/projects/{project_id}/collection/pilot")
async def pilot(
    project_id: uuid.UUID, body: PilotIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    if not body.questions:
        raise HTTPException(status_code=400, detail="no questions provided")
    return synthetic_pilot(body.questions, body.persona, body.n, collection_llm.default_complete)
