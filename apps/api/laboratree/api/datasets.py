"""Datasets — download the CSV bytes and preview the first rows (org-scoped).

Backs the Experiment Lab's "view / download the generated sample data" affordances.
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..core.deps import PrincipalDep, SessionDep
from ..core.storage import get_blob_store
from ..labs.modeling.viz import (
    FeatureSelectionTrace,
    ModelTrace,
    build_feature_selection,
    build_trace,
)
from ..projects.models import Dataset

router = APIRouter(prefix="/api", tags=["datasets"])


async def _require_dataset(session, principal, dataset_id: uuid.UUID) -> Dataset:
    ds = await session.get(Dataset, dataset_id)
    if ds is None or ds.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="dataset not found")
    return ds


@router.get("/datasets/{dataset_id}/download")
async def download_dataset(
    dataset_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> Response:
    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc
    safe = (ds.name or "dataset").replace('"', "").replace("/", "-")
    filename = safe if safe.lower().endswith(".csv") else f"{safe}.csv"
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class DatasetPreview(BaseModel):
    id: uuid.UUID
    name: str
    columns: list[str]
    rows: list[dict]
    n_rows: int | None
    n_cols: int | None
    synthetic: bool
    truncated: bool


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(
    dataset_id: uuid.UUID, principal: PrincipalDep, session: SessionDep, rows: int = 50
) -> DatasetPreview:
    import pandas as pd

    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc

    n = max(1, min(rows, 500))
    df = pd.read_csv(io.BytesIO(data), nrows=n)
    # to_json handles NaN -> null and numpy scalar types cleanly for JSON.
    rows_data = json.loads(df.to_json(orient="records"))
    truncated = bool(ds.n_rows and ds.n_rows > len(df))
    return DatasetPreview(
        id=ds.id,
        name=ds.name,
        columns=[str(c) for c in df.columns],
        rows=rows_data,
        n_rows=ds.n_rows,
        n_cols=ds.n_cols,
        synthetic=bool(ds.synthetic),
        truncated=truncated,
    )


# ---- staged model-visualization traces --------------------------------------------------------
# The per-family trace logic is a pluggable package: laboratree/labs/modeling/viz (one module per
# family, auto-discovered). These endpoints are thin async wrappers that stream the dataset bytes
# into that registry off the event loop.


class TraceParamsIn(BaseModel):
    params: dict[str, Any] = {}


@router.post("/datasets/{dataset_id}/model-trace", response_model=ModelTrace)
async def model_trace(
    dataset_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    target: str,
    family: str = "trees",
    body: TraceParamsIn | None = None,
) -> ModelTrace:
    """Fit the model family on the REAL data and return a staged, data-specific trace to animate
    (data table -> training view -> per-row testing walkthrough). ``body.params`` are the tunable
    hyperparameters (default to the paper's; the family clamps them) so the user can re-fit live."""
    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc
    try:
        return await asyncio.to_thread(build_trace, data, target, family, body.params if body else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # keep the node usable even if a fit fails
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc


@router.post("/datasets/{dataset_id}/feature-selection", response_model=FeatureSelectionTrace)
async def feature_selection(
    dataset_id: uuid.UUID, principal: PrincipalDep, session: SessionDep, target: str
) -> FeatureSelectionTrace:
    """Run a small BBO-style wrapper feature selection on the real data and return the staged search
    (habitats + fitness per generation) to animate."""
    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc
    try:
        return await asyncio.to_thread(build_feature_selection, data, target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc


class ColProfile(BaseModel):
    name: str
    dtype: str  # "numeric" | "categorical"
    missing: int
    missing_pct: float
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q25: float | None = None
    q50: float | None = None
    q75: float | None = None
    unique: int | None = None
    top: list[dict] | None = None  # [{value, count}]


class DatasetProfile(BaseModel):
    n_rows: int
    n_cols: int
    columns: list[ColProfile]
    correlation: dict | None = None  # {"columns": [...], "matrix": [[...]]}


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
async def profile_dataset(
    dataset_id: uuid.UUID, principal: PrincipalDep, session: SessionDep
) -> DatasetProfile:
    """Simple EDA profile: per-column type, missing %, numeric summary or top categories — powers
    the scrollable EDA node."""
    import pandas as pd

    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc

    df = pd.read_csv(io.BytesIO(data), nrows=5000)
    n = len(df)
    cols: list[ColProfile] = []
    for c in df.columns:
        s = df[c]
        missing = int(s.isna().sum())
        mp = round(100 * missing / n, 1) if n else 0.0
        # numeric with enough distinct values → numeric summary; else treat as categorical
        if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 10:
            cols.append(
                ColProfile(
                    name=str(c), dtype="numeric", missing=missing, missing_pct=mp,
                    mean=round(float(s.mean()), 3), std=round(float(s.std(ddof=0)), 3),
                    min=round(float(s.min()), 3), max=round(float(s.max()), 3),
                    q25=round(float(s.quantile(0.25)), 3), q50=round(float(s.quantile(0.5)), 3),
                    q75=round(float(s.quantile(0.75)), 3),
                )
            )
        else:
            vc = s.value_counts(dropna=True).head(5)
            top = [{"value": str(k), "count": int(v)} for k, v in vc.items()]
            cols.append(
                ColProfile(
                    name=str(c), dtype="categorical", missing=missing, missing_pct=mp,
                    unique=int(s.nunique(dropna=True)), top=top,
                )
            )
    # correlation heatmap over the numeric columns (capped for readability)
    correlation = None
    num_df = df.select_dtypes("number")
    if num_df.shape[1] >= 2:
        keep = list(num_df.columns[:12])
        cm = num_df[keep].corr().round(2).fillna(0)
        correlation = {"columns": [str(c) for c in keep], "matrix": cm.to_numpy().tolist()}

    return DatasetProfile(
        n_rows=int(n), n_cols=int(df.shape[1]), columns=cols, correlation=correlation
    )


class PreprocessPreview(BaseModel):
    op: str
    columns: list[str]
    before: list[dict]
    after: list[dict]
    changed: list[list[str]]  # per-row: which columns changed
    stats: dict[str, dict]  # per numeric column: mean/median/std/min/max (for formulas + fill values)
    summary: str


_PREPROC_OPS = ("impute_mean", "impute_median", "standardize", "minmax")


@router.post("/datasets/{dataset_id}/preprocess-preview", response_model=PreprocessPreview)
async def preprocess_preview(
    dataset_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    op: str = "standardize",
    rows: int = 6,
) -> PreprocessPreview:
    """Show a few sample rows BEFORE and AFTER a preprocessing step, and which cells changed —
    powers the Experiment Lab's animated 'watch the rows transform' preprocess node. Mirrors the
    data-lab transforms (mean/median imputation, z-score / min-max scaling)."""
    import pandas as pd

    if op not in _PREPROC_OPS:
        raise HTTPException(status_code=400, detail=f"unknown op '{op}' (use {_PREPROC_OPS})")

    ds = await _require_dataset(session, principal, dataset_id)
    try:
        data = get_blob_store().get(ds.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=410, detail="dataset bytes missing") from exc

    full = pd.read_csv(io.BytesIO(data), nrows=5000)
    num_cols = full.select_dtypes("number").columns.tolist()
    n = max(1, min(rows, 20))

    # For imputation, prefer sample rows that actually contain missing values (so it's visible).
    if op in ("impute_mean", "impute_median") and num_cols:
        with_na = full[full[num_cols].isna().any(axis=1)]
        sample = (with_na if len(with_na) else full).head(n)
    else:
        sample = full.head(n)

    before = sample.copy()
    after = sample.copy()

    if op == "impute_mean":
        filled = 0
        for c in num_cols:
            filled += int(after[c].isna().sum())
            after[c] = after[c].fillna(full[c].mean())
        summary = f"filled {filled} missing value(s) with each column's average"
    elif op == "impute_median":
        filled = 0
        for c in num_cols:
            filled += int(after[c].isna().sum())
            after[c] = after[c].fillna(full[c].median())
        summary = f"filled {filled} missing value(s) with each column's middle value"
    elif op == "standardize":
        for c in num_cols:
            mu = full[c].mean()
            sd = full[c].std(ddof=0)
            after[c] = (after[c] - mu) / (sd if sd else 1.0)
        summary = "rescaled every numeric column to mean 0 and spread 1 (z-score)"
    else:  # minmax
        for c in num_cols:
            lo, hi = full[c].min(), full[c].max()
            after[c] = (after[c] - lo) / ((hi - lo) or 1.0)
        summary = "squeezed every numeric column into the 0..1 range"

    for c in num_cols:
        after[c] = after[c].round(3)

    cols = [str(c) for c in sample.columns]
    before_rows = json.loads(before.to_json(orient="records"))
    after_rows = json.loads(after.to_json(orient="records"))
    changed = [
        [c for c in cols if b.get(c) != a.get(c)]
        for b, a in zip(before_rows, after_rows, strict=False)
    ]
    # per-column stats so the UI can show the fill value and the scaling formula with real numbers
    stats = {
        str(c): {
            "mean": round(float(full[c].mean()), 3),
            "median": round(float(full[c].median()), 3),
            "std": round(float(full[c].std(ddof=0)), 3),
            "min": round(float(full[c].min()), 3),
            "max": round(float(full[c].max()), 3),
        }
        for c in num_cols
    }
    return PreprocessPreview(
        op=op, columns=cols, before=before_rows, after=after_rows, changed=changed,
        stats=stats, summary=summary,
    )
