"""Phase 8 tests: adaptive card (classify/empirical/conceptual), demo data, LLM observability."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.labs.paper.card import classify_paper, generate_card, normalize_card
from laboratree.labs.paper.experiment.demo import generate_demo_dataset
from laboratree.main import app


# ---------------- classification + card shapes ----------------

def test_classify_routes_to_type():
    assert classify_paper("x", lambda s, p: "empirical") == "empirical"
    assert classify_paper("x", lambda s, p: "This is conceptual") == "conceptual"


def _empirical(system, prompt, **kw):
    if "Classify" in system:
        return "empirical"
    return ('{"problem_statement":{"one_liner":"Predict churn","plain":"We predict churn."},'
            '"models_used":[{"name":"Logit","summary":"binary classifier"}],'
            '"independent_variables":[{"name":"tenure","description":"months as a customer","example_value":"12"}],'
            '"target_variable":{"name":"churn","description":"left or not","example_value":"yes"}}')


def test_empirical_card_is_enriched():
    card = generate_card("text", _empirical)
    assert card["paper_type"] == "empirical"
    assert card["problem_statement"]["one_liner"] == "Predict churn"
    assert card["independent_variables"][0]["example_value"] == "12"
    assert card["target_variable"]["name"] == "churn"
    assert card["models_used"][0]["summary"]


def _conceptual(system, prompt, **kw):
    if "Classify" in system:
        return "conceptual"
    return ('{"one_liner":"A framework for X","segments":[{"heading":"Core idea","body":"…",'
            '"analogy":"like a library"}],"glossary":[{"term":"X","definition":"Y"}],'
            '"takeaways":["a","b"]}')


def test_conceptual_card_is_segmented():
    card = generate_card("text", _conceptual)
    assert card["paper_type"] == "conceptual"
    assert card["segments"][0]["analogy"] == "like a library"
    assert card["glossary"][0]["term"] == "X"
    assert card["takeaways"] == ["a", "b"]


def test_normalize_card_backward_compatible():
    card = normalize_card({
        "problem_statement": "plain text", "models_used": ["Logit"],
        "independent_variables": ["age"], "target_variable": "y", "data_sources": ["UCI"],
    })
    assert card["problem_statement"]["plain"] == "plain text"
    assert card["models_used"][0]["name"] == "Logit"
    assert card["independent_variables"][0]["name"] == "age"
    assert card["target_variable"]["name"] == "y"


# ---------------- demo data ----------------

def test_generate_demo_dataset():
    def fake(system, prompt, **kw):
        return '{"columns":["age","churn"],"rows":[{"age":30,"churn":1},{"age":45,"churn":0}]}'

    card = {"independent_variables": [{"name": "age"}], "target_variable": {"name": "churn"}}
    out = generate_demo_dataset("paper text", card, 6, fake)
    assert "age" in out["columns"] and "churn" in out["columns"]
    assert len(out["records"]) >= 1
    assert all(c in out["records"][0] for c in out["columns"])
    assert out["caveat"]


# ---------------- observability ----------------

def test_llm_observability_records_and_summarizes():
    from laboratree.core.llm.context import use_llm_context
    from laboratree.core.llm.observability import record_llm_call

    with TestClient(app) as client:
        email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        reg = client.post("/api/auth/register",
                          json={"email": email, "password": "supersecret1", "full_name": "O"}).json()
        h = {"Authorization": f"Bearer {reg['access_token']}"}
        org = reg["org_id"]
        pid = client.post("/api/projects", json={"name": "Obs"}, headers=h).json()["id"]

        with use_llm_context("paper", "card", project_id=pid, org_id=org):
            record_llm_call(provider="azure", model="gpt-x", role="reasoning",
                            prompt_tokens=10, completion_tokens=5, total_tokens=15,
                            latency_ms=42.0, status="ok")

        summ = client.get(f"/api/projects/{pid}/llm/summary", headers=h).json()
        assert summ["totals"]["calls"] >= 1
        assert any(x["lab"] == "paper" for x in summ["by_lab"])

        calls = client.get(f"/api/projects/{pid}/llm/calls", headers=h).json()
        assert calls and calls[0]["total_tokens"] == 15
