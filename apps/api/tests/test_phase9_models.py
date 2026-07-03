"""Model Lab expansion: random forest, gradient boosting, econometrics (logit/probit/arima)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from laboratree.core.registry import REGISTRY
from laboratree_sdk import RunContext


class _Sink:
    def record(self, *, label, value, kind="metric", **m):
        return "e"


def _run(component_id, params, df):
    ctx = RunContext(run_id="r", org_id="o", params=params, inputs={"dataset": df}, evidence=_Sink())
    return REGISTRY.create(component_id).run(ctx)


def _binary_df(n=80):
    rng = np.random.default_rng(0)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    p = 1 / (1 + np.exp(-(1.6 * x1 - 1.1 * x2)))
    y = (rng.uniform(size=n) < p).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "y": y})


def test_random_forest_classifies_iris():
    from sklearn.datasets import load_iris

    out = _run("model.ml.random_forest", {"target": "target"}, load_iris(as_frame=True).frame)
    assert out["task"] == "classification" and out["metrics"]["accuracy"] > 0.6


def test_gradient_boosting_classifies_iris():
    from sklearn.datasets import load_iris

    out = _run("model.ml.gradient_boosting", {"target": "target"}, load_iris(as_frame=True).frame)
    assert out["metrics"]["accuracy"] > 0.6


def test_logit_binary():
    out = _run("model.econometrics.logit", {"target": "y"}, _binary_df())
    assert "accuracy" in out["metrics"] and "pseudo_r2" in out["metrics"]
    assert "const" in out["coefficients"]


def test_probit_binary():
    out = _run("model.econometrics.probit", {"target": "y"}, _binary_df())
    assert "pseudo_r2" in out["metrics"]


def test_arima_reports_aic():
    rng = np.random.default_rng(1)
    series = np.cumsum(rng.normal(size=48)) + 50
    out = _run("model.econometrics.arima", {"value_column": "sales", "order": [1, 1, 1]},
               pd.DataFrame({"sales": series}))
    assert "aic" in out["metrics"] and out["n_obs"] == 48
