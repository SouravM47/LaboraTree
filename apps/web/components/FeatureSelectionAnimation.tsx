"use client";

import { useEffect, useMemo, useState } from "react";
import { Api, type FeatureSelectionTrace } from "@/lib/api";

/**
 * Beginner-friendly BBO feature-selection walkthrough on the REAL data.
 *  1. Feature relevance — how good each feature is on its own (its fitness).
 *  2. Evolution         — a population of candidate subsets ("habitats") shown as a matrix
 *                         (rows = habitats, columns = features); step through the generations and
 *                         watch weak habitats copy features from strong ones (migration) + mutate,
 *                         the fitness climb, and the chosen columns stabilise.
 *  3. Result            — the converged compact subset that feeds the models.
 */
export default function FeatureSelectionAnimation({
  datasetId,
  target,
}: {
  datasetId: string;
  target: string;
}) {
  const [tr, setTr] = useState<FeatureSelectionTrace | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [gen, setGen] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setErr(null);
    setGen(0);
    setPlaying(false);
    Api.featureSelection(datasetId, target)
      .then((t) => alive && setTr(t))
      .catch((e) => alive && setErr(e instanceof Error ? e.message : "selection failed"))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [datasetId, target]);

  const gens = tr?.generations ?? [];
  useEffect(() => {
    if (!playing) return;
    if (gen >= gens.length - 1) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setGen((g) => Math.min(g + 1, gens.length - 1)), 1500);
    return () => clearTimeout(id);
  }, [playing, gen, gens.length]);

  const maxImp = useMemo(
    () => Math.max(0.01, ...(tr?.importances ?? []).map((i) => Math.abs(i.importance))),
    [tr],
  );
  const maxFit = useMemo(
    () => Math.max(0.01, ...gens.flatMap((gg) => gg.habitats.map((h) => h.fitness))),
    [gens],
  );

  if (busy)
    return (
      <div className="rounded-xl border border-line bg-bg p-4 text-xs text-muted">
        Running BBO feature selection on the real data…
      </div>
    );
  if (err || !tr)
    return (
      <div className="rounded-xl border border-line bg-bg p-3 text-xs text-muted">
        Couldn&apos;t run feature selection{err ? ` (${err})` : ""}. Generate data first.
      </div>
    );

  const feats = tr.features;
  const g = gens[Math.min(gen, gens.length - 1)];
  const isLast = gen >= gens.length - 1;
  const selected = new Set(tr.selected);
  const short = (f: string) => (f.length > 6 ? f.slice(0, 6) + "…" : f);

  return (
    <div className="rounded-xl border border-line bg-gradient-to-b from-white to-[#F6FAF2] p-3">
      <p className="text-sm font-medium text-forest">Feature selection with BBO</p>
      <p className="mt-1 text-xs text-muted">{tr.note}</p>

      {/* 1 · Feature relevance */}
      <div className="mt-3 rounded-lg border border-line bg-white p-2.5">
        <p className="text-xs font-medium text-ink">
          1 · How strong is each feature on its own?
          <span className="ml-1 font-normal text-muted">
            (accuracy a model gets using only that one feature — the raw material BBO mixes and matches)
          </span>
        </p>
        <div className="mt-2 space-y-1">
          {tr.importances.map((im) => (
            <div key={im.feature} className="flex items-center gap-2 text-[11px]">
              <span className="w-24 shrink-0 truncate text-right text-muted" title={im.feature}>
                {im.feature}
              </span>
              <div className="h-3 flex-1 overflow-hidden rounded bg-bg">
                <div
                  className="h-full rounded bg-leaf/60 transition-all duration-500"
                  style={{ width: `${Math.max(2, (Math.abs(im.importance) / maxImp) * 100)}%` }}
                />
              </div>
              <span className="w-10 shrink-0 tabular-nums text-muted">{im.importance.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2 · Evolution controls */}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-medium text-ink">
          2 · Generation {gen + 1} / {gens.length}
        </span>
        <span className="rounded-full bg-leaf/15 px-2 py-0.5 text-forest">
          best fitness {g.best_fitness.toFixed(3)}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => {
              setPlaying(false);
              setGen((x) => Math.max(0, x - 1));
            }}
            disabled={gen === 0}
            className="rounded-lg border border-line px-2 py-1 disabled:opacity-40"
          >
            ◀
          </button>
          <button
            onClick={() => {
              if (isLast) {
                setGen(0);
                setPlaying(true);
              } else setPlaying((p) => !p);
            }}
            className="rounded-lg border border-line bg-forest px-2.5 py-1 text-white"
          >
            {playing ? "❚❚ Pause" : isLast ? "↻ Replay" : "▶ Play"}
          </button>
          <button
            onClick={() => {
              setPlaying(false);
              setGen((x) => Math.min(gens.length - 1, x + 1));
            }}
            disabled={isLast}
            className="rounded-lg border border-line px-2 py-1 disabled:opacity-40"
          >
            ▶
          </button>
        </div>
      </div>
      <p className="mt-1 text-[11px] text-muted">
        Each generation: weak habitats copy features from strong ones (migration) and randomly flip a few
        (mutation). The best two are always kept (elitism).
      </p>

      {/* Habitat × feature matrix */}
      <div className="mt-2 overflow-x-auto rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-[10px]">
          <thead>
            <tr className="text-muted">
              <th className="p-1 text-left font-normal">habitat</th>
              {feats.map((f) => (
                <th
                  key={f}
                  className={`p-1 font-normal ${selected.has(f) && isLast ? "text-forest" : ""}`}
                  title={f}
                >
                  <span className="inline-block max-w-[3.5rem] truncate align-bottom">{short(f)}</span>
                </th>
              ))}
              <th className="p-1 text-right font-normal">fitness</th>
            </tr>
          </thead>
          <tbody>
            {g.habitats.map((h, i) => {
              const sel = new Set(h.selected);
              const best = i === 0;
              return (
                <tr key={i} className={best ? "bg-leaf/10" : i % 2 ? "bg-bg/40" : ""}>
                  <td className="whitespace-nowrap p-1 text-muted">
                    {best ? "👑 " : ""}
                    {best ? "best" : `#${i + 1}`}
                  </td>
                  {feats.map((f) => (
                    <td key={f} className="p-1 text-center">
                      <span
                        className={`inline-block h-3.5 w-3.5 rounded-sm transition-all duration-500 ${
                          sel.has(f)
                            ? best
                              ? "bg-leaf"
                              : "bg-leaf/55"
                            : "bg-bg ring-1 ring-inset ring-line"
                        }`}
                      />
                    </td>
                  ))}
                  <td className="p-1">
                    <div className="flex items-center justify-end gap-1">
                      <div className="h-2 w-14 overflow-hidden rounded bg-bg">
                        <div
                          className={`h-full rounded transition-all duration-500 ${best ? "bg-leaf" : "bg-leaf/50"}`}
                          style={{ width: `${Math.max(3, (h.fitness / maxFit) * 100)}%` }}
                        />
                      </div>
                      <span className="w-8 tabular-nums text-muted">{h.fitness.toFixed(2)}</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 3 · Result */}
      {isLast && (
        <div className="mt-3 rounded-lg border border-leaf/40 bg-leaf/5 p-2.5">
          <p className="text-xs font-medium text-forest">
            3 · Selected subset — {feats.length} → {tr.selected.length} features (fitness{" "}
            {tr.best_fitness.toFixed(3)})
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {tr.selected.map((f) => (
              <span key={f} className="rounded-full bg-leaf/20 px-2 py-0.5 text-[11px] text-forest">
                {f}
              </span>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-muted">
            Fewer features, similar accuracy — these are what the model then trains on. That&apos;s the
            payoff: a simpler, cheaper model that&apos;s easier to trust.
          </p>
        </div>
      )}
    </div>
  );
}
