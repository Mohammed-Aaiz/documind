import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import Base


class ReliabilityLog(Base):
    """Persisted record of the most recent RAG-query reliability snapshot.

    One row per user; updated in-place on every new query so that the
    ``GET /api/reliability/last-query`` endpoint always returns fresh data
    without needing an in-memory cache.
    """

    __tablename__ = "reliability_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Core metrics (same fields the frontend already consumes)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    qa_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_retrieval_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    factual_grounded: Mapped[bool] = mapped_column(nullable=False, default=False)
    insufficient_context: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Source references stored as JSONB array — no separate table needed.
    sources_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# Legacy SourceRef kept for backward-compat with any Alembic history.
# New code should prefer ReliabilityLog for the reliability-center use-case.
# ---------------------------------------------------------------------------

class SourceRef(Base):
    __tablename__ = "source_refs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extraction_node: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UNRESOLVED"
    )  # VERIFIED, MARGINAL, UNRESOLVED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
