"use client";

import { useState } from "react";
import { Api, type ChatTurn, type EvidenceResult, type IdeationSession } from "@/lib/api";

export default function IdeationLab({ projectId }: { projectId: string }) {
  const [goal, setGoal] = useState("");
  const [n, setN] = useState(4);
  const [session, setSession] = useState<IdeationSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (goal.trim().length < 4) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await Api.runIdeation(projectId, { goal: goal.trim(), n, evolve_n: 2 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <EvidenceHunt projectId={projectId} />

      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Co-Scientist</h2>
        <p className="mt-1 text-sm text-muted">
          State a research goal. Agents generate hypotheses, debate them in an Elo tournament,
          evolve the strongest, and synthesize a direction.
        </p>
        <form onSubmit={run} className="mt-4 space-y-3">
          <textarea
            className="w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
            rows={2}
            placeholder="e.g. How might we reduce urban heat islands in dense cities?"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <div className="flex items-center gap-3 text-sm">
            <label className="text-muted">
              Hypotheses{" "}
              <select
                className="ml-1 rounded-lg border border-line px-2 py-1"
                value={n}
                onChange={(e) => setN(Number(e.target.value))}
              >
                {[3, 4, 5, 6].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={busy}
              className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Running tournament…" : "Run Co-Scientist"}
            </button>
          </div>
        </form>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {session && (
        <>
          <div className="rounded-2xl border border-line bg-leaf/10 p-5">
            <h3 className="font-display text-lg text-forest">Research direction</h3>
            <p className="mt-2 text-sm text-ink">{session.meta_review}</p>
          </div>

          <div className="space-y-3">
            {session.hypotheses.map((h) => (
              <div key={h.id} className="rounded-2xl border border-line bg-white p-4">
                <div className="flex items-start gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-forest text-sm font-semibold text-white">
                    {h.rank}
                  </span>
                  <div className="flex-1">
                    <p className="text-ink">{h.text}</p>
                    {h.critique && <p className="mt-1 text-xs text-muted">{h.critique}</p>}
                    <InlineEvidence projectId={projectId} hypothesis={h.text} />
                  </div>
                  <div className="text-right text-xs">
                    <div className="text-muted">Elo {Math.round(h.elo)}</div>
                    {h.origin === "evolved" && (
                      <span className="mt-1 inline-block rounded-full bg-sprout/40 px-2 py-0.5 text-forest">
                        evolved
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ---------------- Evidence Hunt ---------------- */

const STANCE_STYLE: Record<string, { bg: string; label: string }> = {
  supports: { bg: "bg-green-100 text-green-800", label: "supports" },
  refutes: { bg: "bg-red-100 text-red-700", label: "refutes" },
  mixed: { bg: "bg-amber-100 text-amber-800", label: "mixed evidence" },
  inconclusive: { bg: "bg-bg text-muted", label: "inconclusive" },
};

function EvidenceHunt({ projectId }: { projectId: string }) {
  const [hypothesis, setHypothesis] = useState("");
  const [result, setResult] = useState<EvidenceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (hypothesis.trim().length < 8) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await Api.evidenceHunt(projectId, hypothesis.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence hunt failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h2 className="font-display text-xl text-forest">Evidence hunt</h2>
      <p className="mt-1 text-sm text-muted">
        State a conceptual hypothesis. The agent searches the open web for papers, studies and
        articles, then returns a cited brief — what the evidence says, and the variables to test next.
      </p>
      <form onSubmit={run} className="mt-4 space-y-3">
        <textarea
          className="w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
          rows={2}
          placeholder="e.g. If female literacy rises in rural India, rural development improves."
          value={hypothesis}
          onChange={(e) => setHypothesis(e.target.value)}
        />
        <button
          disabled={busy || hypothesis.trim().length < 8}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Searching the web…" : "🔍 Gather evidence"}
        </button>
      </form>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {result && <EvidenceBriefView projectId={projectId} result={result} />}
    </div>
  );
}

function InlineEvidence({ projectId, hypothesis }: { projectId: string; hypothesis: string }) {
  const [result, setResult] = useState<EvidenceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await Api.evidenceHunt(projectId, hypothesis));
    } catch (err) {
      setError(err instanceof Error ? err.message : "evidence hunt failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2">
      {!result && (
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-forest hover:bg-bg disabled:opacity-50"
        >
          {busy ? "Searching…" : "🔍 Gather evidence"}
        </button>
      )}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {result && <EvidenceBriefView projectId={projectId} result={result} compact />}
    </div>
  );
}

function EvidenceBriefView({
  projectId,
  result,
  compact,
}: {
  projectId: string;
  result: EvidenceResult;
  compact?: boolean;
}) {
  const { brief, sources } = result;
  const stance = STANCE_STYLE[brief.stance] ?? STANCE_STYLE.inconclusive;
  // turn [n] citations into clickable references to the sources list
  const cite = (text: string) =>
    text.split(/(\[\d+\])/g).map((part, i) => {
      const m = part.match(/^\[(\d+)\]$/);
      if (!m) return <span key={i}>{part}</span>;
      const idx = Number(m[1]) - 1;
      const src = sources[idx];
      return (
        <a
          key={i}
          href={src?.url}
          target="_blank"
          rel="noreferrer"
          title={src?.title}
          className="align-super text-[10px] font-semibold text-leaf hover:underline"
        >
          [{m[1]}]
        </a>
      );
    });

  return (
    <div className={`${compact ? "mt-2" : "mt-4"} space-y-3 rounded-xl border border-line bg-bg/60 p-4`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${stance.bg}`}>
          {stance.label}
        </span>
        {typeof brief.confidence === "number" && (
          <span className="text-xs text-muted">confidence {Math.round(brief.confidence * 100)}%</span>
        )}
        <span className="text-xs text-muted">· {sources.length} sources</span>
      </div>

      <p className="text-sm leading-relaxed text-ink">{cite(brief.summary)}</p>

      {brief.key_findings?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-forest">Key findings</p>
          <ul className="mt-1 space-y-1 text-sm text-ink">
            {brief.key_findings.map((f, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-leaf">•</span>
                <span>
                  {f.finding}{" "}
                  {(f.sources ?? []).map((n) => {
                    const src = sources[n - 1];
                    return (
                      <a
                        key={n}
                        href={src?.url}
                        target="_blank"
                        rel="noreferrer"
                        title={src?.title}
                        className="align-super text-[10px] font-semibold text-leaf hover:underline"
                      >
                        [{n}]
                      </a>
                    );
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {brief.variables_to_test?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-forest">
            Variables to test next
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {brief.variables_to_test.map((v, i) => (
              <span
                key={i}
                title={v.rationale}
                className="rounded-lg border border-line bg-white px-2 py-0.5 text-xs text-ink"
              >
                <b className="text-forest">{v.name}</b>
                <span className="ml-1 text-muted">· {v.role}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {brief.insights?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-forest">Insights</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink">
            {brief.insights.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {brief.gaps?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Gaps &amp; caveats</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-muted">
            {brief.gaps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {sources.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer font-semibold text-forest">Sources ({sources.length})</summary>
          <ol className="mt-2 space-y-1">
            {sources.map((s, i) => (
              <li key={s.url} className="flex gap-1.5">
                <span className="text-muted">[{i + 1}]</span>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate text-leaf hover:underline"
                  title={s.title}
                >
                  {s.title || s.url}
                </a>
              </li>
            ))}
          </ol>
        </details>
      )}

      <BrainstormChat projectId={projectId} result={result} />
    </div>
  );
}

function BrainstormChat({ projectId, result }: { projectId: string; result: EvidenceResult }) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    const history = turns;
    setTurns((t) => [...t, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const { answer } = await Api.brainstorm(projectId, {
        hypothesis: result.hypothesis,
        brief: result.brief,
        sources: result.sources,
        question: q,
        history,
      });
      setTurns((t) => [...t, { role: "assistant", content: answer }]);
    } catch (err) {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: err instanceof Error ? `⚠ ${err.message}` : "⚠ failed" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-t border-line pt-3">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-forest hover:bg-bg"
        >
          💬 Brainstorm with the evidence
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-forest">
            Brainstorm — grounded in this brief
          </p>
          {turns.length > 0 && (
            <div className="max-h-72 space-y-2 overflow-auto rounded-lg border border-line bg-white p-2">
              {turns.map((t, i) => (
                <div
                  key={i}
                  className={`text-sm ${t.role === "user" ? "text-ink" : "text-forest"}`}
                >
                  <span className="mr-1 text-xs font-semibold text-muted">
                    {t.role === "user" ? "You" : "Agent"}
                  </span>
                  <p className="whitespace-pre-wrap">{t.content}</p>
                </div>
              ))}
              {busy && <p className="text-xs text-muted">thinking…</p>}
            </div>
          )}
          <form onSubmit={send} className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-line px-3 py-1.5 text-sm outline-none focus:border-leaf"
              placeholder="e.g. What confounders should I control for? What data would settle this?"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              disabled={busy || !input.trim()}
              className="rounded-lg bg-forest px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "…" : "Ask"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
