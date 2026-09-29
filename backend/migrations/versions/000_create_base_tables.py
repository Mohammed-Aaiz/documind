"""Create the DocuMind base tables.

This is the ROOT of the migration chain (``down_revision = None``).

Before this migration existed, the application had no way to create its
base tables: only the incremental migrations 001–004 existed, and every one
of them assumes ``users`` / ``documents`` / ``document_chunks`` already
exist.  A fresh database therefore could not be provisioned.

Composition rules (why this migration deliberately does NOT create every
column the final ORM models declare):

  * ``reliability_logs`` is created by migration ``001``.  Creating it here
    as well would make ``001`` fail with "relation already exists".
  * ``documents.content_hash`` is added by ``002``.
  * ``documents.chunker_version`` and the ``document_chunks`` structure
    columns (heading_path, section, element_type, chunker_version,
    token_count) are added by ``003``.
  * ``documents.parser_version``, ``documents.embedding_model``,
    ``documents.updated_at`` and ``documents.processing_started_at`` are
    added by ``004``.

So this migration creates the base tables in their pre-002/003/004 shape and
lets the existing incremental migrations add the rest.  The resulting schema
matches the SQLAlchemy models exactly.

The DDL is idempotent: each table is created only when it does not already
exist, so re-running against a database that already holds some of these
tables (e.g. a manually-created dev database with no ``alembic_version``)
is safe and never drops or overwrites anything.

Revision ID: 000_create_base_tables
Revises: None
Create Date: 2026-09-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "000_create_base_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_offline() -> bool:
    """True when Alembic is generating SQL instead of executing it.

    Offline mode (``alembic upgrade head --sql``) has no connection to
    inspect, so existence checks must be skipped and DDL emitted
    unconditionally.
    """
    return bool(getattr(op.get_context(), "as_sql", False))


def _existing_tables() -> set[str]:
    """Names of tables already present in the connected database.

    Returns an empty set in offline mode (nothing can be inspected), which
    makes the upgrade path emit full DDL for a fresh database.
    """
    if _is_offline():
        return set()
    return set(inspect(op.get_bind()).get_table_names())


def _uuid_pk() -> sa.Column:
    """Standard primary key: client-generated UUID with a server fallback."""
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # pgvector must exist before document_chunks (it uses the vector type).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    existing = _existing_tables()

    # --- users -----------------------------------------------------------
    if "users" not in existing:
        op.create_table(
            "users",
            _uuid_pk(),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False, server_default="User"),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("avatar_url", sa.String(512), nullable=True),
            sa.Column(
                "clearance",
                sa.String(100),
                nullable=False,
                server_default="Level 1 — Viewer",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "two_factor_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "e2e_encryption",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            _created_at(),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
        op.create_index("ix_users_email", "users", ["email"])

    # --- documents (base shape; 002/003/004 add further columns) ---------
    if "documents" not in existing:
        op.create_table(
            "documents",
            _uuid_pk(),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(512), nullable=False),
            sa.Column("file_type", sa.String(10), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("stored_path", sa.String(1024), nullable=False),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
            sa.Column(
                "embedding_status",
                sa.String(20),
                nullable=False,
                server_default="pending",
            ),
            _created_at(),
        )
        op.create_index("ix_documents_user_id", "documents", ["user_id"])

    # --- document_chunks (base shape; 003 adds structure columns) --------
    if "document_chunks" not in existing:
        op.create_table(
            "document_chunks",
            _uuid_pk(),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("page", sa.Integer(), nullable=True),
            sa.Column("embedding", Vector(384), nullable=True),
            sa.Column("embedding_id", sa.String(255), nullable=True),
            _created_at(),
        )
        op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # --- chat_sessions ---------------------------------------------------
    if "chat_sessions" not in existing:
        op.create_table(
            "chat_sessions",
            _uuid_pk(),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            _created_at(),
        )
        op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    # --- chat_messages ---------------------------------------------------
    if "chat_messages" not in existing:
        op.create_table(
            "chat_messages",
            _uuid_pk(),
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sender", sa.String(10), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            _created_at(),
        )
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    # --- verification_results -------------------------------------------
    if "verification_results" not in existing:
        op.create_table(
            "verification_results",
            _uuid_pk(),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("file_name", sa.String(512), nullable=False),
            sa.Column("file_type", sa.String(50), nullable=False),
            sa.Column("stored_path", sa.String(1024), nullable=False),
            sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("verdict", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("lip_sync_drift", sa.String(10), nullable=True),
            sa.Column("blink_rate", sa.String(10), nullable=True),
            _created_at(),
        )
        op.create_index(
            "ix_verification_results_user_id", "verification_results", ["user_id"]
        )

    # --- user_settings ---------------------------------------------------
    if "user_settings" not in existing:
        op.create_table(
            "user_settings",
            _uuid_pk(),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "processing_depth", sa.Integer(), nullable=False, server_default="3"
            ),
            sa.Column(
                "context_window", sa.String(20), nullable=False, server_default="persistent"
            ),
            sa.Column("theme", sa.String(20), nullable=False, server_default="dark-cyber"),
            sa.Column("density", sa.String(20), nullable=False, server_default="high"),
            sa.Column(
                "glass_intensity", sa.Integer(), nullable=False, server_default="70"
            ),
            _created_at(),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("user_id", name="uq_user_settings_user_id"),
        )

    # --- source_refs (legacy table, kept empty) --------------------------
    if "source_refs" not in existing:
        op.create_table(
            "source_refs",
            _uuid_pk(),
            sa.Column(
                "chat_message_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("extraction_node", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="UNRESOLVED"),
            _created_at(),
        )
        op.create_index(
            "ix_source_refs_chat_message_id", "source_refs", ["chat_message_id"]
        )
        op.create_index("ix_source_refs_document_id", "source_refs", ["document_id"])


# ---------------------------------------------------------------------------
# Downgrade (only tables this migration created)
# ---------------------------------------------------------------------------

def downgrade() -> None:
    existing = _existing_tables()
    offline = _is_offline()

    # Offline generation cannot inspect the database, so emit every drop.
    if offline or "source_refs" in existing:
        op.drop_index("ix_source_refs_document_id", table_name="source_refs")
        op.drop_index("ix_source_refs_chat_message_id", table_name="source_refs")
        op.drop_table("source_refs")

    if offline or "user_settings" in existing:
        op.drop_table("user_settings")

    if offline or "verification_results" in existing:
        op.drop_index("ix_verification_results_user_id", table_name="verification_results")
        op.drop_table("verification_results")

    if offline or "chat_messages" in existing:
        op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
        op.drop_table("chat_messages")

    if offline or "chat_sessions" in existing:
        op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
        op.drop_table("chat_sessions")

    if offline or "document_chunks" in existing:
        op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
        op.drop_table("document_chunks")

    if offline or "documents" in existing:
        op.drop_index("ix_documents_user_id", table_name="documents")
        op.drop_table("documents")

    if offline or "users" in existing:
        op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")

    # The pgvector extension is intentionally NOT dropped: it is shared
    # infrastructure and may be used by tables this migration did not create.
