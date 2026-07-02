"""Celery app — async execution of agent runs, pipelines, and heavy Lab work.

Broker + result backend are Redis. Task modules are added as Labs/agents come online.
"""

from __future__ import annotations

from celery import Celery

from .config import settings

celery_app = Celery(
    "laboratree",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="laboratree.ping")
def ping() -> str:
    """Trivial task used to verify the worker is wired up."""
    return "pong"
