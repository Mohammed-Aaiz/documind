"""Document upload, management, and reprocessing routes.

Phase 3E processing lifecycle rules:

  READY means actually searchable and complete.
  A document is READY only after extraction, chunking, AND embedding
  all succeed.  There is no degraded-ready state.

  PROCESSING — extraction/chunking/embedding in progress
  READY      — fully processed, searchable
  ERROR      — processing failed at any stage

  Reprocessing: a failed document can be reprocessed without
  manual delete + re-upload.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.dependencies import CurrentUser
from config import get_settings
from storage.database import get_db
from storage.file_store import save_upload, delete_upload, cleanup_new_file
from documents.models import Document, DocumentChunk
from documents.processing import extract_text, chunk_text, PARSER_VERSIONS
from documents.chunking import (
    CHUNKER_VERSION_STRUCTURE,
    chunk_elements,
    resolve_chunker_version,
)
from tokenization import count_tokens
from documents.schemas import (
    DocumentOut,
    DocumentListResponse,
    DocumentDetailResponse,
    ChunkOut,
)
from documents.validation import (
    validate_file_bytes,
    compute_content_hash,
    sanitize_filename,
)
from embeddings.model import embed_texts, _MODEL_NAME as EMBEDDING_MODEL_NAME

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()

ALLOWED_TYPES = {"pdf", "docx", "txt"}

# Stale processing threshold: documents stuck in "processing" for longer
# than this are considered stale and recoverable via reprocessing.
_STALE_PROCESSING_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _build_chunk_objects(
    elements,
    document_id,
    chunker_version: str,
    db: AsyncSession,
) -> list[DocumentChunk]:
    """Create (but do not flush) ``DocumentChunk`` rows for a document.

    Two strategies are available and both record their version so a corpus
    can never mix strategies unlabelled:

    * legacy (default) -- ``documents.processing.chunk_text``, 1000 chars with
      200 chars of blind overlap.  Content and ordering are unchanged; the
      Phase 3D metadata columns are left NULL except for the version, and
      ``token_count`` is recorded purely so the encoder-truncation metric can
      be computed for the baseline.
    * structure-v2 -- ``documents.chunking.chunk_elements``, section/page
      scoped, token budgeted, with heading/list/table structure preserved.
    """
    chunk_objects: list[DocumentChunk] = []

    if chunker_version == CHUNKER_VERSION_STRUCTURE:
        for idx, chunk in enumerate(chunk_elements(elements, version=chunker_version)):
            obj = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=idx,
                content=chunk.content,
                page=chunk.meta.page,
                embedding_id=None,
                heading_path=list(chunk.meta.heading_path) or None,
                section=chunk.meta.section,
                element_type=chunk.meta.element_type,
                chunker_version=chunk.meta.chunker_version,
                token_count=chunk.meta.token_count,
            )
            db.add(obj)
            chunk_objects.append(obj)
        return chunk_objects

    for idx, (page_num, content) in enumerate(chunk_text(elements)):
        obj = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=idx,
            content=content,
            page=page_num,
            embedding_id=None,
            chunker_version=chunker_version,
            token_count=count_tokens(content),
        )
        db.add(obj)
        chunk_objects.append(obj)

    return chunk_objects


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


async def _process_document(
    doc: Document,
    stored_path: Path,
    file_type: str,
    db: AsyncSession,
) -> None:
    """Run the full processing pipeline for a document.

    Phase 3E: status is ONLY set to READY after all steps succeed.
    The document remains PROCESSING throughout the pipeline.

    On any failure, status becomes ERROR.
    """
    now = _now_utc()
    doc.status = "processing"
    doc.processing_started_at = now
    doc.updated_at = now
    doc.embedding_status = "pending"
    doc.chunk_count = 0
    await db.flush()

    try:
        # --- Step 1: Extract text ---
        try:
            elements = extract_text(stored_path, file_type)
        except Exception:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return

        if not elements:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return

        # --- Step 2: Chunk ---
        chunker_version = resolve_chunker_version(settings.chunker_version)
        try:
            chunk_objects = _build_chunk_objects(elements, doc.id, chunker_version, db)
        except Exception:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return

        if not chunk_objects:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return

        doc.chunker_version = chunker_version
        doc.parser_version = PARSER_VERSIONS.get(file_type, file_type)
        doc.chunk_count = len(chunk_objects)
        doc.embedding_status = "processing"
        doc.updated_at = _now_utc()
        await db.flush()  # persist chunks so we can update embeddings

        # --- Step 3: Generate embeddings ---
        try:
            texts = [c.content for c in chunk_objects]
            embeddings = embed_texts(texts)
            for chunk, embedding in zip(chunk_objects, embeddings):
                chunk.embedding = embedding
        except Exception:
            # Embedding failed -- document is NOT ready.
            # Chunks exist but have no vectors; set ERROR.
            doc.status = "error"
            doc.embedding_status = "error"
            doc.updated_at = _now_utc()
            return

        # --- Step 4: All steps succeeded -- READY ---
        doc.embedding_model = EMBEDDING_MODEL_NAME
        doc.embedding_status = "ready"
        doc.status = "ready"
        doc.updated_at = _now_utc()

    except Exception:
        # Catch-all for unexpected failures
        doc.status = "error"
        doc.embedding_status = "error"
        doc.chunk_count = 0
        doc.updated_at = _now_utc()


def _is_stale_processing(doc: Document) -> bool:
    """Check if a document is stuck in PROCESSING state."""
    if doc.status != "processing":
        return False
    if doc.processing_started_at is None:
        return True
    elapsed = (_now_utc() - doc.processing_started_at).total_seconds()
    return elapsed > _STALE_PROCESSING_SECONDS


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a document (PDF/DOCX/TXT).

    Phase 3E hardened upload:
    - Magic-byte / signature validation (not just extension)
    - MIME cross-check via content inspection
    - SHA-256 content hash for deduplication
    - User-scoped filesystem storage
    - Filename sanitization
    - Duplicate detection (same user + same content)
    - Orphan cleanup on DB failure
    - READY only set after embedding succeeds
    - ERROR on any pipeline failure
    - Stale PROCESSING detection for re-uploads
    """
    # --- 1. Read file bytes ---
    file_bytes = await file.read()

    # --- 2. Validate file size ---
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )

    # --- 3. Validate extension ---
    declared_ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if declared_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{declared_ext}'. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # --- 4. Validate file content (magic bytes + MIME) ---
    validation = validate_file_bytes(file_bytes, declared_ext)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {validation.error}",
        )

    # Use validated type (content-confirmed, not just extension-claimed)
    file_type = validation.file_type

    # --- 5. Compute content hash ---
    content_hash = compute_content_hash(file_bytes)

    # --- 6. Sanitize filename ---
    safe_name = sanitize_filename(file.filename or f"upload.{file_type}")

    # --- 7. Duplicate detection (same user + same content) ---
    existing = await db.execute(
        select(Document).where(
            Document.user_id == current_user.id,
            Document.content_hash == content_hash,
        )
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc is not None:
        # Phase 3E: if the existing document is ERROR, allow reprocessing
        # by re-running the pipeline on the existing file.
        if existing_doc.status == "error":
            await _process_document(
                existing_doc, Path(existing_doc.stored_path), existing_doc.file_type, db
            )
            await db.commit()
            await db.refresh(existing_doc)
            return _doc_to_out(existing_doc)
        # If PROCESSING and stale, allow reprocessing
        if _is_stale_processing(existing_doc):
            await _process_document(
                existing_doc, Path(existing_doc.stored_path), existing_doc.file_type, db
            )
            await db.commit()
            await db.refresh(existing_doc)
            return _doc_to_out(existing_doc)
        # READY or PROCESSING (not stale): return existing
        return _doc_to_out(existing_doc)

    # --- 8. Save file to user-scoped storage ---
    stored_path = save_upload(file_bytes, safe_name, str(current_user.id))

    # --- 9. Create document record ---
    doc = Document(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=safe_name,
        file_type=file_type,
        file_size=len(file_bytes),
        stored_path=str(stored_path),
        content_hash=content_hash,
        status="processing",
        chunk_count=0,
        processing_started_at=_now_utc(),
    )
    db.add(doc)

    try:
        await db.flush()  # get the ID before processing
    except Exception:
        # DB flush failed -- clean up the newly-created file
        cleanup_new_file(stored_path)
        raise

    # --- 10. Run full pipeline ---
    await _process_document(doc, stored_path, file_type, db)

    # --- 11. Commit or clean up ---
    try:
        await db.commit()
    except Exception:
        # DB commit failed -- clean up the newly-created file
        cleanup_new_file(stored_path)
        raise

    await db.refresh(doc)
    return _doc_to_out(doc)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document, its chunks, and the stored file.

    Phase 3E: DB transaction is committed FIRST, then the file is removed.
    If file deletion fails, the DB is already clean -- the orphaned file
    can be cleaned up later.  If DB commit fails, the file is NOT deleted
    (reversing the old ordering that risked a missing-file + intact-DB).
    """
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_path = Path(doc.stored_path)

    # Phase 3E: commit DB first, then remove file.
    await db.delete(doc)
    await db.commit()

    # File removal is best-effort after DB commit.
    delete_upload(stored_path)

    return {"message": "Document deleted successfully"}


# ---------------------------------------------------------------------------
# Reprocess
# ---------------------------------------------------------------------------


@router.post("/{document_id}/reprocess", response_model=DocumentOut)
async def reprocess_document(
    document_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Reprocess an existing document.

    Phase 3E: allows recovering from ERROR or stale PROCESSING states
    without forcing the user to delete and re-upload.

    Behaviour:
    - ERROR document: re-run the full pipeline
    - PROCESSING (stale): re-run the full pipeline
    - READY document: re-run the full pipeline (user chose to re-index)
    - PROCESSING (not stale): reject (already in progress)

    Reprocessing replaces all chunks and embeddings.  The document
    identity, content_hash, and stored file are preserved.
    """
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # If currently processing and NOT stale, reject
    if doc.status == "processing" and not _is_stale_processing(doc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is currently being processed",
        )

    stored_path = Path(doc.stored_path)
    if not stored_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source file no longer exists on disk; cannot reprocess",
        )

    # Phase 3E: delete old chunks before reprocessing to prevent mixing
    # old chunks with new embeddings.
    for chunk in list(doc.chunks):
        await db.delete(chunk)
    doc.chunk_count = 0
    doc.embedding_status = "pending"
    await db.flush()

    # Run the full pipeline
    await _process_document(doc, stored_path, doc.file_type, db)

    await db.commit()
    await db.refresh(doc)
    return _doc_to_out(doc)
