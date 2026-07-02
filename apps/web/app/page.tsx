"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Api, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export default function Dashboard() {
  const { user, loading } = useRequireAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) Api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, [user]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const p = await Api.createProject(name.trim());
      setProjects((prev) => [p, ...prev]);
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) return <p className="text-muted">Loading…</p>;

  return (
    <div>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl text-forest">Projects</h1>
          <p className="mt-1 text-muted">Each project is a research workspace.</p>
        </div>
        <form onSubmit={create} className="flex gap-2">
          <input
            className="rounded-lg border border-line px-3 py-2 outline-none focus:border-leaf"
            placeholder="New project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            disabled={busy}
            className="rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            Create
          </button>
        </form>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => (
          <Link
            key={p.id}
            href={`/projects/${p.id}`}
            className="rounded-2xl border border-line bg-white p-5 transition hover:border-leaf"
          >
            <h3 className="font-medium text-forest">{p.name}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-muted">
              {p.description || "Open workspace →"}
            </p>
            <p className="mt-3 text-xs text-muted">
              {new Date(p.created_at).toLocaleDateString()}
            </p>
          </Link>
        ))}
        {projects.length === 0 && (
          <p className="text-muted">No projects yet — create one to get started.</p>
        )}
      </div>
    </div>
  );
}
