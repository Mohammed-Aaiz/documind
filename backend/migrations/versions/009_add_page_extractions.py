"""Add ``document_page_extractions``: durable per-page extraction provenance.

Why
---
Phase 1a made the document verdict per-page (READY only when every page produced
usable text) and gate 23 kept the API status-only, so the per-page facts lived for
one request and were logged, never stored.  With the OCR fallback implemented, a
user needs to know *which* pages were read by OCR, by which engine, at what
confidence — otherwise "PARTIAL" cannot be investigated and an OCR'd page is
indistinguishable from a native one after the fact.

This is the additive option A already recorded in
``DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md`` §8 (a page-extraction table),
scoped to the facts the code actually observes today.  The owner requested it
on 2026-10-24 ("persist per-page OCR provenance so the UI and API can show which
pages were OCR'd"), which supersedes that record's D-3 clause for *per-page*
provenance: a page's failure reason is now durable too.  D-3's ban on a
*document-level* coverage denominator still stands — this revision adds no
``sourcePageCount`` / ``pagesMissing`` field, and the document verdict is
unchanged and still not derived from these rows.

Additivity
----------
* one new table; no existing column changes type or meaning and nothing is
  backfilled — documents processed before this revision simply have no page
  rows, and the API reports that as "not recorded" rather than as zero pages;
* ``(document_id, page_number)`` is unique, so the per-run replace cannot
  duplicate a page;
* the FK cascades on document delete, like every other document-owned table;
* downgrade drops only this table.

Revision ID: 009
Revises: 008
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_page_extractions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("text_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_engine", sa.String(length=64), nullable=True),
        sa.Column("ocr_engine_version", sa.String(length=32), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("ocr_rotation", sa.Integer(), nullable=True),
        sa.Column("ocr_seconds", sa.Float(), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_page_extractions_document_page",
        ),
    )
    op.create_index(
        "ix_document_page_extractions_document_id",
        "document_page_extractions",
        ["document_id"],
    )
    op.create_index(
        "ix_document_page_extractions_document_page",
        "document_page_extractions",
        ["document_id", "page_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_page_extractions_document_page",
        table_name="document_page_extractions",
    )
    op.drop_index(
        "ix_document_page_extractions_document_id",
        table_name="document_page_extractions",
    )
    op.drop_table("document_page_extractions")
