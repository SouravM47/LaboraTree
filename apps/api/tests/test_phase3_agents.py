"""Phase 3 tests: leakage audit, run executor + Evidence via API, HITL agent graph, sandbox."""

from __future__ import annotations

import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from laboratree.agents import graph as agent_graph
from laboratree.agents import sandbox
from laboratree.labs.modeling.leakage import audit_leakage
from laboratree.main import app


# ---------------- Leakage Sentinel (pure) ----------------

def test_audit_detects_target_leakage():
    df = pd.DataFrame({"x": [1, 2, 3, 4], "leak": [10, 20, 30, 40], "y": [10, 20, 30, 40]})
    findings = audit_leakage(df, target="y")
    assert any(f["check"] == "target_leakage" for f in findings)


def test_audit_detects_train_test_contamination():
    df = pd.DataFrame(
        {"a": [1, 1, 2], "split": ["train", "test", "train"], "y": [0, 0, 1]}
    )
    findings = audit_leakage(df, target="y", split_column="split")
    assert any(f["check"] == "train_test_contamination" for f in findings)


def test_audit_clean_frame_has_no_target_leakage():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "z": [5, 1, 4, 2, 3], "y": [0, 1, 0, 1, 0]})
    findings = audit_leakage(df, target="y")
    assert not any(f["check"] == "target_leakage" for f in findings)


# ---------------- Agent graph (fake LLM) ----------------

def _fake_complete(system: str, prompt: str) -> str:
    if "Planner" in system:
        return "1. do a thing\n2. do another thing"
    if "Engineer" in system:
        return "executed successfully"
    if "Critic" in system:
        return "PASS - result satisfies the task"
    return "ok"


def test_agent_graph_pauses_at_gate_then_resumes_on_approval():
    g = agent_graph.build_graph(complete_fn=_fake_complete)
    tid = f"t-{uuid.uuid4().hex[:8]}"
    first = agent_graph.start(g, "analyze the dataset", tid)
    assert agent_graph.is_interrupted(first)  # paused for human approval

    final = agent_graph.resume(g, tid, approved=True)
    assert not agent_graph.is_interrupted(final)
    assert final["result"] == "executed successfully"
    assert "PASS" in final["verdict"]


def test_agent_graph_rejection_stops_before_engineer():
    g = agent_graph.build_graph(complete_fn=_fake_complete)
    tid = f"t-{uuid.uuid4().hex[:8]}"
    agent_graph.start(g, "analyze the dataset", tid)
    final = agent_graph.resume(g, tid, approved=False)
    assert final.get("approved") is False
    assert "result" not in final  # engineer never ran


# ---------------- Sandbox (gated on image availability) ----------------

@pytest.mark.skipif(not sandbox.is_available(), reason="sandbox image not built")
def test_sandbox_runs_code_isolated():
    result = sandbox.run_code("print('hello-sandbox')\nopen('out.txt','w').write('x')\n")
    assert result.ok
    assert "hello-sandbox" in result.stdout
    assert "out.txt" in result.artifacts


# ---------------- Run executor + Evidence via API (needs Postgres) ----------------

def _register(client: TestClient) -> tuple[str, str]:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret1", "full_name": "T"},
    )
    token = r.json()["access_token"]
    p = client.post(
        "/api/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {token}"}
    )
    return token, p.json()["id"]


def test_run_component_produces_evidence_and_manifest():
    with TestClient(app) as client:
        token, project_id = _register(client)
        h = {"Authorization": f"Bearer {token}"}

        r = client.post(
            f"/api/projects/{project_id}/runs",
            headers=h,
            json={
                "component_id": "transform.drop_duplicates",
                "params": {"keep": "first"},
                "dataset": [{"a": 1, "b": "x"}, {"a": 1, "b": "x"}, {"a": 2, "b": "y"}],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["run"]["status"] == "succeeded"
        assert body["run"]["repro_manifest"]["data_version"]  # hash recorded
        assert body["preview"]["dataset"]["n_rows"] == 2
        run_id = body["run"]["id"]

        ev = client.get(f"/api/runs/{run_id}/evidence", headers=h)
        assert ev.status_code == 200
        labels = {e["label"]: e["value"] for e in ev.json()}
        assert labels.get("rows_removed") == 1


def test_run_leakage_sentinel_via_api():
    with TestClient(app) as client:
        token, project_id = _register(client)
        h = {"Authorization": f"Bearer {token}"}
        r = client.post(
            f"/api/projects/{project_id}/runs",
            headers=h,
            json={
                "component_id": "analyzer.leakage_sentinel",
                "params": {"target": "y"},
                "dataset": [
                    {"x": 1, "leak": 10, "y": 10},
                    {"x": 2, "leak": 20, "y": 20},
                    {"x": 3, "leak": 30, "y": 30},
                ],
            },
        )
        assert r.status_code == 201, r.text
        findings = r.json()["preview"]["findings"]
        assert any(f["check"] == "target_leakage" for f in findings)
