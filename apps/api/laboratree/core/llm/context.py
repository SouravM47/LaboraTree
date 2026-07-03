"""Ambient LLM-call context — lets us attribute every model call to its Lab/operation without
changing the many call-site signatures. Set it at an API/service boundary with `use_llm_context`.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator


@dataclass
class LLMContext:
    lab: str = "unknown"
    operation: str = "complete"
    project_id: str | None = None
    run_id: str | None = None
    org_id: str | None = None


_ctx: contextvars.ContextVar[LLMContext] = contextvars.ContextVar("llm_ctx", default=LLMContext())


def current_llm_context() -> LLMContext:
    return _ctx.get()


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
