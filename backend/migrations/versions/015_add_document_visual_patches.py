"""Store genuinely encoded visual page regions with provenance.

Revision ID: 015
Revises: 014
Create Date: 2026-10-28

This additive table stores no synthetic backfill: existing documents receive
visual rows only after their source regions are rendered and encoded.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_visual_patches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("region_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("encoder_model", sa.String(256), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "document_id", "page_number", "region_id",
            name="uq_document_visual_patches_document_page_region",
        ),
    )
    op.create_index(
        "ix_document_visual_patches_document_page", "document_visual_patches",
        ["document_id", "page_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_visual_patches_document_page", table_name="document_visual_patches"
    )
    op.drop_table("document_visual_patches")
