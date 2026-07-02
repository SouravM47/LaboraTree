"""Imputation transforms."""

from __future__ import annotations

from typing import Any

import pandas as pd
from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


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
