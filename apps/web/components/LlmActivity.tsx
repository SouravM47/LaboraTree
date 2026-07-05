"use client";

import { useEffect, useState } from "react";
import { Api, type LlmCall, type LlmSummary } from "@/lib/api";

const LIMITS = [25, 50, 100, 500];

function fmtTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z"); // stored UTC
  if (Number.isNaN(d.getTime())) return "—";
  const secs = Math.round((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return d.toLocaleString();
}

export default function LlmActivity({ projectId }: { projectId: string }) {
  const [summary, setSummary] = useState<LlmSummary | null>(null);
  const [calls, setCalls] = useState<LlmCall[]>([]);
  const [limit, setLimit] = useState(25);

  function load() {
    Api.llmSummary(projectId).then(setSummary).catch(() => setSummary(null));
    Api.llmCalls(projectId, limit).then(setCalls).catch(() => setCalls([]));
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [projectId, limit]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl text-forest">LLM activity</h2>
          <p className="text-sm text-muted">Every model call in this project, by Lab.</p>
        </div>
        <button onClick={load} className="rounded-lg border border-line px-3 py-1.5 text-sm text-forest hover:bg-bg">
          Refresh
        </button>
      </div>

      {summary && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Stat label="Calls" value={summary.totals.calls} />
          <Stat label="Tokens" value={summary.totals.tokens.toLocaleString()} />
          <Stat label="Est. cost (USD)" value={summary.totals.cost_usd || "—"} />
        </div>
      )}

      {summary && summary.by_lab.length > 0 && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <h3 className="font-display text-lg text-forest">By Lab</h3>
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-muted">
              <tr className="border-b border-line">
                <th className="py-2">Lab</th><th className="py-2">Calls</th>
                <th className="py-2">Tokens</th><th className="py-2">Avg latency</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_lab.map((l) => (
                <tr key={l.lab} className="border-b border-line/60">
                  <td className="py-2 font-medium text-forest">{l.lab}</td>
                  <td className="py-2">{l.calls}</td>
                  <td className="py-2">{l.tokens.toLocaleString()}</td>
                  <td className="py-2 text-muted">{l.avg_latency_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-2xl border border-line bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-display text-lg text-forest">
            Recent calls{" "}
            <span className="text-sm font-normal text-muted">
              (showing {calls.length}
              {summary && summary.totals.calls > calls.length ? ` of ${summary.totals.calls}` : ""})
            </span>
          </h3>
          <label className="flex items-center gap-1.5 text-xs text-muted">
            Show
            <select
              className="rounded-lg border border-line px-2 py-1 text-forest"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              {LIMITS.map((n) => (
                <option key={n} value={n}>
                  {n === 500 ? "max" : `last ${n}`}
                </option>
              ))}
            </select>
          </label>
        </div>
        {calls.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            No LLM calls yet. Generate a Paper Card, run the Co-Scientist, or use a Collection tool.
          </p>
        ) : (
          <div className="mt-3 max-h-[28rem] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-4">When</th>
                  <th className="py-2 pr-4">Lab · op</th><th className="py-2 pr-4">Model</th>
                  <th className="py-2 pr-4">Tokens</th><th className="py-2 pr-4">Latency</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {calls.map((c) => (
                  <tr key={c.id} className="border-b border-line/60">
                    <td className="whitespace-nowrap py-2 pr-4 text-muted" title={new Date(c.created_at).toLocaleString()}>
                      {fmtTime(c.created_at)}
                    </td>
                    <td className="py-2 pr-4 text-forest">{c.lab} · {c.operation}</td>
                    <td className="py-2 pr-4 text-muted">{c.model}</td>
                    <td className="py-2 pr-4">{c.total_tokens}</td>
                    <td className="py-2 pr-4 text-muted">{Math.round(c.latency_ms)} ms</td>
                    <td className="py-2">
                      <span className={c.status === "ok" ? "text-leaf" : "text-red-600"}>{c.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="text-2xl font-semibold text-forest">{value}</div>
      <div className="text-sm text-muted">{label}</div>
    </div>
  );
}
