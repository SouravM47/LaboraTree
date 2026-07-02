"""Laboratree plugin SDK — contracts every Lab component is built against."""

from .component import (
    BlobStore,
    Component,
    EvidenceSink,
    LLM,
    Logger,
    RunContext,
)
from .registry import (
    REGISTRY,
    DuplicateComponentError,
    Registry,
    UnknownComponentError,
    register,
)
from .spec import ComponentKind, ComponentSpec, Port

__all__ = [
    "Component",
    "RunContext",
    "BlobStore",
    "EvidenceSink",
    "LLM",
    "Logger",
    "ComponentKind",
    "ComponentSpec",
    "Port",
    "Registry",
    "REGISTRY",
    "register",
    "DuplicateComponentError",
    "UnknownComponentError",
]
