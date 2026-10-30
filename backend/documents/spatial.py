"""Bounded page geometry for visual-spatial retrieval, computed at ingestion.

Coordinates come from PDF objects or OCR detections, never a language model.
This is layout-aware text extraction, not a learned ColPali/vision embedding.
Digital pages avoid raster/OCR cost; scanned pages reuse the OCR image pass.
"""
from __future__ import annotations

import re
import math
import fitz
from typing import Any, Sequence

VERSION = "page-layout-v1"
MAX_REGIONS = 1500
MAX_LAYOUT_TEXT_CHARS = 120_000
MAX_TABLE_CELLS = 1000


def native_page_size(page: Any) -> tuple[float, float]:
    """Text coordinates use the unrotated crop frame, unlike page.rect."""
    width, height = float(page.rect.width), float(page.rect.height)
    return (height, width) if int(getattr(page, "rotation", 0)) % 180 else (width, height)


def display_bbox(page: Any, bbox: Sequence[float]) -> tuple[float, float, float, float]:
    """Map native text/table geometry to the rendered page's coordinate frame."""
    if int(getattr(page, "rotation", 0)):
        return tuple(fitz.Rect(bbox) * page.rotation_matrix)
    return tuple(bbox)


def normalized_bbox(bbox: Sequence[float], width: float, height: float) -> list[float]:
    if width <= 0 or height <= 0 or not math.isfinite(width) or not math.isfinite(height) or len(bbox) != 4:
        raise ValueError("A page region requires positive page dimensions and four coordinates")
    x0, y0, x1, y1 = [float(value) for value in bbox]
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        raise ValueError("Page region coordinates must be finite")
    return [round(max(0.0, min(1.0, value)), 6) for value in
            (min(x0, x1) / width, min(y0, y1) / height,
             max(x0, x1) / width, max(y0, y1) / height)]


def order_regions(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order clear two-column bands left-to-right, preserving full-width breaks.

    A conservative gutter requires multiple regions on both sides. A heading
    or table crossing the gutter divides bands, so the right column cannot
    jump above the heading governing it. Ambiguous pages retain y/x order.
    """
    regions = [dict(region) for region in regions]
    # OCR source boxes map back to the original page for crop provenance.
    # Reading order must instead use the orientation-corrected OCR frame;
    # sorting source y on an upside-down scan reverses every line again.
    def reading_box(region):
        return region.get("reading_bbox", region["bbox"])
    left = [r for r in regions if reading_box(r)[2] <= .52]
    right = [r for r in regions if reading_box(r)[0] >= .48]
    two_columns = len(left) >= 2 and len(right) >= 2 and (
        max(reading_box(r)[2] for r in left) <= min(reading_box(r)[0] for r in right)
    )
    left_ids, right_ids = {r["id"] for r in left}, {r["id"] for r in right}
    for region in regions:
        region["column"] = (0 if region["id"] in left_ids else 1 if region["id"] in right_ids else None) if two_columns else None
    ordered = sorted(regions, key=lambda r: (reading_box(r)[1], reading_box(r)[0], r["id"]))
    if two_columns:
        output, band = [], []
        for region in ordered:
            if region["column"] is None:
                output.extend(sorted(band, key=lambda r: (r["column"], reading_box(r)[1], reading_box(r)[0])))
                band = []
                output.append(region)
            else:
                band.append(region)
        output.extend(sorted(band, key=lambda r: (r["column"], reading_box(r)[1], reading_box(r)[0])))
        ordered = output
    for position, region in enumerate(ordered):
        region["reading_order"] = position
    return ordered


def page_layout(width: float, height: float, regions: list[dict[str, Any]], *, method: str) -> dict:
    regions = order_regions(regions[:MAX_REGIONS])
    # Captions remain their exact extracted text. A nearby figure/table link is
    # geometric provenance only; it does not claim the diagram was understood.
    visual = [r for r in regions if r["kind"] in {"figure", "table"}]
    for region in regions:
        if region["kind"] != "text" or not re.match(r"^(?:fig(?:ure)?\.?|table|chart)\s*\d", region.get("text", ""), re.I):
            continue
        x0, y0, x1, y1 = region.get("reading_bbox", region["bbox"])
        near = []
        for target in visual:
            tx0, ty0, tx1, ty1 = target.get("reading_bbox", target["bbox"])
            gap = min(abs(y0 - ty1), abs(ty0 - y1))
            if min(x1, tx1) > max(x0, tx0) and gap <= .08:
                near.append((gap, target["id"]))
        if near:
            region["caption_for"] = min(near)[1]
    return {"version": VERSION, "width": float(width), "height": float(height),
            "coordinates": "normalized-top-left", "method": method,
            "regions": regions, "truncated": len(regions) >= MAX_REGIONS,
            "visual_embeddings": False}


def native_text_blocks(page_dict: dict, width: float):
    """Split PDF blocks that incorrectly merge row-aligned separate columns.

    PyMuPDF may put left and right column lines in one text block. Preserve
    ordinary paragraphs intact, splitting only when line boxes show a gutter.
    Both the persisted layout and emitted elements use these identical IDs.
    """
    for index, block in enumerate(page_dict.get("blocks", [])[:MAX_REGIONS]):
        lines = block.get("lines", [])
        left = [line for line in lines if line.get("bbox") and line["bbox"][2] <= width * .52]
        right = [line for line in lines if line.get("bbox") and line["bbox"][0] >= width * .48]
        split = left and right and max(line["bbox"][2] for line in left) < min(line["bbox"][0] for line in right)
        if block.get("type") != 1 and split:
            for line_index, line in enumerate(lines):
                yield f"block-{index}-line-{line_index}", {
                    **block, "bbox": line.get("bbox") or block.get("bbox"), "lines": [line],
                }
        else:
            yield f"block-{index}", block


def native_page_layout(page: Any, page_dict: dict, tables: Sequence[tuple]) -> dict:
    width, height = float(page.rect.width), float(page.rect.height)
    source_width, source_height = native_page_size(page)
    regions = []
    text_left, cells_left = MAX_LAYOUT_TEXT_CHARS, MAX_TABLE_CELLS
    for region_id, block in native_text_blocks(page_dict, source_width):
        if len(regions) >= MAX_REGIONS:
            break
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        text = "\n".join(" ".join(str(s.get("text", "")) for s in line.get("spans", []))
                         for line in block.get("lines", [])).strip()
        kind = "figure" if block.get("type") == 1 else "text"
        if kind == "text" and not text:
            continue
        # Native text inside an extracted table is represented once as cells.
        if kind == "text" and any(_inside(bbox, tb) for tb, _ in tables):
            continue
        excerpt = text[:min(8000, text_left)]
        text_left -= len(excerpt)
        regions.append({"id": region_id, "kind": kind,
                        "bbox": normalized_bbox(display_bbox(page, bbox), width, height),
                        "reading_bbox": normalized_bbox(bbox, source_width, source_height), "text": excerpt,
                        "text_truncated": len(excerpt) < len(text)})
    for index, (bbox, cells) in enumerate(tables):
        bounded_cells = []
        for row in cells[:200]:
            bounded_row = [str(cell)[:256] for cell in row[:min(100, cells_left)]]
            cells_left -= len(bounded_row)
            bounded_cells.append(bounded_row)
            if cells_left <= 0:
                break
        table_text = "\n".join(" | ".join(row) for row in bounded_cells)
        excerpt = table_text[:min(8000, text_left)]
        text_left -= len(excerpt)
        regions.append({"id": f"table-{index}", "kind": "table",
                        "bbox": normalized_bbox(display_bbox(page, bbox), width, height),
                        "reading_bbox": normalized_bbox(bbox, source_width, source_height),
                        "text": excerpt, "cells": bounded_cells,
                        "text_truncated": len(excerpt) < len(table_text),
                        "cells_truncated": len(bounded_cells) < len(cells) or any(
                            len(new) < len(old) or any(len(str(cell)) > 256 for cell in old)
                            for new, old in zip(bounded_cells, cells))})
    layout = page_layout(width, height, regions, method="native-pdf-geometry")
    layout["reading_coordinates"] = "unrotated-native-normalized"
    layout["page_rotation"] = int(getattr(page, "rotation", 0))
    return layout


def _inside(bbox: Sequence[float], table: Sequence[float]) -> bool:
    x0, y0, x1, y1 = bbox
    tx0, ty0, tx1, ty1 = table
    area = max(0, x1 - x0) * max(0, y1 - y0)
    intersection = max(0, min(x1, tx1) - max(x0, tx0)) * max(0, min(y1, ty1) - max(y0, ty0))
    return bool(area and intersection / area > .5)
