"use client";

import type { ModelTrace, TestRow } from "@/lib/api";
import { ContribBlock, type TestProps, type TrainProps } from "./shared";

/** Linear family — logistic/linear regression, SVM-style scoring, probit.
 *  Train: one learned weight per feature + the literal sigmoid curve with every test row on it.
 *  Test: this row's feature×weight contributions → score → its point on the sigmoid. */

/** The literal σ(s)=1/(1+e^−s) curve; test rows are dots placed at their scores. */
export function SigmoidGraph({
  trace,
  highlight,
}: {
  trace: ModelTrace;
  highlight?: TestRow;
}) {
  const rows = (trace.test_rows ?? []).filter((r) => r.sum != null);
  if (trace.task !== "classification") return null;
  const sums = rows.map((r) => r.sum as number).concat(highlight?.sum != null ? [highlight.sum] : []);
  const span = Math.max(4, ...sums.map((s) => Math.abs(s))) * 1.15;
  const W = 340;
  const H = 150;
  const PAD = 26;
  const px = (s: number) => PAD + ((s + span) / (2 * span)) * (W - 2 * PAD);
  const py = (p: number) => H - 18 - p * (H - 40);
  const sig = (s: number) => 1 / (1 + Math.exp(-s));
  const curve = Array.from({ length: 81 }, (_, i) => {
    const s = -span + (2 * span * i) / 80;
    return `${i === 0 ? "M" : "L"}${px(s)},${py(sig(s))}`;
  }).join(" ");
  const pos = trace.labels?.[1] ?? "positive";
  const neg = trace.labels?.[0] ?? "negative";

  return (
    <div className="rounded-lg border border-line bg-white p-2">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="sigmoid">
        {/* decision threshold */}
        <line x1={px(0)} y1={py(0)} x2={px(0)} y2={py(1)} stroke="#C7D4CC" strokeDasharray="3 3" />
        <line x1={PAD} y1={py(0.5)} x2={W - PAD} y2={py(0.5)} stroke="#C7D4CC" strokeDasharray="3 3" />
        <text x={px(0) + 3} y={py(1) + 8} fontSize={8} fill="#7C8A80">score 0 · probability 0.5</text>
        {/* the sigmoid */}
        <path d={curve} fill="none" stroke="#14342A" strokeWidth={1.8} />
        {/* class zones */}
        <text x={W - PAD} y={py(1) - 4} fontSize={9} fill="#6DB33F" textAnchor="end" fontWeight={600}>
          → {pos}
        </text>
        <text x={PAD} y={py(0) + 12} fontSize={9} fill="#C0392B" fontWeight={600}>
          {neg} ←
        </text>
        {/* every test row as a dot on the curve */}
        {rows.map((r, i) => {
          const s = r.sum as number;
          const hot = highlight != null && r === highlight;
          return (
            <circle
              key={i}
              cx={px(s)}
              cy={py(sig(s))}
              r={hot ? 6 : 3.5}
              fill={r.correct === false ? "#C0392B" : "#6DB33F"}
              stroke={hot ? "#C9A227" : "#fff"}
              strokeWidth={hot ? 2.5 : 1}
            />
          );
        })}
        <text x={W / 2} y={H - 2} fontSize={8.5} fill="#7C8A80" textAnchor="middle">
          score s (weighted sum) → σ(s) = 1/(1+e⁻ˢ) = probability of {pos}
        </text>
      </svg>
    </div>
  );
}

export function Train({ trace }: TrainProps) {
  const coef = trace.coef ?? [];
  const scale = Math.max(1e-6, ...coef.map((x) => Math.abs(x.weight)));
  return (
    <div>
      <p className="mb-1 text-[11px] text-muted">
        Training finds a <b>weight</b> for each feature (how much it pushes toward the answer).
        Bigger bar = more influence; green pushes up, red pushes down. Why weights? They let the
        model combine ALL features into one score instead of relying on a single clue.
      </p>
      <div className="space-y-1">
        {coef.map((c) => (
          <div key={c.feature} className="flex items-center gap-2 text-[11px]">
            <span className="w-28 shrink-0 truncate text-muted">{c.feature}</span>
            <div className="relative h-3 flex-1 rounded bg-bg">
              <div className="absolute left-1/2 top-0 h-3 w-px bg-line" />
              <div
                className="absolute top-0 h-3 rounded transition-all duration-500"
                style={{
                  left: c.weight >= 0 ? "50%" : undefined,
                  right: c.weight < 0 ? "50%" : undefined,
                  width: `${(Math.abs(c.weight) / scale) * 45}%`,
                  background: c.weight >= 0 ? "#6DB33F" : "#C0392B",
                }}
              />
            </div>
            <span className="w-14 shrink-0 text-right font-medium text-forest">{c.weight}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-[11px] text-muted">intercept (starting point): {trace.intercept}</p>
      {trace.task === "classification" && (
        <div className="mt-2">
          <p className="mb-1 text-[11px] text-muted">
            The <b>sigmoid</b> — logistic regression&apos;s signature curve. Any score (left–right)
            becomes a probability (bottom–top). Each dot is one of our test rows sitting at its
            score; right of the dashed line → predicted{" "}
            <b className="text-forest">{trace.labels?.[1] ?? "positive"}</b>.
          </p>
          <SigmoidGraph trace={trace} />
        </div>
      )}
    </div>
  );
}

export function Test(props: TestProps) {
  return (
    <div className="space-y-2">
      <ContribBlock {...props} />
      {props.trace.task === "classification" && (
        <div>
          <p className="mb-1 text-[11px] text-muted">
            …and here is THIS row (gold ring) landing on the sigmoid at its score:
          </p>
          <SigmoidGraph trace={props.trace} highlight={props.row} />
        </div>
      )}
    </div>
  );
}
