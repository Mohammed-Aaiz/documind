"""Add Phase 3E processing provenance and lifecycle columns.

Adds columns to ``documents`` needed for honest processing state
management and pipeline traceability:

  - ``parser_version``      — which extractor produced the chunks
  - ``embedding_model``     — which embedding model produced the vectors
  - ``updated_at``          — last state change timestamp
  - ``processing_started_at`` — when the current processing run began

Every column is nullable so existing rows are unaffected.

Revision ID: 004
Revises: 003
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("parser_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("embedding_model", sa.String(128), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "parser_version")
