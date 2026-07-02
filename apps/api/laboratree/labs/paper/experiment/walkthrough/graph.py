"""Mirror a walkthrough into Neo4j as a node graph (best-effort; never fatal)."""

from __future__ import annotations

import uuid
from typing import Any


async def mirror_to_neo4j(
    experiment_id: uuid.UUID, org_id: uuid.UUID, steps: list[dict[str, Any]]
) -> bool:
    """Write (:Experiment)-[:HAS_NODE]->(:Node)-[:NEXT]->(:Node). Returns True on success."""
    try:
        from ....core.db.neo4j import driver

        eid = str(experiment_id)
        async with driver().session() as s:
            await s.run(
                "MERGE (e:Experiment {id:$eid}) SET e.org_id=$org", eid=eid, org=str(org_id)
            )
            prev: str | None = None
            for n in steps:
                nid = n["id"]
                await s.run(
                    "MERGE (x:Node {id:$nid, experiment:$eid}) "
                    "SET x.kind=$kind, x.title=$title, x.component_id=$cid",
                    nid=nid, eid=eid, kind=n.get("kind", ""), title=n.get("title", ""),
                    cid=n.get("component_id"),
                )
                await s.run(
                    "MATCH (e:Experiment {id:$eid}),(x:Node {id:$nid, experiment:$eid}) "
                    "MERGE (e)-[:HAS_NODE]->(x)",
                    eid=eid, nid=nid,
                )
                if prev is not None:
                    await s.run(
                        "MATCH (a:Node {id:$a, experiment:$eid}),(b:Node {id:$b, experiment:$eid}) "
                        "MERGE (a)-[:NEXT]->(b)",
                        a=prev, b=nid, eid=eid,
                    )
                prev = nid
        return True
    except Exception:
        return False
