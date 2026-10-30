"""
RAG (Retrieval-Augmented Generation) orchestration for DocuMind.

Flow:
  User question → query embedding → pgvector retrieval → relevant chunks
  → QA model receives question + concatenated context → answer + evidence

Phase 3D added :func:`build_qa_context`, which sizes the context in *tokens*
against the QA model's real input window.  ``build_context`` (character
based) is retained unchanged for the legacy code path and comparison.

Phase 3D correction pass: :func:`retrieve_chunks` now also returns the Phase 3D
structure metadata (``heading_path``, ``section``, ``element_type``,
``token_count``, ``chunker_version``) so the structure written at ingestion time
actually reaches source attribution and evidence instead of stopping at the
database.  All of it is optional; legacy rows yield ``None``.
"""

import json
import logging
import math
import os
import re
from dataclasses import dataclass, replace
from typing import Mapping, Sequence
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError
from starlette.concurrency import run_in_threadpool

from embeddings.model import embed_query
from graph.service import (
    MAX_HOPS as GRAPH_MAX_HOPS,
    expand_element_seeds,
    expand_from_seeds,
    find_element_seed_matches,
    find_section_seed_matches,
    load_candidates as load_graph_candidates,
    load_element_candidates,
    load_table_rows,
    structural_score as graph_structural_score,
    terms_from_question,
)
from chat.qa_model import (
    answer_question,
    count_input_tokens,
    count_text_tokens,
    get_max_input_length,
    is_model_available,
)


# ---------------------------------------------------------------------------
# Retrieval-path vocabulary
# ---------------------------------------------------------------------------

RETRIEVAL_SEMANTIC = "semantic"
"""Found by the existing pgvector path only."""

RETRIEVAL_LEXICAL = "lexical"
"""Found only by PostgreSQL full-text search; no cosine score is available."""

RETRIEVAL_STRUCTURAL = "structural"
"""Found only by heading/section seeding + document-graph traversal."""

RETRIEVAL_HYBRID = "hybrid"
"""Found independently by more than one retrieval path."""
RETRIEVAL_KNOWLEDGE_GRAPH = "knowledge_graph"
"""Reached through owner-scoped entity/relation triples with source evidence."""

RETRIEVAL_PATHS = (
    RETRIEVAL_SEMANTIC,
    RETRIEVAL_LEXICAL,
    RETRIEVAL_STRUCTURAL,
    RETRIEVAL_HYBRID,
    RETRIEVAL_KNOWLEDGE_GRAPH,
)


@dataclass
class SourceChunk:
    """One retrieved chunk.

    The first six fields are the original contract.  The Phase 3D structure
    metadata below is additive and optional: legacy chunks legitimately carry
    ``None`` for every one of them, so every existing caller keeps working
    unchanged.
    """

    chunk_id: str
    content: str
    score: float
    document_id: str
    document_name: str
    page: int | None

    # --- Phase 3D structure metadata (None for legacy chunks) ---
    heading_path: tuple[str, ...] | None = None
    section: str | None = None
    element_type: str | None = None
    token_count: int | None = None
    chunker_version: str | None = None

    # --- Dual-path provenance (additive; defaults keep legacy callers working) ---
    retrieval_path: str = RETRIEVAL_SEMANTIC
    """Which retrieval path produced this chunk, including ``"knowledge_graph"``.
    ``"hybrid"``.  A chunk found by both paths is ``"hybrid"``."""

    fusion_score: float | None = None
    """Reciprocal-rank-fusion score.  This is **not** a cosine similarity and
    must never be reported as one; ``score`` remains the similarity."""

    structural_hops: int | None = None
    """Graph hops from the nearest structural seed (``0`` = the seed itself)."""

    structural_relation: str | None = None
    """Graph relation that reached this chunk (``None`` at hop 0)."""

    structural_score: float | None = None
    """Graph-distance score (relation weight / (1 + hops)).  Not a similarity."""

    evidence_kind: str = "chunk"
    """Granularity of the evidence record: ``"chunk"`` for a
    ``document_chunks`` row, ``"structure_element"`` for a
    ``document_structure_elements`` row reached by the element-level structural
    stream, or ``"table_row"`` for a ``document_table_rows`` row from the
    query-gated compact table-evidence band.  Defaults to ``"chunk"`` so
    existing producers keep their meaning."""

    # --- Table-row provenance (additive; None for every other evidence kind) ---
    table_element_id: str | None = None
    """The aggregate ``table`` structure element this row belongs to."""

    row_index: int | None = None
    """The row's own 0-based index in the source table (header row is 0)."""

    header_repeated: bool | None = None
    """Whether ``content`` embeds the table's header row above the row itself."""

    # --- Entity-relation GraphRAG provenance ---
    knowledge_graph_path: str | None = None
    knowledge_graph_hops: int | None = None
    knowledge_graph_predicate: str | None = None
    knowledge_graph_quote: str | None = None
    spatial_regions: list[dict] | None = None
    # Request-time section expansion metadata; no persisted schema is implied.
    topic_context_id: str | None = None
    topic_context_complete: bool | None = None
    topic_context_kind: str | None = None
    # Request-time neural rank; cosine score remains a separate measurement.
    rerank_position: int | None = None


def coerce_heading_path(value: object) -> tuple[str, ...] | None:
    """Normalise a stored ``heading_path`` into an immutable tuple.

    The column is ``JSON``, so a raw-SQL row can surface it as a list (SQLAlchemy
    decodes it) or as a JSON string (driver without a JSON codec).  Both are
    accepted so retrieval never loses structure metadata to a driver detail.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    if isinstance(value, (list, tuple)):
        parts = tuple(str(part) for part in value if str(part).strip())
        return parts or None
    return None


@dataclass
class RagResult:
    answer: str
    confidence: float
    sources: list[SourceChunk]
    insufficient_context: bool
    context_used: str
    # Reliability evidence fields
    retrieval_scores: list[float]  # raw similarity scores from pgvector
    avg_retrieval_score: float     # mean of retrieval scores
    best_retrieval_score: float    # top chunk similarity
    factual_grounded: bool         # whether the answer span appears in context
    source_count: int              # number of sources retrieved
    unique_documents: int          # number of distinct source documents


async def retrieve_chunks(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int = 5,
    *, iterative_scan: bool = False,
) -> list[SourceChunk]:
    """Retrieve the most relevant chunks from the user's documents."""
    # CPU embedding must not block voice frames, status requests or cancellation
    # on the event loop while retrieval is running.
    query_embedding = await run_in_threadpool(embed_query, query)
    emb_str = str(query_embedding)
    if iterative_scan:
        # Transaction-local pgvector 0.8+ controls let an ANN scan continue when
        # authenticated ownership filtering removes its first candidates.
        # The planner may still choose exact search for a small owner's corpus.
        await db.execute(text("SELECT set_config('hnsw.iterative_scan', 'strict_order', true), "
                              "set_config('hnsw.ef_search', '100', true)"))

    # All dynamic values use SQLAlchemy parameter binding — no f-string
    # interpolation of user-controlled input.
    #
    # NOTE: We use CAST(:embedding AS vector) instead of :embedding::vector
    # because asyncpg treats `:embedding::vector` as a single parameter name
    # rather than the parameter `:embedding` followed by a type cast.
    search_sql = text(
        "SELECT"
        "  dc.id as chunk_id,"
        "  dc.content,"
        "  dc.document_id,"
        "  d.name as document_name,"
        "  dc.page,"
        "  1 - (dc.embedding <=> CAST(:embedding AS vector)) as similarity,"
        # Phase 3D structure metadata — carried through retrieval so sources and
        # evidence can cite the section a span came from.  NULL for legacy chunks.
        "  dc.heading_path,"
        "  dc.section,"
        "  dc.element_type,"
        "  dc.token_count,"
        "  dc.chunker_version"
        " FROM document_chunks dc"
        " JOIN documents d ON d.id = dc.document_id"
        " WHERE d.user_id = :user_id"
        "   AND d.embedding_status = 'ready'"
        "   AND dc.embedding IS NOT NULL"
        " ORDER BY dc.embedding <=> CAST(:embedding AS vector)"
        " LIMIT :top_k"
    )

    result = await db.execute(
        search_sql,
        {"embedding": emb_str, "user_id": user_id, "top_k": top_k},
    )
    rows = result.fetchall()

    return [
        SourceChunk(
            chunk_id=str(row.chunk_id),
            content=row.content,
            score=round(float(row.similarity), 4),
            document_id=str(row.document_id),
            document_name=row.document_name,
            page=row.page,
            heading_path=coerce_heading_path(row.heading_path),
            section=row.section,
            element_type=row.element_type,
            token_count=row.token_count,
            chunker_version=row.chunker_version,
        )
        for row in rows
    ]


def fuse_search_candidates(
    dense: Sequence[SourceChunk], lexical: Sequence[SourceChunk], *, top_k: int = 5,
) -> list[SourceChunk]:
    """RRF ranks independent search streams without comparing unlike scores.

    Dense cosine stays in ``score``. A lexical-only hit has no measured cosine,
    so its score is zero. ``fusion_score`` is a ranking signal, never confidence.
    """
    by_id: dict[str, SourceChunk] = {}
    ranks: dict[str, float] = {}
    streams: dict[str, set[int]] = {}
    for stream_index, candidates in enumerate((dense, lexical)):
        seen: set[str] = set()
        for rank, candidate in enumerate(candidates, 1):
            key = str(candidate.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            by_id.setdefault(key, candidate)
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (60 + rank)
            streams.setdefault(key, set()).add(stream_index)
    ordered = sorted(ranks, key=lambda key: (-ranks[key], key))
    return [replace(by_id[key], fusion_score=ranks[key],
                    score=by_id[key].score if 0 in streams[key] else 0.0,
                    retrieval_path=RETRIEVAL_HYBRID if len(streams[key]) > 1 else
                    RETRIEVAL_SEMANTIC if 0 in streams[key] else RETRIEVAL_LEXICAL)
            for key in ordered[:max(1, min(int(top_k), 40))]]


async def retrieve_hybrid_chunks(
    db: AsyncSession, user_id: str, query: str, top_k: int = 5, *, candidate_limit: int | None = None,
) -> list[SourceChunk]:
    """Bounded dense + PostgreSQL full-text retrieval for the product path.

    FTS currently evaluates an expression over owner-filtered chunks; a matching
    GIN expression index is a separate migration before large-corpus deployment.
    This is PostgreSQL text ranking, not BM25 or a neural reranker.
    """
    limit = max(1, min(int(top_k), 20))
    output_limit = min(32, max(limit, int(candidate_limit))) if candidate_limit is not None else limit
    candidate_k = min(40, max(20, limit * 3, output_limit))
    dense = await retrieve_chunks(db, user_id, query, top_k=candidate_k, iterative_scan=True)
    try:
        # A failure leaves the surrounding answering transaction usable.
        async with db.begin_nested():
            result = await db.execute(text("""
                SELECT dc.id AS chunk_id, dc.content, dc.document_id,
                       d.name AS document_name, dc.page, dc.heading_path,
                       dc.section, dc.element_type, dc.token_count, dc.chunker_version
                FROM document_chunks dc JOIN documents d ON d.id = dc.document_id
                CROSS JOIN (SELECT websearch_to_tsquery('english', :query) AS terms) search_query
                WHERE d.user_id = :user_id AND d.embedding_status = 'ready'
                  AND to_tsvector('english', dc.content) @@ search_query.terms
                ORDER BY ts_rank_cd(to_tsvector('english', dc.content), search_query.terms) DESC, dc.id
                LIMIT :candidate_k
            """), {"query": query, "user_id": user_id, "candidate_k": candidate_k})
            rows = result.fetchall()
    except DBAPIError:
        logging.getLogger(__name__).warning("Full-text retrieval unavailable; retaining dense results")
        return dense[:output_limit]
    lexical = [SourceChunk(
        chunk_id=str(row.chunk_id), content=row.content, score=0.0,
        document_id=str(row.document_id), document_name=row.document_name, page=row.page,
        heading_path=coerce_heading_path(row.heading_path), section=row.section,
        element_type=row.element_type, token_count=row.token_count,
        chunker_version=row.chunker_version, retrieval_path=RETRIEVAL_LEXICAL,
    ) for row in rows]
    return fuse_search_candidates(dense, lexical, top_k=output_limit)


def build_context(chunks: list[SourceChunk], max_chars: int = 4000) -> str:
    """Legacy character-bounded context builder (unchanged).

    Retained for the legacy path.  It ``break``s at the first chunk that does
    not fit, which can starve later-ranked evidence, and 4000 characters far
    exceeds the QA model's real input window — see :func:`build_qa_context`
    for the token-aware builder used by the Brain path.
    """
    parts = []
    total = 0
    for chunk in chunks:
        if total + len(chunk.content) > max_chars:
            break
        parts.append(chunk.content)
        total += len(chunk.content)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Phase 3D — token-aware context construction
# ---------------------------------------------------------------------------

CONTEXT_JOINER = "\n\n"
QA_TOKEN_SAFETY_MARGIN = 4     # covers tokenizer/edge-case drift
MIN_CONTEXT_TOKENS = 32        # below this, a partial chunk is not worth adding
FALLBACK_CHARS_PER_TOKEN = 4

_BOUNDARY_RE = re.compile(r"(?:[.!?](?=\s))|(?:\n)")


class ContextPack(str):
    """Context text that also reports which sources it actually contains.

    Subclasses ``str`` so every existing consumer (QA model, adapters, tests)
    keeps working unchanged, while the Brain can restrict reported evidence to
    exactly what the QA model was given.
    """

    included_ids: tuple[str, ...]
    omitted_ids: tuple[str, ...]
    truncated_ids: tuple[str, ...]
    budget_tokens: int
    used_tokens: int
    exact: bool

    def __new__(
        cls,
        text: str,
        *,
        included_ids: list[str] | tuple[str, ...] = (),
        omitted_ids: list[str] | tuple[str, ...] = (),
        truncated_ids: list[str] | tuple[str, ...] = (),
        budget_tokens: int = 0,
        used_tokens: int = 0,
        exact: bool = False,
    ) -> "ContextPack":
        obj = super().__new__(cls, text)
        obj.included_ids = tuple(included_ids)
        obj.omitted_ids = tuple(omitted_ids)
        obj.truncated_ids = tuple(truncated_ids)
        obj.budget_tokens = int(budget_tokens)
        obj.used_tokens = int(used_tokens)
        obj.exact = bool(exact)
        return obj


def _count_text(text: str) -> tuple[int, bool]:
    """Token count of ``text``; ``(count, exact)``.

    Falls back to a character estimate (flagged inexact) when the QA
    tokenizer is unavailable, so context construction never fails.
    """
    exact = count_text_tokens(text)
    if exact is not None:
        return exact, True
    if not text:
        return 0, False
    return max(1, int(math.ceil(len(text) / FALLBACK_CHARS_PER_TOKEN))), False


def _question_overhead(question: str) -> tuple[int, bool]:
    """Tokens consumed by the question plus QA special tokens."""
    overhead = count_input_tokens(question, "")
    if overhead is not None:
        return overhead, True
    if not question:
        return 3, False
    est = max(1, int(math.ceil(len(question) / FALLBACK_CHARS_PER_TOKEN)))
    return est + 3, False


def _sentence_boundaries(text: str) -> list[int]:
    """End offsets of sentence-like pieces, in order."""
    return [m.end() for m in _BOUNDARY_RE.finditer(text)]


def truncate_to_tokens(text: str, budget: int) -> str:
    """Longest sentence-aligned prefix of ``text`` within ``budget`` tokens.

    Falls back to a character binary search when not even one sentence fits.
    Deterministic for a deterministic counter.
    """
    if budget <= 0 or not text:
        return ""

    if _count_text(text)[0] <= budget:
        return text

    best = ""
    for end in _sentence_boundaries(text):
        candidate = text[:end].strip()
        if not candidate:
            continue
        if _count_text(candidate)[0] <= budget:
            best = candidate
        else:
            break
    if best:
        return best

    lo, hi = 1, len(text)
    best_len = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if _count_text(text[:mid])[0] <= budget:
            best_len = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return text[:best_len].strip()


def build_qa_context(
    chunks: list[SourceChunk],
    question: str = "",
    *,
    budget_tokens: int | None = None,
) -> ContextPack:
    """Build the QA context within the model's real token window.

    Guarantees:
      * the returned context never exceeds the QA input window, so the model
        never silently truncates evidence away;
      * the highest-ranked chunk is always represented (truncated at a
        sentence boundary if it alone is too large) — it is the most likely
        to contain the answer, so it must not be dropped;
      * every later chunk is included when it fits **fully**, and otherwise
        *skipped* (never used to stop construction), so one large early chunk
        cannot starve later evidence; skipping rather than truncating later
        chunks avoids putting a half sentence into the context where it could
        mislead grounding;
      * the returned pack names the chunks it actually contains, so reported
        sources can be made to match the evidence the QA model received.
    """
    window = get_max_input_length()
    overhead, exact_overhead = _question_overhead(question)
    if budget_tokens is None:
        budget = max(0, window - overhead - QA_TOKEN_SAFETY_MARGIN)
    else:
        budget = max(0, int(budget_tokens))

    joiner_tokens, exact_joiner = _count_text(CONTEXT_JOINER)
    exact = exact_overhead and exact_joiner

    parts: list[str] = []
    included: list[str] = []
    omitted: list[str] = []
    truncated: list[str] = []

    for chunk in chunks:
        content = chunk.content or ""
        if not content.strip():
            omitted.append(chunk.chunk_id)
            continue

        body_tokens = _count_text(content)[0]
        extra = joiner_tokens if parts else 0
        # Cumulative accounting: each candidate is measured against everything
        # already selected, not just against the whole budget on its own.
        used_so_far = _count_text(CONTEXT_JOINER.join(parts))[0] if parts else 0

        if used_so_far + extra + body_tokens <= budget:
            parts.append(content)
            included.append(chunk.chunk_id)
            continue

        # Only the first (top-ranked) chunk may be truncated to fit; later
        # chunks must fit entirely or be skipped.
        if parts:
            omitted.append(chunk.chunk_id)
            continue

        remaining = budget  # nothing has been included yet
        if remaining >= MIN_CONTEXT_TOKENS:
            trimmed = truncate_to_tokens(content, remaining)
            if trimmed.strip():
                parts.append(trimmed)
                included.append(chunk.chunk_id)
                truncated.append(chunk.chunk_id)
                continue

        # Reported, never silently discarded: it is recorded as omitted so
        # callers can surface the difference honestly.
        omitted.append(chunk.chunk_id)

    context = CONTEXT_JOINER.join(parts)
    used, exact_used = _count_text(context)

    return ContextPack(
        context,
        included_ids=included,
        omitted_ids=omitted,
        truncated_ids=truncated,
        budget_tokens=budget,
        used_tokens=used,
        exact=exact and exact_used,
    )


def rag_answer(
    question: str,
    chunks: list[SourceChunk],
    relevance_threshold: float = 0.15,
) -> RagResult:
    """
    Run RAG: combine retrieved chunks into context, then use QA model.

    If no chunks are retrieved or the top chunk score is below the threshold,
    we flag insufficient context.
    """
    if not chunks:
        return RagResult(
            answer="",
            confidence=0.0,
            sources=[],
            insufficient_context=True,
            context_used="",
            retrieval_scores=[],
            avg_retrieval_score=0.0,
            best_retrieval_score=0.0,
            factual_grounded=False,
            source_count=0,
            unique_documents=0,
        )

    all_scores = [c.score for c in chunks]
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    best_score = max(all_scores) if all_scores else 0.0
    unique_docs = len({c.document_id for c in chunks})

    # Check if retrieved chunks are relevant enough
    if chunks[0].score < relevance_threshold:
        return RagResult(
            answer="",
            confidence=max(0.0, chunks[0].score),
            sources=chunks,
            insufficient_context=True,
            context_used="",
            retrieval_scores=all_scores,
            avg_retrieval_score=round(avg_score, 4),
            best_retrieval_score=round(best_score, 4),
            factual_grounded=False,
            source_count=len(chunks),
            unique_documents=unique_docs,
        )

    context = build_context(chunks)
    if not context.strip():
        return RagResult(
            answer="",
            confidence=0.0,
            sources=chunks,
            insufficient_context=True,
            context_used="",
            retrieval_scores=all_scores,
            avg_retrieval_score=round(avg_score, 4),
            best_retrieval_score=round(best_score, 4),
            factual_grounded=False,
            source_count=len(chunks),
            unique_documents=unique_docs,
        )

    # Run QA model
    qa_result = answer_question(question, context)
    answer = qa_result["answer"]
    # Clamp confidence to [0, 1] — raw scores can be slightly negative
    score = max(0.0, min(1.0, qa_result["score"]))

    # ------------------------------------------------------------------
    # Answerability gate: distinguish genuinely supported answers from
    # guesses based on superficially related context.
    #
    # Two real signals, no fabrication:
    #
    #   1. QA confidence: the model's own probability that its extracted
    #      span is correct. Supported answers score 0.39–0.89. Unsupported
    #      guesses score <0.11.
    #
    #   2. Retrieval score: how semantically similar the top chunk is to
    #      the question. Truly relevant context scores ≥0.50. Superficial
    #      matches (e.g. a year near a year-related question) score <0.20.
    #
    # An answer is flagged insufficient when BOTH signals are weak:
    # low QA confidence AND low retrieval — meaning the model extracted
    # a span from context that is only superficially related to the
    # question.
    #
    # This preserves low-confidence answers that ARE grounded (e.g.
    # definition questions where retrieval is high but the model extracts
    # a partial span).
    # ------------------------------------------------------------------

    # Factual grounding: check if the extracted answer span appears
    # in the retrieved context.
    factual_grounded = False
    if answer.strip():
        answer_lower = answer.strip().lower()
        context_lower = context.lower()
        factual_grounded = answer_lower in context_lower

    insufficient = not answer.strip() or (
        score < 0.30 and best_score < 0.50
    )

    return RagResult(
        answer=answer,
        confidence=score,
        sources=chunks,
        insufficient_context=insufficient,
        context_used=context,
        retrieval_scores=all_scores,
        avg_retrieval_score=round(avg_score, 4),
        best_retrieval_score=round(best_score, 4),
        factual_grounded=factual_grounded,
        source_count=len(chunks),
        unique_documents=unique_docs,
    )


# ===========================================================================
# Dual-path retrieval — semantic (pgvector) + structural (document graph)
# ===========================================================================
#
# The semantic path above is untouched.  This section adds a second, independent
# retrieval path that walks the document's own structure, and then fuses the two
# paths with Reciprocal Rank Fusion.
#
# Fusion is deliberately *rank*-based rather than score-based: cosine similarity
# and graph-distance scores live on different scales, and adding them directly
# would invent a calibration that nobody has measured.  RRF only needs each
# path's ordering, and the two weights below are the pipeline's declared prior
# (0.70 semantic / 0.30 structural), not a fitted parameter.

DUAL_PATH_ENV = "DOCUMIND_DUAL_PATH_RAG"
"""Kill switch for the structural path.  Unset (or any value other than
0/false/no/off) → the dual path is active."""

SEMANTIC_SEED_COUNT = 3
"""How many top semantic chunks also act as structural seeds."""

STRUCTURAL_SEED_LIMIT = 8
"""How many heading/section term matches are used as seeds."""

STRUCTURAL_CANDIDATE_LIMIT = 15
"""Hard bound on structurally retrieved candidates handed to fusion."""

STRUCTURAL_ELEMENT_CANDIDATE_LIMIT = 10
"""Hard bound on structure-element candidates handed to fusion."""

RRF_K = 60
RRF_SEMANTIC_WEIGHT = 0.70
RRF_STRUCTURAL_WEIGHT = 0.30


def dual_path_enabled() -> bool:
    """Whether the structural path participates in retrieval."""
    value = os.environ.get(DUAL_PATH_ENV)
    if value is None:
        return True
    return value.strip().lower() not in ("0", "false", "no", "off", "")


# ---------------------------------------------------------------------------
# Compact table-row evidence (query-gated, additive band)
# ---------------------------------------------------------------------------
#
# Why this exists
# ---------------
# A PDF table is persisted as ONE aggregate ``table`` structure element (~230
# tokens for the teacher-demo table) which cannot fit the QA context: the budget
# is 362 usable tokens and the five ranked chunks already consume 266
# (266 + 230 = 496 > 362).  Phase 2 persists the same table's rows individually
# (``document_table_rows``), each ~36-48 tokens with the header repeated, so a
# relevant row *can* fit the remaining budget.
#
# Safety model (this is the whole point of the band)
# -------------------------------------------------
# * **Post-ranking, additive.**  The band is appended AFTER the existing fused
#   chunk list and BEFORE the existing unranked structure-element tail.  It never
#   enters RRF, never re-ranks, never replaces and never reorders chunk evidence;
#   the ranked bands are handed to ``build_qa_context`` in their existing order.
# * **Query-gated.**  Rows are only offered when the question names a persisted
#   table *dimension* (a header cell), not merely text that happens to appear in
#   a cell.  When the gate closes nothing is retrieved and the QA context is
#   byte-for-byte the previous baseline — which is what keeps an unrelated
#   question's answer (e.g. the power-rail question) from changing.
# * **All-or-nothing.**  A row must fit the *actual* remaining budget whole;
#   ``build_qa_context`` already skips (never truncates) later items, so an
#   over-cap row is reported as omitted rather than truncated into the context.
# * **Kill switch, default OFF.**  ``DOCUMIND_TABLE_EVIDENCE`` (mirroring the
#   ``DOCUMIND_DUAL_PATH_RAG`` convention) must be explicitly enabled; the
#   default is the pre-Phase-3 behaviour until Phase 4 measures it.
# * **No fabricated values.**  A row's ``content`` is the persisted serialisation
#   of the extractor's own cells (Phase 2); ``score`` stays ``0.0`` because no
#   similarity was ever computed for it.

TABLE_EVIDENCE_ENV = "DOCUMIND_TABLE_EVIDENCE"
"""Kill switch for the compact table-evidence band.  Unset, empty, or any value
other than ``1``/``true``/``yes``/``on`` → the band is OFF (the default) and the
QA context is exactly the pre-Phase-3 baseline."""

EVIDENCE_KIND_TABLE_ROW = "table_row"
"""``evidence_kind`` of a persisted ``document_table_rows`` row."""

EVIDENCE_KIND_STRUCTURE_ELEMENT = "structure_element"
"""``evidence_kind`` of the document-order structure-element tail (unchanged)."""

TABLE_EVIDENCE_MAX_DOCUMENTS = 5
"""Documents whose rows may be read for one query (matches the element stream)."""

TABLE_EVIDENCE_MAX_TABLES = 2
"""Distinct tables that may contribute row evidence to one query."""

TABLE_EVIDENCE_MAX_ROWS = 2
"""Row units that may be offered to one query."""

TABLE_EVIDENCE_MAX_TOKENS = 64
"""Per-row cap.  An over-cap row is skipped whole; it is never truncated."""

_TABLE_EVIDENCE_TRUTHY = ("1", "true", "yes", "on")


def table_evidence_enabled() -> bool:
    """Whether the compact table-evidence band participates in a request.

    Defaults to ``False``: unlike the structural path, this band changes which
    evidence reaches the extractive QA model, so it stays off until measured.
    """
    value = os.environ.get(TABLE_EVIDENCE_ENV)
    if value is None:
        return False
    return value.strip().lower() in _TABLE_EVIDENCE_TRUTHY


def table_gate_open(
    header_rows: Sequence[Sequence[str]],
    terms: Sequence[str] | set[str],
) -> bool:
    """Whether a question asks about one of a table's own dimensions.

    Deliberately stricter than "a question word appears somewhere in the table":

    * a **multi-word** header cell opens the gate only when at least **two** of its
      own terms are named by the question (e.g. ``calibration`` + ``interval`` for
      the header ``Calibration Interval``);
    * a **single-word** header cell opens the gate when that word is named.

    A question that merely mentions a word shared with a header (for example a
    question about sensor calibration in general) therefore stays closed, and a
    question whose terms only appear in *cells* — a row label or a value — does not
    open the gate either.  The gate reads persisted header cells only, so it is
    deterministic and independent of any question-specific string.
    """
    wanted = {str(term) for term in terms}
    if not wanted:
        return False

    for cells in header_rows:
        for cell in cells:
            cell_terms = set(terms_from_question(str(cell)))
            if not cell_terms:
                continue
            matched = cell_terms & wanted
            if not matched:
                continue
            if len(cell_terms) == 1 or len(matched) >= 2:
                return True
    return False


def _match_count(cells: Sequence[str], wanted: set[str]) -> int:
    """How many distinct question terms appear in ``cells`` (deterministic)."""
    if not cells:
        return 0
    text = " ".join(str(cell) for cell in cells)
    return len(set(terms_from_question(text, limit=64)) & wanted)


def select_table_row_evidence(
    rows: Sequence[object],
    *,
    question: str,
    document_names: Mapping[str, str] | None = None,
    max_rows: int = TABLE_EVIDENCE_MAX_ROWS,
    max_tables: int = TABLE_EVIDENCE_MAX_TABLES,
    max_tokens: int = TABLE_EVIDENCE_MAX_TOKENS,
) -> list[SourceChunk]:
    """Select the most relevant persisted table rows for ``question``.

    ``rows`` are ``document_table_rows`` records (any object exposing ``cells``,
    ``content``, ``is_header``, ``row_index``, ``page_number``, ``heading_path``,
    ``section``, ``token_count``, ``header_repeated``, ``document_id`` and
    ``table_element_id``).  Selection is a pure function of the persisted rows and
    the question: headers decide whether the question is table-relevant at all,
    then rows are ranked by row-label matches first, any-cell matches second, and
    source order last.

    Row-label matches take precedence over incidental cell matches, so a narrow
    question yields its own rows rather than every row that shares a word.

    Returns ``[]`` whenever the gate is closed, no row matches, or no row fits the
    per-row cap — so a caller that adds this list to the evidence stream changes
    nothing in those cases.
    """
    wanted = set(terms_from_question(question))
    if not wanted:
        return []

    grouped: dict[tuple[str, str], list[object]] = {}
    for row in rows:
        key = (str(row.document_id), str(row.table_element_id))
        grouped.setdefault(key, []).append(row)

    gated = [
        key
        for key, group in grouped.items()
        if table_gate_open(
            [list(r.cells or []) for r in group if r.is_header], wanted
        )
    ]
    if not gated:
        # Completely inert: no row selection for a question that does not ask
        # about a table dimension.
        return []

    candidates: list[tuple[int, int, str, str, int, object]] = []
    for key in gated:
        document_id, table_element_id = key
        for row in grouped[key]:
            if row.is_header:
                continue
            cells = list(row.cells or [])
            label_matches = _match_count(cells[:1], wanted)
            cell_matches = _match_count(cells, wanted)
            if not label_matches and not cell_matches:
                continue
            candidates.append(
                (
                    label_matches,
                    cell_matches,
                    document_id,
                    table_element_id,
                    int(row.row_index),
                    row,
                )
            )

    # A question that names a row label ("the lidar array") is asking about those
    # rows, so label matches take precedence exclusively: a row that merely
    # contains one of the question's words somewhere in its cells is only
    # considered when no row label matches at all.  This keeps the band narrow and
    # deterministic — one question, its rows — instead of padding it with rows
    # that happen to share a word.
    label_matched = [item for item in candidates if item[0] > 0]
    pool = label_matched or candidates
    pool.sort(key=lambda item: (-item[0], -item[1], item[2], item[3], item[4]))

    names = document_names or {}
    selected: list[SourceChunk] = []
    tables_used: list[str] = []
    for _label, _cells, document_id, table_element_id, row_index, row in pool:
        if len(selected) >= max_rows:
            break
        if table_element_id not in tables_used and len(tables_used) >= max_tables:
            continue
        content = str(row.content or "")
        if not content.strip():
            continue
        measured = row.token_count
        if not isinstance(measured, int) or measured <= 0:
            measured = _count_text(content)[0]
        if measured > max_tokens:
            # Never truncated: an oversized row is skipped whole (and therefore
            # reported as omitted once the context is built).
            continue
        selected.append(
            SourceChunk(
                chunk_id=f"{EVIDENCE_KIND_TABLE_ROW}:{table_element_id}:{row_index}",
                content=content,
                score=0.0,  # no similarity exists for table evidence
                document_id=document_id,
                document_name=names.get(document_id, ""),
                page=row.page_number,
                heading_path=coerce_heading_path(row.heading_path),
                section=row.section,
                element_type="table",
                token_count=row.token_count,
                retrieval_path=RETRIEVAL_STRUCTURAL,
                evidence_kind=EVIDENCE_KIND_TABLE_ROW,
                table_element_id=table_element_id,
                row_index=row_index,
                header_repeated=bool(row.header_repeated),
            )
        )
        if table_element_id not in tables_used:
            tables_used.append(table_element_id)
    return selected


async def retrieve_table_row_evidence(
    db: AsyncSession,
    user_id: str,
    *,
    question: str,
    chunks: Sequence[SourceChunk],
    max_documents: int = TABLE_EVIDENCE_MAX_DOCUMENTS,
) -> list[SourceChunk]:
    """Query-gated, document-scoped row evidence for an already-retrieved set.

    The document scope is the set of documents that supplied **chunk-level**
    retrieval evidence — the same boundary ``brain.adapters._augment_with_structure``
    uses, so the table band can never reach a document the ranked retrieval did
    not return (an unranked structure-element match does not widen it).  Document
    isolation is therefore inherited rather than re-implemented; the loader
    additionally filters on ``user_id`` in the database.
    """
    document_ids = list(
        dict.fromkeys(
            c.document_id
            for c in chunks
            if getattr(c, "evidence_kind", "chunk") == "chunk"
        )
    )
    if not document_ids:
        return []
    rows = await load_table_rows(
        db, user_id, document_ids, max_documents=max_documents
    )
    if not rows:
        return []
    names = {c.document_id: c.document_name for c in chunks}
    return select_table_row_evidence(rows, question=question, document_names=names)


def order_evidence_bands(
    chunks: Sequence[SourceChunk],
    table_evidence: Sequence[SourceChunk] = (),
) -> list[SourceChunk]:
    """Order evidence as: ranked chunks → table rows → unranked element tail.

    The band boundary is the first item that is not chunk-level evidence, i.e. the
    start of the unranked structure-element tail.  With no table evidence the input
    order is returned unchanged (a copy), so the pre-Phase-3 stream — and therefore
    the QA context built from it — is preserved exactly.
    """
    ordered = list(chunks)
    if not table_evidence:
        return ordered

    tail_start = len(ordered)
    for index, chunk in enumerate(ordered):
        if getattr(chunk, "evidence_kind", "chunk") != "chunk":
            tail_start = index
            break
    return [*ordered[:tail_start], *table_evidence, *ordered[tail_start:]]


async def retrieve_structural_candidates(
    db: AsyncSession,
    user_id: str,
    question: str,
    semantic_seed_ids: list[str] | None = None,
    limit: int = STRUCTURAL_CANDIDATE_LIMIT,
) -> list[SourceChunk]:
    """Retrieve chunks through document structure rather than vector similarity.

    Seeds come from two independent sources:

    A. heading/section term matching — meaningful question terms are matched
       against ``document_chunks.section`` and against the text form of
       ``document_chunks.heading_path``;
    B. the top semantic chunk ids, used as anchors into the graph.

    Seeds are then expanded through ``document_graph_edges`` for at most
    ``MAX_HOPS`` hops.  Every hop is scoped to ``user_id`` at the database, so a
    caller can never traverse or retrieve another user's chunks, and expansion
    cannot cross documents because edges are per-document.

    Returns chunks with ``retrieval_path="structural"`` and ``score=0.0``.  The
    embedding model never scored these chunks, so reporting a cosine for them
    would be fabrication; ``structural_score`` carries the graph-distance score
    instead.  Ordering is by ``structural_score`` descending, then chunk id, so
    the result is deterministic.
    """
    terms = terms_from_question(question)

    seed_ids: list[str] = []
    seed_terms: dict[str, tuple[str, ...]] = {}

    if terms:
        matches = await find_section_seed_matches(
            db, user_id, terms, limit=STRUCTURAL_SEED_LIMIT
        )
        for chunk_id, matched in matches:
            if chunk_id in seed_terms:
                continue
            seed_terms[chunk_id] = matched
            seed_ids.append(chunk_id)

    for chunk_id in (semantic_seed_ids or [])[:SEMANTIC_SEED_COUNT]:
        chunk_id = str(chunk_id)
        if chunk_id in seed_terms:
            continue
        seed_terms[chunk_id] = ()
        seed_ids.append(chunk_id)

    if not seed_ids:
        return []

    visited = await expand_from_seeds(db, user_id, seed_ids, max_hops=GRAPH_MAX_HOPS)
    details = await load_graph_candidates(db, user_id, list(visited.keys()))

    candidates: list[SourceChunk] = []
    for chunk_id, (hops, relation, weight) in visited.items():
        info = details.get(chunk_id)
        if info is None:
            # Not visible to this user (or a seed that is not one of their own
            # chunks).  Dropped rather than reported.
            continue
        candidates.append(
            SourceChunk(
                chunk_id=info["chunk_id"],
                content=info["content"],
                score=0.0,  # not a semantic hit — see the docstring
                document_id=info["document_id"],
                document_name=info["document_name"],
                page=info["page"],
                heading_path=info["heading_path"],
                section=info["section"],
                element_type=info["element_type"],
                token_count=info["token_count"],
                chunker_version=info["chunker_version"],
                retrieval_path=RETRIEVAL_STRUCTURAL,
                fusion_score=None,
                structural_hops=hops,
                structural_relation=relation,
                structural_score=graph_structural_score(hops, weight),
            )
        )

    candidates.sort(key=lambda c: (-(c.structural_score or 0.0), c.chunk_id))
    return candidates[:limit]


async def retrieve_structural_element_candidates(
    db: AsyncSession,
    user_id: str,
    question: str,
    limit: int = STRUCTURAL_ELEMENT_CANDIDATE_LIMIT,
) -> list[SourceChunk]:
    """Retrieve persisted structure elements as structural retrieval candidates.

    This is the element-level structural stream: a ``DocumentStructureElement``
    becomes a candidate here and can then enter the same rank-based fusion as
    semantic chunks (see :func:`retrieve_dual_path`).

    Candidate generation mirrors the chunk-level structural path exactly:

    A. seeds — elements whose own section name (``heading_path[-1]``) matches a
       meaningful question term (structure names only; element content is
       never matched);
    B. expansion — bounded breadth-first walk over the ``parent_id`` tree
       (``MAX_ELEMENT_HOPS`` hops, ``MAX_ELEMENT_NODES`` nodes), scoped to the
       authenticated user at every level.

    Returns elements with ``retrieval_path="structural"`` and
    ``evidence_kind="structure_element"``.  ``score`` stays ``0.0`` because no
    similarity exists for an element — it is never reported as one;
    ``structural_score`` carries the graph-distance score instead.  Ordering is
    by ``structural_score`` descending, then candidate id, so the result is
    deterministic.
    """
    terms = terms_from_question(question)
    if not terms:
        return []

    matches = await find_element_seed_matches(
        db, user_id, terms, limit=STRUCTURAL_SEED_LIMIT
    )
    seed_ids = [element_id for element_id, _matched in matches]
    if not seed_ids:
        return []

    visited = await expand_element_seeds(db, user_id, seed_ids)
    details = await load_element_candidates(db, user_id, list(visited.keys()))

    candidates: list[SourceChunk] = []
    for element_id, (hops, relation, weight) in visited.items():
        info = details.get(element_id)
        if info is None:
            # Not visible to this user (or a foreign seed).  Dropped rather
            # than reported.
            continue
        path = info["heading_path"]
        content = info["content"] or (" > ".join(path) if path else "")
        if not content or not content.strip():
            continue
        candidates.append(
            SourceChunk(
                chunk_id=f"structure:{info['element_id']}",
                content=content,
                score=0.0,  # not a semantic hit — see the docstring
                document_id=info["document_id"],
                document_name=info["document_name"],
                page=info["page"],
                heading_path=path,
                section=(path[-1] if path else None),
                element_type=info["element_type"],
                token_count=None,
                chunker_version=None,
                retrieval_path=RETRIEVAL_STRUCTURAL,
                fusion_score=None,
                structural_hops=hops,
                structural_relation=relation,
                structural_score=graph_structural_score(hops, weight),
                evidence_kind="structure_element",
            )
        )

    candidates.sort(key=lambda c: (-(c.structural_score or 0.0), c.chunk_id))
    return candidates[:limit]


def fuse_dual_path(
    semantic: list[SourceChunk],
    structural: list[SourceChunk],
    top_k: int,
    *,
    semantic_weight: float = RRF_SEMANTIC_WEIGHT,
    structural_weight: float = RRF_STRUCTURAL_WEIGHT,
    k: int = RRF_K,
) -> list[SourceChunk]:
    """Fuse the two retrieval paths with Reciprocal Rank Fusion.

    ``fusion_score = w_semantic / (k + semantic_rank)
                  + w_structural / (k + structural_rank)``

    with 1-based ranks taken from each path's own ordering.  A chunk found by
    only one path receives only that path's contribution.

    Provenance is explicit:

    * both paths  → ``retrieval_path="hybrid"``
    * semantic only → ``"semantic"``
    * structural only → ``"structural"``, and its ``score`` stays ``0.0``
      because no similarity was ever computed for it.  ``fusion_score`` is a
      separate quantity and is never a stand-in for cosine similarity.

    Ordering is fully deterministic: fused score descending, then semantic
    similarity descending, then chunk id ascending.  At most ``top_k`` chunks
    are returned.
    """
    semantic_rank = {c.chunk_id: i + 1 for i, c in enumerate(semantic)}
    structural_rank = {c.chunk_id: i + 1 for i, c in enumerate(structural)}

    semantic_by_id = {c.chunk_id: c for c in semantic}
    structural_by_id = {c.chunk_id: c for c in structural}

    fused: list[SourceChunk] = []
    for chunk_id in set(semantic_by_id) | set(structural_by_id):
        sem = semantic_by_id.get(chunk_id)
        struct = structural_by_id.get(chunk_id)
        base = sem if sem is not None else struct
        assert base is not None  # one of the two always exists

        sem_r = semantic_rank.get(chunk_id)
        struct_r = structural_rank.get(chunk_id)

        score = 0.0
        if sem_r is not None:
            score += semantic_weight / (k + sem_r)
        if struct_r is not None:
            score += structural_weight / (k + struct_r)

        if sem is not None and struct is not None:
            path = RETRIEVAL_HYBRID
        elif sem is not None:
            # Product callers may supply a dense/lexical fused candidate pool.
            # Do not relabel a lexical-only hit as a measured semantic match.
            path = sem.retrieval_path
        else:
            path = RETRIEVAL_STRUCTURAL

        fused.append(
            replace(
                base,
                retrieval_path=path,
                fusion_score=round(score, 8),
                structural_hops=struct.structural_hops if struct is not None else None,
                structural_relation=(
                    struct.structural_relation if struct is not None else None
                ),
                structural_score=(
                    struct.structural_score if struct is not None else None
                ),
            )
        )

    fused.sort(
        key=lambda c: (-(c.fusion_score or 0.0), -(c.score or 0.0), c.chunk_id)
    )
    return fused[:top_k]


async def retrieve_dual_path(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int = 5,
    *,
    semantic_chunks: list[SourceChunk] | None = None,
) -> list[SourceChunk]:
    """Both retrieval paths plus fusion, as one call.

    ``semantic_chunks`` may be supplied by a caller that already ran the
    semantic path (the Brain adapter does) so the embedding and the vector
    query are not paid for twice.

    The structural path has two granularities that share one ranking stream:
    chunk-level graph candidates (:func:`retrieve_structural_candidates`) and
    persisted structure-element candidates
    (:func:`retrieve_structural_element_candidates`).  Both are ordered by the
    same graph-distance score and fused with the same declared structural
    prior, so an element candidate can enter the final top-k and influence its
    ordering without any fabricated similarity score.

    When the semantic path returns nothing the structural path is still tried:
    a question naming a section can be answered from the section even when no
    chunk is vector-similar to it.  The fused result is then structural-only,
    and the evidence gate treats it accordingly (no fabricated similarity).
    """
    semantic = (
        semantic_chunks
        if semantic_chunks is not None
        else await retrieve_chunks(db, user_id, query, top_k=top_k)
    )

    structural = await retrieve_structural_candidates(
        db,
        user_id,
        query,
        semantic_seed_ids=[c.chunk_id for c in semantic],
        limit=max(STRUCTURAL_CANDIDATE_LIMIT, top_k),
    )

    element_structural = await retrieve_structural_element_candidates(
        db, user_id, query
    )

    # One structural ranking stream: chunk-level and element-level candidates
    # are ordered by the same graph-distance score with the same
    # deterministic tie-break, then fused by rank.
    structural_stream = sorted(
        [*structural, *element_structural],
        key=lambda c: (-(c.structural_score or 0.0), c.chunk_id),
    )

    return fuse_dual_path(semantic, structural_stream, top_k)
