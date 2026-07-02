"""Neo4j — graph store for walkthrough DAGs, provenance/lineage, and paper knowledge graphs."""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from ..config import settings

_driver: AsyncDriver | None = None


def driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def ping() -> None:
    await driver().verify_connectivity()


async def dispose() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
