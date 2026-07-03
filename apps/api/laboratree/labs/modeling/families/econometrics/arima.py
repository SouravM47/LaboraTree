"""ARIMA — classic econometric time-series model (statsmodels)."""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register


@register
class ARIMAModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.econometrics.arima",
        name="ARIMA (statsmodels)",
        summary="Fit an ARIMA(p,d,q) model to a series; reports AIC/BIC and in-sample RMSE.",
        params_schema={
            "type": "object",
            "required": ["value_column"],
            "properties": {
                "value_column": {"type": "string", "title": "Value column"},
                "time_column": {"type": "string", "title": "Time column (optional, for sorting)"},
                "order": {
                    "type": "array", "items": {"type": "integer"},
                    "default": [1, 1, 1], "title": "(p, d, q)",
                },
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["econometrics", "timeseries", "regression-family:econometrics"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import numpy as np
        import pandas as pd
        from statsmodels.tsa.arima.model import ARIMA

        df: pd.DataFrame = ctx.inputs["dataset"]
        col = ctx.params["value_column"]
        tcol = ctx.params.get("time_column")
        if tcol and tcol in df.columns:
            df = df.sort_values(tcol)
        series = df[col].astype(float).dropna().reset_index(drop=True)
        order = tuple(int(x) for x in (ctx.params.get("order") or [1, 1, 1]))[:3]
        if len(order) != 3:
            order = (1, 1, 1)

        res = ARIMA(series, order=order).fit()
        resid = res.resid.dropna()
        rmse = float(np.sqrt((resid**2).mean())) if len(resid) else 0.0
        metrics = {
            "aic": round(float(res.aic), 3),
            "bic": round(float(res.bic), 3),
            "rmse": round(rmse, 4),
        }
        for k, v in metrics.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {"metrics": metrics, "order": list(order), "n_obs": int(len(series))}
