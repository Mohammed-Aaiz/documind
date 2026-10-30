"""Per-page extraction provenance, recorded by the real pipeline.

What these tests protect
------------------------
A document's *verdict* is document-level (READY / PARTIAL / ERROR).  The rows in
``document_page_extractions`` are the per-page evidence behind it: which page was
read, whether its text came from a native text layer or the OCR fallback, with
which engine and at what confidence — and, for a page nobody could read, why.
These tests drive the real extraction and the real persistence step, then read
the rows back, so the stored values are produced by the code rather than asserted
against themselves.

Fixtures are real PDFs: digital pages carry a text layer, scanned pages are
rasterised images of the same text (no font file needed), and an unreadable page
is an image with no text on it at all.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz
import pytest
from sqlalchemy import select

from documents.models import Document, DocumentPageExtraction
from documents.ocr import OcrPolicy, ocr_available
from documents.routes import _process_document
from tests.fixtures.pdf_layout import add_text, new_page, new_pdf

HEADING = "DocuMind maintenance manual"
BODY = "The lidar calibration interval is 6 months."


def _digital_pdf(path: Path, pages: int = 2) -> bytes:
    doc = new_pdf()
    for index in range(pages):
        page = new_page(doc)
        add_text(page, 50, 90, HEADING, size=13)
        add_text(page, 50, 120, f"{BODY} (page {index + 1})", size=11)
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _raster(lines: list[str], *, dpi: int = 300) -> bytes:
    source = fitz.open()
    page = source.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((50, y), line, fontsize=13, fontname="helv")
        y += 36
    png = page.get_pixmap(dpi=dpi).tobytes("png")
    source.close()
    return png


def _scanned_pdf(path: Path, lines: list[str]) -> bytes:
    """Image-only page: the text above, rasterised, with no text layer left."""
    doc = new_pdf()
    page = new_page(doc)
    page.insert_image(page.rect, stream=_raster(lines))
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _unreadable_pdf(path: Path) -> bytes:
    """An image-only page whose image carries no text at all."""
    doc = new_pdf()
    page = new_page(doc)
    grey = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200))
    grey.set_rect(grey.irect, (190, 190, 190))
    page.insert_image(fitz.Rect(50, 50, 400, 400), pixmap=grey)
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _document(user, path: Path, data: bytes, file_type: str = "pdf") -> Document:
    return Document(
        id=uuid.uuid4(),
        user_id=user.id,
        name=path.name,
        file_type=file_type,
        file_size=len(data),
        stored_path=str(path),
        status="uploaded",
        embedding_status="pending",
        chunk_count=0,
    )


async def _rows(db_session, document_id) -> list[DocumentPageExtraction]:
    return list(
        (
            await db_session.execute(
                select(DocumentPageExtraction)
                .where(DocumentPageExtraction.document_id == document_id)
                .order_by(DocumentPageExtraction.page_number.asc())
            )
        )
        .scalars()
        .all()
    )


@pytest.fixture
def stub_embeddings(monkeypatch):
    """Embedding is not what these tests measure (and needs no model)."""
    from documents import routes as documents_routes

    monkeypatch.setattr(
        documents_routes, "embed_texts", lambda texts: [None] * len(texts)
    )


# ---------------------------------------------------------------------------
# A page with a text layer
# ---------------------------------------------------------------------------


class TestNativePages:
    async def test_every_page_is_recorded_as_native(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """A digital PDF records one row per page, with no OCR fields invented."""
        user = await create_test_user(email="pages-native@test.com")
        path = tmp_path / "digital.pdf"
        data = _digital_pdf(path)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        await _process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        rows = await _rows(db_session, doc.id)
        assert [row.page_number for row in rows] == [1, 2]
        assert [row.method for row in rows] == ["native", "native"]
        assert all(row.text_chars > 0 for row in rows)
        # Nothing about OCR is recorded for a page that never needed it.
        assert all(row.ocr_engine is None for row in rows)
        assert all(row.ocr_confidence is None for row in rows)
        assert all(row.ocr_rotation is None for row in rows)
        assert all(row.failure_reason is None for row in rows)


# ---------------------------------------------------------------------------
# A page only OCR can read
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not ocr_available(), reason="OCR engine is not provisioned")
class TestOcrPages:
    async def test_the_engine_and_confidence_are_recorded(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """The row says who read the page and how confident that reading was."""
        user = await create_test_user(email="pages-ocr@test.com")
        path = tmp_path / "scanned.pdf"
        data = _scanned_pdf(path, [HEADING, BODY])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        await _process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        rows = await _rows(db_session, doc.id)
        assert len(rows) == 1
        row = rows[0]
        assert row.page_number == 1
        assert row.method == "ocr"
        assert row.ocr_engine == "rapidocr"
        assert row.ocr_engine_version, "the engine version must be recorded"
        assert row.ocr_confidence is not None
        assert 0.0 < row.ocr_confidence <= 1.0
        assert row.ocr_rotation in (0, 90, 180, 270)
        assert row.ocr_seconds is not None and row.ocr_seconds > 0
        assert row.text_chars > 0
        assert row.failure_reason is None, "a page OCR read is not a failure"


# ---------------------------------------------------------------------------
# A page nobody can read
# ---------------------------------------------------------------------------


class TestUnreadablePages:
    async def test_an_unreadable_scan_records_the_failure_reason(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """A page with no text and no OCR result records *why*, not just 'none'."""
        user = await create_test_user(email="pages-unreadable@test.com")
        path = tmp_path / "unreadable.pdf"
        data = _unreadable_pdf(path)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        await _process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        rows = await _rows(db_session, doc.id)
        assert len(rows) == 1
        assert rows[0].method == "none"
        assert rows[0].text_chars == 0
        assert rows[0].failure_reason in {
            "ocr_failed",
            "ocr_unavailable",
            "no_text_layer",
        }

    async def test_ocr_disabled_records_the_disabled_reason(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """With OCR off, the row distinguishes 'off' from 'tried and failed'."""
        user = await create_test_user(email="pages-ocr-off@test.com")
        path = tmp_path / "scanned-off.pdf"
        data = _scanned_pdf(path, [HEADING, BODY])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        await _process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        rows = await _rows(db_session, doc.id)
        assert [row.method for row in rows] == ["none"]
        assert rows[0].failure_reason == "ocr_disabled"

    async def test_an_error_document_still_records_its_pages(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """Rows are written before the verdict, so ERROR keeps its evidence.

        The document-level reason stays transient, but a document nobody could
        read must still say which pages were empty and why — otherwise the
        failure is unexplainable after the fact.
        """
        user = await create_test_user(email="pages-error@test.com")
        path = tmp_path / "no-pages-readable.pdf"
        data = _scanned_pdf(path, [" "])  # a blank scan: nothing to read
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        reason = await _process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "error"
        assert reason == "no_text_layer_ocr_disabled"
        rows = await _rows(db_session, doc.id)
        assert len(rows) == 1
        assert rows[0].method == "none"
        assert rows[0].failure_reason == "ocr_disabled"


# ---------------------------------------------------------------------------
# Replacement, not accumulation
# ---------------------------------------------------------------------------


class TestReplacement:
    async def test_reprocessing_never_duplicates_page_rows(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """The unique constraint is not enough — the replace must be explicit."""
        user = await create_test_user(email="pages-reprocess@test.com")
        path = tmp_path / "digital-twice.pdf"
        data = _digital_pdf(path, pages=2)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        await _process_document(doc, path, "pdf", db_session)
        await db_session.flush()
        first = await _rows(db_session, doc.id)

        await _process_document(doc, path, "pdf", db_session)
        await db_session.flush()
        second = await _rows(db_session, doc.id)

        assert [row.page_number for row in second] == [1, 2]
        assert len(second) == len(first), "a second run must replace, not append"
        # A replacement is a fresh set of rows for the same pages.
        assert {row.id for row in first}.isdisjoint({row.id for row in second})


# ---------------------------------------------------------------------------
# Formats without pages
# ---------------------------------------------------------------------------


class TestFormatsWithoutPages:
    async def test_a_txt_document_records_no_page_rows(
        self, db_session, create_test_user, tmp_path, stub_embeddings
    ):
        """No pages means no page rows — the API then reports 'not recorded'."""
        user = await create_test_user(email="pages-txt@test.com")
        path = tmp_path / "notes.txt"
        path.write_text("DocuMind retrieval notes: citations carry a page.\n")
        doc = _document(user, path, b"notes", file_type="txt")
        db_session.add(doc)
        await db_session.flush()

        await _process_document(doc, path, "txt", db_session)
        await db_session.flush()

        assert await _rows(db_session, doc.id) == []
