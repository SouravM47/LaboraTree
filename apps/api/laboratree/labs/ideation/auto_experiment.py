"""Auto-Experiment — the 'skill selection' brain of the Ideation deep agent.

Pure, injectable, offline-testable. Given a dataset profile it decides *how* to run the experiment
(task, preprocessing, which candidate models to try, and why); after the API layer runs those real
registry components under the Evidence Ledger, it reads the metrics and writes a grounded verdict +
insights. The DB-touching orchestration (running components, tracking runs) lives in the API layer so
this Lab stays isolated — this module only reasons.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ...core.llm.context import use_llm_operation
from .evidence import _parse_json

log = logging.getLogger(__name__)

CompleteFn = Callable[..., str]

# Supervised tabular models that share the {dataset, params.target} contract — safe auto-run pool.
CLASSIFIERS = ["model.ml.logistic_regression", "model.ml.random_forest", "model.ml.gradient_boosting"]
REGRESSORS = ["model.ml.linear_regression", "model.ml.random_forest", "model.ml.gradient_boosting"]

# Metric to rank by, per task (higher is better).
PRIMARY_METRIC = {"classification": ["f1", "accuracy", "auc"], "regression": ["r2"]}


def profile_dataset(df, target: str) -> dict[str, Any]:
    """Compact profile for the planner: shape, target, per-column dtype + missingness."""
    import pandas as pd

    cols = []
    for c in df.columns:
        s = df[c]
        cols.append({
            "name": str(c),
            "dtype": "numeric" if pd.api.types.is_numeric_dtype(s) else "categorical",
            "missing_pct": round(100 * float(s.isna().mean()), 1),
            "unique": int(s.nunique(dropna=True)),
        })
    return {"n_rows": int(len(df)), "n_cols": int(df.shape[1]), "target": target, "columns": cols}


def detect_task(df, target: str) -> str:
    """Deterministic task detection (mirrors the modeling prep): a numeric target with many distinct
    values is regression; otherwise classification."""
    import pandas as pd

    if target not in df.columns:
        return "classification"
    s = df[target]
    return "regression" if (pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 10) else "classification"


def plan_experiment(
    profile: dict[str, Any],
    hypothesis: str,
    task: str,
    available_models: list[str],
    complete_fn: CompleteFn,
) -> dict[str, Any]:
    """LLM 'skill selection': pick the 2-3 best-suited candidate models + a preprocessing approach for
    this data/task, with a rationale. Always returns a valid plan (falls back to sensible defaults)."""
    pool = [m for m in (CLASSIFIERS if task == "classification" else REGRESSORS) if m in available_models]
    if not pool:  # registry differs — use whatever supervised ml models are available
        pool = [m for m in available_models if m.startswith("model.ml.")][:3]
    default = {
        "preprocessing": "impute missing values, then standardize numeric features",
        "models": pool[:3],
        "rationale": "Default supervised baseline for the detected task.",
    }
    system = (
        "You are an ML strategist choosing how to test a hypothesis on a dataset. Given the profile "
        f"and task ({task}), pick the 2-3 MOST suitable models from the AVAILABLE list and a short "
        "preprocessing plan. Return ONLY JSON {preprocessing: str, models: [component_ids from the "
        "available list], rationale: str}."
    )
    prompt = (
        f"Hypothesis: {hypothesis}\nTask: {task}\nAvailable models: {available_models}\n"
        f"Profile: {profile}"
    )
    try:
        with use_llm_operation("auto_experiment.plan"):
            parsed = _parse_json(complete_fn(system, prompt))
    except Exception as exc:
        log.info("plan_experiment failed: %s", exc)
        parsed = None
    if not isinstance(parsed, dict):
        return default
    models = [m for m in (parsed.get("models") or []) if m in available_models]
    if not models:
        models = default["models"]
    return {
        "preprocessing": str(parsed.get("preprocessing") or default["preprocessing"]),
        "models": models[:3],
        "rationale": str(parsed.get("rationale") or default["rationale"]),
    }


def _metric_value(metrics: dict[str, Any], task: str) -> float:
    for key in PRIMARY_METRIC.get(task, []):
        if key in metrics and isinstance(metrics[key], (int, float)):
            return float(metrics[key])
    # fall back to the first numeric metric
    for v in metrics.values():
        if isinstance(v, (int, float)):
            return float(v)
    return float("-inf")


def rank_results(results: list[dict[str, Any]], task: str) -> list[dict[str, Any]]:
    """Sort candidate runs best-first by the task's primary metric."""
    return sorted(results, key=lambda r: -_metric_value(r.get("metrics") or {}, task))


def summarize_results(
    hypothesis: str,
    task: str,
    results: list[dict[str, Any]],
    complete_fn: CompleteFn,
    notes: str = "",
) -> dict[str, Any]:
    """Read the real per-model metrics (and any trust notes — leakage findings, red-team verdict) and
    write a grounded verdict + insights for the hypothesis. Deterministic fallback picks the best
    model by the primary metric."""
    ranked = rank_results(results, task)
    best = ranked[0]["component"] if ranked else ""
    if not results:
        return {"best_model": "", "verdict": "No models were run.", "insights": []}
    system = (
        "You are a research analyst. Given several models and their REAL metrics on data used to test "
        "the hypothesis (plus any leakage/robustness notes), state which performed best and what it "
        "implies for the hypothesis — be honest that predictive fit is not causal proof, and factor in "
        "any leakage or robustness warnings. Return ONLY JSON {best_model (component id), verdict "
        "(2-3 sentences), insights (array of short strings)}."
    )
    lines = "\n".join(f"- {r['component']}: {r.get('metrics')}" for r in ranked)
    trust = f"\nTrust checks:\n{notes}" if notes else ""
    try:
        with use_llm_operation("auto_experiment.summarize"):
            parsed = _parse_json(
                complete_fn(system, f"Hypothesis: {hypothesis}\nTask: {task}\nResults:\n{lines}{trust}")
            )
    except Exception as exc:
        log.info("summarize_results failed: %s", exc)
        parsed = None
    if not isinstance(parsed, dict):
        return {"best_model": best, "verdict": f"Best model by primary metric: {best}.", "insights": []}
    return {
        "best_model": parsed.get("best_model") or best,
        "verdict": str(parsed.get("verdict") or ""),
        "insights": [str(s) for s in (parsed.get("insights") or [])],
    }
