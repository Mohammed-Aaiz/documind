"""Archive the exact derived evidence before replacing a document's index."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import (
    Document, DocumentChunk, DocumentIndexRevision, DocumentPageExtraction,
    DocumentTableRow, DocumentVisualPatch,
)
from graph.models import (
    DocumentGraphEdge, DocumentStructureEdge, DocumentStructureElement,
    KnowledgeGraphEntity, KnowledgeGraphExtraction, KnowledgeGraphMention,
    KnowledgeGraphRelation,
)


def _json_default(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"Unsupported index snapshot value: {type(value).__name__}")


async def archive_document_index(
    db: AsyncSession, doc: Document,
) -> DocumentIndexRevision | None:
    """Caller holds the document lock and commits archive + replacement together.

    Failures propagate before any index deletion. No independent commit is made,
    so a failed reprocessing attempt also rolls back the provisional archive.
    """
    models = (DocumentChunk, DocumentGraphEdge, DocumentStructureElement,
              DocumentStructureEdge, DocumentTableRow, DocumentPageExtraction,
              DocumentVisualPatch, KnowledgeGraphMention, KnowledgeGraphRelation,
              KnowledgeGraphExtraction)
    tables = {}
    for model in models:
        result = await db.execute(select(model).where(model.document_id == doc.id).order_by(model.id))
        tables[model.__tablename__] = [
            {column.key: getattr(row, column.key) for column in model.__table__.columns}
            for row in result.scalars().all()
        ]
    if not any(tables.values()):
        return None
    entity_ids = {row["entity_id"] for row in tables[KnowledgeGraphMention.__tablename__]}
    entities = await db.execute(select(KnowledgeGraphEntity).where(
        KnowledgeGraphEntity.user_id == doc.user_id, KnowledgeGraphEntity.id.in_(entity_ids),
    ).order_by(KnowledgeGraphEntity.id))
    tables[KnowledgeGraphEntity.__tablename__] = [
        {column.key: getattr(row, column.key) for column in KnowledgeGraphEntity.__table__.columns}
        for row in entities.scalars().all()
    ]
    payload = {
        "schemaVersion": 1, "capturedAt": datetime.now(timezone.utc).isoformat(),
        "chunkCount": len(tables[DocumentChunk.__tablename__]),
        "document": {column.key: getattr(doc, column.key) for column in Document.__table__.columns},
        "tables": tables,
    }
    # Normalize vector ndarrays and reject non-finite numbers before DB mutation.
    payload = json.loads(json.dumps(payload, default=_json_default, allow_nan=False))
    revision = DocumentIndexRevision(
        document_id=doc.id, user_id=doc.user_id, chunker_version=doc.chunker_version,
        embedding_model=doc.embedding_model, payload=payload,
    )
    db.add(revision)
    await db.flush()
    return revision


def revision_metadata(revision: DocumentIndexRevision) -> dict:
    chunks = revision.payload.get("tables", {}).get("document_chunks", [])
    return {"revisionId": str(revision.id), "documentId": str(revision.document_id),
            "createdAt": revision.created_at.isoformat() if revision.created_at else "",
            "chunkerVersion": revision.chunker_version, "embeddingModel": revision.embedding_model,
            "chunkCount": len(chunks)}


def revision_sources(revision: DocumentIndexRevision, *, chunk_id: UUID | None = None) -> list[dict]:
    """Expose only citable source fields, never vectors or internal graph rows."""
    chunks = revision.payload.get("tables", {}).get("document_chunks", [])
    if chunk_id is not None:
        chunks = [row for row in chunks if row["id"] == str(chunk_id)]
    return [{"chunkId": row["id"], "chunkIndex": row["chunk_index"],
             "content": row["content"], "page": row.get("page"),
             "headingPath": row.get("heading_path"), "section": row.get("section"),
             "elementType": row.get("element_type"), "tokenCount": row.get("token_count")}
            for row in sorted(chunks, key=lambda row: (row["chunk_index"], row["id"]))]
