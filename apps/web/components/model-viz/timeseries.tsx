"use client";

import type { ModelTrace } from "@/lib/api";
import { ContribBlock, type TestProps, type TrainProps } from "./shared";

/** Time-series family (ARIMA-style AR): the series + fitted line, then per-step lag contributions. */

type Series = {
  history?: number[];
  fitted?: (number | null)[];
  coef?: { c: number; phi: number[] };
  split?: number;
};

function LineChart({ trace }: { trace: ModelTrace }) {
  const s = (trace.series ?? {}) as Series;
  const hist = s.history ?? [];
  const fitted = s.fitted ?? [];
  if (!hist.length) return null;
  const W = 330;
  const H = 150;
  const PAD = 14;
  const all = hist.concat(fitted.filter((v): v is number => v != null));
  const [v0, v1] = [Math.min(...all), Math.max(...all)];
  const px = (i: number) => PAD + (i / Math.max(1, hist.length - 1)) * (W - 2 * PAD);
  const py = (v: number) => H - PAD - ((v - v0) / (v1 - v0 || 1)) * (H - 2 * PAD);
  const path = (vals: (number | null)[]) =>
    vals
      .map((v, i) => (v == null ? null : `${i === 0 || vals[i - 1] == null ? "M" : "L"}${px(i)},${py(v)}`))
      .filter(Boolean)
      .join(" ");
  const split = s.split ?? hist.length;

  return (
    <div className="rounded-lg border border-line bg-white p-2">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="time series">
        {/* holdout shading */}
        <rect x={px(split)} y={PAD / 2} width={Math.max(0, W - PAD - px(split))} height={H - PAD} fill="#FFFBEA" />
        <path d={path(hist)} fill="none" stroke="#14342A" strokeWidth={1.6} />
        <path d={path(fitted)} fill="none" stroke="#6DB33F" strokeWidth={1.6} strokeDasharray="4 3" />
        <text x={PAD} y={10} fontSize={9} fill="#14342A">— actual series</text>
        <text x={PAD + 90} y={10} fontSize={9} fill="#6DB33F">- - model&apos;s one-step predictions</text>
        <text x={px(split) + 4} y={H - 4} fontSize={9} fill="#B8860B">test window</text>
      </svg>
    </div>
  );
}

export function Train({ trace }: TrainProps) {
  const s = (trace.series ?? {}) as Series;
  const phi = s.coef?.phi ?? [];
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-muted">
        A time-series model predicts the <b>next value from the previous ones</b>. Training slides
        along the history and finds the weights (φ) that best turn &quot;yesterday + the day
        before&quot; into &quot;today&quot;:
      </p>
      <div className="rounded-lg bg-leaf/10 p-2 text-[11px]">
        value(t) ≈ <b>{s.coef?.c}</b>
        {phi.map((p, i) => (
          <span key={i}>
            {" "}
            + <b>{p}</b> × value(t−{i + 1})
          </span>
        ))}
      </div>
      <LineChart trace={trace} />
      <p className="text-[11px] text-muted">
        The dashed line is the model re-predicting each step — the closer it hugs the solid line,
        the better it captured the pattern. The gold band is data it never saw during training.
      </p>
    </div>
  );
}

export function Test(props: TestProps) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-muted">
        this step is predicted only from its recent past (lags × learned weights):
      </p>
      <ContribBlock {...props} />
    </div>
  );
}
