"""Round-trip tests for the newest migrations (``007_add_table_rows``,
``008_add_generation_verification``).

The migrations are exercised by the real Alembic machinery against a throwaway
SQLite file, so nothing here touches the configured production database:

1. ``alembic stamp 006`` records revision 006 in the version table *without*
   running any DDL — which is what lets the later revisions run on their own
   (the chain's earlier revisions contain PostgreSQL-only DDL such as
   ``CREATE EXTENSION vector`` and cannot execute on SQLite);
2. the one table those revisions *alter* is stood up minimally, because
   ``stamp`` does not create it either (see :func:`_stage_at_previous_revision`);
3. ``alembic upgrade head`` therefore runs exactly the 007 upgrade and the 008
   upgrade on top of it;
4. ``alembic downgrade 006`` runs exactly their downgrades, in reverse.

The assertions read the real database schema (``PRAGMA table_info`` /
``PRAGMA index_list``), so a migration that silently did nothing would fail
rather than appear to pass.
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[3]
VERSIONS_DIR = BACKEND_DIR / "migrations" / "versions"
TABLE = "document_table_rows"
RELIABILITY_TABLE = "reliability_logs"
PREVIOUS_REVISION = "006"

EXPECTED_COLUMNS = {
    "id",
    "document_id",
    "table_element_id",
    "row_index",
    "is_header",
    "header_repeated",
    "cells",
    "content",
    "page_number",
    "heading_path",
    "section",
    "token_count",
    "parser_version",
    "created_at",
}

EXPECTED_INDEXES = {
    "ix_document_table_rows_document_id",
    "ix_document_table_rows_table_element_id",
    "ix_document_table_rows_document_element_row",
}


def _run_alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _alembic(db_path: Path, *args: str) -> str:
    result = _run_alembic(db_path, *args)
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result.stdout + result.stderr


def _declared_revisions() -> dict[str, str | None]:
    """``revision -> down_revision`` as declared by the migration scripts.

    Every revision declares its identifiers as module-level literals, so the
    chain's shape can be read without importing (and therefore executing) the
    migration modules.  Deriving it from the files is deliberate: the previous,
    hard-coded expectation still said 007 was head after 008 landed, and that
    only went stale silently because the number was written down twice.
    """
    chain: dict[str, str | None] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        revision = re.search(
            r"^revision[^=\n]*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE
        )
        if revision is None:  # not a revision module
            continue
        down = re.search(
            r"^down_revision[^=\n]*=\s*(?:None|[\"']([^\"']+)[\"'])",
            text,
            re.MULTILINE,
        )
        chain[revision.group(1)] = down.group(1) if down else None
    return chain


def _single_head() -> str:
    """The one revision no other revision descends from."""
    chain = _declared_revisions()
    assert chain, f"no revisions found in {VERSIONS_DIR}"
    parents = {down for down in chain.values() if down is not None}
    heads = [revision for revision in chain if revision not in parents]
    assert len(heads) == 1, f"the revisions directory declares {len(heads)} heads: {heads}"
    return heads[0]


def _stage_at_previous_revision(db_path: Path) -> None:
    """Put the file in the state revision 006 leaves behind on this platform.

    ``stamp`` records the version without running DDL, so the file has neither
    ``document_table_rows`` (007 creates it) nor ``reliability_logs`` (001
    creates it, with PostgreSQL-only ``UUID``/``JSONB`` DDL that cannot run on
    SQLite).  007 creates its own table; 008 only *alters* ``reliability_logs``,
    so the test supplies the single precondition 008 depends on — the table
    exists, without the column under test.  That minimal stand-in is the honest
    form of the precondition: it is not a substitute schema, and the ALTER still
    runs against a real table.
    """
    _alembic(db_path, "stamp", PREVIOUS_REVISION)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"CREATE TABLE {RELIABILITY_TABLE} (id VARCHAR(32) PRIMARY KEY)")


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows}


def _columns(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({TABLE})").fetchall()
    return {row[1] for row in rows}


def _indexes(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA index_list({TABLE})").fetchall()
    return {row[1] for row in rows}


def _reliability_columns(db_path: Path) -> dict[str, tuple[str, int]]:
    """``column -> (declared type, notnull flag)`` for ``reliability_logs``."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({RELIABILITY_TABLE})").fetchall()
    return {row[1]: (row[2], row[3]) for row in rows}


class TestTableRowMigration:
    def test_upgrade_creates_the_table_and_downgrade_removes_it(self, tmp_path):
        db_path = tmp_path / "migration.db"

        _stage_at_previous_revision(db_path)
        assert TABLE not in _table_names(db_path)

        _alembic(db_path, "upgrade", "head")

        tables = _table_names(db_path)
        assert TABLE in tables
        assert _columns(db_path) == EXPECTED_COLUMNS
        assert EXPECTED_INDEXES <= _indexes(db_path)
        assert "alembic_version" in tables

        _alembic(db_path, "downgrade", PREVIOUS_REVISION)

        assert TABLE not in _table_names(db_path)

    def test_upgrade_is_repeatable_on_an_already_migrated_database(self, tmp_path):
        db_path = tmp_path / "repeat.db"

        _stage_at_previous_revision(db_path)
        _alembic(db_path, "upgrade", "head")
        # A second upgrade finds the table present (has_table guard) and the
        # version already at head: it must not fail and must not duplicate DDL.
        _alembic(db_path, "upgrade", "head")

        assert _columns(db_path) == EXPECTED_COLUMNS

    def test_revision_chain_has_exactly_one_head(self, tmp_path):
        output = _alembic(tmp_path / "heads.db", "heads")

        heads = [line.split()[0] for line in output.splitlines() if "(head)" in line]
        assert len(heads) == 1, f"expected exactly one head, got {heads}:\n{output}"
        assert heads[0] == _single_head(), (
            "alembic reports a head the revision scripts do not describe"
        )

    def test_the_head_revision_descends_from_the_tested_anchor(self, tmp_path):
        """Staging at 006 must actually exercise 007 — not skip past it.

        Derived from the revision scripts, so adding a revision cannot make this
        assertion stale the way the hard-coded "007 is head" expectation did.
        """
        chain = _declared_revisions()
        assert PREVIOUS_REVISION in chain

        ancestors, current = set(), _single_head()
        assert current != PREVIOUS_REVISION, "the tested anchor is already head"
        while current is not None:
            ancestors.add(current)
            current = chain.get(current)

        assert PREVIOUS_REVISION in ancestors, (
            f"{_single_head()} does not descend from {PREVIOUS_REVISION}"
        )

    def test_the_generation_column_is_added_and_dropped_on_sqlite(self, tmp_path):
        """008's ``JSONB`` column must be runnable on the test platform.

        PostgreSQL is the production database and keeps ``JSONB``; SQLite has no
        such type, so the revision declares a dialect variant rather than a bare
        ``JSONB``.  This executes the real ``ALTER TABLE`` and its downgrade, so a
        revision that declared an unrenderable type — or that silently added
        nothing — fails here rather than in a deployment.
        """
        db_path = tmp_path / "generation.db"
        _stage_at_previous_revision(db_path)
        assert "generation_json" not in _reliability_columns(db_path)

        _alembic(db_path, "upgrade", "head")

        added = _reliability_columns(db_path)["generation_json"]
        assert added == ("JSON", 0), f"unexpected column specification: {added}"

        _alembic(db_path, "downgrade", PREVIOUS_REVISION)

        assert "generation_json" not in _reliability_columns(db_path)

    def test_the_new_table_is_additive_for_the_element_stream(self, tmp_path):
        """007 must not touch document_structure_elements."""
        db_path = tmp_path / "additive.db"
        _stage_at_previous_revision(db_path)
        _alembic(db_path, "upgrade", "head")

        with sqlite3.connect(db_path) as conn:
            # The element table is not created by 007 (it belongs to 006), and
            # 007 introduces no column on it.
            element_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE name='document_structure_elements'"
            ).fetchall()

        assert element_tables == [], (
            "007 created or depended on the structure element table"
        )
