"""Default LLM callables for the Paper Lab (wrap the app LLMClient).

Kept as module-level functions so services take them as injectable defaults and tests can
monkeypatch them without a live model.
"""

from __future__ import annotations


def default_complete(system: str, prompt: str, *, role: str = "reasoning") -> str:
    from ...core.llm import get_llm

    return get_llm().complete(prompt, system=system, role=role)


def default_embed(texts: list[str]) -> list[list[float]]:
    from ...core.llm import get_llm

    return get_llm().embed(texts)
