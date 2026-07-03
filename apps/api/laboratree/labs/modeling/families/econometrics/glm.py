"""Econometric classifiers — Logit and Probit (statsmodels), with pseudo-R² and coefficients."""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import as_metric_dict, classification_metrics, numeric_features

_SEED = 1729


def _binary(y):
    if y.dtype == object or str(y.dtype).startswith("category") or str(y.dtype) == "bool":
        return y.astype("category").cat.codes
    return y


def _params_schema() -> dict:
    return {
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": {"type": "string", "title": "Binary target column"},
            "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
            "test_size": {"type": "number", "default": 0.25},
        },
    }


def _run_glm(ctx: RunContext, family: str, component_id: str) -> dict[str, Any]:
    import statsmodels.api as sm
    from sklearn.model_selection import train_test_split

    df = ctx.inputs["dataset"].dropna()
    target = ctx.params["target"]
    feats = numeric_features(df, target, ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {family}")

    y = _binary(df[target])
    if y.nunique() != 2:
        raise ValueError(f"{family} requires a binary target (got {y.nunique()} classes)")

    X = sm.add_constant(df[feats].astype(float))
    strat = y if y.nunique() > 1 else None
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=ctx.params.get("test_size", 0.25), random_state=_SEED, stratify=strat
    )
    estimator = sm.Logit if family == "logit" else sm.Probit
    res = estimator(ytr, Xtr).fit(disp=0)
    proba = res.predict(Xte)
    pred = (proba >= 0.5).astype(int)

    metrics = as_metric_dict(classification_metrics(yte, pred, proba.to_numpy()))
    metrics["pseudo_r2"] = round(float(res.prsquared), 4)
    coefficients = {str(k): round(float(v), 4) for k, v in res.params.items()}

    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component_id)
    return {"metrics": metrics, "task": "classification", "coefficients": coefficients,
            "n_test": int(len(yte))}


@register
class LogitModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.econometrics.logit",
        name="Logit (logistic regression, statsmodels)",
        summary="Binary logit with pseudo-R² and interpretable coefficients.",
        params_schema=_params_schema(),
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["econometrics", "classification", "regression-family:econometrics"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        return _run_glm(ctx, "logit", self.spec.id)


@register
class ProbitModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.econometrics.probit",
        name="Probit (statsmodels)",
        summary="Binary probit with pseudo-R² and interpretable coefficients.",
        params_schema=_params_schema(),
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["econometrics", "classification", "regression-family:econometrics"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        return _run_glm(ctx, "probit", self.spec.id)
