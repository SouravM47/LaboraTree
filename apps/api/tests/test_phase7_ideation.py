"""Phase 7 tests: Co-Scientist ideation engine + API."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.labs.ideation.coscientist import run_ideation, tournament
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
