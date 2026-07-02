"""Phase 7 tests: EDA profiler + Vega-Lite chart components."""

from __future__ import annotations

import uuid

import pandas as pd
from fastapi.testclient import TestClient

from laboratree.core.registry import REGISTRY
from laboratree.labs.insight.eda.profile import profile_dataframe
from laboratree.main import app
from laboratree_sdk import RunContext


class _Sink:
    def __init__(self):
        self.records = []

    def record(self, *, label, value, kind="metric", **meta):
        self.records.append((label, value))
        return f"e{len(self.records)}"


def _df():
    return pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10], "c": ["x", "y", "x", "y", "x"]})


def _run(component_id, params, df):
    ctx = RunContext(run_id="r", org_id="o", params=params, inputs={"dataset": df}, evidence=_Sink())
    return REGISTRY.create(component_id).run(ctx)


# ---------------- EDA ----------------

def test_profile_dataframe_basics():
    p = profile_dataframe(_df())
    assert p["n_rows"] == 5 and p["n_cols"] == 3
    assert {c["name"] for c in p["columns"]} == {"a", "b", "c"}
    # a and b are perfectly correlated
    assert p["top_correlations"] and abs(p["top_correlations"][0]["corr"]) == 1.0


def test_eda_component_emits_metrics():
    out = _run("analyzer.eda_profile", {}, _df())
    assert out["profile"]["n_rows"] == 5


# ---------------- charts ----------------

def _assert_vega(spec):
    assert spec["$schema"].endswith("v5.json")
    assert "values" in spec["data"]
    assert "mark" in spec and "encoding" in spec


def test_histogram_spec():
    out = _run("chart.histogram", {"column": "a"}, _df())
    _assert_vega(out["spec"])
    assert out["spec"]["encoding"]["x"]["field"] == "a"


def test_scatter_spec_with_color():
    out = _run("chart.scatter", {"x": "a", "y": "b", "color": "c"}, _df())
    _assert_vega(out["spec"])
    assert out["spec"]["encoding"]["color"]["field"] == "c"


def test_correlation_heatmap_spec():
    out = _run("chart.correlation_heatmap", {}, _df())
    _assert_vega(out["spec"])
    assert any(v["a"] == "a" and v["b"] == "b" for v in out["spec"]["data"]["values"])


# ---------------- via API ----------------

def test_chart_via_runs_api():
    with TestClient(app) as client:
        email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        tok = client.post("/api/auth/register",
                          json={"email": email, "password": "supersecret1", "full_name": "I"}).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        pid = client.post("/api/projects", json={"name": "Insight"}, headers=h).json()["id"]
        r = client.post(f"/api/projects/{pid}/runs", headers=h, json={
            "component_id": "chart.histogram",
            "params": {"column": "a"},
            "dataset": [{"a": 1}, {"a": 2}, {"a": 3}],
        })
        assert r.status_code == 201, r.text
        assert r.json()["preview"]["spec"]["$schema"].endswith("v5.json")
