"use client";

import { useEffect, useState } from "react";
import { Api, type Paper, type PaperCardData } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";
import PaperCard from "@/components/PaperCard";
import PaperCompare from "@/components/PaperCompare";
import ChatPanel from "@/components/ChatPanel";
import ExperimentCanvas from "@/components/ExperimentCanvas";
import ConfirmDialog from "@/components/ConfirmDialog";

export default function PapersLab({ projectId }: { projectId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selected, setSelected] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Paper | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    Api.listPapers(projectId).then(setPapers).catch(() => setPapers([]));
  }, [projectId]);

  async function upload(files: File[]) {
    setBusy(true);
    setError(null);
    try {
      const p = await Api.uploadPaper(projectId, files[0]);
      setPapers((prev) => [p, ...prev]);
      setSelected(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setError(null);
    try {
      await Api.deletePaper(pendingDelete.id);
      setPapers((prev) => prev.filter((x) => x.id !== pendingDelete.id));
      if (selected?.id === pendingDelete.id) setSelected(null);
      setPendingDelete(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    } finally {
      setDeleting(false);
    }
  }

  if (selected) {
    return (
      <PaperDetail
        paper={selected}
        onBack={() => setSelected(null)}
        onUpdate={(p) => {
          setSelected(p);
          setPapers((prev) => prev.map((x) => (x.id === p.id ? p : x)));
        }}
      />
    );
  }

  if (comparing) {
    return (
      <PaperCompare
        papers={papers.filter((p) => compareIds.has(p.id))}
        onClose={() => setComparing(false)}
        onOpen={(p) => {
          setComparing(false);
          setSelected(p);
        }}
      />
    );
  }

  const comparable = papers.filter((p) => hasCard(p.card));

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="font-display text-xl text-forest">Understand a paper</h2>
        <p className="mt-1 text-sm text-muted">
          Upload a PDF or Word paper to get a plain-language Paper Card, explain-simpler, and chat.
        </p>
        <div className="mt-4">
          <FileDropzone
            multiple={false}
            accept=".pdf,.docx"
            hint={busy ? "Ingesting…" : "Drop a paper (PDF/DOCX), or click to browse"}
            onFiles={upload}
          />
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {papers.length > 0 && (
        <div className="rounded-2xl border border-line bg-white p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg text-forest">Papers</h3>
            {comparable.length >= 2 && (
              <button
                onClick={() => setComparing(true)}
                disabled={compareIds.size < 2}
                title={
                  compareIds.size < 2
                    ? "Tick 2+ papers (with cards) to compare them side-by-side"
                    : "Compare the ticked papers side-by-side"
                }
                className="rounded-lg border border-line px-3 py-1 text-sm font-medium text-forest hover:bg-bg disabled:opacity-40"
              >
                ⇄ Compare{compareIds.size >= 2 ? ` (${compareIds.size})` : ""}
              </button>
            )}
          </div>
          <ul className="mt-3 divide-y divide-line">
            {papers.map((p) => (
              <li key={p.id} className="flex items-center gap-2">
                {comparable.length >= 2 && (
                  <input
                    type="checkbox"
                    aria-label={`Select ${p.title} for comparison`}
                    disabled={!hasCard(p.card)}
                    title={hasCard(p.card) ? "Select for comparison" : "Generate this paper's card first"}
                    checked={compareIds.has(p.id)}
                    onChange={(e) =>
                      setCompareIds((prev) => {
                        const next = new Set(prev);
                        if (e.target.checked) next.add(p.id);
                        else next.delete(p.id);
                        return next;
                      })
                    }
                    className="h-4 w-4 accent-[#14342A] disabled:opacity-30"
                  />
                )}
                <button
                  onClick={() => setSelected(p)}
                  className="flex flex-1 items-center justify-between py-3 text-left hover:text-forest"
                >
                  <span className="text-ink">{p.title}</span>
                  <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">
                    {p.status} · {p.n_chunks} chunks
                  </span>
                </button>
                <button
                  onClick={() => setPendingDelete(p)}
                  title="Delete paper"
                  aria-label={`Delete ${p.title}`}
                  className="rounded-lg p-1.5 text-muted transition hover:bg-red-50 hover:text-red-600"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                    <line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete paper?"
        message={
          <>
            <b className="text-forest">{pendingDelete?.title}</b> — its Paper Card, chunks and any
            experiments will be permanently deleted. This cannot be undone.
          </>
        }
        confirmLabel="Delete paper"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function hasCard(card: Paper["card"]): card is PaperCardData {
  return !!card && typeof (card as { paper_type?: string }).paper_type === "string";
}

function PaperDetail({
  paper,
  onBack,
  onUpdate,
}: {
  paper: Paper;
  onBack: () => void;
  onUpdate: (p: Paper) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"study" | "experiment">("study");

  async function generate() {
    setBusy(true);
    try {
      onUpdate(await Api.makeCard(paper.id));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button onClick={onBack} className="text-sm text-muted hover:text-forest">
        ← All papers
      </button>
      <h2 className="mt-2 font-display text-2xl text-forest">{paper.title}</h2>

      {!hasCard(paper.card) ? (
        <div className="mt-6 rounded-2xl border border-line bg-white p-8 text-center">
          <p className="text-muted">No Paper Card yet.</p>
          <button
            onClick={generate}
            disabled={busy}
            className="mt-4 rounded-lg bg-leaf px-4 py-2 font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Generating…" : "Generate Paper Card"}
          </button>
        </div>
      ) : (
        <>
          <div className="mt-4 flex gap-2 border-b border-line">
            {(["study", "experiment"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize transition ${
                  mode === m
                    ? "border-leaf text-forest"
                    : "border-transparent text-muted hover:text-forest"
                }`}
              >
                {m === "study" ? "Study" : "Experiment Ground"}
              </button>
            ))}
          </div>

          {mode === "study" ? (
            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <PaperCard paperId={paper.id} card={paper.card} />
              </div>
              <div className="lg:col-span-1">
                <div className="sticky top-4 h-[70vh]">
                  <ChatPanel paperId={paper.id} />
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-6">
              <ExperimentCanvas paperId={paper.id} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
