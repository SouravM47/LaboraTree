"use client";

import { useEffect, useState } from "react";
import { Api, type Paper, type PaperCardData } from "@/lib/api";
import FileDropzone from "@/components/FileDropzone";
import PaperCard from "@/components/PaperCard";
import ChatPanel from "@/components/ChatPanel";

export default function PapersLab({ projectId }: { projectId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selected, setSelected] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          <h3 className="font-display text-lg text-forest">Papers</h3>
          <ul className="mt-3 divide-y divide-line">
            {papers.map((p) => (
              <li key={p.id}>
                <button
                  onClick={() => setSelected(p)}
                  className="flex w-full items-center justify-between py-3 text-left hover:text-forest"
                >
                  <span className="text-ink">{p.title}</span>
                  <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">
                    {p.status} · {p.n_chunks} chunks
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function hasCard(card: Paper["card"]): card is PaperCardData {
  return !!card && typeof (card as PaperCardData).problem_statement === "string" &&
    (card as PaperCardData).problem_statement.length > 0;
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
      )}
    </div>
  );
}
