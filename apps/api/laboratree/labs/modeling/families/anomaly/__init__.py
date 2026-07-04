"""Anomaly-detection family — isolation forest, local outlier factor, one-class SVM.

Unsupervised: the model learns what "usual" rows look like and flags the rest. Metrics are the
flagged count/rate — all Evidence-emitted.
"""

from __future__ import annotations

from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...evaluation.metrics import numeric_features


def _spec(cid: str, name: str, summary: str, extra: dict | None = None) -> ComponentSpec:
    return ComponentSpec(
        kind=ComponentKind.MODEL,
        id=cid,
        name=name,
        summary=summary,
        params_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "title": "Target column (optional — unsupervised)"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                "contamination": {"type": "number", "default": 0.05, "title": "Expected anomaly share"},
                **(extra or {}),
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "anomaly", "unsupervised"],
    )


def _anomaly_run(component: Component, ctx: RunContext, make_detector) -> dict[str, Any]:
    """Shared loop: scale -> predict (1 normal / -1 anomaly) -> rate metrics -> emit."""
    import pandas as pd
    from sklearn.preprocessing import StandardScaler

    df: pd.DataFrame = ctx.inputs["dataset"].dropna()
    target = ctx.params.get("target")
    feats = numeric_features(df, target if target in df.columns else df.columns[-1],
                             ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {component.spec.name}")
    Xs = StandardScaler().fit_transform(df[feats])
    flags = make_detector().fit_predict(Xs)  # 1 normal, -1 anomaly

    n = len(flags)
    n_anom = int((flags == -1).sum())
    metrics: dict[str, float] = {
        "n_anomalies": float(n_anom),
        "anomaly_rate": float(n_anom / n) if n else 0.0,
    }
    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component.spec.id)
    return {"metrics": metrics, "task": "anomaly", "n_test": int(n)}


@register
class IsolationForestModel(Component):
    spec = _spec(
        "model.anomaly.isolation_forest", "Isolation Forest",
        "Flags rows that random cuts isolate too easily (classic anomaly detector).",
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.ensemble import IsolationForest

        c = ctx.params.get("contamination", 0.05)
        return _anomaly_run(self, ctx, lambda: IsolationForest(contamination=c, random_state=0))


@register
class LocalOutlierFactorModel(Component):
    spec = _spec(
        "model.anomaly.lof", "Local Outlier Factor",
        "Flags rows that are much less densely surrounded than their neighbors.",
        {"n_neighbors": {"type": "integer", "default": 20, "title": "Neighbors"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.neighbors import LocalOutlierFactor

        c = ctx.params.get("contamination", 0.05)
        k = ctx.params.get("n_neighbors", 20)
        return _anomaly_run(self, ctx, lambda: LocalOutlierFactor(n_neighbors=k, contamination=c))


@register
class OneClassSVMModel(Component):
    spec = _spec(
        "model.anomaly.one_class_svm", "One-Class SVM",
        "Learns a boundary around 'normal' rows; anything outside is flagged.",
        {"nu": {"type": "number", "default": 0.05, "title": "Boundary looseness (nu)"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.svm import OneClassSVM

        nu = ctx.params.get("nu", 0.05)
        return _anomaly_run(self, ctx, lambda: OneClassSVM(nu=nu))
