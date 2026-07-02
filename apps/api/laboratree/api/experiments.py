"""Paper Experiment API — reproduce a paper's pipeline, then fork nodes and compare to the paper."""

from __future__ import annotations

import io
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from ..agents.run_executor import RunFailed, execute_component
from ..core.deps import PrincipalDep, SessionDep
from ..core.repro import dataframe_hash
from ..core.storage import get_blob_store
from ..labs.paper import llm as paper_llm
from ..labs.paper.experiment.service import create_experiment, load_dataset_df
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
    report.setdefault("fetched", []).append(
        {"name": name, "filename": file.filename, "dataset_id": str(ds.id),
         "resolver": "manual_upload", "source": "human", "n_rows": n_rows, "n_cols": n_cols}
    )
    remaining = [u for u in report.get("unresolved", []) if u.get("name", "").lower() != name.lower()]
    report["unresolved"] = remaining
    exp.fetch_report = report  # reassign so JSONB change is detected

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

    component_id = body.component_id or node.get("component_id")
    if not component_id:
        raise HTTPException(status_code=400, detail="node has no runnable component; pass component_id to fork")

    dataset = await session.get(Dataset, body.dataset_id)
    if dataset is None or dataset.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="dataset not found")

    params = {**(node.get("params") or {}), **body.params, "experiment_id": str(exp.id)}
    try:
        result = await execute_component(
            session,
            org_id=principal.org_id,
            project_id=exp.project_id,
            component_id=component_id,
            params={k: v for k, v in params.items() if k != "experiment_id"},
            inputs={"dataset": load_dataset_df(dataset)},
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
        "paper_reported": card.get("results", ""),
    }
