"""Recover document topic context after small-chunk retrieval.

Sections are contiguous ranges in one authenticated owner's document. Repeated
headings in a later range never get joined to a previous topic. Missing section
metadata permits only a labelled neighbour window, never a claim of completeness.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any, Sequence

from sqlalchemy import text

from chat.rag import SourceChunk, coerce_heading_path

MAX_CONTEXT_BYTES = 128_000

_TOPICS = text("""
WITH requested AS (
 SELECT value::uuid AS id FROM jsonb_array_elements_text(CAST(:seed_ids AS jsonb))
), seeds AS (
 SELECT c.*, CASE WHEN jsonb_array_length(CASE WHEN jsonb_typeof(c.heading_path::jsonb)='array' THEN c.heading_path::jsonb ELSE '[]'::jsonb END)>0
                  THEN c.heading_path::jsonb
                  WHEN NULLIF(c.section,'') IS NOT NULL THEN jsonb_build_array(c.section)
                  ELSE NULL END AS topic
 FROM document_chunks c JOIN requested r ON r.id=c.id
 JOIN documents d ON d.id=c.document_id WHERE d.user_id=CAST(:user_id AS uuid)
)
SELECT s.id::text AS seed_id, c.*, s.document_id::text || ':' || bounds.lo::text AS group_id,
       CASE WHEN s.topic IS NULL THEN 'neighbour' ELSE 'section' END AS context_kind
FROM seeds s
CROSS JOIN LATERAL (
 SELECT CASE WHEN s.topic IS NULL THEN s.chunk_index-2 ELSE COALESCE(MAX(p.chunk_index)
   FILTER (WHERE p.chunk_index<s.chunk_index),-1) END AS lo,
 CASE WHEN s.topic IS NULL THEN s.chunk_index+2 ELSE COALESCE(MIN(p.chunk_index)
   FILTER (WHERE p.chunk_index>s.chunk_index),2147483647) END AS hi
 FROM document_chunks p WHERE p.document_id=s.document_id AND
   (CASE WHEN jsonb_array_length(CASE WHEN jsonb_typeof(p.heading_path::jsonb)='array' THEN p.heading_path::jsonb ELSE '[]'::jsonb END)>0 THEN p.heading_path::jsonb
         WHEN NULLIF(p.section,'') IS NOT NULL THEN jsonb_build_array(p.section)
         ELSE NULL END) IS DISTINCT FROM s.topic
) bounds
CROSS JOIN LATERAL (
 SELECT bounded.* FROM (
   SELECT p.id, p.content, p.page, p.heading_path, p.section, p.element_type,
          p.token_count, p.chunker_version, p.chunk_index,
          SUM(octet_length(p.content)) OVER () AS total_bytes,
          SUM(octet_length(p.content)) OVER (ORDER BY p.chunk_index,p.id) AS cumulative_bytes
   FROM document_chunks p WHERE p.document_id=s.document_id
       AND p.chunk_index>bounds.lo AND p.chunk_index<bounds.hi
 ) bounded WHERE cumulative_bytes<=:max_bytes OR bounded.id=s.id
) c
ORDER BY s.id, c.chunk_index, c.id
""")


def assemble_topic_context(seeds: Sequence[SourceChunk], rows: Sequence[Any], *,
                           max_bytes: int = MAX_CONTEXT_BYTES) -> tuple[list[SourceChunk], dict]:
    """Assemble exact chunks with their original identities and per-group coverage."""
    by_seed: dict[str, list] = {}
    for raw in rows:
        row = dict(raw._mapping) if hasattr(raw, "_mapping") else dict(raw)
        by_seed.setdefault(str(row["seed_id"]), []).append(row)
    originals = {str(seed.chunk_id): seed for seed in seeds}
    output, seen, groups = [], set(), {}
    used_bytes = 0
    missing = 0
    for seed in seeds:
        matches = by_seed.get(str(seed.chunk_id), [])
        if not matches:
            missing += 1
            if str(seed.chunk_id) not in seen:
                output.append(seed)
                seen.add(str(seed.chunk_id))
            continue
        group_id = str(matches[0]["group_id"])
        if group_id in groups:
            if str(seed.chunk_id) not in seen:
                output.append(replace(seed, topic_context_id=group_id, topic_context_complete=False,
                                      topic_context_kind=str(matches[0]["context_kind"])))
                seen.add(str(seed.chunk_id))
                groups[group_id] = False
            continue
        group = []
        for row in matches:
            cid = str(row["id"])
            if cid in seen:
                continue
            size = len(str(row["content"]).encode("utf-8"))
            # Matched seeds always survive the bound; expansion is optional.
            if used_bytes + size > max_bytes and cid not in originals:
                continue
            original = originals.get(cid)
            source = original if original is not None else SourceChunk(
                cid, row["content"], seed.score, seed.document_id, seed.document_name, row["page"],
                heading_path=coerce_heading_path(row.get("heading_path")), section=row.get("section"),
                element_type=row.get("element_type"), token_count=row.get("token_count"),
                chunker_version=row.get("chunker_version"), retrieval_path="section")
            group.append(source)
            seen.add(cid)
            used_bytes += size
        included = sum(len(source.content.encode("utf-8")) for source in group)
        total = int(matches[0]["total_bytes"])
        kind = str(matches[0]["context_kind"])
        complete = kind == "section" and included >= total
        groups[group_id] = complete
        output.extend(replace(source, topic_context_id=group_id, topic_context_complete=complete,
                              topic_context_kind=kind) for source in group)
    complete_count = sum(groups.values())
    status = "complete" if groups and complete_count == len(groups) and not missing else "partial" if groups else "unavailable"
    return output, {"status": status, "groups": len(groups), "completeGroups": complete_count,
                    "returnedChunks": len(output), "maxBytes": max_bytes}


async def expand_topic_context(db, user_id: str, seeds: Sequence[SourceChunk], *,
                               max_bytes: int = MAX_CONTEXT_BYTES) -> tuple[list[SourceChunk], dict]:
    """Fetch candidate sections in one database round trip, bounded by bytes."""
    ids = []
    for seed in seeds:
        if getattr(seed, "evidence_kind", "chunk") != "chunk":
            continue
        try:
            ids.append(str(uuid.UUID(str(seed.chunk_id))))
        except ValueError:
            continue
    if not ids:
        return list(seeds), {"status": "unavailable", "groups": 0, "completeGroups": 0,
                             "returnedChunks": len(seeds), "maxBytes": max_bytes}
    async with db.begin_nested():
        result = await db.execute(_TOPICS, {"seed_ids": json.dumps(list(dict.fromkeys(ids))),
                                          "user_id": str(user_id), "max_bytes": max_bytes})
        rows = result.fetchall()
    return assemble_topic_context(seeds, rows, max_bytes=max_bytes)
