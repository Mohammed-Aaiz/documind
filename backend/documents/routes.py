"""Document upload, management, and reprocessing routes.

Processing lifecycle rules (Phase 1a; gate 4 approved 2026-10-15):

  READY means actually searchable and *complete*: every page of the source
  document produced usable content (or the format has no pages), and
  extraction, chunking, embedding, structure and graph all succeeded.
  A document with unaccounted pages is never READY.

  PROCESSING — extraction/chunking/embedding in progress
  READY      — fully processed, every page accounted for, searchable
  PARTIAL    — searchable, but at least one page produced no usable content
               (no text layer, or extraction of that page failed).  The
               incompleteness is stated here instead of being hidden behind a
               READY status; the document's own page-coverage facts are the
               only evidence for this verdict (§7.2.1).
  ERROR      — no page produced usable content, or any stage failed

  There is still no "degraded ready": PARTIAL is not READY, and an ERROR is
  never reported as success.

  Reprocessing: a failed, partial or stale document can be reprocessed
  without manual delete + re-upload.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.dependencies import CurrentUser
from config import get_settings
from storage.database import get_db
from storage.file_store import save_upload, delete_upload, cleanup_new_file
from documents.models import Document, DocumentChunk
from documents.processing import (
    extract_document,
    chunk_text,
    PARSER_VERSIONS,
    PageCoverage,
)
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
    DocumentInsightsResponse,
    ChunkOut,
)
from documents.validation import (
    validate_file_bytes,
    compute_content_hash,
    sanitize_filename,
)
from documents.insights import compute_document_insights
from documents.parser import parse_pdf
from documents.structure import replace_document_structure
from embeddings.model import embed_texts, _MODEL_NAME as EMBEDDING_MODEL_NAME
from graph.models import DocumentStructureElement
from graph.service import ChunkView, replace_document_graph

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()
logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"pdf", "docx", "txt"}

# Stale processing threshold: documents stuck in "processing" for longer
# than this are considered stale and recoverable via reprocessing.
_STALE_PROCESSING_SECONDS = 600  # 10 minutes

# Chunk pagination bounds for GET /api/documents/{document_id}.
# Without a bound a 50 MB TXT upload yields tens of thousands of chunks in a
# single JSON body.  The window is applied in SQL (LIMIT/OFFSET), never by
# slicing a fully-materialised result in Python.
DEFAULT_CHUNK_LIMIT = 50
MAX_CHUNK_LIMIT = 200


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


def _chunk_views(chunk_objects: list[DocumentChunk]) -> list[ChunkView]:
    """Structural view of the chunks about to be persisted, in document order.

    Only the fields the graph planner reads are carried over; content and
    embeddings are irrelevant to edge construction.
    """
    return [
        ChunkView(
            chunk_id=str(chunk.id),
            index=chunk.chunk_index,
            page=chunk.page,
            heading_path=(
                tuple(chunk.heading_path) if chunk.heading_path else None
            ),
        )
        for chunk in sorted(chunk_objects, key=lambda c: c.chunk_index)
    ]


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


def _document_verdict(coverage: PageCoverage | None) -> tuple[str, str | None]:
    """Phase 1a verdict for a document whose pipeline steps all succeeded.

    This is the single place the §7.2.1 verdict function is implemented, so no
    other statement can drift from it.  It sees coverage facts only; a raised
    step is the caller's business and always produces ``error`` /
    ``pipeline_exception`` regardless of coverage.

      * no pages at all (DOCX/TXT), or every page usable -> ``ready``
      * at least one usable page and at least one unaccounted page -> ``partial``
      * no usable page -> ``error`` / ``no_text_layer_ocr_disabled``

    OCR is neither configured nor approved in this phase (gates 2/3 closed), so
    ``ocr_failed_all_pages`` is unreachable today and is never claimed here: a
    zero-usable-page document is always reported as "no text layer, OCR
    disabled", which is exactly what was observed.
    """
    if coverage is None or coverage.complete:
        return "ready", None
    if coverage.no_usable_pages:
        return "error", "no_text_layer_ocr_disabled"
    return "partial", None


async def _process_document(
    doc: Document,
    stored_path: Path,
    file_type: str,
    db: AsyncSession,
) -> str | None:
    """Run the full processing pipeline for a document.

    Phase 3E/1a: the document remains PROCESSING until every step has
    succeeded, and its final status is the per-page verdict — READY only when
    every page was accounted for, PARTIAL when some page produced no usable
    content, ERROR on any failure or when no page produced usable content.

    Returns the (transient) verdict reason when the document ends as ERROR, so
    the caller and the tests can observe it for this run; it is never persisted
    and no API exposes it (§7.2.3, gate 23 is status-only).  Returns ``None`` for
    READY and PARTIAL.
    """
    now = _now_utc()
    doc.status = "processing"
    doc.processing_started_at = now
    doc.updated_at = now
    doc.embedding_status = "pending"
    doc.chunk_count = 0
    await db.flush()

    try:
        # --- Step 1: Extract text, with per-page completeness accounting ---
        try:
            elements, coverage = extract_document(stored_path, file_type)
        except Exception:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return "pipeline_exception"

        # Phase 1a: the document-level rule is page coverage, never "some
        # element was extracted somewhere".  A document with no usable page at
        # all is ERROR — never PARTIAL, and never READY — and no chunks are
        # written for it.  Unusable pages are reported in this run's result and
        # in the log; nothing durable is claimed about them (gate 23).
        verdict, reason = _document_verdict(coverage)
        if verdict == "error":
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            logger.warning(
                "document %s verdict: error (%s); pages usable %s/%s; "
                "unaccounted pages %s",
                doc.id,
                reason,
                coverage.pages_usable,
                coverage.pages_total,
                list(coverage.unusable_pages),
            )
            return reason

        if not elements:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return None

        # --- Step 2: Chunk ---
        chunker_version = resolve_chunker_version(settings.chunker_version)
        try:
            chunk_objects = _build_chunk_objects(elements, doc.id, chunker_version, db)
        except Exception:
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return "pipeline_exception"

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
            # Chunks exist but have no vectors; set ERROR.  No chunk is
            # searchable (retrieval filters on ``embedding IS NOT NULL`` **and**
            # on the document's ``embedding_status = 'ready'``), so the reported
            # count is zero: the row artifacts are kept, but they are not
            # searchable content and must not be reported as if they were.
            doc.status = "error"
            doc.embedding_status = "error"
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return "pipeline_exception"

        # --- Step 4: Persist the structure-aware element graph (PDF only) ---
        #
        # The parser (documents.parser) is the single source of truth for PDF
        # structure.  Its output is persisted to document_structure_elements so
        # later graph tasks can derive structural edges from real data.  It is
        # rebuilt from scratch on every run, exactly like the chunk graph, so a
        # reprocessed document can never retain stale structure rows.
        #
        # Atomicity: replace_document_structure runs inside a SAVEPOINT, so a
        # failure rolls back only the structure rows and leaves the outer
        # processing transaction (and its ERROR status transition) intact.
        #
        # Boundary: only PARENT_OF/CONTAINS relationships are represented, via
        # parent_id.  No semantic edges, no REFERENCES inference, no traversal.
        if file_type == "pdf":
            try:
                parsed = parse_pdf(stored_path)
                await replace_document_structure(db, doc.id, parsed)
            except Exception:
                logger.exception(
                    "structure extraction failed for document %s; "
                    "document will not be marked ready",
                    doc.id,
                )
                doc.status = "error"
                doc.embedding_status = "error"
                # embedding_status='error' excludes the document from the
                # semantic path, so none of its chunks is searchable.
                doc.chunk_count = 0
                doc.updated_at = _now_utc()
                return "pipeline_exception"

        # --- Step 5: Build the document structure graph ---
        #
        # The structural graph is derived from the document's own structure
        # (reading order, page, heading path) — no LLM, no external graph store.
        # It is rebuilt from scratch on every processing run, which is what makes
        # reprocessing correct: the old chunks (and, by FK cascade, their edges)
        # are gone, so the graph must never be appended to.
        #
        # Ordering matters: the graph must exist before the document can be
        # READY, and a graph failure must leave the document NOT ready.  A
        # searchable document with a missing or partial graph would silently
        # degrade to the semantic-only path, which is exactly the kind of
        # half-truth this project forbids.
        try:
            await replace_document_graph(db, doc.id, _chunk_views(chunk_objects))
        except Exception:
            logger.exception(
                "structural graph construction failed for document %s; "
                "document will not be marked ready",
                doc.id,
            )
            doc.status = "error"
            doc.embedding_status = "error"
            # embedding_status='error' excludes the document from the semantic
            # path, so none of its chunks is searchable.
            doc.chunk_count = 0
            doc.updated_at = _now_utc()
            return "pipeline_exception"

        # --- Step 6: All steps succeeded -- verdict from page coverage ---
        #
        # The pipeline ran to completion for the pages it could read, so the
        # document is searchable either way; what differs is whether every page
        # of the source document is represented in that content.  That is a
        # coverage fact, and it is what decides READY vs PARTIAL.
        verdict, reason = _document_verdict(coverage)
        doc.embedding_model = EMBEDDING_MODEL_NAME
        doc.embedding_status = "ready"
        if verdict == "ready":
            doc.status = "ready"
        else:
            # PARTIAL: at least one page usable, at least one not.  The pages
            # that could not be read are reported for this run only (log +
            # processing result), never persisted (§7.2.3, gate 23).
            doc.status = "partial"
            logger.warning(
                "document %s verdict: partial; pages usable %s/%s; "
                "unaccounted pages %s",
                doc.id,
                coverage.pages_usable,
                coverage.pages_total,
                list(coverage.unusable_pages),
            )
        doc.updated_at = _now_utc()
        return reason

    except Exception:
        # Catch-all for unexpected failures
        doc.status = "error"
        doc.embedding_status = "error"
        doc.chunk_count = 0
        doc.updated_at = _now_utc()
        return "pipeline_exception"


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
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(DEFAULT_CHUNK_LIMIT, ge=1, le=MAX_CHUNK_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Get document details with a bounded, paginated chunk window.

    ``document_id`` is typed as :class:`uuid.UUID` so FastAPI/Pydantic rejects
    a malformed id with a 422 *before* it can be bound as a PostgreSQL UUID --
    the database never sees a non-UUID, so no driver error can leak.

    Chunks are fetched with a SQL ``LIMIT``/``OFFSET`` ordered by
    ``chunk_index`` (with the chunk id as a deterministic tie-breaker); the
    total is counted in the same database round-trip pair rather than by
    materialising every chunk.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    total = (
        await db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
        )
    ).scalar_one()

    chunk_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
        .limit(limit)
        .offset(offset)
    )
    chunks_out = [
        ChunkOut(
            id=str(c.id),
            chunkIndex=c.chunk_index,
            content=c.content,
            page=c.page,
        )
        for c in chunk_result.scalars().all()
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
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


@router.get("/{document_id}/insights", response_model=DocumentInsightsResponse)
async def get_document_insights(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return real, stored-data-only insights for one document.

    ``document_id`` is typed as :class:`uuid.UUID` so FastAPI/Pydantic rejects
    a malformed id with a 422 before any database bind happens.

    The document is fetched scoped to the authenticated user, so an unknown id
    and another user's document are both an indistinguishable 404 and no
    internal detail (including ``stored_path``) is ever returned.  All
    statistics are computed by aggregate SQL over the document's own chunks and
    graph edges; chunk content is never materialised into Python.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    insights = await compute_document_insights(db, doc)
    return DocumentInsightsResponse(**insights)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document, its chunks, and the stored file.

    ``document_id`` is typed as :class:`uuid.UUID` so FastAPI/Pydantic rejects
    a malformed id with a 422 *before* it can be bound as a PostgreSQL UUID --
    the database never sees a non-UUID, so no driver error can leak.

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
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Reprocess an existing document.

    ``document_id`` is typed as :class:`uuid.UUID` so FastAPI/Pydantic rejects
    a malformed id with a 422 *before* it can be bound as a PostgreSQL UUID --
    the database never sees a non-UUID, so no driver error can leak.

    Phase 3E: allows recovering from ERROR or stale PROCESSING states
    without forcing the user to delete and re-upload.

    Behaviour:
    - ERROR document: re-run the full pipeline
    - PROCESSING (stale): re-run the full pipeline
    - READY document: re-run the full pipeline (user chose to re-index)
    - PROCESSING (not stale): reject (already in progress)

    Reprocessing replaces all chunks, embeddings **and** the structural graph.
    The document identity, content_hash, and stored file are preserved.

    Graph edges are removed by FK cascade when the old chunks are deleted, and
    ``_process_document`` then rebuilds the graph from the new chunks — so a
    reprocessed document can never retain edges pointing at chunks that no
    longer exist.

    **Preservation invariant:** a failed attempt never destroys the last
    successfully indexed version.  Every mutation the attempt makes — deleting
    the previous chunks and structure rows, inserting the new chunk rows,
    replacing the structure and the graph — happens inside this request's
    single transaction, and that transaction is committed only once the attempt
    has succeeded.  A failed attempt is rolled back, which restores the
    previous chunks, their embeddings, the structure rows and the graph exactly
    as they were, so no reader ever observed the document without its last
    indexed version.

    The failure outcome is reported honestly instead of as success: the request
    answers 500, and

    * if a searchable version was preserved, the document keeps describing it
      (``status``/``embeddingStatus``/``chunkCount`` are the previous version's,
      because those values still describe the rows the user can search);
    * if there was no searchable version to preserve, the document is left in
      the honest failure state (``error`` / ``error`` / ``0``).

    The verdict reason for the failed run is transient (logged here, never
    persisted — §7.2.3 / gate 23).
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

    # --- What the last successfully indexed version looks like --------------
    # Captured before anything is mutated: a failed attempt must leave exactly
    # this in place.  ``doc.chunks`` is eagerly loaded above, so this reads the
    # persisted rows, not a lazy load.
    had_searchable_version = (
        doc.status in ("ready", "partial")
        and doc.embedding_status == "ready"
        and len(doc.chunks) > 0
    )
    previous_row_count = len(doc.chunks)

    # --- The replacement attempt (provisional; nothing is committed yet) ----
    # Phase 3E: delete old chunks before reprocessing to prevent mixing
    # old chunks with new embeddings.  These deletions are provisional: they
    # reach the database only if the attempt succeeds (see the preservation
    # invariant in the docstring).
    for chunk in list(doc.chunks):
        await db.delete(chunk)
    # Delete stale structure elements up front so that, even if processing
    # fails before the structure step runs, no structure rows from a previous
    # run survive to contradict the new state.
    await db.execute(
        delete(DocumentStructureElement).where(
            DocumentStructureElement.document_id == doc.id
        )
    )
    doc.chunk_count = 0
    doc.embedding_status = "pending"
    await db.flush()

    # Run the full pipeline
    reason = await _process_document(doc, stored_path, doc.file_type, db)

    if doc.status != "error":
        # The replacement is complete and usable: commit it.
        await db.commit()
        await db.refresh(doc)
        return _doc_to_out(doc)

    # --- The attempt failed: undo the whole attempt -------------------------
    # Rolling the request transaction back discards every mutation made above
    # -- the deletions, the new chunk rows, the structure and graph writes --
    # and restores the previous version from the database.  Nothing above was
    # committed, so the previous version was never absent.
    await db.rollback()

    # The ORM state went with the rollback; re-read the restored row.
    restored = (
        await db.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if restored is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if had_searchable_version:
        # The restored rows *are* the previous version and its labels still
        # describe them exactly, so they are deliberately not rewritten: the
        # document keeps telling the truth about what the user can search.  The
        # failed attempt is reported by the response and the log, not by
        # mislabelling searchable content as broken.
        logger.warning(
            "document %s: reprocess attempt failed (%s); previous indexed "
            "version preserved (%s chunks, embedding_status=%r)",
            restored.id,
            reason,
            previous_row_count,
            restored.embedding_status,
        )
        detail = (
            "Reprocessing failed; the previously indexed version is unchanged "
            "and still searchable."
        )
    else:
        # Nothing indexed before, so there is nothing to preserve: record the
        # honest failure state with no searchable content.
        restored.status = "error"
        restored.embedding_status = "error"
        restored.chunk_count = 0
        restored.updated_at = _now_utc()
        logger.warning(
            "document %s: reprocess attempt failed (%s); no previous indexed "
            "version to preserve",
            restored.id,
            reason,
        )
        detail = "Reprocessing failed; the document has no searchable content."

    await db.commit()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )
