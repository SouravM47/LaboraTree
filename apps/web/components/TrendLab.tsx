"use client";

import { useState } from "react";
import Papa from "papaparse";
import { Api } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";
import VegaChart from "@/components/VegaChart";

type Row = Record<string, unknown>;
type Decomp = { original: number[]; trend: number[]; seasonal: number[]; resid: number[] };
type Summary = { period: number; direction: string; seasonality_strength: number };

export default function TrendLab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [col, setCol] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load(files: File[]) {
    Papa.parse<Row>(files[0], {
      header: true, dynamicTyping: true, skipEmptyLines: true,
      complete: (res) => {
        const cols = res.meta.fields ?? [];
        setRows(res.data); setColumns(cols); setCol(cols[0] ?? "");
        setSpec(null); setSummary(null);
      },
    });
  }

  async function decompose() {
    setBusy(true); setError(null);
    try {
      const r = await Api.runComponent(projectId, "analyzer.trend_decompose",
        { value_column: col, period: 12 }, rows);
      const d = r.preview.decomposition as Decomp;
      setSummary(r.preview.summary as Summary);
      const values: { i: number; value: number; series: string }[] = [];
      d.original.forEach((v, i) => values.push({ i, value: v, series: "original" }));
      d.trend.forEach((v, i) => values.push({ i, value: v, series: "trend" }));
      setSpec({
        $schema: "https://vega.github.io/schema/vega-lite/v5.json",
        title: `Trend of ${col}`,
        data: { values },
        mark: { type: "line" },
        encoding: {
          x: { field: "i", type: "quantitative", title: "index" },
          y: { field: "value", type: "quantitative" },
          color: { field: "series", type: "nominal", scale: { range: ["#A8D08D", "#14342A"] } },
        },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Trend analysis</h2>
        <p className="mt-1 text-sm text-muted">Drop a time-series CSV to decompose trend & seasonality.</p>
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
          <span className="text-muted">Value column</span>
          <select className="mt-1 block rounded-lg border border-line px-2 py-1"
            value={col} onChange={(e) => setCol(e.target.value)}>
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <button onClick={decompose} disabled={busy}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
          {busy ? "Decomposing…" : "Decompose"}
        </button>
        <button onClick={() => { setRows([]); setSpec(null); setSummary(null); }}
          className="rounded-lg border border-line px-3 py-2 text-muted">Change file</button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {summary && (
        <div className="flex gap-6 rounded-2xl border border-line bg-white p-4 text-sm text-muted">
          <span>direction: <span className="text-forest">{summary.direction}</span></span>
          <span>seasonality: <span className="text-forest">{summary.seasonality_strength}</span></span>
          <span>period: {summary.period}</span>
        </div>
      )}
      {spec && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <VegaChart spec={spec} />
        </div>
      )}
    </div>
  );
}
