"""Paper Card — an adaptive, plain-language summary of a research paper.

The agent first classifies the paper as **empirical** (data/models/experiments) or **conceptual**
(review/theory/framework), then produces the matching card:
  * empirical  -> a structured card; variables and models carry a description + a realistic example
  * conceptual -> a segmented, analogy-rich wholesome summary that preserves detail
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

MAX_CHARS = 26000


def _parse_json(raw: str) -> dict:
    # Robust to prose, code fences, AND truncated output (a big empirical card can exceed the token
    # budget and get cut off mid-object — the lenient parser closes the open brackets so it survives).
    from ....core.jsonparse import loads_lenient

    data = loads_lenient(raw)
    return data if isinstance(data, dict) else {"raw": raw, "parse_error": True}


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
    "plain language, no unexplained jargon. The goal: someone with NO modeling or math background "
    "should fully understand this paper in ~15 minutes from your card alone — every step should also "
    "say WHY it is done, not just what. Write the problem statement and detailed summary so a "
    "curious 12-year-old could follow them. Attach math to the SPECIFIC model that uses it, and always "
    "work the example using the paper's actual feature names and example values — never generic "
    "placeholders. Define every symbol and read each equation in plain words. For each variable, give a "
    "one-line description of what it actually is and a realistic example value. Be COMPLETE: when the "
    "paper lists attributes/features in a table or enumeration, extract every one of them — do not "
    "summarize, sample, or collapse the list."
)

_EMPIRICAL_INSTRUCTION = (
    "Return ONLY a JSON object with keys:\n"
    "- paper_type: 'empirical'\n"
    "- problem_statement: {one_liner (<=20 words), plain} where plain is EXPLAIN-LIKE-I'M-5 simple: "
    "2-4 short everyday sentences that clearly state WHAT the authors are trying to predict or decide, "
    "and WHAT information they use to do it (name the kind of inputs/features and the data). Zero "
    "jargon; spell out any acronym in plain words.\n"
    "- detailed_summary: a thorough but plain-English summary of the WHOLE study — what problem, what "
    "data, what they did, and what they found — 4-8 simple sentences anyone can follow.\n"
    "- models_used: array of {name, summary, universal, use_case, example, result, math, "
    "features_used} where:\n"
    "    * features_used = array of the EXACT attribute abbreviations this model/variant trains on, "
    "when the paper limits it to a subset (e.g. the 13 BBO-selected attributes for 'XGBoost with "
    "BBO': ['al','pcc','ba','bu','sod','pot','hemo','pcv','wc','htn','dm','appet','ane']); empty "
    "array when it uses all features. If a model appears twice (all features vs selected subset), "
    "emit TWO entries with their own features_used.\n"
    "    * summary = what THIS paper does with the model (1-2 sentences),\n"
    "    * universal = a model-agnostic plain explanation of what this kind of model is and how it "
    "works in general (2-3 sentences, no reference to this paper),\n"
    "    * use_case = a common real-world practical use case for this model type,\n"
    "    * example = a concrete worked mini-example a beginner can picture,\n"
    "    * result = in PLAIN ENGLISH, how THIS model performed in the paper — its accuracy and other "
    "scores and what they mean (e.g. 'scored 99.16% accuracy and 100% precision — almost never wrong'). "
    "Empty string if the paper gives no numbers for it.\n"
    "    * math = array of {formula, plain, symbols, worked_example} for the formula(s) THIS model uses "
    "(only if the paper states them; else []). plain = read it in words; symbols = define EVERY symbol, "
    "one per line as 'symbol = meaning'; worked_example = a SUPER-EASY step-by-step calculation that "
    "PLUGS IN this paper's REAL feature names and their example values (from independent_variables / "
    "target_variable) and shows the numeric result — concrete, not abstract.\n"
    "- best_model: if multiple models are compared, the name of the best one plus one plain sentence on "
    "why (e.g. 'XGBoost — highest accuracy at 99.16%'). Empty string if only one model.\n"
    "- data_sources: array of strings\n"
    "- preprocessing: array of short strings (the preprocessing funnel). Each string states the step "
    "AND, after an em-dash, WHY it is needed in everyday words (e.g. 'Fill missing values with the "
    "column mean — models can't use rows with holes, and this keeps the row without inventing "
    "extreme values').\n"
    "- data_sample: string (size/shape/description)\n"
    "- independent_variables: array of {name, description, example_value, type, units} — list EVERY "
    "feature / attribute / predictor the paper uses. description = what this measurement actually IS "
    "in everyday words AND why a doctor/analyst would care about it (one line, e.g. 'hemoglobin — the "
    "oxygen-carrying protein in blood; low values suggest anemia, common in kidney disease'). type = "
    "plain data type (Integer, Real, Categorical, Binary, Nominal, Text...); units = measurement unit "
    "if any (e.g. mg/dL, years, '' if none). If the paper has an attribute/feature table, include ONE "
    "entry per row. Do NOT truncate or summarize; completeness matters more than brevity (papers "
    "often have 10-50 features).\n"
    "- target_variable: {name, description, example_value, type, units}\n"
    "- variants: array of {name, description} — each distinct configuration the paper evaluates "
    "(e.g. different feature subsets, data splits, or model settings). description = one plain line on "
    "what makes it different and its headline result if the paper gives one (e.g. 'Set 3 = 9 features "
    "picked by BBO from Set 1; ~98.7% accuracy'). Empty array if none.\n"
    "- results: string (simple)\n"
    "- inference: string (what it means, simple)\n"
    "Use empty arrays/strings/objects when unknown. Do not invent numbers."
)


def generate_empirical_card(text: str, complete_fn: CompleteFn) -> dict:
    raw = complete_fn(_EMPIRICAL_SYSTEM, f"{_EMPIRICAL_INSTRUCTION}\n\n=== PAPER TEXT ===\n{text[:MAX_CHARS]}")
    return normalize_card(_parse_json(raw))


def _var(v: Any) -> dict:
    if isinstance(v, dict):
        return {
            "name": str(v.get("name", "")),
            "description": str(v.get("description", "")),
            "example_value": str(v.get("example_value", "")),
            "type": str(v.get("type", "")),
            "units": str(v.get("units", "")),
        }
    return {"name": str(v), "description": "", "example_value": "", "type": "", "units": ""}


def _model(m: Any) -> dict:
    if isinstance(m, dict):
        return {
            "name": str(m.get("name", "")),
            "summary": str(m.get("summary", "")),
            "universal": str(m.get("universal", "")),
            "use_case": str(m.get("use_case", "")),
            "example": str(m.get("example", "")),
            "result": str(m.get("result", "")),
            "math": [_math(x) for x in (m.get("math") or [])],
            "features_used": [str(f) for f in (m.get("features_used") or []) if str(f).strip()],
        }
    return {
        "name": str(m), "summary": "", "universal": "", "use_case": "",
        "example": "", "result": "", "math": [], "features_used": [],
    }


def _variant(v: Any) -> dict:
    if isinstance(v, dict):
        return {"name": str(v.get("name", "")), "description": str(v.get("description", ""))}
    return {"name": str(v), "description": ""}


def _problem(ps: Any) -> dict:
    if isinstance(ps, dict):
        return {"one_liner": str(ps.get("one_liner", "")), "plain": str(ps.get("plain", ""))}
    return {"one_liner": "", "plain": str(ps or "")}


def _math(x: Any) -> dict:
    if isinstance(x, dict):
        symbols = x.get("symbols", "")
        # symbols may come back as a list of {symbol, meaning} or strings — flatten to lines
        if isinstance(symbols, list):
            parts = []
            for s in symbols:
                if isinstance(s, dict):
                    parts.append(f"{s.get('symbol', '')} = {s.get('meaning', s.get('definition', ''))}".strip(" ="))
                else:
                    parts.append(str(s))
            symbols = "\n".join(p for p in parts if p)
        return {
            "formula": str(x.get("formula", "")),
            # accept legacy `explanation` as the plain reading
            "plain": str(x.get("plain", x.get("explanation", ""))),
            "symbols": str(symbols),
            "intuition": str(x.get("intuition", "")),
            # worked_example (real-data, per-model) — fall back to legacy `example`
            "worked_example": str(x.get("worked_example", x.get("example", ""))),
            "example": str(x.get("example", "")),
        }
    return {"formula": str(x), "plain": "", "symbols": "", "intuition": "", "worked_example": "", "example": ""}


def normalize_card(card: dict) -> dict:
    """Empirical card — stable shape, backward-compatible with legacy string fields."""
    out = dict(card)
    out["paper_type"] = "empirical"
    out["problem_statement"] = _problem(out.get("problem_statement"))
    for f in ("data_sources", "preprocessing"):
        out.setdefault(f, [])
    out["variants"] = [_variant(v) for v in out.get("variants", [])]
    out["math"] = [_math(m) for m in out.get("math", [])]  # legacy top-level math (no longer rendered)
    out.setdefault("data_sample", "")
    out.setdefault("results", "")
    out.setdefault("inference", "")
    out.setdefault("detailed_summary", "")
    out.setdefault("best_model", "")
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
