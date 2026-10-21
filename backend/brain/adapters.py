"""
Real service adapters for the DocuMind Brain.

Each adapter bridges a Brain type contract to an existing service function.
Adapters live at the API boundary — they receive infrastructure objects
(db session) from the route handler and translate between Brain types
and service contracts.

The Brain itself never sees database sessions, SQL, or model internals.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from brain.executor import CapabilityRegistry
from brain.types import Capability, ModelUnavailableError, QaResult, SourceRef
from chat.rag import (
    build_qa_context,
    dual_path_enabled,
    order_evidence_bands,
    retrieve_chunks,
    retrieve_dual_path,
    retrieve_table_row_evidence,
    table_evidence_enabled,
    SourceChunk,
)
from chat.qa_model import answer_question, is_model_available
from graph.evidence import (
    EvidenceItem,
    FusedEvidence,
    collect_document_structure_evidence,
    evidence_from_source_chunk,
    fuse_evidence,
)

#: Maximum structural elements contributed per source document (bounds the
#: structure stream fed to fusion; document order, never a whole-graph scan).
STRUCTURE_EVIDENCE_PER_DOCUMENT = 20

#: Maximum distinct source documents enriched with structural evidence.
STRUCTURE_EVIDENCE_MAX_DOCUMENTS = 5

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structural evidence augmentation (Feature #13)
# ---------------------------------------------------------------------------

async def _augment_with_structure(
    db: AsyncSession,
    chunks: list[SourceChunk],
) -> list[SourceChunk]:
    """Append bounded, document-scoped structural evidence to retrieved chunks.

    There is no persisted chunk->structure mapping, so structural evidence is
    kept as a **separate stream** (per the Feature #12 contract) rather than
    guessed onto individual chunks.  Fusion goes through the existing
    :func:`graph.evidence.fuse_evidence`, so deduplication, ordering and
    document isolation are reused rather than reimplemented.

    Element candidates that already entered the ranked dual-path result
    (``chat.rag.retrieve_structural_element_candidates``) are never appended a
    second time: their ``structure:<uuid>`` id is already present, so this
    stream only contributes elements the ranked path did not select.

    Safety properties:

    * **No-op without structure rows** — a document with no
      ``document_structure_elements`` contributes nothing, so semantic-only
      behaviour is byte-for-byte unchanged.
    * **Document-scoped** — elements are fetched by the ``document_id`` of a
      chunk the user's own retrieval already returned; there is no unscoped
      ``SELECT`` over the structure table.
    * **Bounded** — one query per source document (never per chunk), capped by
      ``STRUCTURE_EVIDENCE_PER_DOCUMENT`` and ``STRUCTURE_EVIDENCE_MAX_DOCUMENTS``.
    * **Enhancement, not dependency** — any failure is logged and the semantic
      result is returned unchanged, so QA never breaks because structure is
      unavailable.
    * **No fabricated score** — structural chunks carry ``score=0.0`` and
      ``retrieval_path="structural"`` (the project's existing convention for
      structural chunk evidence, matching ``chat.rag.retrieve_structural_candidates``);
      they are never reported as a semantic similarity.
    """
    if not chunks:
        return chunks

    # Group by document, preserving first-seen order.
    by_document: dict[str, list[SourceChunk]] = {}
    for chunk in chunks:
        by_document.setdefault(chunk.document_id, []).append(chunk)

    augmented = list(chunks)
    ranked_ids = {c.chunk_id for c in chunks}
    for document_id in list(by_document)[:STRUCTURE_EVIDENCE_MAX_DOCUMENTS]:
        try:
            structural_items = await collect_document_structure_evidence(
                db,
                [document_id],
                per_document_limit=STRUCTURE_EVIDENCE_PER_DOCUMENT,
            )
        except Exception:
            logger.exception(
                "structural evidence collection failed for document %s; "
                "continuing with semantic evidence only",
                document_id,
            )
            continue

        if not structural_items:
            continue

        # Fuse through the Feature #12 layer (semantic stream is empty here
        # because structural evidence is an independent stream; the call still
        # gives deterministic ordering, dedup and document isolation).
        fused: FusedEvidence = fuse_evidence(
            semantic_evidence=[],
            structural_evidence=structural_items,
        )

        document_name = by_document[document_id][0].document_name
        for item in fused.structural_items():
            element_chunk_id = f"structure:{item.structure_element_id}"
            if element_chunk_id in ranked_ids:
                # Already a ranked candidate from the dual path — appending it
                # again would duplicate the evidence identity.
                continue
            content = item.content or (
                " > ".join(item.heading_path) if item.heading_path else ""
            )
            if not content or not content.strip():
                continue
            augmented.append(
                SourceChunk(
                    chunk_id=element_chunk_id,
                    content=content,
                    score=0.0,  # no similarity exists for structure (see docstring)
                    document_id=item.document_id,
                    document_name=document_name,
                    page=item.page_number,
                    heading_path=item.heading_path,
                    section=item.section,
                    element_type=item.element_type,
                    retrieval_path="structural",
                    structural_hops=item.provenance.get("hops"),
                    structural_relation=item.provenance.get("relation"),
                    # Distinguishes this element-level evidence from chunk-level
                    # structural retrieval, which both report retrieval_path
                    # "structural".
                    evidence_kind="structure_element",
                )
            )

    return augmented


# ---------------------------------------------------------------------------
# Retrieval adapter
# ---------------------------------------------------------------------------

async def retrieval_adapter(
    *,
    db: AsyncSession,
    user_id: str,
    cleaned_text: str,
    top_k: int = 5,
) -> list[SourceRef]:
    """Adapt chat/rag.py retrieval to the Brain type contract.

    Translates SourceChunk (service type) → SourceRef (Brain type).

    Dual-path: the semantic result is always computed first (unchanged
    ``retrieve_chunks``), then the structural path runs and the two are fused.
    Two guards keep existing callers intact:

    * when there is no database session (``db is None``) the structural path
      cannot run — graph traversal *is* a query — so the semantic result is
      returned unchanged;
    * ``DOCUMIND_DUAL_PATH_RAG`` can switch the structural path off entirely,
      which restores the original single-path behaviour.

    Phase 3 (additive): when ``DOCUMIND_TABLE_EVIDENCE`` is enabled **and** the
    question names a persisted table dimension, compact row evidence is inserted
    between the ranked chunks and the unranked structure-element tail.  The ranked
    bands are untouched — same chunks, same order, same identities — and with the
    switch off (the default) nothing is added, so the evidence stream and the QA
    context are byte-for-byte the previous baseline.
    """
    semantic: list[SourceChunk] = await retrieve_chunks(
        db=db,
        user_id=user_id,
        query=cleaned_text,
        top_k=top_k,
    )

    chunks: list[SourceChunk] = semantic
    if db is not None and dual_path_enabled():
        chunks = await retrieve_dual_path(
            db=db,
            user_id=user_id,
            query=cleaned_text,
            top_k=top_k,
            semantic_chunks=semantic,
        )
        # Feature #13: append the document-scoped structural evidence stream.
        # A no-op when the documents have no persisted structure elements.
        chunks = await _augment_with_structure(db, chunks)

    # Phase 3: query-gated compact table-row evidence, additive and inert by
    # default.  Ordering is explicit: ranked chunks → table rows → element tail.
    if db is not None and table_evidence_enabled():
        table_evidence = await retrieve_table_row_evidence(
            db,
            user_id,
            question=cleaned_text,
            chunks=chunks,
        )
        if table_evidence:
            chunks = order_evidence_bands(chunks, table_evidence)

    return [
        SourceRef(
            chunk_id=c.chunk_id,
            content=c.content,
            score=c.score,
            document_id=c.document_id,
            document_name=c.document_name,
            page=c.page,
            # Phase 3D structure metadata travels with the evidence.
            heading_path=c.heading_path,
            section=c.section,
            element_type=c.element_type,
            token_count=c.token_count,
            chunker_version=c.chunker_version,
            # Dual-path provenance travels with the evidence too.
            retrieval_path=c.retrieval_path,
            fusion_score=c.fusion_score,
            structural_hops=c.structural_hops,
            structural_relation=c.structural_relation,
            structural_score=c.structural_score,
            # "chunk" for semantic / chunk-level structural / hybrid evidence,
            # "structure_element" for the element-level structural stream,
            # "table_row" for the gated compact table-evidence band.
            evidence_kind=getattr(c, "evidence_kind", "chunk"),
            # Table-row provenance (None for every other evidence kind).
            table_element_id=getattr(c, "table_element_id", None),
            row_index=getattr(c, "row_index", None),
            header_repeated=getattr(c, "header_repeated", None),
        )
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# Context building adapter
# ---------------------------------------------------------------------------

async def context_adapter(
    *,
    retrieval_sources: list[SourceRef] | None = None,
    cleaned_text: str = "",
    budget_tokens: int | None = None,
):
    """Adapt chat/rag.py → build_qa_context() to the Brain type contract.

    Phase (GraphRAG): the dual-path provenance on each source is carried through
    unchanged, so the context pack and everything downstream still know which
    path produced each chunk.

    Returns a :class:`~chat.rag.ContextPack`, which *is* a ``str`` (so the QA
    step and every existing consumer are unaffected) and additionally reports
    which sources the context actually contains.  Phase 3D: the context is
    sized in tokens against the QA model's real input window instead of the
    legacy 4000-character budget, which the model silently truncated.

    Phase 3: the incoming source order already encodes the three evidence bands
    (ranked chunks, gated table rows, unranked structure-element tail), so the
    context builder is not changed at all — it fills its budget in that order and
    skips (never truncates) any later item that does not fit whole.
    """
    if not retrieval_sources:
        return ""

    # build_qa_context expects SourceChunk objects — build lightweight
    # adapters that duck-type the fields it reads, carrying the Phase 3D
    # structure metadata through unchanged.
    service_chunks = [
        SourceChunk(
            chunk_id=s.chunk_id,
            content=s.content,
            score=s.score,
            document_id=s.document_id,
            document_name=s.document_name,
            page=s.page,
            heading_path=s.heading_path,
            section=s.section,
            element_type=s.element_type,
            token_count=s.token_count,
            chunker_version=s.chunker_version,
            retrieval_path=s.retrieval_path,
            fusion_score=s.fusion_score,
            structural_hops=s.structural_hops,
            structural_relation=s.structural_relation,
            structural_score=s.structural_score,
            # Evidence granularity and table-row provenance must survive the
            # adapter: the context bands are ordered by evidence_kind.
            evidence_kind=getattr(s, "evidence_kind", "chunk"),
            table_element_id=getattr(s, "table_element_id", None),
            row_index=getattr(s, "row_index", None),
            header_repeated=getattr(s, "header_repeated", None),
        )
        for s in retrieval_sources
    ]
    return build_qa_context(
        service_chunks,
        cleaned_text,
        budget_tokens=budget_tokens,
    )


# ---------------------------------------------------------------------------
# QA adapter
# ---------------------------------------------------------------------------

async def qa_adapter(
    *,
    cleaned_text: str = "",
    context: str = "",
) -> QaResult:
    """Adapt chat/qa_model.py → answer_question() to Brain type contract.

    Translates dict (service contract) → QaResult (Brain type).

    Raises:
        ModelUnavailableError: when the DocuMind QA model cannot be loaded.
            This is classified as ``model_unavailable`` by the executor and
            mapped to ``Outcome.UNAVAILABLE``, so the API returns an honest 503
            instead of a 200 carrying an empty answer.
    """
    if not is_model_available():
        raise ModelUnavailableError(
            "DocuMind QA model is not available (see /api/health for status)."
        )

    result: dict = answer_question(cleaned_text, context)
    return QaResult(
        answer=result["answer"],
        score=result["score"],
        start=result["start"],
        end=result["end"],
    )


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------

def create_registry(db: AsyncSession) -> CapabilityRegistry:
    """Create a CapabilityRegistry wired to real service adapters.

    The db session is captured in the adapter closures — the Brain
    itself never receives or stores database connections.
    """
    registry = CapabilityRegistry()

    async def _retrieval(**kwargs: Any) -> list[SourceRef]:
        return await retrieval_adapter(db=db, **kwargs)

    async def _context(**kwargs: Any) -> str:
        return await context_adapter(**kwargs)

    async def _qa(**kwargs: Any) -> QaResult:
        return await qa_adapter(**kwargs)

    registry.register(Capability.DOCUMENT_RETRIEVAL, _retrieval)
    registry.register(Capability.CONTEXT_BUILDING, _context)
    registry.register(Capability.QA_ANSWER, _qa)

    return registry
