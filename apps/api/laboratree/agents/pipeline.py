"""Cross-Lab pipeline executor — run a sequence of components end to end.

The `dataset` output of each step feeds the next step's input, so you can chain e.g.
clean -> impute -> leakage-audit -> model, every step producing its own tracked Run + Evidence.
Non-dataset steps (charts, analyzers) pass the current dataset through unchanged.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .run_executor import RunFailed, execute_component


def _preview(outputs: dict[str, Any]) -> dict[str, Any]:
    import pandas as pd

    out: dict[str, Any] = {}
    for key, val in (outputs or {}).items():
        if isinstance(val, pd.DataFrame):
            out[key] = {"columns": list(val.columns), "n_rows": int(len(val)),
                        "rows": val.head(10).to_dict(orient="records")}
        else:
            try:
                import json

                json.dumps(val)
                out[key] = val
            except (TypeError, ValueError):
                out[key] = str(val)
    return out


async def run_pipeline(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    steps: list[dict[str, Any]],
    dataset_records: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    import pandas as pd

    df: pd.DataFrame | None = pd.DataFrame(dataset_records) if dataset_records else None
    results: list[dict[str, Any]] = []

    for step in steps:
        cid = step["component_id"]
        inputs = {"dataset": df} if df is not None else {}
        try:
            result = await execute_component(
                session, org_id=org_id, project_id=project_id,
                component_id=cid, params=step.get("params", {}), inputs=inputs, lab="pipeline",
            )
        except RunFailed as exc:
            results.append({"component_id": cid, "status": "failed", "error": str(exc)})
            break

        out = result.outputs
        if isinstance(out, dict) and isinstance(out.get("dataset"), pd.DataFrame):
            df = out["dataset"]
        results.append({
            "component_id": cid,
            "run_id": str(result.run.id),
            "status": "succeeded",
            "evidence_count": result.evidence_count,
            "preview": _preview(out),
        })

    return {
        "steps": results,
        "n_rows_final": int(len(df)) if df is not None else 0,
        "ok": all(s["status"] == "succeeded" for s in results),
    }
