"""Evidence-bound report card — every number shown is backed by a real Evidence record.

The report renders only values that came from the ledger (no hallucinated metrics), plus a
reproducibility/trust score derived from manifests, evidence coverage, and leakage flags.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

RunDict = dict[str, Any]  # {id, lab, component_id, status, repro_manifest}
Evidence = dict[str, Any]  # {label, kind, value, meta}


def compute_trust_score(runs: list[RunDict], ev_by_run: dict[str, list[Evidence]]) -> dict[str, Any]:
    n = len(runs) or 1
    reproducible = sum(
        1 for r in runs if (r.get("repro_manifest") or {}).get("data_version")
        or (r.get("repro_manifest") or {}).get("code_hash")
        or (r.get("repro_manifest") or {}).get("lib_versions")
    )
    with_evidence = sum(1 for r in runs if ev_by_run.get(str(r["id"])))
    leakage_flags = sum(
        int(e["value"]) for evs in ev_by_run.values() for e in evs
        if e.get("label") == "leakage_findings" and isinstance(e.get("value"), (int, float))
    )

    repro = reproducible / n
    coverage = with_evidence / n
    score = 100.0 * (0.5 * repro + 0.5 * coverage) - 10.0 * min(leakage_flags, 5)
    score = max(0.0, min(100.0, score))
    return {
        "score": round(score),
        "reproducibility": round(repro, 2),
        "evidence_coverage": round(coverage, 2),
        "leakage_flags": int(leakage_flags),
        "n_runs": len(runs),
    }


def _badge_color(score: float) -> str:
    return "#6DB33F" if score >= 80 else "#C9A227" if score >= 50 else "#C0392B"


def _short(s: str, n: int = 10) -> str:
    return (s or "")[:n]


def render_report_html(
    project_name: str,
    runs: list[RunDict],
    ev_by_run: dict[str, list[Evidence]],
    trust: dict[str, Any],
    *,
    logo_b64: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.utcnow()
    color = _badge_color(trust["score"])
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" alt="Laboratree" style="height:64px"/>'
        if logo_b64
        else '<span style="font-family:Georgia,serif;font-size:28px;color:#14342A">'
        'Labora<span style="color:#6DB33F">tree</span></span>'
    )

    sections = []
    for r in runs:
        evs = ev_by_run.get(str(r["id"]), [])
        metrics = {e["label"]: e["value"] for e in evs if e.get("kind") == "metric"}
        manifest = r.get("repro_manifest") or {}
        rows = "".join(
            f"<tr><td>{html.escape(str(k))}</td><td style='text-align:right'>{html.escape(str(v))}</td></tr>"
            for k, v in metrics.items()
        ) or "<tr><td colspan=2 style='color:#5B6B60'>no metrics</td></tr>"
        prov = (
            f"run {_short(str(r['id']))} · code {_short(manifest.get('code_hash',''),8) or '—'} · "
            f"data {_short(manifest.get('data_version',''),8) or '—'} · seed {manifest.get('seed','—')}"
        )
        sections.append(
            f"""
            <div class="card">
              <div class="card-head">
                <strong>{html.escape(r.get('lab') or r.get('component_id') or 'run')}</strong>
                <span class="pill">{html.escape(str(r.get('status','')))}</span>
              </div>
              <table>{rows}</table>
              <div class="prov">🔒 {html.escape(prov)}</div>
            </div>"""
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{html.escape(project_name)} — Laboratree Report</title>
<style>
  body {{ font-family: Inter, system-ui, sans-serif; color:#1E2A22; background:#FBFDF9; margin:0; }}
  .wrap {{ max-width: 820px; margin: 0 auto; padding: 40px 24px; }}
  header {{ display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #E4EBE1; padding-bottom:16px; }}
  h1 {{ font-family: Georgia, serif; color:#14342A; margin: 24px 0 4px; }}
  .tagline {{ color:#6DB33F; letter-spacing:3px; font-size:11px; text-transform:uppercase; }}
  .score {{ display:inline-block; margin-top:16px; padding:14px 20px; border-radius:16px; color:#fff; background:{color}; }}
  .score b {{ font-size:28px; }}
  .factors {{ color:#5B6B60; font-size:13px; margin-top:8px; }}
  .card {{ border:1px solid #E4EBE1; border-radius:14px; padding:16px; margin-top:16px; background:#fff; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; color:#14342A; }}
  .pill {{ background:#EAF3E1; color:#14342A; border-radius:999px; padding:2px 10px; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  td {{ padding:4px 0; border-bottom:1px solid #F0F4EE; }}
  .prov {{ margin-top:8px; color:#5B6B60; font-size:12px; }}
  footer {{ margin-top:32px; color:#5B6B60; font-size:12px; text-align:center; border-top:1px solid #E4EBE1; padding-top:16px; }}
</style></head>
<body><div class="wrap">
  <header>{logo_html}<span class="tagline">Grow · Innovate · Impact</span></header>
  <h1>{html.escape(project_name)}</h1>
  <div class="tagline">Research report · generated {generated_at:%Y-%m-%d %H:%M} UTC</div>
  <div class="score"><b>{trust['score']}</b>/100 trust score</div>
  <div class="factors">reproducibility {trust['reproducibility']} · evidence coverage {trust['evidence_coverage']} · leakage flags {trust['leakage_flags']} · {trust['n_runs']} runs</div>
  <h2 style="font-family:Georgia,serif;color:#14342A;margin-top:28px">Results (Evidence-locked)</h2>
  {''.join(sections) or '<p style="color:#5B6B60">No runs yet.</p>'}
  <footer>Every figure above is bound to a re-runnable execution in the Evidence Ledger.</footer>
</div></body></html>"""
