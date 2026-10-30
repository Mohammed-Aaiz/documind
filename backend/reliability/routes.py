import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from reliability.models import ReliabilityLog
from storage.database import get_db

router = APIRouter(prefix="/api/reliability", tags=["reliability"])


# ---------------------------------------------------------------------------
# Write helper — called by chat/routes.py after every RAG query.
# Upserts a single row per user so only the latest snapshot is kept.
# ---------------------------------------------------------------------------

async def store_query_reliability(
    user_id: str, data: dict, *, db: AsyncSession
) -> None:
    """Upsert the last query's reliability data for this user.

    Uses PostgreSQL ``INSERT ... ON CONFLICT (user_id) DO UPDATE`` so the
    operation is atomic and always exactly one row per user, regardless of
    type-coercion quirks between asyncpg and SQLAlchemy's UUID column.
    """
    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    values = dict(
        user_id=user_uuid,
        question=data.get("question", ""),
        answer=data.get("answer", ""),
        qa_confidence=data.get("qaConfidence", 0.0),
        retrieval_score=data.get("retrievalScore", 0.0),
        avg_retrieval_score=data.get("avgRetrievalScore", 0.0),
        source_count=data.get("sourceCount", 0),
        unique_documents=data.get("uniqueDocuments", 0),
        factual_grounded=data.get("factualGrounded", False),
        insufficient_context=data.get("insufficientContext", True),
        sources_json=data.get("sources", []),
        generation_json=data.get("generation"),
    )

    stmt = (
        insert(ReliabilityLog)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={k: v for k, v in values.items() if k != "user_id"},
        )
    )
    await db.execute(stmt)


# ---------------------------------------------------------------------------
# Pydantic response models — same shape the frontend already consumes.
# ---------------------------------------------------------------------------

class ReliabilitySourceRef(BaseModel):
    id: str
    documentId: str
    documentName: str
    content: str
    relevanceScore: float
    page: int | None
    status: str  # VERIFIED, MARGINAL, UNRESOLVED

    # --- Dual-path provenance (additive; None for rows written before it) ---
    retrievalPath: str | None = None  # semantic | structural | hybrid
    fusionScore: float | None = None  # RRF score — not a similarity
    structuralHops: int | None = None
    # chunk | structure_element | table_row — distinguishes element-level
    # structural evidence, chunk-level structural retrieval (both report path
    # "structural") and the compact table-row band.
    evidenceKind: str | None = None

    # --- Structure metadata (Phase 5; None when not recorded) -------------
    # The section / element type captured at ingestion, persisted so the
    # Reliability Center shows real provenance instead of "not reported".
    section: str | None = None
    elementType: str | None = None

    # --- Phase 5: table-row provenance (None for every other evidence kind) -
    # Exact persisted values, copied from the row's SourceRef.  Never derived
    # from the row text and never reconstructed.
    tableElementId: str | None = None  # the aggregate table structure element
    rowIndex: int | None = None        # 0-based row index (header row is 0)
    headerRepeated: bool | None = None # whether content embeds the header row


class ReliabilityQueryData(BaseModel):
    question: str
    answer: str
    qaConfidence: float | None
    retrievalScore: float
    avgRetrievalScore: float
    sourceCount: int
    uniqueDocuments: int
    factualGrounded: bool
    insufficientContext: bool
    sources: list[ReliabilitySourceRef]

    # --- Evidence-sufficiency provenance (GraphRAG) -----------------------
    #
    # Derived from the persisted per-source provenance of *this* query, not
    # recomputed from a guess: each count partitions ``sources`` exactly.
    semanticSourceCount: int = 0
    structuralSourceCount: int = 0
    structuralElementSourceCount: int = 0
    hybridSourceCount: int = 0
    # Of the structural evidence, how much is the compact table-row band.  Kept
    # separate so "structural chunk" sources are not overstated by table rows
    # (a table row reports retrievalPath "structural" too).  Partitions the
    # structural bucket together with structuralElementSourceCount.
    tableRowSourceCount: int = 0
    structuralHopMax: int = 0
    pathAgreement: bool = False

    # --- Additive generative-path metadata (None for extractive answers) ---
    # Engine/model, requested mark format, latency, abstention and the
    # deterministic verification report.  Null means "this answer was produced
    # by the extractive path", never "verification passed".
    generation: dict | None = None


_EMPTY = ReliabilityQueryData(
    question="",
    answer="",
    qaConfidence=0.0,
    retrievalScore=0.0,
    avgRetrievalScore=0.0,
    sourceCount=0,
    uniqueDocuments=0,
    factualGrounded=False,
    insufficientContext=True,
    sources=[],
)


# ---------------------------------------------------------------------------
# GET /api/reliability/last-query
# ---------------------------------------------------------------------------

@router.get("/last-query", response_model=ReliabilityQueryData)
async def get_last_query_reliability(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the reliability data from the user's most recent RAG query."""
    result = await db.execute(
        select(ReliabilityLog).where(ReliabilityLog.user_id == str(current_user.id))
    )
    row = result.scalar_one_or_none()

    if row is None:
        return _EMPTY

    sources = row.sources_json or []
    # Normalise source dicts into the Pydantic model the frontend expects.
    source_refs = [
        ReliabilitySourceRef(
            id=s.get("id", ""),
            documentId=s.get("documentId", ""),
            documentName=s.get("documentName", ""),
            content=s.get("content", ""),
            relevanceScore=s.get("relevanceScore", 0.0),
            page=s.get("page"),
            status=s.get("status", "UNRESOLVED"),
            retrievalPath=s.get("retrievalPath"),
            fusionScore=s.get("fusionScore"),
            structuralHops=s.get("structuralHops"),
            evidenceKind=s.get("evidenceKind"),
            section=s.get("section"),
            elementType=s.get("elementType"),
            tableElementId=s.get("tableElementId"),
            rowIndex=s.get("rowIndex"),
            headerRepeated=s.get("headerRepeated"),
        )
        for s in sources
    ]

    # Path counts are derived from the persisted provenance of this query, so
    # the Reliability Center reports exactly what the answer was built from.
    semantic_count = sum(1 for s in source_refs if s.retrievalPath == "semantic")
    structural_count = sum(1 for s in source_refs if s.retrievalPath == "structural")
    hybrid_count = sum(1 for s in source_refs if s.retrievalPath == "hybrid")
    # Of the structural evidence, how much is element-level (Feature #13).
    structural_element_count = sum(
        1 for s in source_refs if s.evidenceKind == "structure_element"
    )
    # Table-row evidence is structural by path; counted separately so the UI can
    # keep the chunk-level structural remainder honest.
    table_row_count = sum(
        1 for s in source_refs if s.evidenceKind == "table_row"
    )
    hops = [s.structuralHops for s in source_refs if s.structuralHops is not None]

    return ReliabilityQueryData(
        question=row.question,
        answer=row.answer,
        qaConfidence=(None if (row.generation_json or {}).get("engine") in {"ollama", "groq"} else row.qa_confidence),
        retrievalScore=row.retrieval_score,
        avgRetrievalScore=row.avg_retrieval_score,
        sourceCount=row.source_count,
        uniqueDocuments=row.unique_documents,
        factualGrounded=row.factual_grounded,
        insufficientContext=row.insufficient_context,
        sources=source_refs,
        semanticSourceCount=semantic_count,
        structuralSourceCount=structural_count,
        structuralElementSourceCount=structural_element_count,
        hybridSourceCount=hybrid_count,
        tableRowSourceCount=table_row_count,
        structuralHopMax=max(hops) if hops else 0,
        pathAgreement=hybrid_count > 0,
        generation=getattr(row, "generation_json", None),
    )
