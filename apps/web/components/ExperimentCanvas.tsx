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

const KIND_STYLE: Record<string, { bg: string; color: string; icon: string }> = {
  data: { bg: "#E8F0F7", color: "#14342A", icon: "🗄" },
  preprocess: { bg: "#EAF3E1", color: "#14342A", icon: "🧹" },
  eda: { bg: "#6DB33F", color: "#ffffff", icon: "📊" },
  model: { bg: "#14342A", color: "#ffffff", icon: "🤖" },
  result: { bg: "#F3EEE1", color: "#14342A", icon: "📈" },
  inference: { bg: "#EFE9F5", color: "#14342A", icon: "💡" },
};

export default function ExperimentCanvas({ paperId }: { paperId: string }) {
  const [exp, setExp] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WalkNode | null>(null);

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
      const s = KIND_STYLE[n.kind] ?? KIND_STYLE.data;
      return {
        id: n.id,
        position: { x: i * 210, y: (i % 2) * 70 + 20 },
        data: { label: `${s.icon} ${n.title}` },
        style: {
          background: s.bg,
          color: s.color,
          border: "1px solid #E4EBE1",
          borderRadius: 12,
          padding: 8,
          width: 180,
          fontSize: 12,
        },
      };
    });
    const edges: Edge[] = exp.walkthrough.slice(1).map((n, i) => ({
      id: `e${i}`,
      source: exp.walkthrough[i].id,
      target: n.id,
      animated: true,
      style: { stroke: "#A8D08D" },
    }));
    return { nodes, edges };
  }, [exp]);

  if (!exp) {
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center">
        <p className="text-muted">
          Reproduce this paper: auto-fetch its data, rebuild its pipeline, then fork any node.
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-sprout/30 px-3 py-1 text-sm text-forest">
          status: {exp.status}
        </span>
        <span className="text-sm text-muted">{exp.walkthrough.length} steps</span>
      </div>

      <div className="h-[360px] overflow-hidden rounded-2xl border border-line bg-white">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onNodeClick={(_, node) =>
            setSelected(exp.walkthrough.find((n) => n.id === node.id) ?? null)
          }
        >
          <Background color="#E4EBE1" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <DataPanel exp={exp} onChange={setExp} />
        <RunPanel exp={exp} selected={selected} />
      </div>
    </div>
  );
}

function DataPanel({ exp, onChange }: { exp: Experiment; onChange: (e: Experiment) => void }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="font-display text-lg text-forest">Data</h3>
      <div className="mt-3">
        <p className="text-sm font-medium text-ink">Fetched automatically</p>
        {exp.fetch_report.fetched.length ? (
          <ul className="mt-1 space-y-1 text-sm">
            {exp.fetch_report.fetched.map((f) => (
              <li key={f.dataset_id} className="flex justify-between">
                <span className="text-ink">{f.name}</span>
                <span className="text-muted">
                  {f.n_rows ?? "?"}×{f.n_cols ?? "?"} · {f.resolver}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-muted">none</p>
        )}
      </div>

      {exp.fetch_report.unresolved.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-ink">Needs your upload (couldn&apos;t auto-fetch)</p>
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
  exp,
  u,
  onChange,
}: {
  exp: Experiment;
  u: Unresolved;
  onChange: (e: Experiment) => void;
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

function RunPanel({ exp, selected }: { exp: Experiment; selected: WalkNode | null }) {
  const runnable = exp.walkthrough.filter((n) => n.component_id);
  const node = selected?.component_id ? selected : runnable[0] ?? null;
  const [datasetId, setDatasetId] = useState(exp.fetch_report.fetched[0]?.dataset_id ?? "");
  const [fork, setFork] = useState("");
  const [result, setResult] = useState<NodeRunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!node || !datasetId) return;
    setBusy(true);
    setError(null);
    try {
      setResult(
        await Api.runNode(exp.id, node.id, {
          dataset_id: datasetId,
          component_id: fork || undefined,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "run failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="font-display text-lg text-forest">Run &amp; compare</h3>
      {!node ? (
        <p className="mt-2 text-sm text-muted">No runnable model node in this walkthrough.</p>
      ) : exp.fetch_report.fetched.length === 0 ? (
        <p className="mt-2 text-sm text-muted">Upload the data first, then run.</p>
      ) : (
        <div className="mt-3 space-y-3 text-sm">
          <p className="text-ink">
            Node: <span className="font-medium text-forest">{node.title}</span>
          </p>
          <label className="block">
            <span className="text-muted">Dataset</span>
            <select
              className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              {exp.fetch_report.fetched.map((f) => (
                <option key={f.dataset_id} value={f.dataset_id}>
                  {f.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-muted">Fork model (optional)</span>
            <select
              className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={fork}
              onChange={(e) => setFork(e.target.value)}
            >
              <option value="">As paper ({node.component_id})</option>
              <option value="model.ml.logistic_regression">Logistic regression</option>
              <option value="model.ml.linear_regression">Linear regression</option>
            </select>
          </label>
          <button
            onClick={run}
            disabled={busy}
            className="rounded-lg bg-forest px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Running…" : "Run node"}
          </button>
          {error && <p className="text-red-600">{error}</p>}
          {result && (
            <div className="rounded-lg bg-leaf/10 p-3">
              <p className="text-xs uppercase tracking-wide text-leaf">
                Your run {result.forked ? "(forked)" : ""}
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
