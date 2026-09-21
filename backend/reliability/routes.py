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


class ReliabilityQueryData(BaseModel):
    question: str
    answer: str
    qaConfidence: float
    retrievalScore: float
    avgRetrievalScore: float
    sourceCount: int
    uniqueDocuments: int
    factualGrounded: bool
    insufficientContext: bool
    sources: list[ReliabilitySourceRef]


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
        )
        for s in sources
    ]

    return ReliabilityQueryData(
        question=row.question,
        answer=row.answer,
        qaConfidence=row.qa_confidence,
        retrievalScore=row.retrieval_score,
        avgRetrievalScore=row.avg_retrieval_score,
        sourceCount=row.source_count,
        uniqueDocuments=row.unique_documents,
        factualGrounded=row.factual_grounded,
        insufficientContext=row.insufficient_context,
        sources=source_refs,
    )
