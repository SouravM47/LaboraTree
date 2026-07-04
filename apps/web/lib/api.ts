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
export function apiDelete(path: string): Promise<void> {
  return request<void>(path, { method: "DELETE", headers: authHeaders() });
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

export type MathItem = {
  formula: string;
  plain?: string;
  symbols?: string;
  intuition?: string;
  worked_example?: string;
  example?: string; // legacy
  explanation?: string; // legacy
};
export type ProblemStatement = { one_liner: string; plain: string };
export type CardVariable = {
  name: string;
  description: string;
  example_value: string;
  type?: string;
  units?: string;
};
export type CardModel = {
  name: string;
  summary: string;
  universal?: string;
  use_case?: string;
  example?: string;
  result?: string;
  math?: MathItem[];
};
export type EmpiricalCard = {
  paper_type: "empirical";
  problem_statement: ProblemStatement;
  detailed_summary?: string;
  best_model?: string;
  models_used: CardModel[];
  data_sources: string[];
  preprocessing: string[];
  data_sample: string;
  independent_variables: CardVariable[];
  target_variable: CardVariable;
  variants: (string | { name: string; description?: string })[];
  math: MathItem[];
  results: string;
  inference: string;
};
export type Segment = { heading: string; body: string; analogy: string };
export type ConceptualCard = {
  paper_type: "conceptual";
  one_liner: string;
  problem_statement: ProblemStatement;
  segments: Segment[];
  glossary: { term: string; definition: string }[];
  takeaways: string[];
};
export type PaperCardData = EmpiricalCard | ConceptualCard;
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
  available?: boolean;              // false when the paper's model isn't a registered component
  suggested_component?: string;     // comparable stand-in to run instead
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
  synthetic?: boolean;
};
export type Unresolved = {
  name: string;
  reason: string;
  source?: string | null;
  url?: string | null;
  instructions: string;
};
export type DatasetPreview = {
  id: string;
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  n_rows: number | null;
  n_cols: number | null;
  synthetic: boolean;
  truncated: boolean;
};
export type PreprocessOp = "impute_mean" | "impute_median" | "standardize" | "minmax";
export type ColStats = { mean: number; median: number; std: number; min: number; max: number };
export type ColProfile = {
  name: string;
  dtype: "numeric" | "categorical";
  missing: number;
  missing_pct: number;
  mean?: number | null;
  std?: number | null;
  min?: number | null;
  max?: number | null;
  q25?: number | null;
  q50?: number | null;
  q75?: number | null;
  unique?: number | null;
  top?: { value: string; count: number }[] | null;
};
export type DatasetProfile = {
  n_rows: number;
  n_cols: number;
  columns: ColProfile[];
  correlation?: { columns: string[]; matrix: number[][] } | null;
};

export type TreeSplit = { feature: string; threshold: number };
export type TreeRoundRow = {
  row: number;
  feature: string;
  value: number | null;
  goes: string;
  resid_before: number;
  tree_out: number;
  resid_after: number;
};
export type LinearContribution = { feature: string; value: number; weight: number; product: number };
export type LinearSample = {
  contributions: LinearContribution[];
  sum: number;
  prediction: string;
  actual: number | string;
};
export type TreeNode = {
  leaf: boolean;
  samples: number;
  prediction?: number | string;
  confidence?: number;
  feature?: string;
  threshold?: number;
  gain?: number;
  left?: TreeNode;
  right?: TreeNode;
};
export type PathStep = { feature: string; value: number; threshold: number; go: string };
/** One candidate cut-point tried while choosing the tree's root split. */
export type SplitCandidate = { t: number; impurity: number; gain: number; n_left: number; n_right: number };
export type SplitScanFeature = {
  feature: string;
  candidates: SplitCandidate[];
  best_t: number;
  best_gain: number;
};
/** Root-split threshold scan — how the tree auditioned cut-points for its first question. */
export type SplitScan = {
  parent_impurity: number;
  features: SplitScanFeature[]; // chosen feature first, then the best runners-up
  chosen_feature: string;
};
export type TestRow = {
  values: Record<string, number>;
  predicted: number | string;
  actual: number | string | null;
  correct?: boolean | null;
  error?: number | null;
  path?: PathStep[]; // trees
  contributions?: LinearContribution[]; // linear + timeseries (lags × φ)
  sum?: number;
  score?: number | null; // linear probability · anomaly score
  input?: number[]; // nn
  hidden?: number[];
  output?: number;
  x?: number; // knn/clustering/anomaly — position on the 2-D map
  y?: number;
  neighbors?: { x: number; y: number; label: number | string; distance: number }[]; // knn
  distances?: { cluster: string; distance: number }[]; // clustering
  rounds?: { path: PathStep[]; value: number }[]; // boosting: per-round leaf contribution
  boost_score?: number; // baseline + Σ tree outputs
  boost_prob?: number; // sigmoid(boost_score) for classification
  boost_pred?: number | string;
};
export type ScatterPoint = { x: number; y: number; label: number | string };
export type ModelTrace = {
  family: string;
  target: string;
  task: string;
  features: string[];
  labels?: string[] | null;
  table?: Record<string, number | string>[] | null;
  tree?: TreeNode | null;
  baseline?: number | null;
  rounds?: { tree: TreeNode }[] | null; // boosting ensemble: one small tree per round
  scan?: SplitScan | null; // trees — animated "how a split is chosen" threshold scan
  intercept?: number | null;
  coef?: { feature: string; weight: number }[] | null;
  samples?: LinearSample[] | null;
  layers?: number[] | null;
  forward?: {
    input: number[];
    input_names: string[];
    hidden: number[];
    output: number;
    w1?: number[][]; // learned weights: shown-inputs × hidden
    w2?: number[]; // hidden → output
  } | null;
  points?: ScatterPoint[] | null; // knn/clustering/anomaly — 2-D map of training rows
  series?: Record<string, unknown> | null; // family extras (axes, k, AR coefs, history…)
  test_rows?: TestRow[] | null;
  param_spec?: ParamSpec[] | null; // tunable hyperparameters the UI renders (with live values)
  params?: Record<string, number | string> | null; // the values used to fit
  note: string;
};
export type ParamSpec = {
  key: string;
  label: string;
  type: "int" | "float" | "select";
  value: number | string;
  default: number | string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  help?: string;
};
export type FSHabitat = { selected: string[]; fitness: number };
export type FSGeneration = { habitats: FSHabitat[]; best_fitness: number };
export type FeatureSelectionTrace = {
  target: string;
  task: string;
  features: string[];
  importances: { feature: string; importance: number }[];
  generations: FSGeneration[];
  selected: string[];
  best_fitness: number;
  note: string;
};
export type PreprocessPreview = {
  op: PreprocessOp;
  columns: string[];
  before: Record<string, unknown>[];
  after: Record<string, unknown>[];
  changed: string[][];
  stats: Record<string, ColStats>;
  summary: string;
};
export type Experiment = {
  id: string;
  paper_id: string;
  status: string;
  walkthrough: WalkNode[];
  fetch_report: { run_id?: string; fetched: FetchedDataset[]; unresolved: Unresolved[] };
  gate_id?: string | null;
};
export type Prediction = { actual: number | string; predicted: number | string };
export type NodeRunResult = {
  run_id: string;
  component_id: string;
  forked: boolean;
  metrics: Record<string, number>;
  task?: string;
  predictions?: Prediction[];
  paper_reported: string;
  synthetic?: boolean;
  stand_in?: boolean;               // paper's model wasn't available; a comparable one was run
};

export type LlmCall = {
  id: string;
  lab: string;
  operation: string;
  provider: string;
  model: string;
  role: string;
  total_tokens: number;
  latency_ms: number;
  cost_usd: number | null;
  status: string;
  created_at: string;
};
export type LlmSummary = {
  by_lab: { lab: string; calls: number; tokens: number; cost_usd: number; avg_latency_ms: number }[];
  totals: { calls: number; tokens: number; cost_usd: number };
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

export type EvidenceSource = {
  title: string;
  url: string;
  snippet: string;
  provider?: string;
  query?: string;
};
export type TestVariable = {
  name: string;
  role: "independent" | "target" | "control" | string;
  rationale?: string;
};
export type EvidenceBrief = {
  summary: string;
  stance: "supports" | "refutes" | "mixed" | "inconclusive" | string;
  confidence?: number;
  key_findings: { finding: string; sources?: number[] }[];
  insights: string[];
  variables_to_test: TestVariable[];
  gaps: string[];
};
export type EvidenceResult = {
  hypothesis: string;
  queries: string[];
  sources: EvidenceSource[];
  brief: EvidenceBrief;
};
export type ChatTurn = { role: "user" | "assistant"; content: string };

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
  deleteProject: (id: string) => apiDelete(`/api/projects/${id}`),

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
  deletePaper: (id: string) => apiDelete(`/api/papers/${id}`),
  makeCard: (id: string, regenerate = false) =>
    apiPost<Paper>(`/api/papers/${id}/card?regenerate=${regenerate}`),
  simplify: (id: string, body: { field?: string; text?: string; level: number }) =>
    apiPost<{ field: string; level: number; simplified: string }>(
      `/api/papers/${id}/simplify`, body),
  chat: (id: string, question: string) =>
    apiPost<ChatAnswer>(`/api/papers/${id}/chat`, { question }),

  listMembers: (orgId: string) => apiGet<Member[]>(`/api/orgs/${orgId}/members`),
  addMember: (orgId: string, email: string, role: string) =>
    apiPost<Member>(`/api/orgs/${orgId}/members`, { email, role }),
  setMemberRole: (orgId: string, userId: string, role: string) =>
    apiPatch<Member>(`/api/orgs/${orgId}/members/${userId}`, { role }),

  startExperiment: (paperId: string) => apiPost<Experiment>(`/api/papers/${paperId}/experiment`),
  latestExperiment: (paperId: string) =>
    apiGet<Experiment>(`/api/papers/${paperId}/experiment`).catch((e) => {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }),
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
  demoData: (expId: string) =>
    apiPost<Experiment & { caveat: string }>(`/api/experiments/${expId}/demo-data`),
  datasetPreview: (datasetId: string, rows = 50) =>
    apiGet<DatasetPreview>(`/api/datasets/${datasetId}/preview?rows=${rows}`),
  datasetProfile: (datasetId: string) =>
    apiGet<DatasetProfile>(`/api/datasets/${datasetId}/profile`),
  modelTrace: (
    datasetId: string,
    target: string,
    family: string,
    params?: Record<string, number | string>,
  ) =>
    apiPost<ModelTrace>(
      `/api/datasets/${datasetId}/model-trace?target=${encodeURIComponent(target)}&family=${family}`,
      { params: params ?? {} },
    ),
  featureSelection: (datasetId: string, target: string) =>
    apiPost<FeatureSelectionTrace>(
      `/api/datasets/${datasetId}/feature-selection?target=${encodeURIComponent(target)}`,
    ),
  downloadDataset: (datasetId: string, filename: string) =>
    downloadBlob(`/api/datasets/${datasetId}/download`, filename),
  preprocessPreview: (datasetId: string, op: PreprocessOp, rows = 6) =>
    apiPost<PreprocessPreview>(
      `/api/datasets/${datasetId}/preprocess-preview?op=${op}&rows=${rows}`,
    ),

  llmSummary: (projectId: string) => apiGet<LlmSummary>(`/api/projects/${projectId}/llm/summary`),
  llmCalls: (projectId: string) => apiGet<LlmCall[]>(`/api/projects/${projectId}/llm/calls`),

  runIdeation: (projectId: string, body: { goal: string; n?: number; evolve_n?: number }) =>
    apiPost<IdeationSession>(`/api/projects/${projectId}/ideation`, body),
  listIdeation: (projectId: string) =>
    apiGet<IdeationSession[]>(`/api/projects/${projectId}/ideation`),
  evidenceHunt: (projectId: string, hypothesis: string, maxSources = 12) =>
    apiPost<EvidenceResult>(`/api/projects/${projectId}/ideation/evidence`, {
      hypothesis,
      max_sources: maxSources,
    }),
  brainstorm: (
    projectId: string,
    payload: {
      hypothesis: string;
      brief: EvidenceBrief;
      sources: EvidenceSource[];
      question: string;
      history: ChatTurn[];
    },
  ) => apiPost<{ answer: string }>(`/api/projects/${projectId}/ideation/brainstorm`, payload),

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
