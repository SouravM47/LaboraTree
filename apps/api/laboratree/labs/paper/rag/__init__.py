"""Chat-with-paper — retrieval (vector or keyword) + grounded answering with citations."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....papers.models import PaperChunk

CompleteFn = Callable[[str, str], str]
EmbedFn = Callable[[list[str]], list[list[float]]]

_TOKEN = re.compile(r"[a-z0-9]{3,}")

_SYSTEM = (
    "You answer questions about a research paper using ONLY the provided context passages. "
    "Cite the passages you use as [ordinal]. If the answer is not in the context, say you cannot "
    "find it in the paper. Be concise and faithful."
)


async def retrieve(
    session: AsyncSession,
    *,
    paper_id: uuid.UUID,
    org_id: uuid.UUID,
    query: str,
    embed_fn: EmbedFn | None = None,
    k: int = 4,
) -> list[dict]:
    base = select(PaperChunk).where(
        PaperChunk.paper_id == paper_id, PaperChunk.org_id == org_id
    )

    # Vector path: only if we can embed AND at least one chunk has an embedding.
    if embed_fn is not None:
        try:
            qv = embed_fn([query])[0]
            rows = (
                await session.execute(
                    base.where(PaperChunk.embedding.isnot(None))
                    .order_by(PaperChunk.embedding.cosine_distance(qv))
                    .limit(k)
                )
            ).scalars().all()
            if rows:
                return [{"ordinal": c.ordinal, "text": c.text} for c in rows]
        except Exception:
            pass  # fall through to keyword

    # Keyword fallback (deterministic, no model needed).
    chunks = (await session.execute(base.order_by(PaperChunk.ordinal))).scalars().all()
    terms = set(_TOKEN.findall(query.lower()))
    scored = []
    for c in chunks:
        text_l = c.text.lower()
        score = sum(text_l.count(t) for t in terms)
        scored.append((score, c.ordinal, c.text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [s for s in scored if s[0] > 0][:k] or scored[:k]
    return [{"ordinal": o, "text": t} for _, o, t in top]


def answer(question: str, passages: list[dict], complete_fn: CompleteFn) -> dict:
    if not passages:
        return {"answer": "No content available for this paper.", "citations": [], "used": []}
    context = "\n\n".join(f"[{p['ordinal']}] {p['text']}" for p in passages)
    prompt = f"=== CONTEXT ===\n{context}\n\n=== QUESTION ===\n{question}"
    text = complete_fn(_SYSTEM, prompt)
    return {
        "answer": text,
        "citations": [p["ordinal"] for p in passages],
        "used": passages,
    }
