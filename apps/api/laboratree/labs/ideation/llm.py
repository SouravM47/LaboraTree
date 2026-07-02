"""Default LLM callable for the Ideation Lab (injectable; tests monkeypatch this)."""

from __future__ import annotations


def default_complete(system: str, prompt: str, *, role: str = "reasoning") -> str:
    from ...core.llm import get_llm

    return get_llm().complete(prompt, system=system, role=role)
