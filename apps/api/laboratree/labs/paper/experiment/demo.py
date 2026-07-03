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


def _synthesize(card: dict, n_rows: int, target: str) -> dict[str, Any]:
    """Deterministic numpy synthesis — always produces a usable dataset where the target genuinely
    depends on the features. Used as a fallback (and safety net) for the LLM generator."""
    import numpy as np

    rng = np.random.default_rng(42)
    ivs = [_name(v) for v in (card.get("independent_variables") or []) if _name(v)]
    # Guarantee at least a couple of features so a model has something to learn.
    if len(ivs) < 2:
        ivs = list(dict.fromkeys(ivs + [f"feature_{i + 1}" for i in range(3)]))
    n = max(int(n_rows), 30)

    X = rng.normal(size=(n, len(ivs)))
    weights = rng.normal(size=len(ivs))
    latent = X @ weights + rng.normal(scale=0.5, size=n)

    tname = target or "target"
    records: list[dict[str, Any]] = []
    if _looks_categorical(card, target):
        probs = 1.0 / (1.0 + np.exp(-latent))
        y = (probs > 0.5).astype(int)
    else:
        y = np.round(50 + 10 * latent, 2)

    for i in range(n):
        row = {name: round(float(X[i, j]), 3) for j, name in enumerate(ivs)}
        row[tname] = int(y[i]) if _looks_categorical(card, target) else float(y[i])
        records.append(row)
    return {"columns": ivs + [tname], "records": records, "target": tname, "caveat": CAVEAT}


def generate_demo_dataset(
    paper_text: str, card: dict, n_rows: int, complete_fn: CompleteFn
) -> dict[str, Any]:
    ivs = [_name(v) for v in (card.get("independent_variables") or [])]
    target = _name(card.get("target_variable")) or "target"
    system = (
        "You generate a realistic SYNTHETIC tabular dataset to pre-test a paper reproduction. Make "
        "the target genuinely depend on the features (so a model trained on it behaves plausibly). "
        "Honor any sample size, ranges, or distributions the paper mentions. Return ONLY JSON."
    )
    instruction = (
        f'Return ONLY JSON: {{"columns": [...], "rows": [{{"col": value}}, ...]}} with ~{n_rows} rows.\n'
        f"Columns = the feature names plus the target; use numeric values where appropriate.\n"
        f"Variables:\n{_schema_hint(card)}\n\n=== PAPER (excerpt) ===\n{paper_text[:4000]}"
    )
    try:
        parsed = _parse(complete_fn(system, instruction))
    except Exception:
        parsed = {}
    columns = parsed.get("columns") or (ivs + ([target] if target else []))
    rows = [r for r in (parsed.get("rows") or []) if isinstance(r, dict)][: max(n_rows * 3, 300)]

    # Safety net: the LLM can truncate/omit rows (long JSON) — never hand back an empty dataset.
    if len(rows) < 10:
        return _synthesize(card, n_rows, target)
    return {"columns": columns, "records": rows, "target": target, "caveat": CAVEAT}
