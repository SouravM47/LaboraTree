"""Phase 7 tests: Collection Lab (sample size, questionnaire, bias, pilot)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.labs.collection.survey import (
    design_questionnaire,
    detect_bias,
    sample_size,
    synthetic_pilot,
)
from laboratree.main import app


def _fake(system: str, prompt: str, **kw) -> str:
    if "survey methodologist" in system:
        return '[{"text": "How satisfied are you?", "type": "likert"}, {"text": "Your age?", "type": "open"}]'
    if "audit survey questions" in system:
        return '[{"question": "Do not you agree X is great?", "issue": "leading", "severity": "high", "suggestion": "rephrase neutrally"}]'
    if "simulate survey pilot" in system:
        return '[{"1": "yes", "2": "30"}, {"1": "no", "2": "45"}]'
    return "[]"


# ---------------- pure ----------------

def test_sample_size_standard():
    r = sample_size(0.95, 0.05, None, 0.5)
    assert r["sample_size"] == 385  # classic n=384.16 -> 385


def test_sample_size_finite_population_is_smaller():
    infinite = sample_size(0.95, 0.05, None, 0.5)["sample_size"]
    finite = sample_size(0.95, 0.05, 500, 0.5)["sample_size"]
    assert finite < infinite


# ---------------- LLM (fake) ----------------

def test_design_questionnaire():
    qs = design_questionnaire("measure satisfaction", "customers", 2, _fake)
    assert len(qs) == 2 and qs[0]["type"] == "likert"


def test_detect_bias():
    findings = detect_bias(["Do not you agree X is great?"], _fake)
    assert findings and findings[0]["severity"] == "high"


def test_synthetic_pilot():
    out = synthetic_pilot(["Q1?", "Q2?"], "busy urban commuter", 2, _fake)
    assert out["n"] == 2 and len(out["respondents"]) == 2


# ---------------- API ----------------

def _project(client):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/api/auth/register",
                      json={"email": email, "password": "supersecret1", "full_name": "C"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    pid = client.post("/api/projects", json={"name": "Survey"}, headers=h).json()["id"]
    return h, pid


def test_sample_size_api_no_llm():
    with TestClient(app) as client:
        h, pid = _project(client)
        r = client.post(f"/api/projects/{pid}/collection/sample-size", headers=h,
                        json={"confidence": 0.95, "margin": 0.05})
        assert r.status_code == 200
        assert r.json()["sample_size"] == 385


def test_questionnaire_api(monkeypatch):
    from laboratree.labs.collection import llm as collection_llm

    monkeypatch.setattr(collection_llm, "default_complete", _fake)
    with TestClient(app) as client:
        h, pid = _project(client)
        r = client.post(f"/api/projects/{pid}/collection/questionnaire", headers=h,
                        json={"goal": "measure satisfaction", "audience": "customers", "n": 2})
        assert r.status_code == 200
        assert len(r.json()["questions"]) == 2
