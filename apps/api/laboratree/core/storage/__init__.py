"""Blob storage behind a small interface. Local filesystem now; swap to S3/MinIO/GCS later.

The interface matches `laboratree_sdk.BlobStore`, so components are storage-agnostic.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from ..config import settings


class LocalBlobStore:
    """Stores blobs under a root directory. `key` may contain '/' to nest."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # prevent path escape
        safe = Path(key.replace("\\", "/"))
        if safe.is_absolute() or ".." in safe.parts:
            raise ValueError(f"invalid blob key: {key!r}")
        path = self.root / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes) -> str:
        self._path(key).write_bytes(data)
        return self.uri(key)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def open_write(self, key: str) -> BinaryIO:
        return open(self._path(key), "wb")

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def uri(self, key: str) -> str:
        return f"file://{self._path(key)}"

    def writable(self) -> bool:
        try:
            probe = self.root / ".write_probe"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False


_store: LocalBlobStore | None = None


def get_blob_store() -> LocalBlobStore:
    global _store
    if _store is None:
        if settings.blob_backend != "local":
            raise NotImplementedError(f"blob backend '{settings.blob_backend}' not implemented yet")
        _store = LocalBlobStore(settings.blob_root)
    return _store
