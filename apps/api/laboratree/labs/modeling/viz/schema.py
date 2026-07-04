"""Shared response shapes for the staged model-visualization traces."""

from __future__ import annotations

from pydantic import BaseModel


class ModelTrace(BaseModel):
    family: str  # "trees" | "linear" | "nn" | "knn" | "timeseries" | ...
    target: str
    task: str  # "classification" | "regression"
    features: list[str]  # the (top) feature columns shown
    labels: list[str] | None = None  # class label names (classification)
    table: list[dict] | None = None  # sample data rows (features + target) for the "the data" stage
    # trees
    tree: dict | None = None  # recursive node: {feature, threshold, gain, samples, leaf, prediction, left, right}
    baseline: float | None = None
    rounds: list[dict] | None = None  # legacy boosting rounds (kept for compatibility)
    # linear
    intercept: float | None = None
    coef: list[dict] | None = None
    samples: list[dict] | None = None
    # nn
    layers: list[int] | None = None
    forward: dict | None = None
    # knn — 2D scatter of (a sample of) the training rows: [{x, y, label}]
    points: list[dict] | None = None
    # timeseries / any family-specific extras: e.g. {x, y} axis names, history/fitted arrays, coefs
    series: dict | None = None
    # per-row testing walkthrough (all families): each row + how the prediction is formed
    test_rows: list[dict] | None = None
    # tunable hyperparameters: the knobs the UI renders (with the live value) + the values used to fit.
    # Defaults come from the paper; the user can tweak and the trace re-fits with the new settings.
    param_spec: list[dict] | None = None
    params: dict | None = None
    note: str = ""


class FeatureSelectionTrace(BaseModel):
    target: str
    task: str
    features: list[str]  # the search space (top features)
    importances: list[dict]  # [{feature, importance}] one-feature fitness
    generations: list[dict]  # [{habitats:[{selected:[...], fitness}], best_fitness}]
    selected: list[str]
    best_fitness: float
    note: str
