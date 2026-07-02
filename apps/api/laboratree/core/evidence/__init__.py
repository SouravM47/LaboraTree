"""Evidence Ledger — provenance-locking foundation.

`BufferedEvidenceSink` implements the SDK's sync `EvidenceSink` protocol by collecting records
in memory during a (possibly sync) component run. The async run executor then persists them to
Postgres via `persist_evidence`. This keeps components decoupled from the async DB while still
guaranteeing every reported value is captured as an `Evidence` row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...projects.models import Evidence


@dataclass
class BufferedEvidenceSink:
    run_id: uuid.UUID
    org_id: uuid.UUID
    records: list[dict[str, Any]] = field(default_factory=list)

    def record(self, *, label: str, value: Any, kind: str = "metric", **meta: Any) -> str:
        eid = uuid.uuid4()
        self.records.append(
            {
                "id": eid,
                "label": label,
                "kind": kind,
                "value": {"v": value},
                "code_hash": meta.pop("code_hash", ""),
                "data_version": meta.pop("data_version", ""),
                "artifact_id": meta.pop("artifact_id", None),
                "meta": meta,
            }
        )
        return str(eid)


async def persist_evidence(session: AsyncSession, sink: BufferedEvidenceSink) -> int:
    """Write all buffered records as Evidence rows. Returns the count persisted."""
    if not sink.records:
        return 0
    rows = [
        Evidence(
            id=r["id"],
            org_id=sink.org_id,
            run_id=sink.run_id,
            label=r["label"],
            kind=r["kind"],
            value=r["value"],
            code_hash=r["code_hash"],
            data_version=r["data_version"],
            artifact_id=r["artifact_id"],
            meta=r["meta"],
        )
        for r in sink.records
    ]
    session.add_all(rows)
    await session.flush()
    return len(rows)
