"""Bounded optional pixel indexing, reusing observed page layout and OCR.

This stage never extracts text again and runs in the ingestion worker thread.
Missing local CLIP assets are a recorded capability state, not fake vectors.
"""
from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path

import fitz

from documents.processing import PageExtraction
from embeddings.visual import VisualModelUnavailable, encode_page_regions, visual_model_status

logger = logging.getLogger(__name__)


def index_visual_document(path: Path, pages: tuple[PageExtraction, ...], settings):
    """Return updated page facts and actual learned patches; do no DB work.

    A fixed page cap, encoder crop/pixel caps and batch size bound CPU/memory.
    Only page rasterization is repeated: existing native/OCR text is reused.
    """
    state = visual_model_status(settings)
    page_limit = max(1, min(32, int(getattr(settings, "visual_max_pages_per_document", 12))))
    patches, updated = [], []
    document = None
    try:
        if state["available"]:
            document = fitz.open(str(path))
        for index, page in enumerate(pages):
            if not page.spatial_layout:
                updated.append(page)
                continue
            layout = {**page.spatial_layout, "visual_embeddings": False,
                      "visual_embedding_status": state["status"], "visual_patch_count": 0}
            if document is not None:
                if index >= page_limit:
                    layout["visual_embedding_status"] = "page_budget_exhausted"
                else:
                    try:
                        encoded = encode_page_regions(document[page.page_number - 1], layout["regions"], settings)
                        patches.extend(encoded)
                        layout.update(visual_embeddings=bool(encoded), visual_patch_count=len(encoded),
                                      visual_embedding_status="indexed" if encoded else "no_regions")
                    except VisualModelUnavailable:
                        # Stop trying remaining pages if local inference cannot
                        # run. Already successful crops remain truthful facts.
                        state = {"available": False, "status": "encoder_unavailable"}
                        layout["visual_embedding_status"] = "encoder_unavailable"
                        document.close()
                        document = None
                        logger.warning("Local visual encoder unavailable; continuing text/graph ingestion")
            updated.append(replace(page, spatial_layout=layout))
        return tuple(updated), patches
    finally:
        if document is not None:
            document.close()
