"""Artifacts — list a run's artifacts and download their bytes from the BlobStore."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from ..core.deps import PrincipalDep, SessionDep
from ..core.storage import get_blob_store
from ..projects.models import Artifact, Run

router = APIRouter(prefix="/api", tags=["artifacts"])


class ArtifactOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    name: str
    kind: str
    mime: str
    size: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactOut])
async def list_run_artifacts(
    run_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> list[Artifact]:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    rows = (
        await session.execute(select(Artifact).where(Artifact.run_id == run_id))
    ).scalars().all()
    return list(rows)


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> Response:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="artifact not found")
    try:
        data = get_blob_store().get(artifact.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="artifact bytes missing") from exc
    return Response(
        content=data,
        media_type=artifact.mime,
        headers={"Content-Disposition": f'attachment; filename="{artifact.name}"'},
    )
