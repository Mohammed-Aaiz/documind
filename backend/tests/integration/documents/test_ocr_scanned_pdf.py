"""OCR on real scans, through the real extractor and the real pipeline.

Every fixture here is a genuine image-only PDF: text is drawn on a page, the
page is **rasterised** and rebuilt as an image, so the second document has no
text layer at all — the same situation as a photographed or photocopied page.
No font files are needed (the raster is produced by PyMuPDF from its built-in
Helvetica), so the fixtures are identical on every machine.

These tests need the provisioned OCR engine.  When it is absent they skip
rather than pretend: an unprovisioned machine has not measured anything.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz
import pytest
from sqlalchemy import select

from documents.models import Document, DocumentChunk
from documents.ocr import OcrPolicy, ocr_available
from documents.processing import extract_document
from documents.routes import _document_verdict
from tests.fixtures.pdf_layout import add_text, new_page, new_pdf

pytestmark = pytest.mark.skipif(
    not ocr_available(), reason="OCR engine (rapidocr) is not provisioned"
)

HEADING = "DocuMind maintenance manual"
BODY = "The lidar calibration interval is 6 months."
EXTRA = "Warranty claims must be filed within 30 days of the failure."


def _scanned_pdf(path: Path, lines: list[str], *, rotation: int = 0, dpi: int = 300) -> bytes:
    """Write an image-only PDF whose single page shows ``lines`` upright on screen.

    The page rotation is applied **before** rasterising, so the resulting image
    really contains upside-down (or sideways) pixels; the page itself carries no
    rotation flag to give the extractor a shortcut.
    """
    source = fitz.open()
    page = source.new_page(width=595, height=842)
    if rotation:
        page.set_rotation(rotation)
    y = 90.0
    for line in lines:
        page.insert_text((50, y), line, fontsize=13, fontname="helv")
        y += 36
    pixmap = page.get_pixmap(dpi=dpi)
    png = pixmap.tobytes("png")
    source.close()

    target = fitz.open()
    scan_page = target.new_page(width=595, height=842)
    scan_page.insert_image(scan_page.rect, stream=png)
    data = target.tobytes()
    target.close()
    path.write_bytes(data)
    return data


def _raster(lines: list[str], *, dpi: int = 300) -> bytes:
    """PNG bytes showing ``lines`` — text drawn once, then rasterised."""
    source = fitz.open()
    page = source.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((50, y), line, fontsize=13, fontname="helv")
        y += 36
    png = page.get_pixmap(dpi=dpi).tobytes("png")
    source.close()
    return png


def _grey_scan() -> "fitz.Pixmap":
    """A real image with no text in it at all: a page OCR cannot read."""
    grey = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 200))
    grey.set_rect(grey.irect, (190, 190, 190))
    return grey


def _digital_page_pdf(path: Path, *, extra_scan: bool = False) -> bytes:
    """A PDF with a real text layer on page 1 (and optionally a grey scan on page 2)."""
    doc = new_pdf()
    page = new_page(doc)
    add_text(page, 50, 90, HEADING, size=13)
    if extra_scan:
        scan_page = new_page(doc)
        scan_page.insert_image(fitz.Rect(50, 50, 300, 300), pixmap=_grey_scan())
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _digital_plus_scan_pdf(path: Path) -> bytes:
    """Page 1 has a real text layer; page 2 is a scan of readable text."""
    doc = new_pdf()
    page = new_page(doc)
    add_text(page, 50, 90, HEADING, size=13)
    scan_page = new_page(doc)
    scan_page.insert_image(scan_page.rect, stream=_raster([BODY, EXTRA]))
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _unreadable_scan_pdf(path: Path) -> bytes:
    """An image-only document whose image carries no text: OCR cannot help."""
    doc = new_pdf()
    page = new_page(doc)
    page.insert_image(fitz.Rect(50, 50, 400, 400), pixmap=_grey_scan())
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _document(user, path: Path, data: bytes) -> Document:
    return Document(
        id=uuid.uuid4(),
        user_id=user.id,
        name=path.name,
        file_type="pdf",
        file_size=len(data),
        stored_path=str(path),
        status="uploaded",
        embedding_status="pending",
        chunk_count=0,
    )


# ---------------------------------------------------------------------------
# Extraction: what a real scan yields
# ---------------------------------------------------------------------------


class TestScannedExtraction:
    def test_a_scanned_page_is_read_and_accounted_for(self, tmp_path):
        """The page nobody could read now produces text, and coverage says so."""
        path = tmp_path / "scan.pdf"
        _scanned_pdf(path, [HEADING, BODY, EXTRA])

        elements, coverage = extract_document(path, "pdf")

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (1, 1)
        assert coverage.ocr_pages == (1,)
        assert coverage.ocr_attempted is True
        assert coverage.ocr_unavailable is False
        assert coverage.ocr_engine == "rapidocr"
        assert coverage.unusable_pages == ()
        assert _document_verdict(coverage) == ("ready", None)

        text = "\n".join(element.content for element in elements)
        assert BODY in text
        assert EXTRA in text
        assert elements[0].page == 1

    def test_an_upside_down_scan_is_read_after_rotation(self, tmp_path):
        """Measured failure mode: 180 degrees used to garble most of the page."""
        path = tmp_path / "scan-180.pdf"
        _scanned_pdf(path, [HEADING, BODY, EXTRA], rotation=180)

        elements, coverage = extract_document(path, "pdf")

        assert coverage is not None and coverage.pages_usable == 1
        text = "\n".join(element.content for element in elements)
        assert BODY in text
        assert EXTRA in text
        assert text.strip().startswith(HEADING), (
            "reading order must survive the rotation correction"
        )

    def test_a_digital_page_never_reaches_the_ocr_engine(self, tmp_path):
        """OCR must not cost anything for documents that already have text."""
        path = tmp_path / "digital.pdf"
        _digital_page_pdf(path)

        elements, coverage = extract_document(path, "pdf")

        assert coverage is not None
        assert coverage.ocr_attempted is False
        assert coverage.ocr_pages == ()
        assert coverage.ocr_engine is None
        assert elements and elements[0].content.startswith(HEADING)

    def test_ocr_can_be_disabled_and_the_page_is_then_unaccounted(self, tmp_path):
        """``OCR_ENGINE=off`` is a real configuration, and it reports honestly."""
        path = tmp_path / "scan-off.pdf"
        _scanned_pdf(path, [HEADING, BODY])

        elements, coverage = extract_document(
            path, "pdf", ocr_policy=OcrPolicy.disabled()
        )

        assert coverage is not None
        assert coverage.ocr_attempted is False
        assert coverage.no_usable_pages is True
        assert elements == []
        assert _document_verdict(coverage) == ("error", "no_text_layer_ocr_disabled")


# ---------------------------------------------------------------------------
# The pipeline: the status and the content a user actually gets
# ---------------------------------------------------------------------------


class TestScannedIngestion:
    async def test_scanned_pdf_ingests_ready_with_ocr_text_in_its_chunks(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """The thing that matters: OCR text is chunked, not just counted."""
        from documents import routes as documents_routes

        user = await create_test_user(email="ocr-scanned@test.com")
        path = tmp_path / "scanned.pdf"
        data = _scanned_pdf(path, [HEADING, BODY, EXTRA])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session
        )
        await db_session.flush()

        assert doc.status == "ready"
        assert doc.status != "partial"
        assert doc.chunk_count > 0
        assert reason is None

        rows = (
            await db_session.execute(
                select(DocumentChunk.content).where(
                    DocumentChunk.document_id == doc.id
                )
            )
        ).scalars().all()
        chunked = " ".join(rows)
        assert BODY in chunked, "the recognised text must reach the chunk graph"
        assert EXTRA in chunked

    async def test_mixed_document_is_ready_when_both_pages_can_be_read(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """A digital page plus a scanned page: complete, not ``partial``."""
        from documents import routes as documents_routes

        user = await create_test_user(email="ocr-mixed@test.com")
        path = tmp_path / "digital-and-scan.pdf"
        data = _digital_plus_scan_pdf(path)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        assert doc.status == "ready"
        assert doc.chunk_count > 0
        assert reason is None

    async def test_an_unreadable_page_keeps_the_document_partial(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """OCR ran on page 2 and found nothing: ``partial``, never a false ready."""
        from documents import routes as documents_routes

        user = await create_test_user(email="ocr-partial@test.com")
        path = tmp_path / "digital-and-blank.pdf"
        data = _digital_page_pdf(path, extra_scan=True)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        assert doc.status == "partial"
        assert doc.embedding_status == "ready"
        assert doc.chunk_count > 0, "the readable page is still searchable"
        assert reason is None

    async def test_a_scan_ocr_cannot_read_is_error_with_the_ocr_reason(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """When OCR is attempted and reads nothing, the reason says exactly that."""
        from documents import routes as documents_routes

        user = await create_test_user(email="ocr-unreadable@test.com")
        path = tmp_path / "unreadable.pdf"
        data = _unreadable_scan_pdf(path)
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(doc, path, "pdf", db_session)
        await db_session.flush()

        assert doc.status == "error"
        assert doc.chunk_count == 0
        assert reason == "ocr_failed_all_pages", (
            "OCR ran and found nothing — that is not the same as OCR being off"
        )
