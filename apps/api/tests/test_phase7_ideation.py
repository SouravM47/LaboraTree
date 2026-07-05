"""Phase 7 tests: Co-Scientist ideation engine + API."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from laboratree.core.search import SearchHit, looks_like_data_url
from laboratree.labs.ideation.coscientist import run_ideation, tournament
from laboratree.labs.ideation.data_hunt import hunt_datasets
from laboratree.labs.ideation.evidence import (
    brainstorm,
    extract_variables,
    gather_evidence,
    plan_queries,
)
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


def test_generation_grounds_in_evidence_context():
    from laboratree.labs.ideation.coscientist import generate_hypotheses

    seen = {}

    def _cap(system, prompt, **kw):
        seen["system"], seen["prompt"] = system, prompt
        return '["grounded idea 1", "grounded idea 2"]'

    hyps = generate_hypotheses("women literacy & development", 2, _cap,
                               context="Summary: literacy raises income. Key variables: female_literacy_rate")
    assert hyps and hyps[0]["origin"] == "grounded"
    assert "female_literacy_rate" in seen["prompt"]        # the evidence reached generation
    assert "Ground every hypothesis" in seen["system"]      # grounding instruction switched on


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
    if "research methodologist" in system:  # the dedicated exhaustive variable pass
        return (
            '[{"name": "female_literacy_rate", "role": "independent", "measure": "% women 15+ literate",'
            ' "expected_direction": "positive", "source_refs": [1], "rationale": "treatment"},'
            ' {"name": "rural_development_index", "role": "dependent", "measure": "composite index",'
            ' "expected_direction": "positive", "source_refs": [2], "rationale": "outcome"},'
            ' {"name": "household_income", "role": "confounder", "measure": "INR/month",'
            ' "expected_direction": "positive", "source_refs": [], "rationale": "standard control"}]'
        )
    if "evidence brief" in system:
        return (
            '{"summary": "Multiple studies link female literacy to development [1][2].",'
            ' "stance": "supports", "confidence": 0.7,'
            ' "key_findings": [{"finding": "Literacy correlates with income", "sources": [1]}],'
            ' "insights": ["Effect may be mediated by health outcomes"],'
            ' "gaps": ["Few causal (RCT) studies"]}'
        )
    return "ok"


def _fake_search(query: str, count: int):
    return [
        SearchHit(title="Female literacy and growth", url="https://example.org/a", description="A study.", source="brave"),
        SearchHit(title="Rural development report", url="https://example.org/b", description="Stats.", source="brave"),
    ]


def test_open_access_pdf_ignores_non_scholarly_urls():
    from laboratree.core.search import open_access_pdf

    # a plain web page (no DOI / OpenAlex id) resolves to no OA PDF without any network call
    assert open_access_pdf("https://example.com/blog/post") is None


def test_safe_filename():
    from laboratree.api.ideation import _safe_filename

    assert _safe_filename("Women & Human Development: 2000!").endswith(".pdf")
    assert "/" not in _safe_filename("a/b/c") and " " not in _safe_filename("a b c")


def test_openalex_abstract_reconstruction():
    from laboratree.core.search import _openalex_abstract

    inv = {"Female": [0], "literacy": [1], "raises": [2], "income": [3]}
    assert _openalex_abstract(inv) == "Female literacy raises income"
    assert _openalex_abstract(None) == ""


def test_research_search_falls_back_to_web(monkeypatch):
    from laboratree.core import search as S

    monkeypatch.setattr(S, "openalex_search", lambda q, n: [
        S.SearchHit(title="Paper", url="https://doi.org/x", description="abstract", source="openalex")
    ])
    monkeypatch.setattr(S, "web_search", lambda q, n=None: [
        S.SearchHit(title="Web", url="https://example.org/w", description="", source="brave")
    ])
    hits = S.research_search("q", 5)
    assert hits[0].source == "openalex"                     # papers first
    assert any(h.source == "brave" for h in hits)            # web supplements


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
    # variables now come from the dedicated exhaustive pass: grounded (source_refs) + standard controls
    vs = brief["variables_to_test"]
    assert vs[0]["name"] == "female_literacy_rate"
    roles = {v["role"] for v in vs}
    assert {"independent", "dependent", "confounder"} <= roles     # spans roles, not just treatment
    assert any(v["source_refs"] for v in vs)                       # at least one tied to a study
    assert all("measure" in v and "expected_direction" in v for v in vs)


def test_extract_variables_is_exhaustive_and_grounded():
    sources = [{"title": "A", "url": "https://x/a", "snippet": "..."},
               {"title": "B", "url": "https://x/b", "snippet": "..."}]
    vs = extract_variables("female literacy -> development", sources, _fake_evidence_complete)
    assert len(vs) >= 3
    assert {"independent", "dependent", "confounder"} <= {v["role"] for v in vs}
    # a standard control has no source_refs; a study-grounded one does
    assert any(not v["source_refs"] for v in vs) and any(v["source_refs"] for v in vs)


def test_extract_variables_empty_without_sources():
    assert extract_variables("h", [], _fake_evidence_complete) == []


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


# ---------------- data hunt ----------------

def test_looks_like_data_url():
    assert looks_like_data_url("https://example.org/data/file.csv")
    assert looks_like_data_url("https://raw.githubusercontent.com/x/y/main/anything")
    assert not looks_like_data_url("https://example.org/blog/article")


def _fake_data_complete(system: str, prompt: str, **kw) -> str:
    if "FIND DOWNLOADABLE DATASETS" in system:
        return '["female literacy rate India district dataset", "rural development index India data"]'
    if "data-sourcing expert" in system:
        # [1] is a real dataset, [2] is an article to be filtered out
        return (
            '[{"index": 1, "is_dataset": true, "relevance": 0.9, "why": "district literacy panel",'
            ' "variables_covered": ["female_literacy_rate"], "access": "direct_download"},'
            ' {"index": 2, "is_dataset": false, "relevance": 0.1, "why": "news article",'
            ' "variables_covered": [], "access": "unknown"}]'
        )
    return "[]"


def _fake_data_search(query: str, count: int):
    return [
        SearchHit(title="India literacy data.csv", url="https://data.gov/india_literacy.csv",
                  description="District-level literacy.", source="brave"),
        SearchHit(title="Opinion: literacy matters", url="https://news.example.com/op-ed",
                  description="An article.", source="brave"),
    ]


def test_hunt_datasets_ranks_real_datasets_and_filters_articles():
    out = hunt_datasets(
        "female literacy -> rural development",
        ["female_literacy_rate", "rural_development_index"],
        search_fn=_fake_data_search, complete_fn=_fake_data_complete, max_candidates=10,
    )
    urls = [c["url"] for c in out["candidates"]]
    assert "https://data.gov/india_literacy.csv" in urls          # dataset kept
    assert "https://news.example.com/op-ed" not in urls           # article filtered
    top = out["candidates"][0]
    assert top["direct_download"] is True and top["relevance"] >= 0.5


# ---------------- auto-experiment (deep agent skill selection) ----------------

def test_build_master_concatenates_matching_schemas():
    from laboratree.labs.ideation.master_dataset import build_master

    a = b"age,income,y\n30,100,1\n40,200,0\n"
    b = b"age,income,y\n50,300,1\n60,400,0\n"
    diff = b"totally,different\n1,2\n3,4\n"
    blobs = {
        "https://x/a.csv": a, "https://x/b.csv": b, "https://x/c.csv": diff,
        "https://x/bad.csv": b"<html>not data</html>",
    }
    candidates = [
        {"url": "https://x/a.csv", "title": "A", "direct_download": True},
        {"url": "https://x/b.csv", "title": "B", "direct_download": True},
        {"url": "https://x/c.csv", "title": "C", "direct_download": True},
        {"url": "https://x/bad.csv", "title": "bad", "direct_download": True},
        {"url": "https://x/portal", "title": "portal", "direct_download": False},  # skipped
    ]
    out = build_master(candidates, fetch_fn=lambda u: blobs.get(u))
    assert out["master"] is not None
    # a + b share a schema and are the largest group → concatenated to 4 rows
    assert len(out["master"]) == 4 and list(out["master"].columns) == ["age", "income", "y"]
    statuses = {t["url"]: t["status"] for t in out["tables"]}
    assert statuses["https://x/bad.csv"] == "not_tabular"
    # non-direct candidates ARE now attempted (portals often still serve CSV); this one has no bytes
    assert statuses["https://x/portal"] == "download_failed"


def test_build_master_handles_nothing_usable():
    from laboratree.labs.ideation.master_dataset import build_master

    out = build_master([{"url": "https://x/a", "direct_download": True}], fetch_fn=lambda u: None)
    assert out["master"] is None and "No candidate" in out["note"]


def test_detect_task():
    import pandas as pd
    from laboratree.labs.ideation.auto_experiment import detect_task

    clf = pd.DataFrame({"x": range(20), "y": ["a", "b"] * 10})
    reg = pd.DataFrame({"x": range(20), "y": [float(i) for i in range(20)]})
    assert detect_task(clf, "y") == "classification"
    assert detect_task(reg, "y") == "regression"


def test_plan_experiment_validates_and_falls_back():
    from laboratree.labs.ideation.auto_experiment import plan_experiment

    avail = ["model.ml.logistic_regression", "model.ml.random_forest", "model.ml.gradient_boosting"]

    def good(system, prompt, **kw):
        return '{"preprocessing": "impute+scale", "models": ["model.ml.random_forest"], "rationale": "trees handle mixed types"}'

    plan = plan_experiment({"n_rows": 100}, "h", "classification", avail, good)
    assert plan["models"] == ["model.ml.random_forest"]

    # bad LLM output → fall back to the task-appropriate default pool (all in the available list)
    plan2 = plan_experiment({"n_rows": 100}, "h", "classification", avail, lambda s, p, **k: "garbage")
    assert plan2["models"] and all(m in avail for m in plan2["models"])


def test_rank_and_summarize_pick_best_by_metric():
    from laboratree.labs.ideation.auto_experiment import rank_results, summarize_results

    results = [
        {"component": "model.ml.logistic_regression", "metrics": {"f1": 0.70, "accuracy": 0.72}},
        {"component": "model.ml.random_forest", "metrics": {"f1": 0.88, "accuracy": 0.90}},
    ]
    assert rank_results(results, "classification")[0]["component"] == "model.ml.random_forest"

    # deterministic fallback when the LLM can't structure a verdict
    out = summarize_results("h", "classification", results, lambda s, p, **k: "not json")
    assert out["best_model"] == "model.ml.random_forest"


def _auto_experiment_llm(system: str, prompt: str, **kw) -> str:
    if "ML strategist" in system:
        return '{"preprocessing": "impute+scale", "models": ["model.ml.logistic_regression", "model.ml.random_forest"], "rationale": "baselines"}'
    if "research analyst" in system:
        return '{"best_model": "model.ml.random_forest", "verdict": "RF fits best.", "insights": ["fit is not causation"]}'
    return "{}"


def test_auto_experiment_runs_real_models_end_to_end(monkeypatch):
    import asyncio

    import pandas as pd
    from laboratree.core.db.postgres import sessionmaker
    from laboratree.core.repro import dataframe_hash
    from laboratree.core.storage import get_blob_store
    from laboratree.labs.ideation import llm as ideation_llm
    from laboratree.projects.models import Dataset

    monkeypatch.setattr(ideation_llm, "default_complete", _auto_experiment_llm)

    # a small but learnable classification dataset
    rng = __import__("random").Random(0)
    rows = [{"x1": rng.gauss(0, 1), "x2": rng.gauss(0, 1)} for _ in range(80)]
    for r in rows:
        r["y"] = "yes" if (r["x1"] + r["x2"] > 0) else "no"
    df = pd.DataFrame(rows)

    with TestClient(app) as client:
        email = f"user-{uuid.uuid4().hex[:10]}@example.com"
        tok = client.post("/api/auth/register",
                          json={"email": email, "password": "supersecret1", "full_name": "Q"}).json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        pid = client.post("/api/projects", json={"name": "AutoX"}, headers=h).json()["id"]

        # insert a Dataset directly (org-scoped) + its blob
        key = f"test/{uuid.uuid4()}.csv"
        get_blob_store().put(key, df.to_csv(index=False).encode())

        async def _insert() -> str:
            async with sessionmaker()() as s:
                ds = Dataset(org_id=uuid.UUID(tok["org_id"]), project_id=uuid.UUID(pid),
                             name="autox.csv", storage_key=key, content_hash=dataframe_hash(df),
                             n_rows=len(df), n_cols=df.shape[1])
                s.add(ds)
                await s.flush()
                did = str(ds.id)
                await s.commit()
                return did

        dataset_id = asyncio.run(_insert())

        r = client.post(f"/api/projects/{pid}/ideation/auto-experiment", headers=h,
                        json={"dataset_id": dataset_id, "target": "y", "hypothesis": "x1+x2 predicts y"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["task"] == "classification"
        assert body["plan"]["models"]                                   # planner chose models
        ran = [x for x in body["results"] if x.get("metrics")]
        assert ran, body["results"]                                     # real components produced metrics
        assert all(x.get("run_id") for x in ran)                        # each is an Evidence-locked run
        assert body["summary"]["best_model"]                            # a verdict was produced
        # the FULL pipeline ran as Evidence-locked steps: eda -> leakage -> preprocess -> model(s) -> red_team
        step_kinds = {s["step"] for s in body["pipeline"]}
        assert {"eda", "leakage", "preprocess", "model"} <= step_kinds
        assert "redteam" in body and body["redteam"] is not None        # winner was stress-tested
        assert all("run_id" in s for s in body["pipeline"] if "error" not in s)
