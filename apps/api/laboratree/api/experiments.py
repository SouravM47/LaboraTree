"""Paper Experiment API — reproduce a paper's pipeline, then fork nodes and compare to the paper."""

from __future__ import annotations

import io
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from ..agents.run_executor import RunFailed, execute_component
from ..core.deps import PrincipalDep, SessionDep
from ..core.llm.context import use_llm_context
from ..core.repro import dataframe_hash
from ..core.storage import get_blob_store
from ..labs.paper import llm as paper_llm
from ..labs.paper.experiment.demo import generate_demo_dataset
from ..labs.paper.experiment.service import _paper_text, create_experiment, load_dataset_df
from ..papers.models import Experiment, ExperimentStatus, Paper
from ..projects.models import Dataset, GateStatus, GateTask

router = APIRouter(prefix="/api", tags=["experiments"])


class NodeRunIn(BaseModel):
    dataset_id: uuid.UUID
    component_id: str | None = None       # override the node's component to "fork"
    params: dict[str, Any] = {}


async def _require_experiment(session, principal, experiment_id: uuid.UUID) -> Experiment:
    exp = await session.get(Experiment, experiment_id)
    if exp is None or exp.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="experiment not found")
    return exp


def _detail(exp: Experiment) -> dict[str, Any]:
    return {
        "id": str(exp.id),
        "paper_id": str(exp.paper_id),
        "status": exp.status.value,
        "walkthrough": exp.walkthrough,
        "fetch_report": exp.fetch_report,
    }


@router.post("/papers/{paper_id}/experiment", status_code=201)
async def start_experiment(
    paper_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="paper not found")
    if not paper.card:
        raise HTTPException(status_code=409, detail="generate the Paper Card first")

    with use_llm_context("paper", "experiment_fetch", project_id=paper.project_id,
                         org_id=principal.org_id):
        result = await create_experiment(
            session,
            org_id=principal.org_id,
            project_id=paper.project_id,
            paper=paper,
            complete_fn=paper_llm.default_complete,
        )
    detail = _detail(result.experiment)
    detail["gate_id"] = str(result.gate.id) if result.gate else None
    return detail


@router.get("/papers/{paper_id}/experiment")
async def latest_experiment(
    paper_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    """Return the most recent experiment for this paper so revisiting the Experiment Lab restores
    the pipeline, fetched/generated datasets, and gate — nothing is lost between visits."""
    exp = (
        await session.execute(
            select(Experiment)
            .where(Experiment.paper_id == paper_id, Experiment.org_id == principal.org_id)
            .order_by(Experiment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if exp is None:
        raise HTTPException(status_code=404, detail="no experiment yet")
    return _detail(exp)


@router.post("/experiments/{experiment_id}/demo-data", status_code=201)
async def demo_data(
    experiment_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    n_rows: int = 60,
) -> dict[str, Any]:
    """Synthesize a realistic demo dataset from the paper's variables so the user can always proceed."""
    exp = await _require_experiment(session, principal, experiment_id)
    paper = await session.get(Paper, exp.paper_id)
    if paper is None or paper.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="paper not found")

    import pandas as pd

    text = await _paper_text(session, paper)
    with use_llm_context("paper", "demo_data", project_id=exp.project_id, org_id=principal.org_id):
        demo = generate_demo_dataset(text, paper.card or {}, n_rows, paper_llm.default_complete)
    df = pd.DataFrame(demo["records"], columns=demo["columns"] or None)
    if df.empty:
        raise HTTPException(status_code=400, detail="demo-data generation produced no rows")

    key = f"experiments/{exp.project_id}/{uuid.uuid4()}/demo.csv"
    data = df.to_csv(index=False).encode()
    get_blob_store().put(key, data)
    ds = Dataset(
        org_id=principal.org_id, project_id=exp.project_id, name="demo (synthetic)",
        storage_key=key, content_hash=dataframe_hash(df),
        n_rows=int(len(df)), n_cols=int(df.shape[1]), synthetic=True,
    )
    session.add(ds)
    await session.flush()

    report = dict(exp.fetch_report)
    # Build a NEW list (not append to the shared one) so SQLAlchemy sees a real change on the
    # JSONB column — a shallow-copied nested list would be mutated in place and go unpersisted.
    report["fetched"] = [
        *(report.get("fetched") or []),
        {
            "name": "demo (synthetic)", "filename": "demo.csv", "dataset_id": str(ds.id),
            "resolver": "demo_llm", "source": "llm", "n_rows": int(len(df)),
            "n_cols": int(df.shape[1]), "synthetic": True,
        },
    ]
    exp.fetch_report = report
    flag_modified(exp, "fetch_report")
    exp.status = ExperimentStatus.READY
    await session.commit()
    await session.refresh(exp)
    return {**_detail(exp), "caveat": demo["caveat"]}


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    return _detail(await _require_experiment(session, principal, experiment_id))


@router.post("/experiments/{experiment_id}/data", status_code=201)
async def upload_experiment_data(
    experiment_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    name: str,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Manually provide a dataset the auto-fetch agent could not retrieve (resolves the HITL gate)."""
    exp = await _require_experiment(session, principal, experiment_id)
    data = await file.read()

    import pandas as pd

    key = f"experiments/{exp.project_id}/{uuid.uuid4()}/{file.filename}"
    get_blob_store().put(key, data)
    try:
        df = pd.read_csv(io.BytesIO(data))
        n_rows, n_cols, chash = int(len(df)), int(df.shape[1]), dataframe_hash(df)
    except Exception:
        n_rows = n_cols = None
        chash = ""
    ds = Dataset(org_id=principal.org_id, project_id=exp.project_id, name=name,
                 storage_key=key, content_hash=chash, n_rows=n_rows, n_cols=n_cols)
    session.add(ds)
    await session.flush()

    report = dict(exp.fetch_report)
    report["fetched"] = [
        *(report.get("fetched") or []),
        {"name": name, "filename": file.filename, "dataset_id": str(ds.id),
         "resolver": "manual_upload", "source": "human", "n_rows": n_rows, "n_cols": n_cols},
    ]
    remaining = [u for u in report.get("unresolved", []) if u.get("name", "").lower() != name.lower()]
    report["unresolved"] = remaining
    exp.fetch_report = report  # reassign + flag so the JSONB change is detected
    flag_modified(exp, "fetch_report")

    if not remaining:
        exp.status = ExperimentStatus.READY
        run_id = report.get("run_id")
        if run_id:
            gate = (
                await session.execute(
                    select(GateTask).where(
                        GateTask.run_id == uuid.UUID(run_id), GateTask.status == GateStatus.PENDING
                    )
                )
            ).scalar_one_or_none()
            if gate is not None:
                gate.status = GateStatus.APPROVED
                gate.response = {"resolved_by": "manual_upload"}

    await session.commit()
    await session.refresh(exp)
    return _detail(exp)


@router.post("/experiments/{experiment_id}/nodes/{node_id}/run", status_code=201)
async def run_node(
    experiment_id: uuid.UUID,
    node_id: str,
    body: NodeRunIn,
    principal: PrincipalDep,
    session: SessionDep,
) -> dict[str, Any]:
    exp = await _require_experiment(session, principal, experiment_id)
    node = next((n for n in exp.walkthrough if n.get("id") == node_id), None)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")

    # Prefer the explicit fork, then the paper's mapped model, then a stand-in for unknown models
    # (SVM, k-NN, neural nets, custom) so a node is never a dead end.
    component_id = body.component_id or node.get("component_id") or node.get("suggested_component")
    if not component_id:
        raise HTTPException(status_code=400, detail="node has no runnable component; pass component_id to fork")
    stand_in = not node.get("component_id") and not body.component_id

    dataset = await session.get(Dataset, body.dataset_id)
    if dataset is None or dataset.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="dataset not found")

    params = {**(node.get("params") or {}), **body.params, "experiment_id": str(exp.id)}

    df = load_dataset_df(dataset)
    # Resolve the target to a REAL column — demo/uploaded CSVs may name it differently than the
    # Paper Card (e.g. card says 'class' but the demo column is 'classification'). Prefer an exact
    # (case-insensitive) match, then a loose match, then fall back to the last column (the usual
    # target convention). Without this the model raises KeyError and the whole run "fails".
    tgt = params.get("target")
    if tgt is not None and tgt not in df.columns and len(df.columns):
        low = str(tgt).lower()
        match = next((c for c in df.columns if str(c).lower() == low), None)
        if match is None:
            match = next(
                (c for c in df.columns if low in str(c).lower() or str(c).lower() in low), None
            )
        params["target"] = match or df.columns[-1]

    try:
        result = await execute_component(
            session,
            org_id=principal.org_id,
            project_id=exp.project_id,
            component_id=component_id,
            params={k: v for k, v in params.items() if k != "experiment_id"},
            inputs={"dataset": df},
            lab="paper.experiment",
        )
    except RunFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    card = {}
    paper = await session.get(Paper, exp.paper_id)
    if paper is not None:
        card = paper.card or {}
    return {
        "run_id": str(result.run.id),
        "component_id": component_id,
        "forked": bool(body.component_id and body.component_id != node.get("component_id")),
        "metrics": result.outputs.get("metrics", {}),
        "task": result.outputs.get("task", ""),
        "predictions": result.outputs.get("predictions", []),
        "paper_reported": card.get("results", ""),
        "synthetic": bool(dataset.synthetic),
        "stand_in": stand_in,
    }
