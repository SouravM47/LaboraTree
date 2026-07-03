"use client";

import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Api,
  type Experiment,
  type NodeRunResult,
  type Unresolved,
  type WalkNode,
} from "@/lib/api";

type Status = "idle" | "running" | "done" | "failed";

const KIND_STYLE: Record<string, { bg: string; icon: string }> = {
  data: { bg: "#E8F0F7", icon: "🗄" },
  preprocess: { bg: "#EAF3E1", icon: "🧹" },
  eda: { bg: "#DDEFC9", icon: "📊" },
  model: { bg: "#14342A", icon: "🤖" },
  result: { bg: "#F3EEE1", icon: "📈" },
  inference: { bg: "#EFE9F5", icon: "💡" },
};
const STATUS_BG: Record<Status, string | null> = {
  idle: null,
  running: "#C9A227",
  done: "#6DB33F",
  failed: "#C0392B",
};

export default function ExperimentCanvas({ paperId }: { paperId: string }) {
  const [exp, setExp] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [results, setResults] = useState<Record<string, NodeRunResult>>({});

  async function start() {
    setBusy(true);
    setError(null);
    try {
      setExp(await Api.startExperiment(paperId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const { nodes, edges } = useMemo(() => {
    if (!exp) return { nodes: [] as Node[], edges: [] as Edge[] };
    const nodes: Node[] = exp.walkthrough.map((n, i) => {
      const st = KIND_STYLE[n.kind] ?? KIND_STYLE.data;
      const s = status[n.id] ?? "idle";
      const bg = STATUS_BG[s] ?? st.bg;
      const light = s === "running" || s === "done" || s === "failed" || n.kind === "model";
      return {
        id: n.id,
        position: { x: i * 200, y: (i % 2) * 74 + 20 },
        data: { label: `${s === "running" ? "⏳" : st.icon} ${n.title}` },
        style: {
          background: bg,
          color: light ? "#fff" : "#14342A",
          border: n.id === selectedId ? "2px solid #14342A" : "1px solid #E4EBE1",
          borderRadius: 12,
          padding: 8,
          width: 170,
          fontSize: 12,
        },
      };
    });
    const edges: Edge[] = exp.walkthrough.slice(1).map((n, i) => ({
      id: `e${i}`, source: exp.walkthrough[i].id, target: n.id, animated: true,
      style: { stroke: "#A8D08D" },
    }));
    return { nodes, edges };
  }, [exp, status, selectedId]);

  if (!exp) {
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center">
        <p className="text-muted">
          Reproduce this paper: fetch (or generate) its data, rebuild its pipeline, then run & fork any
          step — clicking a node shows its progress.
        </p>
        <button
          onClick={start}
          disabled={busy}
          className="mt-4 rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Reproducing…" : "Reproduce & Explore"}
        </button>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    );
  }

  const selected = exp.walkthrough.find((n) => n.id === selectedId) ?? null;
  const hasSynthetic = exp.fetch_report.fetched.some((f) => f.synthetic);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-sprout/30 px-3 py-1 text-sm text-forest">status: {exp.status}</span>
        <span className="text-sm text-muted">{exp.walkthrough.length} steps · click a node</span>
      </div>

      {hasSynthetic && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          ⚠ Using <b>synthetic demo data</b> — results are approximate and won&apos;t exactly match the paper.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 h-[380px] overflow-hidden rounded-2xl border border-line bg-white">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            proOptions={{ hideAttribution: true }}
            onNodeClick={(_, node) => setSelectedId(node.id)}
          >
            <Background color="#E4EBE1" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <NodeDetail
          exp={exp}
          node={selected}
          status={selected ? status[selected.id] ?? "idle" : "idle"}
          result={selected ? results[selected.id] : undefined}
          onRun={async (node, datasetId, fork) => {
            setStatus((m) => ({ ...m, [node.id]: "running" }));
            try {
              const r = await Api.runNode(exp.id, node.id, {
                dataset_id: datasetId, component_id: fork || undefined,
              });
              setResults((m) => ({ ...m, [node.id]: r }));
              setStatus((m) => ({ ...m, [node.id]: "done" }));
            } catch {
              setStatus((m) => ({ ...m, [node.id]: "failed" }));
            }
          }}
        />
      </div>

      <DataPanel exp={exp} onChange={setExp} />
    </div>
  );
}

function NodeDetail({
  exp, node, status, result, onRun,
}: {
  exp: Experiment;
  node: WalkNode | null;
  status: Status;
  result?: NodeRunResult;
  onRun: (node: WalkNode, datasetId: string, fork: string) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(exp.fetch_report.fetched[0]?.dataset_id ?? "");
  const [fork, setFork] = useState("");

  if (!node) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5 text-sm text-muted">
        Click a node in the flow to see what it does and its progress.
      </div>
    );
  }
  const runnable = !!node.component_id;
  const dsId = datasetId || exp.fetch_report.fetched[0]?.dataset_id || "";

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg text-forest">{node.title}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            status === "done" ? "bg-leaf/20 text-forest"
              : status === "running" ? "bg-amber-100 text-amber-800"
              : status === "failed" ? "bg-red-100 text-red-700" : "bg-bg text-muted"
          }`}
        >
          {status}
        </span>
      </div>
      <p className="mt-1 text-xs uppercase tracking-wide text-leaf">{node.kind}</p>
      {node.detail && <p className="mt-2 text-sm text-ink">{node.detail}</p>}

      {!runnable ? (
        <p className="mt-3 text-sm text-muted">This is an explanatory step — nothing to run.</p>
      ) : exp.fetch_report.fetched.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Get data first (fetch or generate demo data), then run.</p>
      ) : (
        <div className="mt-3 space-y-2 text-sm">
          <label className="block">
            <span className="text-muted">Dataset</span>
            <select className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={dsId} onChange={(e) => setDatasetId(e.target.value)}>
              {exp.fetch_report.fetched.map((f) => (
                <option key={f.dataset_id} value={f.dataset_id}>
                  {f.name}{f.synthetic ? " (synthetic)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-muted">Fork model (optional)</span>
            <select className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={fork} onChange={(e) => setFork(e.target.value)}>
              <option value="">As paper ({node.component_id})</option>
              <option value="model.ml.logistic_regression">Logistic regression</option>
              <option value="model.ml.linear_regression">Linear regression</option>
            </select>
          </label>
          <button
            onClick={() => onRun(node, dsId, fork)}
            disabled={status === "running"}
            className="rounded-lg bg-forest px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {status === "running" ? "Running…" : "Run step"}
          </button>
          {result && (
            <div className="rounded-lg bg-leaf/10 p-3">
              <p className="text-xs uppercase tracking-wide text-leaf">
                Your run {result.forked ? "(forked)" : ""}{result.synthetic ? " · synthetic" : ""}
              </p>
              <ul className="mt-1">
                {Object.entries(result.metrics).map(([k, v]) => (
                  <li key={k} className="flex justify-between">
                    <span className="text-muted">{k}</span>
                    <span className="font-medium text-forest">{v}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted">
                Paper reported: <span className="text-ink">{result.paper_reported || "—"}</span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DataPanel({ exp, onChange }: { exp: Experiment; onChange: (e: Experiment) => void }) {
  const [busy, setBusy] = useState(false);
  const empty = exp.fetch_report.fetched.length === 0;

  async function genDemo() {
    setBusy(true);
    try {
      onChange(await Api.demoData(exp.id));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg text-forest">Data</h3>
        <button
          onClick={genDemo}
          disabled={busy}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
            empty ? "bg-leaf text-white hover:opacity-90" : "border border-line text-forest hover:bg-bg"
          } disabled:opacity-50`}
        >
          {busy ? "Generating…" : "Generate demo data"}
        </button>
      </div>

      {empty ? (
        <p className="mt-2 text-sm text-muted">
          Nothing was auto-fetched (the paper didn&apos;t name a dataset we can retrieve). Upload the
          real data below, or <b>generate realistic demo data</b> to proceed.
        </p>
      ) : (
        <ul className="mt-3 space-y-1 text-sm">
          {exp.fetch_report.fetched.map((f) => (
            <li key={f.dataset_id} className="flex justify-between">
              <span className="text-ink">
                {f.name}{f.synthetic && <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">synthetic</span>}
              </span>
              <span className="text-muted">{f.n_rows ?? "?"}×{f.n_cols ?? "?"} · {f.resolver}</span>
            </li>
          ))}
        </ul>
      )}

      {exp.fetch_report.unresolved.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-ink">Or upload the paper&apos;s data</p>
          <ul className="mt-2 space-y-3">
            {exp.fetch_report.unresolved.map((u) => (
              <UnresolvedItem key={u.name} exp={exp} u={u} onChange={onChange} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UnresolvedItem({
  exp, u, onChange,
}: {
  exp: Experiment; u: Unresolved; onChange: (e: Experiment) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <li className="rounded-lg bg-bg p-3 text-sm">
      <p className="text-ink">{u.name}</p>
      <p className="mt-0.5 text-xs text-muted">{u.instructions}</p>
      <input
        type="file"
        className="mt-2 text-xs"
        disabled={busy}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          setBusy(true);
          try {
            onChange(await Api.uploadExperimentData(exp.id, u.name, file));
          } finally {
            setBusy(false);
          }
        }}
      />
    </li>
  );
}
