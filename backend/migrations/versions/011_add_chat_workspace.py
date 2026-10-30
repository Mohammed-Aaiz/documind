"""Persist the Student/Research partition of chat sessions.

The 2026-10-27 owner-authorized workspace rebuild is recorded in
``architecture/DOCUMIND_WORKSPACE_REBUILD_2026-10-27.md``. Existing sessions
are assigned to Student by the constant server default. No session or message
is deleted, and existing foreign keys and user ownership remain unchanged.

Revision ID: 011
Revises: 010
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The column-level CHECK is portable to SQLite migration fixtures as well
    # as PostgreSQL, without rebuilding the production table.
    op.add_column(
        "chat_sessions",
        sa.Column(
            "workspace",
            sa.String(length=16),
            sa.CheckConstraint(
                "workspace IN ('student', 'research')",
                name="ck_chat_sessions_workspace",
            ),
            nullable=False,
            server_default="student",
        ),
    )
    op.create_index(
        "ix_chat_sessions_user_workspace_created",
        "chat_sessions",
        ["user_id", "workspace", "created_at"],
    )


def downgrade() -> None:
    # Downgrade removes the partition metadata, never the sessions/messages.
    # Operators must explicitly authorize downgrade of a live database.
    op.drop_index(
        "ix_chat_sessions_user_workspace_created", table_name="chat_sessions"
    )
    op.drop_column("chat_sessions", "workspace")
