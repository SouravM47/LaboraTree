"""Data Hunt — find datasets on the open web to empirically test a hypothesis.

Given a hypothesis (and, ideally, the measurable variables the Evidence Hunt surfaced), this plans
dataset-focused web queries, searches (Brave→SerpAPI via core/search), then has the LLM judge which
results are actual downloadable datasets (not papers/blogs), how relevant each is to the variables,
and whether it looks directly downloadable. Returns ranked candidates the user can pull into a project.

All dependencies are injectable, so it runs fully offline in tests. Search misses degrade to [].
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from ...core.llm.context import use_llm_operation
from ...core.search import looks_like_data_url
from .evidence import _parse_json  # shared tolerant JSON extractor (same Lab)

log = logging.getLogger(__name__)

CompleteFn = Callable[..., str]
SearchFn = Callable[[str, int], list[Any]]

MAX_CANDIDATES = 10
QUERIES = 4

# Repositories worth steering queries toward — where downloadable data actually lives.
_REPO_HINT = "(site:data.gov OR site:kaggle.com OR site:data.worldbank.org OR ourworldindata.org OR UCI OR Zenodo)"


def plan_data_queries(
    hypothesis: str, variables: list[str], complete_fn: CompleteFn, n: int = QUERIES
) -> list[str]:
    """LLM proposes dataset-finding queries covering the variables + likely sources; robust fallback."""
    var_txt = ", ".join(variables) if variables else "the variables implied by the hypothesis"
    system = (
        "You plan web searches to FIND DOWNLOADABLE DATASETS (not articles) to empirically test a "
        "research hypothesis. Favor official statistics and data repositories (data.gov, World Bank, "
        "Our World in Data, UCI, Kaggle, Zenodo, national statistics offices). Return ONLY a JSON "
        f"array of {n} short query strings covering the variables: {var_txt}."
    )
    try:
        with use_llm_operation("data_hunt.plan_queries"):
            parsed = _parse_json(complete_fn(system, f"Hypothesis: {hypothesis}"))
        queries = [str(q).strip() for q in parsed if str(q).strip()] if isinstance(parsed, list) else []
    except Exception as exc:
        log.info("data query planning failed: %s", exc)
        queries = []
    if not queries:
        base = variables or [hypothesis]
        queries = [f"{v} dataset download {_REPO_HINT}" for v in base]
    return queries[:n]


def _collect(queries: list[str], search_fn: SearchFn, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    hits: list[dict[str, Any]] = []
    for q in queries:
        try:
            results = search_fn(q, 8)
        except Exception as exc:
            log.info("data search failed for %r: %s", q, exc)
            continue
        for h in results:
            url = getattr(h, "url", "") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            hits.append({
                "title": getattr(h, "title", "") or url,
                "url": url,
                "snippet": getattr(h, "description", "") or "",
                "source": urlparse(url).netloc.lower(),
                "query": q,
            })
            if len(hits) >= limit * 2:  # gather extra; the LLM filters down to real datasets
                return hits
    return hits


def _annotate(
    hypothesis: str, variables: list[str], hits: list[dict[str, Any]], complete_fn: CompleteFn
) -> list[dict[str, Any]]:
    """LLM marks each hit: is it a real dataset, how relevant, which variables it covers, access type."""
    if not hits:
        return []
    numbered = "\n".join(f"[{i + 1}] {h['title']}\n    {h['url']}\n    {h['snippet'][:200]}"
                         for i, h in enumerate(hits))
    system = (
        "You are a data-sourcing expert. For each numbered search result decide whether it is an "
        "actual DOWNLOADABLE DATASET (not a paper, news article, or blog) that could help test the "
        "hypothesis. Return ONLY a JSON array of objects: {index (1-based int), is_dataset (bool), "
        "relevance (0-1 float, how well it fits the variables), why (short reason), "
        "variables_covered (array of strings), access ('direct_download'|'portal'|'unknown')}. "
        "Judge ALL results."
    )
    var_txt = ", ".join(variables) if variables else "(infer from the hypothesis)"
    with use_llm_operation("data_hunt.annotate"):
        parsed = _parse_json(complete_fn(system, f"Hypothesis: {hypothesis}\nVariables: {var_txt}\n\n{numbered}"))
    by_index: dict[int, dict] = {}
    if isinstance(parsed, list):
        for a in parsed:
            if isinstance(a, dict) and isinstance(a.get("index"), int):
                by_index[a["index"]] = a

    candidates: list[dict[str, Any]] = []
    for i, h in enumerate(hits, 1):
        a = by_index.get(i, {})
        # keep anything the LLM called a dataset, or that clearly points at a data file
        direct = looks_like_data_url(h["url"])
        is_dataset = bool(a.get("is_dataset")) or direct
        if not is_dataset:
            continue
        candidates.append({
            **h,
            "relevance": round(float(a.get("relevance", 0.5) or 0.5), 2),
            "why_relevant": str(a.get("why", "")),
            "variables_covered": a.get("variables_covered") or [],
            "access": a.get("access") or ("direct_download" if direct else "unknown"),
            "direct_download": direct,
        })
    candidates.sort(key=lambda c: (-c["relevance"], not c["direct_download"]))
    return candidates


def hunt_datasets(
    hypothesis: str,
    variables: list[str] | None = None,
    *,
    search_fn: SearchFn,
    complete_fn: CompleteFn,
    max_candidates: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    """Full data hunt: plan dataset queries -> search -> LLM-annotate/rank. Returns {hypothesis,
    variables, queries, candidates}. Best-effort — never raises for search/LLM hiccups."""
    variables = variables or []
    queries = plan_data_queries(hypothesis, variables, complete_fn)
    hits = _collect(queries, search_fn, max_candidates)
    candidates = _annotate(hypothesis, variables, hits, complete_fn)[:max_candidates]
    return {"hypothesis": hypothesis, "variables": variables, "queries": queries, "candidates": candidates}
