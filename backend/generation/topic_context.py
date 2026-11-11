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

_FORM_WORDS = frozenset("explain describe define discuss compare contrast evaluate what which how why with the a an of and or is are in for to its their following neat diagram diagrams draw sketch illustrate marks mark detail detailed working principle operation construction conversion".split())

_NAMED_ANCHORS = text("""
WITH subjects AS (
 SELECT upper(value) AS subject, ordinality AS subject_order
 FROM jsonb_array_elements_text(CAST(:subjects AS jsonb)) WITH ORDINALITY
), matches AS (
 SELECT c.id::text, c.document_id::text, d.name AS document_name,
        c.content,c.page,c.heading_path,c.section,c.element_type,c.token_count,c.chunker_version,
        s.subject_order,
        row_number() OVER (PARTITION BY s.subject
          ORDER BY CASE WHEN c.element_type='heading' THEN 0 ELSE 1 END,
                   length(c.content),c.document_id,c.chunk_index,c.id) AS match_rank
 FROM document_chunks c JOIN documents d ON d.id=c.document_id
 CROSS JOIN subjects s
 WHERE d.user_id=CAST(:user_id AS uuid) AND d.status='ready'
   AND length(c.content)<=400
   AND to_tsvector('english'::regconfig,c.content) @@ plainto_tsquery('english'::regconfig,s.subject)
   AND strpos(upper(c.content),'(' || s.subject || ')')>0
)
SELECT * FROM matches WHERE match_rank<=2 ORDER BY subject_order,match_rank
""")


async def add_named_topic_anchors(db, user_id: str, question: str,
                                  seeds: Sequence[SourceChunk]) -> list[SourceChunk]:
    """Recover exact subject definitions lost by a bounded neural candidate cut.

    The lookup is lexical and owner-bound. It does not invent a cosine score or
    change the original score when a matched definition is already a seed.
    """
    subjects = sorted(topic_acronyms(question), key=lambda value: question.casefold().find(value))[:4]
    if not subjects:
        return list(seeds)
    async with db.begin_nested():
        result = await db.execute(_NAMED_ANCHORS, {"subjects": json.dumps(subjects), "user_id": str(user_id)})
        rows = result.fetchall()
    originals = {str(seed.chunk_id): seed for seed in seeds}
    anchors, seen = [], set()
    for raw in rows:
        row = dict(raw._mapping) if hasattr(raw, "_mapping") else dict(raw)
        cid = str(row["id"])
        if cid in seen:
            continue
        anchors.append(originals.get(cid) or SourceChunk(
            cid, row["content"], 0.0, str(row["document_id"]), row["document_name"], row["page"],
            heading_path=coerce_heading_path(row.get("heading_path")), section=row.get("section"),
            element_type=row.get("element_type"), token_count=row.get("token_count"),
            chunker_version=row.get("chunker_version"), retrieval_path="structural",
            structural_relation="exact-subject-heading"))
        seen.add(cid)
    return anchors + [seed for seed in seeds if str(seed.chunk_id) not in seen]


def topic_acronyms(value: str) -> set[str]:
    """Recognize a named abbreviation, including its common plural form."""
    return {match.group(1).casefold() for match in re.finditer(r"\b([A-Z][A-Z0-9]{1,})(?:s)?\b", value)
            if match.group(1).casefold() not in _FORM_WORDS}


def _normalized_terms(value: str) -> set[str]:
    value = re.sub(r"\b([A-Z][A-Z0-9]{1,})s\b", lambda match: match.group(1), value)
    return set(re.findall(r"[a-z][a-z0-9]*", value.casefold()))


def select_topic_window_subject(question: str, heading_path: Sequence[str] | None) -> str | None:
    """Only a broad request for an explicitly named definition can use a window.

    This repairs legacy layouts whose body paragraphs were all classified as
    sibling headings. Specific component questions keep exact heading scope.
    """
    path = tuple(heading_path or ())
    if len(path) < 2 or not question:
        return None
    definition = re.search(r"\(([A-Z][A-Z0-9]{1,})\)", path[-1])
    if not definition:
        return None
    subject = definition.group(1)
    title_words = _normalized_terms(path[-1][:definition.end()]) - _FORM_WORDS
    from generation.provider_prompt import student_question_plan
    _, parts = student_question_plan(question)
    for request in parts or (question,):
        request = re.split(r"[.!?]", request, maxsplit=1)[0]
        words = _normalized_terms(request) - _FORM_WORDS
        if subject.casefold() in topic_acronyms(request) and words and words <= title_words:
            return subject
    return None

_TOPICS = text(r"""
WITH requested AS (
 SELECT value::uuid AS id,
        ARRAY(SELECT jsonb_array_elements_text(COALESCE(
            CAST(:topic_paths AS jsonb)->value, '[]'::jsonb))) AS parent_labels,
        CAST(:window_subjects AS jsonb)->>value AS window_subject
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
             THEN r.parent_labels ELSE NULL END AS parent_labels,
        CASE WHEN c.heading_labels=r.parent_labels
             AND r.window_subject ~ '^[A-Z][A-Z0-9]+$'
             AND c.heading_labels[cardinality(c.heading_labels)] ~ ('\(' || r.window_subject || '\)')
             THEN r.window_subject ELSE NULL END AS window_subject
 FROM tagged c JOIN requested r ON r.id=c.id
)
SELECT s.id::text AS seed_id, c.*, s.document_id::text || ':' || bounds.lo::text || ':' ||
       bounds.hi::text || ':' || COALESCE(to_jsonb(s.parent_labels)::text,s.topic::text,'neighbour') AS group_id,
       CASE WHEN s.window_subject IS NOT NULL THEN 'section_window'
            WHEN s.topic IS NULL THEN 'neighbour'
            WHEN jsonb_typeof(s.topic)='object' THEN 'paragraph' ELSE 'section' END AS context_kind
FROM seeds s
CROSS JOIN LATERAL (
 SELECT CASE WHEN s.window_subject IS NOT NULL THEN s.chunk_index-1
             WHEN s.topic IS NULL THEN s.chunk_index-2 ELSE COALESCE(MAX(p.chunk_index)
   FILTER (WHERE p.chunk_index<s.chunk_index),-1) END AS lo,
 CASE WHEN s.window_subject IS NOT NULL THEN LEAST(s.chunk_index+32,
          COALESCE(MIN(p.chunk_index) FILTER (WHERE p.chunk_index>s.chunk_index),s.chunk_index+32))
      WHEN s.topic IS NULL THEN s.chunk_index+2 ELSE COALESCE(MIN(p.chunk_index)
   FILTER (WHERE p.chunk_index>s.chunk_index),2147483647) END AS hi
 FROM tagged p WHERE p.document_id=s.document_id AND
   CASE WHEN s.window_subject IS NOT NULL THEN p.chunk_index>s.chunk_index AND NOT (
        -- A different explicitly named definition is a hard topic boundary.
        NOT EXISTS (SELECT 1 FROM regexp_matches(p.heading_labels::text, '\(([A-Z][A-Z0-9]+)\)', 'g') other
                    WHERE other[1]<>s.window_subject)
        AND (
          p.element_type IN ('header','footer') OR p.content ~* '^\s*(\[?date\]?|module\s+[0-9]+)'
          OR p.heading_labels::text ~* ('\m' || s.window_subject || 's?\M')
          OR p.content ~* ('\m' || s.window_subject || 's?\M')
          OR (p.heading_labels[1:cardinality(s.heading_labels)-1]=s.heading_labels[1:cardinality(s.heading_labels)-1]
              AND (p.content ~ '(?:^|\n|>\s*)[0-9]{1,2}[.)]\s'
                   OR p.content ~* '\m(working|steps?|principle|conversion)\M'
                   OR p.heading_labels[cardinality(p.heading_labels)] ~* '\m(working|steps?|principle|conversion)\M'
                   OR p.content ~ U&'(\2192|->|\21D2)'))
        ))
        WHEN s.parent_labels IS NOT NULL
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
    requested_acronyms = topic_acronyms(question)
    if requested_acronyms and not requested_acronyms & _normalized_terms(" ".join(path)):
        return ()
    ignored = {"explain", "describe", "define", "discuss", "compare", "contrast", "evaluate",
               "what", "which", "how", "why", "with", "the", "a", "an", "of", "and", "or",
               "is", "are", "in", "for", "to", "its", "their", "following", "neat", "diagram",
               "diagrams", "draw", "sketch", "illustrate", "marks", "mark", "detail", "detailed"}
    def terms(text: str) -> set[str]:
        return _normalized_terms(text) - ignored
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
        acronyms = topic_acronyms(label)
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
    ids, topic_paths, window_subjects = [], {}, {}
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
                window_subject = select_topic_window_subject(question, path)
                if window_subject and selected == tuple(path or ()):
                    window_subjects[identifier] = window_subject
        except ValueError:
            continue
    if not ids:
        return list(seeds), {"status": "unavailable", "groups": 0, "completeGroups": 0,
                             "returnedChunks": len(seeds), "maxBytes": max_bytes}
    async with db.begin_nested():
        result = await db.execute(_TOPICS, {"seed_ids": json.dumps(list(dict.fromkeys(ids))),
                                          "topic_paths": json.dumps(topic_paths),
                                          "window_subjects": json.dumps(window_subjects),
                                          "user_id": str(user_id), "max_bytes": max_bytes})
        rows = result.fetchall()
    return assemble_topic_context(seeds, rows, max_bytes=max_bytes)
