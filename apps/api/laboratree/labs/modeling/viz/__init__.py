"""Model-visualization traces — one pluggable module per model family.

Each module here teaches ONE family by fitting a small stand-in model on the REAL data and
returning a staged trace: the data table -> a training view -> a per-row testing walkthrough.
The frontend mirror lives in ``apps/web/components/model-viz/`` (same family names).

Plug IN a family: add ``<family>.py`` with ``@register_tracer("<family>")`` on a
``(X, y, feats, target, task, labels) -> ModelTrace`` function — discovery is automatic,
no other file changes. Plug OUT: delete the module (requests for it fall back to "trees").
"""

from __future__ import annotations

import importlib
import io
import pkgutil
from collections.abc import Callable
from typing import Any

from .schema import FeatureSelectionTrace, ModelTrace  # re-exported for the API layer

Tracer = Callable[..., ModelTrace]

_TRACERS: dict[str, Tracer] = {}
_DISCOVERED = False


def register_tracer(family: str) -> Callable[[Tracer], Tracer]:
    def deco(fn: Tracer) -> Tracer:
        _TRACERS[family] = fn
        return fn

    return deco


def _discover() -> None:
    """Import every sibling module once so their @register_tracer decorators run."""
    global _DISCOVERED
    if _DISCOVERED:
        return
    pkg = __name__
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_") and m.name not in ("schema", "common"):
            importlib.import_module(f"{pkg}.{m.name}")
    _DISCOVERED = True


def families() -> list[str]:
    _discover()
    return sorted(_TRACERS)


def build_trace(data: bytes, target: str, family: str, params: dict | None = None) -> ModelTrace:
    """Sync (run via asyncio.to_thread): parse the CSV, prep X/y, dispatch to the family's tracer.
    ``params`` are user/paper hyperparameters passed through to the family's fit (each tracer clamps
    them). Unknown families fall back to "trees" — a solid teaching default."""
    import pandas as pd

    from .common import prep_xy

    _discover()
    df = pd.read_csv(io.BytesIO(data), nrows=2000)
    if target not in df.columns:
        target = df.columns[-1]
    X, y, feats, task, labels = prep_xy(df, target)
    if not feats:
        raise ValueError("no numeric features to trace")
    tracer = _TRACERS.get(family) or _TRACERS["trees"]
    return tracer(X, y, feats, target, task, labels, params=params or {})


def build_feature_selection(data: bytes, target: str) -> FeatureSelectionTrace:
    """Sync (run via asyncio.to_thread): the BBO-style wrapper feature-selection trace."""
    _discover()
    from .feature_selection import feature_selection_trace

    return feature_selection_trace(data, target)


__all__ = [
    "FeatureSelectionTrace",
    "ModelTrace",
    "build_feature_selection",
    "build_trace",
    "families",
    "register_tracer",
]
