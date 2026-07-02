"use client";

import { useEffect, useRef } from "react";

// Renders a Vega-Lite spec via vega-embed (loaded client-side only).
export default function VegaChart({ spec }: { spec: Record<string, unknown> }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const el = ref.current;
    if (!el) return;
    import("vega-embed")
      .then(({ default: embed }) => {
        if (cancelled || !ref.current) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return embed(ref.current, spec as any, { actions: false, renderer: "svg" });
      })
      .catch(() => {
        if (el) el.textContent = "Could not render chart.";
      });
    return () => {
      cancelled = true;
      if (el) el.innerHTML = "";
    };
  }, [spec]);

  return <div ref={ref} className="w-full overflow-x-auto" />;
}
