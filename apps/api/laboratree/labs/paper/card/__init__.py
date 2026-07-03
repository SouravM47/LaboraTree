"""Paper Card — an adaptive, plain-language summary of a research paper.

The agent first classifies the paper as **empirical** (data/models/experiments) or **conceptual**
(review/theory/framework), then produces the matching card:
  * empirical  -> a structured card; variables and models carry a description + a realistic example
  * conceptual -> a segmented, analogy-rich wholesome summary that preserves detail
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

MAX_CHARS = 14000


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
        s, e = text.find("{"), text.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                pass
        return {"raw": raw, "parse_error": True}


# ---------------- classification ----------------

def classify_paper(text: str, complete_fn: CompleteFn) -> str:
    system = (
        "Classify the research paper. 'empirical' = uses data, models, experiments, or math. "
        "'conceptual' = review, theory, framework, or position paper with no empirical model. "
        "Reply with ONLY one word: empirical or conceptual."
    )
    raw = complete_fn(system, text[:6000]).strip().lower()
    return "conceptual" if "conceptual" in raw else "empirical"


# ---------------- empirical ----------------

_EMPIRICAL_SYSTEM = (
    "You are a research explainer. Produce a Paper Card as STRICT JSON for a smart non-specialist: "
    "plain language, no unexplained jargon. For every math formula add a beginner-friendly "
    "explanation. For each variable, give a one-line description of what it actually is and a "
    "realistic example value."
)

_EMPIRICAL_INSTRUCTION = (
    "Return ONLY a JSON object with keys:\n"
    "- paper_type: 'empirical'\n"
    "- problem_statement: {one_liner (<=20 words), plain (2-3 simple sentences)}\n"
    "- models_used: array of {name, summary}\n"
    "- data_sources: array of strings\n"
    "- preprocessing: array of short strings (the preprocessing funnel)\n"
    "- data_sample: string (size/shape/description)\n"
    "- independent_variables: array of {name, description, example_value}\n"
    "- target_variable: {name, description, example_value}\n"
    "- variants: array of strings (e.g. AR1/AR2 if any)\n"
    "- math: array of {formula, explanation} (explanation is beginner-friendly)\n"
    "- results: string (simple)\n"
    "- inference: string (what it means, simple)\n"
    "Use empty arrays/strings/objects when unknown. Do not invent numbers."
)


def generate_empirical_card(text: str, complete_fn: CompleteFn) -> dict:
    raw = complete_fn(_EMPIRICAL_SYSTEM, f"{_EMPIRICAL_INSTRUCTION}\n\n=== PAPER TEXT ===\n{text[:MAX_CHARS]}")
    return normalize_card(_parse_json(raw))


def _var(v: Any) -> dict:
    if isinstance(v, dict):
        return {"name": str(v.get("name", "")), "description": str(v.get("description", "")),
                "example_value": str(v.get("example_value", ""))}
    return {"name": str(v), "description": "", "example_value": ""}


def _model(m: Any) -> dict:
    if isinstance(m, dict):
        return {"name": str(m.get("name", "")), "summary": str(m.get("summary", ""))}
    return {"name": str(m), "summary": ""}


def _problem(ps: Any) -> dict:
    if isinstance(ps, dict):
        return {"one_liner": str(ps.get("one_liner", "")), "plain": str(ps.get("plain", ""))}
    return {"one_liner": "", "plain": str(ps or "")}


def normalize_card(card: dict) -> dict:
    """Empirical card — stable shape, backward-compatible with legacy string fields."""
    out = dict(card)
    out["paper_type"] = "empirical"
    out["problem_statement"] = _problem(out.get("problem_statement"))
    for f in ("data_sources", "preprocessing", "variants", "math"):
        out.setdefault(f, [])
    out.setdefault("data_sample", "")
    out.setdefault("results", "")
    out.setdefault("inference", "")
    out["independent_variables"] = [_var(v) for v in out.get("independent_variables", [])]
    out["models_used"] = [_model(m) for m in out.get("models_used", [])]
    tv = out.get("target_variable")
    out["target_variable"] = _var(tv) if tv else {"name": "", "description": "", "example_value": ""}
    return out


# ---------------- conceptual ----------------

_CONCEPTUAL_SYSTEM = (
    "You explain conceptual / review / theory papers so ANY reader understands them fully. Preserve "
    "all key details, but use simple language, concrete examples, and relatable analogies."
)

_CONCEPTUAL_INSTRUCTION = (
    "Return ONLY a JSON object with keys:\n"
    "- paper_type: 'conceptual'\n"
    "- one_liner: string (<=20 words, the core idea)\n"
    "- problem_statement: {one_liner, plain}\n"
    "- segments: array of {heading, body, analogy} covering at least Core idea, Key concepts, "
    "Main arguments/contributions, Examples, and Implications. body is simple but detailed; "
    "analogy is a short relatable comparison (may be empty).\n"
    "- glossary: array of {term, definition}\n"
    "- takeaways: array of strings\n"
    "Be faithful and complete — do not omit important details."
)


def _segment(s: Any) -> dict:
    if isinstance(s, dict):
        return {"heading": str(s.get("heading", "")), "body": str(s.get("body", "")),
                "analogy": str(s.get("analogy", "")) or ""}
    return {"heading": "", "body": str(s), "analogy": ""}


def normalize_conceptual(card: dict) -> dict:
    out = dict(card)
    out["paper_type"] = "conceptual"
    out.setdefault("one_liner", "")
    out["problem_statement"] = _problem(out.get("problem_statement") or out.get("one_liner", ""))
    out["segments"] = [_segment(s) for s in out.get("segments", [])]
    out["glossary"] = [
        {"term": str(g.get("term", "")), "definition": str(g.get("definition", ""))}
        for g in out.get("glossary", []) if isinstance(g, dict)
    ]
    out["takeaways"] = [str(t) for t in out.get("takeaways", [])]
    return out


def generate_conceptual_card(text: str, complete_fn: CompleteFn) -> dict:
    raw = complete_fn(_CONCEPTUAL_SYSTEM, f"{_CONCEPTUAL_INSTRUCTION}\n\n=== PAPER TEXT ===\n{text[:MAX_CHARS]}")
    return normalize_conceptual(_parse_json(raw))


# ---------------- orchestrator ----------------

def generate_card(text: str, complete_fn: CompleteFn) -> dict:
    """Classify then generate the matching card. Returns a dict with `paper_type`."""
    if classify_paper(text, complete_fn) == "conceptual":
        return generate_conceptual_card(text, complete_fn)
    return generate_empirical_card(text, complete_fn)
