"""Explain-simpler — progressive disclosure. Each level restates an idea more simply."""

from __future__ import annotations

from collections.abc import Callable

CompleteFn = Callable[[str, str], str]

_SYSTEM = (
    "You make hard ideas easy. Re-explain the given text more simply than before. "
    "Higher levels mean simpler: use everyday analogies and concrete worked examples, "
    "avoid jargon, keep it faithful. Do not add facts that are not implied by the text."
)


def simplify(text: str, level: int, complete_fn: CompleteFn) -> str:
    """Return a simplified explanation. `level` >= 1; higher = simpler / more examples."""
    level = max(1, int(level))
    guidance = {
        1: "Explain clearly in plain language.",
        2: "Explain as if to a curious beginner, with one analogy.",
        3: "Explain as if to a 12-year-old, with an analogy and a concrete example.",
    }.get(level, "Explain as simply as possible, with multiple analogies and a step-by-step example.")
    prompt = f"Simplification level {level}. {guidance}\n\n=== TEXT ===\n{text}"
    return complete_fn(_SYSTEM, prompt)
