from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from storage.database import get_db
from chat.rag import retrieve_chunks, rag_answer
from chat.qa_model import is_model_available, get_model_status
from reliability.routes import store_query_reliability  # async, takes db=

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    topK: int = 5


class SourceOut(BaseModel):
    chunkId: str
    content: str
    score: float
    documentId: str
    documentName: str
    page: int | None


class ReliabilityEvidence(BaseModel):
    """Real evidence from the RAG pipeline — no fabricated metrics."""
    qaConfidence: float          # QA model confidence score
    retrievalScore: float        # best pgvector similarity score
    avgRetrievalScore: float     # mean of all retrieval scores
    sourceCount: int             # number of retrieved sources
    uniqueDocuments: int         # number of distinct source documents
    factualGrounded: bool        # whether answer span exists in context
    insufficientContext: bool    # retrieval/model flagged insufficient


class AskResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[SourceOut]
    insufficientContext: bool
    question: str
    reliability: ReliabilityEvidence


# ---------------------------------------------------------------------------
# POST /api/chat/ask
# ---------------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Answer a question using RAG over the user's documents."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Check if DocuMind QA model is available
    if not is_model_available():
        status = get_model_status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DocuMind QA model is not available",
                "message": status.get("error", "Unknown error"),
                "model_path": status.get("model_path"),
            },
        )

    # 1. Retrieve relevant chunks
    chunks = await retrieve_chunks(
        db=db,
        user_id=str(current_user.id),
        query=body.question,
        top_k=body.topK,
    )

    # 2. Run RAG answer
    result = rag_answer(body.question, chunks)

    # 3. Build response with real reliability evidence
    sources = [
        SourceOut(
            chunkId=c.chunk_id,
            content=c.content,
            score=round(max(0.0, c.score), 4),
            documentId=c.document_id,
            documentName=c.document_name,
            page=c.page,
        )
        for c in result.sources
    ]

    reliability = ReliabilityEvidence(
        qaConfidence=result.confidence,
        retrievalScore=result.best_retrieval_score,
        avgRetrievalScore=result.avg_retrieval_score,
        sourceCount=result.source_count,
        uniqueDocuments=result.unique_documents,
        factualGrounded=result.factual_grounded,
        insufficientContext=result.insufficient_context,
    )

    # 4. Store reliability data for the Reliability Center page
    reliability_evidence = {
        "question": body.question,
        "answer": result.answer,
        "qaConfidence": result.confidence,
        "retrievalScore": result.best_retrieval_score,
        "avgRetrievalScore": result.avg_retrieval_score,
        "sourceCount": result.source_count,
        "uniqueDocuments": result.unique_documents,
        "factualGrounded": result.factual_grounded,
        "insufficientContext": result.insufficient_context,
        "sources": [
            {
                "id": c.chunk_id,
                "documentId": c.document_id,
                "documentName": c.document_name,
                "content": c.content[:200],
                "relevanceScore": round(max(0.0, c.score), 4),
                "page": c.page,
                "status": "VERIFIED" if c.score >= 0.5 else ("MARGINAL" if c.score >= 0.3 else "UNRESOLVED"),
            }
            for c in result.sources
        ],
    }
    await store_query_reliability(str(current_user.id), reliability_evidence, db=db)

    return AskResponse(
        answer=result.answer,
        confidence=result.confidence,
        sources=sources,
        insufficientContext=result.insufficient_context,
        question=body.question,
        reliability=reliability,
    )
