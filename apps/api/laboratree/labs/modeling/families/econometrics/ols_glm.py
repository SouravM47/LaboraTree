"""Econometric regressions — OLS with inference (p-values) and Poisson GLM for counts.

These complement logit/probit/arima: OLS is THE workhorse of empirical economics (coefficients +
significance, not just prediction), and Poisson covers count outcomes (visits, accidents, patents).
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import as_metric_dict, numeric_features, regression_metrics, sample_predictions

_SEED = 1729


def _params_schema(target_title: str) -> dict:
    return {
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string", "title": target_title},
            "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
            "test_size": {"type": "number", "default": 0.25},
        },
    }


def _prep(ctx: RunContext, name: str):
    import pandas as pd
    import statsmodels.api as sm
    from sklearn.model_selection import train_test_split

    df = ctx.inputs["dataset"].dropna()
    target = ctx.params["target"]
    if not pd.api.types.is_numeric_dtype(df[target]):
        raise ValueError(
            f"{name} needs a numeric target, but '{target}' is categorical — try logit/probit."
        )
    feats = numeric_features(df, target, ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {name}")
    X = sm.add_constant(df[feats].astype(float))
    return train_test_split(
        X, df[target].astype(float), test_size=ctx.params.get("test_size", 0.25), random_state=_SEED
    )


def _finish(ctx: RunContext, component_id: str, res, yte, pred) -> dict[str, Any]:
    metrics = as_metric_dict(regression_metrics(yte, pred))
    coefficients = {str(k): round(float(v), 4) for k, v in res.params.items()}
    pvalues = {str(k): round(float(v), 4) for k, v in res.pvalues.items()}
    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component_id)
    return {
        "metrics": metrics, "task": "regression", "n_test": int(len(yte)),
        "coefficients": coefficients, "p_values": pvalues,
        "predictions": sample_predictions(yte, pred, "regression"),
    }


@register
class OLSModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.econometrics.ols",
        name="OLS (statsmodels)",
        summary="Ordinary least squares with coefficients, p-values and fit metrics — the "
        "econometrics workhorse for 'does X significantly affect Y?'.",
        params_schema=_params_schema("Numeric outcome column"),
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["econometrics", "regression", "regression-family:econometrics"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import statsmodels.api as sm

        Xtr, Xte, ytr, yte = _prep(ctx, self.spec.name)
        res = sm.OLS(ytr, Xtr).fit()
        out = _finish(ctx, self.spec.id, res, yte, res.predict(Xte))
        out["metrics"]["r2_train"] = round(float(res.rsquared), 4)
        return out


@register
class PoissonModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.econometrics.poisson",
        name="Poisson GLM (statsmodels)",
        summary="Count-outcome regression (visits, claims, patents) with coefficients and p-values.",
        params_schema=_params_schema("Count outcome column (non-negative)"),
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["econometrics", "regression", "counts", "regression-family:econometrics"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import statsmodels.api as sm

        Xtr, Xte, ytr, yte = _prep(ctx, self.spec.name)
        if (ytr < 0).any():
            raise ValueError("Poisson needs a non-negative count target.")
        res = sm.GLM(ytr, Xtr, family=sm.families.Poisson()).fit()
        return _finish(ctx, self.spec.id, res, yte, res.predict(Xte))
