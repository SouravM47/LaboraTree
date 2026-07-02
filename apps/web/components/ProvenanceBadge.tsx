"use client";

import { useState } from "react";
import { Api, type EvidenceItem, type RunDetail } from "@/lib/api";

// A "🔒 provenance" badge: click to reveal the run's reproducibility manifest + Evidence records.
export default function ProvenanceBadge({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function toggle() {
    setOpen((o) => !o);
    if (!loaded) {
      try {
        const [r, e] = await Promise.all([Api.getRun(runId), Api.getRunEvidence(runId)]);
        setRun(r);
        setEvidence(e);
      } catch {
        /* ignore */
      } finally {
        setLoaded(true);
      }
    }
  }

  const m = (run?.repro_manifest ?? {}) as Record<string, unknown>;
  const short = (v: unknown, n = 10) => String(v ?? "").slice(0, n);

  return (
    <span className="relative inline-block">
      <button
        onClick={toggle}
        className="rounded-full border border-line px-2 py-0.5 text-xs text-forest hover:bg-bg"
        title="Provenance — every number is bound to a re-runnable execution"
      >
        🔒 provenance
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 w-72 rounded-xl border border-line bg-white p-3 text-xs shadow-lg">
          <p className="font-medium text-forest">Reproducibility</p>
          <ul className="mt-1 text-muted">
            <li>run: {short(runId)}</li>
            <li>seed: {String(m.seed ?? "—")}</li>
            <li>data: {short(m.data_version, 12) || "—"}</li>
            <li>code: {short(m.code_hash, 12) || "—"}</li>
          </ul>
          <p className="mt-2 font-medium text-forest">Evidence ({evidence.length})</p>
          <ul className="mt-1 max-h-40 overflow-auto">
            {evidence.map((e) => (
              <li key={e.id} className="flex justify-between border-b border-line/60 py-0.5">
                <span className="text-muted">{e.label}</span>
                <span className="text-ink">{String(e.value).slice(0, 24)}</span>
              </li>
            ))}
            {loaded && evidence.length === 0 && <li className="text-muted">no evidence</li>}
          </ul>
        </div>
      )}
    </span>
  );
}
