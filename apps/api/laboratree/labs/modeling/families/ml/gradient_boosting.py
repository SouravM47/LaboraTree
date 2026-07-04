"""Gradient-boosted trees — a faithful, registry-native stand-in for XGBoost/LightGBM/CatBoost.

Uses scikit-learn's HistGradientBoosting (already a dependency) so a Paper-Experiment node whose
paper used a boosted-tree classifier (very common) has a real, Evidence-locked component to run and
compare against — instead of dead-ending because "XGBoost" wasn't in the registry. Auto-detects
classification vs regression from the target so it works across papers.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import (
    as_metric_dict,
    classification_metrics,
    numeric_features,
    regression_metrics,
    sample_predictions,
)

_SEED = 1729


def _is_classification(y) -> bool:
    """Treat object/categorical or low-cardinality integer targets as classification."""
    if y.dtype == object or str(y.dtype).startswith("category") or str(y.dtype) == "bool":
        return True
    return y.nunique() <= 10


@register
class GradientBoostingModel(Component):
    spec = ComponentSpec(
        kind=ComponentKind.MODEL,
        id="model.ml.gradient_boosting",
        name="Gradient Boosting (trees)",
        summary="Boosted-tree model (XGBoost-family stand-in) with a train/test split and metrics; "
        "auto-detects classification vs regression.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                "learning_rate": {"type": "number", "default": 0.1, "title": "Learning rate"},
                "max_iter": {"type": "integer", "default": 200, "title": "Boosting rounds"},
                "max_depth": {"type": "integer", "default": 6, "title": "Max depth"},
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "classification", "regression", "trees", "boosting", "regression-family:ml"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        import pandas as pd
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            HistGradientBoostingRegressor,
        )
        from sklearn.model_selection import train_test_split

        df: pd.DataFrame = ctx.inputs["dataset"].dropna()
        target = ctx.params["target"]
        feats = numeric_features(df, target, ctx.params.get("features"))
        if not feats:
            raise ValueError("no numeric features available for gradient boosting")

        y = df[target]
        classify = _is_classification(y)
        if classify and (y.dtype == object or str(y.dtype).startswith("category")):
            y = y.astype("category").cat.codes
        work = df[feats].assign(**{target: y})

        lr = ctx.params.get("learning_rate", 0.1)
        max_iter = ctx.params.get("max_iter", 200)
        max_depth = ctx.params.get("max_depth", 6)
        test_size = ctx.params.get("test_size", 0.25)

        if classify:
            stratify = work[target] if work[target].nunique() > 1 else None
            Xtr, Xte, ytr, yte = train_test_split(
                work[feats], work[target], test_size=test_size, random_state=_SEED, stratify=stratify
            )
            model = HistGradientBoostingClassifier(
                learning_rate=lr, max_iter=max_iter, max_depth=max_depth, random_state=_SEED
            )
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            proba = model.predict_proba(Xte)
            metrics = as_metric_dict(classification_metrics(yte, pred, proba))
            task = "classification"
        else:
            Xtr, Xte, ytr, yte = train_test_split(
                work[feats], work[target], test_size=test_size, random_state=_SEED
            )
            model = HistGradientBoostingRegressor(
                learning_rate=lr, max_iter=max_iter, max_depth=max_depth, random_state=_SEED
            )
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            metrics = as_metric_dict(regression_metrics(yte, pred))
            task = "regression"

        for k, v in metrics.items():
            ctx.emit(k, v, kind="metric", component=self.spec.id)
        return {
            "metrics": metrics,
            "task": task,
            "n_test": int(len(yte)),
            "predictions": sample_predictions(yte, pred, task),
        }
