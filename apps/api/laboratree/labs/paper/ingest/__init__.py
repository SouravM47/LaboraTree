"""Ingestion — turn an uploaded paper into text and retrievable chunks."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ....papers.models import Paper, PaperChunk, PaperStatus
from ...signal.extract import extract_file


def extract_paper_text(filename: str, data: bytes) -> str:
    """Extract readable text from a paper file (PDF/DOCX), with OCR fallback for scans."""
    res = extract_file(filename, data)
    parts = list(res.texts)
    for table in res.tables:  # include table content as text for retrieval/carding
        parts.append(table.df.to_csv(index=False))
    return "\n\n".join(p for p in parts if p and p.strip())


def chunk_text(text: str, *, size: int = 1500, overlap: int = 200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        chunks.append(text[start : start + size])
        start += step
    return chunks


async def ingest_paper(
    session: AsyncSession,
    paper: Paper,
    data: bytes,
    *,
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
) -> str:
    """Extract, chunk, and store a paper's chunks. Embeddings are best-effort.

    Returns the full extracted text (useful for immediate card generation).
    """
    text = extract_paper_text(paper.filename, data)
    pieces = chunk_text(text)

    embeddings: list[list[float] | None] = [None] * len(pieces)
    if embed_fn is not None and pieces:
        try:
            embeddings = list(embed_fn(pieces))
        except Exception:
            embeddings = [None] * len(pieces)

    for i, (piece, emb) in enumerate(zip(pieces, embeddings, strict=False)):
        session.add(
            PaperChunk(
                org_id=paper.org_id,
                paper_id=paper.id,
                ordinal=i,
                text=piece,
                embedding=emb,
            )
        )
    paper.n_chunks = len(pieces)
    paper.status = PaperStatus.PARSED
    await session.flush()
    return text
