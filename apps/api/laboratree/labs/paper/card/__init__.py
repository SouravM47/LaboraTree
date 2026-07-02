"""Paper Card — a plain-language, structured summary of a research paper."""

from __future__ import annotations

import json
from collections.abc import Callable

CompleteFn = Callable[[str, str], str]

MAX_CHARS = 14000  # keep prompt within context

CARD_FIELDS = [
    "problem_statement",
    "models_used",
    "data_sources",
    "preprocessing",
    "data_sample",
    "independent_variables",
    "target_variable",
    "variants",
    "math",            # list of {formula, explanation}
    "results",
    "inference",
]

_SYSTEM = (
    "You are a research explainer. Read the paper and produce a Paper Card as STRICT JSON. "
    "Write for a smart non-specialist: plain language, no jargon without a one-line gloss. "
    "For every mathematical formula, add a beginner-friendly explanation so someone unfamiliar "
    "with the math still understands what it does and why."
)

_INSTRUCTION = (
    "Return ONLY a JSON object with these keys:\n"
    "- problem_statement (string, simple)\n"
    "- models_used (array of strings)\n"
    "- data_sources (array of strings)\n"
    "- preprocessing (array of short strings; the preprocessing funnel)\n"
    "- data_sample (string; size/shape/description)\n"
    "- independent_variables (array of strings)\n"
    "- target_variable (string)\n"
    "- variants (array of strings; model variants like AR1/AR2 if any)\n"
    "- math (array of objects {formula, explanation}; explanation is beginner-friendly)\n"
    "- results (string, simple)\n"
    "- inference (string; what it means, simple)\n"
    "Use empty arrays/strings when unknown. Do not invent numbers."
)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"raw": raw}
    except json.JSONDecodeError:
        # last resort: grab the outermost {...}
        s, e = text.find("{"), text.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
        return {"raw": raw, "parse_error": True}


def normalize_card(card: dict) -> dict:
    """Ensure all expected fields exist so the UI can render a stable shape."""
    out = dict(card)
    for f in CARD_FIELDS:
        out.setdefault(f, [] if f in {"models_used", "data_sources", "preprocessing",
                                      "independent_variables", "variants", "math"} else "")
    return out


def generate_card(text: str, complete_fn: CompleteFn) -> dict:
    prompt = f"{_INSTRUCTION}\n\n=== PAPER TEXT ===\n{text[:MAX_CHARS]}"
    raw = complete_fn(_SYSTEM, prompt)
    return normalize_card(_parse_json(raw))
