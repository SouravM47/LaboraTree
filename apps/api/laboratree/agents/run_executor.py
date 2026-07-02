"""Run executor — turns any registered Component into a tracked, evidence-locked Run.

This is the backbone: it creates a Run row, wires a RunContext (blob storage, a buffered
Evidence sink, the LLM handle, a scratch workdir), executes the component off the event loop,
persists every emitted Evidence record, stores output artifacts, writes the reproducibility
manifest, and updates the Run status. The same path is used by curated-tool runs, Lab pipelines,
and (later) the agent graph's Engineer node.
"""

from __future__ import annotations

import asyncio
import random
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from laboratree_sdk import RunContext
from laboratree_sdk.registry import UnknownComponentError

from ..core.evidence import BufferedEvidenceSink, persist_evidence
from ..core.llm import get_llm
from ..core.registry import REGISTRY
from ..core.repro import DEFAULT_SEED, build_manifest, dataframe_hash
from ..core.storage import get_blob_store
from ..projects.models import Artifact, Run, RunStatus


class RunFailed(RuntimeError):
    def __init__(self, run_id: uuid.UUID, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id


@dataclass
class RunResult:
    run: Run
    outputs: dict[str, Any]
    evidence_count: int


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:
        pass


async def execute_component(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    component_id: str,
    params: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    lab: str = "",
    seed: int = DEFAULT_SEED,
) -> RunResult:
    try:
        component = REGISTRY.create(component_id)
    except UnknownComponentError as exc:
        raise RunFailed(uuid.uuid4(), f"unknown component: {component_id}") from exc

    params = params or {}
    inputs = inputs or {}

    run = Run(
        org_id=org_id,
        project_id=project_id,
        kind="component",
        lab=lab,
        component_id=component_id,
        status=RunStatus.RUNNING,
        params=params,
        repro_manifest={},
    )
    session.add(run)
    await session.flush()  # assign run.id

    sink = BufferedEvidenceSink(run_id=run.id, org_id=org_id)
    data_version = dataframe_hash(inputs.get("dataset")) if "dataset" in inputs else ""

    with tempfile.TemporaryDirectory(prefix=f"run-{run.id}-") as tmp:
        ctx = RunContext(
            run_id=str(run.id),
            org_id=str(org_id),
            params=params,
            inputs=inputs,
            workdir=Path(tmp),
            blobs=get_blob_store(),
            evidence=sink,
            llm=get_llm(),
        )
        _seed_everything(seed)
        try:
            outputs = await asyncio.to_thread(component.run, ctx)
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
            await session.commit()
            raise RunFailed(run.id, run.error) from exc

    count = await persist_evidence(session, sink)
    await _store_dataset_artifact(session, run, outputs, org_id)

    run.status = RunStatus.SUCCEEDED
    run.repro_manifest = build_manifest(
        component=component, data_version=data_version, seed=seed
    )
    await session.commit()
    await session.refresh(run)
    return RunResult(run=run, outputs=outputs, evidence_count=count)


async def _store_dataset_artifact(
    session: AsyncSession, run: Run, outputs: dict[str, Any], org_id: uuid.UUID
) -> None:
    """If a component produced a `dataset` output, persist it as a CSV artifact."""
    df = outputs.get("dataset") if isinstance(outputs, dict) else None
    try:
        import pandas as pd
    except Exception:
        return
    if not isinstance(df, pd.DataFrame):
        return

    key = f"runs/{run.id}/output.csv"
    data = df.to_csv(index=False).encode()
    get_blob_store().put(key, data)
    session.add(
        Artifact(
            org_id=org_id,
            run_id=run.id,
            name="output.csv",
            kind="file",
            storage_key=key,
            mime="text/csv",
            size=len(data),
        )
    )
    await session.flush()
