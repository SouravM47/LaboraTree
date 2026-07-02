"""MongoDB — document store for parsed papers, extraction blocks, and agent traces."""

from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from ..config import settings

_client: AsyncMongoClient | None = None


def client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(settings.mongo_uri)
    return _client


def db() -> AsyncDatabase:
    return client()[settings.mongo_db]


async def ping() -> None:
    await client().admin.command("ping")


async def dispose() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
