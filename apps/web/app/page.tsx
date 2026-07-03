"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Api, type Project } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import ConfirmDialog from "@/components/ConfirmDialog";

export default function Dashboard() {
  const { user, loading } = useRequireAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

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

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setError(null);
    try {
      await Api.deleteProject(pendingDelete.id);
      setProjects((prev) => prev.filter((x) => x.id !== pendingDelete.id));
      setPendingDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "delete failed");
    } finally {
      setDeleting(false);
    }
  }

  if (loading || !user) return <p className="text-muted">Loading…</p>;

  const canDelete = user.role === "owner" || user.role === "admin";

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
          <div
            key={p.id}
            className="group relative rounded-2xl border border-line bg-white p-5 transition hover:border-leaf"
          >
            <Link href={`/projects/${p.id}`} className="block">
              <h3 className="pr-8 font-medium text-forest">{p.name}</h3>
              <p className="mt-1 line-clamp-2 text-sm text-muted">
                {p.description || "Open workspace →"}
              </p>
              <p className="mt-3 text-xs text-muted">
                {new Date(p.created_at).toLocaleDateString()}
              </p>
            </Link>
            {canDelete && (
              <button
                onClick={() => setPendingDelete(p)}
                title="Delete project"
                aria-label={`Delete ${p.name}`}
                className="absolute right-3 top-3 rounded-lg p-1.5 text-muted opacity-0 transition hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                  <line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" />
                </svg>
              </button>
            )}
          </div>
        ))}
        {projects.length === 0 && (
          <p className="text-muted">No projects yet — create one to get started.</p>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete project?"
        message={
          <>
            <b className="text-forest">{pendingDelete?.name}</b> and everything in it — papers,
            datasets, runs and experiments — will be permanently deleted. This cannot be undone.
          </>
        }
        confirmLabel="Delete project"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
