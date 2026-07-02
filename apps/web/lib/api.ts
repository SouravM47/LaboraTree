// Auth-aware API client for the Laboratree backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "lt_token";
const ORG_KEY = "lt_org";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function getOrg(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_KEY);
}
export function setSession(token: string, orgId: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ORG_KEY, orgId);
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ORG_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  const token = getToken();
  const org = getOrg();
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (org) h["X-Org-Id"] = org;
  return h;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json())?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { headers: authHeaders() });
}
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", headers: authHeaders(), body: form });
}

export async function downloadBlob(path: string, filename: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, "download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function openBlob(path: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, "open failed");
  const blob = await res.blob();
  window.open(URL.createObjectURL(blob), "_blank");
}

// ---------------- typed shapes ----------------
export type TokenOut = { access_token: string; org_id: string };
export type Me = { id: string; email: string; full_name: string; active_org_id: string; role: string };
export type Project = { id: string; name: string; description: string; created_at: string };

export type SignalSummary = {
  run_id: string;
  artifact_id: string;
  download_url: string;
  summary: {
    sources: string[];
    n_tables: number;
    total_rows: number;
    text_blocks: number;
    sheets: { sheet: string; source: string; kind: string; n_rows: number; n_cols: number; columns: string }[];
    errors: { source: string; error: string }[];
  };
};

export type MathItem = { formula: string; explanation: string };
export type PaperCardData = {
  problem_statement: string;
  models_used: string[];
  data_sources: string[];
  preprocessing: string[];
  data_sample: string;
  independent_variables: string[];
  target_variable: string;
  variants: string[];
  math: MathItem[];
  results: string;
  inference: string;
  [k: string]: unknown;
};
export type Paper = {
  id: string;
  title: string;
  filename: string;
  status: string;
  n_chunks: number;
  card: PaperCardData | Record<string, never>;
  created_at: string;
};
export type ChatAnswer = { answer: string; citations: number[]; used: { ordinal: number; text: string }[] };

export type Member = { user_id: string; email: string; full_name: string; role: string };
export const ROLES = ["viewer", "analyst", "admin", "owner"] as const;

export type WalkNode = {
  id: string;
  kind: string;
  title: string;
  detail?: string;
  component_id?: string | null;
  params?: Record<string, unknown>;
};
export type FetchedDataset = {
  name: string;
  filename: string;
  dataset_id: string;
  resolver: string;
  source: string;
  n_rows: number | null;
  n_cols: number | null;
};
export type Unresolved = {
  name: string;
  reason: string;
  source?: string | null;
  url?: string | null;
  instructions: string;
};
export type Experiment = {
  id: string;
  paper_id: string;
  status: string;
  walkthrough: WalkNode[];
  fetch_report: { run_id?: string; fetched: FetchedDataset[]; unresolved: Unresolved[] };
  gate_id?: string | null;
};
export type NodeRunResult = {
  run_id: string;
  component_id: string;
  forked: boolean;
  metrics: Record<string, number>;
  paper_reported: string;
};

export type Hypothesis = {
  id: string;
  text: string;
  elo: number;
  rank: number;
  critique?: string;
  origin?: string;
};
export type IdeationSession = {
  id: string;
  goal: string;
  status: string;
  hypotheses: Hypothesis[];
  meta_review: string;
  created_at: string;
};

export type Trust = {
  score: number;
  reproducibility: number;
  evidence_coverage: number;
  leakage_flags: number;
  n_runs: number;
};
export type ReportResult = {
  run_id: string;
  artifact_id: string;
  download_url: string;
  trust: Trust;
  project: string;
};

export type SurveyQuestion = { id: string; text: string; type: string; options?: string[] };
export type BiasFinding = { question: string; issue: string; severity: string; suggestion: string };
export type SampleResult = {
  sample_size: number;
  unadjusted: number;
  params: Record<string, unknown>;
};
export type PilotResult = { persona: string; n: number; respondents: Record<string, string>[] };

export type ComponentSpecLite = {
  id: string;
  name: string;
  kind: string;
  summary: string;
  tags: string[];
};
export type PipelineStepResult = {
  component_id: string;
  run_id?: string;
  status: string;
  evidence_count?: number;
  preview?: Record<string, unknown>;
  error?: string;
};
export type PipelineResult = { steps: PipelineStepResult[]; n_rows_final: number; ok: boolean };

export type RunDetail = {
  id: string;
  status: string;
  lab: string;
  component_id: string | null;
  error: string | null;
  repro_manifest: Record<string, unknown>;
  created_at: string;
};
export type EvidenceItem = {
  id: string;
  label: string;
  kind: string;
  value: unknown;
  meta: Record<string, unknown>;
};

// ---------------- endpoint helpers ----------------
export const Api = {
  register: (email: string, password: string, full_name: string) =>
    apiPost<TokenOut>("/api/auth/register", { email, password, full_name }),
  login: (email: string, password: string) =>
    apiPost<TokenOut>("/api/auth/login", { email, password }),
  me: () => apiGet<Me>("/api/auth/me"),

  listProjects: () => apiGet<Project[]>("/api/projects"),
  createProject: (name: string, description = "") =>
    apiPost<Project>("/api/projects", { name, description }),
  getProject: (id: string) => apiGet<Project>(`/api/projects/${id}`),

  consolidate: (projectId: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return apiUpload<SignalSummary>(`/api/projects/${projectId}/signal/consolidate`, fd);
  },

  listPapers: (projectId: string) => apiGet<Paper[]>(`/api/projects/${projectId}/papers`),
  uploadPaper: (projectId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiUpload<Paper>(`/api/projects/${projectId}/papers`, fd);
  },
  getPaper: (id: string) => apiGet<Paper>(`/api/papers/${id}`),
  makeCard: (id: string, regenerate = false) =>
    apiPost<Paper>(`/api/papers/${id}/card?regenerate=${regenerate}`),
  simplify: (id: string, field: string, level: number) =>
    apiPost<{ field: string; level: number; simplified: string }>(`/api/papers/${id}/simplify`, {
      field,
      level,
    }),
  chat: (id: string, question: string) =>
    apiPost<ChatAnswer>(`/api/papers/${id}/chat`, { question }),

  listMembers: (orgId: string) => apiGet<Member[]>(`/api/orgs/${orgId}/members`),
  addMember: (orgId: string, email: string, role: string) =>
    apiPost<Member>(`/api/orgs/${orgId}/members`, { email, role }),
  setMemberRole: (orgId: string, userId: string, role: string) =>
    apiPatch<Member>(`/api/orgs/${orgId}/members/${userId}`, { role }),

  startExperiment: (paperId: string) => apiPost<Experiment>(`/api/papers/${paperId}/experiment`),
  getExperiment: (id: string) => apiGet<Experiment>(`/api/experiments/${id}`),
  uploadExperimentData: (id: string, name: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiUpload<Experiment>(
      `/api/experiments/${id}/data?name=${encodeURIComponent(name)}`,
      fd,
    );
  },
  runNode: (
    expId: string,
    nodeId: string,
    body: { dataset_id: string; component_id?: string; params?: Record<string, unknown> },
  ) => apiPost<NodeRunResult>(`/api/experiments/${expId}/nodes/${nodeId}/run`, body),

  runIdeation: (projectId: string, body: { goal: string; n?: number; evolve_n?: number }) =>
    apiPost<IdeationSession>(`/api/projects/${projectId}/ideation`, body),
  listIdeation: (projectId: string) =>
    apiGet<IdeationSession[]>(`/api/projects/${projectId}/ideation`),

  generateReport: (projectId: string) =>
    apiPost<ReportResult>(`/api/projects/${projectId}/report`),

  designQuestionnaire: (projectId: string, body: { goal: string; audience: string; n: number }) =>
    apiPost<{ questions: SurveyQuestion[] }>(
      `/api/projects/${projectId}/collection/questionnaire`, body),
  biasCheck: (projectId: string, questions: string[]) =>
    apiPost<{ findings: BiasFinding[] }>(
      `/api/projects/${projectId}/collection/bias-check`, { questions }),
  sampleSize: (
    projectId: string,
    body: { confidence: number; margin: number; population?: number | null; proportion: number },
  ) => apiPost<SampleResult>(`/api/projects/${projectId}/collection/sample-size`, body),
  pilot: (projectId: string, body: { questions: string[]; persona: string; n: number }) =>
    apiPost<PilotResult>(`/api/projects/${projectId}/collection/pilot`, body),

  getRun: (id: string) => apiGet<RunDetail>(`/api/runs/${id}`),
  getRunEvidence: (id: string) => apiGet<EvidenceItem[]>(`/api/runs/${id}/evidence`),
  listComponents: () =>
    apiGet<{ count: number; components: ComponentSpecLite[] }>("/api/components"),
  runPipeline: (
    projectId: string,
    body: {
      steps: { component_id: string; params: Record<string, unknown> }[];
      dataset?: Record<string, unknown>[] | null;
    },
  ) => apiPost<PipelineResult>(`/api/projects/${projectId}/pipeline/run`, body),

  runComponent: (
    projectId: string,
    component_id: string,
    params: Record<string, unknown>,
    dataset: Record<string, unknown>[],
  ) =>
    apiPost<RunPreview>(`/api/projects/${projectId}/runs`, { component_id, params, dataset }),
};

export type RunPreview = {
  run: { id: string; status: string; repro_manifest: Record<string, unknown> };
  evidence_count: number;
  preview: Record<string, unknown>;
};
