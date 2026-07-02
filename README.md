<div align="center">
  <img src="logo/logo.PNG" alt="Laboratree" width="240" />
  <h1>Laboratree</h1>
  <p><em>Grow · Innovate · Impact</em></p>
  <p>The trustworthy, agentic, human-in-the-loop research lab.</p>
</div>

---

Laboratree is an end-to-end, multi-agent research lab covering the full lifecycle of
primary/secondary data research — from messy raw inputs to consolidated data, to understanding and
reproducing research papers, to modelling (ML / DL / econometrics), all with **provenance-locked,
reproducible** results and **human-in-the-loop** control.

See the foundation plan for the full architecture and rationale.

## Monorepo

```
apps/api          FastAPI backend (uv workspace member)
apps/web          Next.js frontend
packages/plugin-sdk   Component / registry contracts (uv workspace member)
infra             docker-compose + Dockerfiles
data              local BlobStore volume (gitignored)
```

## Tech

- **Backend:** FastAPI (Python 3.12, managed by **uv**), LangGraph agent orchestration, Celery.
- **Frontend:** Next.js / React, React Flow, dnd-kit.
- **Persistence (dedicated containers):** Postgres (+pgvector), Redis, Neo4j, MongoDB. Blobs on a
  local volume behind a `BlobStore` interface.
- **LLMs:** OpenAI (pluggable `LLMClient`).

## Quick start (dev)

```bash
# 1. Bring up the datastores + services
cp .env.example .env            # then fill in OPENAI_API_KEY
docker compose -f infra/docker-compose.yml up -d

# 2. Backend (local, without Docker) — uses uv
cd apps/api
uv sync                          # creates .venv, installs workspace deps
uv run uvicorn laboratree.main:app --reload

# 3. Frontend
cd apps/web
npm install && npm run dev
```

Health check: <http://localhost:8000/health> reports connectivity to every datastore.
