"""Runs — execute a registered component on an inline dataset, then inspect run + evidence.

This is the HTTP surface of the run executor: it proves the full trust loop (registry ->
execution -> Evidence Ledger -> reproducibility manifest) without needing dataset upload yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..agents.run_executor import RunFailed, execute_component
from ..core.deps import PrincipalDep, SessionDep
from ..projects.models import Evidence, Project, Run

router = APIRouter(prefix="/api", tags=["runs"])


class RunComponentIn(BaseModel):
    component_id: str
    params: dict[str, Any] = {}
    dataset: list[dict[str, Any]] | None = None  # inline rows -> DataFrame input


class RunOut(BaseModel):
    id: uuid.UUID
    status: str
    lab: str
    component_id: str | None
    error: str | None
    repro_manifest: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceOut(BaseModel):
    id: uuid.UUID
    label: str
    kind: str
    value: Any
    meta: dict[str, Any]

    model_config = {"from_attributes": True}


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _preview(outputs: dict[str, Any]) -> dict[str, Any]:
    import pandas as pd

    out: dict[str, Any] = {}
    for key, val in (outputs or {}).items():
        if isinstance(val, pd.DataFrame):
            out[key] = {
                "columns": list(val.columns),
                "n_rows": int(len(val)),
                "rows": val.head(20).to_dict(orient="records"),
            }
        else:
            try:
                import json

                json.dumps(val)
                out[key] = val
            except (TypeError, ValueError):
                out[key] = str(val)
    return out


@router.post("/projects/{project_id}/runs", status_code=201)
async def run_component(
    project_id: uuid.UUID,
    body: RunComponentIn,
    principal: PrincipalDep,
    session: SessionDep,
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)

    inputs: dict[str, Any] = {}
    if body.dataset is not None:
        import pandas as pd

        inputs["dataset"] = pd.DataFrame(body.dataset)

    try:
        result = await execute_component(
            session,
            org_id=principal.org_id,
            project_id=project_id,
            component_id=body.component_id,
            params=body.params,
            inputs=inputs,
        )
    except RunFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "run": RunOut.model_validate(result.run).model_dump(),
        "evidence_count": result.evidence_count,
        "preview": _preview(result.outputs),
    }


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, principal: PrincipalDep, session: SessionDep) -> Run:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/evidence", response_model=list[EvidenceOut])
async def run_evidence(
    run_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> list[EvidenceOut]:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    rows = (
        await session.execute(
            select(Evidence).where(Evidence.run_id == run_id).order_by(Evidence.created_at)
        )
    ).scalars().all()
    # unwrap {"v": ...}
    return [
        EvidenceOut(id=r.id, label=r.label, kind=r.kind, value=r.value.get("v"), meta=r.meta)
        for r in rows
    ]
