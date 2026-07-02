"""Experiment orchestration — reproduce-and-explore a paper.

create_experiment: extract dataset references, auto-fetch what it can, store fetched datasets,
reconstruct the pipeline walkthrough, record Evidence, and raise a HITL gate for anything that
must be uploaded by hand. Everything hangs off an anchor Run so gates/evidence are first-class.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....api.gates import create_gate_task
from ....core.evidence import BufferedEvidenceSink, persist_evidence
from ....core.repro import build_manifest, dataframe_hash
from ....core.storage import get_blob_store
from ....papers.models import Experiment, ExperimentStatus, Paper, PaperChunk
from ....projects.models import Dataset, GateTask, Run, RunStatus
from .fetch import DataFetchAgent, FetchResult, extract_dataset_refs
from .walkthrough import build_walkthrough
from .walkthrough.graph import mirror_to_neo4j

CompleteFn = Callable[[str, str], str]


@dataclass
class ExperimentResult:
    experiment: Experiment
    run: Run
    gate: GateTask | None


async def _paper_text(session: AsyncSession, paper: Paper) -> str:
    rows = (
        await session.execute(
            select(PaperChunk).where(PaperChunk.paper_id == paper.id).order_by(PaperChunk.ordinal)
        )
    ).scalars().all()
    return "\n\n".join(c.text for c in rows)


def load_dataset_df(dataset: Dataset):
    import pandas as pd

    data = get_blob_store().get(dataset.storage_key)
    return pd.read_csv(io.BytesIO(data))


async def store_fetched_dataset(
    session: AsyncSession, *, org_id: uuid.UUID, project_id: uuid.UUID, fr: FetchResult
) -> Dataset:
    import pandas as pd

    key = f"experiments/{project_id}/{uuid.uuid4()}/{fr.filename}"
    get_blob_store().put(key, fr.data)
    try:
        df = pd.read_csv(io.BytesIO(fr.data))
        n_rows, n_cols, chash = int(len(df)), int(df.shape[1]), dataframe_hash(df)
    except Exception:
        n_rows = n_cols = None
        chash = ""
    ds = Dataset(
        org_id=org_id,
        project_id=project_id,
        name=fr.ref.name,
        storage_key=key,
        content_hash=chash,
        n_rows=n_rows,
        n_cols=n_cols,
    )
    session.add(ds)
    await session.flush()
    return ds


async def create_experiment(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    paper: Paper,
    complete_fn: CompleteFn | None = None,
) -> ExperimentResult:
    text = await _paper_text(session, paper)
    refs = extract_dataset_refs(text, complete_fn)
    outcome = DataFetchAgent().resolve(refs)

    run = Run(
        org_id=org_id,
        project_id=project_id,
        kind="experiment",
        lab="paper.experiment",
        component_id="paper.experiment",
        status=RunStatus.RUNNING,
        params={"paper_id": str(paper.id)},
        repro_manifest={},
    )
    session.add(run)
    await session.flush()

    fetched_report = []
    for fr in outcome.fetched:
        ds = await store_fetched_dataset(session, org_id=org_id, project_id=project_id, fr=fr)
        fetched_report.append(
            {
                "name": fr.ref.name,
                "filename": fr.filename,
                "dataset_id": str(ds.id),
                "resolver": fr.resolver,
                "source": fr.source,
                "n_rows": ds.n_rows,
                "n_cols": ds.n_cols,
            }
        )
    unresolved = [g.__dict__ for g in outcome.unresolved]

    walkthrough = build_walkthrough(paper.card or {}, complete_fn)

    experiment = Experiment(
        org_id=org_id,
        paper_id=paper.id,
        project_id=project_id,
        status=ExperimentStatus.AWAITING_DATA if unresolved else ExperimentStatus.READY,
        walkthrough=walkthrough,
        fetch_report={"run_id": str(run.id), "fetched": fetched_report, "unresolved": unresolved},
    )
    session.add(experiment)
    await session.flush()

    sink = BufferedEvidenceSink(run_id=run.id, org_id=org_id)
    sink.record(label="datasets_fetched", value=len(fetched_report), kind="metric")
    sink.record(label="datasets_unresolved", value=len(unresolved), kind="metric")
    sink.record(label="walkthrough_nodes", value=len(walkthrough), kind="metric")
    await persist_evidence(session, sink)

    gate: GateTask | None = None
    if unresolved:
        gate = await create_gate_task(
            session,
            org_id=org_id,
            run_id=run.id,
            title="Upload missing datasets",
            description="Some datasets could not be fetched automatically — please upload them.",
            payload={"experiment_id": str(experiment.id), "unresolved": unresolved},
        )
        run.status = RunStatus.AWAITING_GATE
    else:
        run.status = RunStatus.SUCCEEDED
    run.repro_manifest = build_manifest(data_version="")

    await mirror_to_neo4j(experiment.id, org_id, walkthrough)
    await session.commit()
    await session.refresh(experiment)
    return ExperimentResult(experiment=experiment, run=run, gate=gate)
