"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Api,
  type ComponentSpecLite,
  type Experiment,
  type NodeRunResult,
  type Unresolved,
  type WalkNode,
} from "@/lib/api";

type Status = "idle" | "running" | "done" | "failed";

const KIND_META: Record<
  string,
  { accent: string; soft: string; icon: string; label: string }
> = {
  data: { accent: "#2E6C8E", soft: "#EAF2F8", icon: "🗄", label: "Data" },
  preprocess: { accent: "#6DB33F", soft: "#EEF6E6", icon: "🧹", label: "Preprocess" },
  eda: { accent: "#3F8F5B", soft: "#E7F4EC", icon: "📊", label: "EDA" },
  model: { accent: "#14342A", soft: "#E4EEE8", icon: "🤖", label: "Model" },
  result: { accent: "#B8860B", soft: "#F7F0DE", icon: "📈", label: "Result" },
  inference: { accent: "#6C4FA1", soft: "#F0EBF8", icon: "💡", label: "Inference" },
};
const meta = (k: string) => KIND_META[k] ?? KIND_META.data;

const STATUS_PILL: Record<Status, { bg: string; fg: string; label: string }> = {
  idle: { bg: "#EEF2EF", fg: "#6B7A70", label: "ready" },
  running: { bg: "#FBF0D3", fg: "#8A6D1A", label: "running" },
  done: { bg: "#E4F3DA", fg: "#2E7D32", label: "done" },
  failed: { bg: "#FBE3E1", fg: "#B23A2E", label: "failed" },
};

function StatusPill({ status }: { status: Status }) {
  const s = STATUS_PILL[status];
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 999,
        background: s.bg,
        color: s.fg,
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: s.fg,
          boxShadow: status === "running" ? `0 0 0 3px ${s.fg}33` : "none",
        }}
      />
      {s.label}
    </span>
  );
}

/* ---------------- custom node ---------------- */

type PhaseData = {
  title: string;
  kind: string;
  step: number;
  status: Status;
  selected: boolean;
  runnable: boolean;
};

function PhaseNode({ data }: NodeProps<Node<PhaseData>>) {
  const m = meta(data.kind);
  return (
    <div
      style={{
        width: 214,
        borderRadius: 16,
        background: "#ffffff",
        borderStyle: "solid",
        borderWidth: "1px",
        borderColor: data.selected ? m.accent : "#E7EEE6",
        boxShadow: data.selected
          ? `0 12px 30px ${m.accent}26`
          : "0 2px 10px rgba(20,52,42,0.06)",
        transform: data.selected ? "translateY(-2px)" : "none",
        transition: "box-shadow .18s, transform .18s, border-color .18s",
        overflow: "hidden",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      {/* accent header strip */}
      <div style={{ height: 4, background: `linear-gradient(90deg, ${m.accent}, ${m.accent}88)` }} />
      <div style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              flexShrink: 0,
              borderRadius: 11,
              background: m.soft,
              color: m.accent,
              display: "grid",
              placeItems: "center",
              fontSize: 18,
            }}
          >
            {data.status === "running" ? "⏳" : m.icon}
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 9.5,
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                fontWeight: 700,
                color: m.accent,
              }}
            >
              {String(data.step).padStart(2, "0")} · {m.label}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.25, color: "#14342A" }}>
              {data.title}
            </div>
          </div>
        </div>
        <div
          style={{
            marginTop: 11,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <StatusPill status={data.status} />
          {data.runnable && data.status === "idle" && (
            <span style={{ fontSize: 11, fontWeight: 700, color: m.accent }}>Run ▸</span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { phase: PhaseNode };

/* ---------------- canvas ---------------- */

export default function ExperimentCanvas({ paperId }: { paperId: string }) {
  const [exp, setExp] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [results, setResults] = useState<Record<string, NodeRunResult>>({});
  const [models, setModels] = useState<ComponentSpecLite[]>([]);

  // Every registered model becomes a fork option — so a new model added to the registry (or a
  // paper naming a model we don't have) is always runnable via a comparable stand-in, no UI edit.
  useEffect(() => {
    Api.listComponents()
      .then((r) => setModels(r.components.filter((c) => c.kind === "model")))
      .catch(() => setModels([]));
  }, []);

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
    const nodes: Node[] = exp.walkthrough.map((n, i) => ({
      id: n.id,
      type: "phase",
      // gentle vertical rhythm so the row reads as a flowing path rather than a rigid line
      position: { x: i * 262, y: (i % 2 === 0 ? 0 : 46) },
      data: {
        title: n.title,
        kind: n.kind,
        step: i + 1,
        status: status[n.id] ?? "idle",
        selected: n.id === selectedId,
        runnable: n.kind === "model",
      } satisfies PhaseData,
    }));
    const edges: Edge[] = exp.walkthrough.slice(1).map((n, i) => ({
      id: `e${i}`,
      source: exp.walkthrough[i].id,
      target: n.id,
      type: "smoothstep",
      animated: true,
      style: { stroke: "#9FCE7C", strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#9FCE7C", width: 18, height: 18 },
    }));
    return { nodes, edges };
  }, [exp, status, selectedId]);

  // Once data is available, auto-select the Model step so the run controls are immediately visible
  // (removes the "what do I click now?" gap after generating/uploading data).
  useEffect(() => {
    if (!exp || selectedId) return;
    if (exp.fetch_report.fetched.length === 0) return;
    const model = exp.walkthrough.find((n) => n.kind === "model");
    if (model) setSelectedId(model.id);
  }, [exp, selectedId]);

  if (!exp) {
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center">
        <p className="text-muted">
          Reproduce this paper: fetch (or generate) its data, rebuild its pipeline, then run &amp; fork any
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
  const dataReady = exp.fetch_report.fetched.length > 0;
  const anyRun = Object.keys(results).length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-sprout/30 px-3 py-1 text-sm text-forest">
          status: {exp.status}
        </span>
        <span className="text-sm text-muted">{exp.walkthrough.length} steps · click a node</span>
      </div>

      {/* Guided next-step banner */}
      {!dataReady ? (
        <div className="rounded-lg border border-line bg-white p-3 text-sm text-ink">
          <b>Step 1 — get data.</b> Scroll to the <b>Data</b> panel below and <b>Generate demo data</b>{" "}
          (or upload the paper&apos;s dataset) to begin.
        </div>
      ) : !anyRun ? (
        <div className="rounded-lg border border-leaf/40 bg-leaf/10 p-3 text-sm text-forest">
          <b>Data ready ✓ — Step 2:</b> the <b>Model</b> step is selected on the right. Pick a model and
          click <b>Run model</b> to reproduce the paper (then fork a different model to compare).
        </div>
      ) : (
        <div className="rounded-lg border border-leaf/40 bg-leaf/10 p-3 text-sm text-forest">
          <b>Ran ✓</b> — your metrics are shown against the paper&apos;s in the panel. Fork a different
          model or dataset to keep exploring.
        </div>
      )}

      {hasSynthetic && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          ⚠ Using <b>synthetic demo data</b> — results are approximate and won&apos;t exactly match the paper.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-2">
          <div className="h-[420px] overflow-hidden rounded-2xl border border-line bg-gradient-to-b from-white to-[#F6FAF2]">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              nodesDraggable={false}
              onNodeClick={(_, node) => setSelectedId(node.id)}
            >
              <Background variant={BackgroundVariant.Dots} gap={22} size={1.5} color="#D9E6D2" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <div className="flex flex-wrap gap-3 px-1 text-xs text-muted">
            {Object.entries(KIND_META).map(([k, m]) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: m.accent }} />
                {m.label}
              </span>
            ))}
          </div>
        </div>
        <NodeDetail
          exp={exp}
          node={selected}
          models={models}
          status={selected ? status[selected.id] ?? "idle" : "idle"}
          result={selected ? results[selected.id] : undefined}
          onRun={async (node, datasetId, component) => {
            setStatus((m) => ({ ...m, [node.id]: "running" }));
            try {
              const r = await Api.runNode(exp.id, node.id, {
                dataset_id: datasetId,
                component_id: component || undefined,
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

/* ---------------- node detail ---------------- */

const FALLBACK_MODELS: { id: string; label: string }[] = [
  { id: "model.ml.gradient_boosting", label: "Gradient boosting (trees)" },
  { id: "model.ml.logistic_regression", label: "Logistic regression" },
  { id: "model.ml.linear_regression", label: "Linear regression" },
];

function NodeDetail({
  exp,
  node,
  models,
  status,
  result,
  onRun,
}: {
  exp: Experiment;
  node: WalkNode | null;
  models: ComponentSpecLite[];
  status: Status;
  result?: NodeRunResult;
  onRun: (node: WalkNode, datasetId: string, component: string) => Promise<void>;
}) {
  const modelOptions = models.length
    ? models.map((m) => ({ id: m.id, label: m.name }))
    : FALLBACK_MODELS;
  const [datasetId, setDatasetId] = useState(exp.fetch_report.fetched[0]?.dataset_id ?? "");
  // Default to the paper's own component when the registry recognises it, else its stand-in.
  const [component, setComponent] = useState(
    node?.component_id ?? node?.suggested_component ?? modelOptions[0].id,
  );

  if (!node) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5 text-sm text-muted">
        Click a node in the flow to see what it does and its progress.
      </div>
    );
  }

  const m = meta(node.kind);
  const isModel = node.kind === "model";
  const dsId = datasetId || exp.fetch_report.fetched[0]?.dataset_id || "";
  const noData = exp.fetch_report.fetched.length === 0;
  // A model step is always runnable: if the paper's exact model isn't in the registry, the user
  // picks a comparable one to run under the Evidence Ledger (an honest "fork").
  const nativeUnknown = isModel && !node.component_id;

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg text-forest">{node.title}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            status === "done"
              ? "bg-leaf/20 text-forest"
              : status === "running"
                ? "bg-amber-100 text-amber-800"
                : status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-bg text-muted"
          }`}
        >
          {status}
        </span>
      </div>
      <p className="mt-1 text-xs uppercase tracking-wide" style={{ color: m.accent }}>
        {m.label}
      </p>
      {node.detail && <p className="mt-2 text-sm text-ink">{node.detail}</p>}

      {!isModel ? (
        <p className="mt-3 text-sm text-muted">This is an explanatory step — nothing to run.</p>
      ) : noData ? (
        <p className="mt-3 text-sm text-muted">
          Get data first (fetch or generate demo data below), then run this model.
        </p>
      ) : (
        <div className="mt-3 space-y-2 text-sm">
          {nativeUnknown && (
            <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
              The paper&apos;s model isn&apos;t in the registry — pick a comparable model to run and
              compare against the paper.
            </p>
          )}
          <label className="block">
            <span className="text-muted">Dataset</span>
            <select
              className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={dsId}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              {exp.fetch_report.fetched.map((f) => (
                <option key={f.dataset_id} value={f.dataset_id}>
                  {f.name}
                  {f.synthetic ? " (synthetic)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-muted">Model to run</span>
            <select
              className="mt-1 w-full rounded-lg border border-line px-2 py-1"
              value={component}
              onChange={(e) => setComponent(e.target.value)}
            >
              {node.component_id && (
                <option value={node.component_id}>As paper ({node.component_id})</option>
              )}
              {modelOptions
                .filter((o) => o.id !== node.component_id)
                .map((o) => (
                  <option key={o.id} value={o.id}>
                    {node.suggested_component === o.id && nativeUnknown
                      ? `${o.label} (suggested stand-in)`
                      : o.label}
                  </option>
                ))}
            </select>
          </label>
          <button
            onClick={() => onRun(node, dsId, component)}
            disabled={status === "running"}
            className="rounded-lg bg-forest px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {status === "running" ? "Running…" : "Run model"}
          </button>
          {result && (
            <div className="rounded-lg bg-leaf/10 p-3">
              <p className="text-xs uppercase tracking-wide text-leaf">
                Your run {result.forked ? "(forked)" : ""}
                {result.stand_in ? " · stand-in model" : ""}
                {result.synthetic ? " · synthetic" : ""}
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

/* ---------------- data panel ---------------- */

function DataPanel({ exp, onChange }: { exp: Experiment; onChange: (e: Experiment) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const empty = exp.fetch_report.fetched.length === 0;

  async function genDemo() {
    setBusy(true);
    setError(null);
    try {
      onChange(await Api.demoData(exp.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "demo generation failed");
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

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

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
                {f.name}
                {f.synthetic && (
                  <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">
                    synthetic
                  </span>
                )}
              </span>
              <span className="text-muted">
                {f.n_rows ?? "?"}×{f.n_cols ?? "?"} · {f.resolver}
              </span>
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
