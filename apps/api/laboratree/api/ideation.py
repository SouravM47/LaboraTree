"""Ideation Lab API — run the Co-Scientist and store the ranked hypotheses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..core.deps import PrincipalDep, SessionDep
from ..core.llm.context import use_llm_context
from ..core.search import search_available, web_search
from ..labs.ideation import llm as ideation_llm
from ..labs.ideation.coscientist import run_ideation
from ..labs.ideation.evidence import brainstorm, gather_evidence
from ..projects.models import IdeationSession, IdeationStatus, Project

router = APIRouter(prefix="/api", tags=["ideation"])


class IdeationIn(BaseModel):
    goal: str = Field(min_length=4)
    n: int = Field(default=4, ge=2, le=8)
    evolve_n: int = Field(default=2, ge=0, le=4)


class EvidenceIn(BaseModel):
    hypothesis: str = Field(min_length=8)
    max_sources: int = Field(default=12, ge=4, le=20)


class BrainstormIn(BaseModel):
    hypothesis: str
    brief: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    question: str = Field(min_length=1)
    history: list[dict[str, str]] = []


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
    with use_llm_context("ideation", "coscientist", project_id=project_id, org_id=principal.org_id):
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


@router.post("/projects/{project_id}/ideation/evidence", status_code=201)
async def evidence_hunt(
    project_id: uuid.UUID, body: EvidenceIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Evidence hunt: search the open web for papers/studies/articles bearing on a conceptual
    hypothesis and return a cited, synthesized brief (summary, stance, findings, insights, the
    variables to test next, and gaps). Runs off the main event loop since search + LLM are sync."""
    import asyncio

    await _require_project(session, principal, project_id)
    if not search_available():
        raise HTTPException(
            status_code=503,
            detail="web search is not configured — set BRAVE_SEARCH_API_KEY or SERPAPI_KEY in .env",
        )

    def _run() -> dict[str, Any]:
        with use_llm_context("ideation", "evidence", project_id=project_id, org_id=principal.org_id):
            return gather_evidence(
                body.hypothesis,
                search_fn=web_search,
                complete_fn=ideation_llm.default_complete,
                max_sources=body.max_sources,
            )

    return await asyncio.to_thread(_run)


@router.post("/projects/{project_id}/ideation/brainstorm")
async def brainstorm_chat(
    project_id: uuid.UUID, body: BrainstormIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Brainstorm a hypothesis with the agent, grounded in an evidence brief + its sources. Stateless:
    the client passes the brief/sources/history back so no session state is needed."""
    import asyncio

    await _require_project(session, principal, project_id)

    def _run() -> dict[str, Any]:
        with use_llm_context("ideation", "brainstorm", project_id=project_id, org_id=principal.org_id):
            return brainstorm(
                body.hypothesis, body.brief, body.sources, body.question, body.history,
                ideation_llm.default_complete,
            )

    return await asyncio.to_thread(_run)
