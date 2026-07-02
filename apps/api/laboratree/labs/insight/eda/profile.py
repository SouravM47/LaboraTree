"""EDA profiler — a compact, provenance-locked profile of a dataset."""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


def profile_dataframe(df, *, top_k_corr: int = 10) -> dict[str, Any]:
    import numpy as np

    n_rows = int(len(df))
    columns = []
    for c in df.columns:
        col = df[c]
        missing = int(col.isna().sum())
        columns.append(
            {
                "name": str(c),
                "dtype": str(col.dtype),
                "missing": missing,
                "missing_pct": round(100.0 * missing / n_rows, 2) if n_rows else 0.0,
                "n_unique": int(col.nunique(dropna=True)),
            }
        )

    numeric = df.select_dtypes("number")
    numeric_summary: dict[str, Any] = {}
    if not numeric.empty:
        desc = numeric.describe().round(4)
        numeric_summary = {col: desc[col].to_dict() for col in desc.columns}

    top_correlations = []
    if numeric.shape[1] >= 2:
        corr = numeric.corr(numeric_only=True)
        seen = set()
        pairs = []
        for i, a in enumerate(corr.columns):
            for b in corr.columns[i + 1 :]:
                v = corr.loc[a, b]
                if a != b and not np.isnan(v):
                    pairs.append((abs(float(v)), str(a), str(b), round(float(v), 4)))
        pairs.sort(reverse=True)
        for _, a, b, v in pairs[:top_k_corr]:
            key = (a, b)
            if key in seen:
                continue
            seen.add(key)
            top_correlations.append({"a": a, "b": b, "corr": v})

    return {
        "n_rows": n_rows,
        "n_cols": int(df.shape[1]),
        "total_missing": int(df.isna().sum().sum()),
        "columns": columns,
        "numeric_summary": numeric_summary,
        "top_correlations": top_correlations,
    }


@register
class EDAProfile(Component):
    spec = ComponentSpec(
        kind=ComponentKind.ANALYZER,
        id="analyzer.eda_profile",
        name="EDA Profile",
        summary="Shape, dtypes, missingness, numeric summary, and top correlations.",
        params_schema={
            "type": "object",
            "properties": {
                "top_k_corr": {"type": "integer", "default": 10, "title": "Top correlations"}
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="profile", dtype="profile")],
        tags=["eda", "insight"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        profile = profile_dataframe(
            ctx.inputs["dataset"], top_k_corr=ctx.params.get("top_k_corr", 10)
        )
        ctx.emit("n_rows", profile["n_rows"], kind="metric", component=self.spec.id)
        ctx.emit("n_cols", profile["n_cols"], kind="metric", component=self.spec.id)
        ctx.emit("total_missing", profile["total_missing"], kind="metric", component=self.spec.id)
        return {"profile": profile}
