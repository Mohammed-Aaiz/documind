"""Visual-spatial provenance policy on synthetic page geometry; no VLM inference."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
import fitz
from PIL import Image

from documents.spatial import MAX_REGIONS, native_page_layout, normalized_bbox, order_regions, page_layout


def region(identifier, bbox, *, kind="text", text="Source text"):
    return {"id": identifier, "bbox": bbox, "kind": kind, "text": text}


def test_bbox_is_normalized_clamped_and_axis_ordered():
    assert normalized_bbox([20, 40, 80, 160], 100, 200) == [0.2, 0.2, 0.8, 0.8]
    assert normalized_bbox([110, 220, -10, -20], 100, 200) == [0, 0, 1, 1]


@pytest.mark.parametrize("bbox,width,height", [([0, 0, 10, 10], 0, 10), ([0, 0, 10, 10], 10, -1), ([0, 0, 10], 10, 10)])
def test_invalid_geometry_is_rejected(bbox, width, height):
    with pytest.raises(ValueError):
        normalized_bbox(bbox, width, height)


def test_two_columns_read_down_left_then_down_right_between_spanning_headings():
    inputs = [
        region("right-2", [.55, .36, .95, .46]),
        region("heading", [.05, .02, .95, .1]),
        region("left-2", [.05, .35, .45, .45]),
        region("right-1", [.55, .16, .95, .26]),
        region("footer", [.05, .8, .95, .9]),
        region("left-1", [.05, .15, .45, .25]),
    ]
    original = deepcopy(inputs)
    ordered = order_regions(inputs)
    assert [item["id"] for item in ordered] == ["heading", "left-1", "left-2", "right-1", "right-2", "footer"]
    assert [item["reading_order"] for item in ordered] == list(range(6))
    assert [item["column"] for item in ordered] == [None, 0, 0, 1, 1, None]
    assert inputs == original, "Adding layout metadata must not mutate extractor-owned regions"


def test_ambiguous_single_column_geometry_keeps_vertical_order():
    inputs = [region("bottom", [.05, .5, .9, .6]), region("top", [.05, .1, .9, .2])]
    ordered = order_regions(inputs)
    assert [item["id"] for item in ordered] == ["top", "bottom"]
    assert all(item["column"] is None for item in ordered)


def test_rotated_ocr_orders_by_corrected_boxes_without_changing_source_geometry():
    heading = region("heading", [.1, .8, .9, .9])
    body = region("body", [.1, .1, .9, .2])
    heading["reading_bbox"] = [.1, .1, .9, .2]
    body["reading_bbox"] = [.1, .8, .9, .9]
    ordered = order_regions([body, heading])
    assert [item["id"] for item in ordered] == ["heading", "body"]
    assert ordered[0]["bbox"] == [.1, .8, .9, .9]


def test_caption_links_only_to_nearby_overlapping_visual_and_does_not_invent_vision_embeddings():
    layout = page_layout(100, 200, [
        region("table", [.05, .1, .45, .4], kind="table", text="Sensor | Interval"),
        region("caption", [.05, .42, .45, .46], text="Table 1. Sensor maintenance"),
        region("far-caption", [.55, .42, .95, .46], text="Figure 2. Separate illustration"),
    ], method="native-pdf-geometry")
    by_id = {item["id"]: item for item in layout["regions"]}
    assert by_id["caption"]["caption_for"] == "table"
    assert "caption_for" not in by_id["far-caption"]
    assert layout["coordinates"] == "normalized-top-left"
    assert layout["visual_embeddings"] is False


def test_native_extraction_preserves_table_cells_once_and_image_bounds():
    page = SimpleNamespace(rect=SimpleNamespace(width=100, height=200))
    page_dict = {"blocks": [
        {"type": 0, "bbox": [10, 20, 40, 40], "lines": [{"spans": [{"text": "Duplicated cell text"}]}]},
        {"type": 0, "bbox": [10, 100, 90, 120], "lines": [{"spans": [{"text": "Figure 1. Calibration rig"}]}]},
        {"type": 1, "bbox": [10, 55, 90, 95]},
    ]}
    cells = [["Sensor", "Interval"], ["Lidar", "30 days"]]
    layout = native_page_layout(page, page_dict, [([5, 15, 45, 45], cells)])
    regions = layout["regions"]
    assert not any(item.get("text") == "Duplicated cell text" for item in regions)
    table = next(item for item in regions if item["kind"] == "table")
    assert table["cells"] == cells
    assert table["bbox"] == [.05, .075, .45, .225]
    figure = next(item for item in regions if item["kind"] == "figure")
    assert figure["bbox"] == [.1, .275, .9, .475]
    caption = next(item for item in regions if item.get("text") == "Figure 1. Calibration rig")
    assert caption["caption_for"] == figure["id"]


def test_region_count_is_bounded_and_truncation_is_explicit():
    regions = [region(f"r-{index}", [0, 0, 1, 1]) for index in range(MAX_REGIONS + 1)]
    layout = page_layout(100, 200, regions, method="ocr-boxes")
    assert len(layout["regions"]) == MAX_REGIONS
    assert layout["truncated"] is True


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotated_native_pdf_boxes_register_with_actual_rendered_text(rotation):
    with fitz.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((72, 100), "Heading near top of native page.")
        page.insert_text((72, 720), "Bottom calibration reference text.")
        original = {block["lines"][0]["spans"][0]["text"]: block["bbox"]
                    for block in page.get_text("dict")["blocks"]}
        page.set_rotation(rotation)
        layout = native_page_layout(page, page.get_text("dict"), [])
        assert layout["page_rotation"] == rotation
        assert layout["reading_coordinates"] == "unrotated-native-normalized"
        assert [item["text"] for item in layout["regions"]] == list(original)
        pix = page.get_pixmap(alpha=False, colorspace=fitz.csRGB)
        with Image.frombytes("RGB", (pix.width, pix.height), pix.samples) as image:
            for item in layout["regions"]:
                source_box = original[item["text"]]
                transformed = fitz.Rect(source_box) * page.rotation_matrix
                expected = normalized_bbox(list(transformed), page.rect.width, page.rect.height)
                assert item["bbox"] == pytest.approx(expected)
                assert item["reading_bbox"] == pytest.approx(normalized_bbox(source_box, 600, 800))
                x0, y0, x1, y1 = item["bbox"]
                assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
                crop = image.crop((int(x0*pix.width), int(y0*pix.height),
                                   int(x1*pix.width)+1, int(y1*pix.height)+1))
                with crop.convert("L") as grayscale:
                    assert grayscale.getextrema()[0] < 200, "The cited crop must contain rendered text ink"
                crop.close()
