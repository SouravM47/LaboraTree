"use client";

import { useState } from "react";
import Papa from "papaparse";
import { Api } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";

type Row = Record<string, unknown>;
type Summary = {
  action_true: string;
  action_false: string;
  n_true: number;
  n_false: number;
  rule: string;
};

export default function DecisionLab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [col, setCol] = useState("");
  const [threshold, setThreshold] = useState("0.5");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load(files: File[]) {
    Papa.parse<Row>(files[0], {
      header: true, dynamicTyping: true, skipEmptyLines: true,
      complete: (res) => {
        const cols = res.meta.fields ?? [];
        setRows(res.data); setColumns(cols); setCol(cols[0] ?? ""); setSummary(null);
      },
    });
  }

  async function evaluate() {
    setBusy(true); setError(null);
    try {
      const r = await Api.runComponent(projectId, "decision.threshold_rule",
        { column: col, threshold: Number(threshold), direction,
          action_true: "act", action_false: "hold" }, rows);
      setSummary(r.preview.summary as Summary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Decision rules</h2>
        <p className="mt-1 text-sm text-muted">
          Drop a CSV with a score/metric column to turn it into recommended actions.
        </p>
        <div className="mt-4">
          <FileDropzone multiple={false} accept=".csv" hint="Drop a CSV, or click to browse" onFiles={load} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-line bg-white p-4 text-sm">
        <label className="block">
          <span className="text-muted">Column</span>
          <select className="mt-1 block rounded-lg border border-line px-2 py-1"
            value={col} onChange={(e) => setCol(e.target.value)}>
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-muted">Direction</span>
          <select className="mt-1 block rounded-lg border border-line px-2 py-1"
            value={direction} onChange={(e) => setDirection(e.target.value as "above" | "below")}>
            <option value="above">≥ threshold</option>
            <option value="below">≤ threshold</option>
          </select>
        </label>
        <label className="block">
          <span className="text-muted">Threshold</span>
          <input className="mt-1 block w-28 rounded-lg border border-line px-2 py-1"
            value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </label>
        <button onClick={evaluate} disabled={busy}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
          {busy ? "Evaluating…" : "Evaluate"}
        </button>
        <button onClick={() => { setRows([]); setSummary(null); }}
          className="rounded-lg border border-line px-3 py-2 text-muted">Change file</button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {summary && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <p className="text-sm text-muted">Rule: <span className="text-forest">{summary.rule}</span></p>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <div className="rounded-xl bg-leaf/10 p-4 text-center">
              <div className="text-2xl font-semibold text-forest">{summary.n_true}</div>
              <div className="text-sm text-muted">→ {summary.action_true}</div>
            </div>
            <div className="rounded-xl bg-bg p-4 text-center">
              <div className="text-2xl font-semibold text-ink">{summary.n_false}</div>
              <div className="text-sm text-muted">→ {summary.action_false}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
