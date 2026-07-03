"use client";

import { useEffect, useMemo, useState } from "react";
import { ReactFlow, Background, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Papa from "papaparse";
import { Api, type ComponentSpecLite, type PipelineResult } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";
import ProvenanceBadge from "@/components/ProvenanceBadge";

type Step = { component_id: string; paramsText: string };

export default function PipelineLab({ projectId }: { projectId: string }) {
  const [components, setComponents] = useState<ComponentSpecLite[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [fileName, setFileName] = useState("");
  const [pick, setPick] = useState("");
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Api.listComponents().then((r) => setComponents(r.components)).catch(() => setComponents([]));
  }, []);

  function loadCsv(files: File[]) {
    Papa.parse<Record<string, unknown>>(files[0], {
      header: true, dynamicTyping: true, skipEmptyLines: true,
      complete: (res) => { setRows(res.data); setFileName(files[0].name); },
    });
  }

  function addStep() {
    if (!pick) return;
    setSteps((s) => [...s, { component_id: pick, paramsText: "{}" }]);
    setResult(null);
  }

  async function runPipeline() {
    setBusy(true); setError(null);
    try {
      const parsed = steps.map((s) => ({
        component_id: s.component_id,
        params: s.paramsText.trim() ? JSON.parse(s.paramsText) : {},
      }));
      setResult(await Api.runPipeline(projectId, { steps: parsed, dataset: rows.length ? rows : null }));
    } catch (e) {
      setError(e instanceof Error ? `Invalid params or run failed: ${e.message}` : "failed");
    } finally {
      setBusy(false);
    }
  }

  const { nodes, edges } = useMemo(() => {
    const chain: { id: string; label: string; status?: string }[] = [
      { id: "data", label: `🗄 ${fileName || (rows.length ? "dataset" : "no data")}` },
      ...steps.map((s, i) => ({
        id: `s${i}`,
        label: s.component_id,
        status: result?.steps[i]?.status,
      })),
    ];
    const nodes: Node[] = chain.map((c, i) => ({
      id: c.id,
      position: { x: i * 200, y: 20 },
      data: { label: c.label },
      style: {
        width: 170, fontSize: 12, padding: 8, borderRadius: 12,
        border: "1px solid #E4EBE1",
        background: c.status === "succeeded" ? "#6DB33F"
          : c.status === "failed" ? "#C0392B"
          : c.id === "data" ? "#E8F0F7" : "#fff",
        color: c.status === "succeeded" || c.status === "failed" ? "#fff" : "#14342A",
      },
    }));
    const edges: Edge[] = chain.slice(1).map((c, i) => ({
      id: `e${i}`, source: chain[i].id, target: c.id, animated: true,
      style: { stroke: "#A8D08D" },
    }));
    return { nodes, edges };
  }, [steps, rows, fileName, result]);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Pipeline canvas</h2>
        <p className="mt-1 text-sm text-muted">
          Chain components across Labs. The dataset flows from step to step; every step is a tracked,
          Evidence-locked run.
        </p>
        <div className="mt-4">
          <FileDropzone multiple={false} accept=".csv"
            hint={rows.length ? `${fileName} · ${rows.length} rows` : "Drop a starting CSV (optional)"}
            onFiles={loadCsv} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <select className="rounded-lg border border-line px-2 py-1.5"
            value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Add a component…</option>
            {components.map((c) => (
              <option key={c.id} value={c.id}>{c.kind} · {c.name}</option>
            ))}
          </select>
          <button onClick={addStep} className="rounded-lg border border-line px-3 py-1.5 text-forest hover:bg-bg">
            + Add step
          </button>
          <button onClick={runPipeline} disabled={busy || steps.length === 0}
            className="rounded-lg bg-leaf px-4 py-1.5 font-medium text-white hover:opacity-90 disabled:opacity-50">
            {busy ? "Running…" : `Run pipeline (${steps.length})`}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {steps.length > 0 && (
        <div className="h-[220px] overflow-hidden rounded-2xl border border-line bg-white">
          <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
            <Background color="#E4EBE1" />
          </ReactFlow>
        </div>
      )}

      <div className="space-y-2">
        {steps.map((s, i) => {
          const r = result?.steps[i];
          return (
            <div key={i} className="rounded-2xl border border-line bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium text-forest">{i + 1}. {s.component_id}</span>
                <div className="flex items-center gap-2">
                  {r && (
                    <span className={`rounded-full px-2 py-0.5 text-xs ${
                      r.status === "succeeded" ? "bg-leaf/20 text-forest" : "bg-red-100 text-red-700"
                    }`}>{r.status}{r.evidence_count != null ? ` · ${r.evidence_count} evidence` : ""}</span>
                  )}
                  {r?.run_id && <ProvenanceBadge runId={r.run_id} />}
                  <button onClick={() => setSteps(steps.filter((_, j) => j !== i))}
                    className="text-sm text-muted hover:text-red-600">remove</button>
                </div>
              </div>
              <textarea
                className="mt-2 w-full rounded-lg border border-line px-2 py-1 font-mono text-xs outline-none focus:border-leaf"
                rows={2}
                value={s.paramsText}
                onChange={(e) =>
                  setSteps(steps.map((x, j) => (j === i ? { ...x, paramsText: e.target.value } : x)))
                }
                placeholder='params JSON, e.g. {"target": "y"}'
              />
              {r?.error && <p className="mt-1 text-xs text-red-600">{r.error}</p>}
              {r?.preview && (
                <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-bg p-2 text-xs text-ink">
                  {JSON.stringify(r.preview, null, 1).slice(0, 1200)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
