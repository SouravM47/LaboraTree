"""Component catalog — the registry exposed over HTTP.

Drives both the agent tool list and the frontend palette/forms. Adding a plugin makes it
appear here automatically with no code changes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from laboratree_sdk import ComponentKind
from laboratree_sdk.registry import UnknownComponentError

from ..core.registry import REGISTRY

router = APIRouter(prefix="/api/components", tags=["components"])


@router.get("")
def list_components(
    kind: ComponentKind | None = Query(default=None),
    tag: list[str] | None = Query(default=None),
) -> dict:
    specs = REGISTRY.specs(kind=kind, tags=tag)
    return {"count": len(specs), "components": [s.model_dump() for s in specs]}


@router.get("/{component_id}")
def get_component(component_id: str) -> dict:
    try:
        return REGISTRY.get(component_id).spec.model_dump()
    except UnknownComponentError as exc:
        raise HTTPException(status_code=404, detail=f"unknown component: {component_id}") from exc
