"""Opt-in execution of topic SQL over synthetic CTEs, with no database writes.

Set DOCUMIND_TEST_POSTGRES_CONTAINER to an existing PostgreSQL Docker container.
The transaction is READ ONLY. CTEs shadow both application table names, so these
checks do not read or change uploaded documents or provision a test database.
"""
from __future__ import annotations

import json
import os
import subprocess
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from chat.rag import SourceChunk
from generation.topic_context import _TOPICS, assemble_topic_context, select_topic_heading_path


pytestmark = pytest.mark.skipif(
    not os.environ.get("DOCUMIND_TEST_POSTGRES_CONTAINER"),
    reason="Opt-in read-only PostgreSQL CTE checks require an existing container",
)
OWNER, OTHER, DOC, FOREIGN_DOC = [str(UUID(int=i)) for i in range(1, 5)]


def chunk(index, heading, content=None, *, document=DOC):
    return dict(
        id=str(UUID(int=index + (100 if document == DOC else 200))),
        document_id=document, chunk_index=index, content=content or f"Exact source sentence {index}.",
        page=index + 1, heading_path=heading, section=heading[-1] if heading else None,
        element_type="paragraph", token_count=12, chunker_version="structure-v2",
        source_element_indices=[index],
    )


def execute_topic_query(chunks, seeds, *, owner=OWNER, max_bytes=128000, question="Explain VAWT"):
    documents = [{"id": DOC, "user_id": OWNER}, {"id": FOREIGN_DOC, "user_id": OTHER}]
    # A parameterized JSON recordset preserves the actual column types used by
    # PostgreSQL; no CREATE, INSERT, DELETE or temporary table is needed.
    fixture_ctes = """WITH documents AS (
      SELECT * FROM jsonb_to_recordset(CAST(:fixture_documents AS jsonb))
      AS d(id uuid, user_id uuid)
    ), document_chunks AS (
      SELECT * FROM jsonb_to_recordset(CAST(:fixture_chunks AS jsonb))
      AS c(id uuid, document_id uuid, chunk_index integer, content text, page integer,
           heading_path jsonb, section text, element_type text, token_count integer,
           chunker_version text, source_element_indices jsonb)
    ), """
    production = str(_TOPICS).strip()
    assert production.startswith("WITH requested AS (")
    topic_paths = {}
    for row in chunks:
        if row["id"] not in seeds:
            continue
        path = tuple(row["heading_path"] or ())
        selected = select_topic_heading_path(question, path)
        if selected:
            topic_paths[row["id"]] = selected
    statement = text(fixture_ctes + production.removeprefix("WITH ")).bindparams(
        fixture_documents=json.dumps(documents), fixture_chunks=json.dumps(chunks),
        seed_ids=json.dumps(seeds), topic_paths=json.dumps(topic_paths), user_id=owner, max_bytes=max_bytes,
    )
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    sql = "BEGIN READ ONLY;\nSELECT COALESCE(jsonb_agg(row_to_json(result)), '[]') FROM (\n" + sql + "\n) result;\nROLLBACK;"
    result = subprocess.run(
        ["docker", "exec", "-i", os.environ["DOCUMIND_TEST_POSTGRES_CONTAINER"],
         "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
         "-U", os.environ.get("DOCUMIND_TEST_POSTGRES_USER", "documind"),
         "-d", os.environ.get("DOCUMIND_TEST_POSTGRES_DB", "documind")],
        input=sql, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


def test_hierarchical_topic_recovers_sibling_leaves_and_preserves_provenance():
    rows = [
        chunk(0, ["Wind", "HAWT", "Horizontal rotor"]),
        chunk(1, ["Wind", "VAWT", "Vertical rotor"]),
        chunk(2, ["Wind", "VAWT", "Shaft connection"]),
        chunk(3, ["Wind", "VAWT", "Generator conversion"]),
        chunk(4, ["Wind", "Tidal", "Tidal barrage"]),
    ]
    selected = execute_topic_query(rows, [rows[1]["id"]])
    assert [row["id"] for row in selected] == [row["id"] for row in rows[1:4]]
    source = SourceChunk(rows[1]["id"], rows[1]["content"], .83, DOC, "energy.pdf", 2,
                         heading_path=tuple(rows[1]["heading_path"]))
    expanded, coverage = assemble_topic_context([source], selected)
    assert coverage["status"] == "complete"
    assert [source.content for source in expanded] == [row["content"] for row in rows[1:4]]
    assert [source.page for source in expanded] == [2, 3, 4]
    assert all(source.document_id == DOC and source.document_name == "energy.pdf" for source in expanded)
    assert [source.heading_path for source in expanded] == [tuple(row["heading_path"]) for row in rows[1:4]]


def test_repeated_parent_heading_after_another_topic_is_a_separate_occurrence():
    rows = [
        chunk(0, ["Wind", "VAWT", "Definition"]),
        chunk(1, ["Wind", "VAWT", "Shaft"]),
        chunk(2, ["Wind", "HAWT", "Horizontal rotor"]),
        chunk(3, ["Wind", "VAWT", "Definition"]),
        chunk(4, ["Wind", "VAWT", "Generator"]),
    ]
    selected = execute_topic_query(rows, [rows[0]["id"], rows[3]["id"]])
    early = [row for row in selected if row["seed_id"] == rows[0]["id"]]
    later = [row for row in selected if row["seed_id"] == rows[3]["id"]]
    assert [row["id"] for row in early] == [row["id"] for row in rows[:2]]
    assert [row["id"] for row in later] == [row["id"] for row in rows[3:]]
    assert early[0]["group_id"] != later[0]["group_id"]


def test_parent_expansion_never_reads_foreign_owner_seed_or_siblings():
    own = [chunk(0, ["Wind", "VAWT", "Definition"]), chunk(1, ["Wind", "VAWT", "Shaft"])]
    foreign = [chunk(i, ["Wind", "VAWT", "Private"], "PRIVATE SOURCE", document=FOREIGN_DOC) for i in range(2)]
    selected = execute_topic_query(own + foreign, [own[0]["id"], foreign[0]["id"]])
    assert {row["id"] for row in selected} == {row["id"] for row in own}
    assert all(row["seed_id"] == own[0]["id"] for row in selected)
    assert "PRIVATE" not in str(selected)


def test_byte_limit_keeps_late_seed_and_reports_partial_parent():
    rows = [chunk(i, ["Wind", "VAWT", f"Detail {i}"], f"Detail {i}: " + "source " * 15 + ".") for i in range(5)]
    selected = execute_topic_query(rows, [rows[-1]["id"]], max_bytes=150)
    assert rows[-1]["id"] in {row["id"] for row in selected}
    assert len(selected) < len(rows)
    source = SourceChunk(rows[-1]["id"], rows[-1]["content"], .8, DOC, "energy.pdf", 5)
    expanded, coverage = assemble_topic_context([source], selected, max_bytes=150)
    assert source.chunk_id in {item.chunk_id for item in expanded}
    assert coverage["status"] == "partial"
    assert not any(item.topic_context_complete for item in expanded)


def test_single_level_topics_are_not_merged_across_different_headings():
    rows = [chunk(0, ["Wind"]), chunk(1, ["Wind"]), chunk(2, ["Tidal"])]
    selected = execute_topic_query(rows, [rows[0]["id"]])
    assert [row["id"] for row in selected] == [row["id"] for row in rows[:2]]


@pytest.mark.parametrize("question", ["", "Explain shaft connection", "Explain VAWT shaft connection"])
def test_no_question_or_narrow_leaf_question_retains_exact_topic(question):
    rows = [
        chunk(0, ["Wind", "VAWT", "Vertical rotor"]),
        chunk(1, ["Wind", "VAWT", "Shaft connection"]),
        chunk(2, ["Wind", "VAWT", "Generator conversion"]),
    ]
    selected = execute_topic_query(rows, [rows[1]["id"]], question=question)
    assert [row["id"] for row in selected] == [rows[1]["id"]]


def test_matching_root_heading_seed_recovers_its_child_steps():
    rows = [
        chunk(0, ["VAWT"], "A VAWT has a vertical rotor axis and accepts changing wind directions."),
        chunk(1, ["VAWT", "Shaft connection"]),
        chunk(2, ["VAWT", "Generator conversion"]),
        chunk(3, ["HAWT", "Horizontal rotor"]),
    ]
    selected = execute_topic_query(rows, [rows[0]["id"]])
    assert [row["id"] for row in selected] == [row["id"] for row in rows[:3]]


def test_overlapping_exact_and_parent_ranges_never_hide_missing_tail():
    rows = [
        chunk(0, ["Wind", "VAWT"], "The VAWT definition names its vertical rotor axis."),
        chunk(1, ["Wind", "VAWT", "Shaft connection"], "The rotating shaft transfers mechanical power to the generator."),
        chunk(2, ["Wind", "VAWT", "Generator conversion"], "The generator converts mechanical rotation into electrical power."),
        chunk(3, ["Wind", "HAWT"], "Horizontal axis turbines have a different rotor orientation."),
    ]
    selected = execute_topic_query(rows, [rows[0]["id"], rows[1]["id"]], max_bytes=100)
    seeds = [SourceChunk(row["id"], row["content"], .8, DOC, "energy.pdf", row["page"],
                         heading_path=tuple(row["heading_path"])) for row in rows[:2]]
    expanded, coverage = assemble_topic_context(seeds, selected, max_bytes=100)
    assert len({source.chunk_id for source in expanded}) == len(expanded)
    assert rows[2]["id"] not in {source.chunk_id for source in expanded}
    assert coverage["status"] == "partial"
    assert any(not source.topic_context_complete for source in expanded)


def test_overlapping_parent_ranges_count_previously_emitted_source_once():
    rows = [
        chunk(0, ["VAWT"], "The VAWT definition names its vertical rotor axis."),
        chunk(1, ["VAWT", "VAWT shaft connection"], "The rotating shaft transfers mechanical power to the generator."),
        chunk(2, ["VAWT", "VAWT shaft connection", "Bearings"], "Bearings support the rotating shaft and permit smooth movement."),
        chunk(3, ["VAWT", "Generator conversion"], "The generator converts mechanical rotation into electrical power."),
    ]
    selected = execute_topic_query(rows, [rows[1]["id"], rows[0]["id"]], question="Explain VAWT shaft connection")
    seeds = [SourceChunk(row["id"], row["content"], .8, DOC, "energy.pdf", row["page"],
                         heading_path=tuple(row["heading_path"])) for row in (rows[1], rows[0])]
    expanded, coverage = assemble_topic_context(seeds, selected)
    assert len({source.chunk_id for source in expanded}) == len(expanded) == 4
    assert coverage["status"] == "complete"
    assert coverage["completeGroups"] == coverage["groups"]
