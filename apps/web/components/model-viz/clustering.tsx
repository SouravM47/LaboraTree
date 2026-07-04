"use client";

import { Scatter } from "./knn";
import type { TestProps, TrainProps } from "./shared";

/** Clustering family — groups discovered on the map; tests join the nearest centre. */

export function Train({ trace }: TrainProps) {
  const s = (trace.series ?? {}) as { k?: number; sizes?: number[] };
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        Clustering has <b>no answer column</b> — the model looks for natural groups on its own.
        k-means placed {s.k ?? "k"} centre points, assigned every row to its nearest centre, moved
        each centre to the middle of its rows, and repeated until nothing changed.
        {s.sizes ? ` Group sizes: ${s.sizes.join(" · ")}.` : ""}
      </p>
      <Scatter trace={trace} />
    </div>
  );
}

export function Test({ trace, row }: TestProps) {
  return (
    <div className="space-y-2">
      <Scatter trace={trace} row={row} />
      {row.distances && (
        <div className="rounded-lg border border-line bg-white p-2 text-[11px]">
          <p className="mb-1 text-muted">distance from this row to each cluster centre:</p>
          {row.distances.map((d, i) => (
            <div key={i} className="flex justify-between border-t border-line/50 py-0.5 first:border-t-0">
              <span className={i === 0 ? "font-medium text-forest" : "text-muted"}>
                {d.cluster}
                {i === 0 ? " ← closest" : ""}
              </span>
              <span className="text-ink">{d.distance}</span>
            </div>
          ))}
          <p className="mt-1 rounded bg-leaf/10 p-1.5">
            joins <b className="text-forest">{String(row.predicted)}</b> (the nearest centre)
          </p>
        </div>
      )}
    </div>
  );
}
