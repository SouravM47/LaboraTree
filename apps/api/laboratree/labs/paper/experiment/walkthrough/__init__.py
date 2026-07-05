"""Walkthrough reconstruction — the paper's pipeline as an ordered node graph.

Nodes: data -> preprocess -> eda -> model -> result -> inference. Model nodes carry a suggested
`component_id` so a user can re-run (and fork) them under the Evidence Ledger.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

# Ordered longest/most-specific cues first so "logistic regression" doesn't match the generic
# "regression" rule. Boosted-tree / forest / SVM classifiers map to the gradient-boosting component
# (a faithful, registry-native stand-in) so common classification papers have something real to run.
MODEL_MAP: list[tuple[str, str]] = [
    ("logistic", "model.ml.logistic_regression"),
    ("probit", "model.econometrics.probit"),
    ("logit", "model.ml.logistic_regression"),
    ("sarima", "model.timeseries.sarima"),
    ("arima", "model.econometrics.arima"),
    ("holt", "model.timeseries.ets"),
    ("exponential smoothing", "model.timeseries.ets"),
    ("adaboost", "model.ml.adaboost"),
    ("ada boost", "model.ml.adaboost"),
    ("extra trees", "model.ml.extra_trees"),
    ("extremely randomized", "model.ml.extra_trees"),
    ("bagging", "model.ml.bagging"),
    ("xgboost", "model.ml.xgboost"),
    ("xgb", "model.ml.xgboost"),
    ("lightgbm", "model.ml.gradient_boosting"),
    ("catboost", "model.ml.gradient_boosting"),
    ("gradient boost", "model.ml.gradient_boosting"),
    ("gradient-boost", "model.ml.gradient_boosting"),
    ("gbm", "model.ml.gradient_boosting"),
    ("boost", "model.ml.gradient_boosting"),
    ("random forest", "model.ml.random_forest"),
    ("decision tree", "model.ml.decision_tree"),
    ("gbdt", "model.ml.gradient_boosting"),
    ("k-nearest", "model.ml.knn"),
    ("nearest neighbor", "model.ml.knn"),
    ("nearest neighbour", "model.ml.knn"),
    ("k-nn", "model.ml.knn"),
    ("knn", "model.ml.knn"),
    ("support vector", "model.ml.svm"),
    ("svm", "model.ml.svm"),
    ("svc", "model.ml.svm"),
    ("naive bayes", "model.ml.naive_bayes"),
    ("naïve bayes", "model.ml.naive_bayes"),
    ("transformer", "model.dl.transformer"),
    ("attention", "model.dl.transformer"),
    ("bert", "model.dl.transformer"),
    ("bidirectional lstm", "model.dl.rnn"),
    ("bi-lstm", "model.dl.rnn"),
    ("bilstm", "model.dl.rnn"),
    ("lstm", "model.dl.rnn"),
    ("gru", "model.dl.rnn"),
    ("cnn", "model.dl.cnn"),
    ("convolutional", "model.dl.cnn"),
    ("rnn", "model.dl.rnn"),
    ("recurrent", "model.dl.rnn"),
    ("neural network", "model.ml.mlp"),
    ("neural", "model.ml.mlp"),
    ("perceptron", "model.ml.mlp"),
    ("mlp", "model.ml.mlp"),
    ("deep learning", "model.ml.mlp"),
    ("hierarchical", "model.clustering.hierarchical"),
    ("agglomerative", "model.clustering.hierarchical"),
    ("spectral", "model.clustering.spectral"),
    ("k-means", "model.clustering.kmeans"),
    ("kmeans", "model.clustering.kmeans"),
    ("dbscan", "model.clustering.dbscan"),
    ("gaussian mixture", "model.clustering.gmm"),
    ("gmm", "model.clustering.gmm"),
    ("clustering", "model.clustering.kmeans"),
    ("isolation forest", "model.anomaly.isolation_forest"),
    ("local outlier", "model.anomaly.lof"),
    ("one-class svm", "model.anomaly.one_class_svm"),
    ("anomaly", "model.anomaly.isolation_forest"),
    ("outlier", "model.anomaly.isolation_forest"),
    ("poisson", "model.econometrics.poisson"),
    ("ols", "model.econometrics.ols"),
    ("elastic net", "model.ml.elastic_net"),
    ("elasticnet", "model.ml.elastic_net"),
    ("ridge", "model.ml.ridge"),
    ("lasso", "model.ml.lasso"),
    ("gaussian process", "model.ml.gaussian_process"),
    ("linear", "model.ml.linear_regression"),
    ("regression", "model.ml.linear_regression"),
]


# Model variants are the same component with different params (AR1/AR2 rule): a "GRU" or a
# "Bidirectional LSTM" is model.dl.rnn with its cell/bidirectional params set.
MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "bidirectional lstm": {"cell": "lstm", "bidirectional": True},
    "bi-lstm": {"cell": "lstm", "bidirectional": True},
    "bilstm": {"cell": "lstm", "bidirectional": True},
    "lstm": {"cell": "lstm"},
    "gru": {"cell": "gru"},
    "rnn": {"cell": "rnn"},
    "recurrent": {"cell": "rnn"},
}

# Truly unavailable architectures — the closest honest stand-in is the MLP.
_NEURAL_HINTS = ("autoencoder", "gan", "diffusion")


def standin_for(model_name: str) -> str:
    low = model_name.lower()
    if any(h in low for h in _NEURAL_HINTS):
        return "model.ml.mlp"
    return DEFAULT_STANDIN


# When a paper's model isn't in the registry (SVM, k-NN, a neural net, a custom model…), the user
# can still run a comparable, auto-task-detecting stand-in — flagged so the UI shows a caveat.
DEFAULT_STANDIN = "model.ml.gradient_boosting"


def _model_component(model_name: str) -> tuple[str, dict[str, Any]] | None:
    """Match a paper's model name to a registry component id + any variant params (cell type…)."""
    low = model_name.lower()
    for key, cid in MODEL_MAP:
        if key in low:
            return cid, dict(MODEL_PARAMS.get(key, {}))
    return None


def _name(x: Any) -> str:
    """Coerce a card field (may be a string or a {name,...} object) to its name."""
    return str(x.get("name", "")) if isinstance(x, dict) else str(x or "")


def _node(i: int, kind: str, title: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {"id": f"n{i}", "kind": kind, "title": title, "detail": detail, "source": "paper", **extra}


# Structured preprocessing operations the LLM classifies each funnel step into, so the UI renders the
# RIGHT animation instead of guessing from wording. "model_spec" = an estimation choice (fixed
# effects, clustered SEs, controls) that changes how the model is fit, not the data.
_PP_OPS = {
    "drop_missing_rows", "impute_mean", "impute_median", "standardize", "minmax", "encode",
    "filter_rows", "model_spec", "split", "none",
}
_PP_CMPS = {"lt", "le", "gt", "ge", "eq", "ne"}


def _apply_preprocess_op(node: dict[str, Any], item: dict[str, Any]) -> None:
    """Attach the LLM's structured op (+ filter) to a preprocess node, validated. The frontend trusts
    node['op'] and only falls back to text-parsing when it's absent."""
    op = str(item.get("op", "")).strip().lower()
    if op in _PP_OPS and op != "none":
        node["op"] = op
    filt = item.get("filter")
    if op == "filter_rows" and isinstance(filt, dict) and str(filt.get("cmp", "")).lower() in _PP_CMPS:
        try:
            node["filter"] = {
                "column": str(filt.get("column", "")).strip(),
                "cmp": str(filt["cmp"]).lower(),
                "value": float(filt.get("value")),
            }
        except (TypeError, ValueError):
            pass


def default_walkthrough(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic pipeline derived straight from the Paper Card (no LLM)."""
    steps: list[dict[str, Any]] = []
    i = 0

    sources = card.get("data_sources") or []
    steps.append(_node(i, "data", "Load data", ", ".join(sources) or "dataset(s) from the paper"))
    i += 1

    # Every preprocessing step the paper describes becomes a funnel node — the card/LLM already only
    # lists steps the paper actually performed, and each node's operation is classified downstream.
    for pp in card.get("preprocessing") or []:
        steps.append(_node(i, "preprocess", pp))
        i += 1

    ivs = [_name(v) for v in (card.get("independent_variables") or [])]
    target = _name(card.get("target_variable"))
    steps.append(_node(i, "eda", "Explore relationships",
                       f"Features {', '.join(ivs) if ivs else '—'} vs target '{target}'"))
    i += 1

    for model in card.get("models_used") or []:
        mname = _name(model)
        detail = model.get("summary", "") if isinstance(model, dict) else "Fit and evaluate"
        match = _model_component(mname)
        cid, extra = match if match else (None, {})
        # the paper's selected feature subset for this variant (e.g. the 13 BBO-picked attributes)
        subset = model.get("features_used") if isinstance(model, dict) else None
        if subset:
            extra = extra | {"features": [str(f) for f in subset]}
            detail = (detail + f" Uses only the {len(subset)} selected features: "
                      + ", ".join(str(f) for f in subset) + ".").strip()
        steps.append(_node(i, "model", mname, detail or "Fit and evaluate",
                           component_id=cid,
                           available=cid is not None,
                           suggested_component=cid or standin_for(mname),
                           params=({"target": target} if target else {}) | extra))
        i += 1

    steps.append(_node(i, "result", "Reported results", str(card.get("results") or "")))
    i += 1
    steps.append(_node(i, "inference", "Inference", str(card.get("inference") or "")))
    return steps


def _normalize_pipeline(steps: list[dict[str, Any]], card: dict[str, Any]) -> list[dict[str, Any]]:
    """Guarantee an EDA step sits BEFORE the first model, and demote any post-model 'eda' (e.g. a
    SHAP explanation the LLM tagged as EDA) to a result step — so 'EDA' always means pre-model
    exploration. Re-id nodes n0..nk afterwards."""
    model_idx = next((i for i, s in enumerate(steps) if s.get("kind") == "model"), None)
    if model_idx is not None:
        for i, s in enumerate(steps):
            if i >= model_idx and s.get("kind") == "eda":
                s["kind"] = "result"
        if not any(s.get("kind") == "eda" for s in steps[:model_idx]):
            ivs = [_name(v) for v in (card.get("independent_variables") or [])]
            target = _name(card.get("target_variable"))
            steps.insert(
                model_idx,
                _node(
                    0, "eda", "Exploratory data analysis",
                    f"Explore the {len(ivs)} features vs the target '{target}' before modeling.",
                ),
            )

    # Collapse to exactly ONE result node and ONE inference node — every 'result' node renders the
    # same paper-vs-ours comparison, so multiples are just noise. Keep the first of each; the single
    # result node carries the paper's reported results, the inference node the authors' conclusion.
    collapsed: list[dict[str, Any]] = []
    seen_result = seen_inference = False
    for s in steps:
        if s.get("kind") == "result":
            if seen_result:
                continue
            seen_result = True
            if not s.get("detail"):
                s["detail"] = str(card.get("results") or "")
        elif s.get("kind") == "inference":
            if seen_inference:
                continue
            seen_inference = True
            if not s.get("detail"):
                s["detail"] = str(card.get("inference") or "")
        collapsed.append(s)
    steps = collapsed

    for i, s in enumerate(steps):
        s["id"] = f"n{i}"
    return steps


def build_walkthrough(card: dict[str, Any], complete_fn: CompleteFn | None = None) -> list[dict[str, Any]]:
    """Build the walkthrough. With an LLM, refine node titles/details; always fall back to the
    deterministic card-derived pipeline on any error."""
    base = default_walkthrough(card)
    if complete_fn is None:
        return _normalize_pipeline(base, card)

    system = (
        "You reconstruct a research paper's pipeline as ordered steps. Return STRICT JSON: an array of "
        "{kind, title, detail, op?, filter?} where kind in [data, preprocess, eda, model, result, "
        "inference]. Keep it faithful and concise. Each detail must be plain everyday language that "
        "also says WHY the step is done (one sentence of what + one of why). "
        "For kind='preprocess', ALSO classify the operation as 'op', EXACTLY one of: "
        "drop_missing_rows | impute_mean | impute_median | standardize | minmax | encode | "
        "filter_rows | model_spec | split | none. "
        "Use 'model_spec' for ESTIMATION choices that do NOT change the data values (year/entity fixed "
        "effects, clustered or robust standard errors, control variables, survey weighting, interaction "
        "terms). Use 'filter_rows' when rows are KEPT or EXCLUDED by a rule (age cutoffs, marital "
        "status, inclusion criteria); for it add filter:{column, cmp, value} where cmp is one of "
        "lt,le,gt,ge,eq,ne and describes the condition for rows to REMOVE (e.g. 'keep age >= 18' → "
        "{column:'age', cmp:'lt', value:18}). Use 'split' for a train/test split. If a step does "
        "several things, pick the PRIMARY op."
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
                match = _model_component(node["title"])
                cid, extra = match if match else (None, {})
                node["component_id"] = cid
                node["available"] = cid is not None
                node["suggested_component"] = cid or standin_for(node["title"])
                node["params"] = {"target": _name(card.get("target_variable"))} | extra
            elif kind == "preprocess":
                _apply_preprocess_op(node, item)
            steps.append(node)
        return _normalize_pipeline(steps or base, card)
    except Exception:
        return _normalize_pipeline(base, card)
