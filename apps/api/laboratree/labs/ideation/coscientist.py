"""The Co-Scientist engine: multi-agent hypothesis generation, debate, and evolution.

Agents (all via one injectable `complete_fn`, so it's fully testable offline):
  Generation  -> propose distinct hypotheses
  Reflection  -> critique each (novelty / feasibility / rigor)
  Ranking     -> pairwise debates -> Elo tournament
  Evolution   -> combine & mutate the strongest into improved hypotheses
  Meta-review -> synthesize the top into a research direction
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

CompleteFn = Callable[[str, str], str]

K_FACTOR = 32
BASE_ELO = 1200.0


def _parse_list(raw: str) -> list[str]:
    text = raw.strip()
    s, e = text.find("["), text.rfind("]")
    if 0 <= s < e:
        try:
            data = json.loads(text[s : e + 1])
            return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            pass
    # fallback: split lines
    return [ln.strip("-* \t") for ln in text.splitlines() if ln.strip()]


def _numbered(hyps: list[dict[str, Any]]) -> str:
    return "\n".join(f"{i + 1}. {h['text']}" for i, h in enumerate(hyps))


def generate_hypotheses(goal: str, n: int, complete_fn: CompleteFn) -> list[dict[str, Any]]:
    system = (
        "You are the Generation agent in a Co-Scientist system. Propose distinct, testable, "
        "novel research hypotheses. Return ONLY a JSON array of hypothesis strings."
    )
    raw = complete_fn(system, f"Goal: {goal}\nReturn exactly {n} hypotheses as a JSON array.")
    items = _parse_list(raw)[:n]
    return [{"id": f"h{i}", "text": t, "elo": BASE_ELO, "critique": "", "origin": "generated"}
            for i, t in enumerate(items)]


def reflect(hyps: list[dict[str, Any]], goal: str, complete_fn: CompleteFn) -> None:
    if not hyps:
        return
    system = (
        "You are the Reflection agent. Critique each hypothesis for novelty, feasibility, and "
        "rigor in one sentence. Return ONLY a JSON array of critique strings, same order."
    )
    raw = complete_fn(system, f"Goal: {goal}\nHypotheses:\n{_numbered(hyps)}")
    for h, c in zip(hyps, _parse_list(raw), strict=False):
        h["critique"] = c


def _debate(a: dict[str, Any], b: dict[str, Any], goal: str, complete_fn: CompleteFn) -> dict[str, Any]:
    system = (
        "You are the Ranking agent judging a scientific debate between two hypotheses. Consider "
        "novelty, testability, and impact. Reply with ONLY 'A' or 'B'."
    )
    raw = complete_fn(system, f"Goal: {goal}\nA: {a['text']}\nB: {b['text']}\nWhich is stronger?")
    return a if raw.strip().upper().startswith("A") else b


def tournament(
    hyps: list[dict[str, Any]], goal: str, complete_fn: CompleteFn, rounds: int = 1
) -> list[dict[str, Any]]:
    for _ in range(rounds):
        for i in range(len(hyps)):
            for j in range(i + 1, len(hyps)):
                a, b = hyps[i], hyps[j]
                winner = _debate(a, b, goal, complete_fn)
                ea = 1.0 / (1.0 + 10 ** ((b["elo"] - a["elo"]) / 400.0))
                sa = 1.0 if winner is a else 0.0
                a["elo"] += K_FACTOR * (sa - ea)
                b["elo"] += K_FACTOR * ((1.0 - sa) - (1.0 - ea))
    ranked = sorted(hyps, key=lambda h: -h["elo"])
    for rank, h in enumerate(ranked, 1):
        h["rank"] = rank
        h["elo"] = round(h["elo"], 1)
    return ranked


def evolve(top: list[dict[str, Any]], goal: str, n: int, complete_fn: CompleteFn) -> list[dict[str, Any]]:
    if n <= 0 or not top:
        return []
    system = (
        "You are the Evolution agent. Combine and mutate the strongest hypotheses into improved, "
        "still-distinct ones. Return ONLY a JSON array of new hypothesis strings."
    )
    raw = complete_fn(system, f"Goal: {goal}\nStrongest:\n{_numbered(top)}\nReturn {n} improved.")
    items = _parse_list(raw)[:n]
    return [{"id": f"e{i}", "text": t, "elo": BASE_ELO, "critique": "", "origin": "evolved"}
            for i, t in enumerate(items)]


def meta_review(ranked: list[dict[str, Any]], goal: str, complete_fn: CompleteFn) -> str:
    system = (
        "You are the Meta-review agent. Synthesize the top hypotheses into a concise, actionable "
        "research direction (a short paragraph)."
    )
    return complete_fn(system, f"Goal: {goal}\nTop hypotheses:\n{_numbered(ranked[:3])}")


def run_ideation(
    goal: str, complete_fn: CompleteFn, *, n: int = 4, evolve_n: int = 2
) -> dict[str, Any]:
    """Full Co-Scientist pass. Returns {goal, hypotheses (ranked), meta_review}."""
    hyps = generate_hypotheses(goal, n, complete_fn)
    reflect(hyps, goal, complete_fn)
    ranked = tournament(hyps, goal, complete_fn)

    if evolve_n:
        offspring = evolve(ranked[:2], goal, evolve_n, complete_fn)
        reflect(offspring, goal, complete_fn)
        ranked = tournament(ranked + offspring, goal, complete_fn)

    review = meta_review(ranked, goal, complete_fn)
    return {"goal": goal, "hypotheses": ranked, "meta_review": review}
