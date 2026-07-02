"""Phase 7 tests: adversarial Red-Team Critic."""

from __future__ import annotations

import pandas as pd

from laboratree.core.registry import REGISTRY
from laboratree_sdk import RunContext


class _Sink:
    def __init__(self):
        self.records = []

    def record(self, *, label, value, kind="metric", **meta):
        self.records.append((label, value))
        return f"e{len(self.records)}"


def _run(params, df):
    ctx = RunContext(run_id="r", org_id="o", params=params, inputs={"dataset": df}, evidence=_Sink())
    return REGISTRY.create("critic.red_team").run(ctx)


def test_red_team_passes_healthy_model():
    from sklearn.datasets import load_iris

    out = _run({"target": "target"}, load_iris(as_frame=True).frame)
    assert out["base_metric"] > 0.6
    assert out["verdict"] in ("PASS", "FAIL")
    assert "robustness_drop" in out and "ablation" in out


def test_red_team_fails_on_leakage():
    df = pd.DataFrame({
        "leak": [0, 1, 0, 1, 0, 1, 0, 1],
        "noise": [1, 2, 3, 4, 5, 6, 7, 8],
        "y": [0, 1, 0, 1, 0, 1, 0, 1],
    })
    out = _run({"target": "y"}, df)
    assert out["verdict"] == "FAIL"
    assert any(f["check"] == "leakage" for f in out["findings"])
