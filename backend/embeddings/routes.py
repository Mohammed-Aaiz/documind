"""
Embedding generation and semantic search endpoints.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from auth.dependencies import CurrentUser
from documents.models import Document, DocumentChunk
from embeddings.model import embed_texts, embed_query, get_embedding_descriptor, compatible_embedding_labels
from storage.database import get_db

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EmbedRequest(BaseModel):
    documentId: str


class EmbedResponse(BaseModel):
    message: str
    documentId: str
    chunksEmbedded: int


class SearchRequest(BaseModel):
    query: str
    topK: int = 5


class SearchResult(BaseModel):
    chunkId: str
    content: str
    score: float
    documentId: str
    documentName: str
    page: int | None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


# ---------------------------------------------------------------------------
# POST /api/embeddings/generate  — Generate embeddings for a document
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=EmbedResponse, status_code=status.HTTP_200_OK)
async def generate_embeddings(
    body: EmbedRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate embeddings for all chunks of a document."""
    # Verify document exists and belongs to user
    result = await db.execute(
        select(Document).where(
            Document.id == body.documentId,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get all chunks for this document
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(result.scalars().all())
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no chunks")

    # Set status to processing
    doc.embedding_status = "processing"
    await db.flush()

    try:
        # Generate embeddings for all chunks
        texts = [c.content for c in chunks]
        embeddings = await run_in_threadpool(embed_texts, texts)
        descriptor = get_embedding_descriptor()

        # Store embeddings back to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        doc.embedding_status = "ready"
        doc.embedding_model = descriptor["identityKey"]
        await db.commit()

        return EmbedResponse(
            message="Embeddings generated successfully",
            documentId=body.documentId,
            chunksEmbedded=len(chunks),
        )
    except HTTPException:
        raise
    except Exception:
        # The full exception is logged server-side only.  The client receives a
        # fixed message: the try block spans model inference *and*
        # ``await db.commit()``, so the exception can carry third-party ML,
        # filesystem, network or database-driver detail that must not be
        # disclosed.  Matches the convention in ``backend/voice.py``.
        logger.exception(
            "Embedding generation failed for document %s", doc.id
        )
        doc.embedding_status = "error"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding generation failed",
        )


# ---------------------------------------------------------------------------
# POST /api/embeddings/search  — Semantic search across user's documents
# ---------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    body: SearchRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across all embedded chunks belonging to the user."""
    # Generate query embedding
    query_embedding = await run_in_threadpool(embed_query, body.query)
    embedding_models = compatible_embedding_labels()

    # Use pgvector cosine distance to find the most similar chunks.
    # Only search chunks that belong to documents owned by the current user
    # and whose documents have embedding_status = 'ready'.
    #
    # The embedding vector is passed as a string parameter and cast to
    # pgvector's `vector` type in the SQL.  All other values use standard
    # SQLAlchemy parameter binding — no f-string interpolation of user
    # input.
    emb_str = str(query_embedding)

    # NOTE: CAST(:embedding AS vector) instead of :embedding::vector
    # because asyncpg treats `:embedding::vector` as a single parameter name.
    search_sql = text(
        "SELECT"
        "  dc.id as chunk_id,"
        "  dc.content,"
        "  dc.document_id,"
        "  d.name as document_name,"
        "  dc.page,"
        "  1 - (dc.embedding <=> CAST(:embedding AS vector)) as similarity"
        " FROM document_chunks dc"
        " JOIN documents d ON d.id = dc.document_id"
        " WHERE d.user_id = :user_id"
        "   AND d.embedding_status = 'ready'"
        "   AND d.embedding_model = ANY(CAST(:embedding_models AS text[]))"
        "   AND dc.embedding IS NOT NULL"
        " ORDER BY dc.embedding <=> CAST(:embedding AS vector)"
        " LIMIT :top_k"
    )

    result = await db.execute(
        search_sql,
        {"embedding": emb_str, "user_id": str(current_user.id), "top_k": body.topK,
         "embedding_models": list(embedding_models)},
    )
    rows = result.fetchall()

    results = [
        SearchResult(
            chunkId=str(row.chunk_id),
            content=row.content,
            score=round(float(row.similarity), 4),
            documentId=str(row.document_id),
            documentName=row.document_name,
            page=row.page,
        )
        for row in rows
    ]

    return SearchResponse(query=body.query, results=results)
