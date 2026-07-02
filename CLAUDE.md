# CLAUDE.md — Laboratree

Guidance for working in this repo. Laboratree is a **trustworthy, agentic, human-in-the-loop
research lab** (SaaS). See `~/.claude/plans/i-want-to-build-wondrous-steele.md` for the full plan.

## What this product is
An end-to-end research lab: raw inputs → consolidated data → understand/reproduce papers →
model (ML/DL/econometrics) → decide → report. Differentiators (the moat): **provenance-locked
results** (Evidence Ledger), **leakage detection + reproducibility**, **Co-Scientist ideation**,
**adversarial red-team critic**. Orchestrated with **LangGraph** + human-in-the-loop gates.

## Monorepo & tooling
- **uv workspace** (root `pyproject.toml`). Members: `apps/api`, `packages/plugin-sdk`.
  - `uv sync` — install everything. `uv run <cmd>` — run in the env. Python pinned to **3.12**.
- `apps/api` — FastAPI backend. `apps/web` — Next.js (npm). `infra/` — docker-compose + Dockerfiles.
- Datastores are **polyglot, one container each**: Postgres(+pgvector), Redis, Neo4j, MongoDB.
  Blobs → local volume behind `core/storage` `BlobStore` (swap to S3 later).
- LLM via `core/llm` `LLMClient` — **Azure OpenAI** (v1 route) or plain OpenAI, chosen by
  `LLM_PROVIDER`. Never hardcode model ids; read from settings.

## Run it
```bash
docker compose -f infra/docker-compose.yml up -d        # datastores + services
cd apps/api && uv run uvicorn laboratree.main:app --reload   # or run api locally
cd apps/web && npm install && npm run dev
```
Check `http://localhost:8000/health` (all stores) and `/api/components` (the registry).

## The core pattern: everything is a Component
Every Lab capability is a `Component` (see `packages/plugin-sdk/laboratree_sdk`). It declares a
`ComponentSpec` (id, kind, JSON-Schema params, ports, tags) and implements `run(ctx) -> dict`.
- Register with `@register`; it is discovered on startup by `core/registry.discover()` (walks
  `laboratree.labs.*`).
- The spec drives BOTH the agent tool list AND the frontend forms — **adding a component needs zero
  UI code**. Model variants (AR1/AR2) are the same id with different params, not new classes.
- Components touch the world only through `RunContext` (`blobs`, `evidence`, `llm`, `workdir`,
  `logger`). Report every number via `ctx.emit(...)` so it is provenance-locked.

To scaffold a new Lab/Component, use the **`laboratree-scaffold`** skill in `.claude/skills/`.

## Conventions
- Reuse mature libraries (sklearn/statsmodels/PyTorch/sktime/PyOD/ydata-profiling); agents
  orchestrate, they don't reimplement.
- Keep Labs **isolated** — a Lab is its own package under `laboratree/labs/<lab>/`; don't cross-import
  between Labs. Share only via `core/` and `plugin-sdk`.
- Curated (registered) components run in-process; the Modeling R&D loop writes/runs code in the
  **Docker sandbox** (`infra/sandbox.Dockerfile`) with no network + resource limits.
- Async everywhere in the API. Long/heavy work goes to Celery (`core/jobs`).
- Theme = **light forest** (see `apps/web/tailwind.config.ts`): forest `#14342A`, leaf `#6DB33F`,
  bg `#FBFDF9`. Serif display (Lora) + Inter. Brand reports with the logo + tagline.

## Tests
`uv run pytest` (tests live in `apps/api/tests`).
