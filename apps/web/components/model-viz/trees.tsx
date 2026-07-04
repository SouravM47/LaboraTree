"use client";

import { useState } from "react";
import type { TreeNode } from "@/lib/api";
import type { TestProps, TrainProps } from "./shared";

/** Trees family — a LITERAL tree diagram (SVG): question nodes branch yes/no down to colored
 *  leaf predictions; during testing the row's root-to-leaf path lights up gold. */

const NODE_W = 104;
const NODE_H = 34;
const LEAF_W = 92;
const X_GAP = 12;
const Y_GAP = 64;
const PALETTE = ["#6DB33F", "#C0392B", "#2E6C8E", "#B8860B", "#7D3C98"];

type Laid = {
  node: TreeNode;
  x: number; // center x
  y: number; // top y
  onPath: boolean;
  children: Laid[];
};

function countLeaves(n: TreeNode): number {
  if (n.leaf || (!n.left && !n.right)) return 1;
  return (n.left ? countLeaves(n.left) : 0) + (n.right ? countLeaves(n.right) : 0);
}

function depthOf(n: TreeNode): number {
  if (n.leaf || (!n.left && !n.right)) return 0;
  return 1 + Math.max(n.left ? depthOf(n.left) : 0, n.right ? depthOf(n.right) : 0);
}

/** Assign x by leaf slots (each leaf gets a column; parents sit midway over their children). */
function layout(node: TreeNode, path: string[] | undefined, depth: number, leafStart: number, onPath: boolean): Laid {
  const slotW = LEAF_W + X_GAP;
  if (node.leaf || (!node.left && !node.right)) {
    return { node, x: (leafStart + 0.5) * slotW, y: depth * Y_GAP, onPath, children: [] };
  }
  const go = path?.[depth];
  const leftLeaves = node.left ? countLeaves(node.left) : 0;
  const kids: Laid[] = [];
  if (node.left)
    kids.push(layout(node.left, path, depth + 1, leafStart, onPath && go === "left"));
  if (node.right)
    kids.push(layout(node.right, path, depth + 1, leafStart + leftLeaves, onPath && go === "right"));
  const x = kids.length ? (kids[0].x + kids[kids.length - 1].x) / 2 : (leafStart + 0.5) * slotW;
  return { node, x, y: depth * Y_GAP, onPath, children: kids };
}

function collectPredictions(n: TreeNode, out: string[]) {
  if (n.leaf || (!n.left && !n.right)) {
    const p = String(n.prediction);
    if (!out.includes(p)) out.push(p);
    return;
  }
  if (n.left) collectPredictions(n.left, out);
  if (n.right) collectPredictions(n.right, out);
}

function renderEdges(l: Laid, out: React.ReactNode[], key = "e") {
  l.children.forEach((c, i) => {
    const hot = l.onPath && c.onPath;
    const x1 = l.x;
    const y1 = l.y + NODE_H;
    const x2 = c.x;
    const y2 = c.y;
    out.push(
      <g key={`${key}${i}`}>
        <path
          d={`M${x1},${y1} C${x1},${y1 + 22} ${x2},${y2 - 22} ${x2},${y2}`}
          fill="none"
          stroke={hot ? "#C9A227" : "#C7D4CC"}
          strokeWidth={hot ? 2.5 : 1.4}
        />
        <text
          x={(x1 + x2) / 2 + (i === 0 ? -6 : 6)}
          y={(y1 + y2) / 2}
          fontSize={9}
          fill={hot ? "#B8860B" : "#7C8A80"}
          textAnchor={i === 0 ? "end" : "start"}
          fontWeight={hot ? 700 : 400}
        >
          {i === 0 ? "yes" : "no"}
        </text>
      </g>,
    );
    renderEdges(c, out, `${key}${i}.`);
  });
}

function renderNodes(l: Laid, preds: string[], out: React.ReactNode[], key = "n") {
  const n = l.node;
  const isLeaf = n.leaf || (!n.left && !n.right);
  if (isLeaf) {
    const color = PALETTE[preds.indexOf(String(n.prediction)) % PALETTE.length];
    out.push(
      <g key={key}>
        <rect
          x={l.x - LEAF_W / 2}
          y={l.y}
          width={LEAF_W}
          height={NODE_H}
          rx={16}
          fill={color}
          opacity={l.onPath ? 1 : 0.72}
          stroke={l.onPath ? "#C9A227" : "none"}
          strokeWidth={3}
        />
        <text x={l.x} y={l.y + 14} fontSize={9.5} fill="#fff" textAnchor="middle" fontWeight={700}>
          {String(n.prediction)}
        </text>
        <text x={l.x} y={l.y + 26} fontSize={8} fill="#fff" textAnchor="middle" opacity={0.9}>
          {n.confidence != null ? `${Math.round(n.confidence * 100)}% of ${n.samples}` : `${n.samples} rows`}
        </text>
      </g>,
    );
    return;
  }
  out.push(
    <g key={key}>
      <rect
        x={l.x - NODE_W / 2}
        y={l.y}
        width={NODE_W}
        height={NODE_H}
        rx={8}
        fill={l.onPath ? "#FFFBEA" : "#fff"}
        stroke={l.onPath ? "#C9A227" : "#14342A"}
        strokeWidth={l.onPath ? 2.5 : 1.2}
      />
      <text x={l.x} y={l.y + 14} fontSize={9.5} fill="#14342A" textAnchor="middle" fontWeight={700}>
        {n.feature} ≤ {n.threshold}
      </text>
      <text x={l.x} y={l.y + 26} fontSize={8} fill="#7C8A80" textAnchor="middle">
        gain {n.gain} · {n.samples} rows
      </text>
    </g>,
  );
  l.children.forEach((c, i) => renderNodes(c, preds, out, `${key}${i}`));
}

export function TreeDiagram({ root, path }: { root: TreeNode; path?: string[] }) {
  const leaves = countLeaves(root);
  const depth = depthOf(root);
  const W = leaves * (LEAF_W + X_GAP);
  const H = depth * Y_GAP + NODE_H + 8;
  const laid = layout(root, path, 0, 0, path != null);
  const edges: React.ReactNode[] = [];
  const nodes: React.ReactNode[] = [];
  const preds: string[] = [];
  collectPredictions(root, preds);
  renderEdges(laid, edges);
  renderNodes(laid, preds, nodes);
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-white p-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ minWidth: Math.min(W, 560) }}
        role="img"
        aria-label="decision tree"
      >
        {edges}
        {nodes}
      </svg>
    </div>
  );
}

const isBoostHint = (hint?: string) => /(boost|xgb|gbm|gbdt|lightgbm|catboost)/i.test(hint ?? "");

function ModeTabs({
  mode,
  setMode,
}: {
  mode: "single" | "ensemble";
  setMode: (m: "single" | "ensemble") => void;
}) {
  return (
    <div className="mb-1.5 flex gap-1 text-[11px]">
      {(
        [
          ["single", "One decision tree"],
          ["ensemble", "Boosting — 3 trees stacked"],
        ] as const
      ).map(([m, label]) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={`rounded-full px-2.5 py-0.5 transition ${
            mode === m ? "bg-forest text-white" : "border border-line text-forest hover:bg-bg"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function Train({ trace, hint }: TrainProps) {
  const hasEnsemble = !!trace.rounds?.length;
  const [mode, setMode] = useState<"single" | "ensemble">(
    hasEnsemble && isBoostHint(hint) ? "ensemble" : "single",
  );

  if (mode === "ensemble" && hasEnsemble) {
    return (
      <div>
        <ModeTabs mode={mode} setMode={setMode} />
        <p className="mb-1 text-[11px] text-muted">
          The REAL boosting ensemble fitted on this data. It starts from a baseline score of{" "}
          <b>{trace.baseline}</b>, then each tree is trained on the <b>mistakes left by the previous
          ones</b> — its leaves output score corrections (+pushes toward{" "}
          {trace.labels?.[1] ?? "higher"}, − toward {trace.labels?.[0] ?? "lower"}) that all ADD UP.
        </p>
        <div className="space-y-2">
          {trace.rounds!.map((r, i) => (
            <div key={i}>
              <p className="mb-0.5 text-[11px] font-medium text-forest">
                Tree {i + 1}
                {i > 0 && <span className="font-normal text-muted"> — fixes what trees 1…{i} still get wrong</span>}
              </p>
              <TreeDiagram root={r.tree} />
            </div>
          ))}
        </div>
        <p className="mt-1 rounded-lg bg-leaf/10 p-1.5 text-[11px]">
          final score = {trace.baseline} + tree₁ + tree₂ + tree₃{" "}
          {trace.task === "classification" && <>→ sigmoid → probability → class</>}
        </p>
      </div>
    );
  }

  return (
    <div>
      {hasEnsemble && <ModeTabs mode={mode} setMode={setMode} />}
      <p className="mb-1 text-[11px] text-muted">
        A literal decision tree, grown from this data. Each box asks a yes/no question about ONE
        feature — chosen because it best separates the groups (<b>gain</b> = how much cleaner the
        split makes them). Follow yes ↙ / no ↘ down to a colored leaf = the prediction.
      </p>
      {trace.tree && <TreeDiagram root={trace.tree} />}
    </div>
  );
}

export function Test({ trace, row, hint }: TestProps) {
  const hasEnsemble = !!(trace.rounds?.length && row.rounds?.length);
  const [mode, setMode] = useState<"single" | "ensemble">(
    hasEnsemble && isBoostHint(hint) ? "ensemble" : "single",
  );

  if (mode === "ensemble" && hasEnsemble) {
    let running = trace.baseline ?? 0;
    return (
      <div className="space-y-2">
        <ModeTabs mode={mode} setMode={setMode} />
        <div className="rounded-lg bg-bg p-1.5 text-[11px]">
          start at baseline score <b>{trace.baseline}</b>
        </div>
        {trace.rounds!.map((r, i) => {
          const c = row.rounds![i];
          running = Math.round((running + c.value) * 1000) / 1000;
          return (
            <div key={i}>
              <p className="mb-0.5 text-[11px] font-medium text-forest">
                Tree {i + 1} — this row follows the gold path:
              </p>
              <TreeDiagram root={r.tree} path={c.path.map((s) => s.go)} />
              <p className="mt-0.5 text-[11px]">
                tree {i + 1} outputs{" "}
                <b className={c.value >= 0 ? "text-green-700" : "text-red-600"}>
                  {c.value >= 0 ? "+" : ""}
                  {c.value}
                </b>{" "}
                → running score <b>{running}</b>
              </p>
            </div>
          );
        })}
        <div className="rounded-lg bg-leaf/10 p-2 text-[11px]">
          final score <b>{row.boost_score}</b>
          {row.boost_prob != null && (
            <>
              {" "}
              → sigmoid → probability <b>{row.boost_prob}</b>
            </>
          )}{" "}
          → predicts <b className="text-forest">{String(row.boost_pred ?? row.predicted)}</b>
        </div>
      </div>
    );
  }

  if (!trace.tree) return null;
  const steps = row.path ?? [];
  return (
    <div className="space-y-2">
      {hasEnsemble && <ModeTabs mode={mode} setMode={setMode} />}
      <TreeDiagram root={trace.tree} path={steps.map((s) => s.go)} />
      <div className="rounded-lg border border-line bg-white p-2 text-[11px]">
        <p className="mb-1 text-muted">the gold path, question by question:</p>
        {steps.map((s, i) => (
          <div key={i} className="flex flex-wrap gap-1 border-t border-line/50 py-0.5 first:border-t-0">
            <span className="text-muted">{i + 1}.</span>
            <span>
              {s.feature} = <b>{s.value}</b> — is it ≤ {s.threshold}?
            </span>
            <b className={s.go === "left" ? "text-forest" : "text-red-700"}>
              {s.go === "left" ? "yes ↙" : "no ↘"}
            </b>
          </div>
        ))}
        <p className="mt-1 rounded bg-leaf/10 p-1.5">
          lands on leaf → predicts <b className="text-forest">{String(row.predicted)}</b>
        </p>
      </div>
    </div>
  );
}
