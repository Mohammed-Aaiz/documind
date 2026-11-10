"""Recover document topic context after small-chunk retrieval.

Sections are contiguous ranges in one authenticated owner's document. Repeated
headings in a later range never get joined to a previous topic. Persisted source
element membership recovers unheaded paragraphs; unknown metadata permits only
a labelled neighbour window, never a claim of completeness.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import replace
from typing import Any, Sequence

from sqlalchemy import text

from chat.rag import SourceChunk, coerce_heading_path

MAX_CONTEXT_BYTES = 128_000

_TOPICS = text("""
WITH requested AS (
 SELECT value::uuid AS id,
        ARRAY(SELECT jsonb_array_elements_text(COALESCE(
            CAST(:topic_paths AS jsonb)->value, '[]'::jsonb))) AS parent_labels
 FROM jsonb_array_elements_text(CAST(:seed_ids AS jsonb))
), owned AS (
 SELECT c.id,c.document_id,c.chunk_index,c.content,c.page,c.heading_path,c.section,
        c.element_type,c.token_count,c.chunker_version,
        CASE WHEN jsonb_typeof(c.heading_path::jsonb)='array'
             THEN c.heading_path::jsonb ELSE '[]'::jsonb END AS headings,
        CASE WHEN jsonb_typeof(c.source_element_indices::jsonb)='array'
             THEN c.source_element_indices::jsonb ELSE '[]'::jsonb END AS elements
 FROM document_chunks c JOIN documents d ON d.id=c.document_id
 WHERE d.user_id=CAST(:user_id AS uuid) AND c.document_id IN
       (SELECT p.document_id FROM document_chunks p JOIN requested r ON r.id=p.id)
), tagged AS (
 SELECT c.*, ARRAY(SELECT jsonb_array_elements_text(headings)) AS heading_labels,
        CASE WHEN jsonb_array_length(headings)>0 THEN headings
                  WHEN NULLIF(section,'') IS NOT NULL THEN jsonb_build_array(section)
                  WHEN jsonb_array_length(elements)>0 AND NOT EXISTS
                    (SELECT 1 FROM jsonb_array_elements(elements) e
                     WHERE jsonb_typeof(e.value)<>'number' OR e.value::text !~ '^[0-9]+$')
                    THEN jsonb_build_object('paragraph', elements)
                  ELSE NULL END AS topic
 FROM owned c
), seeds AS (
 SELECT c.*, CASE WHEN cardinality(r.parent_labels)>0
             AND c.heading_labels[1:cardinality(r.parent_labels)]=r.parent_labels
             THEN r.parent_labels ELSE NULL END AS parent_labels
 FROM tagged c JOIN requested r ON r.id=c.id
)
SELECT s.id::text AS seed_id, c.*, s.document_id::text || ':' || bounds.lo::text || ':' ||
       bounds.hi::text || ':' || COALESCE(to_jsonb(s.parent_labels)::text,s.topic::text,'neighbour') AS group_id,
       CASE WHEN s.topic IS NULL THEN 'neighbour'
            WHEN jsonb_typeof(s.topic)='object' THEN 'paragraph' ELSE 'section' END AS context_kind
FROM seeds s
CROSS JOIN LATERAL (
 SELECT CASE WHEN s.topic IS NULL THEN s.chunk_index-2 ELSE COALESCE(MAX(p.chunk_index)
   FILTER (WHERE p.chunk_index<s.chunk_index),-1) END AS lo,
 CASE WHEN s.topic IS NULL THEN s.chunk_index+2 ELSE COALESCE(MIN(p.chunk_index)
   FILTER (WHERE p.chunk_index>s.chunk_index),2147483647) END AS hi
 FROM tagged p WHERE p.document_id=s.document_id AND
   CASE WHEN s.parent_labels IS NOT NULL
        THEN p.heading_labels[1:cardinality(s.parent_labels)] IS DISTINCT FROM s.parent_labels
        ELSE p.topic IS DISTINCT FROM s.topic END
) bounds
CROSS JOIN LATERAL (
 SELECT bounded.* FROM (
   SELECT p.id, p.content, p.page, p.heading_path, p.section, p.element_type,
          p.token_count, p.chunker_version, p.chunk_index,
          SUM(octet_length(p.content)) OVER () AS total_bytes,
          SUM(octet_length(p.content)) OVER (ORDER BY p.chunk_index,p.id) AS cumulative_bytes
   FROM tagged p WHERE p.document_id=s.document_id
       AND p.chunk_index>bounds.lo AND p.chunk_index<bounds.hi
 ) bounded WHERE cumulative_bytes<=:max_bytes OR bounded.id=s.id
) c
ORDER BY s.id, c.chunk_index, c.id
""")


def select_topic_heading_path(question: str, heading_path: Sequence[str] | None) -> tuple[str, ...]:
    """Recover a named parent topic, not an unrelated chapter or generic term.

    Some parsers store each working step as a leaf heading. For a question about
    its parent, that exact leaf alone loses the rest of the process. Explicit
    topic words (or an acronym) select the best matching heading; a more
    specific leaf wins over its ancestor. An empty result keeps exact legacy
    matching. SQL bounds any selected prefix to one contiguous occurrence.
    """
    path = tuple(heading_path or ())
    if not path or not question:
        return ()
    ignored = {"explain", "describe", "define", "discuss", "compare", "contrast", "evaluate",
               "what", "which", "how", "why", "with", "the", "a", "an", "of", "and", "or",
               "is", "are", "in", "for", "to", "its", "their", "following", "neat", "diagram",
               "diagrams", "draw", "sketch", "illustrate", "marks", "mark", "detail", "detailed"}
    def terms(text: str) -> set[str]:
        return set(re.findall(r"[a-z][a-z0-9]*", text.casefold())) - ignored
    query_terms = terms(question)
    if not query_terms:
        return ()
    matches = []
    prefix_terms: set[str] = set()
    for depth, label in enumerate(path, 1):
        label_terms = terms(label)
        prefix_terms.update(label_terms)
        overlap = query_terms & label_terms
        prefix_overlap = query_terms & prefix_terms
        acronyms = {value.casefold() for value in re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", label)}
        # Topic words can be split across labels (Energy > Wind > Steps).
        # Prefer the label's own subject match. A leaf that repeats only part
        # of the question must not beat its full-topic parent through inheritance.
        if overlap and (len(prefix_overlap) >= 2 or overlap & acronyms or label_terms == query_terms):
            matches.append((len(overlap), len(prefix_overlap), depth))
    if not matches:
        return ()
    return path[:max(matches)[2]]


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
        # A parent and a narrower seed can overlap. Already emitted passages
        # still cover this range; deduplication must not report them as missing.
        included = sum(len(str(row["content"]).encode("utf-8"))
                       for row in matches if str(row["id"]) in seen)
        total = int(matches[0]["total_bytes"])
        kind = str(matches[0]["context_kind"])
        complete = kind in ("section", "paragraph") and included >= total
        groups[group_id] = complete
        output.extend(replace(source, topic_context_id=group_id, topic_context_complete=complete,
                              topic_context_kind=kind) for source in group)
    complete_count = sum(groups.values())
    status = "complete" if groups and complete_count == len(groups) and not missing else "partial" if groups else "unavailable"
    return output, {"status": status, "groups": len(groups), "completeGroups": complete_count,
                    "returnedChunks": len(output), "maxBytes": max_bytes}


async def expand_topic_context(db, user_id: str, seeds: Sequence[SourceChunk], *,
                               question: str = "",
                               max_bytes: int = MAX_CONTEXT_BYTES) -> tuple[list[SourceChunk], dict]:
    """Fetch candidate sections in one database round trip, bounded by bytes."""
    ids, topic_paths = [], {}
    for seed in seeds:
        if getattr(seed, "evidence_kind", "chunk") != "chunk":
            continue
        try:
            identifier = str(uuid.UUID(str(seed.chunk_id)))
            ids.append(identifier)
            path = coerce_heading_path(getattr(seed, "heading_path", None))
            selected = select_topic_heading_path(question, path)
            if selected:
                topic_paths[identifier] = selected
        except ValueError:
            continue
    if not ids:
        return list(seeds), {"status": "unavailable", "groups": 0, "completeGroups": 0,
                             "returnedChunks": len(seeds), "maxBytes": max_bytes}
    async with db.begin_nested():
        result = await db.execute(_TOPICS, {"seed_ids": json.dumps(list(dict.fromkeys(ids))),
                                          "topic_paths": json.dumps(topic_paths),
                                          "user_id": str(user_id), "max_bytes": max_bytes})
        rows = result.fetchall()
    return assemble_topic_context(seeds, rows, max_bytes=max_bytes)
