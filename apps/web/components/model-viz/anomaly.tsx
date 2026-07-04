"use client";

import { Scatter } from "./knn";
import type { TestProps, TrainProps } from "./shared";

/** Anomaly family — the detector's normal/anomaly split on the map; tests get a score vs threshold. */

export function Train({ trace }: TrainProps) {
  const s = (trace.series ?? {}) as { n_anomalies?: number; n_train?: number };
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        Anomaly detection learns what a <b>usual</b> row looks like — no labels needed. The isolation
        forest slices the data with random cuts; rows that end up alone after very few cuts are
        suspicious.
        {s.n_anomalies != null ? ` Here it flagged ${s.n_anomalies} of ${s.n_train} rows.` : ""}
      </p>
      <Scatter trace={trace} />
    </div>
  );
}

export function Test({ trace, row }: TestProps) {
  const score = row.score ?? 0;
  const anomalous = String(row.predicted) === "anomaly";
  return (
    <div className="space-y-2">
      <Scatter trace={trace} row={row} />
      <div className="rounded-lg border border-line bg-white p-2 text-[11px]">
        <p className="text-muted">
          anomaly score (above 0 = looks usual, below 0 = easily isolated):
        </p>
        <div className="relative mt-1 h-4 rounded bg-gradient-to-r from-red-200 via-bg to-green-200">
          <div className="absolute left-1/2 top-0 h-4 w-px bg-line" />
          <div
            className="absolute top-0.5 h-3 w-3 rounded-full border-2 border-white bg-forest shadow"
            style={{
              left: `${Math.min(97, Math.max(1, 50 + score * 120))}%`,
            }}
          />
        </div>
        <p className="mt-1.5 rounded bg-leaf/10 p-1.5">
          score <b>{score}</b> →{" "}
          <b className={anomalous ? "text-red-600" : "text-forest"}>
            {anomalous ? "⚠ anomaly" : "✓ normal"}
          </b>
        </p>
      </div>
    </div>
  );
}
