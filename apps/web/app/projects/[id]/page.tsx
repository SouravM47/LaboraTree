"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Api, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import SignalLab from "@/components/SignalLab";
import PapersLab from "@/components/PapersLab";

const TABS = [
  { key: "signal", label: "Signal Lab" },
  { key: "papers", label: "Paper Lab" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function ProjectWorkspace() {
  const { user, loading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<TabKey>("signal");
  const [error, setError] = useState<string | null>(null);

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
      <h1 className="mt-2 font-display text-3xl text-forest">{project?.name ?? "…"}</h1>

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
        {tab === "signal" && <SignalLab projectId={projectId} />}
        {tab === "papers" && <PapersLab projectId={projectId} />}
      </div>
    </div>
  );
}
