"use client";

import { useState } from "react";
import {
  Api,
  type CardModel,
  type CardVariable,
  type ConceptualCard,
  type EmpiricalCard,
  type PaperCardData,
} from "@/lib/api";

export default function PaperCard({ paperId, card }: { paperId: string; card: PaperCardData }) {
  if (card.paper_type === "conceptual") return <Conceptual paperId={paperId} card={card} />;
  return <Empirical paperId={paperId} card={card} />;
}

/* ---------------- empirical ---------------- */

function Empirical({ paperId, card }: { paperId: string; card: EmpiricalCard }) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-display text-lg text-forest">Problem</h3>
        {card.problem_statement.one_liner && (
          <p className="mt-1 font-medium text-ink">{card.problem_statement.one_liner}</p>
        )}
        <SimplifyBlock paperId={paperId} text={card.problem_statement.plain}>
          <p className="mt-1 text-sm text-ink">{card.problem_statement.plain || "—"}</p>
        </SimplifyBlock>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <ChipCard title="Independent variables" hint="click a variable">
          {card.independent_variables.map((v, i) => (
            <VariablePop key={i} v={v} />
          ))}
        </ChipCard>
        <ChipCard title="Models used" hint="click a model">
          {card.models_used.map((m, i) => (
            <ModelPop key={i} m={m} />
          ))}
        </ChipCard>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="text-sm font-medium text-forest">Target variable</h3>
          <div className="mt-2">
            {card.target_variable.name ? <VariablePop v={card.target_variable} tone="forest" /> : "—"}
          </div>
        </div>
        <MiniCard title="Data sample">{card.data_sample || "—"}</MiniCard>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <ListCard title="Data sources" items={card.data_sources} />
        <ListCard title="Preprocessing funnel" items={card.preprocessing} />
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

      <SimplifyCard paperId={paperId} title="Results" field="results" text={card.results} />
      <SimplifyCard paperId={paperId} title="Inference" field="inference" text={card.inference} />
    </div>
  );
}

function VariablePop({ v, tone }: { v: CardVariable; tone?: "forest" }) {
  return (
    <Pop
      label={v.name}
      tone={tone}
      body={
        <>
          <p className="text-ink">{v.description || "No description."}</p>
          {v.example_value && (
            <p className="mt-2 text-xs text-muted">
              Example: <span className="text-forest">{v.example_value}</span>
            </p>
          )}
        </>
      }
    />
  );
}

function ModelPop({ m }: { m: CardModel }) {
  return <Pop label={m.name} body={<p className="text-ink">{m.summary || "No summary."}</p>} />;
}

/* ---------------- conceptual ---------------- */

function Conceptual({ paperId, card }: { paperId: string; card: ConceptualCard }) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-leaf/10 p-5">
        <span className="text-xs uppercase tracking-wide text-leaf">Core idea</span>
        <p className="mt-1 font-display text-lg text-forest">{card.one_liner}</p>
        {card.problem_statement.plain && (
          <p className="mt-2 text-sm text-ink">{card.problem_statement.plain}</p>
        )}
      </div>

      {card.segments.map((s, i) => (
        <div key={i} className="rounded-2xl border border-line bg-white p-5">
          <SimplifyBlock paperId={paperId} text={s.body} title={s.heading}>
            <p className="mt-1 text-sm text-ink">{s.body}</p>
          </SimplifyBlock>
          {s.analogy && (
            <div className="mt-3 rounded-lg bg-sprout/20 p-3 text-sm text-forest">
              <span className="font-medium">Analogy: </span>
              {s.analogy}
            </div>
          )}
        </div>
      ))}

      {card.takeaways?.length > 0 && (
        <ListCard title="Key takeaways" items={card.takeaways} />
      )}
      {card.glossary?.length > 0 && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="text-sm font-medium text-forest">Glossary</h3>
          <dl className="mt-2 space-y-1 text-sm">
            {card.glossary.map((g, i) => (
              <div key={i} className="flex gap-2">
                <dt className="font-medium text-ink">{g.term}:</dt>
                <dd className="text-muted">{g.definition}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

/* ---------------- shared bits ---------------- */

function Pop({ label, body, tone }: { label: string; body: React.ReactNode; tone?: "forest" }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`rounded-full px-2.5 py-1 text-xs ${
          tone === "forest" ? "bg-forest text-white" : "bg-sprout/30 text-forest"
        } hover:opacity-90`}
      >
        {label || "—"}
      </button>
      {open && (
        <div className="absolute left-0 z-10 mt-1 w-64 rounded-xl border border-line bg-white p-3 text-xs shadow-lg">
          {body}
        </div>
      )}
    </span>
  );
}

function ChipCard({
  title, hint, children,
}: {
  title: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-forest">{title}</h3>
        {hint && <span className="text-[10px] text-muted">{hint}</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">{children}</div>
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

/** Explain-simpler that can target a Paper Card field OR arbitrary text (segments). */
function SimplifyBlock({
  paperId, field, text, title, children,
}: {
  paperId: string;
  field?: string;
  text?: string;
  title?: string;
  children: React.ReactNode;
}) {
  const [level, setLevel] = useState(0);
  const [simpler, setSimpler] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function explain() {
    setBusy(true);
    try {
      const next = level + 1;
      const r = await Api.simplify(paperId, field ? { field, level: next } : { text, level: next });
      setSimpler(r.simplified);
      setLevel(next);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        {title ? <h3 className="font-display text-lg text-forest">{title}</h3> : <span />}
        <button
          onClick={explain}
          disabled={busy || (!text && !field)}
          className="rounded-lg border border-line px-2.5 py-0.5 text-xs text-forest hover:bg-bg disabled:opacity-40"
        >
          {busy ? "…" : simpler ? "Even simpler" : "Explain simpler"}
        </button>
      </div>
      {children}
      {simpler && (
        <div className="mt-2 rounded-lg bg-leaf/10 p-3 text-sm text-forest">
          <span className="mb-1 block text-xs uppercase tracking-wide text-leaf">
            Simpler · level {level}
          </span>
          {simpler}
        </div>
      )}
    </div>
  );
}

function SimplifyCard({
  paperId, title, field, text,
}: {
  paperId: string; title: string; field: string; text: string;
}) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <SimplifyBlock paperId={paperId} field={field} title={title}>
        <p className="mt-1 text-sm text-ink">{text || "—"}</p>
      </SimplifyBlock>
    </div>
  );
}
