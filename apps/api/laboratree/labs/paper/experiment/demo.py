"""LLM-generated demo dataset — synthesize realistic data from a paper's described variables.

Lets a user always proceed with the Experiment Lab even when the real dataset can't be fetched.
The target is made to genuinely depend on the features so models behave plausibly. Synthetic data
only approximates the paper — a caveat is surfaced wherever it's used.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

CAVEAT = (
    "Synthetic demo data generated from the paper's described variables. Results are approximate "
    "and will not exactly match the paper's reported numbers."
)


def _name(x: Any) -> str:
    return str(x.get("name", "")) if isinstance(x, dict) else str(x or "")


def _parse(raw: str) -> dict:
    text = raw.strip()
    s, e = text.find("{"), text.rfind("}")
    if 0 <= s < e:
        try:
            return json.loads(text[s : e + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _schema_hint(card: dict) -> str:
    lines = []
    for v in card.get("independent_variables") or []:
        if isinstance(v, dict):
            lines.append(f"- {v.get('name')}: {v.get('description', '')} (e.g. {v.get('example_value', '')})")
        else:
            lines.append(f"- {v}")
    tv = card.get("target_variable")
    if isinstance(tv, dict) and tv.get("name"):
        lines.append(f"- TARGET {tv.get('name')}: {tv.get('description', '')} (e.g. {tv.get('example_value', '')})")
    elif tv:
        lines.append(f"- TARGET {tv}")
    return "\n".join(lines)


_CLASSIFICATION_CUES = (
    "class", "status", "label", "disease", "diagnos", "churn", "fraud", "spam", "ckd",
    "positive", "category", "type", "outcome", "yes/no", "binary",
)


def _looks_categorical(card: dict, target: str) -> bool:
    tv = card.get("target_variable")
    blob = f"{target} {tv.get('description', '') if isinstance(tv, dict) else ''}".lower()
    if any(cue in blob for cue in _CLASSIFICATION_CUES):
        return True
    # a short non-numeric example value is a strong categorical signal
    ex = tv.get("example_value", "") if isinstance(tv, dict) else ""
    ex = str(ex).strip()
    return bool(ex) and not ex.replace(".", "", 1).replace("-", "", 1).isdigit()


def _num(x: Any) -> float | None:
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def _synthesize(card: dict, n_rows: int, target: str) -> dict[str, Any]:
    """Deterministic numpy synthesis with REALISTIC feature values (centered on each variable's
    example value) and a NOISY, MULTI-feature target — so a model must use several features, metrics
    aren't a trivial 100%, and correlations look realistic."""
    import numpy as np

    rng = np.random.default_rng(42)
    iv_objs = [v for v in (card.get("independent_variables") or []) if _name(v)]
    ivs = [_name(v) for v in iv_objs]
    if len(ivs) < 2:
        extra = [f"feature_{i + 1}" for i in range(3)]
        ivs = list(dict.fromkeys(ivs + extra))
        iv_objs = [{"name": x} for x in ivs]
    n = max(int(n_rows), 500)  # enough that dropna (from injected missingness) still leaves a solid set
    k = len(ivs)

    # realistic centre + spread per feature, from its example value
    centers, spreads = [], []
    for v in iv_objs[:k]:
        c = _num(v.get("example_value") if isinstance(v, dict) else None)
        c = 50.0 if c is None else c
        centers.append(c)
        spreads.append(max(1.0, abs(c) * 0.25))
    centers = np.array(centers)
    spreads = np.array(spreads)

    Z = rng.normal(size=(n, k))  # standardized latent features
    Xraw = centers + spreads * Z  # realistic-looking values
    # A handful of STRONG predictors among many pure-noise columns (like real data) — so models reach
    # a believable ~0.85 (not a trivial 1.0) and the tree branches on several features (not just one).
    strong_k = min(5, k)
    mag = np.zeros(k)
    idx = rng.choice(k, size=strong_k, replace=False)
    mag[idx] = rng.uniform(1.8, 3.0, size=strong_k)
    weights = np.sign(rng.normal(size=k)) * mag
    raw = Z @ weights
    raw = (raw - raw.mean()) / (raw.std() or 1.0)

    tname = target or "target"
    classif = _looks_categorical(card, target)
    tv = card.get("target_variable")
    pos = (str(tv.get("example_value", "")).strip() if isinstance(tv, dict) else "") or "yes"
    neg = f"not {pos}"
    if classif:
        # deterministic boundary + ~6% label-flip noise → a believable ~0.86 ceiling (not a fake 1.0)
        clean = raw > 0
        flip = rng.random(n) < 0.06
        yb = (clean ^ flip).astype(int)
    else:
        yv = np.round(50 + 12 * raw + rng.normal(scale=2.5, size=n), 2)

    # Inject light, realistic missingness into a few feature columns so the imputation step has
    # something to do (real clinical data like CKD is missing-heavy). Kept low + to few columns so
    # row-wise dropna still keeps most of the data for the models.
    miss_cols = ivs[: min(3, k)]
    miss = rng.random((n, len(miss_cols))) < 0.08

    records: list[dict[str, Any]] = []
    for i in range(n):
        row = {name: round(float(Xraw[i, j]), 2) for j, name in enumerate(ivs)}
        for mj, mc in enumerate(miss_cols):
            if miss[i, mj]:
                row[mc] = None  # → empty CSV cell → NaN → imputed later
        row[tname] = (pos if yb[i] else neg) if classif else float(yv[i])
        records.append(row)
    return {"columns": ivs + [tname], "records": records, "target": tname, "caveat": CAVEAT}


def generate_demo_dataset(
    paper_text: str, card: dict, n_rows: int, complete_fn: CompleteFn
) -> dict[str, Any]:
    """Deterministic, tunable synthetic data. We use the numpy synthesizer (not the LLM) so the data
    has realistic values, friendly class labels, and a genuine multi-feature signal — which the EDA
    charts and model animations depend on."""
    target = _name(card.get("target_variable")) or "target"
    return _synthesize(card, n_rows, target)
