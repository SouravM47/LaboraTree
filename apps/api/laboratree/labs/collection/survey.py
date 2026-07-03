"""Survey assist — questionnaire design, bias detection, sample size, synthetic pilots.

LLM-driven functions take an injectable `complete_fn`; `sample_size` is pure math (Cochran).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

CompleteFn = Callable[[str, str], str]

_Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


def _z(confidence: float) -> float:
    return min(_Z.items(), key=lambda kv: abs(kv[0] - confidence))[1]


def _parse_json(raw: str, default: Any):
    text = raw.strip()
    for open_c, close_c in (("[", "]"), ("{", "}")):
        s, e = text.find(open_c), text.rfind(close_c)
        if 0 <= s < e:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    return default


# ---------------- pure: sample size ----------------

def sample_size(
    confidence: float = 0.95,
    margin: float = 0.05,
    population: int | None = None,
    proportion: float = 0.5,
) -> dict[str, Any]:
    z = _z(confidence)
    n0 = (z**2 * proportion * (1 - proportion)) / (margin**2)
    if population and population > 0:
        n = n0 / (1 + (n0 - 1) / population)
    else:
        n = n0
    return {
        "sample_size": int(math.ceil(n)),
        "unadjusted": int(math.ceil(n0)),
        "params": {"confidence": confidence, "margin": margin,
                   "population": population, "proportion": proportion, "z": round(z, 4)},
    }


# ---------------- LLM: design / bias / pilot ----------------

def design_questionnaire(goal: str, audience: str, n: int, complete_fn: CompleteFn) -> list[dict[str, Any]]:
    system = (
        "You are a survey methodologist. Design clear, unbiased questions. Return ONLY a JSON array "
        "of objects {text, type, options?} where type in [multiple_choice, likert, yes_no, open]."
    )
    raw = complete_fn(system, f"Goal: {goal}\nAudience: {audience or 'general'}\nDesign {n} questions.")
    items = _parse_json(raw, [])
    out = []
    for i, q in enumerate(items[:n]):
        if isinstance(q, dict) and q.get("text"):
            out.append({"id": f"q{i}", "text": str(q["text"]), "type": q.get("type", "open"),
                        "options": q.get("options", [])})
    return out


def detect_bias(questions: list[str], complete_fn: CompleteFn) -> list[dict[str, Any]]:
    system = (
        "You audit survey questions for leading, loaded, double-barreled, or ambiguous wording. "
        "Return ONLY a JSON array of {question, issue, severity, suggestion}; severity in "
        "[low, medium, high]. Only include problematic questions."
    )
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    raw = complete_fn(system, f"Questions:\n{numbered}")
    findings = _parse_json(raw, [])
    return [f for f in findings if isinstance(f, dict) and f.get("question")]


def synthetic_pilot(questions: list[str], persona: str, n: int, complete_fn: CompleteFn) -> dict[str, Any]:
    system = (
        "You simulate survey pilot respondents to pre-test an instrument. Answer in-character and "
        "realistically. Return ONLY a JSON array of respondent objects, each mapping the question "
        "number (as a string) to a short answer."
    )
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    raw = complete_fn(system, f"Persona: {persona}\nSimulate {n} respondents.\nQuestions:\n{numbered}")
    respondents = _parse_json(raw, [])
    respondents = [r for r in respondents if isinstance(r, dict)][:n]
    return {"persona": persona, "n": len(respondents), "respondents": respondents}


# ---------------- component (catalog + /runs) ----------------

@register
class SampleSize(Component):
    spec = ComponentSpec(
        kind=ComponentKind.TOOL,
        id="tool.sample_size",
        name="Sample size calculator",
        summary="Required sample size (Cochran) for a target confidence and margin of error.",
        params_schema={
            "type": "object",
            "properties": {
                "confidence": {"type": "number", "default": 0.95},
                "margin": {"type": "number", "default": 0.05},
                "population": {"type": "integer"},
                "proportion": {"type": "number", "default": 0.5},
            },
        },
        inputs=[],
        outputs=[Port(name="result", dtype="metrics")],
        tags=["collection", "sampling"],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        result = sample_size(
            confidence=ctx.params.get("confidence", 0.95),
            margin=ctx.params.get("margin", 0.05),
            population=ctx.params.get("population"),
            proportion=ctx.params.get("proportion", 0.5),
        )
        ctx.emit("sample_size", result["sample_size"], kind="metric", component=self.spec.id)
        return result
