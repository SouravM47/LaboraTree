"""Foundation smoke tests: registry discovery, component catalog API, and a component run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from laboratree.core.registry import REGISTRY, discover
from laboratree.main import app
from laboratree_sdk import RunContext


class _ListSink:
    """Minimal EvidenceSink for tests."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, *, label, value, kind="metric", **meta) -> str:
        eid = f"ev-{len(self.records)}"
        self.records.append({"id": eid, "label": label, "value": value, "kind": kind, **meta})
        return eid


def test_registry_discovers_reference_components():
    discover()
    ids = REGISTRY.ids()
    assert "transform.drop_duplicates" in ids
    assert "transform.mean_impute" in ids


def test_components_endpoint_lists_specs():
    with TestClient(app) as client:
        resp = client.get("/api/components")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 2
        assert any(c["id"] == "transform.drop_duplicates" for c in body["components"])


def test_health_endpoint_answers_even_without_stores():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "services" in resp.json()


def test_drop_duplicates_component_runs_and_emits_evidence(tmp_path: Path):
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    sink = _ListSink()
    ctx = RunContext(
        run_id="r1",
        org_id="o1",
        params={"keep": "first"},
        inputs={"dataset": df},
        workdir=tmp_path,
        evidence=sink,
    )
    out = REGISTRY.create("transform.drop_duplicates").run(ctx)
    assert len(out["dataset"]) == 2
    assert sink.records and sink.records[0]["label"] == "rows_removed"
    assert sink.records[0]["value"] == 1
