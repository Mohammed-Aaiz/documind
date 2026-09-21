"""
Real service adapters for the DocuMind Brain.

Each adapter bridges a Brain type contract to an existing service function.
Adapters live at the API boundary — they receive infrastructure objects
(db session) from the route handler and translate between Brain types
and service contracts.

The Brain itself never sees database sessions, SQL, or model internals.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from brain.executor import CapabilityRegistry
from brain.types import Capability, ModelUnavailableError, QaResult, SourceRef
from chat.rag import retrieve_chunks, build_qa_context, SourceChunk
from chat.qa_model import answer_question, is_model_available


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
    """Adapt chat/rag.py → retrieve_chunks() to Brain type contract.

    Translates SourceChunk (service type) → SourceRef (Brain type).
    """
    chunks: list[SourceChunk] = await retrieve_chunks(
        db=db,
        user_id=user_id,
        query=cleaned_text,
        top_k=top_k,
    )
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

    Returns a :class:`~chat.rag.ContextPack`, which *is* a ``str`` (so the QA
    step and every existing consumer are unaffected) and additionally reports
    which sources the context actually contains.  Phase 3D: the context is
    sized in tokens against the QA model's real input window instead of the
    legacy 4000-character budget, which the model silently truncated.
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
