import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.dependencies import CurrentUser
from config import get_settings
from storage.database import get_db
from storage.file_store import save_upload, delete_upload
from documents.models import Document, DocumentChunk
from documents.processing import extract_text, chunk_text
from documents.schemas import (
    DocumentOut,
    DocumentListResponse,
    DocumentDetailResponse,
    ChunkOut,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()

ALLOWED_TYPES = {"pdf", "docx", "txt"}


def _doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        name=doc.name,
        fileType=doc.file_type,
        fileSize=doc.file_size,
        chunkCount=doc.chunk_count,
        status=doc.status,
        embeddingStatus=doc.embedding_status,
        createdAt=doc.created_at.isoformat() if doc.created_at else "",
    )


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a document (PDF/DOCX/TXT)."""
    # Validate file type
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # Read file bytes
    file_bytes = await file.read()

    # Validate file size
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Save file to disk
    stored_path = save_upload(file_bytes, file.filename or f"upload.{ext}")

    # Create document record
    doc = Document(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=file.filename or f"upload.{ext}",
        file_type=ext,
        file_size=len(file_bytes),
        stored_path=str(stored_path),
        status="processing",
        chunk_count=0,
    )
    db.add(doc)
    await db.flush()  # get the ID before chunk inserts

    # Extract text and chunk
    try:
        raw_chunks = extract_text(stored_path, ext)
        text_chunks = chunk_text(raw_chunks)

        for idx, (page_num, content) in enumerate(text_chunks):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                chunk_index=idx,
                content=content,
                page=page_num,
                embedding_id=None,
            )
            db.add(chunk)

        doc.chunk_count = len(text_chunks)
        doc.status = "ready"
    except Exception:
        doc.status = "error"
        doc.chunk_count = 0

    await db.commit()
    await db.refresh(doc)
    return _doc_to_out(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """List all documents for the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return DocumentListResponse(documents=[_doc_to_out(d) for d in docs])


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get document details with chunks."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_out = [
        ChunkOut(
            id=str(c.id),
            chunkIndex=c.chunk_index,
            content=c.content,
            page=c.page,
        )
        for c in sorted(doc.chunks, key=lambda c: c.chunk_index)
    ]

    return DocumentDetailResponse(
        id=str(doc.id),
        name=doc.name,
        fileType=doc.file_type,
        fileSize=doc.file_size,
        chunkCount=doc.chunk_count,
        status=doc.status,
        embeddingStatus=doc.embedding_status,
        createdAt=doc.created_at.isoformat() if doc.created_at else "",
        chunks=chunks_out,
    )


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document, its chunks, and the stored file."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file from disk
    delete_upload(Path(doc.stored_path))

    # Delete from database (chunks cascade)
    await db.delete(doc)
    await db.commit()

    return {"message": "Document deleted successfully"}
