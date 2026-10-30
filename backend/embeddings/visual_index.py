"""Owner-scoped persistence and image/text-aligned pgvector patch retrieval."""
from __future__ import annotations

import math
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from embeddings.visual import VisualPatch, encode_visual_query, encoder_identity


async def persist_visual_patches(
    db: AsyncSession, *, document_id: UUID, user_id: UUID,
    patches: list[VisualPatch], replace_existing: bool = True,
) -> int:
    """Caller owns the transaction; validate ownership before any mutation."""
    from documents.models import Document, DocumentVisualPatch
    owner = await db.scalar(select(Document.id).where(
        Document.id == document_id, Document.user_id == user_id))
    if owner is None:
        raise ValueError("Document is unavailable for visual indexing")
    seen = set()
    for patch in patches:
        key = (patch.page_number, patch.region_id)
        if key in seen:
            raise ValueError("Duplicate visual region identifier")
        seen.add(key)
        if (patch.page_number < 1 or not patch.region_id or len(patch.region_id) > 64
                or len(patch.embedding) != 512
                or not all(math.isfinite(v) for v in patch.embedding)
                or not any(v != 0 for v in patch.embedding)
                or len(patch.bbox) != 4
                or not all(math.isfinite(v) and 0 <= v <= 1 for v in patch.bbox)
                or patch.bbox[0] >= patch.bbox[2] or patch.bbox[1] >= patch.bbox[3]):
            raise ValueError("Invalid visual patch")
    # Validate the whole replacement before deleting any current index rows.
    if replace_existing:
        await db.execute(delete(DocumentVisualPatch).where(
            DocumentVisualPatch.document_id == document_id))
    for patch in patches:
        db.add(DocumentVisualPatch(
            document_id=document_id, page_number=patch.page_number,
            region_id=patch.region_id, kind=patch.kind, bbox=patch.bbox,
            ocr_text=patch.ocr_text, embedding=patch.embedding,
            encoder_model=patch.encoder_model))
    await db.flush()
    return len(patches)


async def retrieve_visual_patches(
    db: AsyncSession, question: str, user_id: UUID, *,
    document_ids: list[UUID] | None = None, top_k: int = 4, settings=None,
) -> list:
    """Retrieve real image crops with aligned CLIP text cosine similarity.

    An image with no observed OCR/caption is searchable but cannot support a
    textual answer; omit it here rather than fabricate image understanding.
    The actual region bounds still identify exactly which image was retrieved.
    """
    if settings is None:
        from config import get_settings
        settings = get_settings()
    if not getattr(settings, "visual_embeddings_enabled", False):
        return []
    if document_ids is not None and not document_ids:
        return []
    from documents.models import Document, DocumentVisualPatch
    from chat.rag import SourceChunk
    identity = encoder_identity(settings)
    scoped = select(DocumentVisualPatch.id).join(
        Document, Document.id == DocumentVisualPatch.document_id).where(
        Document.user_id == user_id,
        Document.status.in_(["ready", "partial"]),
        DocumentVisualPatch.encoder_model == identity,
        DocumentVisualPatch.ocr_text != "",
    )
    if document_ids is not None:
        scoped = scoped.where(Document.id.in_(document_ids))
    # Cold CLIP loading is much slower than this indexed owner/document probe.
    # Empty indexes should never trigger a large CPU model allocation.
    if await db.scalar(scoped.limit(1)) is None:
        return []
    vector = await run_in_threadpool(encode_visual_query, question, settings)
    distance = DocumentVisualPatch.embedding.cosine_distance(vector)
    statement = select(DocumentVisualPatch, Document.name, distance.label("distance")).join(
        Document, Document.id == DocumentVisualPatch.document_id).where(
        DocumentVisualPatch.id.in_(scoped))
    result = await db.execute(statement.order_by(distance).limit(max(1, min(top_k, 8))))
    sources = []
    for patch, document_name, cosine_distance in result.all():
        sources.append(SourceChunk(
            chunk_id=f"visual:{patch.id}", content=patch.ocr_text,
            score=1.0 - float(cosine_distance), document_id=str(patch.document_id),
            document_name=document_name, page=patch.page_number,
            retrieval_path="visual_spatial", evidence_kind="visual_patch",
            element_type=patch.kind,
            spatial_regions=[{"id": patch.region_id, "kind": patch.kind,
                              "bbox": patch.bbox, "text": patch.ocr_text,
                              "coordinates": "normalized-top-left",
                              "encoder_model": patch.encoder_model,
                              "visual_embedding": True}],
        ))
    return sources
