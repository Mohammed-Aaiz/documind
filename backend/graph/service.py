"""Document-native structural graph: construction and traversal.

What this is
------------
Edges are **derived from the document's own structure** — reading order, page
number and heading path — at ingestion time, and stored as ordinary relational
rows.  It is a *structure* graph, not a knowledge graph:

* no language model extracts triples,
* no external graph database is required,
* no entity resolution or semantic edge inference happens anywhere.

Relations and weights
---------------------
=============== ====== ====================================================
Relation        Weight Meaning
=============== ====== ====================================================
``NEXT``         1.0   next chunk in document order
``PREV``         1.0   previous chunk in document order
``SAME_PAGE``    0.7   consecutive chunks on the same page
``SAME_SECTION`` 0.5   chunks under the same ``heading_path``
=============== ====== ====================================================

Scoring
-------
``structural_score = relation_weight / (1 + hops)``, with hop 0 (a seed found
by heading/section term matching, or a semantic seed) scoring ``1.0``.  This is
**not** a similarity and is never reported as one: it is a graph-distance
score.  Where a chunk is reachable by several paths, the shortest hop count
wins and ties at the same hop are broken by the larger relation weight (the
breadth-first walk therefore never explores a longer path when a shorter one
exists).

Isolation
---------
Every traversal statement joins ``edge -> chunk -> document`` and filters on
``documents.user_id``; ownership is never taken from the caller's chunk ids.
A user can therefore only ever traverse their own graph, and cross-document
expansion is impossible because edges are per-document (``document_id``).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sqlalchemy import Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import Document, DocumentChunk, DocumentTableRow
from graph.models import (
    RELATION_PARENT_OF,
    DocumentGraphEdge,
    DocumentStructureElement,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

RELATION_NEXT = "NEXT"
RELATION_PREV = "PREV"
RELATION_SAME_PAGE = "SAME_PAGE"
RELATION_SAME_SECTION = "SAME_SECTION"

RELATIONS: tuple[str, ...] = (
    RELATION_NEXT,
    RELATION_PREV,
    RELATION_SAME_PAGE,
    RELATION_SAME_SECTION,
)

RELATION_WEIGHTS: dict[str, float] = {
    RELATION_NEXT: 1.0,
    RELATION_PREV: 1.0,
    RELATION_SAME_PAGE: 0.7,
    RELATION_SAME_SECTION: 0.5,
}

#: Maximum graph hops for structural expansion (the spec's bound: 2).
MAX_HOPS = 2

#: Window (in document order) inside one heading path.  Chunks closer than this
#: are linked by ``SAME_SECTION`` so a section is navigable; the window is what
#: keeps a long section from becoming a dense clique.
SECTION_NEIGHBOURHOOD = 2

#: Hard cap on nodes materialised by one expansion, so a pathological document
#: cannot turn a question into an unbounded traversal.
MAX_NODES = 40

#: Default relation weight used when a row somehow carries none.
DEFAULT_WEIGHT = 1.0


# ---------------------------------------------------------------------------
# Views / specs (pure data, so edge planning is unit-testable without a DB)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChunkView:
    """The structural fields of one chunk, in document order."""

    chunk_id: str
    index: int
    page: int | None
    heading_path: tuple[str, ...] | None


@dataclass(frozen=True)
class EdgeSpec:
    """One planned edge, before it is persisted."""

    source_chunk_id: str
    target_chunk_id: str
    relation: str
    weight: float


@dataclass
class StructuralCandidate:
    """One chunk reached by the structural path, with its provenance."""

    chunk_id: str
    content: str
    document_id: str
    document_name: str
    page: int | None
    heading_path: tuple[str, ...] | None
    section: str | None
    element_type: str | None
    token_count: int | None
    chunker_version: str | None
    hops: int
    relation: str | None
    structural_score: float
    matched_terms: tuple[str, ...] = field(default=())


# ---------------------------------------------------------------------------
# Edge planning (pure)
# ---------------------------------------------------------------------------

def _norm_path(path: Sequence[str] | str | None) -> tuple[str, ...] | None:
    """Normalise a heading path to a comparable tuple of non-empty strings."""
    if path is None:
        return None
    if isinstance(path, str):
        parts = [p.strip() for p in path.split(">")]
    else:
        parts = [str(p).strip() for p in path]
    cleaned = tuple(p for p in parts if p)
    return cleaned or None


def plan_edges(chunks: Sequence[ChunkView]) -> list[EdgeSpec]:
    """Plan every structural edge for an ordered chunk list.

    Pure and deterministic.  Guarantees:

    * no self edges,
    * no duplicate ``(source, target, relation)`` triples,
    * page adjacency only between consecutive chunks that actually share a page,
    * section adjacency only between chunks with an identical non-empty heading
      path, within :data:`SECTION_NEIGHBOURHOOD`.
    """
    spans: list[tuple[ChunkView, tuple[str, ...] | None]] = [
        (c, _norm_path(c.heading_path)) for c in chunks
    ]

    seen: set[tuple[str, str, str]] = set()
    out: list[EdgeSpec] = []

    def add(src: str, dst: str, relation: str) -> None:
        if src == dst:
            return
        key = (str(src), str(dst), relation)
        if key in seen:
            return
        seen.add(key)
        out.append(
            EdgeSpec(
                source_chunk_id=str(src),
                target_chunk_id=str(dst),
                relation=relation,
                weight=RELATION_WEIGHTS[relation],
            )
        )

    for i in range(len(spans) - 1):
        cur, cur_path = spans[i]
        nxt, nxt_path = spans[i + 1]

        add(cur.chunk_id, nxt.chunk_id, RELATION_NEXT)
        add(nxt.chunk_id, cur.chunk_id, RELATION_PREV)

        if cur.page is not None and nxt.page is not None and cur.page == nxt.page:
            add(cur.chunk_id, nxt.chunk_id, RELATION_SAME_PAGE)
            add(nxt.chunk_id, cur.chunk_id, RELATION_SAME_PAGE)

        if cur_path is not None and cur_path == nxt_path:
            add(cur.chunk_id, nxt.chunk_id, RELATION_SAME_SECTION)
            add(nxt.chunk_id, cur.chunk_id, RELATION_SAME_SECTION)

    # Nearby chunks inside one heading path, wider than the immediate neighbour
    # but bounded, so the section stays a path rather than a clique.
    for i, (cur, cur_path) in enumerate(spans):
        if cur_path is None:
            continue
        for gap in range(2, SECTION_NEIGHBOURHOOD + 1):
            j = i + gap
            if j >= len(spans):
                break
            other, other_path = spans[j]
            if other_path == cur_path:
                add(cur.chunk_id, other.chunk_id, RELATION_SAME_SECTION)
                add(other.chunk_id, cur.chunk_id, RELATION_SAME_SECTION)

    return out


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _as_uuid(value: object):
    """Best-effort UUID coercion; returns the input unchanged if impossible."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return value


async def delete_document_graph(db: AsyncSession, document_id) -> int:
    """Remove every edge belonging to ``document_id``.  Returns rows deleted."""
    result = await db.execute(
        delete(DocumentGraphEdge).where(
            DocumentGraphEdge.document_id == _as_uuid(document_id)
        )
    )
    return int(result.rowcount or 0)


async def replace_document_graph(
    db: AsyncSession,
    document_id,
    chunks: Sequence[ChunkView],
) -> int:
    """Delete then rebuild one document's graph.  Returns the edge count.

    Rebuild (rather than append) is what makes reprocessing correct: the old
    chunk rows are deleted on reprocess, so their edges must not survive.

    The caller owns the transaction — this function only flushes, so the graph
    and the document's ``status`` commit or roll back together.  If it raises,
    the document must not be marked READY.
    """
    await delete_document_graph(db, document_id)

    specs = plan_edges(chunks)
    doc_uuid = _as_uuid(document_id)
    for spec in specs:
        db.add(
            DocumentGraphEdge(
                id=uuid.uuid4(),
                document_id=doc_uuid,
                source_chunk_id=_as_uuid(spec.source_chunk_id),
                target_chunk_id=_as_uuid(spec.target_chunk_id),
                relation=spec.relation,
                weight=spec.weight,
            )
        )
    await db.flush()
    return len(specs)


# ---------------------------------------------------------------------------
# Query terms
# ---------------------------------------------------------------------------

# Deliberately small and English-only: these are the words that carry no
# section-naming information.  Anything not in this list and at least
# MIN_TERM_LENGTH characters long is treated as a candidate section term.
STOP_WORDS: frozenset[str] = frozenset(
    """
    a about above after again against all am an and any are arent as at be because
    been before being below between both but by can cannot could couldnt did didnt
    do does doesnt doing dont down during each few for from further had hadnt has
    hasnt have havent having he hed hell hes her here heres hers herself him himself
    his how hows i id ill im ive if in into is isnt it its itself lets me more most
    mustnt my myself no nor not of off on once only or other ought our ours ourselves
    out over own same shant she shed shell shes should shouldnt so some such than that
    thats the their theirs them themselves then there theres these they theyd theyll
    theyre theyve this those through to too under until up very was wasnt we wed well
    were werent weve what whats when whens where wheres which while who whos whom why
    whys with wont would wouldnt you youd youll your youre yours yourself yourselves
    what which how many much does did is are was were tell explain describe give show
    list name say says said about document documents paper report section sections
    chapter page pages paragraph text according mention mentions mention
    """.split()
)

MIN_TERM_LENGTH = 3
MAX_TERMS = 8

_TERM_RE = re.compile(r"[a-z0-9]+")


def terms_from_question(question: str, *, limit: int = MAX_TERMS) -> list[str]:
    """Meaningful terms of a question, in first-appearance order.

    Lowercased, tokenised, stop-worded and de-duplicated.  Deterministic.
    """
    if not question:
        return []

    terms: list[str] = []
    for token in _TERM_RE.findall(question.lower()):
        if len(token) < MIN_TERM_LENGTH:
            continue
        if token in STOP_WORDS:
            continue
        if token in terms:
            continue
        terms.append(token)
        if len(terms) >= limit:
            break
    return terms


def structural_score(hops: int, relation_weight: float) -> float:
    """Graph-distance score.  NOT a similarity — see the module docstring."""
    if hops <= 0:
        return 1.0
    return round(float(relation_weight) / (1.0 + float(hops)), 6)


# ---------------------------------------------------------------------------
# Seed selection (heading / section term matching)
# ---------------------------------------------------------------------------

async def find_section_seed_matches(
    db: AsyncSession,
    user_id: str,
    terms: Iterable[str],
    *,
    limit: int = 10,
) -> list[tuple[str, tuple[str, ...]]]:
    """Chunks whose ``section`` or ``heading_path`` mentions any question term.

    Returns ``(chunk_id, matched_terms)`` ordered by how many terms matched
    (descending), then by chunk id for determinism.  Only the caller's own
    ready documents are considered.
    """
    term_list = [t for t in terms if t]
    if not term_list:
        return []

    lowered_section = func.lower(func.coalesce(DocumentChunk.section, ""))
    lowered_path = func.lower(cast(DocumentChunk.heading_path, Text))

    clauses = []
    for term in term_list:
        clauses.append(lowered_section.contains(term))
        clauses.append(lowered_path.contains(term))

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.section,
            DocumentChunk.heading_path,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.user_id == _as_uuid(user_id))
        .where(Document.embedding_status == "ready")
        .where(or_(*clauses))
        # Bounded scan: the match is refined and ranked in Python below.
        .limit(max(limit * 5, 50))
    )

    rows = (await db.execute(stmt)).fetchall()

    scored: list[tuple[str, tuple[str, ...]]] = []
    for row in rows:
        haystack = " ".join(
            filter(
                None,
                [
                    (row.section or "").lower(),
                    ((row.heading_path if isinstance(row.heading_path, str) else " > ".join(row.heading_path or [])).lower()),
                ],
            )
        )
        matched = tuple(t for t in term_list if t in haystack)
        if matched:
            scored.append((str(row.id), matched))

    scored.sort(key=lambda item: (-len(item[1]), item[0]))
    return scored[:limit]


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------

async def expand_from_seeds(
    db: AsyncSession,
    user_id: str,
    seed_chunk_ids: Sequence[str],
    *,
    max_hops: int = MAX_HOPS,
    max_nodes: int = MAX_NODES,
) -> dict[str, tuple[int, str | None, float]]:
    """Breadth-first expansion over the user's own graph.

    Returns ``{chunk_id: (hops, relation, relation_weight)}`` including the
    seeds themselves at hop ``0`` with relation ``None``.

    Every hop is fetched with a join to ``documents`` filtered on
    ``user_id``, so a forged or foreign chunk id can never be traversed.
    """
    seed_uuids = [_as_uuid(s) for s in seed_chunk_ids]
    visited: dict[str, tuple[int, str | None, float]] = {
        str(s): (0, None, 1.0) for s in seed_uuids
    }
    frontier: list = list(dict.fromkeys(seed_uuids))

    for hop in range(1, max_hops + 1):
        if not frontier or len(visited) >= max_nodes:
            break

        stmt = (
            select(
                DocumentGraphEdge.source_chunk_id,
                DocumentGraphEdge.target_chunk_id,
                DocumentGraphEdge.relation,
                DocumentGraphEdge.weight,
            )
            .join(
                DocumentChunk,
                DocumentChunk.id == DocumentGraphEdge.target_chunk_id,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentGraphEdge.source_chunk_id.in_(frontier))
            .where(Document.user_id == _as_uuid(user_id))
        )
        rows = (await db.execute(stmt)).fetchall()

        next_frontier: list = []
        for row in rows:
            target = str(row.target_chunk_id)
            weight = float(row.weight) if row.weight is not None else DEFAULT_WEIGHT

            if target in visited:
                # Same hop, better relation: keep the stronger edge.
                prev_hops, _prev_rel, prev_weight = visited[target]
                if prev_hops == hop and weight > prev_weight:
                    visited[target] = (hop, row.relation, weight)
                continue

            visited[target] = (hop, row.relation, weight)
            next_frontier.append(row.target_chunk_id)
            if len(visited) >= max_nodes:
                break

        frontier = next_frontier

    return visited


async def load_candidates(
    db: AsyncSession,
    user_id: str,
    chunk_ids: Sequence[str],
) -> dict[str, dict]:
    """Load chunk + document fields for ``chunk_ids``, scoped to the user.

    Ids that are not visible to ``user_id`` are silently absent from the
    result — which is what makes cross-user expansion impossible.
    """
    ids = [_as_uuid(c) for c in chunk_ids]
    if not ids:
        return {}

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.content,
            DocumentChunk.document_id,
            DocumentChunk.page,
            DocumentChunk.heading_path,
            DocumentChunk.section,
            DocumentChunk.element_type,
            DocumentChunk.token_count,
            DocumentChunk.chunker_version,
            Document.name,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.user_id == _as_uuid(user_id))
        .where(DocumentChunk.id.in_(ids))
    )

    rows = (await db.execute(stmt)).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        path = row.heading_path
        if isinstance(path, str):
            try:
                import json as _json

                path = _json.loads(path)
            except Exception:
                path = None
        normalized = _norm_path(path)
        out[str(row.id)] = {
            "chunk_id": str(row.id),
            "content": row.content or "",
            "document_id": str(row.document_id),
            "document_name": row.name,
            "page": row.page,
            "heading_path": normalized,
            "section": row.section,
            "element_type": row.element_type,
            "token_count": row.token_count,
            "chunker_version": row.chunker_version,
        }
    return out


async def count_document_edges(db: AsyncSession, document_id) -> int:
    """Number of edges currently stored for a document."""
    stmt = (
        select(func.count())
        .select_from(DocumentGraphEdge)
        .where(DocumentGraphEdge.document_id == _as_uuid(document_id))
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


# ===========================================================================
# Structure-aware element graph traversal (Sprint 2 Feature #11)
# ===========================================================================
#
# Traversal over the persisted structural elements produced by the parser and
# stored in ``document_structure_elements``.  The authoritative hierarchy is
# ``DocumentStructureElement.parent_id``; these functions never infer
# relationships from text, embeddings, headings, page proximity or filenames,
# and never create ``DocumentStructureEdge`` rows.
#
# Everything is document-scoped: every query filters on ``document_id``, so an
# element of Document A can never cause traversal into Document B.
#
# This is *structure* traversal only.  It performs no semantic retrieval, no
# embedding, no GraphRAG fusion and no LLM call — it exists so a later Dual-Path
# GraphRAG task can walk a document's structure deterministically.
#
# Determinism
# -----------
# * sibling / descendant ordering: ``sequence_index ASC, id ASC``.
# * parent chain direction: requested element -> ... -> root (root first in the
#   returned list, since the walk is reversed at the end).

#: Bounded default depth for descendant traversal (guards pathological nesting).
MAX_STRUCTURE_DEPTH = 100

#: Guard against an unreasonably large subtree being materialised at once.
MAX_STRUCTURE_DESCENDANTS = 10_000


def _element_uuid(value: object) -> uuid.UUID:
    """Coerce to a UUID.  Raises :class:`ValueError` on a malformed id."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _element_order(stmt):
    """Apply the canonical deterministic element ordering."""
    return stmt.order_by(
        DocumentStructureElement.sequence_index.asc(),
        DocumentStructureElement.id.asc(),
    )


async def get_structure_element(
    db: AsyncSession,
    document_id,
    element_id,
) -> DocumentStructureElement | None:
    """Fetch one structural element, scoped to ``document_id``.

    Returns ``None`` when the element does not exist **or** belongs to another
    document — the two cases are deliberately indistinguishable, so a caller
    cannot probe for another document's element ids.
    """
    stmt = select(DocumentStructureElement).where(
        DocumentStructureElement.id == _element_uuid(element_id),
        DocumentStructureElement.document_id == _element_uuid(document_id),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_direct_children(
    db: AsyncSession,
    document_id,
    element_id,
) -> list[DocumentStructureElement]:
    """Direct children of ``element_id`` within ``document_id``.

    Children are the elements whose ``parent_id`` equals ``element_id``,
    ordered deterministically by ``sequence_index ASC, id ASC``.  Document-
    scoped, so a parent id from another document returns nothing.
    """
    stmt = _element_order(
        select(DocumentStructureElement).where(
            DocumentStructureElement.document_id == _element_uuid(document_id),
            DocumentStructureElement.parent_id == _element_uuid(element_id),
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_parent_chain(
    db: AsyncSession,
    document_id,
    element_id,
) -> list[DocumentStructureElement]:
    """Ancestor chain of ``element_id``, from the root down to the element.

    Walks ``parent_id`` iteratively (one row fetched per level, no recursive
    SQL) and returns ``[root, ..., parent, element]`` — the requested element
    is the last item.  Returns ``[]`` when the element does not exist in the
    document.

    Safety:

    * a parent that is not in the same document (broken / cross-document
      reference) stops the walk rather than following it;
    * a cycle stops the walk and logs a warning — it never loops forever and
      never returns duplicate nodes.
    """
    doc_uuid = _element_uuid(document_id)
    current = await get_structure_element(db, doc_uuid, element_id)
    if current is None:
        return []

    chain: list[DocumentStructureElement] = [current]
    seen: set[uuid.UUID] = {current.id}

    while current.parent_id is not None:
        parent = (
            await db.execute(
                select(DocumentStructureElement).where(
                    DocumentStructureElement.id == current.parent_id,
                    DocumentStructureElement.document_id == doc_uuid,
                )
            )
        ).scalar_one_or_none()

        if parent is None:
            # Broken or cross-document reference: stop safely.
            break
        if parent.id in seen:
            logger.warning(
                "structure cycle detected in document %s at element %s; "
                "stopping parent walk",
                doc_uuid,
                parent.id,
            )
            break
        seen.add(parent.id)
        chain.append(parent)
        current = parent

    chain.reverse()  # root first, requested element last
    return chain


async def get_descendants(
    db: AsyncSession,
    document_id,
    element_id,
    *,
    max_depth: int = MAX_STRUCTURE_DEPTH,
    max_nodes: int = MAX_STRUCTURE_DESCENDANTS,
) -> list[DocumentStructureElement]:
    """All descendants of ``element_id``, breadth-first, bounded and deduped.

    Ordering is deterministic: breadth-first by depth, then
    ``sequence_index ASC, id ASC`` within each level.  Traversal is document-
    scoped at every level and uses an in-Python queue (one SQL query per level)
    rather than recursive SQL, so a pathological hierarchy cannot recurse the
    database.

    The element itself is **not** included.  Cycles and shared children can
    never produce duplicates because visited ids are tracked.  ``max_depth``
    bounds the levels walked and ``max_nodes`` caps how many rows are
    materialised.
    """
    doc_uuid = _element_uuid(document_id)
    root = await get_structure_element(db, doc_uuid, element_id)
    if root is None:
        return []

    out: list[DocumentStructureElement] = []
    visited: set[uuid.UUID] = {root.id}
    frontier: list[uuid.UUID] = [root.id]

    for _depth in range(max(0, int(max_depth))):
        if not frontier:
            break
        stmt = _element_order(
            select(DocumentStructureElement).where(
                DocumentStructureElement.document_id == doc_uuid,
                DocumentStructureElement.parent_id.in_(frontier),
            )
        )
        level = list((await db.execute(stmt)).scalars().all())

        next_frontier: list[uuid.UUID] = []
        for element in level:
            if element.id in visited:
                continue  # cycle / shared-child guard: no duplicates
            visited.add(element.id)
            out.append(element)
            next_frontier.append(element.id)
            if len(out) >= max_nodes:
                return out
        frontier = next_frontier

    return out


async def get_structural_neighborhood(
    db: AsyncSession,
    document_id,
    element_id,
    *,
    ancestor_depth: int = MAX_STRUCTURE_DEPTH,
    descendant_depth: int = 1,
) -> dict:
    """A small, reusable structural view around one element.

    Returns a plain dict (JSON-serialisable) with:

    * ``element``       — the requested element;
    * ``ancestors``     — the parent chain, root first, excluding the element;
    * ``children``      — direct children, ``sequence_index ASC, id ASC``;
    * ``descendants``   — bounded subtree, breadth-first (``descendant_depth``).

    This is a pure structure primitive for a future GraphRAG step: no semantic
    retrieval, no embeddings, no edge inference.  Returns ``{}`` when the
    element does not exist in the document.  ``ancestor_depth`` bounds the
    parent walk; the element's own chain is naturally finite.
    """
    element = await get_structure_element(db, document_id, element_id)
    if element is None:
        return {}

    chain = await get_parent_chain(db, document_id, element_id)
    ancestors = [e for e in chain if e.id != element.id]
    if ancestor_depth is not None and ancestor_depth >= 0:
        # Keep the nearest ``ancestor_depth`` ancestors (root-most dropped).
        ancestors = ancestors[-ancestor_depth:] if ancestor_depth else []

    children = await get_direct_children(db, document_id, element_id)
    descendants = await get_descendants(
        db, document_id, element_id, max_depth=descendant_depth
    )

    return {
        "element": element,
        "ancestors": ancestors,
        "children": children,
        "descendants": descendants,
    }


# ===========================================================================
# Structure-element candidate generation (dual-path element stream)
# ===========================================================================
#
# Query-conditioned candidate selection over the persisted element tree, so a
# ``DocumentStructureElement`` can become a retrieval candidate in the same
# final ranking process as semantic chunks.  The design mirrors the chunk-level
# structural path exactly:
#
# * **seeds** — elements whose own section name (``heading_path[-1]``) matches
#   a question term.  This is the same structural-name term matching the chunk
#   path uses (``find_section_seed_matches``); element *content* is never
#   matched, so a term that only occurs in body text cannot seed structure.
#   Deeper sections are deliberately not seeded by ancestor names — they are
#   reached by traversal, which is what the parent/child walk is for.
# * **expansion** — bounded breadth-first walk over ``parent_id`` children
#   (the authoritative hierarchy link), document-scoped and user-scoped at
#   every level, exactly like ``expand_from_seeds``.
# * **ranking** — the existing graph-distance ``structural_score``
#   (``relation_weight / (1 + hops)``, seed = 1.0).  No lexical score is
#   invented for ranking; matched-term counts only bound which seeds enter.
#
# Determinism: element order is ``sequence_index ASC, id ASC`` at every level
# (the canonical ``_element_order``), and the seed order is matched-term count
# descending then element id — identical to the chunk path.

#: How many matched elements act as seeds (mirrors the chunk seed limit).
ELEMENT_SEED_LIMIT = 8

#: Maximum tree hops for element expansion (mirrors ``MAX_HOPS``).
MAX_ELEMENT_HOPS = 2

#: Hard cap on elements materialised by one expansion (mirrors ``MAX_NODES``).
MAX_ELEMENT_NODES = 40


def _element_heading_leaf(heading_path: object) -> str:
    """The element's own section name: the last heading-path entry.

    Structural identity only — this is never inferred from content.
    """
    if not heading_path:
        return ""
    if isinstance(heading_path, str):
        parts = [p.strip() for p in heading_path.split(">")]
    else:
        parts = [str(p).strip() for p in heading_path]
    parts = [p for p in parts if p]
    return parts[-1].lower() if parts else ""


async def find_element_seed_matches(
    db: AsyncSession,
    user_id: str,
    terms: Iterable[str],
    *,
    limit: int = 10,
) -> list[tuple[str, tuple[str, ...]]]:
    """Elements whose own section name mentions any question term.

    Returns ``(element_id, matched_terms)`` ordered by how many terms matched
    (descending), then by element id for determinism.  Only the caller's own
    ready documents are considered, and only structural names are read —
    never element content.
    """
    term_list = [t for t in terms if t]
    if not term_list:
        return []

    # Coarse bounded SQL filter on the heading path (a superset of the leaf
    # match below), refined deterministically in Python.
    lowered_path = func.lower(cast(DocumentStructureElement.heading_path, Text))
    clauses = [lowered_path.contains(term) for term in term_list]

    stmt = (
        select(
            DocumentStructureElement.id,
            DocumentStructureElement.heading_path,
        )
        .join(Document, Document.id == DocumentStructureElement.document_id)
        .where(Document.user_id == _as_uuid(user_id))
        .where(Document.embedding_status == "ready")
        .where(or_(*clauses))
        .limit(max(limit * 5, 50))
    )

    rows = (await db.execute(stmt)).fetchall()

    scored: list[tuple[str, tuple[str, ...]]] = []
    for row in rows:
        leaf = _element_heading_leaf(row.heading_path)
        matched = tuple(t for t in term_list if t in leaf)
        if matched:
            scored.append((str(row.id), matched))

    scored.sort(key=lambda item: (-len(item[1]), item[0]))
    return scored[:limit]


async def expand_element_seeds(
    db: AsyncSession,
    user_id: str,
    seed_element_ids: Sequence[str],
    *,
    max_hops: int = MAX_ELEMENT_HOPS,
    max_nodes: int = MAX_ELEMENT_NODES,
) -> dict[str, tuple[int, str | None, float]]:
    """Breadth-first expansion over ``parent_id`` children for the user's own
    elements.

    Returns ``{element_id: (hops, relation, relation_weight)}`` including the
    seeds themselves at hop ``0`` with relation ``None``.  Children are reached
    through the ``PARENT_OF`` hierarchy link (parent -> child), weight 1.0.

    Every hop is fetched with a join to ``documents`` filtered on ``user_id``,
    so a forged or foreign element id can never be traversed, and traversal
    cannot cross documents because ``parent_id`` lives inside one document.
    """
    seed_uuids = [_as_uuid(s) for s in seed_element_ids]
    visited: dict[str, tuple[int, str | None, float]] = {
        str(s): (0, None, 1.0) for s in seed_uuids
    }
    frontier: list = list(dict.fromkeys(seed_uuids))

    for hop in range(1, max_hops + 1):
        if not frontier or len(visited) >= max_nodes:
            break

        stmt = _element_order(
            select(DocumentStructureElement.id)
            .join(Document, Document.id == DocumentStructureElement.document_id)
            .where(DocumentStructureElement.parent_id.in_(frontier))
            .where(Document.user_id == _as_uuid(user_id))
        )
        rows = (await db.execute(stmt)).scalars().all()

        next_frontier: list = []
        for element_id in rows:
            target = str(element_id)
            if target in visited:
                continue
            visited[target] = (hop, RELATION_PARENT_OF, DEFAULT_WEIGHT)
            next_frontier.append(element_id)
            if len(visited) >= max_nodes:
                break

        frontier = next_frontier

    return visited


async def load_table_rows(
    db: AsyncSession,
    user_id: str,
    document_ids: Sequence[str],
    *,
    max_documents: int = 5,
) -> list[DocumentTableRow]:
    """Compact table-row evidence for the caller's own documents.

    Returns the persisted :class:`~documents.models.DocumentTableRow` rows for at
    most ``max_documents`` of ``document_ids``, ordered by
    ``(document_id, table_element_id, row_index)`` so selection is deterministic
    and independent of insertion order.

    Ownership is enforced in the database: the query joins ``documents`` and
    filters on ``user_id``, so a forged or foreign document id yields no rows and
    a caller can only ever read its own evidence.  This is a bounded, targeted
    read (document-scoped, never a whole-table scan) — the rows are small
    (header-repeated row units), not the aggregate table element.
    """
    ids = [_as_uuid(d) for d in dict.fromkeys(document_ids)][
        : max(0, int(max_documents))
    ]
    if not ids:
        return []

    stmt = (
        select(DocumentTableRow)
        .join(Document, Document.id == DocumentTableRow.document_id)
        .where(DocumentTableRow.document_id.in_(ids))
        .where(Document.user_id == _as_uuid(user_id))
        .order_by(
            DocumentTableRow.document_id.asc(),
            DocumentTableRow.table_element_id.asc(),
            DocumentTableRow.row_index.asc(),
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def load_element_candidates(
    db: AsyncSession,
    user_id: str,
    element_ids: Sequence[str],
) -> dict[str, dict]:
    """Load element + document fields for ``element_ids``, scoped to the user.

    Ids that are not visible to ``user_id`` are silently absent from the
    result — which is what makes cross-user element retrieval impossible.
    """
    ids = [_as_uuid(e) for e in element_ids]
    if not ids:
        return {}

    stmt = (
        select(
            DocumentStructureElement.id,
            DocumentStructureElement.document_id,
            DocumentStructureElement.element_type,
            DocumentStructureElement.sequence_index,
            DocumentStructureElement.page_number,
            DocumentStructureElement.heading_path,
            DocumentStructureElement.content,
            DocumentStructureElement.parent_id,
            DocumentStructureElement.parser_version,
            Document.name,
        )
        .join(Document, Document.id == DocumentStructureElement.document_id)
        .where(Document.user_id == _as_uuid(user_id))
        .where(DocumentStructureElement.id.in_(ids))
    )

    rows = (await db.execute(stmt)).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        out[str(row.id)] = {
            "element_id": str(row.id),
            "document_id": str(row.document_id),
            "document_name": row.name,
            "element_type": row.element_type,
            "sequence_index": int(row.sequence_index),
            "page": row.page_number,
            "heading_path": _norm_path(row.heading_path),
            "content": row.content or "",
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "parser_version": row.parser_version,
        }
    return out
