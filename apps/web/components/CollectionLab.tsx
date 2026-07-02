"use client";

import { useState } from "react";
import { Api, type BiasFinding, type PilotResult, type SampleResult, type SurveyQuestion } from "@/lib/api";

const TOOLS = ["sample", "questionnaire", "bias", "pilot"] as const;
type Tool = (typeof TOOLS)[number];
const LABELS: Record<Tool, string> = {
  sample: "Sample size",
  questionnaire: "Questionnaire",
  bias: "Bias check",
  pilot: "Synthetic pilot",
};

export default function CollectionLab({ projectId }: { projectId: string }) {
  const [tool, setTool] = useState<Tool>("sample");
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {TOOLS.map((t) => (
          <button
            key={t}
            onClick={() => setTool(t)}
            className={`rounded-full px-3 py-1.5 text-sm ${
              tool === t ? "bg-forest text-white" : "border border-line text-forest hover:bg-bg"
            }`}
          >
            {LABELS[t]}
          </button>
        ))}
      </div>
      {tool === "sample" && <SampleTool projectId={projectId} />}
      {tool === "questionnaire" && <QuestionnaireTool projectId={projectId} />}
      {tool === "bias" && <BiasTool projectId={projectId} />}
      {tool === "pilot" && <PilotTool projectId={projectId} />}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="font-display text-lg text-forest">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function SampleTool({ projectId }: { projectId: string }) {
  const [confidence, setConfidence] = useState(0.95);
  const [margin, setMargin] = useState(0.05);
  const [population, setPopulation] = useState("");
  const [res, setRes] = useState<SampleResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    try {
      setRes(await Api.sampleSize(projectId, {
        confidence, margin, proportion: 0.5,
        population: population ? Number(population) : null,
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Sample size (power) calculator">
      <div className="flex flex-wrap items-end gap-3 text-sm">
        <label className="block">
          <span className="text-muted">Confidence</span>
          <select className="mt-1 block rounded-lg border border-line px-2 py-1"
            value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}>
            {[0.8, 0.9, 0.95, 0.99].map((v) => <option key={v} value={v}>{v * 100}%</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-muted">Margin of error</span>
          <input type="number" step="0.01" className="mt-1 block w-24 rounded-lg border border-line px-2 py-1"
            value={margin} onChange={(e) => setMargin(Number(e.target.value))} />
        </label>
        <label className="block">
          <span className="text-muted">Population (optional)</span>
          <input className="mt-1 block w-32 rounded-lg border border-line px-2 py-1"
            value={population} onChange={(e) => setPopulation(e.target.value)} placeholder="∞" />
        </label>
        <button onClick={go} disabled={busy}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
          Calculate
        </button>
      </div>
      {res && (
        <div className="mt-4 rounded-xl bg-leaf/10 p-4">
          <span className="text-3xl font-semibold text-forest">{res.sample_size}</span>
          <span className="ml-2 text-sm text-muted">respondents needed</span>
        </div>
      )}
    </Card>
  );
}

function QuestionnaireTool({ projectId }: { projectId: string }) {
  const [goal, setGoal] = useState("");
  const [audience, setAudience] = useState("");
  const [questions, setQuestions] = useState<SurveyQuestion[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    if (goal.trim().length < 4) return;
    setBusy(true); setError(null);
    try {
      const r = await Api.designQuestionnaire(projectId, { goal: goal.trim(), audience, n: 6 });
      setQuestions(r.questions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Questionnaire designer">
      <input className="w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
        placeholder="Research goal" value={goal} onChange={(e) => setGoal(e.target.value)} />
      <div className="mt-2 flex gap-2">
        <input className="flex-1 rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
          placeholder="Audience (optional)" value={audience} onChange={(e) => setAudience(e.target.value)} />
        <button onClick={go} disabled={busy}
          className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
          {busy ? "Designing…" : "Design"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <ol className="mt-4 space-y-2">
        {questions.map((q) => (
          <li key={q.id} className="rounded-lg bg-bg p-3 text-sm">
            <span className="text-ink">{q.text}</span>
            <span className="ml-2 rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">{q.type}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function BiasTool({ projectId }: { projectId: string }) {
  const [text, setText] = useState("");
  const [findings, setFindings] = useState<BiasFinding[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    const questions = text.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!questions.length) return;
    setBusy(true);
    try {
      setFindings((await Api.biasCheck(projectId, questions)).findings);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Leading-question (bias) check">
      <textarea rows={5} className="w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
        placeholder="One question per line…" value={text} onChange={(e) => setText(e.target.value)} />
      <button onClick={go} disabled={busy}
        className="mt-2 rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
        {busy ? "Auditing…" : "Audit questions"}
      </button>
      {findings && (
        findings.length === 0 ? (
          <p className="mt-3 text-sm text-leaf">No biased questions detected.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {findings.map((f, i) => (
              <li key={i} className="rounded-lg bg-red-50 p-3 text-sm">
                <p className="text-ink">“{f.question}”</p>
                <p className="mt-1 text-red-700">{f.severity} · {f.issue}</p>
                <p className="mt-1 text-muted">→ {f.suggestion}</p>
              </li>
            ))}
          </ul>
        )
      )}
    </Card>
  );
}

function PilotTool({ projectId }: { projectId: string }) {
  const [text, setText] = useState("");
  const [persona, setPersona] = useState("");
  const [res, setRes] = useState<PilotResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    const questions = text.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!questions.length || !persona.trim()) return;
    setBusy(true);
    try {
      setRes(await Api.pilot(projectId, { questions, persona: persona.trim(), n: 3 }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Synthetic pilot respondents">
      <input className="w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
        placeholder="Respondent persona (e.g. busy urban commuter)" value={persona}
        onChange={(e) => setPersona(e.target.value)} />
      <textarea rows={4} className="mt-2 w-full rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
        placeholder="One question per line…" value={text} onChange={(e) => setText(e.target.value)} />
      <button onClick={go} disabled={busy}
        className="mt-2 rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50">
        {busy ? "Simulating…" : "Run pilot"}
      </button>
      {res && (
        <div className="mt-3 space-y-2">
          {res.respondents.map((r, i) => (
            <div key={i} className="rounded-lg bg-bg p-3 text-sm">
              <p className="text-xs uppercase tracking-wide text-leaf">respondent {i + 1}</p>
              <ul className="mt-1 text-ink">
                {Object.entries(r).map(([q, a]) => (
                  <li key={q}><span className="text-muted">Q{q}:</span> {a}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
