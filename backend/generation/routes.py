"""Stateless Groq answering with authenticated retrieval and source verification.

No evidence returns an explicit abstention; provider failures return a sanitized
503. Unsupported claims are omitted with a warning only when the remaining
answer passes verification again; otherwise the answer is withheld.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from chat.rag import dual_path_enabled
from chat.routes import SourceOut
from generation.providers import provider_status
from generation.service import persist_generation, run_generation
from generation.types import AnswerFormat, GenerationUnavailableError
from storage.database import get_db

router = APIRouter(prefix="/api/generation", tags=["generation"])

MAX_QUESTION_CHARS = 2000


class GenerateRequest(BaseModel):
    question: str
    topK: int = Field(default=5, ge=1, le=20)
    answerFormat: str = Field(default="10", description="Academic answer format: 5, 10 or 15 marks.")


class GenerationVerification(BaseModel):
    claimCount: int
    supportedClaims: int
    unsupportedClaims: list[str]
    uncitedClaims: int
    citationAccuracy: float
    verified: bool
    #: Answer-level state: SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED |
    #: INSUFFICIENT_EVIDENCE.  ``verified`` means the first of those only.
    status: str = "UNSUPPORTED"
    #: Claims whose numeric value belongs to a different entity than the
    #: question asks about (the measured wrong-entity failure).
    wrongEntityClaims: list[str] = []


class GenerateResponse(BaseModel):
    answer: str
    engine: str = "groq"
    model: str
    answerFormat: str
    marks: int
    latencyMs: int
    abstained: bool
    insufficientContext: bool
    question: str
    sources: list[SourceOut]
    verification: GenerationVerification
    warnings: list[str]
    pipelineVersion: str


@router.post("/answer", response_model=GenerateResponse)
async def generate_answer(
    body: GenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Answer a question using Groq and the shared evidence retrieval pipeline."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Question exceeds {MAX_QUESTION_CHARS} characters",
        )

    try:
        answer_format = AnswerFormat.coerce(body.answerFormat)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_id = str(current_user.id)

    # Share the retrieval and provider infrastructure with workspace chat.
    try:
        chunks, result = await run_generation(
            db, user_id, question, body.topK, answer_format
        )
    except GenerationUnavailableError as exc:
        status = provider_status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "The Groq answer provider is unavailable",
                "message": str(exc),
                "model": status.get("model"),
            },
        ) from exc

    verification = GenerationVerification(**result.verification)

    sources = [
        SourceOut(
            chunkId=chunk.chunk_id,
            content=chunk.content,
            score=round(max(0.0, float(getattr(chunk, "score", 0.0) or 0.0)), 4),
            documentId=chunk.document_id,
            documentName=chunk.document_name,
            page=chunk.page,
            headingPath=list(chunk.heading_path) if chunk.heading_path else None,
            section=chunk.section,
            elementType=chunk.element_type,
            tokenCount=chunk.token_count,
            chunkerVersion=chunk.chunker_version,
            retrievalPath=chunk.retrieval_path,
            fusionScore=chunk.fusion_score,
            structuralHops=chunk.structural_hops,
            evidenceKind=chunk.evidence_kind,
            tableElementId=chunk.table_element_id,
            rowIndex=chunk.row_index,
            headerRepeated=chunk.header_repeated,
        )
        for chunk in chunks
    ]

    pipeline_version = "generative-dual-path-v1" if dual_path_enabled() else "generative-semantic-v1"
    await persist_generation(db, user_id, question, chunks, result, answer_format)

    return GenerateResponse(
        answer=result.answer,
        model=result.model,
        answerFormat=answer_format.value,
        marks=result.marks,
        latencyMs=result.latency_ms,
        abstained=result.abstained,
        insufficientContext=result.insufficient_context,
        question=question,
        sources=sources,
        verification=verification,
        warnings=result.warnings,
        pipelineVersion=pipeline_version,
    )
