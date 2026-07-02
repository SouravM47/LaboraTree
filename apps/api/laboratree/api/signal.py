"""Signal Lab API — upload a raw mix of files, get one consolidated master workbook.

Runs the full trust loop: creates a Run, consolidates, stores the workbook as an Artifact,
records Evidence (provenance-locked counts), and writes a reproducibility manifest.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select

from ..core.deps import PrincipalDep, SessionDep
from ..core.evidence import BufferedEvidenceSink, persist_evidence
from ..core.repro import build_manifest, sha256_bytes
from ..core.storage import get_blob_store
from ..labs.signal.consolidate import consolidate
from ..projects.models import Artifact, Project, Run, RunStatus

router = APIRouter(prefix="/api", tags=["signal"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _require_project(session, principal, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post("/projects/{project_id}/signal/consolidate", status_code=201)
async def consolidate_files(
    project_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    await _require_project(session, principal, project_id)
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")

    payloads: list[tuple[str, bytes]] = [(f.filename or "file", await f.read()) for f in files]

    run = Run(
        org_id=principal.org_id,
        project_id=project_id,
        kind="signal",
        lab="signal",
        component_id="signal.consolidate",
        status=RunStatus.RUNNING,
        params={"n_files": len(payloads)},
        repro_manifest={},
    )
    session.add(run)
    await session.flush()

    try:
        result = consolidate(payloads)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = f"{type(exc).__name__}: {exc}"
        await session.commit()
        raise HTTPException(status_code=400, detail=run.error) from exc

    key = f"runs/{run.id}/master.xlsx"
    get_blob_store().put(key, result.workbook)
    artifact = Artifact(
        org_id=principal.org_id,
        run_id=run.id,
        name="master.xlsx",
        kind="workbook",
        storage_key=key,
        mime=XLSX_MIME,
        size=len(result.workbook),
    )
    session.add(artifact)
    await session.flush()

    sink = BufferedEvidenceSink(run_id=run.id, org_id=principal.org_id)
    sink.record(label="source_files", value=len(result.sources), kind="metric")
    sink.record(label="consolidated_tables", value=result.n_tables, kind="metric")
    sink.record(label="total_rows", value=result.total_rows, kind="metric")
    sink.record(label="text_blocks", value=result.texts, kind="metric")
    if result.errors:
        sink.record(label="extraction_errors", value=result.errors, kind="claim")
    await persist_evidence(session, sink)

    sources_hash = sha256_bytes(b"".join(name.encode() + data for name, data in payloads))
    run.status = RunStatus.SUCCEEDED
    run.repro_manifest = build_manifest(data_version=sources_hash)
    await session.commit()
    await session.refresh(run)

    return {
        "run_id": str(run.id),
        "artifact_id": str(artifact.id),
        "download_url": f"/api/artifacts/{artifact.id}/download",
        "summary": {
            "sources": result.sources,
            "n_tables": result.n_tables,
            "total_rows": result.total_rows,
            "text_blocks": result.texts,
            "sheets": result.sheets,
            "errors": result.errors,
        },
    }
