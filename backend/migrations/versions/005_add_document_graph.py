"""Add the document structure graph table.

Creates ``document_graph_edges`` — the document-native structural graph used by
the dual-path (semantic + structural) retrieval pipeline.

Each row is one *directed* structural relation between two chunks of the same
document (``NEXT``, ``PREV``, ``SAME_PAGE``, ``SAME_SECTION``).  There is no
knowledge-graph triple extraction here: the edges are derived from reading
order, page and heading path at ingestion time.

Design notes
------------
* ``document_id`` / ``source_chunk_id`` / ``target_chunk_id`` all cascade on
  delete, so deleting a document (or replacing its chunks during reprocessing)
  can never leave an orphan edge behind.
* ``UNIQUE (source_chunk_id, target_chunk_id, relation)`` makes graph
  construction idempotent: re-running the planner cannot duplicate an edge.
* Ownership is *not* duplicated onto the edge — it is reached through
  ``source_chunk_id -> document_chunks.document_id -> documents.user_id``, so a
  traverser can only ever reach its own rows.
* Self edges are prevented in ``graph/service.py`` (a CHECK constraint would be
  redundant and would block legitimate future self-relations).

The upgrade is safe to re-apply: it is a no-op when the table already exists.

Revision ID: 005
Revises: 004
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "document_graph_edges"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        # Already present (e.g. re-run against a partially migrated database).
        return

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "relation",
            name="uq_document_graph_edges_triplet",
        ),
    )

    op.create_index(
        "ix_document_graph_edges_document_id", _TABLE, ["document_id"]
    )
    op.create_index(
        "ix_document_graph_edges_source_chunk_id", _TABLE, ["source_chunk_id"]
    )
    op.create_index(
        "ix_document_graph_edges_target_chunk_id", _TABLE, ["target_chunk_id"]
    )
    op.create_index("ix_document_graph_edges_relation", _TABLE, ["relation"])
    # Adjacency lookups always filter by source and sort/scan by relation, so a
    # composite index serves the traversal better than the single-column one.
    op.create_index(
        "ix_document_graph_edges_source_relation",
        _TABLE,
        ["source_chunk_id", "relation"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    op.drop_index("ix_document_graph_edges_source_relation", table_name=_TABLE)
    op.drop_index("ix_document_graph_edges_relation", table_name=_TABLE)
    op.drop_index("ix_document_graph_edges_target_chunk_id", table_name=_TABLE)
    op.drop_index("ix_document_graph_edges_source_chunk_id", table_name=_TABLE)
    op.drop_index("ix_document_graph_edges_document_id", table_name=_TABLE)
    op.drop_table(_TABLE)
