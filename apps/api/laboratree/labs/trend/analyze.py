"""Trend components — additive decomposition + naive causal impact (dependency-free)."""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


@register
class TrendDecompose(Component):
    spec = ComponentSpec(
        kind=ComponentKind.ANALYZER,
        id="analyzer.trend_decompose",
        name="Trend decomposition",
        summary="Additive decomposition of a series into trend, seasonal, and residual.",
        params_schema={
            "type": "object",
            "required": ["value_column"],
            "properties": {
                "value_column": {"type": "string", "title": "Value column"},
                "time_column": {"type": "string", "title": "Time column (optional, for sorting)"},
                "period": {"type": "integer", "title": "Seasonal period", "default": 12},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="decomposition", dtype="series")],
        tags=["trend", "timeseries"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import pandas as pd

        df: pd.DataFrame = ctx.inputs["dataset"]
        col = ctx.params["value_column"]
        tcol = ctx.params.get("time_column")
        if tcol and tcol in df.columns:
            df = df.sort_values(tcol)
        s = df[col].astype(float).reset_index(drop=True).dropna()
        n = len(s)
        period = max(2, min(int(ctx.params.get("period", 12)), max(2, n // 2)))

        trend = s.rolling(window=period, center=True, min_periods=1).mean()
        detrended = s - trend
        seasonal = pd.Series(0.0, index=s.index)
        for p in range(period):
            idx = s.index[s.index % period == p]
            seasonal.loc[idx] = detrended.loc[idx].mean()
        seasonal = seasonal - seasonal.mean()
        resid = s - trend - seasonal

        var_detr = float(detrended.var()) or 1.0
        strength = max(0.0, min(1.0, 1.0 - float(resid.var()) / var_detr))
        direction = "up" if float(trend.iloc[-1]) >= float(trend.iloc[0]) else "down"

        ctx.emit("trend_direction", direction, kind="metric", component=self.spec.id)
        ctx.emit("seasonality_strength", round(strength, 4), kind="metric", component=self.spec.id)
        return {
            "decomposition": {
                "original": [round(v, 4) for v in s.tolist()],
                "trend": [round(v, 4) for v in trend.tolist()],
                "seasonal": [round(v, 4) for v in seasonal.tolist()],
                "resid": [round(v, 4) for v in resid.tolist()],
            },
            "summary": {"period": period, "direction": direction,
                        "seasonality_strength": round(strength, 4)},
        }


@register
class CausalImpact(Component):
    spec = ComponentSpec(
        kind=ComponentKind.ANALYZER,
        id="analyzer.causal_impact",
        name="Causal impact (before/after)",
        summary="Estimate an intervention's effect vs a linear-trend counterfactual.",
        params_schema={
            "type": "object",
            "required": ["value_column", "intervention_index"],
            "properties": {
                "value_column": {"type": "string"},
                "intervention_index": {"type": "integer", "title": "Row where intervention starts"},
                "time_column": {"type": "string"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="impact", dtype="metrics")],
        tags=["trend", "causal", "timeseries"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import numpy as np
        import pandas as pd

        df: pd.DataFrame = ctx.inputs["dataset"]
        col = ctx.params["value_column"]
        tcol = ctx.params.get("time_column")
        if tcol and tcol in df.columns:
            df = df.sort_values(tcol)
        s = df[col].astype(float).reset_index(drop=True).dropna()
        idx = int(ctx.params["intervention_index"])
        if not (1 <= idx <= len(s) - 1):
            raise ValueError("intervention_index must be within the series (not at the ends)")

        pre, post = s[:idx], s[idx:]
        coef = np.polyfit(np.arange(len(pre)), pre.to_numpy(), 1)
        cf = np.polyval(coef, np.arange(len(pre), len(s)))
        cf_mean = float(cf.mean())
        post_mean = float(post.mean())
        abs_effect = post_mean - cf_mean
        rel = (100.0 * abs_effect / cf_mean) if cf_mean else 0.0

        impact = {
            "pre_mean": round(float(pre.mean()), 4),
            "post_mean": round(post_mean, 4),
            "counterfactual_mean": round(cf_mean, 4),
            "absolute_effect": round(abs_effect, 4),
            "relative_effect_pct": round(rel, 2),
            "n_pre": int(len(pre)),
            "n_post": int(len(post)),
        }
        for k, v in impact.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {"impact": impact}
