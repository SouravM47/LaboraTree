"""Classical ML reference models — logistic & linear regression (train/test + metrics).

Each is a self-contained, Evidence-locked node: it splits, fits, predicts, evaluates, and
emits every metric to the ledger — so a Paper-Experiment node run is provably comparable to the
paper's reported numbers.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import (
    as_metric_dict,
    classification_metrics,
    numeric_features,
    regression_metrics,
)

_SEED = 1729


def _split(df, target, features, test_size, stratify=None):
    from sklearn.model_selection import train_test_split

    X = df[features]
    y = df[target]
    return train_test_split(X, y, test_size=test_size, random_state=_SEED, stratify=stratify)


@register
class LogisticRegressionModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.ml.logistic_regression",
        name="Logistic Regression",
        summary="Binary/multiclass classification with a train/test split and metrics.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                "C": {"type": "number", "default": 1.0, "title": "Inverse regularization"},
                "max_iter": {"type": "integer", "default": 1000},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "classification", "regression-family:ml"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import pandas as pd
        from sklearn.linear_model import LogisticRegression

        df: pd.DataFrame = ctx.inputs["dataset"].dropna()
        target = ctx.params["target"]
        feats = numeric_features(df, target, ctx.params.get("features"))
        if not feats:
            raise ValueError("no numeric features available for logistic regression")

        y = df[target]
        if y.dtype == object or str(y.dtype).startswith("category"):
            y = y.astype("category").cat.codes
        work = df[feats].assign(**{target: y})

        stratify = work[target] if work[target].nunique() > 1 else None
        Xtr, Xte, ytr, yte = _split(work, target, feats, ctx.params.get("test_size", 0.25), stratify)
        clf = LogisticRegression(C=ctx.params.get("C", 1.0), max_iter=ctx.params.get("max_iter", 1000))
        clf.fit(Xtr, ytr)
        pred = clf.predict(Xte)
        proba = clf.predict_proba(Xte)
        metrics = as_metric_dict(classification_metrics(yte, pred, proba))

        for k, v in metrics.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {"metrics": metrics, "task": "classification", "n_test": int(len(yte))}


@register
class LinearRegressionModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.ml.linear_regression",
        name="Linear Regression",
        summary="OLS regression with a train/test split and metrics (r2/rmse/mae).",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "regression", "regression-family:ml"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import pandas as pd
        from sklearn.linear_model import LinearRegression

        df: pd.DataFrame = ctx.inputs["dataset"].dropna()
        target = ctx.params["target"]
        feats = numeric_features(df, target, ctx.params.get("features"))
        if not feats:
            raise ValueError("no numeric features available for linear regression")

        Xtr, Xte, ytr, yte = _split(df, target, feats, ctx.params.get("test_size", 0.25))
        reg = LinearRegression()
        reg.fit(Xtr, ytr)
        pred = reg.predict(Xte)
        metrics = as_metric_dict(regression_metrics(yte, pred))

        for k, v in metrics.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {"metrics": metrics, "task": "regression", "n_test": int(len(yte))}
