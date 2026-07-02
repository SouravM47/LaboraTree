"""Walkthrough reconstruction — the paper's pipeline as an ordered node graph.

Nodes: data -> preprocess -> eda -> model -> result -> inference. Model nodes carry a suggested
`component_id` so a user can re-run (and fork) them under the Evidence Ledger.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

MODEL_MAP = {
    "logistic": "model.ml.logistic_regression",
    "logit": "model.ml.logistic_regression",
    "linear": "model.ml.linear_regression",
    "ols": "model.ml.linear_regression",
    "regression": "model.ml.linear_regression",
}


def _model_component(model_name: str) -> str | None:
    low = model_name.lower()
    for key, cid in MODEL_MAP.items():
        if key in low:
            return cid
    return None


def _node(i: int, kind: str, title: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {"id": f"n{i}", "kind": kind, "title": title, "detail": detail, "source": "paper", **extra}


def default_walkthrough(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic pipeline derived straight from the Paper Card (no LLM)."""
    steps: list[dict[str, Any]] = []
    i = 0

    sources = card.get("data_sources") or []
    steps.append(_node(i, "data", "Load data", ", ".join(sources) or "dataset(s) from the paper"))
    i += 1

    for pp in card.get("preprocessing") or []:
        steps.append(_node(i, "preprocess", pp))
        i += 1

    ivs = card.get("independent_variables") or []
    target = card.get("target_variable") or ""
    steps.append(_node(i, "eda", "Explore relationships",
                       f"Features {', '.join(ivs) if ivs else '—'} vs target '{target}'"))
    i += 1

    for model in card.get("models_used") or []:
        cid = _model_component(model)
        steps.append(_node(i, "model", model, "Fit and evaluate",
                           component_id=cid, params={"target": target} if target else {}))
        i += 1

    steps.append(_node(i, "result", "Reported results", str(card.get("results") or "")))
    i += 1
    steps.append(_node(i, "inference", "Inference", str(card.get("inference") or "")))
    return steps


def build_walkthrough(card: dict[str, Any], complete_fn: CompleteFn | None = None) -> list[dict[str, Any]]:
    """Build the walkthrough. With an LLM, refine node titles/details; always fall back to the
    deterministic card-derived pipeline on any error."""
    base = default_walkthrough(card)
    if complete_fn is None:
        return base

    system = (
        "You reconstruct a research paper's pipeline as ordered steps. Return STRICT JSON: an array "
        "of {kind, title, detail} where kind in [data, preprocess, eda, model, result, inference]. "
        "Keep it faithful and concise."
    )
    try:
        raw = complete_fn(system, json.dumps(card)[:12000])
        body = raw.strip()
        s, e = body.find("["), body.rfind("]")
        if not (0 <= s < e):
            return base
        parsed = json.loads(body[s : e + 1])
        steps: list[dict[str, Any]] = []
        for idx, item in enumerate(parsed):
            kind = str(item.get("kind", "data"))
            node = _node(idx, kind, str(item.get("title", "")), str(item.get("detail", "")))
            if kind == "model":
                node["component_id"] = _model_component(node["title"])
                node["params"] = {"target": card.get("target_variable") or ""}
            steps.append(node)
        return steps or base
    except Exception:
        return base
