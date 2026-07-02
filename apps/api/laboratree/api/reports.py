"""Report Card API — assemble a project's Evidence-locked results into a branded HTML report."""

from __future__ import annotations

import base64
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..core.config import REPO_ROOT
from ..core.deps import PrincipalDep, SessionDep
from ..core.evidence import BufferedEvidenceSink, persist_evidence
from ..core.repro import build_manifest
from ..core.storage import get_blob_store
from ..labs.intelligence.report import compute_trust_score, render_report_html
from ..projects.models import Artifact, Evidence, Project, Run, RunStatus

router = APIRouter(prefix="/api", tags=["reports"])

HTML_MIME = "text/html"


def _logo_b64() -> str | None:
    for candidate in ("apps/web/public/logo.png", "logo/IMG_5652.PNG", "logo/logo.PNG"):
        path = REPO_ROOT / candidate
        if path.exists():
            try:
                return base64.b64encode(path.read_bytes()).decode()
            except OSError:
                continue
    return None


@router.post("/projects/{project_id}/report", status_code=201)
async def generate_report(
    project_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> dict[str, Any]:
    project = await session.get(Project, project_id)
    if project is None or project.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="project not found")

    runs = (
        await session.execute(
            select(Run).where(Run.project_id == project_id, Run.org_id == principal.org_id)
            .order_by(Run.created_at.desc()).limit(50)
        )
    ).scalars().all()
    run_dicts = [
        {"id": r.id, "lab": r.lab, "component_id": r.component_id,
         "status": r.status.value, "repro_manifest": r.repro_manifest}
        for r in runs
    ]

    ev_by_run: dict[str, list[dict[str, Any]]] = {}
    if runs:
        rows = (
            await session.execute(
                select(Evidence).where(Evidence.run_id.in_([r.id for r in runs]))
            )
        ).scalars().all()
        for e in rows:
            ev_by_run.setdefault(str(e.run_id), []).append(
                {"label": e.label, "kind": e.kind, "value": (e.value or {}).get("v"), "meta": e.meta}
            )

    trust = compute_trust_score(run_dicts, ev_by_run)
    document = render_report_html(project.name, run_dicts, ev_by_run, trust, logo_b64=_logo_b64())

    report_run = Run(
        org_id=principal.org_id, project_id=project_id, kind="report", lab="intelligence",
        component_id="intelligence.report_card", status=RunStatus.SUCCEEDED,
        params={}, repro_manifest=build_manifest(),
    )
    session.add(report_run)
    await session.flush()

    key = f"runs/{report_run.id}/report.html"
    data = document.encode()
    get_blob_store().put(key, data)
    artifact = Artifact(
        org_id=principal.org_id, run_id=report_run.id, name="report.html",
        kind="report", storage_key=key, mime=HTML_MIME, size=len(data),
    )
    session.add(artifact)
    await session.flush()

    sink = BufferedEvidenceSink(run_id=report_run.id, org_id=principal.org_id)
    sink.record(label="trust_score", value=trust["score"], kind="metric")
    await persist_evidence(session, sink)
    await session.commit()

    return {
        "run_id": str(report_run.id),
        "artifact_id": str(artifact.id),
        "download_url": f"/api/artifacts/{artifact.id}/download",
        "trust": trust,
        "project": project.name,
    }
