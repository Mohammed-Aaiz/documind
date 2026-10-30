"""Owner-scoped spatial context from persisted, observed page regions.

Image/OCR/layout analysis runs at ingestion. A question only reads a bounded
number of page records reached by semantic/graph retrieval. Coordinates encode
page geometry; these are not ColPali embeddings or inferred chart values.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import replace
from typing import Sequence

from sqlalchemy import and_, or_, select

from documents.models import Document, DocumentPageExtraction
from generation.verification import content_tokens

_SPATIAL = re.compile(r"\b(?:above|below|left|right|beside|column|columns|layout|chart|charts|figure|diagram|table|tables|caption)\b", re.I)


def is_spatial_query(question: str) -> bool:
    return bool(_SPATIAL.search(question))


def select_spatial_regions(layout: dict, question: str, content: str = "", *, limit: int = 4) -> list[dict]:
    """Rank real regions; keep normalized coordinates and exact extracted text."""
    terms = set(content_tokens(question))
    candidates = []
    for index, region in enumerate((layout.get("regions") or [])[:2000]):
        if not isinstance(region, dict):
            continue
        box = region.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            coords = [float(value) for value in box]
        except (TypeError, ValueError):
            continue
        if not all(0 <= value <= 1 for value in coords) or coords[0] > coords[2] or coords[1] > coords[3]:
            continue
        text = str(region.get("text") or "")
        kind = str(region.get("kind") or "text")
        overlap = len(terms & set(content_tokens(text)))
        contained = bool(text.strip()) and text.strip() in content
        visual_kind = kind in ("figure", "table", "caption") and bool(_SPATIAL.search(question))
        if not overlap and not contained and not visual_kind:
            continue
        candidates.append((-(3 * overlap + int(contained) + int(visual_kind)), index,
                           {"id": str(region.get("id", index)), "kind": kind, "bbox": coords,
                            "text": text[:240], "reading_order": region.get("reading_order", index),
                            "column": region.get("column"), "caption_for": region.get("caption_for")}))
    candidates.sort(key=lambda item: item[:2])
    selected = [item[2] for item in candidates[: max(1, min(limit, 6))]]
    # Retain a figure's actual caption association, not a caption invented from
    # proximity at query time. Ingestion alone decides and records the link.
    return sorted(selected, key=lambda item: (item.get("reading_order") or 0, item["id"]))


async def enrich_spatial_sources(db, user_id: str, question: str, chunks: Sequence) -> tuple[list, str]:
    pairs = []
    for chunk in chunks:
        try:
            pair = (uuid.UUID(str(chunk.document_id)), int(chunk.page))
        except (ValueError, TypeError, AttributeError):
            continue
        if pair not in pairs:
            pairs.append(pair)
        if len(pairs) >= 6:
            break
    if not pairs:
        return list(chunks), "not_recorded"
    owner = uuid.UUID(str(user_id))
    result = await db.execute(select(DocumentPageExtraction).join(
        Document, Document.id == DocumentPageExtraction.document_id
    ).where(Document.user_id == owner, or_(*[
        and_(DocumentPageExtraction.document_id == document_id,
             DocumentPageExtraction.page_number == page) for document_id, page in pairs
    ])).limit(6))
    layouts = {(str(row.document_id), row.page_number): row.spatial_layout
               for row in result.scalars().all() if isinstance(row.spatial_layout, dict)}
    enriched = []
    for chunk in chunks:
        if getattr(chunk, "evidence_kind", "") == "visual_patch":
            # The retrieved crop already carries the exact region used to
            # compute its image vector. Never replace it with a nearby box.
            enriched.append(chunk)
            continue
        layout = layouts.get((str(chunk.document_id), chunk.page))
        regions = select_spatial_regions(layout, question, chunk.content) if layout else []
        content = chunk.content
        if regions and _SPATIAL.search(question):
            # This serializes measured geometry and observed OCR/native text.
            # Keeping it in the same cited source lets the reader inspect the
            # evidence behind an above/below/column answer.
            context = json.dumps(regions, ensure_ascii=False, separators=(",", ":"))
            content = "Observed page layout (normalized top-left coordinates): " + context + "\n" + content
        enriched.append(replace(chunk, content=content, spatial_regions=regions or None))
    return enriched, "available" if layouts else "not_recorded"
