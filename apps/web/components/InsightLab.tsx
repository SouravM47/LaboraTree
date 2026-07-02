"use client";

import { useState } from "react";
import Papa from "papaparse";
import { Api } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";
import VegaChart from "@/components/VegaChart";

type Row = Record<string, unknown>;
type ChartType = "histogram" | "scatter" | "correlation_heatmap";

type Profile = {
  n_rows: number;
  n_cols: number;
  total_missing: number;
  columns: { name: string; dtype: string; missing: number; missing_pct: number; n_unique: number }[];
  top_correlations: { a: string; b: string; corr: number }[];
};

export default function InsightLab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [fileName, setFileName] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [chartType, setChartType] = useState<ChartType>("histogram");
  const [x, setX] = useState("");
  const [y, setY] = useState("");
  const [color, setColor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load(files: File[]) {
    const file = files[0];
    setError(null);
    Papa.parse<Row>(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (res) => {
        const cols = res.meta.fields ?? [];
        setRows(res.data);
        setColumns(cols);
        setFileName(file.name);
        setProfile(null);
        setSpec(null);
        setX(cols[0] ?? "");
        setY(cols[1] ?? "");
      },
      error: () => setError("could not parse CSV"),
    });
  }

  async function runProfile() {
    setBusy(true);
    setError(null);
    try {
      const r = await Api.runComponent(projectId, "analyzer.eda_profile", {}, rows);
      setProfile(r.preview.profile as Profile);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  async function renderChart() {
    setBusy(true);
    setError(null);
    const params =
      chartType === "histogram"
        ? { column: x }
        : chartType === "scatter"
          ? { x, y, ...(color ? { color } : {}) }
          : {};
    try {
      const r = await Api.runComponent(projectId, `chart.${chartType}`, params, rows);
      setSpec(r.preview.spec as Record<string, unknown>);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Explore a dataset</h2>
        <p className="mt-1 text-sm text-muted">
          Drop a CSV to profile it and build charts. Every chart is computed server-side and
          provenance-locked.
        </p>
        <div className="mt-4">
          <FileDropzone multiple={false} accept=".csv" hint="Drop a CSV, or click to browse" onFiles={load} />
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-2xl border border-line bg-white p-4">
        <span className="text-sm text-ink">
          {fileName} · {rows.length} rows × {columns.length} cols
        </span>
        <div className="flex gap-2">
          <button onClick={runProfile} disabled={busy}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-forest hover:bg-bg disabled:opacity-50">
            {busy ? "…" : "Profile"}
          </button>
          <button onClick={() => { setRows([]); setColumns([]); setProfile(null); setSpec(null); }}
            className="rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:bg-bg">
            Change file
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {profile && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="font-display text-lg text-forest">Profile</h3>
          <div className="mt-2 flex gap-6 text-sm text-muted">
            <span>{profile.n_rows} rows</span>
            <span>{profile.n_cols} cols</span>
            <span>{profile.total_missing} missing</span>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-4">Column</th><th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Missing</th><th className="py-2">Unique</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((c) => (
                  <tr key={c.name} className="border-b border-line/60">
                    <td className="py-2 pr-4 font-medium text-forest">{c.name}</td>
                    <td className="py-2 pr-4 text-muted">{c.dtype}</td>
                    <td className="py-2 pr-4">{c.missing} ({c.missing_pct}%)</td>
                    <td className="py-2">{c.n_unique}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {profile.top_correlations.length > 0 && (
            <div className="mt-3 text-sm">
              <p className="font-medium text-ink">Top correlations</p>
              <ul className="mt-1 text-muted">
                {profile.top_correlations.slice(0, 5).map((c, i) => (
                  <li key={i}>{c.a} ↔ {c.b}: <span className="text-forest">{c.corr}</span></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-display text-lg text-forest">Chart</h3>
        <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
          <label className="block">
            <span className="text-muted">Type</span>
            <select className="mt-1 block rounded-lg border border-line px-2 py-1"
              value={chartType} onChange={(e) => setChartType(e.target.value as ChartType)}>
              <option value="histogram">Histogram</option>
              <option value="scatter">Scatter</option>
              <option value="correlation_heatmap">Correlation heatmap</option>
            </select>
          </label>
          {chartType === "histogram" && <ColSelect label="Column" cols={columns} value={x} onChange={setX} />}
          {chartType === "scatter" && (
            <>
              <ColSelect label="X" cols={columns} value={x} onChange={setX} />
              <ColSelect label="Y" cols={columns} value={y} onChange={setY} />
              <ColSelect label="Color (optional)" cols={["", ...columns]} value={color} onChange={setColor} />
            </>
          )}
          <button onClick={renderChart} disabled={busy}
            className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
            {busy ? "Rendering…" : "Render chart"}
          </button>
        </div>
        {spec && (
          <div className="mt-5">
            <VegaChart spec={spec} />
          </div>
        )}
      </div>
    </div>
  );
}

function ColSelect({
  label, cols, value, onChange,
}: {
  label: string; cols: string[]; value: string; onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-muted">{label}</span>
      <select className="mt-1 block rounded-lg border border-line px-2 py-1"
        value={value} onChange={(e) => onChange(e.target.value)}>
        {cols.map((c) => (
          <option key={c} value={c}>{c || "—"}</option>
        ))}
      </select>
    </label>
  );
}
