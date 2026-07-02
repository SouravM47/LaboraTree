"""Reproducibility helpers — the manifest that makes every Run deterministically re-runnable.

A Run's `repro_manifest` captures the data version (content hash), random seeds, code hash of
the executed component, and library versions. Combined with the sandbox image digest (added by
the sandbox executor), this is what powers the one-click "reproduce" guarantee.
"""

from __future__ import annotations

import hashlib
import inspect
import platform
from importlib.metadata import PackageNotFoundError, version
from typing import Any

DEFAULT_SEED = 1729

_TRACKED_LIBS = ("pandas", "numpy", "scikit-learn", "statsmodels", "xgboost", "lightgbm", "torch")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dataframe_hash(df: Any) -> str:
    """Stable content hash of a pandas DataFrame (order-sensitive)."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return ""
    row_hashes = pd.util.hash_pandas_object(df, index=True).values
    header = ",".join(map(str, df.columns)).encode()
    return sha256_bytes(header + row_hashes.tobytes())


def code_hash(obj: Any) -> str:
    """Hash the source of a component class/function (best-effort)."""
    try:
        src = inspect.getsource(obj if inspect.isclass(obj) else obj.__class__)
    except (OSError, TypeError):
        return ""
    return sha256_bytes(src.encode())


def lib_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for lib in _TRACKED_LIBS:
        try:
            versions[lib] = version(lib)
        except PackageNotFoundError:
            continue
    return versions


def build_manifest(
    *,
    component: Any | None = None,
    data_version: str = "",
    seed: int = DEFAULT_SEED,
    image_digest: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "seed": seed,
        "data_version": data_version,
        "code_hash": code_hash(component) if component is not None else "",
        "image_digest": image_digest,
        "lib_versions": lib_versions(),
    }
    if extra:
        manifest.update(extra)
    return manifest
