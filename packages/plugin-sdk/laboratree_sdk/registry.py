"""The global component registry — the heart of Laboratree's plug-in / plug-out design.

Components register themselves at import time via the `@register` decorator. The registry
is queried by:
  * the API   -> `GET /api/components` (drives dynamic UI forms)
  * the agents -> to build their available tool list
  * the Labs  -> to instantiate and run a component by id
"""

from __future__ import annotations

from .component import Component
from .spec import ComponentKind, ComponentSpec


class DuplicateComponentError(RuntimeError):
    pass


class UnknownComponentError(KeyError):
    pass


class Registry:
    def __init__(self) -> None:
        self._by_id: dict[str, type[Component]] = {}

    def register(self, cls: type[Component]) -> type[Component]:
        spec = getattr(cls, "spec", None)
        if not isinstance(spec, ComponentSpec):
            raise TypeError(f"{cls.__name__} must define a class-level `spec: ComponentSpec`")
        if spec.id in self._by_id:
            existing = self._by_id[spec.id].__name__
            raise DuplicateComponentError(
                f"Component id '{spec.id}' already registered by {existing}"
            )
        self._by_id[spec.id] = cls
        return cls

    def get(self, component_id: str) -> type[Component]:
        try:
            return self._by_id[component_id]
        except KeyError as exc:
            raise UnknownComponentError(component_id) from exc

    def create(self, component_id: str) -> Component:
        return self.get(component_id)()

    def specs(
        self,
        kind: ComponentKind | None = None,
        tags: list[str] | None = None,
    ) -> list[ComponentSpec]:
        return [
            cls.spec
            for cls in self._by_id.values()
            if cls.spec.matches(kind=kind, tags=tags)
        ]

    def ids(self) -> list[str]:
        return sorted(self._by_id)

    def __len__(self) -> int:
        return len(self._by_id)


# Single process-wide registry.
REGISTRY = Registry()


def register(cls: type[Component]) -> type[Component]:
    """Class decorator: `@register` adds a Component subclass to the global registry."""
    return REGISTRY.register(cls)
