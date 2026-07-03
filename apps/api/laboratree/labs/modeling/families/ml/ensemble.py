"""Random Forest — a common baseline in applied papers, auto-detecting task from the target."""

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


def _is_classification(y) -> bool:
    if y.dtype == object or str(y.dtype).startswith("category") or str(y.dtype) == "bool":
        return True
    return y.nunique() <= 10


@register
class RandomForestModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.ml.random_forest",
        name="Random Forest",
        summary="Random-forest model with a train/test split and metrics; auto-detects "
        "classification vs regression.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                "n_estimators": {"type": "integer", "default": 300, "title": "Trees"},
                "max_depth": {"type": "integer", "title": "Max depth (0 = none)"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "classification", "regression", "trees", "regression-family:ml"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.model_selection import train_test_split

        df: pd.DataFrame = ctx.inputs["dataset"].dropna()
        target = ctx.params["target"]
        feats = numeric_features(df, target, ctx.params.get("features"))
        if not feats:
            raise ValueError("no numeric features available for random forest")

        y = df[target]
        classify = _is_classification(y)
        if classify and (y.dtype == object or str(y.dtype).startswith("category")):
            y = y.astype("category").cat.codes
        work = df[feats].assign(**{target: y})

        n = ctx.params.get("n_estimators", 300)
        depth = ctx.params.get("max_depth") or None
        test_size = ctx.params.get("test_size", 0.25)

        if classify:
            stratify = work[target] if work[target].nunique() > 1 else None
            Xtr, Xte, ytr, yte = train_test_split(
                work[feats], work[target], test_size=test_size, random_state=_SEED, stratify=stratify
            )
            model = RandomForestClassifier(n_estimators=n, max_depth=depth, random_state=_SEED)
            model.fit(Xtr, ytr)
            metrics = as_metric_dict(
                classification_metrics(yte, model.predict(Xte), model.predict_proba(Xte))
            )
            task = "classification"
        else:
            Xtr, Xte, ytr, yte = train_test_split(
                work[feats], work[target], test_size=test_size, random_state=_SEED
            )
            model = RandomForestRegressor(n_estimators=n, max_depth=depth, random_state=_SEED)
            model.fit(Xtr, ytr)
            metrics = as_metric_dict(regression_metrics(yte, model.predict(Xte)))
            task = "regression"

        for k, v in metrics.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {"metrics": metrics, "task": task, "n_test": int(len(yte))}
