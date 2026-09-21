"""Add Phase 3D chunk structure metadata (additive, nullable).

Adds structure metadata to ``document_chunks`` so that chunking strategy,
section context and token budget survive into the persisted chunk, and a
chunker version to ``documents`` so a corpus can never mix strategies
unlabelled.

Every column is nullable and there is deliberately no backfill: existing
rows keep working and are identified as legacy chunks by a NULL
``chunker_version``.

Revision ID: 003
Revises: 002
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("chunker_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("heading_path", sa.JSON(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("section", sa.String(512), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("element_type", sa.String(32), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("chunker_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("token_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "token_count")
    op.drop_column("document_chunks", "chunker_version")
    op.drop_column("document_chunks", "element_type")
    op.drop_column("document_chunks", "section")
    op.drop_column("document_chunks", "heading_path")
    op.drop_column("documents", "chunker_version")
