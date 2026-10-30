"""Preserve original paragraph membership for structured chunk children.

Revision ID: 018
Revises: 017

Existing rows intentionally remain NULL: their paragraph boundaries cannot be
reconstructed from chunk order alone.
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("source_element_indices", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "source_element_indices")
