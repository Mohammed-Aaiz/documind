"""Read-only owner-scoped exact/ANN recall and query-plan check.

Run from backend: python -m scripts.check_retrieval_indexes --user-id <uuid>
Uses persisted query vectors (including self matches), so these samples measure
index recall, not question/answer relevance or general retrieval quality.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid

from sqlalchemy import text

from storage.database import engine

_SEARCH = """
SELECT dc.id::text AS id FROM document_chunks dc
JOIN documents d ON d.id=dc.document_id
WHERE d.user_id=CAST(:user_id AS uuid) AND d.embedding_status='ready'
  AND dc.embedding IS NOT NULL
ORDER BY dc.embedding <=> CAST(:embedding AS vector) LIMIT :top_k
"""


def _plan_nodes(plan: dict) -> list[str]:
    nodes = [plan.get("Node Type", "") + (":" + plan["Index Name"] if "Index Name" in plan else "")]
    for child in plan.get("Plans", []):
        nodes.extend(_plan_nodes(child))
    return nodes


async def check(user_id: str, *, samples: int = 10, top_k: int = 10) -> dict:
    user_id = str(uuid.UUID(user_id))
    if not 1 <= samples <= 100 or not 1 <= top_k <= 100:
        raise ValueError("samples and top_k must each be between 1 and 100")
    async with engine.connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            await connection.execute(text("SET LOCAL statement_timeout='15s'"))
            vectors = (await connection.execute(text("""
                SELECT dc.embedding::text FROM document_chunks dc JOIN documents d ON d.id=dc.document_id
                WHERE d.user_id=CAST(:user_id AS uuid) AND d.embedding_status='ready'
                  AND dc.embedding IS NOT NULL ORDER BY dc.id LIMIT :samples
            """), {"user_id": user_id, "samples": samples})).scalars().all()
            if not vectors:
                return {"samples": 0, "status": "no_searchable_vectors"}
            params = {"user_id": user_id, "embedding": vectors[0], "top_k": top_k}
            normal_plan = (await connection.execute(text("EXPLAIN (FORMAT JSON) " + _SEARCH), params)).scalar_one()[0]["Plan"]
            await connection.execute(text("SET LOCAL enable_indexscan=off"))
            await connection.execute(text("SET LOCAL enable_bitmapscan=off"))
            exact, exact_ms = [], []
            for vector in vectors:
                params["embedding"] = vector
                started = time.perf_counter()
                exact.append(set((await connection.execute(text(_SEARCH), params)).scalars().all()))
                exact_ms.append((time.perf_counter() - started) * 1000)
            await connection.execute(text("SET LOCAL enable_indexscan=on"))
            await connection.execute(text("SET LOCAL enable_bitmapscan=on"))
            await connection.execute(text("SET LOCAL enable_seqscan=off"))
            await connection.execute(text("SET LOCAL enable_sort=off"))
            await connection.execute(text("SET LOCAL hnsw.ef_search=100"))
            await connection.execute(text("SET LOCAL hnsw.iterative_scan='strict_order'"))
            forced_plan = (await connection.execute(text("EXPLAIN (FORMAT JSON) " + _SEARCH), params)).scalar_one()[0]["Plan"]
            recall, ann_ms = [], []
            for vector, gold in zip(vectors, exact):
                params["embedding"] = vector
                started = time.perf_counter()
                found = set((await connection.execute(text(_SEARCH), params)).scalars().all())
                ann_ms.append((time.perf_counter() - started) * 1000)
                recall.append(len(found & gold) / len(gold) if gold else 0.0)
            indexes = (await connection.execute(text("""
                SELECT c.relname AS name, i.indisvalid AS valid
                FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
                JOIN pg_class t ON t.oid=i.indrelid WHERE t.relname='document_chunks'
                ORDER BY c.relname
            """))).mappings().all()
            return {"samples": len(vectors), "top_k": top_k,
                    "mean_candidate_recall": statistics.mean(recall),
                    "min_candidate_recall": min(recall),
                    "exact_mean_ms": round(statistics.mean(exact_ms), 3),
                    "forced_ann_mean_ms": round(statistics.mean(ann_ms), 3),
                    "normal_plan": _plan_nodes(normal_plan), "forced_ann_plan": _plan_nodes(forced_plan),
                    "hnsw_used": any("ix_document_chunks_embedding_hnsw" in node for node in _plan_nodes(forced_plan)),
                    "indexes": [dict(row) for row in indexes],
                    "limitations": "Persisted query vectors include self matches; forced ANN plan is diagnostic, not a production performance estimate."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=uuid.UUID)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=10)
    arguments = parser.parse_args()

    async def run():
        try:
            print(json.dumps(await check(str(arguments.user_id), samples=arguments.samples, top_k=arguments.top_k)))
        finally:
            await engine.dispose()
    asyncio.run(run())


if __name__ == "__main__":
    main()
