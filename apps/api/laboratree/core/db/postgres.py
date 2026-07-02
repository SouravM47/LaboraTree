"""Postgres (+pgvector) — transactional source of truth + LangGraph checkpointer + embeddings."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from ..config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # NullPool: don't cache connections across event loops (safe for TestClient/ASGI portals
        # and dev). Put a real pool (or pgbouncer) in front for production throughput.
        _engine = create_async_engine(settings.postgres_dsn, poolclass=NullPool, future=True)
    return _engine


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session and closes it."""
    async with sessionmaker()() as session:
        yield session


async def ping() -> None:
    async with engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
