"""Persist per-page extraction provenance into ``document_page_extractions``.

One row per page, replaced on every processing run.  The rows answer a question
the document verdict cannot: *which* pages were read, how each page's text was
obtained, and — for a page read by OCR — with what engine and confidence.

Why this is not part of the verdict
-----------------------------------
The verdict (READY / PARTIAL / ERROR) is a document-level fact and stays that
way.  These rows are the per-page evidence behind it, stored so the insights
endpoint and the UI can show it.  Nothing here can change a status.

Atomicity
---------
The replace runs inside a ``SAVEPOINT`` (``db.begin_nested()``), the same
discipline ``documents/structure.py`` uses: the document's previous page rows are
deleted and the new ones inserted as one unit.  A reprocessing run therefore
cannot leave a document with page rows from two different extractions.

Honesty rules
-------------
* Rows are written only for pages the run actually observed.  A document
  processed before this table existed has **no** rows, and the API reports
  ``recorded: false`` rather than inventing page counts.
* ``method`` and ``failure_reason`` come from the extraction itself
  (:class:`documents.processing.PageExtraction`); nothing is inferred here.
"""

from __future__ import annotations

import logging
import uuid
from typing import Sequence

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import DocumentPageExtraction
from documents.processing import PageExtraction

logger = logging.getLogger(__name__)


async def replace_document_page_extractions(
    db: AsyncSession,
    document_id: uuid.UUID,
    pages: Sequence[PageExtraction],
) -> int:
    """Replace this document's page rows with ``pages``; return how many.

    A document with no pages (DOCX/TXT) simply ends with no rows — and any stale
    rows from a previous run are removed, so the table never contradicts the
    format that is currently indexed.
    """
    async with db.begin_nested():
        await db.execute(
            delete(DocumentPageExtraction).where(
                DocumentPageExtraction.document_id == document_id
            )
        )
        for page in pages:
            db.add(
                DocumentPageExtraction(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    page_number=page.page_number,
                    method=page.method,
                    text_chars=page.text_chars,
                    ocr_engine=page.ocr_engine,
                    ocr_engine_version=page.ocr_engine_version,
                    ocr_confidence=page.ocr_confidence,
                    ocr_rotation=page.ocr_rotation,
                    ocr_seconds=page.ocr_seconds,
                    failure_reason=page.failure_reason,
                    spatial_layout=page.spatial_layout,
                )
            )

    if pages:
        logger.info(
            "document %s: %s page extraction row(s) recorded (%s by OCR)",
            document_id,
            len(pages),
            sum(1 for page in pages if page.method == "ocr"),
        )
    return len(pages)
