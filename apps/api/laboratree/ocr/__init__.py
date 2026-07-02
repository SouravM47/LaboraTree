"""OCR subsystem — self-contained so it can later be extracted as a plugin.

pdfplumber only reads a PDF's embedded text layer; scanned/image-only PDFs and image files
have no text to read. This package adds optical character recognition behind a small
`OCREngine` interface. The default engine is Tesseract (gated on the system binary); other
engines (cloud OCR, docTR, EasyOCR) can be dropped in without touching call sites.
"""

from .base import OCREngine, OCRUnavailable
from .service import get_ocr_engine, ocr_available, ocr_image_bytes, ocr_pdf_pages

__all__ = [
    "OCREngine",
    "OCRUnavailable",
    "get_ocr_engine",
    "ocr_available",
    "ocr_image_bytes",
    "ocr_pdf_pages",
]
