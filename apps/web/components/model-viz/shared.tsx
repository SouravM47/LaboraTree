"use client";

import type { ModelTrace, TestRow } from "@/lib/api";

/** Props every family's Train stage receives. `hint` = the paper's model name (e.g. "XGBoost"),
 *  so a family can pick its variant view (single tree vs boosting ensemble). */
export type TrainProps = { trace: ModelTrace; hint?: string };
/** Props every family's Test stage receives (one held-out row at a time). */
export type TestProps = { trace: ModelTrace; row: TestRow; hint?: string };

/** Stage 1 — the actual data table (features + target), shared by every family. */
export function DataStage({ trace }: { trace: ModelTrace }) {
  const rows = trace.table ?? [];
  const cols = [...trace.features.filter((f) => rows[0] && f in rows[0]), trace.target];
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        The model learns from these columns. The last column (
        <span className="text-forest">{trace.target}</span>) is what we predict.
      </p>
      <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight: 220 }}>
        <table className="min-w-full text-[11px]">
          <thead className="sticky top-0 bg-bg">
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className={`whitespace-nowrap px-2 py-1 text-left font-medium ${
                    c === trace.target ? "text-[#B8860B]" : "text-forest"
                  }`}
                >
                  {c}
                  {c === trace.target ? " ★" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-line/60">
                {cols.map((c) => (
                  <td
                    key={c}
                    className={`whitespace-nowrap px-2 py-1 ${
                      c === trace.target ? "bg-[#FBF3D6] font-medium text-ink" : "text-ink"
                    }`}
                  >
                    {String(r[c] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** This row's feature values, as chips. */
export function RowValues({ row }: { row: TestRow }) {
  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(row.values).map(([k, v]) => (
        <span key={k} className="rounded bg-bg px-2 py-0.5 text-[11px] text-ink">
          {k}=<b>{v}</b>
        </span>
      ))}
    </div>
  );
}

/** predicted vs actual (+ error) badge. */
export function ResultBadge({ row }: { row: TestRow }) {
  if (row.correct != null) {
    return (
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          row.correct ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
        }`}
      >
        predicted {String(row.predicted)} · actual {String(row.actual)} ·{" "}
        {row.correct ? "✓ correct" : "✗ wrong"}
      </span>
    );
  }
  const e = row.error ?? 0;
  const col = Math.abs(e) < 5 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${col}`}>
      predicted {String(row.predicted)} · actual {String(row.actual)} · error {e > 0 ? "+" : ""}
      {e}
    </span>
  );
}

/** Per-row weighted-sum contribution list — used by linear AND timeseries (lags × φ). */
export function ContribBlock({ trace, row }: TestProps) {
  if (!row.contributions) return null;
  return (
    <div className="space-y-1">
      {row.contributions.map((c, i) => (
        <div key={i} className="flex items-center gap-2 text-[11px]">
          <span className="w-32 shrink-0 truncate text-muted">
            {c.feature}={c.value} × {c.weight}
          </span>
          <span
            className={`w-14 text-right font-medium ${
              c.product >= 0 ? "text-green-700" : "text-red-600"
            }`}
          >
            {c.product >= 0 ? "+" : "−"}
            {Math.abs(c.product)}
          </span>
        </div>
      ))}
      <div className="rounded-lg bg-leaf/10 p-2 text-[11px]">
        score (with intercept {trace.intercept}) = <b className="text-forest">{row.sum}</b>
        {row.score != null && (
          <>
            {" "}
            → sigmoid → probability <b>{row.score}</b>
          </>
        )}
      </div>
    </div>
  );
}
