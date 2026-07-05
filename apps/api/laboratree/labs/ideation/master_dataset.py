"""Master dataset builder — download the data-hunt's candidate datasets from the web and consolidate
them into one analyzable table the auto-experiment can run on.

Honest consolidation: sources that share a schema are concatenated (a real merge); when schemas
differ we keep the largest as the master and record the rest as separate tables — we never fabricate
a join. The actual HTTP download is injected (`fetch_fn`) so this is fully offline-testable; the API
layer supplies a rate-limited, size-capped fetcher and persists the results as project Datasets.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable

log = logging.getLogger(__name__)

FetchFn = Callable[[str], bytes | None]  # url -> raw bytes (or None on any failure)

MAX_DOWNLOADS = 6
MAX_ROWS = 5000
SCHEMA_MATCH = 0.8  # fraction of shared columns to treat two tables as the same schema


def _parse_csv(raw: bytes):
    import pandas as pd

    for kw in ({}, {"sep": ";"}, {"sep": "\t"}):
        try:
            df = pd.read_csv(io.BytesIO(raw), nrows=MAX_ROWS, **kw)
            if df.shape[1] >= 2 and len(df) >= 2:
                return df
        except Exception:
            continue
    return None


def _norm_cols(df) -> set[str]:
    return {str(c).strip().lower() for c in df.columns}


def _same_schema(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / max(len(a), len(b)) >= SCHEMA_MATCH


def build_master(candidates: list[dict], fetch_fn: FetchFn) -> dict:
    """Download each direct-download candidate, parse to a table, and consolidate. Returns
    {tables: [{url,name,n_rows,n_cols,status}], master (DataFrame|None), note}. `master` is left as a
    live DataFrame for the API layer to persist; everything else is JSON-safe."""
    import pandas as pd

    tables: list[dict] = []
    frames: list[tuple[dict, "pd.DataFrame"]] = []
    # try direct-download candidates first, then the rest — a portal URL often still serves/redirects
    # to a CSV, and _parse_csv rejects anything that isn't tabular, so trying is safe.
    picked = sorted(candidates, key=lambda c: not c.get("direct_download"))[:MAX_DOWNLOADS]
    for c in picked:
        url = c.get("url", "")
        raw = fetch_fn(url) if url else None
        if raw is None:
            tables.append({"url": url, "name": c.get("title", url), "status": "download_failed"})
            continue
        df = _parse_csv(raw)
        if df is None:
            tables.append({"url": url, "name": c.get("title", url), "status": "not_tabular"})
            continue
        rec = {"url": url, "name": c.get("title", url), "n_rows": int(len(df)),
               "n_cols": int(df.shape[1]), "status": "ok"}
        tables.append(rec)
        frames.append((rec, df))

    if not frames:
        return {"tables": tables, "master": None,
                "note": "No candidate downloaded into a usable table — try other sources or upload the data."}

    # group by schema; concatenate the largest schema-compatible group into the master
    groups: list[list[tuple[dict, "pd.DataFrame"]]] = []
    for rec, df in frames:
        cols = _norm_cols(df)
        for g in groups:
            if _same_schema(cols, _norm_cols(g[0][1])):
                g.append((rec, df))
                break
        else:
            groups.append([(rec, df)])
    best = max(groups, key=lambda g: sum(len(df) for _, df in g))

    if len(best) > 1:
        master = pd.concat([df for _, df in best], ignore_index=True)
        note = f"Consolidated {len(best)} web sources sharing a schema into one master table ({len(master)} rows)."
    else:
        master = max(frames, key=lambda f: len(f[1]))[1]
        note = ("Downloaded sources had differing schemas (no honest join key), so the largest was used "
                "as the master; the others are kept as separate tables.")
    for rec, _df in best:
        rec["in_master"] = True
    return {"tables": tables, "master": master, "note": note}
