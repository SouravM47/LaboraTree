"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Api, openBlob, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

// Each Lab is loaded on demand (only when its tab is opened) so the project page opens fast and
// heavy deps (React Flow, vega, papaparse) aren't pulled into the initial route bundle.
const TabLoading = () => <p className="text-sm text-muted">Loading Lab…</p>;
const dyn = (loader: () => Promise<{ default: React.ComponentType<{ projectId: string }> }>) =>
  dynamic(loader, { ssr: false, loading: TabLoading });

const SignalLab = dyn(() => import("@/components/SignalLab"));
const PapersLab = dyn(() => import("@/components/PapersLab"));
const InsightLab = dyn(() => import("@/components/InsightLab"));
const IdeationLab = dyn(() => import("@/components/IdeationLab"));
const TrendLab = dyn(() => import("@/components/TrendLab"));
const DecisionLab = dyn(() => import("@/components/DecisionLab"));
const CollectionLab = dyn(() => import("@/components/CollectionLab"));
const PipelineLab = dyn(() => import("@/components/PipelineLab"));
const LlmActivity = dyn(() => import("@/components/LlmActivity"));

const TABS = [
  { key: "ideation", label: "Ideation Lab" },
  { key: "collection", label: "Collection Lab" },
  { key: "signal", label: "Signal Lab" },
  { key: "insight", label: "Insight Lab" },
  { key: "trend", label: "Trend Lab" },
  { key: "decision", label: "Decision Lab" },
  { key: "papers", label: "Paper Lab" },
  { key: "pipeline", label: "Pipeline" },
  { key: "llm", label: "LLM Activity" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function ProjectWorkspace() {
  const { user, loading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<TabKey>("signal");
  const [error, setError] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [trustScore, setTrustScore] = useState<number | null>(null);

  async function makeReport() {
    setReportBusy(true);
    try {
      const r = await Api.generateReport(projectId);
      setTrustScore(r.trust.score);
      await openBlob(r.download_url);
    } catch {
      /* ignore */
    } finally {
      setReportBusy(false);
    }
  }

  useEffect(() => {
    if (user && projectId) {
      Api.getProject(projectId)
        .then(setProject)
        .catch((e) => setError(e instanceof Error ? e.message : "failed"));
    }
  }, [user, projectId]);

  if (loading || !user) return <p className="text-muted">Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <Link href="/" className="text-sm text-muted hover:text-forest">
        ← Projects
      </Link>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="font-display text-3xl text-forest">{project?.name ?? "…"}</h1>
        <div className="flex items-center gap-3">
          {trustScore !== null && (
            <span className="rounded-full bg-leaf/15 px-3 py-1 text-sm text-forest">
              trust {trustScore}/100
            </span>
          )}
          <button
            onClick={makeReport}
            disabled={reportBusy}
            className="rounded-lg bg-forest px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {reportBusy ? "Building…" : "Report card"}
          </button>
        </div>
      </div>

      <div className="mt-6 flex gap-2 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === t.key
                ? "border-leaf text-forest"
                : "border-transparent text-muted hover:text-forest"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "ideation" && <IdeationLab projectId={projectId} />}
        {tab === "collection" && <CollectionLab projectId={projectId} />}
        {tab === "signal" && <SignalLab projectId={projectId} />}
        {tab === "insight" && <InsightLab projectId={projectId} />}
        {tab === "trend" && <TrendLab projectId={projectId} />}
        {tab === "decision" && <DecisionLab projectId={projectId} />}
        {tab === "papers" && <PapersLab projectId={projectId} />}
        {tab === "pipeline" && <PipelineLab projectId={projectId} />}
        {tab === "llm" && <LlmActivity projectId={projectId} />}
      </div>
    </div>
  );
}
