"use client";

import { useEffect, useState, type ComponentType } from "react";
import { Api, type ModelTrace, type ParamSpec, type TestRow } from "@/lib/api";
import { DataStage, stagesFor } from "@/components/model-viz";

/**
 * Granular, beginner-friendly model walkthrough on the REAL data — a thin host over the pluggable
 * per-family stages in components/model-viz/ (mirrors the backend labs/modeling/viz registry):
 *   1. The data  — the actual feature + target table
 *   2. Training  — how this model family learns (tree/weights/network/map/series…)
 *   3. Testing   — step through each held-out row and watch the prediction form
 */

type Phase = "data" | "train" | "test";

export default function StagedModelAnimation({
  datasetId,
  target,
  family,
  title,
  initialParams,
}: {
  datasetId: string;
  target: string;
  family: string;
  title?: string; // the paper's model name — lets a family pick its variant (XGBoost → ensemble)
  initialParams?: Record<string, number | string>; // the paper's hyperparameters (defaults)
}) {
  const [trace, setTrace] = useState<ModelTrace | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [phase, setPhase] = useState<Phase>("data");
  const [rowIdx, setRowIdx] = useState(0);
  // live hyperparameter overrides (start from the paper's, user can tweak → re-fit)
  const [params, setParams] = useState<Record<string, number | string>>(initialParams ?? {});
  const seed = JSON.stringify(initialParams ?? {});

  // switching node/dataset/family resets the view and the knobs back to the paper's defaults
  useEffect(() => {
    setPhase("data");
    setRowIdx(0);
    setParams(initialParams ? { ...initialParams } : {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, target, family, seed]);

  // (re)fit whenever inputs or the knobs change — but DON'T bounce the user off their current tab
  const paramsKey = JSON.stringify(params);
  useEffect(() => {
    let alive = true;
    setBusy(true);
    setErr(null);
    const id = setTimeout(() => {
      Api.modelTrace(datasetId, target, family, params)
        .then((t) => alive && setTrace(t))
        .catch((e) => alive && setErr(e instanceof Error ? e.message : "trace failed"))
        .finally(() => alive && setBusy(false));
    }, 220); // debounce slider drags
    return () => {
      alive = false;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, target, family, paramsKey]);

  // first-ever load (no trace yet) shows the full loader; later re-fits keep the panel + a subtle badge
  if (busy && !trace)
    return (
      <div className="rounded-xl border border-line bg-bg p-4 text-xs text-muted">
        Training a small model on the real data…
      </div>
    );
  if (err || !trace)
    return (
      <div className="rounded-xl border border-line bg-bg p-3 text-xs text-muted">
        Couldn&apos;t build the walkthrough{err ? ` (${err})` : ""}. Generate data first.
      </div>
    );

  const { Train, Test } = stagesFor(trace.family);
  const rows = trace.test_rows ?? [];
  const row = rows[Math.min(rowIdx, Math.max(0, rows.length - 1))];

  return (
    <div className="rounded-xl border border-line bg-gradient-to-b from-white to-[#F6FAF2] p-3">
      {/* phase tabs */}
      <div className="mb-2 flex items-center gap-1 text-xs">
        {(
          [
            ["data", "1 · The data"],
            ["train", "2 · Training"],
            ["test", "3 · Testing"],
          ] as [Phase, string][]
        ).map(([p, label]) => (
          <button
            key={p}
            onClick={() => setPhase(p)}
            className={`rounded-lg px-2.5 py-1 font-medium transition ${
              phase === p ? "bg-forest text-white" : "border border-line text-forest hover:bg-bg"
            }`}
          >
            {label}
          </button>
        ))}
        {busy && <span className="ml-auto animate-pulse text-[10px] text-[#8a6d1a]">re-fitting…</span>}
      </div>

      <ParamPanel
        spec={trace.param_spec ?? []}
        paperDefaults={initialParams}
        onChange={(k, v) => setParams((prev) => ({ ...prev, [k]: v }))}
        onReset={() => setParams(initialParams ? { ...initialParams } : {})}
      />

      {phase === "data" && <DataStage trace={trace} />}
      {phase === "train" && <Train trace={trace} hint={title} />}
      {phase === "test" && row && (
        <TestTable
          trace={trace}
          rows={rows}
          rowIdx={rowIdx}
          setRowIdx={setRowIdx}
          Test={Test}
          hint={title}
        />
      )}

      <p className="mt-2 text-[11px] text-muted">{trace.note}</p>
    </div>
  );
}

/* ---------------- hyperparameters: tune the model, defaults from the paper --------------------- */

function ParamPanel({
  spec,
  paperDefaults,
  onChange,
  onReset,
}: {
  spec: ParamSpec[];
  paperDefaults?: Record<string, number | string>;
  onChange: (key: string, value: number | string) => void;
  onReset: () => void;
}) {
  const [open, setOpen] = useState(false);
  if (!spec.length) return null;
  // a knob is "tweaked" when it differs from what the paper (or the library) defaults to
  const dirty = spec.some((s) => {
    const base = paperDefaults?.[s.key] ?? s.default;
    return String(s.value) !== String(base);
  });

  return (
    <div className="mb-2 rounded-lg border border-line bg-white/70">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-medium text-forest"
      >
        <span>
          ⚙ Hyperparameters{" "}
          <span className="font-normal text-muted">
            — {spec.map((s) => `${s.label} ${s.value}`).join(" · ")}
          </span>
        </span>
        <span className="flex items-center gap-2">
          {dirty && <span className="rounded-full bg-amber-100 px-1.5 text-[10px] text-amber-800">tweaked</span>}
          <span className="text-muted">{open ? "▲" : "▼"}</span>
        </span>
      </button>

      {open && (
        <div className="space-y-2.5 border-t border-line px-3 py-2.5">
          <p className="text-[10px] text-muted">
            Defaults follow the paper; drag to explore how each setting changes the model, then watch
            Training/Testing re-fit on the real data.
          </p>
          {spec.map((s) => (
            <ParamControl key={s.key} s={s} onChange={onChange} />
          ))}
          {dirty && (
            <button
              onClick={onReset}
              className="rounded border border-line px-2 py-0.5 text-[11px] text-forest hover:bg-bg"
            >
              ↺ Reset to paper defaults
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ParamControl({
  s,
  onChange,
}: {
  s: ParamSpec;
  onChange: (key: string, value: number | string) => void;
}) {
  return (
    <label className="block" title={s.help}>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-ink">{s.label}</span>
        <span className="font-mono text-forest">{s.value}</span>
      </div>
      {s.type === "select" ? (
        <select
          className="mt-1 w-full rounded border border-line px-2 py-1 text-xs"
          value={String(s.value)}
          onChange={(e) => onChange(s.key, e.target.value)}
        >
          {(s.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : (
        <input
          type="range"
          className="mt-1 w-full accent-leaf"
          min={s.min}
          max={s.max}
          step={s.step ?? (s.type === "int" ? 1 : 0.01)}
          value={Number(s.value)}
          onChange={(e) =>
            onChange(s.key, s.type === "int" ? Math.round(Number(e.target.value)) : Number(e.target.value))
          }
        />
      )}
      {s.help && <p className="mt-0.5 text-[10px] text-muted">{s.help}</p>}
    </label>
  );
}

/* ---------------- testing: ONE results table (all rows), click a row for its walkthrough -------- */

function TestTable({
  trace,
  rows,
  rowIdx,
  setRowIdx,
  Test,
  hint,
}: {
  trace: ModelTrace;
  rows: TestRow[];
  rowIdx: number;
  setRowIdx: (i: number) => void;
  Test: ComponentType<{ trace: ModelTrace; row: TestRow; hint?: string }>;
  hint?: string;
}) {
  const [wave, setWave] = useState(0); // bump to replay the reveal animation
  // every feature column the rows carry (the table scrolls horizontally)
  const feats = Object.keys(rows[0]?.values ?? {});
  const row = rows[Math.min(rowIdx, rows.length - 1)];
  const unsupervised = rows.every((r) => r.actual == null);

  const resultCell = (r: TestRow) => {
    if (r.actual == null)
      return <span className="font-medium text-forest">{String(r.predicted)}</span>;
    if (r.correct != null)
      return (
        <span className={`font-semibold ${r.correct ? "text-green-700" : "text-red-600"}`}>
          {r.correct ? "✓ correct" : "✗ wrong"}
        </span>
      );
    const e = r.error ?? 0;
    return (
      <span className={`font-semibold ${Math.abs(e) < 5 ? "text-green-700" : "text-red-600"}`}>
        {e > 0 ? "+" : ""}
        {e}
      </span>
    );
  };

  return (
    <div className="space-y-2">
      <style>{`@keyframes mvRowIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }`}</style>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">
          All {rows.length} held-out rows at a glance — <b>click a row</b> to watch its prediction
          being made below.
        </span>
        <button
          onClick={() => setWave((w) => w + 1)}
          className="rounded border border-line px-2 py-0.5 text-forest hover:bg-bg"
        >
          ↻ replay
        </button>
      </div>

      <div className="overflow-auto rounded-lg border border-line bg-white" style={{ maxHeight: 230 }}>
        <table className="min-w-full text-[11px]">
          <thead className="sticky top-0 bg-bg">
            <tr>
              <th className="px-2 py-1 text-left font-medium text-muted">#</th>
              {feats.map((f) => (
                <th key={f} className="whitespace-nowrap px-2 py-1 text-left font-medium text-forest">
                  {f}
                </th>
              ))}
              <th className="whitespace-nowrap px-2 py-1 text-left font-medium text-[#B8860B]">
                predicted
              </th>
              {!unsupervised && (
                <th className="whitespace-nowrap px-2 py-1 text-left font-medium text-[#B8860B]">
                  actual
                </th>
              )}
              <th className="whitespace-nowrap px-2 py-1 text-left font-medium text-muted">
                {unsupervised ? "" : trace.task === "classification" ? "result" : "error"}
              </th>
            </tr>
          </thead>
          <tbody key={wave}>
            {rows.map((r, i) => {
              const sel = i === rowIdx;
              const tint =
                r.actual == null
                  ? ""
                  : (r.correct ?? Math.abs(r.error ?? 0) < 5)
                    ? "bg-green-50/60"
                    : "bg-red-50/60";
              return (
                <tr
                  key={i}
                  onClick={() => setRowIdx(i)}
                  className={`cursor-pointer border-t border-line/60 transition hover:bg-bg ${tint} ${
                    sel ? "outline outline-2 -outline-offset-2 outline-[#C9A227]" : ""
                  }`}
                  style={{ animation: "mvRowIn .35s both", animationDelay: `${i * 130}ms` }}
                >
                  <td className="px-2 py-1 text-muted">{i + 1}</td>
                  {feats.map((f) => (
                    <td key={f} className="whitespace-nowrap px-2 py-1 text-ink">
                      {r.values[f] ?? "—"}
                    </td>
                  ))}
                  <td className="whitespace-nowrap px-2 py-1 font-medium text-ink">
                    {String(r.predicted)}
                  </td>
                  {!unsupervised && (
                    <td className="whitespace-nowrap px-2 py-1 text-ink">{String(r.actual)}</td>
                  )}
                  <td className="whitespace-nowrap px-2 py-1">{resultCell(r)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {row && (
        <div className="rounded-lg border border-[#C9A227]/50 bg-[#FFFDF5] p-2">
          <p className="mb-1.5 text-[11px] font-medium text-[#8a6d1a]">
            How row {rowIdx + 1} was predicted:
          </p>
          <Test trace={trace} row={row} hint={hint} />
        </div>
      )}
    </div>
  );
}
