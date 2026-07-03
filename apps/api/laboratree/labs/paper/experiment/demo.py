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


def generate_demo_dataset(
    paper_text: str, card: dict, n_rows: int, complete_fn: CompleteFn
) -> dict[str, Any]:
    ivs = [_name(v) for v in (card.get("independent_variables") or [])]
    target = _name(card.get("target_variable"))
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
    parsed = _parse(complete_fn(system, instruction))
    columns = parsed.get("columns") or (ivs + ([target] if target else []))
    rows = [r for r in (parsed.get("rows") or []) if isinstance(r, dict)][: max(n_rows * 3, 300)]
    return {"columns": columns, "records": rows, "target": target, "caveat": CAVEAT}
