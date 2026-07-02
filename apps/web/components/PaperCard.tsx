"use client";

import { useState } from "react";
import { Api, type PaperCardData } from "@/lib/api";

export default function PaperCard({ paperId, card }: { paperId: string; card: PaperCardData }) {
  return (
    <div className="space-y-4">
      <SimplifyBlock paperId={paperId} field="problem_statement" title="Problem statement" text={card.problem_statement} />

      <div className="grid gap-4 sm:grid-cols-2">
        <ListCard title="Models used" items={card.models_used} />
        <ListCard title="Data sources" items={card.data_sources} />
        <ListCard title="Preprocessing funnel" items={card.preprocessing} />
        <ListCard title="Independent variables" items={card.independent_variables} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <MiniCard title="Target variable">{card.target_variable || "—"}</MiniCard>
        <MiniCard title="Data sample">{card.data_sample || "—"}</MiniCard>
      </div>

      {card.variants?.length > 0 && <ListCard title="Variants" items={card.variants} />}

      {card.math?.length > 0 && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="font-display text-lg text-forest">Mathematics, explained</h3>
          <div className="mt-3 space-y-4">
            {card.math.map((m, i) => (
              <div key={i} className="rounded-lg bg-bg p-3">
                <code className="block text-sm text-forest">{m.formula}</code>
                <p className="mt-1 text-sm text-muted">{m.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <SimplifyBlock paperId={paperId} field="results" title="Results" text={card.results} />
      <SimplifyBlock paperId={paperId} field="inference" title="Inference" text={card.inference} />
    </div>
  );
}

function SimplifyBlock({
  paperId,
  field,
  title,
  text,
}: {
  paperId: string;
  field: string;
  title: string;
  text: string;
}) {
  const [level, setLevel] = useState(0);
  const [simpler, setSimpler] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function explain() {
    setBusy(true);
    try {
      const next = level + 1;
      const r = await Api.simplify(paperId, field, next);
      setSimpler(r.simplified);
      setLevel(next);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg text-forest">{title}</h3>
        <button
          onClick={explain}
          disabled={busy || !text}
          className="rounded-lg border border-line px-3 py-1 text-sm text-forest hover:bg-bg disabled:opacity-40"
        >
          {busy ? "…" : simpler ? "Even simpler" : "Explain simpler"}
        </button>
      </div>
      <p className="mt-2 text-sm text-ink">{text || "—"}</p>
      {simpler && (
        <div className="mt-3 rounded-lg bg-leaf/10 p-3 text-sm text-forest">
          <span className="mb-1 block text-xs uppercase tracking-wide text-leaf">
            Simpler · level {level}
          </span>
          {simpler}
        </div>
      )}
    </div>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="text-sm font-medium text-forest">{title}</h3>
      {items?.length ? (
        <ul className="mt-2 list-inside list-disc text-sm text-ink">
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted">—</p>
      )}
    </div>
  );
}

function MiniCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="text-sm font-medium text-forest">{title}</h3>
      <p className="mt-2 text-sm text-ink">{children}</p>
    </div>
  );
}
