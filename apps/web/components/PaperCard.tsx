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

      <VariablesTable card={card} />

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

      {card.variants?.length > 0 && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="text-sm font-medium text-forest">Variants</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {card.variants.map((v, i) => {
              const name = typeof v === "string" ? v : v.name;
              const desc = typeof v === "string" ? "" : (v.description ?? "");
              return (
                <li key={i}>
                  <span className="font-medium text-forest">{name}</span>
                  {desc && <span className="text-ink"> — {desc}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {(card.detailed_summary || card.best_model || card.models_used.some((m) => m.result)) && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="font-display text-lg text-forest">Summary &amp; model impact</h3>
          {card.detailed_summary && (
            <SimplifyBlock paperId={paperId} text={card.detailed_summary}>
              <p className="mt-1 text-sm text-ink">{card.detailed_summary}</p>
            </SimplifyBlock>
          )}
          {card.best_model && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-leaf/10 p-3 text-sm text-forest">
              <span aria-hidden>🏆</span>
              <span>
                <span className="font-medium">Best model: </span>
                {card.best_model}
              </span>
            </div>
          )}
          {card.models_used.some((m) => m.result) && (
            <div className="mt-3">
              <p className="text-xs uppercase tracking-wide text-leaf">How each model did</p>
              <ul className="mt-2 space-y-2 text-sm">
                {card.models_used
                  .filter((m) => m.result)
                  .map((m, i) => (
                    <li key={i}>
                      <span className="font-medium text-forest">{m.name}: </span>
                      <span className="text-ink">{m.result}</span>
                    </li>
                  ))}
              </ul>
              <p className="mt-2 text-xs text-muted">Click a model above for its math, worked with real data.</p>
            </div>
          )}
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
  return (
    <Pop
      label={m.name}
      wide
      body={
        <div className="space-y-2">
          {m.universal && (
            <div>
              <p className="text-xs uppercase tracking-wide text-leaf">What it is</p>
              <p className="text-ink">{m.universal}</p>
            </div>
          )}
          <div>
            <p className="text-xs uppercase tracking-wide text-leaf">In this paper</p>
            <p className="text-ink">{m.summary || "No summary."}</p>
          </div>
          {m.use_case && (
            <div>
              <p className="text-xs uppercase tracking-wide text-leaf">Practical use case</p>
              <p className="text-ink">{m.use_case}</p>
            </div>
          )}
          {m.example && (
            <div>
              <p className="text-xs uppercase tracking-wide text-leaf">Example</p>
              <p className="text-ink">{m.example}</p>
            </div>
          )}
          {m.result && (
            <div>
              <p className="text-xs uppercase tracking-wide text-leaf">Result in this paper</p>
              <p className="text-ink">{m.result}</p>
            </div>
          )}
          {m.math && m.math.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wide text-leaf">Mathematics (worked with real data)</p>
              <div className="mt-1 space-y-2">
                {m.math.map((mm, i) => (
                  <div key={i} className="rounded-lg bg-bg p-2">
                    <code className="block whitespace-pre-wrap text-forest">{mm.formula}</code>
                    {(mm.plain || mm.explanation) && (
                      <p className="mt-1 text-ink">{mm.plain || mm.explanation}</p>
                    )}
                    {mm.symbols && (
                      <p className="mt-1 whitespace-pre-wrap text-muted">
                        <span className="font-medium text-forest">Symbols: </span>
                        {mm.symbols}
                      </p>
                    )}
                    {(mm.worked_example || mm.example) && (
                      <p className="mt-1 whitespace-pre-wrap rounded bg-leaf/10 p-1.5 text-ink">
                        <span className="font-medium text-forest">Worked example: </span>
                        {mm.worked_example || mm.example}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      }
    />
  );
}

function VariablesTable({ card }: { card: EmpiricalCard }) {
  const [open, setOpen] = useState(false);
  const rows: { v: CardVariable; role: string }[] = [
    ...card.independent_variables.map((v) => ({ v, role: "Feature" })),
    ...(card.target_variable?.name ? [{ v: card.target_variable, role: "Target" }] : []),
  ];
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between">
        <h3 className="font-display text-lg text-forest">Variables table</h3>
        <span className="text-sm text-muted">
          {card.independent_variables.length} features · {open ? "▲ hide" : "▼ show"}
        </span>
      </button>
      {open && (
        <div className="mt-3 overflow-auto rounded-lg border border-line">
          <table className="min-w-full text-sm">
            <thead className="bg-bg text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2">Variable</th>
                <th className="px-3 py-2">Role</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Units</th>
                <th className="px-3 py-2">Description</th>
                <th className="px-3 py-2">Example</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ v, role }, i) => (
                <tr key={i} className="border-t border-line/60">
                  <td className="whitespace-nowrap px-3 py-2 font-medium text-forest">{v.name}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        role === "Target" ? "bg-forest text-white" : "bg-sprout/30 text-forest"
                      }`}
                    >
                      {role}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink">{v.type || "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink">{v.units || "—"}</td>
                  <td className="px-3 py-2 text-muted">{v.description || "—"}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink">{v.example_value || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
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

function Pop({
  label,
  body,
  tone,
  wide,
}: {
  label: string;
  body: React.ReactNode;
  tone?: "forest";
  wide?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    // Hover to open; stays open while the pointer is anywhere in the chip → gap → card region
    // (the popover is a descendant of this span, so moving onto it does NOT fire onMouseLeave).
    <span
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        onClick={() => setOpen(true)}
        className={`rounded-full px-2.5 py-1 text-xs ${
          tone === "forest" ? "bg-forest text-white" : "bg-sprout/30 text-forest"
        } hover:opacity-90`}
      >
        {label || "—"}
      </button>
      {open && (
        // top-full + pt-1.5 bridges the visual gap so the card stays open when you move onto it
        <div className={`absolute left-0 top-full z-20 pt-1.5 ${wide ? "w-80" : "w-64"}`}>
          <div
            className={`${
              wide ? "max-h-96 overflow-y-auto" : ""
            } rounded-xl border border-line bg-white p-3 text-xs shadow-lg`}
          >
            {body}
          </div>
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
