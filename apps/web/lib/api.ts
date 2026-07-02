export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type Health = {
  status: string;
  services: Record<string, { ok: boolean; error?: string; provider?: string; backend?: string }>;
};

export type ComponentSpec = {
  id: string;
  name: string;
  kind: string;
  summary: string;
  tags: string[];
};

export type ComponentList = { count: number; components: ComponentSpec[] };
