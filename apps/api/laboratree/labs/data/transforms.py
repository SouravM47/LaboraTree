"""Reference preprocessing transforms for the Data Lab.

These are *curated tools*: deterministic, registered components an agent can call by id.
They also prove the plug-in/plug-out pattern end to end (registry -> API -> dynamic UI form).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


@register
class DropDuplicates(Component):
    spec = ComponentSpec(
        kind=ComponentKind.TRANSFORM,
        id="transform.drop_duplicates",
        name="Drop duplicate rows",
        summary="Remove duplicate rows, optionally scoped to a subset of columns.",
        params_schema={
            "type": "object",
            "properties": {
                "subset": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Columns subset",
                    "description": "Columns to consider; empty = all columns.",
                },
                "keep": {
                    "type": "string",
                    "enum": ["first", "last"],
                    "default": "first",
                    "title": "Which to keep",
                },
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="dataset", dtype="dataset")],
        tags=["cleaning"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        df: pd.DataFrame = ctx.inputs["dataset"]
        subset = ctx.params.get("subset") or None
        keep = ctx.params.get("keep", "first")
        before = len(df)
        out = df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)
        ctx.emit("rows_removed", before - len(out), kind="metric", component=self.spec.id)
        return {"dataset": out}


@register
class MeanImpute(Component):
    spec = ComponentSpec(
        kind=ComponentKind.TRANSFORM,
        id="transform.mean_impute",
        name="Impute missing (mean)",
        summary="Fill missing numeric values with the column mean.",
        params_schema={
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Columns",
                    "description": "Numeric columns to impute; empty = all numeric columns.",
                }
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="dataset", dtype="dataset")],
        tags=["cleaning", "imputation"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        df: pd.DataFrame = ctx.inputs["dataset"].copy()
        cols = ctx.params.get("columns") or df.select_dtypes("number").columns.tolist()
        filled = 0
        for col in cols:
            missing = int(df[col].isna().sum())
            if missing:
                df[col] = df[col].fillna(df[col].mean())
                filled += missing
        ctx.emit("values_imputed", filled, kind="metric", component=self.spec.id)
        return {"dataset": df}
