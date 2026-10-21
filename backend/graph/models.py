"""ORM model for the document structure graph.

One row per directed structural edge between two chunks of the *same*
document.  Ownership is not duplicated onto the edge: it is reached through
``source_chunk_id -> document_chunks.document_id -> documents.user_id``, so a
user can only ever traverse their own graph (and the foreign keys cascade on
document/chunk deletion, so no stale edges can survive a delete).

Revision ``005_add_document_graph`` creates this table.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import Base


class DocumentGraphEdge(Base):
    """A directed structural relation between two chunks of one document."""

    __tablename__ = "document_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "relation",
            name="uq_document_graph_edges_triplet",
        ),
    )


# ---------------------------------------------------------------------------
# Structure-aware element graph (Sprint 2)
# ---------------------------------------------------------------------------
#
# The chunk-level graph above links *retrieval units*.  The two models below
# add the finer-grained representation the structure-aware pipeline needs: the
# document's own elements (pages, sections, paragraphs, tables, table cells,
# figures, lists and list items) plus the directed relations between them.
#
# This is still a *document-native* structure graph — no knowledge-graph triple
# extraction, no external graph database.  Every row is an ordinary PostgreSQL
# row reached through ``document_id`` and the ``documents`` ownership chain.
#
# Element types (``element_type``)
# --------------------------------
# ``page`` / ``section`` / ``paragraph`` / ``text_block`` / ``table`` /
# ``table_row`` / ``table_cell`` / ``figure`` / ``list`` / ``list_item``.
# These mirror the ``DocumentElement`` subtypes in
# ``architecture/phase4f_6/DOMAIN_MODEL.md`` and the parser's existing
# ``ALLOWED_ELEMENT_TYPES`` vocabulary (``documents/processing.py``).
#
# Relations (``relation``)
# ------------------------
# ``CONTAINS`` / ``PARENT_OF`` / ``NEXT`` / ``REFERENCES`` / ``BELONGS_TO_PAGE``.
# Deliberately no wider semantic vocabulary: only what structure-aware
# traversal requires.
#
# ``parent_id`` is the authoritative tree link (efficient recursive traversal);
# the ``PARENT_OF`` / ``CONTAINS`` edges mirror that hierarchy so a single
# generic adjacency query can walk the whole graph.
#
# The models live here (the DATABASE_AGENT-owned ``graph/models.py``) so the
# chunk graph and the element graph share one module and one migration chain;
# ``graph/service.py`` (AI_AGENT) is untouched by this change.

ELEMENT_TYPE_PAGE = "page"
ELEMENT_TYPE_SECTION = "section"
ELEMENT_TYPE_PARAGRAPH = "paragraph"
ELEMENT_TYPE_TEXT_BLOCK = "text_block"
ELEMENT_TYPE_TABLE = "table"
ELEMENT_TYPE_TABLE_ROW = "table_row"
ELEMENT_TYPE_TABLE_CELL = "table_cell"
ELEMENT_TYPE_FIGURE = "figure"
ELEMENT_TYPE_LIST = "list"
ELEMENT_TYPE_LIST_ITEM = "list_item"

ELEMENT_TYPES: tuple[str, ...] = (
    ELEMENT_TYPE_PAGE,
    ELEMENT_TYPE_SECTION,
    ELEMENT_TYPE_PARAGRAPH,
    ELEMENT_TYPE_TEXT_BLOCK,
    ELEMENT_TYPE_TABLE,
    ELEMENT_TYPE_TABLE_ROW,
    ELEMENT_TYPE_TABLE_CELL,
    ELEMENT_TYPE_FIGURE,
    ELEMENT_TYPE_LIST,
    ELEMENT_TYPE_LIST_ITEM,
)

RELATION_CONTAINS = "CONTAINS"
RELATION_PARENT_OF = "PARENT_OF"
RELATION_NEXT = "NEXT"
RELATION_REFERENCES = "REFERENCES"
RELATION_BELONGS_TO_PAGE = "BELONGS_TO_PAGE"

STRUCTURE_RELATIONS: tuple[str, ...] = (
    RELATION_CONTAINS,
    RELATION_PARENT_OF,
    RELATION_NEXT,
    RELATION_REFERENCES,
    RELATION_BELONGS_TO_PAGE,
)


class DocumentStructureElement(Base):
    """One structural element of a document (page, section, table, ...).

    ``sequence_index`` is the element's position in document reading order and
    is unique per document, so ordering never depends on insertion order.
    ``parent_id`` is the authoritative nesting link (self-referential, cascades
    on delete); ``page_number`` is the 1-based source page for provenance.

    ``content`` is optional and only populated for leaf elements whose text is
    not already owned by ``document_chunks`` (e.g. a table cell or list item);
    whole-document text stays with the chunk architecture.
    """

    __tablename__ = "document_structure_elements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_structure_elements.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    element_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[list | None] = mapped_column(JSON, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Provenance (DOMAIN_MODEL: position, extraction method, bbox) ---
    bbox_x0: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y0: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Deterministic document order: one element per position, and the
        # backing index also serves ``document_id + sequence_index`` lookups.
        UniqueConstraint(
            "document_id",
            "sequence_index",
            name="uq_document_structure_elements_document_sequence",
        ),
        Index(
            "ix_document_structure_elements_document_page",
            "document_id",
            "page_number",
        ),
    )


class DocumentStructureEdge(Base):
    """A directed structural relation between two elements of one document.

    Mirrors :class:`DocumentGraphEdge` at element granularity.  ``document_id``
    is carried on the edge (as in the chunk graph) so a document's whole
    structure graph can be indexed and rebuilt atomically.  Ownership is not
    duplicated: it flows ``edge -> element -> document -> user``.
    """

    __tablename__ = "document_structure_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_structure_elements.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_structure_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "source_element_id",
            "target_element_id",
            "relation",
            name="uq_document_structure_edges_triplet",
        ),
        # Adjacency traversal always filters by source and relation; the
        # composite index covers the source prefix too, so no separate
        # single-column source index is needed.
        Index(
            "ix_document_structure_edges_source_relation",
            "source_element_id",
            "relation",
        ),
    )
