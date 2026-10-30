"""Add the reverse composite edge indexes used by graph-expanded retrieval.

Why
---
Structural traversal is adjacency work in two directions:

* **outward** (what a chunk/section leads to) filters ``source`` + ``relation``;
* **inward** (which parent/section contains this chunk) filters ``target`` +
  ``relation``.

Revision ``005`` already created ``ix_document_graph_edges_source_relation`` for
the chunk graph, and ``006`` created
``ix_document_structure_edges_source_relation`` for the element graph, so the
outward direction is covered.  The inward direction is not: it can only use the
single-column ``target_*`` index and then filter ``relation`` row by row.  The
15-mark expansion path walks a seed *up* to its parent heading before walking
out to sibling chunks, which is exactly that query shape.

This revision adds only the two missing indexes.  It deliberately does **not**
recreate ``(source, relation)`` (it exists) and does **not** drop the
single-column indexes: they still serve plain foreign-key lookups and cascade
deletes.

Additivity
----------
* indexes only — no table, column, constraint or row changes, nothing backfilled;
* each ``CREATE INDEX`` is guarded, so re-running against a database where the
  index already exists is a no-op rather than an error;
* downgrade drops only the two indexes this revision created.

Revision ID: 010
Revises: 009
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHUNK_EDGES = "document_graph_edges"
_STRUCTURE_EDGES = "document_structure_edges"

_CHUNK_TARGET_INDEX = "ix_document_graph_edges_target_relation"
_STRUCTURE_TARGET_INDEX = "ix_document_structure_edges_target_relation"


def _index_names(table: str) -> set[str] | None:
    """Existing index names on ``table``, or ``None`` when the table is absent.

    ``None`` is not "no indexes": it means there is nothing to index.  A
    database that was stamped to an earlier revision (the SQLite migration
    round-trip tests do exactly that) has no edge tables, and creating an index
    on a missing table would abort the whole upgrade.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return None
    return {index["name"] for index in inspector.get_indexes(table)}


def _add_index(table: str, name: str, columns: list[str]) -> None:
    existing = _index_names(table)
    if existing is None or name in existing:
        return
    op.create_index(name, table, columns)


def _drop_index(table: str, name: str) -> None:
    existing = _index_names(table)
    if existing is None or name not in existing:
        return
    op.drop_index(name, table_name=table)


def upgrade() -> None:
    _add_index(_CHUNK_EDGES, _CHUNK_TARGET_INDEX, ["target_chunk_id", "relation"])
    _add_index(
        _STRUCTURE_EDGES,
        _STRUCTURE_TARGET_INDEX,
        ["target_element_id", "relation"],
    )


def downgrade() -> None:
    _drop_index(_STRUCTURE_EDGES, _STRUCTURE_TARGET_INDEX)
    _drop_index(_CHUNK_EDGES, _CHUNK_TARGET_INDEX)
