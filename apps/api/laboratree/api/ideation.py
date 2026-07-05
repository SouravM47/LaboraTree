"""Ideation Lab API — run the Co-Scientist and store the ranked hypotheses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..agents.run_executor import RunFailed, execute_component
from ..core.cache import cache_key, cached_json
from ..core.config import settings
from ..core.deps import PrincipalDep, SessionDep
from ..core.llm.context import use_llm_context
from ..core.ratelimit import rate_limited
from ..core.registry import REGISTRY
from ..core.search import research_available, research_search, search_available, web_search
from ..core.storage import get_blob_store
from ..labs.ideation import llm as ideation_llm
from ..labs.ideation.auto_experiment import (
    detect_task,
    plan_experiment,
    profile_dataset,
    rank_results,
    summarize_results,
)
from ..core.repro import dataframe_hash
from ..labs.ideation.coscientist import run_ideation
from ..labs.ideation.data_hunt import hunt_datasets
from ..labs.ideation.evidence import brainstorm, gather_evidence
from ..labs.ideation.master_dataset import build_master
from ..projects.models import Dataset, IdeationSession, IdeationStatus, Project

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


class DataHuntIn(BaseModel):
    hypothesis: str = Field(min_length=8)
    variables: list[str] = []
    max_candidates: int = Field(default=10, ge=4, le=20)


class BuildDatasetIn(BaseModel):
    candidates: list[dict[str, Any]]          # from the data-hunt result
    name: str = "master (web)"


class PushPapersIn(BaseModel):
    sources: list[dict[str, Any]]             # [{title, url}] from an evidence brief
    max_papers: int = Field(default=8, ge=1, le=15)


def _safe_filename(title: str) -> str:
    import re

    slug = re.sub(r"[^A-Za-z0-9]+", "_", (title or "paper")).strip("_")[:80]
    return (slug or "paper") + ".pdf"


class AutoExperimentIn(BaseModel):
    dataset_id: uuid.UUID
    target: str
    hypothesis: str = ""


def _download_bytes(url: str) -> bytes | None:
    """Size-capped, SSRF-safe GET for the master-dataset / paper-PDF builders (redirects re-validated)."""
    from ..core.net import safe_fetch

    return safe_fetch(url, user_agent="Laboratree/0.1 (dataset builder)")


def _step_summary(kind: str, outputs: dict[str, Any] | None) -> dict[str, Any]:
    """Compact, JSON-safe summary of a pipeline component's outputs (drops the DataFrame etc.)."""
    outputs = outputs or {}
    if kind == "eda":
        p = outputs.get("profile") or {}
        return {k: p.get(k) for k in ("n_rows", "n_cols", "total_missing") if k in p}
    if kind == "leakage":
        return {"findings": len(outputs.get("findings") or [])}
    if kind == "preprocess":
        ds = outputs.get("dataset")
        shape = [int(ds.shape[0]), int(ds.shape[1])] if ds is not None else None
        return {"shape": shape}
    if kind == "red_team":
        return {k: outputs.get(k) for k in ("verdict", "base_metric", "robustness_drop") if k in outputs}
    return {k: v for k, v in outputs.items() if isinstance(v, (int, float, str, bool))}


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


def _evidence_context(brief: dict[str, Any]) -> str:
    """Condense an evidence brief into a grounding prompt for the Co-Scientist generation agent."""
    parts = [str(brief.get("summary") or "")]
    vs = brief.get("variables_to_test") or []
    if vs:
        parts.append("Key measurable variables: " + ", ".join(
            (v.get("name", "") if isinstance(v, dict) else str(v)) for v in vs[:12]))
    kf = brief.get("key_findings") or []
    if kf:
        parts.append("Findings: " + "; ".join(
            (f.get("finding", "") if isinstance(f, dict) else str(f)) for f in kf[:5]))
    gaps = brief.get("gaps") or []
    if gaps:
        parts.append("Open gaps to target: " + "; ".join(str(g) for g in gaps[:4]))
    return "\n".join(p for p in parts if p)


@router.post("/projects/{project_id}/ideation/grounded", status_code=201,
             dependencies=[rate_limited("grounded", limit=10)])
async def grounded_ideation(
    project_id: uuid.UUID, body: IdeationIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """The unified Co-Scientist: FIRST hunt the evidence for the goal, THEN generate + tournament
    hypotheses GROUNDED in that real evidence (not blind priors) — tying Evidence Hunt into the
    Co-Scientist. Returns the ranked session plus the evidence brief it was grounded in."""
    import asyncio

    await _require_project(session, principal, project_id)
    if not research_available():
        raise HTTPException(
            status_code=503,
            detail="evidence search is disabled — enable OpenAlex or set a web-search key in .env",
        )

    def _hunt() -> dict[str, Any]:
        with use_llm_context("ideation", "grounded", project_id=project_id, org_id=principal.org_id):
            return gather_evidence(
                body.goal, search_fn=research_search, complete_fn=ideation_llm.default_complete,
                max_sources=8,
            )

    # reuse the cached evidence brief (same key as the evidence endpoint) so re-running the
    # Co-Scientist on a goal doesn't re-pay for the search + synthesis every time
    ev_key = cache_key("evidence", project_id, body.goal.strip().lower(), 8)
    ev = await cached_json(ev_key, settings.ideation_cache_ttl_s, lambda: asyncio.to_thread(_hunt))

    def _tournament() -> dict[str, Any]:
        with use_llm_context("ideation", "grounded", project_id=project_id, org_id=principal.org_id):
            context = _evidence_context(ev["brief"])
            return run_ideation(
                body.goal, ideation_llm.default_complete,
                n=body.n, evolve_n=body.evolve_n, context=context,
            )

    result = await asyncio.to_thread(_tournament)
    record = IdeationSession(
        org_id=principal.org_id, project_id=project_id, goal=body.goal,
        status=IdeationStatus.COMPLETE, hypotheses=result["hypotheses"],
        meta_review=result["meta_review"],
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": str(record.id), "goal": record.goal, "status": record.status.value,
        "hypotheses": record.hypotheses, "meta_review": record.meta_review,
        "created_at": record.created_at.isoformat(), "evidence": ev,
    }


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


@router.post("/projects/{project_id}/ideation/evidence", status_code=201,
             dependencies=[rate_limited("evidence", limit=20)])
async def evidence_hunt(
    project_id: uuid.UUID, body: EvidenceIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Evidence hunt: search real academic databases (OpenAlex — free journals/studies) plus the open
    web for evidence bearing on a conceptual hypothesis, and return a cited, synthesized brief
    (summary, stance, findings, insights, the variables to test next, gaps). Cached per hypothesis."""
    import asyncio

    await _require_project(session, principal, project_id)
    if not research_available():
        raise HTTPException(
            status_code=503,
            detail="evidence search is disabled — enable OpenAlex or set a web-search key in .env",
        )

    def _run() -> dict[str, Any]:
        with use_llm_context("ideation", "evidence", project_id=project_id, org_id=principal.org_id):
            return gather_evidence(
                body.hypothesis,
                search_fn=research_search,
                complete_fn=ideation_llm.default_complete,
                max_sources=body.max_sources,
            )

    key = cache_key("evidence", project_id, body.hypothesis.strip().lower(), body.max_sources)
    return await cached_json(key, settings.ideation_cache_ttl_s, lambda: asyncio.to_thread(_run))


@router.post("/projects/{project_id}/ideation/brainstorm",
             dependencies=[rate_limited("brainstorm", limit=40)])
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


@router.post("/projects/{project_id}/ideation/data-hunt", status_code=201,
             dependencies=[rate_limited("data_hunt", limit=20)])
async def data_hunt(
    project_id: uuid.UUID, body: DataHuntIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Find candidate datasets on the open web to test a hypothesis — ranked, annotated with why each
    is relevant and whether it's directly downloadable. Cached per hypothesis + variables."""
    import asyncio

    await _require_project(session, principal, project_id)
    if not search_available():
        raise HTTPException(
            status_code=503,
            detail="web search is not configured — set BRAVE_SEARCH_API_KEY or SERPAPI_KEY in .env",
        )

    def _run() -> dict[str, Any]:
        with use_llm_context("ideation", "data_hunt", project_id=project_id, org_id=principal.org_id):
            return hunt_datasets(
                body.hypothesis, body.variables,
                search_fn=web_search, complete_fn=ideation_llm.default_complete,
                max_candidates=body.max_candidates,
            )

    key = cache_key("data_hunt", project_id, body.hypothesis.strip().lower(),
                    sorted(body.variables), body.max_candidates)
    return await cached_json(key, settings.ideation_cache_ttl_s, lambda: asyncio.to_thread(_run))


@router.post("/projects/{project_id}/ideation/resolve-oa",
             dependencies=[rate_limited("resolve_oa", limit=15)])
async def resolve_oa(
    project_id: uuid.UUID, body: PushPapersIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """For each evidence source, resolve a directly-downloadable OPEN-ACCESS PDF (or null if
    paywalled) — so the UI can let the user DECIDE per paper: download it, or send it to the Paper
    Lab. No side effects; nothing is imported here."""
    import asyncio

    from ..core.search import open_access_pdf

    await _require_project(session, principal, project_id)

    def _run() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for src in body.sources[: body.max_papers]:
            url = str(src.get("url") or "")
            out.append({
                "title": str(src.get("title") or url)[:200],
                "url": url,
                "pdf_url": (open_access_pdf(url) if url else None),
            })
        return out

    return {"sources": await asyncio.to_thread(_run)}


@router.post("/projects/{project_id}/ideation/push-to-paper-lab", status_code=201,
             dependencies=[rate_limited("import_papers", limit=8)])
async def push_to_paper_lab(
    project_id: uuid.UUID, body: PushPapersIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Download the OPEN-ACCESS full text of the evidence sources and ingest them into the Paper Lab
    (extract → chunk → embed) so each becomes a chattable Paper with its own Paper Card. Paywalled
    sources are skipped honestly with a reason — we only pull genuinely free PDFs."""
    import asyncio

    from ..core.search import open_access_pdf
    from ..labs.paper import llm as paper_llm
    from ..labs.paper.ingest import ingest_paper
    from ..papers.models import Paper, PaperStatus

    await _require_project(session, principal, project_id)
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    with use_llm_context("ideation", "import_papers", project_id=project_id, org_id=principal.org_id):
        for src in body.sources[: body.max_papers]:
            url = str(src.get("url") or "")
            title = str(src.get("title") or url)[:200]
            pdf_url = await asyncio.to_thread(open_access_pdf, url)
            if not pdf_url:
                skipped.append({"title": title, "reason": "no open-access PDF (paywalled)"})
                continue
            data = await asyncio.to_thread(_download_bytes, pdf_url)
            if not data or not data[:5].startswith(b"%PDF"):
                skipped.append({"title": title, "reason": "could not download a valid PDF"})
                continue

            filename = _safe_filename(title)
            paper = Paper(org_id=principal.org_id, project_id=project_id, title=title,
                          filename=filename, storage_key="", status=PaperStatus.UPLOADED)
            session.add(paper)
            await session.flush()
            key = f"papers/{paper.id}/{filename}"
            get_blob_store().put(key, data)
            paper.storage_key = key
            try:
                await ingest_paper(session, paper, data, embed_fn=paper_llm.default_embed)
            except Exception as exc:
                paper.status = PaperStatus.FAILED
                await session.commit()
                skipped.append({"title": title, "reason": f"ingest failed: {exc}"})
                continue
            await session.commit()
            await session.refresh(paper)
            imported.append({"title": title, "paper_id": str(paper.id), "filename": filename})

    return {"imported": imported, "skipped": skipped}


@router.post("/projects/{project_id}/ideation/build-dataset", status_code=201,
             dependencies=[rate_limited("build_dataset", limit=10)])
async def build_dataset(
    project_id: uuid.UUID, body: BuildDatasetIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Download the data-hunt's direct-download candidates and consolidate them into ONE master
    dataset (schema-compatible sources concatenated; others kept as separate tables), persisted as a
    project Dataset the auto-experiment can run on. Honest — never fabricates a join."""
    import asyncio

    await _require_project(session, principal, project_id)
    if not body.candidates:
        raise HTTPException(status_code=422, detail="no candidate datasets to build from")

    result = await asyncio.to_thread(build_master, body.candidates, _download_bytes)
    master = result.get("master")
    if master is None:
        raise HTTPException(status_code=422, detail=result.get("note", "no usable data downloaded"))

    key = f"ideation/{project_id}/{uuid.uuid4()}/master.csv"
    get_blob_store().put(key, master.to_csv(index=False).encode())
    ds = Dataset(
        org_id=principal.org_id, project_id=project_id, name=body.name, storage_key=key,
        content_hash=dataframe_hash(master), n_rows=int(len(master)), n_cols=int(master.shape[1]),
    )
    session.add(ds)
    await session.flush()
    await session.commit()
    await session.refresh(ds)
    return {
        "dataset_id": str(ds.id), "name": ds.name,
        "n_rows": ds.n_rows, "n_cols": ds.n_cols,
        "columns": [str(c) for c in master.columns],
        "tables": result["tables"], "note": result["note"],
    }


@router.post("/projects/{project_id}/ideation/auto-experiment", status_code=201,
             dependencies=[rate_limited("auto_experiment", limit=10)])
async def auto_experiment(
    project_id: uuid.UUID, body: AutoExperimentIn, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """The deep agent's auto-experiment: profile a dataset, let the LLM pick the task-appropriate
    models (skill selection), run each as a REAL Evidence-locked component, then read the metrics and
    write a grounded verdict. Every model run is a tracked Run; every LLM decision is observable."""
    import asyncio
    import io

    import pandas as pd

    await _require_project(session, principal, project_id)
    ds = await session.get(Dataset, body.dataset_id)
    if ds is None or ds.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="dataset not found")
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc
    try:
        df = pd.read_csv(io.BytesIO(data), nrows=5000)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"could not parse dataset as CSV: {exc}") from exc
    if df.empty or body.target not in df.columns:
        raise HTTPException(status_code=400, detail=f"target '{body.target}' not in dataset columns")

    task = detect_task(df, body.target)
    profile = profile_dataset(df, body.target)
    available = sorted(s.id for s in REGISTRY.specs() if s.id.startswith("model.ml."))
    pipeline: list[dict[str, Any]] = []

    async def _step(kind: str, component_id: str, params: dict, dataset) -> Any:
        """Run one pipeline component as a tracked, Evidence-locked Run; record it in `pipeline`."""
        try:
            res = await execute_component(
                session, org_id=principal.org_id, project_id=project_id,
                component_id=component_id, params=params,
                inputs={"dataset": dataset}, lab="ideation.auto_experiment",
            )
        except RunFailed as exc:
            pipeline.append({"step": kind, "component": component_id, "error": str(exc)})
            return None
        pipeline.append({
            "step": kind, "component": component_id, "run_id": str(res.run.id),
            "evidence_count": res.evidence_count, "outputs": _step_summary(kind, res.outputs),
        })
        return res

    with use_llm_context("ideation", "auto_experiment", project_id=project_id, org_id=principal.org_id):
        # 1) EDA  2) leakage check (a trust differentiator) — both on the raw data
        await _step("eda", "analyzer.eda_profile", {}, df)
        leak = await _step("leakage", "analyzer.leakage_sentinel", {"target": body.target}, df)
        leak_findings = (leak.outputs.get("findings") if leak else []) or []

        # 3) preprocess — actually run mean-impute and feed the CLEANED frame forward
        pre = await _step("preprocess", "transform.mean_impute", {}, df)
        model_df = pre.outputs.get("dataset", df) if pre else df

        # 4) model selection — the LLM picks, each runs as a real Evidence-locked component
        plan = await asyncio.to_thread(
            plan_experiment, profile, body.hypothesis, task, available, ideation_llm.default_complete
        )
        results: list[dict[str, Any]] = []
        for cid in plan["models"]:
            res = await _step("model", cid, {"target": body.target}, model_df)
            results.append({
                "component": cid,
                "metrics": (res.outputs.get("metrics", {}) if res else {}),
                "run_id": (str(res.run.id) if res else None),
            })
        ranked = rank_results(results, task)

        # 5) red-team the winning model (a trust differentiator)
        redteam = None
        if ranked and ranked[0].get("metrics"):
            rt = await _step("red_team", "critic.red_team", {"target": body.target}, model_df)
            redteam = _step_summary("red_team", rt.outputs) if rt else None

        # 6) grounded verdict — factoring in leakage + robustness
        notes = f"Leakage findings: {len(leak_findings)}."
        if redteam:
            notes += f" Red-team verdict: {redteam.get('verdict')}, robustness_drop={redteam.get('robustness_drop')}."
        summary = await asyncio.to_thread(
            summarize_results, body.hypothesis, task, [r for r in results if r.get("metrics")],
            ideation_llm.default_complete, notes,
        )

    return {
        "task": task, "profile": profile, "plan": plan, "pipeline": pipeline,
        "results": ranked, "leakage": leak_findings, "redteam": redteam, "summary": summary,
    }
