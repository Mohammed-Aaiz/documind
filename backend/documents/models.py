import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # Composite ownership references used by the entity-relation graph.
        # `id` is already a primary key; this unique key lets PostgreSQL enforce
        # that a graph row's owner and document always belong together.
        UniqueConstraint("user_id", "id", name="uq_documents_owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf, docx, txt
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    chunker_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded"
    )  # uploaded, processing, ready, partial, error
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, ready, error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    owner = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        # Composite provenance references ensure graph evidence chunks belong
        # to the same document as their mention and relation rows.
        UniqueConstraint("document_id", "id", name="uq_document_chunks_document_id"),
        Index("ix_document_chunks_document_order", "document_id", "chunk_index"),
        Index("ix_document_chunks_content_fts", text("to_tsvector('english'::regconfig, content)"), postgresql_using="gin").ddl_if(dialect="postgresql"),
        Index("ix_document_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(384), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Phase 3D structure metadata (nullable; absent for legacy chunks) ---
    heading_path: Mapped[list | None] = mapped_column(JSON, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    element_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chunker_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    document = relationship("Document", back_populates="chunks")


class DocumentIndexRevision(Base):
    """Exact derived-index snapshot saved before a successful replacement.

    Original uploads are referenced by Document; snapshots preserve chunk IDs,
    text and provenance already cited by historical answers.
    """

    __tablename__ = "document_index_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "document_id"], ["documents.user_id", "documents.id"],
            name="fk_document_index_revisions_owner_document", ondelete="CASCADE",
        ),
        Index("ix_document_index_revisions_document_created", "document_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    chunker_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class DocumentPageExtraction(Base):
    """How one page's text was obtained, recorded per page of a paged document.

    Phase 1a already counted coverage per page ("this page produced usable
    text"), but that accounting died with the request: the API was allowed to
    say only READY / PARTIAL / ERROR, so a user could not learn *which* page had
    been read by OCR and how confident that reading was.  This table makes the
    per-page facts durable, which is what the insights endpoint and the UI read.

    One row per page, replaced on every processing run (never appended):

    * ``method`` is ``native`` (the page had a usable text layer), ``ocr`` (its
      text came from the OCR fallback) or ``none`` (no usable text was obtained);
    * ``text_chars`` is the same non-whitespace alphanumeric measure the verdict
      uses (``processing.count_usable_chars``), so the row and the status can
      never disagree about what "usable" means;
    * the ``ocr_*`` fields are set only for ``method = 'ocr'`` — engine, version,
      mean line confidence, the rotation the page had to be read at, and the
      time OCR took.  They are NULL for native pages rather than zero-filled;
    * ``failure_reason`` is set only for ``method = 'none'`` and uses a fixed
      vocabulary (``no_text_layer``, ``ocr_disabled``, ``ocr_unavailable``,
      ``ocr_failed``, ``ocr_budget_exhausted``) — never free text, so it can be
      rendered without interpretation.

    ``(document_id, page_number)`` is unique and both columns are indexed, so a
    page can never have two competing records and the replace is idempotent.
    """

    __tablename__ = "document_page_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # native|ocr|none
    text_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_engine_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_rotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Observed page geometry, not inferred visual semantics. NULL explicitly
    # distinguishes documents indexed before spatial extraction was available.
    # Regions preserve normalized bboxes, reading order, column and caption
    # associations so extraction can be inspected without re-rendering a PDF.
    spatial_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_page_extractions_document_page",
        ),
        Index(
            "ix_document_page_extractions_document_page",
            "document_id",
            "page_number",
        ),
    )


class DocumentVisualPatch(Base):
    """A genuinely encoded image region with its original page provenance.

    Only successfully encoded regions are persisted: no NULL, zero or text-only
    placeholder vector stands in for visual evidence. Ownership is inherited
    through ``document_id -> documents.user_id``; retrieval must scope that join.
    ``bbox`` contains normalized page coordinates in source reading geometry.
    """

    __tablename__ = "document_visual_patches"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "page_number", "region_id",
            name="uq_document_visual_patches_document_page_region",
        ),
        Index(
            "ix_document_visual_patches_document_page", "document_id", "page_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    region_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    bbox: Mapped[list] = mapped_column(JSON, nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(512), nullable=False)
    encoder_model: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentTableRow(Base):
    """Faithful row-level evidence for one persisted aggregate ``table`` element.

    Tables are persisted as a *single* aggregate structure element
    (``document_structure_elements``), which is far too large to enter the QA
    context: the teacher-demo table is ~230 tokens against a 362-token QA
    budget that five ranked chunks already fill to 266.  This table adds a
    second, purely additive representation so later phases can offer a compact,
    header-repeated row unit (~36-48 tokens) instead of the aggregate blob —
    without touching the element stream, its ``sequence_index`` ordering or its
    unique constraint.

    Faithfulness rules:

    * ``cells`` holds the extractor's own cell strings, verbatim, in column
      order; ``content`` is a deterministic *serialisation* of those cells
      (never a paraphrase, summary, normalisation or computed value);
    * ``is_header`` marks the extractor's first row when the table has more
      than one row (the same rule ``documents/chunking.py`` already uses); no
      header is ever invented for a single-row table;
    * ``header_repeated`` records whether ``content`` embeds the header row, so
      a reader can tell a self-contained unit from a bare row;
    * ``row_index`` is the extractor's own 0-based row index (including the
      header row), so ordering is document order — never insertion order — and
      a skipped empty row leaves a visible gap rather than silently renumbering
      evidence.

    Provenance and ownership:

    * ``table_element_id`` references the aggregate ``table`` element this row
      belongs to; ``document_id`` carries the document so a whole document's
      row evidence can be indexed, queried and rebuilt atomically;
    * ownership is not duplicated — it is reached through
      ``document_id -> documents.user_id``;
    * both foreign keys cascade on delete, so deleting a document (or replacing
      its structure during reprocessing) can never leave an orphan row behind;
    * ``parser_version`` records the parser that produced the row.

    ``(document_id, table_element_id, row_index)`` is unique, which makes
    ingestion idempotent and duplicate rows impossible; the same columns are
    indexed for the ordered per-table read a later retrieval phase performs.
    """

    __tablename__ = "document_table_rows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_structure_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_header: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    header_repeated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    cells: Mapped[list] = mapped_column(JSON, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[list | None] = mapped_column(JSON, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Deterministic per-table rows: one row per source row index, and the
        # backing index also serves the ordered per-table read.
        UniqueConstraint(
            "document_id",
            "table_element_id",
            "row_index",
            name="uq_document_table_rows_element_row",
        ),
        Index(
            "ix_document_table_rows_document_element_row",
            "document_id",
            "table_element_id",
            "row_index",
        ),
    )
