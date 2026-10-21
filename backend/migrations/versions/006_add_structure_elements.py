"""Add the structure-aware document element graph.

Creates the two tables behind the Sprint 2 structure graph:

* ``document_structure_elements`` — one row per structural element of a
  document (``page``, ``section``, ``paragraph``, ``text_block``, ``table``,
  ``table_row``, ``table_cell``, ``figure``, ``list``, ``list_item``) with a
  stable id, deterministic ``sequence_index``, self-referential ``parent_id``
  and parser provenance (page number, bounding box, parser version).
* ``document_structure_edges`` — one row per *directed* structural relation
  between two elements of the same document (``CONTAINS``, ``PARENT_OF``,
  ``NEXT``, ``REFERENCES``, ``BELONGS_TO_PAGE``).

Design notes
------------
* Both tables are additive: no existing table is altered, so applying this
  migration is non-destructive.
* ``document_id`` cascades on document delete; ``parent_id`` and the edge
  endpoints cascade on element delete, so deleting a document (or replacing
  its structure during reprocessing) can never leave an orphan row behind.
* ``UNIQUE (document_id, sequence_index)`` makes element ordering deterministic
  (never insertion order) and graph construction idempotent.
  ``UNIQUE (source_element_id, target_element_id, relation)`` does the same for
  edges.
* Ownership is not duplicated onto either table — it is reached through
  ``document_id -> documents.user_id``, so a traverser can only ever reach its
  own rows.
* Only the five relations structure-aware traversal requires are modelled; no
  wider knowledge-graph vocabulary is introduced.

The upgrade is safe to re-apply: each table is skipped when it already exists.

Revision ID: 006
Revises: 005
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ELEMENTS = "document_structure_elements"
_EDGES = "document_structure_edges"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_ELEMENTS):
        op.create_table(
            _ELEMENTS,
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
            ),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "parent_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(
                    f"{_ELEMENTS}.id",
                    ondelete="CASCADE",
                ),
                nullable=True,
            ),
            sa.Column("element_type", sa.String(32), nullable=False),
            sa.Column("sequence_index", sa.Integer(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("heading_level", sa.Integer(), nullable=True),
            sa.Column("heading_path", sa.JSON(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("bbox_x0", sa.Float(), nullable=True),
            sa.Column("bbox_y0", sa.Float(), nullable=True),
            sa.Column("bbox_x1", sa.Float(), nullable=True),
            sa.Column("bbox_y1", sa.Float(), nullable=True),
            sa.Column("parser_version", sa.String(64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "document_id",
                "sequence_index",
                name="uq_document_structure_elements_document_sequence",
            ),
        )
        op.create_index(
            "ix_document_structure_elements_document_id", _ELEMENTS, ["document_id"]
        )
        op.create_index(
            "ix_document_structure_elements_parent_id", _ELEMENTS, ["parent_id"]
        )
        op.create_index(
            "ix_document_structure_elements_element_type", _ELEMENTS, ["element_type"]
        )
        op.create_index(
            "ix_document_structure_elements_document_page",
            _ELEMENTS,
            ["document_id", "page_number"],
        )

    if not inspector.has_table(_EDGES):
        op.create_table(
            _EDGES,
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
            ),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "source_element_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{_ELEMENTS}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "target_element_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{_ELEMENTS}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("relation", sa.String(32), nullable=False),
            sa.Column(
                "weight", sa.Float(), nullable=False, server_default=sa.text("1.0")
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "source_element_id",
                "target_element_id",
                "relation",
                name="uq_document_structure_edges_triplet",
            ),
        )
        op.create_index(
            "ix_document_structure_edges_document_id", _EDGES, ["document_id"]
        )
        op.create_index(
            "ix_document_structure_edges_target_element_id",
            _EDGES,
            ["target_element_id"],
        )
        op.create_index("ix_document_structure_edges_relation", _EDGES, ["relation"])
        op.create_index(
            "ix_document_structure_edges_source_relation",
            _EDGES,
            ["source_element_id", "relation"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table(_EDGES):
        op.drop_index(
            "ix_document_structure_edges_source_relation", table_name=_EDGES
        )
        op.drop_index("ix_document_structure_edges_relation", table_name=_EDGES)
        op.drop_index(
            "ix_document_structure_edges_target_element_id", table_name=_EDGES
        )
        op.drop_index("ix_document_structure_edges_document_id", table_name=_EDGES)
        op.drop_table(_EDGES)

    if inspector.has_table(_ELEMENTS):
        op.drop_index(
            "ix_document_structure_elements_document_page", table_name=_ELEMENTS
        )
        op.drop_index(
            "ix_document_structure_elements_element_type", table_name=_ELEMENTS
        )
        op.drop_index(
            "ix_document_structure_elements_parent_id", table_name=_ELEMENTS
        )
        op.drop_index(
            "ix_document_structure_elements_document_id", table_name=_ELEMENTS
        )
        op.drop_table(_ELEMENTS)
