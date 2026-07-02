"""Tesseract OCR engine (default). Gated on the `tesseract` system binary being installed."""

from __future__ import annotations

import io

from .base import OCRUnavailable


class TesseractEngine:
    name = "tesseract"

    def available(self) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def image_to_text(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise OCRUnavailable("pytesseract/Pillow not installed") from exc

        if not self.available():
            raise OCRUnavailable(
                "tesseract binary not found — install it (e.g. `choco install tesseract` on "
                "Windows, `apt-get install tesseract-ocr` on Debian) to enable OCR."
            )
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
