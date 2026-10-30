"""Phase 1a: per-page completeness accounting and the ``partial`` verdict.

The defect these tests exist for: a **mixed PDF** — some pages carrying a text
layer, some scanned or otherwise unextractable — was ingested and marked
``ready`` while the pages that produced no text were silently dropped.  The
document-level rule was "some element was extracted somewhere", so a document
missing an unknown subset of its pages looked complete.

The rule is now per-page coverage (R5 plan §7.2.1; gate 4 approved by the owner
2026-10-15): a document with at least one usable page and at least one
unaccounted page is ``partial``, never ``ready``; a document with no usable page
at all is ``error``.

Gate 24's page-usability value was approved by the owner on **2026-10-15** as
``MIN_USABLE_CHARS = 4`` (evidence and scope:
``backend/architecture/DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md``),
replacing the previously shipped 32.  Measured, a page of legitimate short text
("Part I" = 5 alphanumeric characters) is accounted for, while a page carrying
only a folio ("17" = 2) is not.

Every test drives the **real** parser on a real generated PDF: real extraction,
real coverage accounting, real chunking/structure/graph persistence where a
database is involved.  Only the embedding model is stubbed — the project's
convention for that boundary (see ``tests/integration/documents/
test_table_row_persistence.py``) — so no test reproduces the expected answer by
hand.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz

from documents.models import Document
from documents.processing import (
    MIN_USABLE_CHARS,
    PageCoverage,
    count_usable_chars,
    extract_document,
)
from documents.ocr import OcrPolicy
from documents.routes import _doc_to_out, _document_verdict
from tests.fixtures.pdf_layout import add_text, new_page, new_pdf

# ---------------------------------------------------------------------------
# Helpers — deterministic, small generated documents
# ---------------------------------------------------------------------------

#: Long enough to clear ``MIN_USABLE_CHARS`` on its own, short enough to stay
#: readable in a diff.
_TEXT_LINE = (
    "DocuMind extracts structured content from documents so every page can be "
    "cited and answered from."
)


def _add_image(page) -> None:
    """Give ``page`` real raster content but **no** text layer.

    This is what a scanned page looks like to the extractor: an image the
    pipeline currently cannot read, contributing zero characters.
    """
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 120))
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(fitz.Rect(50, 50, 200, 200), pixmap=pix)


def _write_pdf(path: Path, pages: list[str]) -> bytes:
    """Write a PDF whose per-page content is ``"text"``, ``"image"`` or ``"blank"``."""
    doc = new_pdf()
    for kind in pages:
        page = new_page(doc)
        if kind == "text":
            add_text(page, 50, 60, _TEXT_LINE, size=11)
        elif kind == "image":
            _add_image(page)
        # "blank": an untouched page — no text layer, no image.
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


def _document(user, path: Path, data: bytes, file_type: str = "pdf") -> Document:
    """Build the ``Document`` row the pipeline needs, without touching the API."""
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


# ---------------------------------------------------------------------------
# 1. The measure and the threshold
# ---------------------------------------------------------------------------


class TestUsableCharsMeasure:
    def test_counts_only_non_whitespace_alphanumeric_characters(self):
        """Punctuation, whitespace and control characters are not usable text.

        A page carrying only a rule, dashes or stray whitespace has produced no
        content and must not be able to make a document ready.
        """
        assert count_usable_chars("abc") == 3
        assert count_usable_chars(" -- 7 -- ") == 1
        assert count_usable_chars("...") == 0
        assert count_usable_chars("\n\t   ") == 0
        assert count_usable_chars("") == 0

    def test_threshold_is_the_owners_gate_24_decision(self):
        """``MIN_USABLE_CHARS`` is pinned: changing it changes verdicts.

        Owner decision (gate 24, 2026-10-15): the value is **4** and its home is
        ``backend/documents/processing.py`` as a module constant, with no
        configuration surface.  The value sits inside the measured gap between
        the largest content-free text-bearing page (2) and the shortest
        legitimate sparse page (5); see ``TestSparsePagesAreAccountedFor``.
        """
        assert MIN_USABLE_CHARS == 4


# ---------------------------------------------------------------------------
# 2. Coverage facts and the verdict function (no database, no model)
# ---------------------------------------------------------------------------


class TestPageCoverageFacts:
    def test_complete_only_when_every_page_is_usable(self):
        assert PageCoverage(pages_total=2, pages_usable=2, unusable_pages=()).complete is True
        assert PageCoverage(pages_total=2, pages_usable=1, unusable_pages=(2,)).complete is False
        assert PageCoverage(pages_total=2, pages_usable=0, unusable_pages=(1, 2)).complete is False

    def test_no_usable_pages_flag(self):
        assert PageCoverage(2, 0, (1, 2)).no_usable_pages is True
        assert PageCoverage(2, 1, (2,)).no_usable_pages is False
        assert PageCoverage(2, 2, ()).no_usable_pages is False


class TestVerdictFunction:
    def test_no_page_denominator_is_ready(self):
        """DOCX/TXT have no pages, so coverage is ``None`` and steps decide."""
        assert _document_verdict(None) == ("ready", None)

    def test_every_page_usable_is_ready(self):
        assert _document_verdict(PageCoverage(2, 2, ())) == ("ready", None)

    def test_some_pages_unaccounted_is_partial(self):
        """The mixed-document case: usable content AND known unread pages."""
        assert _document_verdict(PageCoverage(3, 2, (3,))) == ("partial", None)

    def test_no_usable_page_is_error_never_partial(self):
        """Zero usable pages is ``error``, and the reason names the truth.

        A coverage object with no OCR attempt — OCR configured off, or no page
        handed to it — reports "no text layer, OCR disabled", never
        ``ocr_failed_all_pages``, which would claim an attempt that was never
        made.  The OCR-attempted case is covered in ``test_ocr_scanned_pdf.py``
        and ``test_ocr_fallback.py``.
        """
        status, reason = _document_verdict(PageCoverage(2, 0, (1, 2)))
        assert status == "error"
        assert status != "partial"
        assert reason == "no_text_layer_ocr_disabled"


# ---------------------------------------------------------------------------
# 3. Real extraction: what the generated PDFs actually yield
# ---------------------------------------------------------------------------


class TestExtractionCoverage:
    def test_digital_pdf_accounts_for_every_page(self, tmp_path):
        """Regression: a fully text-based PDF is still complete."""
        path = tmp_path / "digital.pdf"
        _write_pdf(path, ["text", "text"])

        elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (2, 2)
        assert coverage.unusable_pages == ()
        assert coverage.complete is True
        assert elements, "a page with a text layer must still produce elements"
        assert {element.page for element in elements} == {1, 2}

    def test_mixed_pdf_reports_the_scanned_page_as_unaccounted(self, tmp_path):
        """The defect case: page 2 has content but no text, and is *reported*."""
        path = tmp_path / "mixed.pdf"
        _write_pdf(path, ["text", "image"])

        elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (2, 1)
        assert coverage.unusable_pages == (2,)
        assert coverage.complete is False
        # Page 1 contributed elements; page 2 contributed none, and the
        # accounting is the only thing that records its absence.
        assert {element.page for element in elements} == {1}

    def test_text_plus_empty_page_is_unaccounted(self, tmp_path):
        """An untouched page has no text layer either, and is unaccounted."""
        path = tmp_path / "text-and-blank.pdf"
        _write_pdf(path, ["text", "blank"])

        _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (2, 1)
        assert coverage.unusable_pages == (2,)

    def test_image_only_document_has_no_usable_page(self, tmp_path):
        """Scanned-only: every page unaccounted, and not a single element."""
        path = tmp_path / "scanned.pdf"
        _write_pdf(path, ["image", "image"])

        elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (2, 0)
        assert coverage.unusable_pages == (1, 2)
        assert coverage.no_usable_pages is True
        assert elements == [], "an image-only page must not fabricate text"

    def test_txt_has_no_page_denominator(self, tmp_path):
        """A format without pages reports ``None`` rather than a made-up count."""
        path = tmp_path / "notes.txt"
        path.write_text("DocuMind retrieval notes: citations carry a page and a chunk id.\n")

        elements, coverage = extract_document(path, "txt")

        assert coverage is None
        assert elements, "the text itself must still be extracted"


# ---------------------------------------------------------------------------
# 4. The whole pipeline: the status a user would actually observe
# ---------------------------------------------------------------------------


class TestPipelineVerdict:
    """``_process_document`` is the function every upload and reprocess runs.

    Only ``embed_texts`` is stubbed; extraction, coverage accounting, chunking,
    structure persistence and graph construction are the real implementations.
    """

    async def test_mixed_pdf_is_partial_and_never_ready(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """**The defect.** This document used to be reported as ``ready``."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-mixed@test.com")
        path = tmp_path / "mixed.pdf"
        data = _write_pdf(path, ["text", "image"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status != "ready", "an incomplete document must never be ready"
        assert doc.status == "partial"
        # The extracted page is genuinely searchable, and that is why the
        # document is not an error.
        assert doc.embedding_status == "ready"
        assert doc.chunk_count > 0
        assert reason is None, "partial is a coverage verdict, not an error reason"

    async def test_digital_pdf_is_ready(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """Regression: existing digital documents keep their behaviour."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-digital@test.com")
        path = tmp_path / "digital.pdf"
        data = _write_pdf(path, ["text", "text"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "ready"
        assert doc.embedding_status == "ready"
        assert doc.chunk_count > 0
        assert reason is None

    async def test_image_only_pdf_is_error_with_the_honest_reason(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """Scanned-only: error with a reason, no chunks, no false success."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-scanned@test.com")
        path = tmp_path / "scanned.pdf"
        data = _write_pdf(path, ["image", "image"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "error"
        assert doc.status != "partial", "zero usable pages is not partial"
        assert doc.embedding_status == "error"
        assert doc.chunk_count == 0
        assert reason == "no_text_layer_ocr_disabled"

    async def test_empty_txt_is_error(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """A format without pages still cannot be ready with nothing extracted."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-empty-txt@test.com")
        path = tmp_path / "empty.txt"
        path.write_bytes(b"")
        doc = _document(user, path, b"", file_type="txt")
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "txt", db_session
        )
        await db_session.flush()

        assert doc.status == "error"
        assert doc.embedding_status == "error"
        assert doc.chunk_count == 0
        # No page-coverage reason applies to a format that has no pages, so no
        # reason is claimed.
        assert reason is None

    async def test_raised_extraction_is_a_pipeline_exception(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """An exception is an exception fact: ``error``/``pipeline_exception``.

        Coverage and exceptions are never merged: a raised step produces an
        error whatever the coverage would have been.
        """
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-raised@test.com")
        path = tmp_path / "digital.pdf"
        data = _write_pdf(path, ["text", "text"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        def _explode(*_args, **_kwargs):
            raise RuntimeError("extraction exploded")

        monkeypatch.setattr(documents_routes, "extract_document", _explode)

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "error"
        assert reason == "pipeline_exception"


# ---------------------------------------------------------------------------
# 5. Serialization: the new value reaches the API unchanged
# ---------------------------------------------------------------------------


class TestStatusSerialization:
    def test_partial_status_is_serialized_as_is(self):
        """``status`` is typed ``str``, so the new value needs no schema change."""
        doc = Document(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="mixed.pdf",
            file_type="pdf",
            file_size=1024,
            stored_path="/tmp/mixed.pdf",
            status="partial",
            embedding_status="ready",
            chunk_count=4,
        )

        out = _doc_to_out(doc)

        assert out.status == "partial"
        assert out.embeddingStatus == "ready"
        assert out.chunkCount == 4


# ---------------------------------------------------------------------------
# 6. Rotated pages (R5 plan §15.2 row 4) — Phase 1a's remaining acceptance case
# ---------------------------------------------------------------------------


def _write_rotated_pdf(path: Path, pages: list[str], rotation: int) -> bytes:
    """Write a PDF whose pages all carry ``rotation`` degrees (0/90/180/270).

    Rotation is a layout property and must not decide coverage: a rotated page
    that *has* a text layer is still usable, and a rotated page that has none is
    still unaccounted.  This is the §15.2 requirement for Phase 1a ("a rotated
    page that yields no text is an unaccounted page").
    """
    doc = new_pdf()
    for kind in pages:
        page = new_page(doc)
        page.set_rotation(rotation)
        if kind == "text":
            add_text(page, 50, 60, _TEXT_LINE, size=11)
        elif kind == "image":
            _add_image(page)
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


class TestRotatedPages:
    def test_rotated_page_with_text_is_usable(self, tmp_path):
        """Rotation alone never turns an accounted-for page into a missing one."""
        for rotation in (0, 90, 180, 270):
            path = tmp_path / f"rotated-{rotation}.pdf"
            _write_rotated_pdf(path, ["text"], rotation)
            elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())
            assert coverage is not None
            assert coverage.pages_total == 1
            assert coverage.pages_usable == 1, f"rotation {rotation} lost usable text"
            assert coverage.unusable_pages == ()
            assert elements, "the rotated page's text must still be extracted"
            assert _document_verdict(coverage) == ("ready", None)

    def test_rotated_page_without_text_is_unaccounted(self, tmp_path):
        """A rotated, scan-only page yields no text and is counted as missing."""
        for rotation in (90, 180, 270):
            path = tmp_path / f"rotated-scan-{rotation}.pdf"
            _write_rotated_pdf(path, ["text", "image"], rotation)
            _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())
            assert coverage is not None
            assert (coverage.pages_usable, coverage.pages_total) == (1, 2)
            assert coverage.unusable_pages == (2,)
            assert _document_verdict(coverage) == ("partial", None)

            only_scan = tmp_path / f"rotated-scan-only-{rotation}.pdf"
            _write_rotated_pdf(only_scan, ["image"], rotation)
            _elements2, coverage2 = extract_document(only_scan, "pdf", ocr_policy=OcrPolicy.disabled())
            assert coverage2 is not None
            assert coverage2.no_usable_pages
            assert _document_verdict(coverage2) == (
                "error",
                "no_text_layer_ocr_disabled",
            )


# ---------------------------------------------------------------------------
# 7. Sparse pages — the approved gate-24 value (4, 2026-10-15)
# ---------------------------------------------------------------------------


#: Pages whose *entire* content is a legitimate short title or heading.  Every
#: one of these carries real, extracted text and must count as accounted for.
_SPARSE_TEXTS = (
    "Part I",
    "Figure 1",
    "Chapter 1",
    "Appendix A",
    "References",
    "Introduction",
    "Bibliography",
    "Lecture 3: Attention",
)

#: Text-bearing pages that carry no content at all: a bare folio or page number.
_FOLIO_TEXTS = ("17", "iv")


def _write_texts_pdf(path: Path, lines: list[str]) -> bytes:
    """Write a PDF with one real line of text per page (sparse-page fixtures)."""
    doc = new_pdf()
    for line in lines:
        page = new_page(doc)
        add_text(page, 50, 60, line, size=11)
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return data


class TestSparsePagesAreAccountedFor:
    """Decision A: shortness alone never makes a page's content "missing"."""

    def test_legitimate_short_pages_are_usable(self, tmp_path):
        """A page carrying only a chapter title or heading is accounted for."""
        for index, text in enumerate(_SPARSE_TEXTS):
            path = tmp_path / f"sparse-{index}.pdf"
            _write_texts_pdf(path, [text])

            elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

            assert coverage is not None
            assert (coverage.pages_total, coverage.pages_usable) == (1, 1), text
            assert coverage.unusable_pages == ()
            assert coverage.complete is True
            assert _document_verdict(coverage) == ("ready", None), text
            assert elements, f"the page text {text!r} must still be extracted"

    def test_bare_folio_page_is_not_usable(self, tmp_path):
        """A page carrying only a folio produced text but no content."""
        for index, text in enumerate(_FOLIO_TEXTS):
            path = tmp_path / f"folio-{index}.pdf"
            _write_texts_pdf(path, [text])

            _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

            assert coverage is not None
            assert (coverage.pages_total, coverage.pages_usable) == (1, 0), text
            assert coverage.unusable_pages == (1,)
            assert _document_verdict(coverage) == (
                "error",
                "no_text_layer_ocr_disabled",
            )

    def test_short_title_page_plus_substantive_page_is_ready(self, tmp_path):
        """A mixed substantive/sparse document is complete, not ``partial``."""
        path = tmp_path / "title-and-body.pdf"
        _write_texts_pdf(path, ["Chapter 1", _TEXT_LINE])

        elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (2, 2)
        assert _document_verdict(coverage) == ("ready", None)
        assert {element.page for element in elements} == {1, 2}

    def test_all_sparse_text_bearing_document_is_ready(self, tmp_path):
        """Every page legitimately short: still ``ready``, never an error.

        This is the case the previously shipped value turned into a false
        extraction failure even though every page's text was extracted.
        """
        path = tmp_path / "all-sparse.pdf"
        _write_texts_pdf(path, ["Part I", "Chapter 1", "References"])

        elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert (coverage.pages_total, coverage.pages_usable) == (3, 3)
        assert _document_verdict(coverage) == ("ready", None)
        assert {element.page for element in elements} == {1, 2, 3}

    def test_punctuation_and_whitespace_only_pages_are_unaccounted(self, tmp_path):
        """Content-free text still cannot make a document usable."""
        for index, text in enumerate((". . . -- .", "     ")):
            path = tmp_path / f"no-content-{index}.pdf"
            _write_texts_pdf(path, [text])

            _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

            assert coverage is not None
            assert (coverage.pages_total, coverage.pages_usable) == (1, 0), text
            assert _document_verdict(coverage) == (
                "error",
                "no_text_layer_ocr_disabled",
            )

    def test_blank_only_document_is_error(self, tmp_path):
        """Blank pages have no text layer, so zero usable pages is ``error``."""
        path = tmp_path / "blank-only.pdf"
        _write_pdf(path, ["blank", "blank"])

        _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())

        assert coverage is not None
        assert coverage.no_usable_pages is True
        assert _document_verdict(coverage) == (
            "error",
            "no_text_layer_ocr_disabled",
        )


class TestSparseDocumentPipeline:
    """The statuses a user observes for sparse documents (real pipeline)."""

    async def test_all_sparse_document_is_ready_with_indexed_content(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """Legitimate sparse text is indexed instead of being discarded."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-sparse-ready@test.com")
        path = tmp_path / "sparse.pdf"
        data = _write_texts_pdf(path, ["Part I", "Chapter 1"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "ready"
        assert doc.embedding_status == "ready"
        assert doc.chunk_count > 0, "extracted sparse text must be chunked"
        assert reason is None

    async def test_substantive_and_sparse_pages_are_ready(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-sparse-mixed@test.com")
        path = tmp_path / "mixed-sparse.pdf"
        data = _write_texts_pdf(path, [_TEXT_LINE, "References"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "ready"
        assert doc.chunk_count > 0
        assert reason is None

    async def test_folio_only_document_is_error_with_no_chunks(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """A folio is text without content, so no page is usable."""
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-folio@test.com")
        path = tmp_path / "folio-only.pdf"
        data = _write_texts_pdf(path, ["17", "iv"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "error"
        assert doc.embedding_status == "error"
        assert doc.chunk_count == 0
        assert reason == "no_text_layer_ocr_disabled"

    async def test_mixed_digital_and_scanned_document_stays_partial(
        self, db_session, create_test_user, tmp_path, monkeypatch
    ):
        """With OCR configured off, a scanned page is still unaccounted.

        These coverage tests disable OCR on purpose (``OcrPolicy.disabled()``)
        so they measure the accounting rule alone.  The OCR path has its own
        tests; this file must not start depending on an engine being
        provisioned.
        """
        from documents import routes as documents_routes

        user = await create_test_user(email="phase1a-sparse-scan@test.com")
        path = tmp_path / "digital-and-scan.pdf"
        data = _write_pdf(path, ["text", "image"])
        doc = _document(user, path, data)
        db_session.add(doc)
        await db_session.flush()

        monkeypatch.setattr(
            documents_routes, "embed_texts", lambda texts: [None] * len(texts)
        )

        reason = await documents_routes._process_document(
            doc, path, "pdf", db_session, ocr_policy=OcrPolicy.disabled()
        )
        await db_session.flush()

        assert doc.status == "partial"
        assert doc.chunk_count > 0, "the digital page is still searchable"
        assert reason is None
