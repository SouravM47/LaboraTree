# OCR subsystem

Self-contained OCR, kept separate so it can later graduate into a standalone plugin.

**Why it exists:** `pdfplumber` only reads a PDF's embedded *text layer*. Scanned/image-only
PDFs and image files (PNG/JPG/TIFF) have no text to read — they need optical character
recognition. The Signal Lab and Paper Lab extractors call into this package as a fallback.

## Layout
- `base.py` — `OCREngine` protocol + `OCRUnavailable`.
- `tesseract.py` — default engine (Tesseract), gated on the system binary.
- `service.py` — engine factory + `ocr_image_bytes` / `ocr_pdf_pages` (PDF rasterized via pypdfium2).

## Availability
OCR is **optional and gated**: `ocr_available()` is False until the Tesseract binary is installed
(`choco install tesseract` on Windows, `apt-get install tesseract-ocr` on Debian). When absent,
digital extraction still works; image/scanned inputs surface a clear message instead of faking output.

## Adding an engine (future plugin)
Implement `OCREngine` (a `name`, `available()`, `image_to_text(bytes)`) and return it from
`get_ocr_engine()`. No call sites change. Candidates: cloud OCR (Azure Document Intelligence),
docTR, EasyOCR, PaddleOCR.
