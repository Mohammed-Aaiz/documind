"""Persist answer citations and bounded evidence metadata on chat messages.

Revision ID: 012
Revises: 011
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add an optional JSON object for answers; historical rows remain intact."""
    op.add_column(
        "chat_messages",
        sa.Column("evidence_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove only the optional metadata column; never touch chat messages."""
    op.drop_column("chat_messages", "evidence_metadata")
