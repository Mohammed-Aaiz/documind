"""Persistence of compact table-row evidence through the production persister.

Every test drives the real path: a real generated PDF -> the real extractor and
public parser -> the real ``replace_document_structure`` -> real ORM rows in an
SQLite database with foreign keys enforced (see ``tests/conftest.py``).

What is asserted here is the Phase 2 contract: row evidence is additive, the
``document_structure_elements`` stream (count, types, ``sequence_index`` values)
is untouched, ingestion is idempotent, reprocessing replaces stale rows, deleting
a document removes its rows, and no value is ever fabricated.
"""

from __future__ import annotations

import dataclasses
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select

from documents.models import Document, DocumentTableRow
from documents.parser import ParsedDocument, parse_pdf
from documents.structure import replace_document_structure
from documents.tables import total_row_records
from graph.models import DocumentStructureElement
from tests.fixtures.graph_data import create_document_with_chunks
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_page, new_pdf

REPO_ROOT = Path(__file__).resolve().parents[3].parent
DEMO_PDF = REPO_ROOT / "Field_Robotics_Deployment_and_Maintenance_Report.pdf"
DEMO_LIDAR_ROW = (
    "Lidar Array LR-9",
    "250 h",
    "0-80 m",
    "> 2.5 mm error",
    "Recalibrate on reference rig",
)


def _pdf_bytes(pages: list[list[tuple]]) -> bytes:
    doc = new_pdf()
    for items in pages:
        page = new_page(doc)
        for item in items:
            if item[0] == "text":
                _, y, text, size = item
                add_text(page, 50, y, text, size=size)
            else:
                _, y, rows = item
                draw_ruled_table(page, 50, y, rows)
    data = doc.tobytes()
    doc.close()
    return data


ONE_TABLE_PAGE_1 = [
    [
        ("text", 60, "Maintenance Schedule", 16),
        (
            "table",
            110,
            [
                ["Component", "Interval"],
                ["Lidar Array", "250 h"],
                ["Thermal Enclosure", "1500 h"],
            ],
        ),
    ]
]

TABLE_ON_PAGE_2 = [
    [("text", 60, "Cover", 16)],
    [("text", 60, "Maintenance Schedule", 16), ("table", 110, [["C", "I"], ["Lidar", "250 h"]])],
]


async def _seed_document(db, user, *, name: str):
    doc, _chunks = await create_document_with_chunks(db, user.id, name=name, chunks=[])
    return doc


async def _persist(db, doc, parsed: ParsedDocument):
    return await replace_document_structure(db, doc.id, parsed)


async def _rows(db, doc) -> list[DocumentTableRow]:
    result = await db.execute(
        select(DocumentTableRow)
        .where(DocumentTableRow.document_id == doc.id)
        .order_by(DocumentTableRow.row_index)
    )
    return list(result.scalars().all())


async def _elements(db, doc) -> list[DocumentStructureElement]:
    result = await db.execute(
        select(DocumentStructureElement)
        .where(DocumentStructureElement.document_id == doc.id)
        .order_by(DocumentStructureElement.sequence_index)
    )
    return list(result.scalars().all())


class TestRowPersistence:
    async def test_rows_are_persisted_against_the_aggregate_table_element(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-persist@test.com")
        doc = await _seed_document(db_session, user, name="rows.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc, parsed)
        rows = await _rows(db_session, doc)
        elements = await _elements(db_session, doc)

        table_elements = [e for e in elements if e.element_type == "table"]
        assert len(table_elements) == 1
        assert len(rows) == len(_table_grid(parsed))
        assert len(rows) == 3
        for row in rows:
            assert row.table_element_id == table_elements[0].id
            assert row.document_id == doc.id
            assert row.page_number == 1
            assert row.parser_version == parsed.parser_version
            assert row.heading_path == ["Maintenance Schedule"]
            assert row.section == "Maintenance Schedule"
            assert isinstance(row.token_count, int) and row.token_count > 0

    async def test_cells_are_verbatim_and_header_is_repeated(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-verbatim@test.com")
        doc = await _seed_document(db_session, user, name="verbatim.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc, parsed)
        rows = await _rows(db_session, doc)

        header, first, second = rows
        assert header.is_header is True and header.header_repeated is False
        assert header.cells == ["Component", "Interval"]
        assert header.content == "Component | Interval"

        assert first.is_header is False and first.header_repeated is True
        assert first.cells == ["Lidar Array", "250 h"]
        assert first.content == "Component | Interval\nLidar Array | 250 h"
        assert second.cells == ["Thermal Enclosure", "1500 h"]

        source_cells = {cell for row in _table_grid(parsed) for cell in row}
        for row in rows:
            assert set(row.cells) <= source_cells, "a persisted cell was not extracted"

    async def test_row_order_is_source_order(self, db_session, create_test_user):
        user = await create_test_user(email="rows-order@test.com")
        doc = await _seed_document(db_session, user, name="order.pdf")
        parsed = parse_pdf(_pdf_bytes(TABLE_ON_PAGE_2))

        await _persist(db_session, doc, parsed)
        rows = await _rows(db_session, doc)

        assert [row.row_index for row in rows] == [0, 1]
        # Page provenance comes from the table element itself (page 2 here).
        assert {row.page_number for row in rows} == {2}

    async def test_element_stream_is_unchanged_by_row_evidence(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-elements@test.com")
        doc = await _seed_document(db_session, user, name="elements.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc, parsed)
        elements = await _elements(db_session, doc)

        # One element per parser element, in parser order, with no row/cell
        # elements anywhere in the stream.
        assert len(elements) == len(parsed.elements)
        assert [e.sequence_index for e in elements] == list(range(len(elements)))
        assert [e.element_type for e in elements] == [
            e.element_type for e in parsed.elements
        ]
        assert not [
            e for e in elements if e.element_type in ("table_row", "table_cell")
        ]

    async def test_ingestion_is_idempotent(self, db_session, create_test_user):
        user = await create_test_user(email="rows-idempotent@test.com")
        doc = await _seed_document(db_session, user, name="idempotent.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc, parsed)
        first = await _rows(db_session, doc)
        await _persist(db_session, doc, parsed)
        second = await _rows(db_session, doc)

        assert len(first) == len(second) == 3
        # The (document, table element, row index) uniqueness contract holds.
        assert len(
            {(r.document_id, r.table_element_id, r.row_index) for r in second}
        ) == 3

    async def test_reprocessing_replaces_stale_rows(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-reprocess@test.com")
        doc = await _seed_document(db_session, user, name="reprocess.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc, parsed)
        assert len(await _rows(db_session, doc)) == 3

        # A reprocess that yields fewer, different rows must not leave stale ones.
        table = next(e for e in parsed.elements if e.element_type == "table")
        trimmed = dataclasses.replace(
            table, table_data=[["Component", "Interval"], ["Payload Mast", "2000 h"]]
        )
        reparsed = dataclasses.replace(
            parsed,
            elements=[
                trimmed if e is table else e for e in parsed.elements
            ],
        )

        await _persist(db_session, doc, reparsed)
        rows = await _rows(db_session, doc)

        assert [row.row_index for row in rows] == [0, 1]
        assert rows[1].cells == ["Payload Mast", "2000 h"]
        assert all("Thermal Enclosure" not in row.content for row in rows)

    async def test_deleting_the_document_removes_its_rows(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-cascade@test.com")
        doc = await _seed_document(db_session, user, name="cascade.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))
        await _persist(db_session, doc, parsed)
        assert len(await _rows(db_session, doc)) == 3

        # Bulk delete so the removal is performed by the database, exercising the
        # declared ON DELETE CASCADE rather than an ORM cascade.
        await db_session.execute(sa_delete(Document).where(Document.id == doc.id))
        await db_session.flush()

        remaining = (
            await db_session.execute(
                select(func.count()).select_from(DocumentTableRow)
            )
        ).scalar_one()
        assert remaining == 0, "table row evidence outlived its document"

    async def test_rows_of_one_document_are_isolated_from_another(
        self, db_session, create_test_user
    ):
        owner = await create_test_user(email="rows-owner@test.com")
        other = await create_test_user(email="rows-other@test.com")
        doc_a = await _seed_document(db_session, owner, name="a.pdf")
        doc_b = await _seed_document(db_session, other, name="b.pdf")
        parsed = parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1))

        await _persist(db_session, doc_a, parsed)
        await _persist(db_session, doc_b, parsed)

        rows_a = await _rows(db_session, doc_a)
        rows_b = await _rows(db_session, doc_b)

        assert len(rows_a) == len(rows_b) == 3
        assert {row.document_id for row in rows_a} == {doc_a.id}
        assert {row.document_id for row in rows_b} == {doc_b.id}
        assert {row.table_element_id for row in rows_a}.isdisjoint(
            {row.table_element_id for row in rows_b}
        )


class TestRowsForTablesWithoutCells:
    async def test_table_without_cells_persists_no_rows_but_stays_an_element(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-nocells@test.com")
        doc = await _seed_document(db_session, user, name="nocells.pdf")
        parsed = ParsedDocument(
            parser_version="test-parser",
            source="<test>",
            page_count=1,
            elements=[
                type(parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1)).elements[0])(
                    source_id="table:1:0",
                    element_type="table",
                    page_number=1,
                    sequence_index=0,
                    content="aggregate only",
                    table_data=None,
                )
            ],
        )

        await _persist(db_session, doc, parsed)
        rows = await _rows(db_session, doc)
        elements = await _elements(db_session, doc)

        assert rows == []
        assert [e.element_type for e in elements] == ["table"]

    async def test_blank_rows_persist_nothing(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-blank@test.com")
        doc = await _seed_document(db_session, user, name="blank.pdf")
        table_element = type(parse_pdf(_pdf_bytes(ONE_TABLE_PAGE_1)).elements[0])(
            source_id="table:1:0",
            element_type="table",
            page_number=1,
            sequence_index=0,
            content="   ",
            table_data=[["", " "], ["  ", ""]],
        )
        parsed = ParsedDocument(
            parser_version="test-parser",
            source="<test>",
            page_count=1,
            elements=[table_element],
        )

        await _persist(db_session, doc, parsed)

        assert await _rows(db_session, doc) == []


@pytest.mark.skipif(
    not DEMO_PDF.exists(), reason="teacher-demo PDF is not present in this checkout"
)
class TestTeacherDemoDocument:
    """Real-PDF verification; expectations come from the extractor, not constants."""

    async def test_rows_match_the_extractor_grid(
        self, db_session, create_test_user
    ):
        user = await create_test_user(email="rows-demo@test.com")
        doc = await _seed_document(db_session, user, name="demo.pdf")
        parsed = parse_pdf(DEMO_PDF)

        expected_elements = len(parsed.elements)
        expected_rows = total_row_records(parsed)

        await _persist(db_session, doc, parsed)
        rows = await _rows(db_session, doc)
        elements = await _elements(db_session, doc)

        # Structure element stream unchanged: same count, same order, and the
        # table is still exactly one aggregate element.
        assert len(elements) == expected_elements
        assert [e.sequence_index for e in elements] == list(range(expected_elements))
        table_elements = [e for e in elements if e.element_type == "table"]
        assert len(table_elements) == 1

        # Row count equals the extractor's rows, per table index.
        grid = _table_grid(parsed)
        assert len(grid) == 9
        assert len(rows) == expected_rows == len(grid)
        assert [row.row_index for row in rows] == list(range(len(grid)))

        # The lidar row is persisted verbatim.
        lidar = next(row for row in rows if row.cells[0] == "Lidar Array LR-9")
        assert tuple(lidar.cells) == DEMO_LIDAR_ROW
        assert lidar.row_index == 1
        assert lidar.is_header is False and lidar.header_repeated is True
        assert lidar.page_number == 4
        assert lidar.section == "5. Maintenance Schedule"
        assert lidar.table_element_id == table_elements[0].id
        assert lidar.parser_version == parsed.parser_version

        # Every persisted cell came from the extractor's grid.
        source_cells = {cell for row in grid for cell in row}
        for row in rows:
            assert set(row.cells) <= source_cells


def _row_indices(rows: list[DocumentTableRow]) -> list[int]:
    return [row.row_index for row in rows]


def _table_grid(parsed: ParsedDocument) -> list[list[str]]:
    table = next(e for e in parsed.elements if e.element_type == "table")
    return table.table_data or []


class TestIngestionServiceWiring:
    """The rows must appear through the real ingestion service, not only the persister.

    ``documents.routes._process_document`` is the function every upload runs.  Only
    the embedding model is stubbed (the project's test convention for the model
    boundary); extraction, chunking, structure persistence, row persistence and
    graph construction are all real.
    """

    async def test_process_document_persists_row_evidence(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        from documents import routes as documents_routes

        user = await create_test_user(email="rows-ingest@test.com")
        pdf_path = tmp_path / "ingest.pdf"
        pdf_bytes = _pdf_bytes(ONE_TABLE_PAGE_1)
        pdf_path.write_bytes(pdf_bytes)

        doc = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            name="ingest.pdf",
            file_type="pdf",
            file_size=len(pdf_bytes),
            stored_path=str(pdf_path),
            status="uploaded",
            embedding_status="pending",
            chunk_count=0,
        )
        db_session.add(doc)
        await db_session.flush()

        # Stub only the embedding model (no weights are loaded in tests).
        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        await documents_routes._process_document(doc, pdf_path, "pdf", db_session)
        await db_session.flush()

        assert doc.status == "ready", "ingestion did not complete"
        assert doc.chunk_count > 0

        rows = await _rows(db_session, doc)
        elements = await _elements(db_session, doc)
        parsed = parse_pdf(pdf_bytes)

        assert _row_indices(rows) == [0, 1, 2]
        table_elements = [e for e in elements if e.element_type == "table"]
        assert len(table_elements) == 1
        assert all(row.table_element_id == table_elements[0].id for row in rows)
        assert {(row.page_number, row.section) for row in rows} == {
            (1, "Maintenance Schedule")
        }
        # Element stream still mirrors the parser one-to-one.
        assert len(elements) == len(parsed.elements)
        assert [e.sequence_index for e in elements] == list(range(len(elements)))

