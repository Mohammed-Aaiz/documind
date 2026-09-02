"""Add reliability_logs table for persistent user-scoped reliability data.

Revision ID: 001
Revises: None
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reliability_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("question", sa.Text, nullable=False, server_default=""),
        sa.Column("answer", sa.Text, nullable=False, server_default=""),
        sa.Column("qa_confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("retrieval_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("avg_retrieval_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unique_documents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("factual_grounded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("insufficient_context", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sources_json", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_reliability_logs_user_id",
        "reliability_logs",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reliability_logs_user_id", table_name="reliability_logs")
    op.drop_table("reliability_logs")
