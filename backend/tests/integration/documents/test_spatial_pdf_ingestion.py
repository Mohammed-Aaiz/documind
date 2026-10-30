"""Real PDF geometry extraction and JSON persistence on synthetic page fixtures.

No embedding model, visual model or hosted LLM is involved. SQLite exercises
the persistence contract; it does not establish PostgreSQL migration validity.
"""
from __future__ import annotations

import fitz
import pytest
from sqlalchemy import select

from documents.models import DocumentPageExtraction
from documents.ocr import OcrPolicy
from documents.page_extractions import replace_document_page_extractions
from documents.processing import extract_document
from tests.fixtures.graph_data import create_document_with_chunks


def two_column_pdf(path):
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=800)
    # Insertion is deliberately row-interleaved. Correct column reading order
    # must come from the extracted geometry rather than PDF object order.
    page.insert_text((40, 150), "Left first: calibration reference rig.", fontsize=11)
    page.insert_text((350, 150), "Right first: documented maintenance.", fontsize=11)
    page.insert_text((40, 350), "Left second: sensor alignment procedure.", fontsize=11)
    page.insert_text((350, 350), "Right second: safe power delivery.", fontsize=11)
    pdf.save(path)
    pdf.close()


def test_real_pdf_columns_preserve_reading_order_and_source_coordinates(tmp_path):
    path = tmp_path / "two-columns.pdf"
    two_column_pdf(path)
    elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())
    assert coverage.pages_total == coverage.pages_usable == 1
    layout = coverage.pages[0].spatial_layout
    assert layout["method"] == "native-pdf-geometry"
    assert layout["visual_embeddings"] is False
    assert [region["text"].split(":")[0] for region in layout["regions"]] == [
        "Left first", "Left second", "Right first", "Right second",
    ]
    assert [element.content.split(":")[0] for element in elements] == [
        "Left first", "Left second", "Right first", "Right second",
    ]
    assert all(0 <= coordinate <= 1 for region in layout["regions"] for coordinate in region["bbox"])
    assert all(element.page == 1 and element.bbox_x0 is not None for element in elements)
    assert elements[0].bbox_x0 < elements[2].bbox_x0


@pytest.mark.asyncio
async def test_real_page_geometry_survives_page_provenance_persistence(db_session, create_test_user, tmp_path):
    path = tmp_path / "persisted-two-columns.pdf"
    two_column_pdf(path)
    _elements, coverage = extract_document(path, "pdf", ocr_policy=OcrPolicy.disabled())
    user = await create_test_user(email="spatial-pdf@example.com")
    document, _chunks = await create_document_with_chunks(
        db_session, user.id, name="persisted-two-columns.pdf", chunks=[{"content": "Calibration reference rig."}],
    )
    count = await replace_document_page_extractions(db_session, document.id, coverage.pages)
    await db_session.flush()
    row = (await db_session.execute(select(DocumentPageExtraction).where(
        DocumentPageExtraction.document_id == document.id,
    ))).scalar_one()
    assert count == 1 and row.page_number == 1 and row.method == "native"
    assert row.spatial_layout == coverage.pages[0].spatial_layout
    assert row.spatial_layout["regions"][0]["text"].startswith("Left first:")
