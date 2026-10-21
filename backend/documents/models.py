import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.database import Base


class Document(Base):
    __tablename__ = "documents"

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
