"""Document request/response Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


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


class DocumentOcrPageInsights(BaseModel):
    """One page whose text came from the OCR fallback.

    ``ocrConfidence`` is the mean confidence of the recognised lines the engine
    kept — a reading, not a probability that the page is understood.
    ``ocrRotation`` is the rotation the page had to be read at (0/90/180/270).
    """

    pageNumber: int
    textChars: int
    ocrEngine: str | None
    ocrEngineVersion: str | None
    ocrConfidence: float | None
    ocrRotation: int | None
    ocrSeconds: float | None


class DocumentUnaccountedPageInsights(BaseModel):
    """One page that produced no usable text, and the reason recorded for it."""

    pageNumber: int
    failureReason: str | None


class DocumentPageExtractionInsights(BaseModel):
    """Per-page extraction provenance for the last processing run.

    ``recorded`` is ``False`` for a format without pages (DOCX/TXT) and for a
    document processed before this provenance was persisted — the counts are
    then all zero and must not be read as "this document has no pages".
    """

    recorded: bool
    pagesTotal: int
    nativePageCount: int
    ocrPageCount: int
    unaccountedPageCount: int
    ocrPages: list[DocumentOcrPageInsights]
    unaccountedPages: list[DocumentUnaccountedPageInsights]
    spatialLayouts: list[dict] = Field(default_factory=list)


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
    pages: DocumentPageExtractionInsights
    provenance: DocumentProvenanceInsights
