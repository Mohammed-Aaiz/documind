"""Opt-in execution of topic SQL over synthetic CTEs, with no database writes.

Set DOCUMIND_TEST_POSTGRES_CONTAINER to an existing PostgreSQL Docker container.
The transaction is READ ONLY. CTEs shadow both application table names, so these
checks do not read or change uploaded documents or provision a test database.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from chat.rag import SourceChunk
from generation.topic_context import (
    _TOPICS, assemble_topic_context, select_topic_heading_path, select_topic_window_subject,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("DOCUMIND_TEST_POSTGRES_CONTAINER"),
    reason="Opt-in read-only PostgreSQL CTE checks require an existing container",
)
OWNER, OTHER, DOC, FOREIGN_DOC = [str(UUID(int=i)) for i in range(1, 5)]
DOCUMENTS = [
    {"id": DOC, "user_id": OWNER, "name": "energy.pdf", "status": "ready"},
    {"id": FOREIGN_DOC, "user_id": OTHER, "name": "private.pdf", "status": "ready"},
]


def chunk(index, heading, content=None, *, document=DOC):
    return dict(
        id=str(UUID(int=index + (100 if document == DOC else 200))),
        document_id=document, chunk_index=index, content=content or f"Exact source sentence {index}.",
        page=index + 1, heading_path=heading, section=heading[-1] if heading else None,
        element_type="paragraph", token_count=12, chunker_version="structure-v2",
        source_element_indices=[index],
    )


def execute_fixture_query(query, chunks, documents, **parameters):
    # A parameterized JSON recordset preserves the actual column types used by
    # PostgreSQL; no CREATE, INSERT, DELETE or temporary table is needed.
    fixture_ctes = """WITH documents AS (
      SELECT * FROM jsonb_to_recordset(CAST(:fixture_documents AS jsonb))
      AS d(id uuid, user_id uuid, name text, status text)
    ), document_chunks AS (
      SELECT * FROM jsonb_to_recordset(CAST(:fixture_chunks AS jsonb))
      AS c(id uuid, document_id uuid, chunk_index integer, content text, page integer,
           heading_path jsonb, section text, element_type text, token_count integer,
           chunker_version text, source_element_indices jsonb)
    ), """
    production = str(query).strip()
    assert production.startswith("WITH ")
    statement = text(fixture_ctes + production.removeprefix("WITH ")).bindparams(
        fixture_documents=json.dumps(documents), fixture_chunks=json.dumps(chunks),
        **parameters,
    )
    # A standalone dialect has not negotiated the server's string setting.
    # The real PostgreSQL connection uses standard_conforming_strings=on;
    # double-escaping JSON backslashes here would turn source newlines into
    # literal "\\n" text before the production query even sees this fixture.
    dialect = postgresql.dialect()
    dialect._backslash_escapes = False
    sql = str(statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
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


def execute_topic_query(chunks, seeds, *, owner=OWNER, max_bytes=128000, question="Explain VAWT"):
    topic_paths, window_subjects = {}, {}
    for row in chunks:
        if row["id"] not in seeds:
            continue
        path = tuple(row["heading_path"] or ())
        selected = select_topic_heading_path(question, path)
        if selected:
            topic_paths[row["id"]] = selected
        subject = select_topic_window_subject(question, path)
        if subject and selected == path:
            window_subjects[row["id"]] = subject
    return execute_fixture_query(
        _TOPICS, chunks, DOCUMENTS, seed_ids=json.dumps(seeds), topic_paths=json.dumps(topic_paths),
        window_subjects=json.dumps(window_subjects), user_id=owner, max_bytes=max_bytes,
    )


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


def fragmented_hawt_chunks():
    """Legacy extraction stores a subject title and every body step as leaves.

    The next page's gearbox paragraph becomes a new root. The topic repair
    must recover this source sequence without widening to all of Wind Energy.
    """
    wind = "CONVERSION\nWind Energy"
    definition = "Horizontal Axis Wind Turbines (HAWT): Most common, rotor blades face the wind."
    first = "1. Wind strikes the blades and produces lift around the aerodynamic surfaces."
    second = "2. The lift force causes the blades and rotor to rotate around the horizontal shaft."
    third = "3. Shaft transmits rotation: The low-speed shaft transfers mechanical power to the drivetrain."
    fourth = "CONVERSION\n4. Gearbox increases speed: In conventional HAWTs, a gearbox increases rotational speed."
    fifth = "5. Generator produces electricity: The generator converts mechanical energy into electrical energy."
    sixth = "6. A yaw mechanism keeps the rotor properly aligned with the wind direction."
    vertical = "CONVERSION\nVertical Axis Wind Turbines (VAWT): Blades are perpendicular to the ground."
    rows = [
        chunk(0, [wind, "Tidal energy"], "Tidal energy harnesses the rise and fall of seawater."),
        chunk(1, [wind, "Types"], "Types"),
        chunk(2, [wind, definition], definition),
        chunk(3, [wind, "Working of HAWT"], "Working of HAWT"),
        chunk(4, [wind, "Working principle"], "Wind energy is converted into mechanical and electrical energy."),
        chunk(5, [wind, "Working steps"], "Working steps"),
        chunk(6, [wind, first], first),
        chunk(7, [wind, second], second),
        chunk(8, [wind, third], third),
        chunk(9, ["[Date]\nWIND,TIDAL AND OCEAN THERMAL ENERGY"], "MODULE 4"),
        chunk(10, [fourth], fourth),
        chunk(11, [fourth, fifth], fifth),
        chunk(12, [fourth, sixth], sixth),
        chunk(13, [vertical], vertical),
        chunk(14, [vertical, "Working of VAWT"], "The VAWT rotor rotates around a vertical shaft."),
    ]
    for row in rows:
        row["page"] = 10 if row["chunk_index"] < 8 else 11 if row["chunk_index"] < 13 else 12
    return rows


def test_named_working_topic_recovers_body_heading_siblings_across_page_header():
    rows = fragmented_hawt_chunks()
    selected = execute_topic_query(
        rows, [rows[2]["id"]],
        question="Explain the working of Horizontal Axis Wind Turbines (HAWT) with a neat diagram.",
    )
    required = [rows[index] for index in (2, 6, 7, 8, 10, 11, 12)]
    assert {row["id"] for row in required} <= {row["id"] for row in selected}
    assert not {rows[index]["id"] for index in (0, 13, 14)} & {row["id"] for row in selected}
    original = SourceChunk(rows[2]["id"], rows[2]["content"], .8, DOC, "energy.pdf", rows[2]["page"],
                           heading_path=tuple(rows[2]["heading_path"]))
    expanded, _ = assemble_topic_context([original], selected)
    sources = {source.chunk_id: source for source in expanded}
    for row in required:
        assert sources[row["id"]].content == row["content"]
        assert sources[row["id"]].page == row["page"]
        assert sources[row["id"]].document_id == DOC
        assert sources[row["id"]].heading_path == tuple(row["heading_path"])


def test_fragmented_working_topic_remains_owner_scoped_and_stops_at_next_turbine():
    rows = fragmented_hawt_chunks()
    foreign = chunk(2, rows[2]["heading_path"], "PRIVATE HAWT SOURCE", document=FOREIGN_DOC)
    selected = execute_topic_query(
        rows + [foreign], [rows[2]["id"], foreign["id"]],
        question="Explain HAWT working with a neat diagram.",
    )
    returned = {row["id"] for row in selected}
    assert rows[6]["id"] in returned and rows[11]["id"] in returned
    assert not {rows[0]["id"], rows[13]["id"], rows[14]["id"], foreign["id"]} & returned
    assert "PRIVATE" not in str(selected)


def test_narrow_hawt_shaft_question_does_not_expand_the_whole_working_window():
    rows = fragmented_hawt_chunks()
    selected = execute_topic_query(
        rows, [rows[8]["id"]], question="Explain HAWT shaft transmission of rotation.",
    )
    assert [row["id"] for row in selected] == [rows[8]["id"]]


@pytest.mark.asyncio
async def test_routed_retrieval_recovers_the_named_topic_missing_after_reranking(monkeypatch):
    from chat import rag
    from generation import reranking, service, spatial_retrieval
    from graph import service as graph_service

    rows = fragmented_hawt_chunks()
    stale_doc = str(UUID(int=5))
    documents = [*DOCUMENTS, {"id": stale_doc, "user_id": OWNER, "name": "stale.pdf", "status": "failed"}]
    foreign = chunk(0, ["VAWT"], "Private (VAWT)", document=FOREIGN_DOC)
    stale = chunk(1, ["VAWT"], "Stale (VAWT)", document=stale_doc)
    unrelated = chunk(15, ["SWT"], "Small Wind Turbines (SWT)")
    rows.extend([foreign, stale, unrelated])

    class FixtureDB:
        @asynccontextmanager
        async def begin_nested(self):
            yield

        async def execute(self, query, parameters):
            selected = execute_fixture_query(query, rows, documents, **parameters)
            return SimpleNamespace(fetchall=lambda: selected)

    def seed(row, score):
        return SourceChunk(
            row["id"], row["content"], score, DOC, "energy.pdf", row["page"],
            heading_path=tuple(row["heading_path"]),
        )

    retained, lower_ranked = seed(rows[2], .83), seed(rows[13], .51)
    dense = [retained, seed(rows[3], .82), lower_ranked]

    async def rerank(question, values, *, top_k):
        return values[:top_k], {"status": "applied"}

    async def no_spatial_enrichment(db, user_id, question, values):
        return values, "not_searched"

    monkeypatch.setattr(rag, "retrieve_hybrid_chunks", AsyncMock(return_value=dense))
    monkeypatch.setattr(rag, "dual_path_enabled", lambda: False)
    monkeypatch.setattr(rag, "table_evidence_enabled", lambda: False)
    monkeypatch.setattr(graph_service, "knowledge_graph_status", AsyncMock(return_value="empty"))
    monkeypatch.setattr(reranking, "rerank_candidates", rerank)
    monkeypatch.setattr(spatial_retrieval, "is_spatial_query", lambda question: False)
    monkeypatch.setattr(spatial_retrieval, "enrich_spatial_sources", no_spatial_enrichment)

    retrieved = await service.retrieve_evidence(
        FixtureDB(), OWNER, "Explain with diagrams: (a) HAWT working (b) VAWT working.",
        top_k=2, answer_format=10, query_routing=True,
    )
    sources = {item.chunk_id: item for item in retrieved}
    recovered = sources[lower_ranked.chunk_id]
    assert recovered.score == 0 and recovered.retrieval_path == "structural"
    assert recovered.document_id == DOC and recovered.document_name == "energy.pdf"
    assert (recovered.content, recovered.page, recovered.heading_path) == (
        lower_ranked.content, lower_ranked.page, lower_ranked.heading_path,
    )
    assert sources[retained.chunk_id].score == .83
    assert sources[retained.chunk_id].retrieval_path == retained.retrieval_path
    assert len(sources) == len(retrieved)
    assert {rows[index]["id"] for index in (6, 7, 8, 10, 11, 12, 14)} <= sources.keys()
    assert not {row["id"] for row in (foreign, stale, unrelated)} & sources.keys()


@pytest.mark.asyncio
@pytest.mark.parametrize("marks", [5, 10, 15])
async def test_recovered_hawt_working_steps_survive_final_diagram_and_evidence_gate(monkeypatch, marks):
    """Exercise SQL recovery, prompt fitting, drawing and the final answer gate.

    The answer model is stubbed only to omit a figure. It does not supply the
    missing steps; those must actually be recovered from the source structure.
    """
    from generation import providers, service
    from generation.planning import extract_citations, text_diagram_blocks, validate_text_diagram
    from generation.providers import ProviderCompletion
    from generation.verification import verify_with_mode

    rows = fragmented_hawt_chunks()
    question = "Explain the working of Horizontal Axis Wind Turbines (HAWT) with a neat diagram."
    selected = execute_topic_query(rows, [rows[2]["id"]], question=question)
    seed_row = rows[2]
    original = SourceChunk(
        seed_row["id"], seed_row["content"], .8, DOC, "energy.pdf", seed_row["page"],
        heading_path=tuple(seed_row["heading_path"]),
    )
    expanded, coverage = assemble_topic_context([original], selected)

    def draft(messages, **kwargs):
        labels = [json.loads(line) for line in messages[-1]["content"].split("Source data (JSON):\n", 1)[1].splitlines()]
        generator = next(label for label in labels
                         if "The generator converts mechanical energy into electrical energy." in label.get("text", ""))
        return ProviderCompletion(
            f"The generator converts mechanical energy into electrical energy [{generator['source']}].",
            "groq", "test-model", "stop",
        )

    complete = AsyncMock(side_effect=draft)
    monkeypatch.setattr(providers, "complete_answer", complete)
    _, result = await service.answer_from_evidence(
        question, expanded, marks, settings=SimpleNamespace(groq_context_tokens=16384),
    )
    assert not result.abstained
    figures = text_diagram_blocks(result.answer)
    assert figures, "Recovered working evidence must produce the requested final diagram"
    assert any([int(value) for value in re.findall(r"(?m)^\|\s*(\d+)\.", figure)] == list(range(1, 7))
               for figure in figures), "The diagram must retain the complete six-step source sequence"
    required_chunks = {rows[index]["id"] for index in (6, 7, 8, 10, 11, 12)}
    expected_citations = {block.index for block in result.blocks if block.chunk_id in required_chunks}
    assert len(expected_citations) == 6
    assert expected_citations <= set(extract_citations("\n".join(figures)))
    assert "VAWT" not in "\n".join(figures) and "tidal" not in "\n".join(figures).lower()
    assert validate_text_diagram(result.answer, result.blocks, question=question)
    assert verify_with_mode(result.answer, result.blocks, question=question).verified
    assert result.verification["verified"]
    assert complete.await_count == 1
    # Recovery is inferred from a damaged heading hierarchy. It must not be
    # presented as proof of complete topic coverage merely because it found six steps.
    assert coverage["status"] == "partial"
    assert any(source.topic_context_kind == "section_window" for source in expanded)


def test_recovered_hawt_window_fallback_keeps_anonymous_steps_and_their_figure():
    from generation.diagrams import ensure_source_diagrams
    from generation.planning import extract_citations, text_diagram_blocks, validate_text_diagram
    from generation.provider_prompt import prepare_prompt
    from generation.types import AnswerFormat
    from generation.verification import verify_with_mode
    from orchestration.service import _build_extractive_fallback

    rows = fragmented_hawt_chunks()
    question = "Explain the working of Horizontal Axis Wind Turbines (HAWT) with a neat diagram."
    selected = execute_topic_query(rows, [rows[2]["id"]], question=question)
    original = SourceChunk(
        rows[2]["id"], rows[2]["content"], .8, DOC, "energy.pdf", rows[2]["page"],
        heading_path=tuple(rows[2]["heading_path"]),
    )
    expanded, _ = assemble_topic_context([original], selected)
    prepared = prepare_prompt(
        question, expanded, [], workspace="student", task="answer",
        answer_format=AnswerFormat.TEN, context_tokens=16384,
    )
    body = _build_extractive_fallback(question, prepared.blocks, 10)
    required_chunks = {rows[index]["id"] for index in (6, 7, 8, 10, 11, 12)}
    expected = {block.index for block in prepared.blocks if block.chunk_id in required_chunks}
    assert len(expected) == 6
    assert expected <= set(extract_citations(body)), "Fallback prose must not omit anonymous working steps"
    assert verify_with_mode(body, prepared.blocks, question=question).verified
    final, notes = ensure_source_diagrams(body, prepared.blocks, question)
    assert text_diagram_blocks(final)
    assert validate_text_diagram(final, prepared.blocks, question=question)
    assert verify_with_mode(final, prepared.blocks, question=question).verified
