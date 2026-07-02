"""Consolidation — reconcile extracted tables from many files into one master .xlsx.

Output workbook layout:
  * "Data Dictionary" — one row per table (sheet, source, kind, rows, cols, column list)
  * one sheet per extracted table (segregated)
  * "Text Blocks" — free text pulled from DOCX/PDF (if any)
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .extract import ExtractedTable, extract_file

_INVALID = re.compile(r"[\[\]:*?/\\]")


@dataclass
class ConsolidationResult:
    workbook: bytes
    sources: list[str] = field(default_factory=list)
    sheets: list[dict[str, Any]] = field(default_factory=list)  # data-dictionary rows
    texts: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def n_tables(self) -> int:
        return len(self.sheets)

    @property
    def total_rows(self) -> int:
        return sum(int(s["n_rows"]) for s in self.sheets)


def _sheet_name(raw: str, used: set[str]) -> str:
    name = _INVALID.sub("_", raw)[:31] or "sheet"
    candidate = name
    i = 1
    while candidate.lower() in used:
        suffix = f"_{i}"
        candidate = name[: 31 - len(suffix)] + suffix
        i += 1
    used.add(candidate.lower())
    return candidate


def consolidate(files: list[tuple[str, bytes]]) -> ConsolidationResult:
    tables: list[ExtractedTable] = []
    texts: list[tuple[str, str]] = []
    sources: list[str] = []
    errors: list[dict[str, str]] = []

    for name, data in files:
        sources.append(name)
        try:
            res = extract_file(name, data)
        except Exception as exc:
            errors.append({"source": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        tables.extend(res.tables)
        texts.extend((name, t) for t in res.texts)

    used: set[str] = {"data dictionary", "text blocks"}
    dict_rows: list[dict[str, Any]] = []
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # placeholder so the dictionary sheet is first; rewritten at the end
        pd.DataFrame().to_excel(writer, sheet_name="Data Dictionary", index=False)

        for table in tables:
            sheet = _sheet_name(table.name, used)
            table.df.to_excel(writer, sheet_name=sheet, index=False)
            dict_rows.append(
                {
                    "sheet": sheet,
                    "source": table.source,
                    "kind": table.kind,
                    "n_rows": int(len(table.df)),
                    "n_cols": int(table.df.shape[1]),
                    "columns": ", ".join(map(str, table.df.columns)),
                }
            )

        if texts:
            pd.DataFrame(texts, columns=["source", "text"]).to_excel(
                writer, sheet_name="Text Blocks", index=False
            )

        dictionary = pd.DataFrame(
            dict_rows,
            columns=["sheet", "source", "kind", "n_rows", "n_cols", "columns"],
        )
        # overwrite the placeholder with the real dictionary
        std = writer.book["Data Dictionary"]
        writer.book.remove(std)
        dictionary.to_excel(writer, sheet_name="Data Dictionary", index=False)
        writer.book.move_sheet("Data Dictionary", -(len(writer.book.sheetnames) - 1))

    return ConsolidationResult(
        workbook=buffer.getvalue(),
        sources=sources,
        sheets=dict_rows,
        texts=len(texts),
        errors=errors,
    )
