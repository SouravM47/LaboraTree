"use client";

import { useState } from "react";
import { Api } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string; citations?: number[] };

export default function ChatPanel({ paperId }: { paperId: string }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    const question = q.trim();
    setMessages((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const r = await Api.chat(paperId, question);
      setMessages((m) => [...m, { role: "assistant", text: r.answer, citations: r.citations }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: err instanceof Error ? err.message : "error" },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-line bg-white p-5">
      <h3 className="font-display text-lg text-forest">Chat with paper</h3>
      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-sm text-muted">Ask anything about this paper — answers cite passages.</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg p-3 text-sm ${
              m.role === "user" ? "bg-bg text-ink" : "bg-leaf/10 text-forest"
            }`}
          >
            {m.text}
            {m.citations && m.citations.length > 0 && (
              <div className="mt-1 text-xs text-muted">passages: {m.citations.join(", ")}</div>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-muted">Thinking…</p>}
      </div>
      <form onSubmit={ask} className="mt-3 flex gap-2">
        <input
          className="flex-1 rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
          placeholder="Ask a question…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          disabled={busy}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
