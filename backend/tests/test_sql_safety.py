"""Tests verifying that production SQL code is safe from injection.

These tests inspect the actual source code to confirm that:
  • No f-string interpolation of user input into SQL
  • Parameterised queries are used for all dynamic values
  • The dangerous patterns identified in the Phase 0 audit are gone
"""

import re
import pathlib

import pytest


# Files that contain raw SQL queries in production code
_SQL_FILES = [
    pathlib.Path(__file__).resolve().parent.parent / "embeddings" / "routes.py",
    pathlib.Path(__file__).resolve().parent.parent / "chat" / "rag.py",
]


class TestNoFStringSQL:
    """Verify that no production SQL uses f-string interpolation."""

    @pytest.mark.parametrize("sql_file", _SQL_FILES, ids=lambda p: p.name)
    def test_no_fstring_in_text_calls(self, sql_file: pathlib.Path):
        """Reject text(f\"...SELECT...\") patterns in production code."""
        content = sql_file.read_text(encoding="utf-8")
        # Match: text(\n  f"SELECT  or text(f"SELECT
        pattern = re.compile(r"text\(\s*f[\"']", re.IGNORECASE)
        matches = pattern.findall(content)
        assert not matches, (
            f"{sql_file.name} contains f-string SQL injection pattern: "
            f"{matches}.  Use parameterised queries with :param syntax."
        )

    @pytest.mark.parametrize("sql_file", _SQL_FILES, ids=lambda p: p.name)
    def test_no_string_format_in_text_calls(self, sql_file: pathlib.Path):
        """Reject text(\"...\".format(...)) patterns in production code."""
        content = sql_file.read_text(encoding="utf-8")
        pattern = re.compile(r"text\([\"'].*\.format\(", re.IGNORECASE)
        matches = pattern.findall(content)
        assert not matches, (
            f"{sql_file.name} contains .format() SQL injection pattern: "
            f"{matches}.  Use parameterised queries with :param syntax."
        )


class TestParameterisedQueries:
    """Verify that the critical SQL uses :param binding."""

    def test_embeddings_search_uses_binding(self):
        sql_file = _SQL_FILES[0]
        content = sql_file.read_text(encoding="utf-8")
        # Must use named parameters for embedding, user_id, top_k
        assert ":embedding" in content, "embeddings search must bind :embedding"
        assert ":user_id" in content, "embeddings search must bind :user_id"
        assert ":top_k" in content, "embeddings search must bind :top_k"

    def test_rag_search_uses_binding(self):
        sql_file = _SQL_FILES[1]
        content = sql_file.read_text(encoding="utf-8")
        assert ":embedding" in content, "RAG search must bind :embedding"
        assert ":user_id" in content, "RAG search must bind :user_id"
        assert ":top_k" in content, "RAG search must bind :top_k"

    def test_embeddings_search_passes_params_dict(self):
        sql_file = _SQL_FILES[0]
        content = sql_file.read_text(encoding="utf-8")
        assert "db.execute(" in content
        # Must pass a params dict as second arg to db.execute
        pattern = re.compile(r"db\.execute\(\s*search_sql\s*,\s*\{")
        assert pattern.search(content), (
            "embeddings search must pass parameters dict to db.execute()"
        )

    def test_rag_search_passes_params_dict(self):
        sql_file = _SQL_FILES[1]
        content = sql_file.read_text(encoding="utf-8")
        pattern = re.compile(r"db\.execute\(\s*search_sql\s*,\s*\{")
        assert pattern.search(content), (
            "RAG search must pass parameters dict to db.execute()"
        )
