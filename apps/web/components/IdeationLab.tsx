"use client";

import { useState } from "react";
import { Api, type IdeationSession } from "@/lib/api";

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
