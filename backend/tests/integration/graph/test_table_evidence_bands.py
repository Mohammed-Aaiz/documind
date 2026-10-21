"""Phase 3 wiring: three-band QA context, gate inertness and provenance.

These tests drive the real production path with a real database:

    retrieval_adapter (patched semantic stream, real fusion + real structure
    augmentation + real gated table-row retrieval) → context_adapter (real
    build_qa_context)

The invariant under test is that the compact table-evidence band is **purely
additive**: with the kill switch off, or the gate closed, or the row too large to
fit, the QA context is byte-for-byte the pre-Phase-3 baseline, and the ranked
chunk evidence is never reordered, replaced or re-scored.

Table rows are persisted through the real Phase 2 persister from a real generated
PDF, so the evidence under test is genuine extraction output.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from brain.adapters import context_adapter, qa_adapter, retrieval_adapter
from chat.rag import (
    RRF_K,
    RRF_SEMANTIC_WEIGHT,
    RRF_STRUCTURAL_WEIGHT,
    TABLE_EVIDENCE_ENV,
    _count_text,
)
from documents.parser import parse_pdf
from documents.structure import replace_document_structure
from tests.fixtures.graph_data import create_document_with_chunks
from tests.fixtures.pdf_layout import add_text, draw_ruled_table, new_page, new_pdf

REPO_ROOT = Path(__file__).resolve().parents[3].parent
DEMO_PDF = REPO_ROOT / "Field_Robotics_Deployment_and_Maintenance_Report.pdf"

#: A question that names a table dimension twice ("service interval") and a row.
OPEN_QUESTION = "What service interval does the maintenance schedule give for the gyro unit?"
#: The real regression question.  It shares the term "calibration" with the
#: fixture table's header but never names a header dimension, so it must not
#: activate table evidence.
Q3_QUESTION = (
    "According to Sensor Calibration and Power Management, which power rail "
    "supplies the inertial measurement unit?"
)
#: The real teacher-demo question (used only for the real-PDF test).
Q2_QUESTION = "What calibration interval does the Maintenance Schedule give for the lidar array?"

HEADER = ["Module", "Service Interval", "Operating Range"]
BODY_ROWS = [
    ["Gyro Unit", "250 h", "0-80 m"],
    ["Primary Rail", "1000 h", "19.5-26.0 V"],
    ["Auxiliary Bus", "750 h", "18.0-24.0 V"],
]


def _pdf_bytes(rows: list[list[str]], *, heading: str = "Maintenance Schedule") -> bytes:
    doc = new_pdf()
    page = new_page(doc)
    add_text(page, 50, 60, heading, size=16)
    draw_ruled_table(page, 50, 110, rows)
    data = doc.tobytes()
    doc.close()
    return data


async def _seed_document(
    db, user, *, name: str, question_chunk: str, section: str = "Maintenance Schedule"
):
    """One document with a chunk (the 'retrieved' evidence) and real table rows.

    ``section`` controls whether the structural path can seed this document's chunk
    from the question's terms, which is what makes a document "retrieved".
    """
    doc, chunks = await create_document_with_chunks(
        db,
        user.id,
        name=name,
        chunks=[
            {
                "index": 0,
                "content": question_chunk,
                "page": 1,
                "heading_path": [section],
                "section": section,
            }
        ],
    )
    parsed = parse_pdf(_pdf_bytes([HEADER, *BODY_ROWS]))
    await replace_document_structure(db, doc.id, parsed)
    await db.flush()
    return doc, chunks


def _refs_of_kind(refs, kind: str):
    return [r for r in refs if getattr(r, "evidence_kind", "chunk") == kind]


async def _retrieve(db, user, doc, chunk, question: str):
    """Run the real retrieval adapter with a declared semantic stream."""
    from chat.rag import SourceChunk

    declared = SourceChunk(
        chunk_id=str(chunk.id),
        content=chunk.content,
        score=0.71,
        document_id=str(doc.id),
        document_name=doc.name,
        page=chunk.page,
        retrieval_path="semantic",
    )
    with patch(
        "brain.adapters.retrieve_chunks", new=AsyncMock(return_value=[declared])
    ):
        refs = await retrieval_adapter(
            db=db, user_id=str(user.id), cleaned_text=question, top_k=5
        )
    return refs, declared


def _context_text(pack) -> str:
    return str(pack)


class TestBandInertness:
    async def test_switch_off_adds_no_table_evidence(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        user = await create_test_user(email="bands-off@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="off.pdf", question_chunk="Maintenance schedule notes."
        )

        refs, _declared = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)

        assert _refs_of_kind(refs, "table_row") == []
        # The element tail is still there: only the table band is off.
        assert _refs_of_kind(refs, "structure_element")

    async def test_closed_gate_leaves_the_context_byte_identical(
        self, db_session, create_test_user, monkeypatch
    ):
        """The Q3 regression invariant, asserted directly."""
        user = await create_test_user(email="bands-q3@test.com")
        doc, chunks = await _seed_document(
            db_session,
            user,
            name="q3.pdf",
            question_chunk=(
                "The emergency stop for the primary battery rail is located on "
                "the control mast."
            ),
        )

        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        refs_off, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
        pack_off = await context_adapter(
            retrieval_sources=refs_off, cleaned_text=Q3_QUESTION
        )

        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        refs_on, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
        pack_on = await context_adapter(
            retrieval_sources=refs_on, cleaned_text=Q3_QUESTION
        )

        assert _refs_of_kind(refs_on, "table_row") == []
        assert _context_text(pack_on) == _context_text(pack_off)
        assert pack_on.included_ids == pack_off.included_ids
        assert [r.chunk_id for r in refs_on] == [r.chunk_id for r in refs_off]

    async def test_unmatched_row_keeps_the_context_identical(
        self, db_session, create_test_user, monkeypatch
    ):
        """Gate open but no matching row → still no change to the context."""
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-nomatch@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="nomatch.pdf", question_chunk="General notes."
        )

        question = "What service interval applies to the payload harness?"
        refs_on, _ = await _retrieve(db_session, user, doc, chunks[0], question)
        pack_on = await context_adapter(retrieval_sources=refs_on, cleaned_text=question)

        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        refs_off, _ = await _retrieve(db_session, user, doc, chunks[0], question)
        pack_off = await context_adapter(
            retrieval_sources=refs_off, cleaned_text=question
        )

        assert _refs_of_kind(refs_on, "table_row") == []
        assert _context_text(pack_on) == _context_text(pack_off)


class TestHardRegression:
    async def test_q3_reaches_the_model_with_byte_identical_inputs(
        self, db_session, create_test_user, monkeypatch
    ):
        """The hard Q3 invariant, asserted at the QA-model boundary.

        The model is a deterministic function of exactly two values — the question
        and the context — and production passes exactly those two (see
        ``brain.adapters.qa_adapter``).  If that pair is identical with the feature
        off and on, the answer is identical too, independent of the model's wording
        and of the local model artifacts being present: the call itself is stubbed
        here, while the retrieval and context steps are the real ones.
        """
        user = await create_test_user(email="bands-hard-q3@test.com")
        doc, chunks = await _seed_document(
            db_session,
            user,
            name="hard-q3.pdf",
            question_chunk=(
                "The emergency stop for the primary battery rail is located on "
                "the control mast."
            ),
        )

        calls: list[tuple[str, str]] = []

        def _record(question: str, context: str) -> dict:
            calls.append((question, context))
            return {"answer": "", "score": 0.0, "start": 0, "end": 0}

        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        with patch("brain.adapters.answer_question", new=_record), patch(
            "brain.adapters.is_model_available", return_value=True
        ):
            refs_off, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
            pack_off = await context_adapter(
                retrieval_sources=refs_off, cleaned_text=Q3_QUESTION
            )
            await qa_adapter(cleaned_text=Q3_QUESTION, context=_context_text(pack_off))

            monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
            refs_on, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
            pack_on = await context_adapter(
                retrieval_sources=refs_on, cleaned_text=Q3_QUESTION
            )
            await qa_adapter(cleaned_text=Q3_QUESTION, context=_context_text(pack_on))

        assert _refs_of_kind(refs_on, "table_row") == []
        assert len(calls) == 2, "the QA model must be called exactly once per run"
        assert calls[0] == calls[1], "the QA model's inputs changed for Q3"
        assert calls[0][0] == Q3_QUESTION
        assert calls[0][1] == _context_text(pack_off) == _context_text(pack_on)

        # The power-rail fact survives in the input the model receives: the table
        # path being inert is what keeps the earlier correct answer reachable.
        assert "battery rail" in calls[0][1]


class TestBandActivation:
    async def test_relevant_row_is_added_between_chunks_and_element_tail(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-on@test.com")
        doc, chunks = await _seed_document(
            db_session,
            user,
            name="on.pdf",
            question_chunk="The maintenance schedule records each interval.",
        )

        refs, _declared = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)
        rows = _refs_of_kind(refs, "table_row")
        elements = _refs_of_kind(refs, "structure_element")
        chunk_refs = [r for r in refs if r.evidence_kind == "chunk"]

        assert len(rows) == 1
        row = rows[0]
        assert row.document_id == str(doc.id)
        assert row.document_name == doc.name
        assert row.table_element_id is not None
        assert row.row_index == 1  # header row is 0, so this is the first body row
        assert row.header_repeated is True
        assert row.score == 0.0 and row.fusion_score is None
        assert row.retrieval_path == "structural"
        assert row.page == 1
        assert row.section == "Maintenance Schedule"
        assert row.heading_path == ("Maintenance Schedule",)

        # Provenance is identity, not a re-parse: the row is the persisted one.
        from documents.models import DocumentTableRow
        from sqlalchemy import select

        persisted = (
            await db_session.execute(
                select(DocumentTableRow)
                .where(DocumentTableRow.document_id == doc.id)
                .where(DocumentTableRow.table_element_id == row.table_element_id)
                .where(DocumentTableRow.row_index == row.row_index)
            )
        ).scalars().one()
        assert row.content == persisted.content
        assert row.token_count == persisted.token_count
        assert list(persisted.cells) == ["Gyro Unit", "250 h", "0-80 m"]

        # Band order: ranked chunks, then the row, then the element tail.
        assert [r.chunk_id for r in refs] == [
            *[r.chunk_id for r in chunk_refs],
            *[r.chunk_id for r in rows],
            *[r.chunk_id for r in elements],
        ]

    async def test_ranked_chunks_are_identical_with_the_band_on_and_off(
        self, db_session, create_test_user, monkeypatch
    ):
        user = await create_test_user(email="bands-chunks@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="chunks.pdf", question_chunk="Interval records."
        )

        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        refs_off, _ = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)

        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        refs_on, _ = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)

        band = [
            (
                r.chunk_id,
                r.content,
                r.score,
                r.fusion_score,
                r.retrieval_path,
                r.evidence_kind,
            )
            for r in refs_off
        ]
        assert band == [
            (
                r.chunk_id,
                r.content,
                r.score,
                r.fusion_score,
                r.retrieval_path,
                r.evidence_kind,
            )
            for r in refs_on
            if r.evidence_kind != "table_row"
        ], "the ranked chunks changed when the table band was enabled"

    async def test_rrf_configuration_is_unchanged_and_rows_never_enter_it(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-rrf@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="rrf.pdf", question_chunk="Interval records."
        )

        refs, _ = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)

        assert RRF_K == 60
        assert RRF_SEMANTIC_WEIGHT == 0.70
        assert RRF_STRUCTURAL_WEIGHT == 0.30
        for row in _refs_of_kind(refs, "table_row"):
            assert row.fusion_score is None, "table rows must not receive an RRF score"


class TestBudgetAndOmission:
    async def test_row_that_cannot_fit_is_omitted_and_reported(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-budget@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="budget.pdf", question_chunk="Interval records."
        )

        refs, declared = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)
        rows = _refs_of_kind(refs, "table_row")
        assert rows, "fixture assumption: the row is retrieved"

        # A budget that only admits the ranked chunk: the row cannot fit whole.
        tight_budget = _count_text(declared.content)[0]
        pack = await context_adapter(
            retrieval_sources=refs, cleaned_text=OPEN_QUESTION, budget_tokens=tight_budget
        )

        assert rows[0].chunk_id not in pack.included_ids
        assert rows[0].chunk_id in pack.omitted_ids, "an unfitted row must be reported"
        assert rows[0].content not in _context_text(pack), (
            "an unfitted row must not be truncated into the context"
        )
        assert pack.used_tokens <= pack.budget_tokens

    async def test_row_fits_within_the_existing_budget(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-fits@test.com")
        doc, chunks = await _seed_document(
            db_session, user, name="fits.pdf", question_chunk="Interval records."
        )

        refs, _ = await _retrieve(db_session, user, doc, chunks[0], OPEN_QUESTION)
        pack = await context_adapter(retrieval_sources=refs, cleaned_text=OPEN_QUESTION)
        rows = _refs_of_kind(refs, "table_row")

        assert rows[0].chunk_id in pack.included_ids
        assert pack.used_tokens <= pack.budget_tokens
        assert rows[0].content in _context_text(pack)
        # The row is small: it did not cost the semantic evidence its place.
        assert refs[0].chunk_id in pack.included_ids


class TestIsolation:
    async def test_another_users_rows_are_never_used(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        owner = await create_test_user(email="bands-owner@test.com")
        other = await create_test_user(email="bands-other@test.com")

        owner_doc, owner_chunks = await create_document_with_chunks(
            db_session,
            owner.id,
            name="owner.pdf",
            chunks=[{"index": 0, "content": "Owner notes only.", "page": 1}],
        )
        await _seed_document(
            db_session, other, name="other.pdf", question_chunk="Other notes."
        )
        await db_session.flush()

        refs, _ = await _retrieve(
            db_session, owner, owner_doc, owner_chunks[0], OPEN_QUESTION
        )

        assert _refs_of_kind(refs, "table_row") == []

    async def test_rows_come_only_from_documents_that_were_retrieved(
        self, db_session, create_test_user, monkeypatch
    ):
        """Row evidence is scoped to the documents that supplied chunk evidence, not
        to every document the user owns.  A second document is retrieved too (the
        question names its section), while a third is not — a heading-only element
        match on that third document must not widen the table scope either.
        """
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-two-docs@test.com")
        first_doc, first_chunks = await _seed_document(
            db_session,
            user,
            name="first.pdf",
            question_chunk="The maintenance schedule records each interval.",
        )
        second_doc, _second_chunks = await _seed_document(
            db_session,
            user,
            name="second.pdf",
            question_chunk="The maintenance schedule is repeated here.",
        )
        third_doc, _third_chunks = await _seed_document(
            db_session,
            user,
            name="third.pdf",
            question_chunk="Unrelated appendix notes.",
            section="Appendix Notes",
        )

        refs, _ = await _retrieve(
            db_session, user, first_doc, first_chunks[0], OPEN_QUESTION
        )
        rows = _refs_of_kind(refs, "table_row")
        chunk_documents = {r.document_id for r in refs if r.evidence_kind == "chunk"}
        row_documents = {r.document_id for r in rows}

        assert rows, "fixture assumption: the first document's row is retrieved"
        assert str(first_doc.id) in chunk_documents
        assert str(second_doc.id) in chunk_documents
        assert str(third_doc.id) not in chunk_documents, "fixture assumption drifted"
        assert row_documents <= chunk_documents, (
            "a row was offered for a document with no retrieved chunk"
        )
        assert str(third_doc.id) not in row_documents, (
            "an element-only match widened the table scope"
        )
        assert row_documents == {str(first_doc.id), str(second_doc.id)}


@pytest.mark.skipif(
    not DEMO_PDF.exists(), reason="teacher-demo PDF is not present in this checkout"
)
class TestTeacherDemoQ2:
    async def test_lidar_row_reaches_the_evidence_stream_with_true_provenance(
        self, db_session, create_test_user, monkeypatch
    ):
        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        user = await create_test_user(email="bands-demo@test.com")
        doc, chunks = await create_document_with_chunks(
            db_session,
            user.id,
            name="demo.pdf",
            chunks=[{"index": 0, "content": "Maintenance schedule notes.", "page": 4}],
        )
        await replace_document_structure(db_session, doc.id, parse_pdf(DEMO_PDF))
        await db_session.flush()

        refs, _ = await _retrieve(db_session, user, doc, chunks[0], Q2_QUESTION)
        rows = _refs_of_kind(refs, "table_row")

        assert len(rows) == 1
        row = rows[0]
        assert row.row_index == 1
        assert row.page == 4
        assert row.section == "5. Maintenance Schedule"
        assert row.header_repeated is True
        assert "Lidar Array LR-9" in row.content
        assert "250 h" in row.content
        assert "Calibration Interval" in row.content, "the header must be repeated"
        assert row.content == row.content.strip()
        # Never fabricated: every cell is a verbatim persisted cell.
        for cell in ("Lidar Array LR-9", "250 h", "0-80 m", "> 2.5 mm error"):
            assert cell in row.content

        pack = await context_adapter(retrieval_sources=refs, cleaned_text=Q2_QUESTION)
        assert row.chunk_id in pack.included_ids
        assert row.evidence_kind == "table_row"
        assert row.table_element_id is not None
        # The fact is in the text the QA model is given, not merely in the source
        # list — and the ranked chunk evidence kept its place alongside it.
        assert "250 h" in _context_text(pack)
        assert refs[0].chunk_id in pack.included_ids
        assert pack.used_tokens <= pack.budget_tokens

    async def test_q3_question_remains_inert_on_the_real_document(
        self, db_session, create_test_user, monkeypatch
    ):
        user = await create_test_user(email="bands-demo-q3@test.com")
        doc, chunks = await create_document_with_chunks(
            db_session,
            user.id,
            name="demo-q3.pdf",
            chunks=[
                {
                    "index": 0,
                    "content": (
                        "The emergency stop for the primary battery rail is "
                        "located on the control mast."
                    ),
                    "page": 2,
                }
            ],
        )
        await replace_document_structure(db_session, doc.id, parse_pdf(DEMO_PDF))
        await db_session.flush()

        monkeypatch.delenv(TABLE_EVIDENCE_ENV, raising=False)
        refs_off, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
        pack_off = await context_adapter(
            retrieval_sources=refs_off, cleaned_text=Q3_QUESTION
        )

        monkeypatch.setenv(TABLE_EVIDENCE_ENV, "1")
        refs_on, _ = await _retrieve(db_session, user, doc, chunks[0], Q3_QUESTION)
        pack_on = await context_adapter(
            retrieval_sources=refs_on, cleaned_text=Q3_QUESTION
        )

        assert _refs_of_kind(refs_on, "table_row") == []
        assert _context_text(pack_on) == _context_text(pack_off)
