"""OCR engine interface — the seam future OCR plugins implement."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class OCRUnavailable(RuntimeError):
    """Raised when OCR is requested but no engine is installed/configured."""


@runtime_checkable
class OCREngine(Protocol):
    name: str

    def available(self) -> bool:
        """True if this engine can run (e.g. binary installed)."""
        ...

    def image_to_text(self, image_bytes: bytes) -> str:
        """OCR a single image (PNG/JPG/TIFF bytes) into text."""
        ...
