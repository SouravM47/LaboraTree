"use client";

import { useEffect, useState } from "react";
import { getJSON, type ComponentList, type Health } from "@/lib/api";

export default function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [components, setComponents] = useState<ComponentList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJSON<Health>("/health"), getJSON<ComponentList>("/api/components")])
      .then(([h, c]) => {
        setHealth(h);
        setComponents(c);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="rounded-2xl border border-line bg-white p-5 text-sm text-muted">
        API unreachable ({error}). Start it with{" "}
        <code className="text-forest">uv run uvicorn laboratree.main:app --reload</code>.
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-display text-lg text-forest">Datastores</h3>
        <ul className="mt-3 space-y-2 text-sm">
          {health
            ? Object.entries(health.services).map(([name, s]) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="capitalize text-ink">{name}</span>
                  <span className={s.ok ? "text-leaf" : "text-red-500"}>
                    {s.ok ? "● connected" : "○ down"}
                  </span>
                </li>
              ))
            : "Loading…"}
        </ul>
      </div>

      <div className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-display text-lg text-forest">
          Registered components {components ? `(${components.count})` : ""}
        </h3>
        <ul className="mt-3 space-y-2 text-sm">
          {components?.components.map((c) => (
            <li key={c.id} className="flex items-center justify-between">
              <span className="text-ink">{c.name}</span>
              <span className="rounded-full bg-sprout/30 px-2 py-0.5 text-xs text-forest">
                {c.kind}
              </span>
            </li>
          )) ?? "Loading…"}
        </ul>
      </div>
    </div>
  );
}
