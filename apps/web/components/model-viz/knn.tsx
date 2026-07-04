"use client";

import type { ModelTrace, TestRow } from "@/lib/api";
import type { TestProps, TrainProps } from "./shared";

/** KNN family — a 2-D map of the memorized training rows; tests connect to their k nearest. */

const PALETTE = ["#6DB33F", "#C0392B", "#2E6C8E", "#B8860B", "#7D3C98"];

function labelColor(labels: (string | number)[], l: string | number) {
  const i = labels.indexOf(l);
  return PALETTE[(i < 0 ? labels.length : i) % PALETTE.length];
}

export function Scatter({
  trace,
  row,
}: {
  trace: ModelTrace;
  row?: TestRow;
}) {
  const pts = trace.points ?? [];
  const xs = pts.map((p) => p.x).concat(row?.x != null ? [row.x] : []);
  const ys = pts.map((p) => p.y).concat(row?.y != null ? [row.y] : []);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const W = 320;
  const H = 190;
  const PAD = 18;
  const sx = (v: number) => PAD + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * PAD);
  const sy = (v: number) => H - PAD - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * PAD);
  const labels = Array.from(new Set(pts.map((p) => String(p.label))));
  const axes = (trace.series ?? {}) as { x?: string; y?: string };

  return (
    <div className="rounded-lg border border-line bg-white p-2">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="knn map">
        {/* neighbor connections */}
        {row?.neighbors?.map((nb, i) =>
          row.x != null && row.y != null ? (
            <line
              key={i}
              x1={sx(row.x)}
              y1={sy(row.y)}
              x2={sx(nb.x)}
              y2={sy(nb.y)}
              stroke="#C9A227"
              strokeDasharray="3 2"
              strokeWidth={1.2}
            />
          ) : null,
        )}
        {pts.map((p, i) => (
          <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={3} fill={labelColor(labels, String(p.label))} opacity={0.55} />
        ))}
        {row?.neighbors?.map((nb, i) => (
          <circle key={`n${i}`} cx={sx(nb.x)} cy={sy(nb.y)} r={5} fill="none" stroke="#C9A227" strokeWidth={2} />
        ))}
        {row?.x != null && row?.y != null && (
          <g>
            <circle cx={sx(row.x)} cy={sy(row.y)} r={6} fill="#14342A" />
            <text x={sx(row.x) + 8} y={sy(row.y) - 6} fontSize={10} fill="#14342A">
              new row
            </text>
          </g>
        )}
        <text x={W / 2} y={H - 3} fontSize={9} fill="#7C8A80" textAnchor="middle">
          {axes.x ?? "x"}
        </text>
        <text x={8} y={H / 2} fontSize={9} fill="#7C8A80" transform={`rotate(-90 8 ${H / 2})`} textAnchor="middle">
          {axes.y ?? "y"}
        </text>
      </svg>
      <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted">
        {labels.map((l) => (
          <span key={l} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: labelColor(labels, l) }} />
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Train({ trace }: TrainProps) {
  const k = ((trace.series ?? {}) as { k?: number }).k ?? 5;
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        KNN doesn&apos;t learn an equation — it <b>memorizes every training row</b>. This map places
        them by the two strongest features (distance is really computed across ALL features). To
        predict, it will ask the {k} closest rows to vote.
      </p>
      <Scatter trace={trace} />
    </div>
  );
}

export function Test({ trace, row }: TestProps) {
  return (
    <div className="space-y-2">
      <Scatter trace={trace} row={row} />
      {row.neighbors && (
        <div className="rounded-lg border border-line bg-white p-2 text-[11px]">
          <p className="mb-1 text-muted">
            the {row.neighbors.length} nearest memorized rows (smaller distance = more similar):
          </p>
          {row.neighbors.map((nb, i) => (
            <div key={i} className="flex justify-between border-t border-line/50 py-0.5 first:border-t-0">
              <span className="text-muted">#{i + 1} · distance {nb.distance}</span>
              <span className="font-medium text-forest">{String(nb.label)}</span>
            </div>
          ))}
          <p className="mt-1 rounded bg-leaf/10 p-1.5">
            {trace.task === "classification" ? "majority vote → " : "average → "}
            <b className="text-forest">{String(row.predicted)}</b>
          </p>
        </div>
      )}
    </div>
  );
}
