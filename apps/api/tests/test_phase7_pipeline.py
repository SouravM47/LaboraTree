"""Phase 7 tests: cross-Lab pipeline (chained components, data + Evidence flow)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.main import app


def _project(client):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/api/auth/register",
                      json={"email": email, "password": "supersecret1", "full_name": "P"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    pid = client.post("/api/projects", json={"name": "Pipe"}, headers=h).json()["id"]
    return h, pid


def test_pipeline_chains_steps_and_threads_dataset():
    with TestClient(app) as client:
        h, pid = _project(client)
        body = {
            "dataset": [{"a": 1, "b": 2.0}, {"a": 1, "b": 2.0}, {"a": 2, "b": None}],
            "steps": [
                {"component_id": "transform.drop_duplicates", "params": {}},
                {"component_id": "transform.mean_impute", "params": {}},
                {"component_id": "analyzer.eda_profile", "params": {}},
            ],
        }
        r = client.post(f"/api/projects/{pid}/pipeline/run", headers=h, json=body)
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["ok"] is True
        assert len(out["steps"]) == 3
        # after drop_duplicates the frame has 2 rows, threaded through to the profile
        assert out["steps"][0]["preview"]["dataset"]["n_rows"] == 2
        assert out["steps"][2]["preview"]["profile"]["n_rows"] == 2
        # each step produced its own tracked run
        assert all(s["run_id"] for s in out["steps"])


def test_pipeline_stops_on_failed_step():
    with TestClient(app) as client:
        h, pid = _project(client)
        r = client.post(f"/api/projects/{pid}/pipeline/run", headers=h, json={
            "dataset": [{"a": 1}],
            "steps": [{"component_id": "does.not.exist", "params": {}}],
        })
        assert r.status_code == 201
        out = r.json()
        assert out["ok"] is False
        assert out["steps"][0]["status"] == "failed"
