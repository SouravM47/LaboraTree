"""Ambient LLM-call context — lets us attribute every model call to its Lab/operation without
changing the many call-site signatures. Set it at an API/service boundary with `use_llm_context`.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator


@dataclass(frozen=True)
class LLMContext:
    lab: str = "unknown"
    operation: str = "complete"
    project_id: str | None = None
    run_id: str | None = None
    org_id: str | None = None


# default None (not a shared mutable instance); current_llm_context() supplies a fresh empty context
_ctx: contextvars.ContextVar[LLMContext | None] = contextvars.ContextVar("llm_ctx", default=None)


def current_llm_context() -> LLMContext:
    return _ctx.get() or LLMContext()


@contextmanager
def use_llm_context(
    lab: str,
    operation: str,
    *,
    project_id: object | None = None,
    run_id: object | None = None,
    org_id: object | None = None,
) -> Iterator[None]:
    token = _ctx.set(
        LLMContext(
            lab=lab,
            operation=operation,
            project_id=str(project_id) if project_id else None,
            run_id=str(run_id) if run_id else None,
            org_id=str(org_id) if org_id else None,
        )
    )
    try:
        yield
    finally:
        _ctx.reset(token)


@contextmanager
def use_llm_operation(operation: str, *, lab: str | None = None) -> Iterator[None]:
    """Refine ONLY the operation (and optionally lab) of the enclosing context — inherits its
    project_id/org_id/run_id. Lets a multi-step agent label each sub-call (e.g. 'evidence.plan',
    'evidence.synthesize', 'evidence.variables') so every LLM call is individually observable."""
    cur = current_llm_context()
    token = _ctx.set(
        LLMContext(
            lab=lab or cur.lab,
            operation=operation,
            project_id=cur.project_id,
            run_id=cur.run_id,
            org_id=cur.org_id,
        )
    )
    try:
        yield
    finally:
        _ctx.reset(token)
