# Laboratree API image — Python 3.12 (ML-wheel compatible), managed by uv.
# Build context is the repo root (see docker-compose).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy workspace sources (manifests + code) and resolve the environment.
COPY pyproject.toml ./
COPY packages ./packages
COPY apps/api ./apps/api

RUN uv sync --no-dev

WORKDIR /app/apps/api
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "laboratree.main:app", "--host", "0.0.0.0", "--port", "8000"]
