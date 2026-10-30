"""Owner-scoped patch persistence and SQL contracts; no pgvector ranking claim."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from documents.models import DocumentVisualPatch
from embeddings import visual_index
from embeddings.visual import VisualPatch
from tests.fixtures.graph_data import create_document_with_chunks


def patch(identity="clip512:fixture"):
    return VisualPatch(1, "figure1", "figure", [.1, .2, .8, .7], "Figure 1. Exact OCR caption.",
                       [1.0] + [0.0]*511, identity)


@pytest.mark.asyncio
async def test_persist_validates_owner_before_replacing_any_vectors(db_session, create_test_user):
    owner = await create_test_user(email="patch-owner@example.com")
    other = await create_test_user(email="patch-other@example.com")
    doc, _ = await create_document_with_chunks(db_session, owner.id, chunks=[])
    assert await visual_index.persist_visual_patches(db_session, document_id=doc.id, user_id=owner.id, patches=[patch()]) == 1
    with pytest.raises(ValueError, match="unavailable"):
        await visual_index.persist_visual_patches(db_session, document_id=doc.id, user_id=other.id, patches=[])
    rows = (await db_session.execute(select(DocumentVisualPatch).where(DocumentVisualPatch.document_id == doc.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].ocr_text == "Figure 1. Exact OCR caption."
    assert rows[0].bbox == [.1, .2, .8, .7]
    assert len(rows[0].embedding) == 512


@pytest.mark.asyncio
async def test_empty_owner_index_never_allocates_query_encoder(db_session, monkeypatch):
    def forbidden(*_args):
        pytest.fail("An empty owner index must not load CLIP")

    monkeypatch.setattr(visual_index, "encoder_identity", lambda _: "clip512:fixture")
    monkeypatch.setattr(visual_index, "encode_visual_query", forbidden)
    assert await visual_index.retrieve_visual_patches(db_session, "Which diagram?", uuid4(),
        settings=SimpleNamespace(visual_embeddings_enabled=True)) == []


@pytest.mark.asyncio
async def test_retrieval_sql_keeps_owner_model_filter_and_observed_patch_provenance(monkeypatch):
    owner, docid = uuid4(), uuid4()
    identity = "clip512:fixture"
    item = SimpleNamespace(**patch(identity).__dict__, id=uuid4(), document_id=docid)
    statements = []

    class DB:
        async def scalar(self, statement):
            statements.append(statement)
            return item.id

        async def execute(self, statement):
            statements.append(statement)
            return SimpleNamespace(all=lambda: [(item, "diagram.pdf", .15)])

    monkeypatch.setattr(visual_index, "encoder_identity", lambda _: identity)
    monkeypatch.setattr(visual_index, "encode_visual_query", lambda *_: [1.0] + [0.0]*511)
    sources = await visual_index.retrieve_visual_patches(DB(), "Which diagram?", owner,
        document_ids=[docid], top_k=999, settings=SimpleNamespace(visual_embeddings_enabled=True))
    for statement in statements:
        compiled = statement.compile()
        assert "documents.user_id =" in str(compiled)
        assert owner in compiled.params.values()
        assert identity in compiled.params.values()
        assert [docid] in compiled.params.values()
    assert list(statements[-1].compile().params.values())[-1] == 8
    source = sources[0]
    assert source.evidence_kind == "visual_patch" and source.retrieval_path == "visual_spatial"
    assert source.content == item.ocr_text
    assert source.score == pytest.approx(.85)
    assert source.spatial_regions[0]["bbox"] == item.bbox
    assert source.spatial_regions[0]["visual_embedding"] is True
    assert source.spatial_regions[0]["encoder_model"] == identity
