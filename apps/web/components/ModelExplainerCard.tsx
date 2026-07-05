"use client";

import { useEffect, useState } from "react";
import { Api, type ModelExplainer } from "@/lib/api";
import StagedModelAnimation from "@/components/StagedModelAnimation";

/**
 * A beginner-first "learn this model from zero" modal for a model node. Fetches the curated explainer
 * for the model's family (intuition → how it works → every formula with its symbols explained and a
 * worked example filled with numbers → a demo table → when-to-use/pitfalls → references) and pairs it
 * with the live staged animation on the real data.
 */
export default function ModelExplainerCard({
  family,
  modelName,
  datasetId,
  target,
  initialParams,
  onClose,
}: {
  family: string;
  modelName: string;
  datasetId?: string;
  target?: string;
  initialParams?: Record<string, number | string | string[]>;
  onClose: () => void;
}) {
  const [ex, setEx] = useState<ModelExplainer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Api.modelExplainer(family)
      .then(setEx)
      .catch((e) => setErr(e instanceof Error ? e.message : "failed to load"));
  }, [family]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-forest/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="my-6 w-full max-w-3xl rounded-2xl border border-line bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-leaf">
              Learn this model
            </p>
            <h2 className="font-display text-xl text-forest">{ex?.title ?? modelName}</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-muted transition hover:bg-bg hover:text-forest"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {err && <p className="p-5 text-sm text-red-600">Couldn&apos;t load the explainer ({err}).</p>}
        {!ex && !err && <p className="p-5 text-sm text-muted">Loading…</p>}

        {ex && (
          <div className="space-y-5 px-5 py-5">
            {/* the gist */}
            <p className="text-sm leading-relaxed text-ink">{ex.one_liner}</p>
            {ex.analogy && (
              <div className="rounded-xl bg-sprout/15 p-3 text-sm text-forest">
                <span className="font-semibold">In plain terms: </span>
                {ex.analogy}
              </div>
            )}

            {/* how it works */}
            {ex.how_it_works?.length > 0 && (
              <Section title="How it works">
                <ol className="space-y-1.5">
                  {ex.how_it_works.map((s, i) => (
                    <li key={i} className="flex gap-2 text-sm text-ink">
                      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-forest text-[10px] font-bold text-white">
                        {i + 1}
                      </span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ol>
              </Section>
            )}

            {/* the maths, demystified */}
            {ex.math?.length > 0 && (
              <Section title="The maths — with the terms explained">
                <div className="space-y-3">
                  {ex.math.map((m, i) => (
                    <div key={i} className="rounded-xl border border-line p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{m.name}</p>
                      <p className="mt-1 overflow-x-auto rounded-lg bg-ink/[0.04] px-3 py-2 font-mono text-sm text-forest">
                        {m.formula}
                      </p>
                      <p className="mt-2 text-sm text-ink">{m.plain}</p>
                      {m.symbols?.length > 0 && (
                        <dl className="mt-2 grid gap-x-3 gap-y-1 text-xs sm:grid-cols-2">
                          {m.symbols.map((s, j) => (
                            <div key={j} className="flex gap-1.5">
                              <dt className="shrink-0 font-mono font-semibold text-leaf">{s.sym}</dt>
                              <dd className="text-muted">— {s.means}</dd>
                            </div>
                          ))}
                        </dl>
                      )}
                      {m.worked_example && (
                        <p className="mt-2 rounded-lg bg-leaf/10 p-2 text-xs text-forest">
                          <span className="font-semibold">Worked example: </span>
                          {m.worked_example}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* demo table */}
            {ex.example_table && (
              <Section title={ex.example_table.caption}>
                <div className="overflow-x-auto rounded-xl border border-line">
                  <table className="min-w-full text-sm">
                    <thead className="bg-bg">
                      <tr>
                        {ex.example_table.columns.map((c) => (
                          <th key={c} className="whitespace-nowrap px-3 py-1.5 text-left font-medium text-forest">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ex.example_table.rows.map((r, i) => (
                        <tr key={i} className="border-t border-line/60">
                          {r.map((cell, j) => (
                            <td key={j} className="whitespace-nowrap px-3 py-1.5 text-ink">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}

            {/* watch this model actually run on the real data */}
            {datasetId && (
              <Section title="Watch it on the real data">
                <StagedModelAnimation
                  datasetId={datasetId}
                  target={target ?? ""}
                  family={family}
                  title={modelName}
                  initialParams={initialParams}
                />
              </Section>
            )}

            {/* when to use / pitfalls */}
            <div className="grid gap-3 sm:grid-cols-2">
              {ex.when_to_use && (
                <div className="rounded-xl border border-line p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-forest">When to use it</p>
                  <p className="mt-1 text-sm text-ink">{ex.when_to_use}</p>
                </div>
              )}
              {ex.watch_out_for?.length > 0 && (
                <div className="rounded-xl border border-line p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Watch out for</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-ink">
                    {ex.watch_out_for.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* references */}
            {ex.references?.length > 0 && (
              <Section title="Go deeper">
                <ul className="space-y-1 text-sm">
                  {ex.references.map((r) => (
                    <li key={r.url}>
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-leaf hover:underline">
                        {r.title} ↗
                      </a>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-1.5 font-display text-base text-forest">{title}</h3>
      {children}
    </div>
  );
}
