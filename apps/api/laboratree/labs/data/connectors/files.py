"""File connector — read an uploaded blob and extract its first table as a dataset.

Wraps the Signal Lab extractors so any supported format (CSV/Excel/DOCX/PDF/image) can enter a
pipeline as a registered component. Multi-table consolidation is the Signal Lab's job.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from laboratree_sdk import Component, ComponentKind, ComponentSpec, Port, RunContext, register

from ...signal.extract import extract_file, supported_suffixes


@register
class FileConnector(Component):
    spec = ComponentSpec(
        kind=ComponentKind.CONNECTOR,
        id="connector.file",
        name="File connector",
        summary="Read a stored file (CSV/Excel/DOCX/PDF/image) and emit its first table.",
        params_schema={
            "type": "object",
            "required": ["storage_key", "filename"],
            "properties": {
                "storage_key": {"type": "string", "title": "Blob storage key"},
                "filename": {"type": "string", "title": "Original filename (determines parser)"},
            },
        },
        inputs=[],
        outputs=[Port(name="dataset", dtype="dataset"), Port(name="texts", dtype="texts")],
        tags=["ingestion", "connector", *[s.lstrip(".") for s in supported_suffixes()]],
    )

    def run(self, ctx: RunContext) -> dict[str, Any]:
        data = ctx.blobs.get(ctx.params["storage_key"])
        res = extract_file(ctx.params["filename"], data)
        df = res.tables[0].df if res.tables else pd.DataFrame()
        ctx.emit("tables_found", len(res.tables), kind="metric", component=self.spec.id)
        ctx.emit("text_blocks", len(res.texts), kind="metric", component=self.spec.id)
        return {"dataset": df, "texts": res.texts, "table_names": [t.name for t in res.tables]}
