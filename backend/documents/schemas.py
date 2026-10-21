"""Document request/response Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    name: str
    fileType: str
    fileSize: int
    chunkCount: int
    status: str
    embeddingStatus: str
    createdAt: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class DocumentDetailResponse(BaseModel):
    id: str
    name: str
    fileType: str
    fileSize: int
    chunkCount: int
    status: str
    embeddingStatus: str
    createdAt: str
    chunks: list["ChunkOut"]
    # Chunk pagination window (DB-level LIMIT/OFFSET, ordered by chunk_index).
    # ``total`` is the document's full chunk count, independent of the window.
    total: int = 0
    limit: int = 0
    offset: int = 0


class ChunkOut(BaseModel):
    id: str
    chunkIndex: int
    content: str
    page: int | None


DocumentDetailResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Document insights (GET /api/documents/{document_id}/insights)
# ---------------------------------------------------------------------------


class DocumentStructureInsights(BaseModel):
    """Chunk-level structural statistics, computed by SQL aggregation.

    ``pageCount`` is only meaningful for paged formats (PDF); it is ``None``
    for DOCX/TXT, where chunk ``page`` metadata does not exist.  Averages are
    ``None`` when there are no observations (never a fabricated zero).
    """

    totalChunks: int
    pagesRepresented: int
    pageCount: int | None
    sectionsRepresented: int
    headingPathsRepresented: int
    elementTypeCounts: dict[str, int]
    avgChunkLength: float | None
    avgTokenCount: float | None
    totalTokenCount: int


class DocumentEmbeddingInsights(BaseModel):
    """Embedding coverage for the document's chunks."""

    embeddedChunkCount: int
    coverage: float


class DocumentGraphInsights(BaseModel):
    """Read-only statistics for the document's structure graph."""

    nodeCount: int
    edgeCount: int
    relationCounts: dict[str, int]
    coverage: float


class DocumentProvenanceInsights(BaseModel):
    """Which pipeline components produced this document's data."""

    parserVersion: str | None
    chunkerVersion: str | None
    embeddingModel: str | None


class DocumentInsightsResponse(BaseModel):
    """Real, stored-data-only insights for one document.

    Deliberately excludes query-scoped reliability/QA metrics and any
    generated summary: those are not document-scoped and would be fabricated
    here.
    """

    documentId: str
    name: str
    fileType: str
    fileSize: int
    status: str
    embeddingStatus: str
    createdAt: str
    chunkCount: int
    structure: DocumentStructureInsights
    embedding: DocumentEmbeddingInsights
    graph: DocumentGraphInsights
    provenance: DocumentProvenanceInsights
