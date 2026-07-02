"""Cleaning transforms."""

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
