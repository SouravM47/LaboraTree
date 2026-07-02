"""The `Component` base class and the `RunContext` handed to it at execution time.

Components are deliberately isolated: a component only touches the world through its
`RunContext` (blob storage, an evidence sink, an LLM handle, a scratch workdir, a logger).
This keeps every capability swappable and auditable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from .spec import ComponentSpec


@runtime_checkable
class BlobStore(Protocol):
    """Binary artifact storage (datasets, models, figures, workbooks)."""

    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def open_write(self, key: str) -> Any: ...  # returns a writable binary file-like
    def uri(self, key: str) -> str: ...


@runtime_checkable
class EvidenceSink(Protocol):
    """Provenance-locking: every reported value is recorded here and gets an Evidence id."""

    def record(self, *, label: str, value: Any, kind: str = "metric", **meta: Any) -> str:
        """Persist an evidence record and return its id. `value` must come from real execution."""
        ...


@runtime_checkable
class LLM(Protocol):
    """Minimal LLM handle exposed to components/agents (provider-agnostic)."""

    def complete(self, prompt: str, *, system: str | None = None, **kw: Any) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Logger(Protocol):
    def info(self, msg: str, **kw: Any) -> None: ...
    def warning(self, msg: str, **kw: Any) -> None: ...
    def error(self, msg: str, **kw: Any) -> None: ...


@dataclass
class RunContext:
    """Everything a component is allowed to touch during a single execution."""

    run_id: str
    org_id: str
    params: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    workdir: Path = field(default_factory=lambda: Path("."))
    blobs: BlobStore | None = None
    evidence: EvidenceSink | None = None
    llm: LLM | None = None
    logger: Logger | None = None

    def emit(self, label: str, value: Any, *, kind: str = "metric", **meta: Any) -> str:
        """Convenience: record an Evidence record. Raises if no sink is wired."""
        if self.evidence is None:
            raise RuntimeError("RunContext.evidence is not configured for this run")
        return self.evidence.record(label=label, value=value, kind=kind, **meta)


class Component(ABC):
    """Base class for every Lab capability. Subclasses set `spec` and implement `run`."""

    spec: ClassVar[ComponentSpec]

    @abstractmethod
    def run(self, ctx: RunContext) -> dict[str, Any]:
        """Execute using `ctx.params` and `ctx.inputs`; return a dict keyed by output port name."""
        raise NotImplementedError
