"""Paper Lab (Study) API — upload, Paper Card, explain-simpler, and chat-with-paper."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from ..core.deps import Principal, PrincipalDep, SessionDep, require_role
from ..tenancy.models import Role
from ..core.llm.context import use_llm_context
from ..core.storage import get_blob_store
from ..labs.paper import llm as paper_llm
from ..labs.paper.card import generate_card
from ..labs.paper.ingest import ingest_paper
from ..labs.paper.rag import answer as rag_answer
from ..labs.paper.rag import retrieve
from ..labs.paper.simplify import simplify as simplify_text
from ..papers.models import Paper, PaperChunk, PaperStatus
from ..projects.models import Project

router = APIRouter(prefix="/api", tags=["papers"])


class PaperOut(BaseModel):
    id: uuid.UUID
    title: str
    filename: str
    status: str
    n_chunks: int
    card: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class SimplifyIn(BaseModel):
    field: str | None = None       # a Paper Card field to simplify
    text: str | None = None        # or arbitrary text
    level: int = 2


class ChatIn(BaseModel):
    question: str


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


async def _require_paper(session, principal, paper_id: uuid.UUID) -> Paper:
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="paper not found")
    return paper


@router.post("/projects/{project_id}/papers", response_model=PaperOut, status_code=201)
async def upload_paper(
    project_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    file: UploadFile = File(...),
) -> Paper:
    await _require_project(session, principal, project_id)
    data = await file.read()

    paper = Paper(
        org_id=principal.org_id,
        project_id=project_id,
        title=(file.filename or "paper"),
        filename=file.filename or "paper.pdf",
        storage_key="",
        status=PaperStatus.UPLOADED,
    )
    session.add(paper)
    await session.flush()

    key = f"papers/{paper.id}/{paper.filename}"
    get_blob_store().put(key, data)
    paper.storage_key = key

    try:
        await ingest_paper(session, paper, data, embed_fn=paper_llm.default_embed)
    except Exception as exc:
        paper.status = PaperStatus.FAILED
        await session.commit()
        raise HTTPException(status_code=400, detail=f"ingest failed: {exc}") from exc

    await session.commit()
    await session.refresh(paper)
    return paper


@router.get("/projects/{project_id}/papers", response_model=list[PaperOut])
async def list_papers(
    project_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> list[Paper]:
    await _require_project(session, principal, project_id)
    rows = (
        await session.execute(
            select(Paper).where(Paper.project_id == project_id, Paper.org_id == principal.org_id)
            .order_by(Paper.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.get("/papers/{paper_id}", response_model=PaperOut)
async def get_paper(paper_id: uuid.UUID, principal: PrincipalDep, session: SessionDep) -> Paper:
    return await _require_paper(session, principal, paper_id)


@router.delete("/papers/{paper_id}", status_code=204)
async def delete_paper(
    paper_id: uuid.UUID,
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_role(Role.ANALYST))],
) -> None:
    """Delete a paper and its chunks + experiments (DB-level ON DELETE CASCADE). Analyst+ only."""
    paper = await _require_paper(session, principal, paper_id)
    await session.delete(paper)
    await session.commit()


async def _paper_text(session, paper: Paper) -> str:
    rows = (
        await session.execute(
            select(PaperChunk).where(PaperChunk.paper_id == paper.id).order_by(PaperChunk.ordinal)
        )
    ).scalars().all()
    return "\n\n".join(c.text for c in rows)


@router.post("/papers/{paper_id}/card", response_model=PaperOut)
async def make_card(
    paper_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    regenerate: bool = False,
) -> Paper:
    paper = await _require_paper(session, principal, paper_id)
    if paper.card and not regenerate:
        return paper
    text = await _paper_text(session, paper)
    with use_llm_context("paper", "card", project_id=paper.project_id, org_id=principal.org_id):
        paper.card = generate_card(text, complete_fn=paper_llm.default_complete)
    paper.status = PaperStatus.CARDED
    await session.commit()
    await session.refresh(paper)
    return paper


@router.post("/papers/{paper_id}/simplify")
async def simplify(
    paper_id: uuid.UUID, body: SimplifyIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    paper = await _require_paper(session, principal, paper_id)
    source = body.text
    if source is None and body.field:
        source = str(paper.card.get(body.field, ""))
    if not source:
        raise HTTPException(status_code=400, detail="nothing to simplify (give field or text)")

    with use_llm_context("paper", "simplify", project_id=paper.project_id, org_id=principal.org_id):
        result = simplify_text(source, body.level, complete_fn=paper_llm.default_complete)

    # cache per field+level
    key = body.field or "_text"
    cache = dict(paper.simplifications)
    cache.setdefault(key, {})[str(body.level)] = result
    paper.simplifications = cache
    await session.commit()
    return {"field": key, "level": body.level, "simplified": result}


@router.post("/papers/{paper_id}/chat")
async def chat(
    paper_id: uuid.UUID, body: ChatIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    paper = await _require_paper(session, principal, paper_id)
    with use_llm_context("paper", "chat", project_id=paper.project_id, org_id=principal.org_id):
        passages = await retrieve(
            session,
            paper_id=paper.id,
            org_id=principal.org_id,
            query=body.question,
            embed_fn=paper_llm.default_embed,
        )
        return rag_answer(body.question, passages, complete_fn=paper_llm.default_complete)
