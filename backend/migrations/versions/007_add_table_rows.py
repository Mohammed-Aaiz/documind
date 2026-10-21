"""Add compact, faithful table-row evidence (Phase 2).

Creates ``document_table_rows``: one row per source table row of a persisted
aggregate ``table`` structure element, holding the extractor's own cells
verbatim plus a deterministic serialised ``content`` (header-repeated for body
rows, so the unit is self-contained).

Why a separate table
--------------------
The teacher-demo table persists as a single aggregate element of ~230 tokens,
while the QA context budget is 362 tokens and the five ranked chunks already
consume 266 — so the aggregate can never enter the QA context intact
(``266 + 230 = 496 > 362``).  Row-level evidence is the compact alternative
(~36-48 tokens per header-repeated row).  It is stored **here** rather than as
extra ``document_structure_elements`` rows on purpose:

* the element stream keeps its ``sequence_index`` values, ordering and
  ``UNIQUE (document_id, sequence_index)`` constraint untouched, so the existing
  document-order selection behaviour cannot shift;
* ``table_row`` / ``table_cell`` remain unsupported *element* types — no such
  element is synthesised;
* the aggregate ``table`` element itself is unchanged and still persisted.

Design notes
------------
* Purely additive: no existing table, column, constraint or row is altered, so
  applying this migration is non-destructive and safe to re-apply.
* ``document_id`` cascades on document delete and ``table_element_id`` cascades on
  element delete, so deleting a document — or replacing its structure during
  reprocessing — can never leave orphaned row evidence.
* ``UNIQUE (document_id, table_element_id, row_index)`` makes ingestion
  idempotent (duplicate rows impossible) and ``row_index`` is the extractor's own
  0-based index, so ordering is document order rather than insertion order.
* Ownership is not duplicated: it is reached through
  ``document_id -> documents.user_id``.
* No retrieval, fusion, RRF, chunker or QA-model behaviour is affected by this
  migration on its own; the table is written during ingestion and read by no
  production code yet.

Revision ID: 007
Revises: 006
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "document_table_rows"
_ELEMENTS = "document_structure_elements"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table(_TABLE):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_ELEMENTS}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("is_header", sa.Boolean(), nullable=False),
        sa.Column("header_repeated", sa.Boolean(), nullable=False),
        sa.Column("cells", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.JSON(), nullable=True),
        sa.Column("section", sa.String(512), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("parser_version", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "document_id",
            "table_element_id",
            "row_index",
            name="uq_document_table_rows_element_row",
        ),
    )
    op.create_index("ix_document_table_rows_document_id", _TABLE, ["document_id"])
    op.create_index(
        "ix_document_table_rows_table_element_id", _TABLE, ["table_element_id"]
    )
    op.create_index(
        "ix_document_table_rows_document_element_row",
        _TABLE,
        ["document_id", "table_element_id", "row_index"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(_TABLE):
        return

    op.drop_index("ix_document_table_rows_document_element_row", table_name=_TABLE)
    op.drop_index("ix_document_table_rows_table_element_id", table_name=_TABLE)
    op.drop_index("ix_document_table_rows_document_id", table_name=_TABLE)
    op.drop_table(_TABLE)
