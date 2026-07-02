"""Phase 7 tests: Evidence-bound report card + trust score."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.labs.intelligence.report import compute_trust_score, render_report_html
from laboratree.main import app


def test_trust_score():
    runs = [{"id": "r1", "repro_manifest": {"data_version": "abc"}}, {"id": "r2", "repro_manifest": {}}]
    ev = {"r1": [{"label": "acc", "kind": "metric", "value": 0.9}]}
    trust = compute_trust_score(runs, ev)
    assert trust["reproducibility"] == 0.5
    assert trust["evidence_coverage"] == 0.5
    assert trust["score"] == 50


def test_render_report_contains_metrics():
    runs = [{"id": "r1", "lab": "data", "component_id": "transform.x", "status": "succeeded",
             "repro_manifest": {"code_hash": "deadbeef"}}]
    ev = {"r1": [{"label": "rows_removed", "kind": "metric", "value": 3}]}
    trust = compute_trust_score(runs, ev)
    html = render_report_html("My Project", runs, ev, trust)
    assert "My Project" in html and "trust score" in html and "rows_removed" in html


def test_report_api_end_to_end():
    with TestClient(app) as client:
        email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        tok = client.post("/api/auth/register",
                          json={"email": email, "password": "supersecret1", "full_name": "R"}).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        pid = client.post("/api/projects", json={"name": "ReportProj"}, headers=h).json()["id"]

        # produce a run with evidence
        client.post(f"/api/projects/{pid}/runs", headers=h, json={
            "component_id": "transform.drop_duplicates", "params": {},
            "dataset": [{"a": 1}, {"a": 1}, {"a": 2}],
        })

        rep = client.post(f"/api/projects/{pid}/report", headers=h)
        assert rep.status_code == 201, rep.text
        body = rep.json()
        assert 0 <= body["trust"]["score"] <= 100

        dl = client.get(body["download_url"], headers=h)
        assert dl.status_code == 200
        assert "ReportProj" in dl.text and "rows_removed" in dl.text
