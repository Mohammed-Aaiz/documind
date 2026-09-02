"""
Embedding generation and semantic search endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from documents.models import Document, DocumentChunk
from embeddings.model import embed_texts, embed_query
from storage.database import get_db

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


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
        embeddings = embed_texts(texts)

        # Store embeddings back to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        doc.embedding_status = "ready"
        await db.commit()

        return EmbedResponse(
            message="Embeddings generated successfully",
            documentId=body.documentId,
            chunksEmbedded=len(chunks),
        )
    except Exception as e:
        doc.embedding_status = "error"
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Embedding generation failed: {str(e)}",
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
    query_embedding = embed_query(body.query)

    # Use pgvector cosine distance to find the most similar chunks
    # Only search chunks that belong to documents owned by the current user
    # and whose documents have embedding_status = 'ready'
    # Note: vector is interpolated directly because SQLAlchemy's :param
    # syntax conflicts with PostgreSQL's ::type cast syntax.
    emb_str = str(query_embedding)
    user_id_str = str(current_user.id)

    search_sql = text(
        f"SELECT"
        f"  dc.id as chunk_id,"
        f"  dc.content,"
        f"  dc.document_id,"
        f"  d.name as document_name,"
        f"  dc.page,"
        f"  1 - (dc.embedding <=> '{emb_str}'::vector) as similarity"
        f" FROM document_chunks dc"
        f" JOIN documents d ON d.id = dc.document_id"
        f" WHERE d.user_id = '{user_id_str}'"
        f"   AND d.embedding_status = 'ready'"
        f"   AND dc.embedding IS NOT NULL"
        f" ORDER BY dc.embedding <=> '{emb_str}'::vector"
        f" LIMIT {body.topK}"
    )

    result = await db.execute(search_sql)
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
