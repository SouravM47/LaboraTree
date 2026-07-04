"""Clustering family — unsupervised grouping (k-means, DBSCAN, Gaussian mixture).

Unsupervised: no target needed. Metrics are structure-quality scores (silhouette: -1..1, higher =
tighter, better-separated clusters) plus the found cluster sizes — all Evidence-emitted.
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
                "target": {"type": "string", "title": "Target column (ignored — unsupervised)"},
                "features": {"type": "array", "items": {"type": "string"}, "title": "Features"},
                **(extra or {}),
            },
        },
        inputs=[Port(name="dataset", dtype="dataset")],
        outputs=[Port(name="metrics", dtype="metrics")],
        tags=["ml", "clustering", "unsupervised"],
    )


def _cluster_run(component: Component, ctx: RunContext, fit_predict) -> dict[str, Any]:
    """Shared loop: scale -> fit_predict(Xs) -> silhouette + sizes -> emit."""
    import numpy as np
    import pandas as pd
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    df: pd.DataFrame = ctx.inputs["dataset"].dropna()
    target = ctx.params.get("target")
    feats = numeric_features(df, target if target in df.columns else df.columns[-1],
                             ctx.params.get("features"))
    if not feats:
        raise ValueError(f"no numeric features available for {component.spec.name}")
    Xs = StandardScaler().fit_transform(df[feats])
    labels = np.asarray(fit_predict(Xs))

    uniq = [int(c) for c in sorted(set(labels)) if c != -1]
    sizes = {f"cluster_{c + 1}_size": float((labels == c).sum()) for c in uniq}
    noise = float((labels == -1).sum())
    metrics: dict[str, float] = {"n_clusters": float(len(uniq)), **sizes}
    if noise:
        metrics["noise_points"] = noise
    if len(uniq) >= 2:
        mask = labels != -1
        metrics["silhouette"] = float(silhouette_score(Xs[mask], labels[mask]))

    for k, v in metrics.items():
        ctx.emit(k, v, kind="metric", component=component.spec.id)
    return {"metrics": metrics, "task": "clustering", "n_test": int(len(df))}


@register
class KMeansModel(Component):
    spec = _spec(
        "model.clustering.kmeans", "K-Means Clustering",
        "Groups rows into k clusters around moving centre points; silhouette + sizes.",
        {"n_clusters": {"type": "integer", "default": 3, "title": "Clusters (k)"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.cluster import KMeans

        k = ctx.params.get("n_clusters", 3)
        return _cluster_run(self, ctx, lambda X: KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X))


@register
class DBSCANModel(Component):
    spec = _spec(
        "model.clustering.dbscan", "DBSCAN Clustering",
        "Density-based clustering — finds arbitrary-shaped clusters and flags noise points.",
        {
            "eps": {"type": "number", "default": 0.8, "title": "Neighborhood radius (eps)"},
            "min_samples": {"type": "integer", "default": 5, "title": "Min samples"},
        },
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.cluster import DBSCAN

        eps = ctx.params.get("eps", 0.8)
        ms = ctx.params.get("min_samples", 5)
        return _cluster_run(self, ctx, lambda X: DBSCAN(eps=eps, min_samples=ms).fit_predict(X))


@register
class GaussianMixtureModel(Component):
    spec = _spec(
        "model.clustering.gmm", "Gaussian Mixture (GMM)",
        "Soft clustering — models the data as k overlapping bell curves.",
        {"n_components": {"type": "integer", "default": 3, "title": "Components (k)"}},
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        from sklearn.mixture import GaussianMixture

        k = ctx.params.get("n_components", 3)
        return _cluster_run(
            self, ctx, lambda X: GaussianMixture(n_components=k, random_state=0).fit(X).predict(X)
        )
