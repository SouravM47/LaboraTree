"use client";

import { useState } from "react";
import { Api, downloadBlob, type SignalSummary } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";

export default function SignalLab({ projectId }: { projectId: string }) {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<SignalSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await Api.consolidate(projectId, files));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Noise → Signal</h2>
        <p className="mt-1 text-sm text-muted">
          Drop any mix of CSV, Excel, Word, PDF (or scans). We extract, reconcile, and hand back one
          consolidated master workbook.
        </p>
        <div className="mt-4">
          <FileDropzone
            onFiles={(f) => setFiles((prev) => [...prev, ...f])}
            accept=".csv,.tsv,.xlsx,.xls,.xlsm,.docx,.pdf,.png,.jpg,.jpeg,.tif,.tiff"
          />
        </div>

        {files.length > 0 && (
          <div className="mt-4">
            <ul className="flex flex-wrap gap-2">
              {files.map((f, i) => (
                <li key={i} className="rounded-full bg-bg px-3 py-1 text-xs text-ink">
                  {f.name}
                  <button
                    className="ml-2 text-muted hover:text-red-600"
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex gap-2">
              <button
                onClick={run}
                disabled={busy}
                className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Consolidating…" : `Consolidate ${files.length} file(s)`}
              </button>
              <button onClick={() => setFiles([])} className="rounded-lg border border-line px-4 py-2">
                Clear
              </button>
            </div>
          </div>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {result && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg text-forest">Master workbook</h3>
            <button
              onClick={() => downloadBlob(result.download_url, "master.xlsx")}
              className="rounded-lg bg-forest px-3 py-1.5 text-sm text-white hover:opacity-90"
            >
              ⬇ Download .xlsx
            </button>
          </div>
          <div className="mt-2 flex gap-6 text-sm text-muted">
            <span>{result.summary.n_tables} tables</span>
            <span>{result.summary.total_rows} rows</span>
            <span>{result.summary.text_blocks} text blocks</span>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-4">Sheet</th>
                  <th className="py-2 pr-4">Source</th>
                  <th className="py-2 pr-4">Rows</th>
                  <th className="py-2 pr-4">Cols</th>
                  <th className="py-2">Columns</th>
                </tr>
              </thead>
              <tbody>
                {result.summary.sheets.map((s) => (
                  <tr key={s.sheet} className="border-b border-line/60">
                    <td className="py-2 pr-4 font-medium text-forest">{s.sheet}</td>
                    <td className="py-2 pr-4 text-muted">{s.source}</td>
                    <td className="py-2 pr-4">{s.n_rows}</td>
                    <td className="py-2 pr-4">{s.n_cols}</td>
                    <td className="py-2 text-muted">{s.columns}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.summary.errors.length > 0 && (
            <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {result.summary.errors.map((e, i) => (
                <p key={i}>
                  {e.source}: {e.error}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
