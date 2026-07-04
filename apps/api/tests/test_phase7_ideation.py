"""Phase 7 tests: Co-Scientist ideation engine + API."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.core.search import SearchHit
from laboratree.labs.ideation.coscientist import run_ideation, tournament
from laboratree.labs.ideation.evidence import brainstorm, gather_evidence, plan_queries
from laboratree.main import app


def _fake(system: str, prompt: str, **kw) -> str:
    if "Generation agent" in system:
        return '["Weak idea one", "The BEST idea", "Weak idea two"]'
    if "Reflection agent" in system:
        return '["critique", "critique", "critique"]'
    if "Ranking agent" in system:
        # prefer whichever side mentions BEST, else A
        a_line = next((ln for ln in prompt.splitlines() if ln.startswith("A:")), "")
        return "A" if "BEST" in a_line else "B" if "BEST" in prompt else "A"
    if "Evolution agent" in system:
        return '["Evolved idea X", "Evolved idea Y"]'
    if "Meta-review agent" in system:
        return "Synthesis of the strongest hypotheses into a research direction."
    return "ok"


def test_run_ideation_ranks_and_reviews():
    result = run_ideation("cure boredom", _fake, n=3, evolve_n=2)
    hyps = result["hypotheses"]
    assert len(hyps) == 5  # 3 generated + 2 evolved
    ranks = sorted(h["rank"] for h in hyps)
    assert ranks == [1, 2, 3, 4, 5]
    assert all("elo" in h for h in hyps)
    assert result["meta_review"].startswith("Synthesis")


def test_tournament_promotes_best():
    hyps = [
        {"id": "h0", "text": "mediocre", "elo": 1200.0},
        {"id": "h1", "text": "the BEST hypothesis", "elo": 1200.0},
        {"id": "h2", "text": "also mediocre", "elo": 1200.0},
    ]
    ranked = tournament(hyps, "goal", _fake, rounds=2)
    assert "BEST" in ranked[0]["text"]
    assert ranked[0]["rank"] == 1


def test_ideation_api(monkeypatch):
    from laboratree.labs.ideation import llm as ideation_llm

    monkeypatch.setattr(ideation_llm, "default_complete", _fake)

    with TestClient(app) as client:
        email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        tok = client.post("/api/auth/register",
                          json={"email": email, "password": "supersecret1", "full_name": "Q"}).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        pid = client.post("/api/projects", json={"name": "Ideas"}, headers=h).json()["id"]

        r = client.post(f"/api/projects/{pid}/ideation", headers=h,
                        json={"goal": "reduce urban heat islands", "n": 3, "evolve_n": 2})
        assert r.status_code == 201, r.text
        body = r.json()
        assert len(body["hypotheses"]) == 5
        assert body["meta_review"]
        sid = body["id"]

        got = client.get(f"/api/ideation/{sid}", headers=h)
        assert got.status_code == 200
        assert got.json()["goal"] == "reduce urban heat islands"


# ---------------- evidence hunt ----------------

def _fake_evidence_complete(system: str, prompt: str, **kw) -> str:
    if "plan web searches" in system:
        return '["women literacy rural development study", "female education economic growth India"]'
    if "evidence brief" in system:
        return (
            '{"summary": "Multiple studies link female literacy to development [1][2].",'
            ' "stance": "supports", "confidence": 0.7,'
            ' "key_findings": [{"finding": "Literacy correlates with income", "sources": [1]}],'
            ' "insights": ["Effect may be mediated by health outcomes"],'
            ' "variables_to_test": [{"name": "female_literacy_rate", "role": "independent",'
            ' "rationale": "the treatment variable"}],'
            ' "gaps": ["Few causal (RCT) studies"]}'
        )
    return "ok"


def _fake_search(query: str, count: int):
    return [
        SearchHit(title="Female literacy and growth", url="https://example.org/a", description="A study.", source="brave"),
        SearchHit(title="Rural development report", url="https://example.org/b", description="Stats.", source="brave"),
    ]


def test_plan_queries_falls_back_without_llm_json():
    qs = plan_queries("some hypothesis", lambda s, p, **k: "not json")
    assert qs and all(isinstance(q, str) for q in qs)


def test_gather_evidence_builds_cited_brief():
    out = gather_evidence(
        "If female literacy rises in rural India, rural development improves",
        search_fn=_fake_search,
        complete_fn=_fake_evidence_complete,
        max_sources=6,
    )
    assert out["sources"] and out["sources"][0]["url"] == "https://example.org/a"
    brief = out["brief"]
    assert brief["stance"] == "supports"
    assert brief["variables_to_test"][0]["name"] == "female_literacy_rate"


def test_gather_evidence_handles_no_sources():
    out = gather_evidence(
        "obscure hypothesis", search_fn=lambda q, c: [], complete_fn=_fake_evidence_complete
    )
    assert out["sources"] == []
    assert out["brief"]["stance"] == "inconclusive"


def test_brainstorm_is_grounded_in_brief_and_sources():
    captured = {}

    def _complete(system, prompt, **kw):
        captured["system"] = system
        captured["prompt"] = prompt
        return "Consider controlling for household income [1]. Gather district-level literacy data."

    out = brainstorm(
        hypothesis="female literacy -> rural development",
        brief={"summary": "positive link", "stance": "mixed",
               "variables_to_test": [{"name": "female_literacy_rate", "role": "independent"}]},
        sources=[{"title": "Study A", "url": "https://example.org/a", "snippet": "..."}],
        question="What confounders should I control for?",
        history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        complete_fn=_complete,
    )
    assert "income" in out["answer"]
    # grounded: the brief + the source + the question all reach the model
    assert "female_literacy_rate" in captured["prompt"]
    assert "https://example.org/a" in captured["prompt"]
    assert "confounders" in captured["prompt"]


def test_brainstorm_degrades_on_llm_error():
    def _boom(system, prompt, **kw):
        raise RuntimeError("llm down")

    out = brainstorm("h", {}, [], "q?", [], _boom)
    assert out["answer"]  # non-empty fallback, never raises
