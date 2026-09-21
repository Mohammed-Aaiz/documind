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
import math
import re
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from embeddings.model import embed_query
from chat.qa_model import (
    answer_question,
    count_input_tokens,
    count_text_tokens,
    get_max_input_length,
    is_model_available,
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
) -> list[SourceChunk]:
    """Retrieve the most relevant chunks from the user's documents."""
    query_embedding = embed_query(query)
    emb_str = str(query_embedding)

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
