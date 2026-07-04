"""Classic ML reference models — decision tree, KNN, SVM, naive Bayes, MLP.

One shared fit/eval routine (train/test split -> fit -> metrics -> Evidence emits) parameterised by
an estimator factory, so each Component is a thin spec + factory. All auto-detect classification vs
regression from the target, mirroring gradient_boosting.py.
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
    if y.dtype == object or str(y.dtype).startswith("category") or str(y.dtype) == "bool":
        return True
    return y.nunique() <= 10


def _fit_eval(component: Component, ctx: RunContext, make_estimator) -> dict[str, Any]:
    """Shared train/test/evaluate/emit loop. ``make_estimator(task)`` returns a fitted-able model
    (may be a Pipeline); task is "classification" | "regression"."""
    import pandas as pd
    from sklearn.model_selection import train_test_split

    df: pd.DataFrame = ctx.inputs["dataset"].dropna()
    target = ctx.params["target"]
    feats = numeric_features(df, target, ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {component.spec.name}")

    y = df[target]
    classify = _is_classification(y)
    if classify and (y.dtype == object or str(y.dtype).startswith("category")):
        y = y.astype("category").cat.codes
    task = "classification" if classify else "regression"

    model = make_estimator(task)
    if model is None:
        raise ValueError(
            f"{component.spec.name} supports classification only, but '{target}' looks numeric — "
            "try linear regression or gradient boosting."
        )

    stratify = y if (classify and y.nunique() > 1) else None
    Xtr, Xte, ytr, yte = train_test_split(
        df[feats], y, test_size=ctx.params.get("test_size", 0.25),
        random_state=_SEED, stratify=stratify,
    )
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    if classify:
        proba = model.predict_proba(Xte) if hasattr(model, "predict_proba") else None
        metrics = as_metric_dict(classification_metrics(yte, pred, proba))
    else:
        metrics = as_metric_dict(regression_metrics(yte, pred))

    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component.spec.id)
    return {
        "metrics": metrics,
        "task": task,
        "n_test": int(len(yte)),
        "predictions": sample_predictions(yte, pred, task),
    }


def _spec(cid: str, name: str, summary: str, extra_props: dict | None = None) -> ComponentSpec:
    return ComponentSpec(
        kind=ComponentKind.MODEL,
        id=cid,
        name=name,
        summary=summary + " Auto-detects classification vs regression.",
        params_schema={
            "type": "object",
            "required": ["target"],
            "properties": {
                "target": {"type": "string", "title": "Target column"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "test_size": {"type": "number", "default": 0.25},
                **(extra_props or {}),
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "classification", "regression", "regression-family:ml"],
    )


@register
class DecisionTreeModel(Component):
    spec = _spec(
        "model.ml.decision_tree", "Decision Tree",
        "A single interpretable decision tree (CART) with a train/test split and metrics.",
        {"max_depth": {"type": "integer", "default": 5, "title": "Max depth"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

        depth = ctx.params.get("max_depth", 5)

        def make(task):
            M = DecisionTreeClassifier if task == "classification" else DecisionTreeRegressor
            return M(max_depth=depth, random_state=_SEED)

        return _fit_eval(self, ctx, make)


@register
class KNNModel(Component):
    spec = _spec(
        "model.ml.knn", "K-Nearest Neighbors",
        "Predicts from the k most similar rows (standardized distance).",
        {"n_neighbors": {"type": "integer", "default": 5, "title": "Neighbors (k)"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        k = ctx.params.get("n_neighbors", 5)

        def make(task):
            M = KNeighborsClassifier if task == "classification" else KNeighborsRegressor
            return make_pipeline(StandardScaler(), M(n_neighbors=k))

        return _fit_eval(self, ctx, make)


@register
class SVMModel(Component):
    spec = _spec(
        "model.ml.svm", "Support Vector Machine",
        "SVM (RBF kernel) with standardized features, train/test split and metrics.",
        {"C": {"type": "number", "default": 1.0, "title": "Regularization C"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC, SVR

        C = ctx.params.get("C", 1.0)

        def make(task):
            if task == "classification":
                return make_pipeline(StandardScaler(), SVC(C=C, probability=True, random_state=_SEED))
            return make_pipeline(StandardScaler(), SVR(C=C))

        return _fit_eval(self, ctx, make)


@register
class NaiveBayesModel(Component):
    spec = _spec(
        "model.ml.naive_bayes", "Naive Bayes (Gaussian)",
        "Probabilistic classifier that adds up per-feature evidence (classification only).",
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.naive_bayes import GaussianNB

        def make(task):
            return GaussianNB() if task == "classification" else None

        return _fit_eval(self, ctx, make)


@register
class MLPModel(Component):
    spec = _spec(
        "model.ml.mlp", "Neural Network (MLP)",
        "Feed-forward neural network (deep-learning stand-in) with standardized features.",
        {
            "hidden": {"type": "integer", "default": 32, "title": "Hidden units"},
            "max_iter": {"type": "integer", "default": 400, "title": "Training epochs"},
        },
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.neural_network import MLPClassifier, MLPRegressor
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        hidden = ctx.params.get("hidden", 32)
        max_iter = ctx.params.get("max_iter", 400)

        def make(task):
            M = MLPClassifier if task == "classification" else MLPRegressor
            return make_pipeline(
                StandardScaler(),
                M(hidden_layer_sizes=(hidden,), max_iter=max_iter, random_state=_SEED),
            )

        return _fit_eval(self, ctx, make)
