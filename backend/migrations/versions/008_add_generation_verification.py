"""Add persisted generation/verification metadata to reliability_logs.

The generative answer path is additive: it reuses ``reliability_logs`` for the
last-query snapshot, but it must persist facts the extractive path does not
produce — the engine and model used, the requested mark format, decoding
latency, whether the model abstained, and the deterministic verification result
(claim count, supported claims, unsupported claims, citation accuracy).

One nullable JSONB column is sufficient and keeps the migration additive:

* ``generation_json`` is ``NULL`` for rows written by the extractive path, so
  existing rows and clients are unaffected;
* no existing column changes type or meaning, and there is no backfill;
* downgrade drops only this column.

The column type is dialect-explicit rather than bare ``JSONB``:
``postgresql.JSONB()`` is the production type and renders as ``JSONB`` on
PostgreSQL exactly as before, while ``sa.JSON`` is registered as its variant
for SQLite.  SQLite has no ``JSONB`` and no renderer for it, so a bare ``JSONB``
makes this revision impossible to execute there at all.  The revision is
exercised against a throwaway SQLite file by
``tests/integration/documents/test_table_row_migration.py``, which drives real
Alembic in a subprocess — outside the pytest process, so the suite's
dialect-scoped DDL rules (``tests/conftest.py``) do not apply to it.  Declaring
the variant on the type keeps PostgreSQL's schema byte-identical and makes the
revision runnable on SQLite without a test-side shim.

Revision ID: 008
Revises: 007_add_table_rows
Create Date: 2026-10-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

#: ``JSONB`` on PostgreSQL (the production database), ``JSON`` on SQLite (no
#: ``JSONB`` type or renderer).  PostgreSQL DDL is unchanged: ``JSONB``.
generation_json_type = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reliability_logs",
        sa.Column("generation_json", generation_json_type, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reliability_logs", "generation_json")
