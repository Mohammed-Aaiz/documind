"""Measured spatial source context is bounded and remains owner-scoped."""
from __future__ import annotations

import pytest

from chat.rag import SourceChunk
from documents.models import DocumentPageExtraction
from generation.spatial_retrieval import enrich_spatial_sources, select_spatial_regions
from tests.fixtures.graph_data import create_document_with_chunks


def layout(text="Figure 1. Calibration reference rig"):
    return {"coordinates": "normalized-top-left", "visual_embeddings": False, "regions": [
        {"id": "figure", "kind": "figure", "bbox": [.1, .1, .9, .5], "text": "", "reading_order": 0},
        {"id": "caption", "kind": "text", "bbox": [.1, .52, .9, .57], "text": text, "reading_order": 1, "caption_for": "figure"},
    ]}


def test_region_selection_keeps_measured_boxes_and_caption_link():
    regions = select_spatial_regions(layout(), "Which caption is below the figure?")
    assert [item["id"] for item in regions] == ["figure", "caption"]
    assert regions[0]["bbox"] == [.1, .1, .9, .5]
    assert regions[1]["caption_for"] == "figure"
    assert regions[1]["text"] == "Figure 1. Calibration reference rig"


def test_invalid_boxes_are_dropped_and_selection_is_capped():
    data = layout()
    data["regions"].extend([
        {"id": "outside", "kind": "figure", "bbox": [-1, 0, 1, 1], "text": "figure"},
        {"id": "reversed", "kind": "figure", "bbox": [.8, 0, .2, 1], "text": "figure"},
        {"id": "nonnumeric", "kind": "figure", "bbox": ["x", 0, 1, 1], "text": "figure"},
    ])
    selected = select_spatial_regions(data, "Explain the figure", limit=999)
    assert {item["id"] for item in selected} == {"figure", "caption"}
    assert len(selected) <= 6


@pytest.mark.asyncio
async def test_spatial_enrichment_never_fetches_another_owners_page_geometry(db_session, create_test_user):
    owner = await create_test_user(email="spatial-owner@example.com")
    other = await create_test_user(email="spatial-other@example.com")
    own_doc, own_chunks = await create_document_with_chunks(db_session, owner.id, name="own.pdf", chunks=[{"content": "Calibration rig.", "page": 1}])
    foreign_doc, foreign_chunks = await create_document_with_chunks(db_session, other.id, name="private.pdf", chunks=[{"content": "Other document.", "page": 1}])
    db_session.add_all([
        DocumentPageExtraction(document_id=own_doc.id, page_number=1, method="native", spatial_layout=layout()),
        DocumentPageExtraction(document_id=foreign_doc.id, page_number=1, method="native", spatial_layout=layout("Figure 1. PRIVATE OWNER CAPTION")),
    ])
    await db_session.flush()
    chunks = [
        SourceChunk(str(own_chunks[0].id), "Calibration rig.", .8, str(own_doc.id), "own.pdf", 1),
        SourceChunk(str(foreign_chunks[0].id), "Other document.", .8, str(foreign_doc.id), "private.pdf", 1),
    ]
    enriched, status = await enrich_spatial_sources(db_session, str(owner.id), "Which caption is below the figure?", chunks)
    assert status == "available"
    assert enriched[0].spatial_regions and "Observed page layout" in enriched[0].content
    assert enriched[1].spatial_regions is None
    assert enriched[1].content == "Other document."
    assert "PRIVATE OWNER CAPTION" not in str(enriched)


@pytest.mark.asyncio
async def test_learned_crop_geometry_is_not_replaced_by_nearby_layout_regions(db_session, create_test_user):
    owner = await create_test_user(email="patch-geometry@example.com")
    document, _ = await create_document_with_chunks(db_session, owner.id, chunks=[])
    db_session.add(DocumentPageExtraction(document_id=document.id, page_number=1,
        method="native", spatial_layout=layout("Different neighbouring caption")))
    await db_session.flush()
    original = [{"id": "actual-crop", "bbox": [.2, .3, .6, .7], "visual_embedding": True,
                 "encoder_model": "clip512:fixture", "text": "Exact crop caption"}]
    source = SourceChunk("visual:patch1", "Exact crop caption", .8, str(document.id), "figure.pdf", 1,
        evidence_kind="visual_patch", retrieval_path="visual_spatial", spatial_regions=original)
    enriched, _ = await enrich_spatial_sources(db_session, str(owner.id), "Which figure is below?", [source])
    assert enriched[0].spatial_regions == original
    assert enriched[0].content == "Exact crop caption"
