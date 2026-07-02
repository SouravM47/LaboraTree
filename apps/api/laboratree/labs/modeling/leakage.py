"""Leakage Sentinel — audits a modelling frame for the leakage patterns that produce the
inflated, irreproducible results documented across the ML-reproducibility literature.

Checks:
  * target leakage      — a feature equals / is a near-perfect proxy for the target
  * perfect predictor   — a feature functionally determines the target (100% purity, not an id)
  * train/test contamination — identical rows appear in both splits
  * temporal leakage    — training data is dated at/after the test period
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

Finding = dict[str, Any]


def audit_leakage(
    df: Any,
    target: str,
    *,
    feature_cols: list[str] | None = None,
    split_column: str | None = None,
    time_column: str | None = None,
    corr_threshold: float = 0.999,
) -> list[Finding]:
    import numpy as np
    import pandas as pd

    if target not in df.columns:
        raise ValueError(f"target column {target!r} not in dataframe")

    features = feature_cols or [
        c for c in df.columns if c not in {target, split_column, time_column} and c is not None
    ]
    y = df[target]
    n = len(df)
    findings: list[Finding] = []

    for col in features:
        s = df[col]
        # exact duplicate of the target
        if s.equals(y):
            findings.append(_f("target_leakage", "high", col,
                               f"'{col}' is identical to target '{target}'"))
            continue
        # near-perfect numeric correlation
        if pd.api.types.is_numeric_dtype(s) and pd.api.types.is_numeric_dtype(y):
            if s.nunique() > 1 and y.nunique() > 1:
                corr = float(np.corrcoef(s.fillna(s.mean()), y.fillna(y.mean()))[0, 1])
                if abs(corr) >= corr_threshold:
                    findings.append(_f("target_leakage", "high", col,
                                       f"|corr('{col}', '{target}')| = {abs(corr):.4f}"))
                    continue
        # functional dependency: feature perfectly determines target and isn't a row id
        distinct = s.nunique(dropna=False)
        if 1 < distinct < n:
            purity = df.groupby(col, observed=True)[target].nunique(dropna=False)
            if (purity <= 1).all():
                findings.append(_f("perfect_predictor", "medium", col,
                                   f"'{col}' functionally determines '{target}' (100% purity)"))

    if split_column and split_column in df.columns:
        findings.extend(_contamination(df, split_column, target))
        if time_column and time_column in df.columns:
            findings.extend(_temporal(df, split_column, time_column))

    return findings


def _f(check: str, severity: str, column: str | None, detail: str) -> Finding:
    return {"check": check, "severity": severity, "column": column, "detail": detail}


def _contamination(df: Any, split_column: str, target: str) -> list[Finding]:
    cols = [c for c in df.columns if c != split_column]
    groups = {str(k): g[cols] for k, g in df.groupby(split_column, observed=True)}
    if len(groups) < 2:
        return []
    names = list(groups)
    findings: list[Finding] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = groups[names[i]], groups[names[j]]
            merged = a.merge(b, how="inner")
            if len(merged) > 0:
                findings.append(_f("train_test_contamination", "high", None,
                                   f"{len(merged)} identical rows shared by "
                                   f"splits '{names[i]}' and '{names[j]}'"))
    return findings


def _temporal(df: Any, split_column: str, time_column: str) -> list[Finding]:
    import pandas as pd

    t = pd.to_datetime(df[time_column], errors="coerce")
    frame = df.assign(_t=t)
    by = {str(k): g["_t"] for k, g in frame.groupby(split_column, observed=True)}
    if not {"train", "test"}.issubset({k.lower() for k in by}):
        return []
    lower = {k.lower(): v for k, v in by.items()}
    train_max, test_min = lower["train"].max(), lower["test"].min()
    if pd.notna(train_max) and pd.notna(test_min) and train_max >= test_min:
        return [_f("temporal_leakage", "high", time_column,
                   f"train max ({train_max}) >= test min ({test_min})")]
    return []


@register
class LeakageSentinel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.ANALYZER,
        id="analyzer.leakage_sentinel",
        name="Leakage Sentinel",
        summary="Audit a modelling frame for target, train/test, and temporal leakage.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "split_column": {"type": "string", "title": "Split column (train/test)"},
                "time_column": {"type": "string", "title": "Time column"},
                "corr_threshold": {"type": "number", "default": 0.999},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="findings", dtype="findings")],
        tags=["leakage", "trust", "modeling"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        findings = audit_leakage(
            ctx.inputs["dataset"],
            target=ctx.params["target"],
            split_column=ctx.params.get("split_column"),
            time_column=ctx.params.get("time_column"),
            corr_threshold=ctx.params.get("corr_threshold", 0.999),
        )
        ctx.emit("leakage_findings", len(findings), kind="metric", component=self.spec.id)
        for i, f in enumerate(findings):
            ctx.emit(f"leakage[{i}]", f, kind="claim", component=self.spec.id, severity=f["severity"])
        return {"findings": findings}
