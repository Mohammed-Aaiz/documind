"""Document Insights aggregation service.

Computes real, stored-data-only statistics for a single document using
bounded aggregate SQL.  No chunk content is materialised into Python, no
external model or LLM is called, and no metric is fabricated: every value is
produced by a database aggregate over the document's own rows.

Ownership is enforced by the caller (``documents/routes.py``), which fetches
the document scoped to the authenticated user before this service runs.

Portability: only ``func.length`` / ``func.avg`` / ``func.count`` /
``func.distinct`` / ``cast(..., Text)`` are used, so the same statements run
against the SQLite test harness and PostgreSQL production.

Page-count rule
---------------
``pageCount`` is only reported for paged formats (PDF), where a chunk's
``page`` metadata is a real document page.  For DOCX/TXT and any other format
``page`` is NULL, so ``pageCount`` is honestly reported as ``None`` rather than
invented.

Element-type rule
-----------------
``elementTypeCounts`` counts only chunks that carry a non-null
``element_type``.  Legacy chunks written before the structure metadata existed
have a NULL ``element_type`` and are therefore not assigned a fabricated
category.
"""

from __future__ import annotations

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import Document, DocumentChunk
from graph.models import DocumentGraphEdge

#: File types whose chunk ``page`` metadata represents real document pages.
_PAGED_FILE_TYPES = frozenset({"pdf"})


def _avg_to_float(value) -> float | None:
    """Normalise a SQL ``AVG`` result (``Decimal`` on PostgreSQL) to float.

    ``None`` is preserved: an average with no observations is not zero.
    """
    if value is None:
        return None
    return round(float(value), 2)


async def _structure_metrics(db: AsyncSession, document: Document) -> dict:
    """Chunk-level structural statistics for ``document`` (one aggregate query)."""
    row = (
        await db.execute(
            select(
                func.count(),
                func.count(func.distinct(DocumentChunk.page)),
                func.max(DocumentChunk.page),
                func.count(func.distinct(DocumentChunk.section)),
                # ``heading_path`` is JSON, which has no equality operator in
                # PostgreSQL; cast to text so DISTINCT is portable.
                func.count(
                    func.distinct(cast(DocumentChunk.heading_path, Text))
                ),
                func.avg(func.length(DocumentChunk.content)),
                func.avg(DocumentChunk.token_count),
                func.coalesce(func.sum(DocumentChunk.token_count), 0),
            ).where(DocumentChunk.document_id == document.id)
        )
    ).one()

    (
        total_chunks,
        pages_represented,
        max_page,
        sections_represented,
        heading_paths_represented,
        avg_chunk_length,
        avg_token_count,
        total_token_count,
    ) = row

    element_rows = (
        await db.execute(
            select(DocumentChunk.element_type, func.count())
            .where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.element_type.isnot(None),
            )
            .group_by(DocumentChunk.element_type)
        )
    ).all()

    page_count: int | None = None
    if document.file_type in _PAGED_FILE_TYPES and max_page is not None:
        page_count = int(max_page)

    return {
        "totalChunks": int(total_chunks or 0),
        "pagesRepresented": int(pages_represented or 0),
        "pageCount": page_count,
        "sectionsRepresented": int(sections_represented or 0),
        "headingPathsRepresented": int(heading_paths_represented or 0),
        "elementTypeCounts": {str(t): int(c) for t, c in element_rows},
        "avgChunkLength": _avg_to_float(avg_chunk_length),
        "avgTokenCount": _avg_to_float(avg_token_count),
        "totalTokenCount": int(total_token_count or 0),
    }


async def _embedding_metrics(
    db: AsyncSession, document: Document, total_chunks: int
) -> dict:
    """How much of the document is actually embedded."""
    embedded_chunk_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document.id,
                    DocumentChunk.embedding.isnot(None),
                )
            )
        ).scalar_one()
        or 0
    )

    coverage = (
        round(embedded_chunk_count / total_chunks, 4) if total_chunks else 0.0
    )
    return {
        "embeddedChunkCount": embedded_chunk_count,
        "coverage": coverage,
    }


async def _graph_metrics(
    db: AsyncSession, document: Document, total_chunks: int
) -> dict:
    """Structural-graph statistics for ``document`` (read-only)."""
    edge_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(DocumentGraphEdge)
                .where(DocumentGraphEdge.document_id == document.id)
            )
        ).scalar_one()
        or 0
    )

    relation_rows = (
        await db.execute(
            select(DocumentGraphEdge.relation, func.count())
            .where(DocumentGraphEdge.document_id == document.id)
            .group_by(DocumentGraphEdge.relation)
        )
    ).all()

    # Distinct chunk ids appearing as either endpoint of an edge.  UNION
    # deduplicates across the two id sets, so the count is exact.
    source_ids = select(
        DocumentGraphEdge.source_chunk_id.label("chunk_id")
    ).where(DocumentGraphEdge.document_id == document.id)
    target_ids = select(
        DocumentGraphEdge.target_chunk_id.label("chunk_id")
    ).where(DocumentGraphEdge.document_id == document.id)
    node_count = int(
        (
            await db.execute(
                select(func.count()).select_from(
                    source_ids.union(target_ids).subquery()
                )
            )
        ).scalar_one()
        or 0
    )

    coverage = round(node_count / total_chunks, 4) if total_chunks else 0.0
    return {
        "nodeCount": node_count,
        "edgeCount": edge_count,
        "relationCounts": {str(r): int(c) for r, c in relation_rows},
        "coverage": coverage,
    }


async def compute_document_insights(db: AsyncSession, document: Document) -> dict:
    """Return the full insights payload for an already-ownership-checked document.

    The caller must have loaded ``document`` scoped to the authenticated user;
    this function does not perform ownership checks itself.
    """
    structure = await _structure_metrics(db, document)
    embedding = await _embedding_metrics(db, document, structure["totalChunks"])
    graph = await _graph_metrics(db, document, structure["totalChunks"])

    return {
        "documentId": str(document.id),
        "name": document.name,
        "fileType": document.file_type,
        "fileSize": document.file_size,
        "status": document.status,
        "embeddingStatus": document.embedding_status,
        "createdAt": (
            document.created_at.isoformat() if document.created_at else ""
        ),
        "chunkCount": document.chunk_count,
        "structure": structure,
        "embedding": embedding,
        "graph": graph,
        "provenance": {
            "parserVersion": document.parser_version,
            "chunkerVersion": document.chunker_version,
            "embeddingModel": document.embedding_model,
        },
    }
