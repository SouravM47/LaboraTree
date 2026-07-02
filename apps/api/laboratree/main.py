"""Laboratree API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    artifacts,
    auth,
    components,
    experiments,
    gates,
    health,
    orgs,
    papers,
    projects,
    runs,
    signal,
)
from .core.config import settings
from .core.db import mongo, neo4j, postgres, redis
from .core.registry import discover

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("laboratree")


@asynccontextmanager
async def lifespan(app: FastAPI):
    count = discover()  # import all Labs -> populate the component registry
    logger.info("Laboratree API starting (env=%s, components=%d)", settings.app_env, count)
    yield
    # graceful shutdown of datastore clients
    for module in (postgres, neo4j, mongo, redis):
        try:
            await module.dispose()
        except Exception:
            logger.exception("error disposing %s", module.__name__)


app = FastAPI(
    title="Laboratree API",
    version="0.1.0",
    summary="The trustworthy, agentic, human-in-the-loop research lab.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten per-tenant in Phase 2
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(artifacts.router)
app.include_router(gates.router)
app.include_router(signal.router)
app.include_router(papers.router)
app.include_router(experiments.router)
app.include_router(components.router)


@app.get("/")
def root() -> dict:
    return {"name": "Laboratree", "tagline": "Grow · Innovate · Impact", "docs": "/docs"}
