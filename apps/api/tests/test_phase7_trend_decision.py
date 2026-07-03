"""Phase 7 tests: Trend (decompose, causal impact) + Decision (threshold, expected value)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from laboratree.core.registry import REGISTRY
from laboratree_sdk import RunContext


class _Sink:
    def __init__(self):
        self.records = []

    def record(self, *, label, value, kind="metric", **meta):
        self.records.append((label, value))
        return f"e{len(self.records)}"


def _run(component_id, params, df=None):
    ctx = RunContext(run_id="r", org_id="o", params=params,
                     inputs={"dataset": df} if df is not None else {}, evidence=_Sink())
    return REGISTRY.create(component_id).run(ctx)


def test_trend_decompose_shapes_and_direction():
    t = np.arange(48)
    df = pd.DataFrame({"y": 0.5 * t + 10 * np.sin(2 * np.pi * t / 12)})
    out = _run("analyzer.trend_decompose", {"value_column": "y", "period": 12}, df)
    d = out["decomposition"]
    assert len(d["trend"]) == 48 and len(d["seasonal"]) == 48 and len(d["resid"]) == 48
    assert out["summary"]["direction"] == "up"


def test_causal_impact_detects_jump():
    df = pd.DataFrame({"y": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 30, 31, 32, 33, 34]})
    out = _run("analyzer.causal_impact", {"value_column": "y", "intervention_index": 10}, df)
    assert out["impact"]["absolute_effect"] > 5


def test_threshold_rule_counts():
    df = pd.DataFrame({"score": [0.1, 0.6, 0.9, 0.3]})
    out = _run("decision.threshold_rule", {"column": "score", "threshold": 0.5}, df)
    assert out["summary"]["n_true"] == 2


def test_expected_value_recommends_best():
    out = _run(
        "decision.expected_value",
        {"options": [
            {"name": "A", "value": 100, "probability": 0.5},
            {"name": "B", "value": 10, "probability": 0.9},
        ]},
    )
    assert out["recommended"] == "A"
    assert out["ranked"][0]["ev"] == 50.0
