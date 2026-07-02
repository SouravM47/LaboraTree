"use client";

import { useRef, useState } from "react";

export default function FileDropzone({
  onFiles,
  accept,
  multiple = true,
  hint = "Drag & drop files here, or click to browse",
}: {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  hint?: string;
}) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handle(list: FileList | null) {
    if (!list || list.length === 0) return;
    onFiles(Array.from(list));
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        handle(e.dataTransfer.files);
      }}
      className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition ${
        over ? "border-leaf bg-leaf/5" : "border-line bg-white hover:border-sprout"
      }`}
    >
      <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-full bg-sprout/30 text-forest">
        ⬆
      </div>
      <p className="text-sm text-ink">{hint}</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => handle(e.target.files)}
      />
    </div>
  );
}
