"use client";

/**
 * Model-appropriate animated diagram for a model node.
 *  - "nn"      → neural network: activations flow forward, then a backprop sweep flows back
 *  - "trees"   → boosted-tree ensemble: small trees appear one after another (boosting rounds)
 *  - "linear"  → features → weighted sum (Σ) → prediction
 *  - "generic" → data → computation → prediction
 * Pure SVG + CSS keyframes (self-contained, GPU-friendly). react-spring drives the trophy elsewhere.
 */

export type ModelKind =
  | "nn"
  | "trees"
  | "linear"
  | "knn"
  | "timeseries"
  | "clustering"
  | "anomaly"
  | "generic";

/** Map a model's name/component-id to its animation family (mirrors labs/modeling/viz). Order
 *  matters: the most specific cues run first (e.g. "isolation forest" before "forest"). */
export function modelKind(text: string): ModelKind {
  const s = (text || "").toLowerCase();
  if (/(isolation forest|anomal|outlier|one-?class|\blof\b)/.test(s)) return "anomaly";
  if (/(k-?means|dbscan|cluster|gaussian mixture|\bgmm\b|hierarchical)/.test(s)) return "clustering";
  if (/(arima|sarima|time[\s-]?series|forecast|exponential smoothing|prophet|autoregress)/.test(s))
    return "timeseries";
  if (/(k-?nearest|nearest neighbou?r|\bknn\b)/.test(s)) return "knn";
  if (/(neural|cnn|mlp|perceptron|deep|lstm|rnn|gru|transformer|network|dnn|autoencoder)/.test(s))
    return "nn";
  if (/(xgboost|xgb|boost|forest|tree|gbm|gbdt|catboost|lightgbm|gradient_boosting|bagging|ensemble)/.test(s))
    return "trees";
  if (/(linear|logistic|logit|ols|regression|svm|support vector|glm|ridge|lasso|probit|poisson|bayes)/.test(s))
    return "linear";
  return "generic";
}

/** True when a "model" node is really a feature-selection step (BBO etc.), not a predictive model. */
export function isFeatureSelection(text: string): boolean {
  return /(feature[\s-]*selection|feature[\s-]*subset|\bbbo\b|biogeograph|feature[\s-]*optim|select[\w\s]*feature)/i.test(
    text || "",
  );
}

const KIND_CAPTION: Record<ModelKind, string> = {
  nn: "Data flows forward through the layers; errors flow back to adjust the weights.",
  trees: "Trees are added one by one — each fixes the mistakes of the ones before it.",
  linear: "Each feature is weighted, summed, and turned into a prediction.",
  knn: "A new row is predicted by the most similar rows the model has memorized.",
  timeseries: "The next value is predicted from the last few values of the same series.",
  clustering: "Rows are grouped by similarity — no answer column needed.",
  anomaly: "The model learns what usual rows look like and flags the unusual ones.",
  generic: "Data flows in, the model computes, a prediction comes out.",
};

export default function ModelAnimation({ kind }: { kind: ModelKind }) {
  return (
    <div className="rounded-xl border border-line bg-gradient-to-b from-white to-[#F6FAF2] p-2">
      <style>{CSS}</style>
      <svg viewBox="0 0 260 120" width="100%" height="120" role="img" aria-label={`${kind} animation`}>
        {kind === "nn" && <NN />}
        {kind === "trees" && <Trees />}
        {kind === "linear" && <Linear />}
        {/* knn/timeseries/clustering/anomaly get their granular staged view when data exists;
            the mini conceptual SVG falls back to the generic compute-flow */}
        {!["nn", "trees", "linear"].includes(kind) && <Generic />}
      </svg>
      <p className="px-1 pb-0.5 text-[11px] text-muted">{KIND_CAPTION[kind]}</p>
    </div>
  );
}

/* ---------------- neural network ---------------- */

function NN() {
  const layers = [4, 5, 4, 2];
  const xs = [30, 103, 176, 235];
  const cols = layers.map((count, li) => {
    const gap = 96 / (count + 1);
    return Array.from({ length: count }, (_, i) => ({ x: xs[li], y: 12 + gap * (i + 1) }));
  });
  const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
  for (let l = 0; l < cols.length - 1; l++)
    for (const a of cols[l]) for (const b of cols[l + 1]) edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });

  return (
    <g>
      {edges.map((e, i) => (
        <line key={i} className="nnEdge" x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} />
      ))}
      {cols.map((col, li) =>
        col.map((n, i) => (
          <circle
            key={`${li}-${i}`}
            className="nnNode"
            cx={n.x}
            cy={n.y}
            r={li === 0 ? 5 : li === cols.length - 1 ? 6 : 5.5}
            style={{ animationDelay: `${li * 0.25}s`, fill: NODE_FILL[li] ?? "#6DB33F" }}
          />
        )),
      )}
      {/* backprop sweep bar, right → left */}
      <rect className="bpSweep" x={0} y={6} width={7} height={108} rx={3} />
      <text x={30} y={116} className="lbl">
        input
      </text>
      <text x={205} y={116} className="lbl">
        output
      </text>
    </g>
  );
}
const NODE_FILL = ["#2E6C8E", "#6DB33F", "#3F8F5B", "#14342A"];

/* ---------------- boosted trees ---------------- */

function Trees() {
  const trees = [0, 1, 2, 3];
  return (
    <g>
      {trees.map((t) => (
        <g key={t} className="treeItem" style={{ animationDelay: `${t * 0.5}s` }} transform={`translate(${20 + t * 60}, 20)`}>
          <MiniTree />
          {t < trees.length - 1 && (
            <text x={44} y={44} className="plus">
              +
            </text>
          )}
        </g>
      ))}
      <text x={20} y={112} className="lbl">
        round 1
      </text>
      <text x={196} y={112} className="lbl">
        stronger ensemble →
      </text>
    </g>
  );
}
function MiniTree() {
  return (
    <g stroke="#14342A" strokeWidth={1.4} fill="none">
      <line x1={20} y1={8} x2={8} y2={30} />
      <line x1={20} y1={8} x2={32} y2={30} />
      <line x1={8} y1={30} x2={2} y2={52} />
      <line x1={8} y1={30} x2={14} y2={52} />
      <line x1={32} y1={30} x2={26} y2={52} />
      <line x1={32} y1={30} x2={38} y2={52} />
      <circle cx={20} cy={8} r={3.5} fill="#6DB33F" stroke="none" />
      {[2, 14, 26, 38].map((x) => (
        <circle key={x} cx={x} cy={52} r={3} fill="#A8D08D" stroke="none" />
      ))}
    </g>
  );
}

/* ---------------- linear ---------------- */

function Linear() {
  const feats = [24, 48, 72, 96];
  return (
    <g>
      {feats.map((y, i) => (
        <g key={i}>
          <circle cx={26} cy={y} r={7} fill="#EAF2F8" stroke="#2E6C8E" strokeWidth={1.2} />
          <text x={26} y={y + 3} className="feat">
            x{i + 1}
          </text>
          <line className="lnEdge" x1={34} y1={y} x2={120} y2={60} />
          <text x={70} y={y < 60 ? y - 4 : y + 12} className="wlbl">
            w{i + 1}
          </text>
        </g>
      ))}
      <circle className="sumPulse" cx={130} cy={60} r={16} fill="#EEF6E6" stroke="#6DB33F" strokeWidth={1.6} />
      <text x={130} y={65} className="sum">
        Σ
      </text>
      <line className="lnEdge" x1={146} y1={60} x2={210} y2={60} />
      <rect x={210} y={48} width={40} height={24} rx={6} fill="#14342A" />
      <text x={230} y={64} className="pred">
        ŷ
      </text>
    </g>
  );
}

/* ---------------- generic ---------------- */

function Generic() {
  return (
    <g>
      <rect x={16} y={44} width={46} height={32} rx={6} fill="#EAF2F8" stroke="#2E6C8E" strokeWidth={1.2} />
      <text x={39} y={64} className="box">
        data
      </text>
      <line className="lnEdge" x1={62} y1={60} x2={104} y2={60} />
      <g className="gear" style={{ transformOrigin: "130px 60px" }}>
        <circle cx={130} cy={60} r={20} fill="#EEF6E6" stroke="#6DB33F" strokeWidth={1.6} />
        {Array.from({ length: 8 }).map((_, i) => {
          const a = (i * Math.PI) / 4;
          return (
            <rect
              key={i}
              x={128}
              y={36}
              width={4}
              height={7}
              fill="#6DB33F"
              transform={`rotate(${(a * 180) / Math.PI} 130 60)`}
            />
          );
        })}
      </g>
      <line className="lnEdge" x1={156} y1={60} x2={198} y2={60} />
      <rect x={198} y={44} width={50} height={32} rx={6} fill="#14342A" />
      <text x={223} y={64} className="pred">
        prediction
      </text>
    </g>
  );
}

/* ---------------- styles ---------------- */

const CSS = `
.nnEdge { stroke:#9FCE7C; stroke-width:1; stroke-dasharray:3 3; animation: nnflow 1.1s linear infinite; }
@keyframes nnflow { to { stroke-dashoffset:-6; } }
.nnNode { animation: nnpulse 2s ease-in-out infinite; }
@keyframes nnpulse { 0%,100% { opacity:.65; } 50% { opacity:1; } }
.bpSweep { fill:#C9A227; opacity:0; animation: bpsweep 3.4s ease-in-out infinite; }
@keyframes bpsweep {
  0% { transform: translateX(200px); opacity:0; }
  55% { opacity:0; }
  60% { opacity:.45; }
  92% { opacity:.45; transform: translateX(0); }
  100% { opacity:0; transform: translateX(0); }
}
.lbl { fill:#5b6b62; font-size:8px; }
.treeItem { opacity:0; transform: scale(.6); transform-origin: center; animation: treein 2.4s ease-in-out infinite; }
@keyframes treein { 0% { opacity:0; transform:scale(.6);} 15% { opacity:1; transform:scale(1);} 85% { opacity:1;} 100% { opacity:.15; } }
.plus { fill:#14342A; font-size:16px; font-weight:700; }
.lnEdge { stroke:#9FCE7C; stroke-width:1.6; stroke-dasharray:4 4; animation: nnflow 1s linear infinite; }
.wlbl { fill:#8a9a90; font-size:7px; }
.feat { fill:#2E6C8E; font-size:8px; text-anchor:middle; font-weight:600; }
.sum { fill:#14342A; font-size:15px; text-anchor:middle; font-weight:700; }
.sumPulse { animation: sump 1.8s ease-in-out infinite; }
@keyframes sump { 0%,100% { r:15; } 50% { r:17; } }
.pred { fill:#fff; font-size:9px; text-anchor:middle; font-weight:600; }
.box { fill:#14342A; font-size:9px; text-anchor:middle; }
.gear { animation: spin 6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
`;
