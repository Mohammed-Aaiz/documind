"""Persist observed page layout alongside extraction provenance.

Revision ID: 014
Revises: 013
Create Date: 2026-10-28

The nullable JSON payload is additive: existing page rows stay NULL until an
actual extraction observes regions. No document, chunk, embedding or graph
record is rewritten or inferred by this migration.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_page_extractions",
        sa.Column("spatial_layout", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_page_extractions", "spatial_layout")
