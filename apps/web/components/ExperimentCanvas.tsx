"use client";

import { useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";
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
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { animated, useSpring } from "@react-spring/web";
import ModelAnimation, { isFeatureSelection, modelKind } from "@/components/ModelAnimation";
import ResultsComparison from "@/components/ResultsComparison";
import StagedModelAnimation from "@/components/StagedModelAnimation";
import ModelExplainerCard from "@/components/ModelExplainerCard";
import FeatureSelectionAnimation from "@/components/FeatureSelectionAnimation";

/** A "model" node that is really a dedicated feature-selection step (BBO) — no model family named. */
function isFeatSelNode(n: { kind: string; title?: string; component_id?: string | null }): boolean {
  const t = n.title || n.component_id || "";
  return n.kind === "model" && isFeatureSelection(t) && modelKind(t) === "generic";
}
import VegaChart from "@/components/VegaChart";
import {
  Api,
  type ColProfile,
  type ComponentSpecLite,
  type DatasetPreview,
  type DatasetProfile,
  type EmpiricalCard,
  type Experiment,
  type NodeRunResult,
  type PreprocessOp,
  type PreprocessPreview,
  type RowFilter,
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
  eval: { accent: "#C9A227", soft: "#FBF3D6", icon: "🏁", label: "Evaluation" },
  result: { accent: "#B8860B", soft: "#F7F0DE", icon: "📈", label: "Result" },
  inference: { accent: "#6C4FA1", soft: "#F0EBF8", icon: "💡", label: "Inference" },
};
const meta = (k: string) => KIND_META[k] ?? KIND_META.data;

const EVAL_ID = "__eval__";
// pick the headline metric to rank models by (higher = better for all of these)
const METRIC_ORDER = ["roc_auc", "f1_macro", "f1", "accuracy", "r2"];
function primaryMetric(m: Record<string, number>): { key: string; value: number } {
  for (const k of METRIC_ORDER) if (k in m) return { key: k, value: m[k] };
  const e = Object.entries(m);
  return e.length ? { key: e[0][0], value: e[0][1] } : { key: "", value: -Infinity };
}

// per-metric: formula, a worked example (using TP=90,TN=45,FP=0,FN=5), and how to read it
const METRIC_HELP: {
  key: string;
  formula: string;
  example: string;
  interpret: string;
  when: string;
}[] = [
  {
    key: "accuracy",
    formula: "(TP + TN) / (TP + TN + FP + FN)",
    example: "(90 + 45) / (90 + 45 + 0 + 5) = 135/140 = 0.964",
    interpret: "Share of all predictions that were right. Can look great even when one class is rare — check precision/recall too.",
    when: "Use when classes are roughly balanced and every mistake costs about the same. Avoid as the ONLY metric on rare-event data (predicting 'no disease' for everyone can score 95%).",
  },
  {
    key: "precision",
    formula: "TP / (TP + FP)",
    example: "90 / (90 + 0) = 1.00",
    interpret: "When it says 'positive', how often it's right. High precision = few false alarms.",
    when: "Prioritize when a FALSE ALARM is expensive — spam filters (don't bin real mail), fraud teams with limited investigators, flagging students for cheating.",
  },
  {
    key: "recall",
    formula: "TP / (TP + FN)",
    example: "90 / (90 + 5) = 0.947",
    interpret: "Of the truly positive cases, how many it caught. High recall = few missed cases.",
    when: "Prioritize when a MISS is expensive — disease screening, safety inspections, security threats. Missing a sick patient is far worse than one extra test.",
  },
  {
    key: "f1_macro",
    formula: "2 · (precision · recall) / (precision + recall)",
    example: "2 · (1.00 · 0.947) / (1.00 + 0.947) = 0.973",
    interpret: "One number balancing precision and recall (macro = averaged over classes equally).",
    when: "Use when classes are imbalanced or you must balance false alarms vs misses in one score — the usual headline metric for medical/fraud papers.",
  },
  {
    key: "roc_auc",
    formula: "area under the TPR-vs-FPR curve",
    example: "1.0 = perfect ranking, 0.5 = random",
    interpret: "How well the model ranks positives above negatives, across ALL thresholds at once.",
    when: "Use to compare models before choosing a decision threshold, or when the threshold will be tuned later. Less meaningful on extremely imbalanced data (see precision instead).",
  },
  {
    key: "r2",
    formula: "1 − Σ(y−ŷ)² / Σ(y−ȳ)²",
    example: "1 − 120/1000 = 0.88 → explains 88% of the variation",
    interpret: "How much of the outcome's variation the model explains (1 = perfect, 0 = no better than guessing the average).",
    when: "The default score for regression — compare models on the same data. Beware: adding features never lowers it, so pair with rmse/mae for honesty.",
  },
  {
    key: "rmse",
    formula: "√( mean( (y − ŷ)² ) )",
    example: "√mean(2², 1², 3²) = √4.67 ≈ 2.16 (same units as the target)",
    interpret: "Typical prediction error, punishing BIG misses extra hard (errors are squared).",
    when: "Use when large errors are disproportionately bad (dosage, structural load). Same units as the target, so it's easy to judge: 'off by ~2.2 mg/dL on average'.",
  },
  {
    key: "mae",
    formula: "mean( |y − ŷ| )",
    example: "mean(2, 1, 3) = 2.0",
    interpret: "Average absolute miss — every unit of error counts the same.",
    when: "Use when errors hurt proportionally and outliers shouldn't dominate the score (house prices, demand forecasts). More robust than rmse to a few wild rows.",
  },
];

// react-spring 9.x ships types that predate React 19, so animated.* JSX children are mistyped.
// Cast to permissive aliases — runtime behaviour is correct.
type AnimatedTag = (props: {
  className?: string;
  style?: Record<string, unknown>;
  children?: ReactNode;
}) => ReactElement;
const ADiv = animated.div as unknown as AnimatedTag;
const ATd = animated.td as unknown as AnimatedTag;
const ASpan = animated.span as unknown as AnimatedTag;

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
  step?: number;
  status: Status;
  selected: boolean;
  runnable: boolean;
  winner?: boolean;
};

function TrophyBadge() {
  const s = useSpring({
    from: { scale: 0, rotate: -25 },
    to: { scale: 1, rotate: 0 },
    config: { tension: 260, friction: 12 },
  });
  return (
    <ADiv
      style={{
        position: "absolute",
        top: -12,
        right: -10,
        fontSize: 22,
        zIndex: 5,
        transform: s.scale.to((v) => `scale(${v})`),
        filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.2))",
      }}
    >
      🏆
    </ADiv>
  );
}

function PhaseNode({ data }: NodeProps<Node<PhaseData>>) {
  const m = meta(data.kind);
  return (
    <div style={{ position: "relative", width: 214 }}>
      {data.winner && <TrophyBadge />}
      <div
        style={{
          width: 214,
          borderRadius: 16,
          background: data.winner ? "#FFFBEA" : "#ffffff",
          borderStyle: "solid",
          borderWidth: "1px",
          borderColor: data.winner ? "#C9A227" : data.selected ? m.accent : "#E7EEE6",
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
                {data.step != null ? `${String(data.step).padStart(2, "0")} · ` : ""}
                {m.label}
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
    </div>
  );
}

const nodeTypes = { phase: PhaseNode };

/** The paper's hyperparameters carried on a model node (everything except plumbing like `target`),
 * used to seed the animation's tunable knobs so defaults match the paper. */
function paperHyperparams(
  params?: Record<string, unknown>,
): Record<string, number | string | string[]> | undefined {
  if (!params) return undefined;
  const out: Record<string, number | string | string[]> = {};
  for (const [k, v] of Object.entries(params)) {
    if (k === "target" || k === "experiment_id") continue;
    if (typeof v === "number" || typeof v === "string") out[k] = v;
    // the paper's selected feature subset rides along so the animation trains on ONLY those
    if (k === "features" && Array.isArray(v)) out[k] = v.map(String);
  }
  return Object.keys(out).length ? out : undefined;
}

/* ---------------- canvas ---------------- */

export default function ExperimentCanvas({ paperId }: { paperId: string }) {
  const [exp, setExp] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [results, setResults] = useState<Record<string, NodeRunResult>>({});
  const [models, setModels] = useState<ComponentSpecLite[]>([]);
  const [rf, setRf] = useState<ReactFlowInstance | null>(null);
  // extra model branches the user adds to compete in parallel (beyond the paper's own models)
  const [extras, setExtras] = useState<WalkNode[]>([]);
  const [runErrors, setRunErrors] = useState<Record<string, string>>({});

  const [loading, setLoading] = useState(true);

  // Every registered model becomes a fork option — so a new model added to the registry (or a
  // paper naming a model we don't have) is always runnable via a comparable stand-in, no UI edit.
  useEffect(() => {
    Api.listComponents()
      .then((r) => setModels(r.components.filter((c) => c.kind === "model")))
      .catch(() => setModels([]));
  }, []);

  // Restore the existing experiment (and its fetched/generated data) on revisit — nothing is lost.
  useEffect(() => {
    let alive = true;
    Api.latestExperiment(paperId)
      .then((e) => alive && e && setExp(e))
      .catch(() => {})
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [paperId]);

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

  // Default: start at the FIRST node. It only changes when the user explicitly clicks a node.
  useEffect(() => {
    if (exp && !selectedId && exp.walkthrough[0]) setSelectedId(exp.walkthrough[0].id);
  }, [exp, selectedId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center text-muted">
        Loading experiment…
      </div>
    );
  }

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

  // ----- pipeline structure: models fan out into parallel branches, converge at Evaluation -----
  const walk = exp.walkthrough;
  // A DEDICATED feature-selection node (e.g. "BBO feature selection") is a sequential pre-step, not a
  // parallel model branch. A model that merely USES BBO-selected features (e.g. "XGBoost + BBO") still
  // names a real family (trees), so it stays a model — we only divert when no model family is named.
  const isRealModel = (n: WalkNode) => n.kind === "model" && !isFeatSelNode(n);
  const firstModel = walk.findIndex(isRealModel);
  const lastModel = walk.reduce((acc, n, i) => (isRealModel(n) ? i : acc), -1);
  const hasModels = firstModel >= 0;
  const pre = hasModels ? walk.slice(0, firstModel) : walk;
  const post = hasModels ? walk.slice(lastModel + 1) : [];
  const paperModels = hasModels
    ? walk.slice(firstModel, lastModel + 1).filter(isRealModel)
    : [];
  const branches: WalkNode[] = [...paperModels, ...extras];
  const evalNode: WalkNode = {
    id: EVAL_ID,
    kind: "eval",
    title: "Evaluation",
    detail: "Compare every model on the same data and keep the best.",
  };

  const nodeById = (id: string | null): WalkNode | null => {
    if (!id) return null;
    if (id === EVAL_ID) return evalNode;
    return walk.find((n) => n.id === id) ?? extras.find((e) => e.id === id) ?? null;
  };
  const selected = nodeById(selectedId);
  const hasSynthetic = exp.fetch_report.fetched.some((f) => f.synthetic);
  const dataReady = exp.fetch_report.fetched.length > 0;
  const anyRun = Object.keys(results).length > 0;

  // rank the models that have run → current best gets the trophy
  const leaderboard = branches
    .map((b) => ({ node: b, res: results[b.id] }))
    .filter((x): x is { node: WalkNode; res: NodeRunResult } => !!x.res)
    .map((x) => ({ ...x, metric: primaryMetric(x.res.metrics) }))
    .sort((a, b) => b.metric.value - a.metric.value);
  const winnerId = leaderboard[0]?.node.id ?? null;

  // derived status: explicit run-status wins; otherwise data/preprocess/EDA are "done" once data is
  // ready, and eval/result/inference are "done" once at least one model has run.
  const statusFor = (n: WalkNode): Status => {
    if (status[n.id]) return status[n.id];
    if (["data", "preprocess", "eda"].includes(n.kind)) return dataReady ? "done" : "idle";
    if (["eval", "result", "inference"].includes(n.kind)) return anyRun ? "done" : "idle";
    return "idle";
  };

  // ----- build the branching graph -----
  const COL = 262;
  const ROW = 122;
  const nodes: Node[] = [];
  const mk = (n: WalkNode, x: number, y: number, stepNo?: number) =>
    nodes.push({
      id: n.id,
      type: "phase",
      position: { x, y },
      data: {
        title: n.title,
        kind: n.kind,
        step: stepNo,
        status: statusFor(n),
        selected: n.id === selectedId,
        runnable: isRealModel(n),
        winner: n.id === winnerId,
      } satisfies PhaseData,
    });

  let s = 1;
  pre.forEach((n, i) => mk(n, i * COL, 0, s++));
  const branchX = pre.length * COL;
  if (hasModels) {
    branches.forEach((b, i) => mk(b, branchX, (i - (branches.length - 1) / 2) * ROW, s++));
    const evalX = branchX + COL;
    mk(evalNode, evalX, 0, s++);
    post.forEach((n, i) => mk(n, evalX + (i + 1) * COL, 0, s++));
  } else {
    post.forEach((n, i) => mk(n, (pre.length + i) * COL, 0, s++));
  }

  const edges: Edge[] = [];
  const link = (a: string, b: string) =>
    edges.push({
      id: `${a}->${b}`,
      source: a,
      target: b,
      type: "smoothstep",
      animated: true,
      style: { stroke: "#9FCE7C", strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#9FCE7C", width: 18, height: 18 },
    });
  for (let i = 0; i < pre.length - 1; i++) link(pre[i].id, pre[i + 1].id);
  if (hasModels) {
    const lastPre = pre[pre.length - 1];
    branches.forEach((b) => {
      if (lastPre) link(lastPre.id, b.id);
      link(b.id, EVAL_ID);
    });
    if (post[0]) link(EVAL_ID, post[0].id);
  }
  for (let i = 0; i < post.length - 1; i++) link(post[i].id, post[i + 1].id);

  // ordered ids for Back/Next
  const journeyIds = [
    ...pre.map((n) => n.id),
    ...(hasModels ? [...branches.map((b) => b.id), EVAL_ID] : []),
    ...post.map((n) => n.id),
  ];
  const curIdx = journeyIds.indexOf(selectedId ?? "");

  // Journey navigation: select a node AND glide the canvas to center it (no dragging needed).
  const focusNode = (id: string) => {
    setSelectedId(id);
    window.requestAnimationFrame(() =>
      rf?.fitView({ nodes: [{ id }], duration: 500, padding: 0.6, maxZoom: 1.4 }),
    );
  };
  const step = (delta: number) => {
    const next = journeyIds[(curIdx < 0 ? 0 : curIdx) + delta];
    if (next) focusNode(next);
    else if (curIdx < 0 && journeyIds[0]) focusNode(journeyIds[0]);
  };

  const defaultComponent = (n: WalkNode) =>
    n.component_id ?? n.suggested_component ?? models[0]?.id ?? "model.ml.gradient_boosting";

  // Run a model branch. Extra branches don't exist in the backend walkthrough, so we borrow the
  // first paper model node's id (for its target/params) and override the component to run.
  const runModel = async (node: WalkNode, datasetId: string, component: string) => {
    const backendNodeId = node.id.startsWith("extra-")
      ? (paperModels[0]?.id ?? node.id)
      : node.id;
    setStatus((m) => ({ ...m, [node.id]: "running" }));
    setRunErrors((m) => {
      const { [node.id]: _drop, ...rest } = m;
      return rest;
    });
    try {
      const r = await Api.runNode(exp.id, backendNodeId, {
        dataset_id: datasetId,
        component_id: component || undefined,
        // variant branches carry their own hyperparameters (saved from the animation's knobs)
        params: node.id.startsWith("extra-") && node.params ? node.params : undefined,
      });
      setResults((m) => ({ ...m, [node.id]: r }));
      setStatus((m) => ({ ...m, [node.id]: "done" }));
    } catch (e) {
      setStatus((m) => ({ ...m, [node.id]: "failed" }));
      setRunErrors((m) => ({ ...m, [node.id]: e instanceof Error ? e.message : "run failed" }));
    }
  };

  const addModel = (componentId: string, label: string, params?: Record<string, unknown>) => {
    const id = `extra-${extras.length}-${componentId}`;
    setExtras((prev) => [
      ...prev,
      { id, kind: "model", title: label, component_id: componentId, params },
    ]);
    focusNode(id);
  };

  const runAll = async () => {
    const dsId = exp.fetch_report.fetched[0]?.dataset_id;
    if (!dsId) return;
    for (const b of branches) await runModel(b, dsId, defaultComponent(b));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-sprout/30 px-3 py-1 text-sm text-forest">
          status: {exp.status}
        </span>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted">{journeyIds.length} steps · click a node</span>
          <button
            onClick={() => Api.downloadEvidenceBundle(exp.id).catch(() => {})}
            title="Download the reproducibility receipts: paper claims + supporting quotes, dataset content hashes, pipeline, and every run's provenance-locked metrics + manifest"
            className="rounded-lg border border-line px-3 py-1 text-xs font-medium text-forest transition hover:bg-bg"
          >
            ⬇ Evidence bundle
          </button>
          <button
            onClick={async () => {
              setResults({});
              setStatus({});
              setExtras([]);
              setRunErrors({});
              setSelectedId(null);
              await start();
            }}
            disabled={busy}
            className="rounded-lg border border-line px-3 py-1 text-xs font-medium text-forest transition hover:bg-bg disabled:opacity-50"
          >
            ↻ Start fresh
          </button>
        </div>
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
          {/* Journey navigation — walk the pipeline with Back/Next; the canvas glides to each step */}
          <div className="flex items-center justify-between rounded-xl border border-line bg-white px-3 py-2 text-sm">
            <button
              onClick={() => step(-1)}
              disabled={curIdx <= 0}
              className="rounded-lg border border-line px-3 py-1 font-medium text-forest transition hover:bg-bg disabled:opacity-40"
            >
              ◀ Back
            </button>
            <span className="truncate px-2 text-center text-muted">
              {curIdx >= 0
                ? `Step ${curIdx + 1} of ${journeyIds.length}`
                : `${journeyIds.length} steps`}
              {selected && (
                <>
                  {" · "}
                  <span className="font-medium text-forest">{selected.title}</span>
                </>
              )}
            </span>
            <button
              onClick={() => step(1)}
              disabled={curIdx >= 0 && curIdx >= journeyIds.length - 1}
              className="rounded-lg border border-line px-3 py-1 font-medium text-forest transition hover:bg-bg disabled:opacity-40"
            >
              Next ▶
            </button>
          </div>
          <div className="h-[420px] overflow-hidden rounded-2xl border border-line bg-gradient-to-b from-white to-[#F6FAF2]">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
              nodesDraggable={false}
              onInit={setRf}
              onNodeClick={(_, node) => focusNode(node.id)}
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
        {selected?.kind === "eval" ? (
          <EvaluationPanel
            exp={exp}
            branches={branches}
            leaderboard={leaderboard}
            status={status}
            models={models}
            onFocus={focusNode}
            onAddModel={addModel}
            onRunAll={runAll}
          />
        ) : (
          <NodeDetail
            exp={exp}
            node={selected}
            models={models}
            status={selected ? statusFor(selected) : "idle"}
            result={selected ? results[selected.id] : undefined}
            results={results}
            error={selected ? runErrors[selected.id] : undefined}
            onRun={runModel}
            onAddModel={addModel}
          />
        )}
      </div>

      <DataPanel exp={exp} onChange={setExp} />
    </div>
  );
}

/* ---------------- evaluation node: leaderboard + best model + add-your-own ---------------- */

type LeaderRow = { node: WalkNode; res: NodeRunResult; metric: { key: string; value: number } };

function EvaluationPanel({
  exp,
  branches,
  leaderboard,
  status,
  models,
  onFocus,
  onAddModel,
  onRunAll,
}: {
  exp: Experiment;
  branches: WalkNode[];
  leaderboard: LeaderRow[];
  status: Record<string, Status>;
  models: ComponentSpecLite[];
  onFocus: (id: string) => void;
  onAddModel: (componentId: string, label: string, params?: Record<string, unknown>) => void;
  onRunAll: () => Promise<void>;
}) {
  const [pick, setPick] = useState("");
  const [runningAll, setRunningAll] = useState(false);
  const noData = exp.fetch_report.fetched.length === 0;
  const existing = new Set(branches.map((b) => b.component_id).filter(Boolean) as string[]);
  const addable = models.filter((m) => !existing.has(m.id));
  const pending = branches.filter((b) => !leaderboard.some((l) => l.node.id === b.id));

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h3 className="font-display text-lg text-forest">Evaluation</h3>
      <p className="mt-1 text-sm text-muted">
        Every model runs on the same data; the best one wins the trophy. Add your own model to try to
        beat the paper.
      </p>

      <button
        onClick={async () => {
          setRunningAll(true);
          try {
            await onRunAll();
          } finally {
            setRunningAll(false);
          }
        }}
        disabled={noData || runningAll}
        className="mt-3 rounded-lg bg-forest px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
      >
        {runningAll ? "Running all…" : `Run all ${branches.length} model${branches.length === 1 ? "" : "s"}`}
      </button>
      {noData && <p className="mt-2 text-xs text-muted">Get data first (Data panel below).</p>}

      {leaderboard.length > 0 && (
        <ol className="mt-4 space-y-2">
          {leaderboard.map((l, i) => (
            <li
              key={l.node.id}
              onClick={() => onFocus(l.node.id)}
              className={`cursor-pointer rounded-xl border p-3 transition ${
                i === 0 ? "border-[#C9A227] bg-[#FFFBEA]" : "border-line bg-white hover:bg-bg"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 font-medium text-forest">
                  <span>{i === 0 ? "🏆" : `#${i + 1}`}</span>
                  {l.node.title}
                </span>
                <span className="text-sm">
                  <span className="text-muted">{l.metric.key}: </span>
                  <span className="font-semibold text-forest">{l.metric.value.toFixed(3)}</span>
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
                {Object.entries(l.res.metrics).map(([k, v]) => (
                  <span key={k}>
                    {k} {typeof v === "number" ? v.toFixed(3) : String(v)}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}

      {leaderboard.length > 0 && (
        <details className="mt-3 rounded-lg bg-bg p-3 text-xs">
          <summary className="cursor-pointer font-medium text-forest">
            How these metrics are calculated (with an example)
          </summary>
          <p className="mt-1 text-[11px] text-muted">
            Example confusion counts: TP=90, TN=45, FP=0, FN=5 (TP/TN = correct positives/negatives,
            FP/FN = false alarms/misses).
          </p>
          <ul className="mt-2 space-y-2">
            {METRIC_HELP.map((mh) => (
              <li key={mh.key} className="rounded-lg bg-white p-2">
                <div>
                  <span className="font-medium text-forest">{mh.key}</span> ={" "}
                  <code className="text-ink">{mh.formula}</code>
                </div>
                <div className="mt-0.5 text-[11px]">
                  <span className="text-muted">example: </span>
                  <code className="text-ink">{mh.example}</code>
                </div>
                <div className="mt-0.5 text-[11px] text-muted">{mh.interpret}</div>
                <div className="mt-1 rounded bg-leaf/10 px-1.5 py-1 text-[11px] text-ink">
                  <b>When to use it:</b> {mh.when}
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}

      {pending.length > 0 && (
        <p className="mt-3 text-xs text-muted">
          Not run yet:{" "}
          {pending.map((b, i) => (
            <span key={b.id}>
              <button className="text-forest underline" onClick={() => onFocus(b.id)}>
                {b.title}
              </button>
              {status[b.id] === "running" ? " (running…)" : ""}
              {i < pending.length - 1 ? ", " : ""}
            </span>
          ))}
        </p>
      )}

      {addable.length > 0 && (
        <div className="mt-4 flex items-center gap-2">
          <select
            className="min-w-0 flex-1 rounded-lg border border-line px-2 py-1 text-sm"
            value={pick}
            onChange={(e) => setPick(e.target.value)}
          >
            <option value="">➕ Add a model to compete…</option>
            {addable.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <button
            disabled={!pick}
            onClick={() => {
              const m = addable.find((x) => x.id === pick);
              if (m) onAddModel(m.id, m.name);
              setPick("");
            }}
            className="shrink-0 rounded-lg border border-line px-3 py-1 text-sm font-medium text-forest transition hover:bg-bg disabled:opacity-40"
          >
            Add
          </button>
        </div>
      )}
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
  results,
  error,
  onRun,
  onAddModel,
}: {
  exp: Experiment;
  node: WalkNode | null;
  models: ComponentSpecLite[];
  status: Status;
  result?: NodeRunResult;
  results: Record<string, NodeRunResult>;
  error?: string;
  onRun: (node: WalkNode, datasetId: string, component: string) => Promise<void>;
  onAddModel: (componentId: string, label: string, params?: Record<string, unknown>) => void;
}) {
  const [datasetId, setDatasetId] = useState(exp.fetch_report.fetched[0]?.dataset_id ?? "");
  const [addPick, setAddPick] = useState("");
  const [showExplain, setShowExplain] = useState(false);

  if (!node) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5 text-sm text-muted">
        Click a node in the flow to see what it does and its progress.
      </div>
    );
  }

  const m = meta(node.kind);
  // A "model" node that's really a feature-selection step (BBO) gets its own animation, no scoring.
  const isFeatSel = isFeatSelNode(node);
  const isModel = node.kind === "model" && !isFeatSel;
  const dsId = datasetId || exp.fetch_report.fetched[0]?.dataset_id || "";
  const noData = exp.fetch_report.fetched.length === 0;
  const nativeUnknown = isModel && !node.component_id;
  // This node runs the paper's own model (or a stand-in if it's not in the registry) — no dropdown.
  const runComponent = node.component_id ?? node.suggested_component ?? "model.ml.gradient_boosting";
  const runLabel = models.find((mm) => mm.id === runComponent)?.name ?? runComponent;

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

      {isModel && (
        <div className="mt-3">
          <button
            onClick={() => setShowExplain(true)}
            className="mb-2 flex items-center gap-1.5 rounded-lg border border-leaf/50 bg-leaf/10 px-3 py-1.5 text-xs font-medium text-forest hover:bg-leaf/20"
          >
            📖 New to {node.title}? Learn it from zero
          </button>
          {showExplain && (
            <ModelExplainerCard
              family={modelKind(node.title || node.component_id || "")}
              modelName={node.title}
              datasetId={exp.fetch_report.fetched[0]?.dataset_id}
              target={(node.params?.target as string) || ""}
              initialParams={paperHyperparams(node.params)}
              onClose={() => setShowExplain(false)}
            />
          )}
          {exp.fetch_report.fetched.length > 0 ? (
            <StagedModelAnimation
              datasetId={exp.fetch_report.fetched[0].dataset_id}
              target={(node.params?.target as string) || ""}
              family={modelKind(node.title || node.component_id || "")}
              title={node.title}
              initialParams={paperHyperparams(node.params)}
              onSaveVariant={(p) =>
                onAddModel(
                  node.component_id ?? node.suggested_component ?? "model.ml.gradient_boosting",
                  `${node.title} (tweaked)`,
                  { ...(node.params ?? {}), ...p },
                )
              }
            />
          ) : (
            <ModelAnimation kind={modelKind(node.title || node.component_id || "")} />
          )}
        </div>
      )}

      {isFeatSel && (
        <div className="mt-3">
          {exp.fetch_report.fetched.length > 0 ? (
            <FeatureSelectionAnimation
              datasetId={exp.fetch_report.fetched[0].dataset_id}
              target={(node.params?.target as string) || ""}
            />
          ) : (
            <ModelAnimation kind="generic" />
          )}
        </div>
      )}

      {node.kind === "data" ? (
        <DataNodePanel exp={exp} />
      ) : node.kind === "eda" ? (
        <EdaPanel exp={exp} />
      ) : node.kind === "preprocess" ? (
        isSplit(node.title) ? <TrainTestSplitPanel exp={exp} /> : <PreprocessPanel key={node.id} exp={exp} node={node} />
      ) : node.kind === "result" || node.kind === "inference" ? (
        <ResultsComparison node={node} exp={exp} results={results} primary={primaryMetric} />
      ) : !isModel ? (
        <p className="mt-3 text-sm text-muted">
          {isFeatSel
            ? "This step picks the compact feature subset shown above; the models then train on it — nothing to score here."
            : "This is an explanatory step — nothing to run."}
        </p>
      ) : noData ? (
        <p className="mt-3 text-sm text-muted">
          Get data first (fetch or generate demo data below), then run this model.
        </p>
      ) : (
        <div className="mt-3 space-y-3 text-sm">
          {nativeUnknown && (
            <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
              The paper&apos;s exact model isn&apos;t in the registry, so this step runs a comparable
              stand-in (<span className="font-medium">{runLabel}</span>) to compare against the paper.
            </p>
          )}
          {exp.fetch_report.fetched.length > 1 && (
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
          )}
          <div className="rounded-lg bg-bg px-3 py-2 text-xs text-muted">
            {nativeUnknown ? (
              <>
                No exact match in the registry for{" "}
                <span className="font-medium text-forest">{node.title}</span> — runs the closest
                comparable model, <b>{runLabel}</b>.
              </>
            ) : (
              <>
                Runs the paper&apos;s model:{" "}
                <span className="font-medium text-forest">{node.title}</span>.
              </>
            )}
          </div>
          <button
            onClick={() => onRun(node, dsId, runComponent)}
            disabled={status === "running"}
            className="rounded-lg bg-forest px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {status === "running" ? "Running…" : "Run this model"}
          </button>
          {status === "failed" && error && (
            <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700">Run failed: {error}</p>
          )}
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
              <PredictionsBlock result={result} />
            </div>
          )}
          {/* + add another model as a parallel branch to compete */}
          <div className="flex items-center gap-2 border-t border-line pt-3">
            <select
              className="min-w-0 flex-1 rounded-lg border border-line px-2 py-1 text-xs"
              value={addPick}
              onChange={(e) => setAddPick(e.target.value)}
            >
              <option value="">➕ Add another model to compare…</option>
              {models
                .filter((mm) => mm.id !== runComponent)
                .map((mm) => (
                  <option key={mm.id} value={mm.id}>
                    {mm.name}
                  </option>
                ))}
            </select>
            <button
              disabled={!addPick}
              onClick={() => {
                const mm = models.find((x) => x.id === addPick);
                if (mm) onAddModel(mm.id, mm.name);
                setAddPick("");
              }}
              className="shrink-0 rounded-lg border border-line px-3 py-1 text-xs font-medium text-forest hover:bg-bg disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- data node: view + download the actual rows ---------------- */

function fmtCell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

function DataNodePanel({ exp }: { exp: Experiment }) {
  const fetched = exp.fetch_report.fetched;
  const [dsId, setDsId] = useState(fetched[0]?.dataset_id ?? "");
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dsId) {
      setPreview(null);
      return;
    }
    let alive = true;
    setBusy(true);
    setError(null);
    Api.datasetPreview(dsId, 25)
      .then((p) => alive && setPreview(p))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "preview failed"))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [dsId]);

  if (fetched.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">
        No data yet — generate demo data or upload the paper&apos;s dataset in the Data panel below.
      </p>
    );
  }
  const cur = fetched.find((f) => f.dataset_id === dsId) ?? fetched[0];

  return (
    <div className="mt-3 space-y-2 text-sm">
      <div className="flex items-center gap-2">
        <select
          className="min-w-0 flex-1 rounded-lg border border-line px-2 py-1"
          value={dsId}
          onChange={(e) => setDsId(e.target.value)}
        >
          {fetched.map((f) => (
            <option key={f.dataset_id} value={f.dataset_id}>
              {f.name}
              {f.synthetic ? " (synthetic)" : ""}
            </option>
          ))}
        </select>
        <button
          onClick={() => Api.downloadDataset(dsId, cur?.name ?? "dataset")}
          className="shrink-0 rounded-lg border border-line px-3 py-1 font-medium text-forest transition hover:bg-bg"
        >
          ⬇ CSV
        </button>
      </div>

      {error && <p className="text-red-600">{error}</p>}
      {busy && <p className="text-muted">Loading preview…</p>}

      {preview && (
        <>
          <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight: 260 }}>
            <table className="min-w-full text-xs">
              <thead className="sticky top-0 bg-bg">
                <tr>
                  {preview.columns.map((c) => (
                    <th
                      key={c}
                      className="whitespace-nowrap px-2 py-1 text-left font-medium text-forest"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="odd:bg-white even:bg-bg/40">
                    {preview.columns.map((c) => (
                      <td key={c} className="whitespace-nowrap px-2 py-1 text-ink">
                        {fmtCell(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">
            Showing {preview.rows.length}
            {preview.truncated ? ` of ${preview.n_rows ?? "?"}` : ""} rows ·{" "}
            {preview.n_cols ?? preview.columns.length} columns
          </p>
        </>
      )}
    </div>
  );
}

/* ---------------- EDA node: scrollable simple exploration ---------------- */

function heatmapSpec(corr: { columns: string[]; matrix: number[][] }) {
  const values: { x: string; y: string; v: number }[] = [];
  corr.columns.forEach((yc, yi) =>
    corr.columns.forEach((xc, xi) => values.push({ x: xc, y: yc, v: corr.matrix[yi][xi] })),
  );
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    data: { values },
    mark: "rect",
    width: 300,
    height: 300,
    encoding: {
      x: { field: "x", type: "nominal", axis: { labelAngle: -45, title: null } },
      y: { field: "y", type: "nominal", axis: { title: null } },
      color: {
        field: "v",
        type: "quantitative",
        scale: { scheme: "redyellowgreen", domain: [-1, 1] },
        legend: { title: "corr" },
      },
      tooltip: [{ field: "x" }, { field: "y" }, { field: "v", title: "corr" }],
    },
  } as Record<string, unknown>;
}

function histogramSpec(values: number[], field: string) {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    data: { values: values.map((v) => ({ v })) },
    mark: { type: "bar", color: "#6DB33F" },
    width: 220,
    height: 84,
    encoding: {
      x: { field: "v", bin: { maxbins: 15 }, type: "quantitative", axis: { title: field } },
      y: { aggregate: "count", type: "quantitative", axis: { title: null } },
    },
  } as Record<string, unknown>;
}

// feature vs target: scatter+regression line (numeric target) or class-split histogram with a
// vertical mean line per class (categorical target) — the line reveals a distinct pattern.
function featureVsTargetSpec(
  rows: Record<string, unknown>[],
  feature: string,
  target: string,
  targetNumeric: boolean,
): Record<string, unknown> {
  if (targetNumeric) {
    const values = rows
      .map((r) => ({ x: Number(r[feature]), y: Number(r[target]) }))
      .filter((d) => Number.isFinite(d.x) && Number.isFinite(d.y));
    return {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      data: { values },
      width: 220,
      height: 120,
      layer: [
        {
          mark: { type: "point", opacity: 0.4, color: "#2E6C8E", size: 30 },
          encoding: {
            x: { field: "x", type: "quantitative", axis: { title: feature } },
            y: { field: "y", type: "quantitative", axis: { title: target } },
          },
        },
        {
          mark: { type: "line", color: "#C0392B", strokeWidth: 2 },
          transform: [{ regression: "y", on: "x" }],
          encoding: {
            x: { field: "x", type: "quantitative" },
            y: { field: "y", type: "quantitative" },
          },
        },
      ],
    } as Record<string, unknown>;
  }
  // Classification: the sigmoid-style view — each patient is a dot at 0 (one class) or 1 (the
  // other), jittered so dots don't stack; dashed lines mark what 0 and 1 MEAN; the green curve is
  // the observed probability of the positive class as this feature increases (an S-ish curve =
  // strong predictor, a flat line = uninformative).
  const classes = Array.from(
    new Set(rows.map((r) => String(r[target] ?? "—")).filter((t) => t !== "—")),
  ).sort();
  const neg = classes[0] ?? "0";
  const pos = classes[1] ?? "1";
  const pts = rows
    .map((r) => ({
      v: Number(r[feature]),
      y: String(r[target]) === pos ? 1 : 0,
      t: String(r[target] ?? "—"),
    }))
    .filter((d) => Number.isFinite(d.v));
  // observed P(pos) per feature bin → the empirical "sigmoid"
  const xs = pts.map((p) => p.v);
  const [lo, hi] = [Math.min(...xs), Math.max(...xs)];
  const BINS = 8;
  const curve: { v: number; p: number }[] = [];
  for (let b = 0; b < BINS; b++) {
    const b0 = lo + ((hi - lo) * b) / BINS;
    const b1 = lo + ((hi - lo) * (b + 1)) / BINS;
    const inBin = pts.filter((p) => p.v >= b0 && (b === BINS - 1 ? p.v <= b1 : p.v < b1));
    if (inBin.length >= 3)
      curve.push({ v: (b0 + b1) / 2, p: inBin.reduce((s, p) => s + p.y, 0) / inBin.length });
  }
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    width: 220,
    height: 120,
    layer: [
      {
        data: { values: [{ y: 1, label: `1 = ${pos}` }, { y: 0, label: `0 = ${neg}` }] },
        mark: { type: "rule", strokeDash: [5, 4], color: "#7C8A80" },
        encoding: { y: { field: "y", type: "quantitative", axis: { title: `P(${pos})`, values: [0, 0.5, 1] } } },
      },
      {
        data: { values: [{ y: 1, label: `1 = ${pos}` }, { y: 0, label: `0 = ${neg}` }] },
        mark: { type: "text", align: "left", dx: 3, dy: -6, fontSize: 9, color: "#7C8A80" },
        encoding: {
          y: { field: "y", type: "quantitative" },
          x: { value: 0 },
          text: { field: "label" },
        },
      },
      {
        data: { values: pts },
        mark: { type: "circle", opacity: 0.35, size: 26 },
        transform: [{ calculate: "datum.y + (random() - 0.5) * 0.12", as: "yj" }],
        encoding: {
          x: { field: "v", type: "quantitative", axis: { title: feature } },
          y: { field: "yj", type: "quantitative", scale: { domain: [-0.15, 1.15] }, axis: null },
          color: {
            field: "t",
            type: "nominal",
            legend: { title: null, orient: "top" },
            scale: { domain: [neg, pos], range: ["#C0392B", "#6DB33F"] },
          },
        },
      },
      {
        data: { values: curve },
        mark: { type: "line", color: "#14342A", strokeWidth: 2.5, interpolate: "monotone", point: true },
        encoding: {
          x: { field: "v", type: "quantitative" },
          y: { field: "p", type: "quantitative" },
        },
      },
    ],
  } as Record<string, unknown>;
}

function EdaPanel({ exp }: { exp: Experiment }) {
  const fetched = exp.fetch_report.fetched;
  const [dsId, setDsId] = useState(fetched[0]?.dataset_id ?? "");
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [nameMap, setNameMap] = useState<Record<string, string>>({});
  const [targetName, setTargetName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // full names ("pcv" → "Packed cell volume") + the target, from the Paper Card
  useEffect(() => {
    let alive = true;
    Api.getPaper(exp.paper_id)
      .then((p) => {
        if (!alive) return;
        const card = p.card as EmpiricalCard;
        if (card?.paper_type !== "empirical") return;
        const map: Record<string, string> = {};
        for (const v of card.independent_variables ?? [])
          if (v.name && v.description) map[v.name.toLowerCase()] = v.description;
        if (card.target_variable?.name && card.target_variable.description)
          map[card.target_variable.name.toLowerCase()] = card.target_variable.description;
        setNameMap(map);
        setTargetName(card.target_variable?.name ?? "");
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [exp.paper_id]);

  useEffect(() => {
    if (!dsId) return;
    let alive = true;
    setBusy(true);
    setError(null);
    Promise.all([Api.datasetProfile(dsId), Api.datasetPreview(dsId, 400)])
      .then(([p, pv]) => {
        if (!alive) return;
        setProfile(p);
        setRows(pv.rows);
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : "profile failed"))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [dsId]);

  // resolve the target COLUMN present in the data + whether it's numeric (regression) or classes
  const targetCol =
    profile?.columns.find((c) => c.name.toLowerCase() === targetName.toLowerCase())?.name ??
    profile?.columns[profile.columns.length - 1]?.name ??
    "";
  const targetNumeric =
    profile?.columns.find((c) => c.name === targetCol)?.dtype === "numeric";
  const fullName = (code: string) => nameMap[code.toLowerCase()] ?? "";

  if (fetched.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">
        Get data first (Data panel below), then explore it here.
      </p>
    );
  }
  return (
    <div className="mt-3 space-y-2 text-sm">
      {fetched.length > 1 && (
        <select
          className="rounded-lg border border-line px-2 py-1 text-xs"
          value={dsId}
          onChange={(e) => setDsId(e.target.value)}
        >
          {fetched.map((f) => (
            <option key={f.dataset_id} value={f.dataset_id}>
              {f.name}
            </option>
          ))}
        </select>
      )}
      {error && <p className="text-red-600">{error}</p>}
      {busy && <p className="text-muted">Profiling…</p>}
      {profile && (
        <>
          <div className="rounded-lg bg-leaf/10 p-2.5 text-xs text-ink">
            <b>Why explore first?</b> Before trusting any model, we look at the raw data with our own
            eyes: how each measurement is spread, where values are missing, and which measurements
            already separate the outcomes. This catches data problems early and tells us which
            features the models will probably lean on. <span className="text-muted">
            ({profile.n_rows} rows · {profile.n_cols} columns — scroll for a chart on every variable)</span>
          </div>
          <div className="max-h-96 space-y-2 overflow-auto pr-1">
            {profile.correlation && profile.correlation.columns.length >= 2 && (
              <div className="rounded-lg border border-line bg-white p-3">
                <p className="mb-1 text-xs font-medium text-forest">Correlation heatmap</p>
                <p className="mb-1 text-[11px] text-muted">
                  Each square: how strongly two measurements move together (+1 = rise together, −1 =
                  one rises as the other falls, 0 = unrelated). <b>Why it matters:</b> two features
                  that are almost copies (deep green/red) carry the same information — and a feature
                  strongly tied to the target is a promising predictor.
                </p>
                <VegaChart spec={heatmapSpec(profile.correlation)} />
              </div>
            )}
            {profile.columns.map((c) => (
              <EdaColumn
                key={c.name}
                c={c}
                rows={rows}
                full={fullName(c.name)}
                target={targetCol}
                targetNumeric={targetNumeric}
                isTarget={c.name === targetCol}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function EdaColumn({
  c,
  rows,
  full,
  target,
  targetNumeric,
  isTarget,
}: {
  c: ColProfile;
  rows: Record<string, unknown>[];
  full: string;
  target: string;
  targetNumeric: boolean;
  isTarget: boolean;
}) {
  const numericValues =
    c.dtype === "numeric"
      ? rows.map((r) => Number(r[c.name])).filter((v) => Number.isFinite(v))
      : [];
  const showVsTarget = !isTarget && target && c.dtype === "numeric" && rows.length > 3;
  return (
    <div className="rounded-lg border border-line bg-white p-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-forest">
          {c.name}
          {full && <span className="ml-1 font-normal text-muted">({full})</span>}
        </span>
        <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">{c.dtype}</span>
      </div>
      <p className="mt-0.5 text-xs text-muted">
        {c.missing_pct}% missing ({c.missing})
        {c.missing > 0 && (
          <span className="text-[#B8860B]"> — these holes are what the imputation step fills</span>
        )}
      </p>
      {c.dtype === "numeric" ? (
        <div className="mt-2">
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink">
            <span>mean {c.mean}</span>
            <span>std {c.std}</span>
            <span>min {c.min}</span>
            <span>median {c.q50}</span>
            <span>max {c.max}</span>
          </div>
          {numericValues.length > 3 && (
            <div className="mt-2">
              <p className="mb-1 text-[11px] text-muted">
                distribution — how common each range of values is (a quick check for skew and
                outliers that could mislead a model):
              </p>
              <VegaChart spec={histogramSpec(numericValues, c.name)} />
            </div>
          )}
          {showVsTarget && (
            <div className="mt-2 border-t border-line/60 pt-2">
              <p className="mb-1 text-[11px] text-muted">
                vs target <span className="text-forest">{target}</span>
                {" — "}
                {targetNumeric
                  ? "each dot is one row (scatter + trend line); if the trend line clearly slopes, this feature helps predict the target."
                  : "each dot is one patient, sitting on the dashed line of its class (1 = top, 0 = bottom); the dark curve is how the CHANCE of the top class changes as this feature grows — an S-shaped or sloping curve = strong predictor, a flat curve = adds little."}
              </p>
              <VegaChart spec={featureVsTargetSpec(rows, c.name, target, targetNumeric)} />
            </div>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-1">
          <p className="text-xs text-muted">{c.unique} unique · top values:</p>
          {(c.top ?? []).map((t) => (
            <div key={t.value} className="flex items-center gap-2 text-xs">
              <span className="w-16 shrink-0 truncate text-ink">{t.value}</span>
              <div className="h-2 flex-1 rounded-full bg-bg">
                <div
                  className="h-2 rounded-full bg-leaf"
                  style={{
                    width: `${Math.min(100, (t.count / (c.top?.[0]?.count || 1)) * 100)}%`,
                  }}
                />
              </div>
              <span className="w-8 shrink-0 text-right text-muted">{t.count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- train / test split node ---------------- */

function isSplit(title: string): boolean {
  return /(split|train|test|hold[- ]?out|70\/30|70-30)/i.test(title);
}

function makeSplit(n: number, testFrac: number): boolean[] {
  const arr = Array.from({ length: n }, (_, i) => i < Math.round(n * testFrac)); // true = test
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function TrainTestSplitPanel({ exp }: { exp: Experiment }) {
  const ds = exp.fetch_report.fetched[0];
  const total = ds?.n_rows ?? 0;
  const TILES = 48;
  const testFrac = 0.3;
  const [tiles, setTiles] = useState<boolean[]>(() => makeSplit(TILES, testFrac));
  if (!ds) {
    return <p className="mt-3 text-sm text-muted">Get data first (Data panel below).</p>;
  }
  const nTest = Math.round(total * testFrac);
  const nTrain = total - nTest;
  return (
    <div className="mt-3 space-y-3 text-sm">
      <p className="text-muted">
        Rows are shuffled, then split — {Math.round((1 - testFrac) * 100)}% train,{" "}
        {Math.round(testFrac * 100)}% test.
      </p>
      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm" style={{ background: "#6DB33F" }} />
          Train {nTrain ? `(${nTrain} rows)` : ""}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-sm" style={{ background: "#F0B429" }} />
          Test {nTest ? `(${nTest} rows)` : ""}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {tiles.map((isTest, i) => (
          <span
            key={i}
            className="h-4 w-4 rounded-sm transition-colors duration-300"
            style={{ background: isTest ? "#F0B429" : "#6DB33F" }}
          />
        ))}
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full">
        <div className="flex h-full">
          <div style={{ width: `${(1 - testFrac) * 100}%`, background: "#6DB33F" }} />
          <div style={{ width: `${testFrac * 100}%`, background: "#F0B429" }} />
        </div>
      </div>
      <button
        onClick={() => setTiles(makeSplit(TILES, testFrac))}
        className="rounded-lg border border-line px-3 py-1 text-xs font-medium text-forest transition hover:bg-bg"
      >
        🔀 Re-split (new random shuffle)
      </button>
    </div>
  );
}

/* ---------------- predicted vs actual ---------------- */

function PredictionsBlock({ result }: { result: NodeRunResult }) {
  const preds = result.predictions ?? [];
  if (!preds.length) return null;
  const isReg = result.task === "regression";
  const acts = preds.map((p) => Number(p.actual));
  const range = Math.max(1e-9, Math.max(...acts) - Math.min(...acts));
  const tier = (diff: number) => {
    const e = Math.abs(diff) / range;
    if (e <= 0.1) return "text-green-700";
    if (e <= 0.25) return "text-amber-600";
    return "text-red-600";
  };
  return (
    <div className="mt-3">
      <p className="text-xs uppercase tracking-wide text-leaf">Predicted vs actual (test sample)</p>
      <div className="mt-1 max-h-56 overflow-auto rounded-lg border border-line">
        <table className="min-w-full text-xs">
          <thead className="sticky top-0 bg-bg">
            <tr>
              <th className="px-2 py-1 text-left text-muted">#</th>
              <th className="px-2 py-1 text-left text-muted">Actual</th>
              <th className="px-2 py-1 text-left text-muted">Predicted</th>
              <th className="px-2 py-1 text-left text-muted">{isReg ? "Difference" : "Result"}</th>
            </tr>
          </thead>
          <tbody>
            {preds.map((p, i) => {
              const diff = Number(p.predicted) - Number(p.actual);
              const correct = p.predicted === p.actual;
              const sign = diff > 0 ? "+" : diff < 0 ? "−" : "";
              return (
                <tr key={i} className="border-t border-line/60">
                  <td className="px-2 py-1 text-muted">{i + 1}</td>
                  <td className="px-2 py-1 text-ink">{p.actual}</td>
                  <td className="px-2 py-1 text-ink">{p.predicted}</td>
                  <td
                    className={`px-2 py-1 font-medium ${
                      isReg ? tier(diff) : correct ? "text-green-700" : "text-red-600"
                    }`}
                  >
                    {isReg
                      ? `${sign}${Math.abs(diff).toFixed(2)}`
                      : correct
                        ? "✓ correct"
                        : "✗ wrong"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs text-muted">
        {isReg
          ? "green = close · amber = off · red = far"
          : "green = correct · red = misclassified"}{" "}
        · first {preds.length} test rows
      </p>
    </div>
  );
}

/* ---------------- preprocess node: watch the rows transform ---------------- */

const PREPROC_LABELS: Record<PreprocessOp, string> = {
  impute_mean: "Fill missing → column mean",
  impute_median: "Fill missing → column median",
  standardize: "Standardize (z-score)",
  minmax: "Scale to 0–1 (min–max)",
  drop_missing_rows: "Remove rows with missing values",
  filter_rows: "Remove rows by condition",
  encode: "Encode categories → numbers",
};

// Why each step exists — in words anyone can follow (shown above the animation).
const PREPROC_WHY: Record<PreprocessOp, string> = {
  impute_mean:
    "Real data has holes — a patient whose blood pressure was never recorded. Most models can't use a row with a hole, and throwing the whole row away wastes everything else we know about it. Filling the hole with that column's AVERAGE keeps the row while adding no opinion of its own (the average is the least-surprising guess).",
  impute_median:
    "Same idea as filling with the average, but using the MIDDLE value instead — safer when a column has extreme values (one millionaire would drag the average income up, but not the median).",
  standardize:
    "Columns live on wildly different scales (age ~50, hemoglobin ~13). Distance- and weight-based models would let the big-number column shout over the rest. Standardizing re-expresses every value as 'how many spreads above/below its column's average' so every feature speaks at the same volume.",
  minmax:
    "Squeezes every column into the same 0-to-1 range (0 = that column's smallest value, 1 = its largest) so no feature dominates just because its numbers are bigger. Popular for neural networks.",
  drop_missing_rows:
    "The strictest way to handle holes: any row with even one missing value is thrown out entirely. You lose data (sometimes a lot), but every remaining row is fully trustworthy — no guessed values. Papers often build one 'complete rows only' set this way and compare it against a mean-filled set.",
  filter_rows:
    "Some rows simply don't belong in the study — outside the age range, impossible values, wrong population. This step removes them by a rule so the model only ever learns from rows that match the paper's inclusion criteria.",
  encode:
    "Models can only do math on numbers, but columns like 'yes/no' or 'normal/abnormal' are text. Encoding gives each category a number (no→0, yes→1) so those columns can join the math — without changing what they mean.",
};

/** Parse the paper's own funnel step (title + detail) into the exact operation to animate —
 *  including row filters like "remove rows where age is less than 18". */
function inferOpRich(text: string): { op: PreprocessOp; filter?: RowFilter } {
  const t = (text || "").toLowerCase();
  // row filter: (remove|drop|exclude|filter|discard) ... <col> ... (less than|under|>|≥...) <number>
  const m = t.match(
    /(?:remov\w*|drop\w*|exclud\w*|filter\w*|discard\w*|delet\w*)[^.;]*?\b([a-z_][a-z0-9_ ]{1,24}?)\s*(?:is |are |was |be |)(less than or equal|greater than or equal|less than|greater than|below|under|above|over|at least|at most|>=|<=|>|<|=|equal to)\s*(\d+(?:\.\d+)?)/,
  );
  if (m) {
    const cmpMap: Record<string, RowFilter["cmp"]> = {
      "less than": "lt", below: "lt", under: "lt", "<": "lt",
      "greater than": "gt", above: "gt", over: "gt", ">": "gt",
      "less than or equal": "le", "at most": "le", "<=": "le",
      "greater than or equal": "ge", "at least": "ge", ">=": "ge",
      "=": "eq", "equal to": "eq",
    };
    const col = m[1].trim().split(/\s+/).slice(-2).join(" "); // last word(s) before the comparator
    return { op: "filter_rows", filter: { column: col, cmp: cmpMap[m[2]] ?? "lt", value: Number(m[3]) } };
  }
  if (/(remov|drop|delet|discard|exclud|elimina)\w*[^.;]*(missing|null|incomplete|na\b|empty)/.test(t) ||
      /(complete case|without missing|no missing)/.test(t))
    return { op: "drop_missing_rows" };
  if (/(encod|one.?hot|label encod|categor\w+ (?:to|into) num|convert\w*[^.;]*(numeric|binary)|nominal)/.test(t))
    return { op: "encode" };
  if (t.includes("median")) return { op: "impute_median" };
  if (/(mean|imput|fill|replac\w*[^.;]*missing)/.test(t)) return { op: "impute_mean" };
  if (t.includes("min") && t.includes("max")) return { op: "minmax" };
  if (t.includes("normal")) return { op: "minmax" };
  return { op: "standardize" };
}

function inferOp(title: string): PreprocessOp {
  const t = title.toLowerCase();
  if (t.includes("median")) return "impute_median";
  if (t.includes("missing") || t.includes("impute") || t.includes("fill") || t.includes("mean"))
    return "impute_mean";
  if (t.includes("min") && t.includes("max")) return "minmax";
  if (t.includes("normal")) return "minmax";
  // lively default: standardize always shows a visible change (even on complete demo data)
  return "standardize";
}

/** Age / numeric INCLUSION criteria ("keeps women aged 18 or older", "at least 18", "18+", excludes
 *  those "under 18") → the row-removal condition that enforces it (remove age < 18). */
function inferInclusionFilter(t: string): RowFilter | undefined {
  const older =
    t.match(/\bage[d]?\s*(?:of\s*)?(\d{1,3})\s*(?:years?\s*)?(?:or|and|)\s*(?:older|above|over|up|plus)\b/) ||
    t.match(/\b(\d{1,3})\s*(?:years?\s*)?(?:or|and)\s*(?:older|above|over|up)\b/) ||
    t.match(/\bat least\s*(\d{1,3})\s*(?:years?)?\b/) ||
    t.match(/\bolder than\s*(\d{1,3})\b/) ||
    t.match(/\b(\d{1,3})\s*\+\b/);
  if (older) return { column: "age", cmp: "lt", value: Number(older[1]) }; // keep ≥ N ⇒ drop < N
  const under =
    t.match(/\bunder\s*(?:age\s*)?(\d{1,3})\b/) ||
    t.match(/\byounger than\s*(\d{1,3})\b/) ||
    t.match(/\bbelow\s*(?:age\s*)?(\d{1,3})\b/);
  if (under) return { column: "age", cmp: "lt", value: Number(under[1]) }; // exclude the young ⇒ drop < N
  return undefined;
}

/** Parse EVERY operation the paper's funnel step mentions — a step like "remove incomplete records
 *  AND standardize income" is two operations, so we show both (each animatable), not just one.
 *  Selection/inclusion steps ("keep women aged 18+…") are row FILTERS, never standardization. */
function inferOpsRich(text: string): { ops: PreprocessOp[]; filter?: RowFilter } {
  const t = (text || "").toLowerCase();
  const ops: PreprocessOp[] = [];
  const rich = inferOpRich(text);
  let filter = rich.filter;
  if (rich.op === "filter_rows" && rich.filter) {
    ops.push("filter_rows");
  } else {
    const inc = inferInclusionFilter(t);
    if (inc) {
      ops.push("filter_rows");
      filter = inc;
    }
  }
  if (/(remov|drop|delet|discard|exclud|elimina)\w*[^.;]*(missing|null|incomplete|\bna\b|empty)/.test(t) ||
      /(complete case|without missing|no missing|listwise)/.test(t))
    ops.push("drop_missing_rows");
  if (/(encod|one.?hot|label encod|categor\w+ (?:to|into) num|dummy|nominal)/.test(t))
    ops.push("encode");
  if (t.includes("median")) ops.push("impute_median");
  else if (/(\bmean\b|imput|fill\w*[^.;]*missing|replac\w*[^.;]*missing)/.test(t)) ops.push("impute_mean");
  if ((t.includes("min") && t.includes("max")) || /normali[sz]/.test(t)) ops.push("minmax");
  if (/standardi[sz]|z-?score|constant .*price|deflat/.test(t)) ops.push("standardize");

  const uniq = [...new Set(ops)];
  if (uniq.length) return { ops: uniq, filter };
  // nothing explicit: a SELECTION/inclusion step is a filter; otherwise fall back to standardize
  if (/\b(keep|kept|retain|includ|\bonly\b|restrict|eligib|inclusion|subset|sample keeps|population|criteria|currently married|never married|unmarried)\b/.test(t))
    return { ops: ["filter_rows"], filter };
  return { ops: [inferOp(text)], filter };
}

function AnimatedCell({
  before,
  after,
  active,
  changed,
}: {
  before: unknown;
  after: unknown;
  active: boolean;
  changed: boolean;
}) {
  const bNum = typeof before === "number";
  const aNum = typeof after === "number";
  const numeric = bNum && aNum;
  const spring = useSpring({
    val: active && numeric ? (after as number) : bNum ? (before as number) : 0,
    bg: active && changed ? 1 : 0,
    config: { tension: 120, friction: 20 },
  });

  return (
    <ATd
      className="whitespace-nowrap px-2 py-1 text-ink"
      style={{
        backgroundColor: spring.bg.to((v) => `rgba(109,179,63,${0.28 * v})`),
        fontWeight: changed ? 600 : 400,
      }}
    >
      {numeric ? (
        <ASpan>{spring.val.to((v) => v.toFixed(2)) as unknown as ReactNode}</ASpan>
      ) : (
        <span>{active ? fmtCell(after) : fmtCell(before)}</span>
      )}
    </ATd>
  );
}

function PreprocessPanel({ exp, node }: { exp: Experiment; node: WalkNode }) {
  const fetched = exp.fetch_report.fetched;
  const [dsId, setDsId] = useState(fetched[0]?.dataset_id ?? "");
  // the PAPER's exact funnel step(s), parsed from this node's title + detail — may be several
  const inferred = useMemo(() => inferOpsRich(`${node.title}. ${node.detail ?? ""}`), [node.title, node.detail]);
  const paperOps = inferred.ops;
  // extra steps the user chooses to apply IN ADDITION to the paper's
  const [extra, setExtra] = useState<PreprocessOp[]>([]);
  const allOps = useMemo(() => [...paperOps, ...extra], [paperOps, extra]);
  const [op, setOp] = useState<PreprocessOp>(paperOps[0]);
  const [pv, setPv] = useState<PreprocessPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(false); // false = "before", true = "after"

  useEffect(() => {
    if (!dsId) return;
    let alive = true;
    setBusy(true);
    setError(null);
    setActive(false);
    const req =
      op === "filter_rows" && inferred.filter
        ? Api.preprocessPreviewFilter(dsId, inferred.filter, 8)
        : Api.preprocessPreview(dsId, op === "filter_rows" ? "drop_missing_rows" : op, op === "drop_missing_rows" ? 8 : 6);
    req
      .then((p) => alive && setPv(p))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "preview failed"))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dsId, op]);

  if (fetched.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted">
        Get data first (Data panel below), then watch it transform here.
      </p>
    );
  }

  // show a readable subset: prioritise columns that actually change
  const cols = pv
    ? (() => {
        const changedCols = new Set<string>(pv.changed.flat());
        const ordered = [
          ...pv.columns.filter((c) => changedCols.has(c)),
          ...pv.columns.filter((c) => !changedCols.has(c)),
        ];
        return ordered.slice(0, 6);
      })()
    : [];

  return (
    <div className="mt-3 space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {fetched.length > 1 && (
          <select
            className="rounded-lg border border-line px-2 py-1 text-xs"
            value={dsId}
            onChange={(e) => setDsId(e.target.value)}
          >
            {fetched.map((f) => (
              <option key={f.dataset_id} value={f.dataset_id}>
                {f.name}
              </option>
            ))}
          </select>
        )}
        <button
          onClick={() => setActive((a) => !a)}
          disabled={busy || !pv}
          className="rounded-lg bg-forest px-3 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          {active ? "◀ Reset" : "Transform ▶"}
        </button>
      </div>

      {/* the paper's step(s) for this node — click one to animate it; add more only if you want to */}
      <div className="flex flex-wrap items-center gap-1.5">
        {allOps.map((k, idx) => {
          const isPaper = idx < paperOps.length;
          return (
            <button
              key={`${k}-${idx}`}
              onClick={() => setOp(k)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                op === k ? "bg-forest text-white" : "border border-line text-forest hover:bg-bg"
              }`}
            >
              {PREPROC_LABELS[k]}
              <span className={`ml-1 text-[9px] ${op === k ? "text-white/70" : "text-muted"}`}>
                {isPaper ? "· paper" : "· added"}
              </span>
              {!isPaper && (
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    const j = idx - paperOps.length;
                    setExtra((x) => x.filter((_, i) => i !== j));
                    if (op === k) setOp(paperOps[0]);
                  }}
                  className={`ml-1 cursor-pointer ${op === k ? "text-white/80" : "text-muted"} hover:text-red-500`}
                >
                  ×
                </span>
              )}
            </button>
          );
        })}
        <select
          className="rounded-lg border border-dashed border-line px-2 py-1 text-xs text-muted"
          value=""
          onChange={(e) => {
            const k = e.target.value as PreprocessOp;
            if (k && !allOps.includes(k)) {
              setExtra((x) => [...x, k]);
              setOp(k);
            }
          }}
        >
          <option value="">➕ Add step…</option>
          {(Object.keys(PREPROC_LABELS) as PreprocessOp[])
            .filter((k) => !allOps.includes(k))
            .map((k) => (
              <option key={k} value={k}>
                {PREPROC_LABELS[k]}
              </option>
            ))}
        </select>
      </div>

      <div className="rounded-lg bg-leaf/10 p-2.5 text-xs text-ink">
        <b>Why this step?</b> {PREPROC_WHY[op]}
      </div>

      {error && <p className="text-red-600">{error}</p>}
      {busy && <p className="text-muted">Loading…</p>}

      {pv && pv.removed && <RowDropTable pv={pv} active={active} />}

      {pv && !pv.removed && cols.length > 0 && (
        <>
          <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight: 240 }}>
            <table className="min-w-full text-xs">
              <thead className="sticky top-0 bg-bg">
                <tr>
                  {cols.map((c) => (
                    <th key={c} className="whitespace-nowrap px-2 py-1 text-left font-medium text-forest">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pv.before.map((brow, i) => (
                  <tr key={i} className="border-t border-line/60">
                    {cols.map((c) => (
                      <AnimatedCell
                        key={c}
                        before={brow[c]}
                        after={pv.after[i]?.[c]}
                        active={active}
                        changed={pv.changed[i]?.includes(c) ?? false}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">
            <span className="font-medium text-forest">{active ? "After" : "Before"}:</span>{" "}
            {active ? pv.summary : "raw values from the dataset"} · showing {cols.length} of{" "}
            {pv.columns.length} columns
          </p>
          <PreprocessFormula pv={pv} />
        </>
      )}
    </div>
  );
}

/** Row-level funnel steps (drop missing / filter by rule): red rows leave, green rows stay.
 *  On Transform the red rows fade + strike through, and the counts tell the whole-dataset story. */
function RowDropTable({ pv, active }: { pv: PreprocessPreview; active: boolean }) {
  const cols = pv.columns.slice(0, 7);
  const removed = pv.removed ?? [];
  return (
    <>
      <div className="overflow-auto rounded-lg border border-line" style={{ maxHeight: 260 }}>
        <table className="min-w-full text-xs">
          <thead className="sticky top-0 bg-bg">
            <tr>
              <th className="px-2 py-1 text-left font-medium text-muted">fate</th>
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1 text-left font-medium text-forest">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pv.before.map((row, i) => {
              const gone = removed[i];
              return (
                <tr
                  key={i}
                  className={`border-t border-line/60 transition-all duration-700 ${
                    gone ? "bg-red-50" : "bg-green-50/50"
                  } ${gone && active ? "line-through opacity-25" : ""}`}
                >
                  <td className={`whitespace-nowrap px-2 py-1 text-[11px] font-semibold ${gone ? "text-red-600" : "text-green-700"}`}>
                    {gone ? (active ? "✗ removed" : "✗ will be removed") : "✓ stays"}
                  </td>
                  {cols.map((c) => (
                    <td key={c} className="whitespace-nowrap px-2 py-1 text-ink">
                      {row[c] == null ? (
                        <span className="rounded bg-red-100 px-1 font-semibold text-red-600">?</span>
                      ) : (
                        String(row[c])
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        {active ? (
          <>
            <span className="font-medium text-forest">After:</span> {pv.summary}
            {pv.n_removed_total != null && pv.n_total != null && (
              <>
                {" "}
                — the dataset shrinks from <b>{pv.n_total}</b> to{" "}
                <b>{pv.n_total - pv.n_removed_total}</b> rows.
              </>
            )}
          </>
        ) : (
          <>
            <span className="font-medium text-forest">Before:</span> sample rows —{" "}
            <span className="text-red-600">red will be removed</span>,{" "}
            <span className="text-green-700">green stays</span> (? = missing value). Press
            Transform ▶ to apply the paper&apos;s rule.
          </>
        )}
      </p>
    </>
  );
}

function firstNumChanged(
  pv: PreprocessPreview,
): { col: string; before: number; after: number } | null {
  for (let i = 0; i < pv.before.length; i++) {
    for (const c of pv.changed[i] ?? []) {
      const bv = pv.before[i]?.[c];
      const av = pv.after[i]?.[c];
      if (typeof bv === "number" && typeof av === "number")
        return { col: c, before: bv, after: av };
    }
  }
  return null;
}

function PreprocessFormula({ pv }: { pv: PreprocessPreview }) {
  const ex = firstNumChanged(pv);
  const changedCols = Array.from(new Set(pv.changed.flat()));

  if (pv.op === "impute_mean" || pv.op === "impute_median") {
    const kind = pv.op === "impute_mean" ? "mean" : "median";
    return (
      <div className="rounded-lg bg-bg p-3 text-xs">
        <p className="font-medium text-forest">
          Each missing cell (highlighted green) is filled with its column&apos;s {kind}:
        </p>
        {changedCols.length ? (
          <ul className="mt-1 space-y-0.5">
            {changedCols.slice(0, 8).map((c) => (
              <li key={c}>
                <span className="text-ink">{c}</span> → {kind} ={" "}
                <span className="font-medium text-forest">{pv.stats[c]?.[kind]}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-muted">No missing values in this sample — nothing to fill.</p>
        )}
      </div>
    );
  }

  if (pv.op === "standardize") {
    const s = ex ? pv.stats[ex.col] : undefined;
    return (
      <div className="rounded-lg bg-bg p-3 text-xs">
        <p className="font-medium text-forest">z = (x − mean) / std</p>
        {ex && s && (
          <p className="mt-1 text-ink">
            Example — {ex.col}: ({ex.before} − {s.mean}) / {s.std} ={" "}
            <span className="font-medium text-forest">{ex.after}</span>
          </p>
        )}
      </div>
    );
  }

  const s = ex ? pv.stats[ex.col] : undefined;
  return (
    <div className="rounded-lg bg-bg p-3 text-xs">
      <p className="font-medium text-forest">scaled = (x − min) / (max − min)</p>
      {ex && s && (
        <p className="mt-1 text-ink">
          Example — {ex.col}: ({ex.before} − {s.min}) / ({s.max} − {s.min}) ={" "}
          <span className="font-medium text-forest">{ex.after}</span>
        </p>
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

  async function refetch() {
    setBusy(true);
    setError(null);
    try {
      onChange(await Api.refetchData(exp.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "auto-fetch failed");
    } finally {
      setBusy(false);
    }
  }

  const hasReal = exp.fetch_report.fetched.some((f) => !f.synthetic);
  const hasMaster = exp.fetch_report.fetched.some((f) => f.resolver === "master");

  async function buildMaster() {
    setBusy(true);
    setError(null);
    try {
      onChange(await Api.buildMasterDataset(exp.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "master build failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-lg text-forest">Data</h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={refetch}
            disabled={busy}
            title="Search OpenML + the UCI repository for the paper's real dataset and pull it in"
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              !hasReal ? "bg-forest text-white hover:opacity-90" : "border border-line text-forest hover:bg-bg"
            } disabled:opacity-50`}
          >
            {busy ? "Working…" : "⟳ Auto-fetch real dataset"}
          </button>
          {exp.fetch_report.fetched.length > 1 && !hasMaster && (
            <button
              onClick={buildMaster}
              disabled={busy}
              title="Consolidate every fetched/uploaded dataset into ONE master table (columns aligned, duplicates dropped) that the whole pipeline runs on"
              className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-forest hover:bg-bg disabled:opacity-50"
            >
              {busy ? "Working…" : "⧉ Build master dataset"}
            </button>
          )}
          <button
            onClick={genDemo}
            disabled={busy}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              empty ? "bg-leaf text-white hover:opacity-90" : "border border-line text-forest hover:bg-bg"
            } disabled:opacity-50`}
          >
            {busy ? "Working…" : "Generate demo data"}
          </button>
        </div>
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
            <li key={f.dataset_id} className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-ink">
                {f.name}
                {f.synthetic && (
                  <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">
                    synthetic
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-muted">
                  {f.n_rows ?? "?"}×{f.n_cols ?? "?"} · {f.resolver}
                </span>
                <button
                  onClick={() => Api.downloadDataset(f.dataset_id, f.name)}
                  title="Download CSV"
                  aria-label={`Download ${f.name}`}
                  className="rounded-lg border border-line px-2 py-0.5 text-xs font-medium text-forest transition hover:bg-bg"
                >
                  ⬇ CSV
                </button>
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
