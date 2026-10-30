"""Preserve derived-index versions before document reprocessing.

Revision ID: 017
Revises: 016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_index_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("chunker_version", sa.String(64)),
        sa.Column("embedding_model", sa.String(128)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["user_id", "document_id"], ["documents.user_id", "documents.id"],
                                name="fk_document_index_revisions_owner_document", ondelete="CASCADE"),
    )
    op.create_index("ix_document_index_revisions_document_created", "document_index_revisions", ["document_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_index_revisions_document_created", table_name="document_index_revisions")
    op.drop_table("document_index_revisions")
