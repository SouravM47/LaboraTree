"""Component discovery — imports every Lab module so `@register` decorators fire.

Re-exports the SDK's global `REGISTRY` so the rest of the app has one import site.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from laboratree_sdk import REGISTRY

logger = logging.getLogger("laboratree.registry")

_discovered = False


def discover() -> int:
    """Import all submodules under `laboratree.labs`, registering their components.

    Idempotent. Returns the number of registered components.
    """
    global _discovered
    if _discovered:
        return len(REGISTRY)

    from laboratree import labs  # imported here to avoid a heavy import at module load

    for module in pkgutil.walk_packages(labs.__path__, labs.__name__ + "."):
        try:
            importlib.import_module(module.name)
        except Exception:  # a broken Lab must not take down the whole registry
            logger.exception("failed to import lab module %s", module.name)

    _discovered = True
    logger.info("registry discovery complete: %d components", len(REGISTRY))
    return len(REGISTRY)


__all__ = ["REGISTRY", "discover"]
