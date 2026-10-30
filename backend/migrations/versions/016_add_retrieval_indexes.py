"""Build hybrid retrieval indexes without blocking normal document writes.

Revision ID: 016
Revises: 015
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_document_chunks_content_fts", "USING gin (to_tsvector('english'::regconfig, content))"),
    ("ix_document_chunks_document_order", "(document_id, chunk_index)"),
    ("ix_document_chunks_embedding_hnsw", "USING hnsw (embedding vector_cosine_ops)"),
)


def upgrade() -> None:
    # Concurrent builds avoid holding a table write lock for a corpus-wide build.
    # Alembic records the revision only when every index has completed.
    with op.get_context().autocommit_block():
        op.execute("SET lock_timeout = '5s'")
        op.execute("SET statement_timeout = '120s'")
        try:
            for name, definition in _INDEXES:
                op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON document_chunks {definition}")
                if not op.get_context().as_sql:
                    valid = op.get_bind().execute(sa.text(
                        "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname=:name"
                    ), {"name": name}).scalar_one()
                    if not valid:
                        raise RuntimeError(f"Index {name} is invalid; repair the interrupted index build before retrying")
        finally:
            op.execute("RESET lock_timeout")
            op.execute("RESET statement_timeout")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _ in reversed(_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
