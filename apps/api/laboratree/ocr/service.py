"""OCR service — engine selection + helpers for images and (rasterized) PDF pages.

PDF rasterization uses pypdfium2 (already available via pdfplumber), so no extra native deps
beyond the Tesseract binary itself.
"""

from __future__ import annotations

import io

from .base import OCREngine, OCRUnavailable
from .tesseract import TesseractEngine

_engine: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    """Return the configured OCR engine. Swap here to add cloud/docTR/EasyOCR engines."""
    global _engine
    if _engine is None:
        _engine = TesseractEngine()
    return _engine


def ocr_available() -> bool:
    return get_ocr_engine().available()


def ocr_image_bytes(image_bytes: bytes) -> str:
    return get_ocr_engine().image_to_text(image_bytes)


def ocr_pdf_pages(pdf_bytes: bytes, *, scale: float = 2.0) -> list[str]:
    """Rasterize each PDF page and OCR it. Returns per-page text (empty pages dropped)."""
    engine = get_ocr_engine()
    if not engine.available():
        raise OCRUnavailable("no OCR engine available")

    import pypdfium2 as pdfium

    texts: list[str] = []
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            text = engine.image_to_text(buf.getvalue())
            if text.strip():
                texts.append(text)
    finally:
        pdf.close()
    return texts
