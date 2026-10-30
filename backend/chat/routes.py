from datetime import datetime, timezone
from typing import Literal
import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from storage.database import get_db
from chat.models import ChatSession, ChatMessage
from outcomes import Outcome

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    topK: int = Field(default=5, ge=1, le=20)
    #: The configured Ollama/Groq provider is the product answer engine.
    #: ``generative`` remains a compatibility alias; extractive is retired.
    engine: str = "provider"
    #: Academic answer format for the generative engine: 5, 10 or 15 marks.
    answerFormat: str = "10"
    workspace: Literal["student", "research"] = "student"
    task: str = "answer"


class SourceOut(BaseModel):
    """One supporting source.

    Phase 3D correction: the structure metadata captured at ingestion is now
    carried through retrieval and reported here.  Every added field is
    optional, so existing clients keep working unchanged and legacy chunks
    report ``None``.
    """

    chunkId: str
    content: str
    score: float
    documentId: str
    documentName: str
    page: int | None

    # --- Phase 3D structure metadata (null for legacy chunks) ---
    headingPath: list[str] | None = None
    section: str | None = None
    elementType: str | None = None
    tokenCount: int | None = None
    chunkerVersion: str | None = None

    # --- Dual-path provenance (null when the structural path did not run) ---
    retrievalPath: str | None = None
    """"semantic", "structural", "hybrid" or "knowledge_graph" — which retrieval path(s) found
    this source.  Null only for responses produced before the dual path ran."""

    fusionScore: float | None = None
    """Reciprocal-rank-fusion score.  NOT a similarity; ``score`` still holds
    the pgvector similarity (and stays 0.0 for structural-only sources)."""

    structuralHops: int | None = None
    """Graph hops from the nearest structural seed (0 = the seed itself)."""

    evidenceKind: str | None = None
    """"chunk" (a ``document_chunks`` row), "structure_element" (a
    ``document_structure_elements`` row from the Feature #13 element-level
    structural stream), or "table_row" (a ``document_table_rows`` row from the
    Phase 3 query-gated compact table-evidence band).  Null for responses
    produced before this field."""

    # --- Phase 3 table-row provenance (null for every other evidence kind) ---
    tableElementId: str | None = None
    """The aggregate ``table`` structure element a "table_row" came from."""

    rowIndex: int | None = None
    """The row's own 0-based index inside that table (header row is 0)."""

    headerRepeated: bool | None = None
    """Whether the row's content embeds the table's header row."""

    # --- Owner-scoped entity-relation GraphRAG provenance ---
    knowledgeGraphPath: str | None = None
    knowledgeGraphHops: int | None = None
    knowledgeGraphPredicate: str | None = None
    knowledgeGraphQuote: str | None = None
    spatialRegions: list[dict] | None = None


class ReliabilityEvidence(BaseModel):
    """Real evidence from the RAG pipeline — no fabricated metrics.

    Phase 3D: ``sourceCount`` now counts the sources that were actually
    supplied to the QA model (not merely retrieved), and the extra fields make
    omissions and the token budget explicit rather than silent.  They have
    defaults so existing clients are unaffected.
    """
    qaConfidence: float | None   # None for providers without calibrated confidence
    retrievalScore: float        # best pgvector similarity score
    avgRetrievalScore: float     # mean of all retrieval scores
    sourceCount: int             # sources actually supplied to the QA model
    uniqueDocuments: int         # number of distinct source documents
    factualGrounded: bool        # whether answer span exists in supplied context
    insufficientContext: bool    # retrieval/model flagged insufficient
    retrievedSourceCount: int = 0   # retrieved before the QA window was applied
    omittedSourceCount: int = 0     # retrieved but not supplied to the QA model
    contextBudgetTokens: int = 0    # tokens available in the QA context
    contextUsedTokens: int = 0      # tokens actually supplied to the QA model

    # --- Evidence-sufficiency diagnostics (computed from real signals) ---
    semanticSourceCount: int = 0    # supplied evidence found by pgvector only
    structuralSourceCount: int = 0  # supplied evidence found by the graph only
    structuralElementSourceCount: int = 0  # of those, element-level (structure_element)
    hybridSourceCount: int = 0      # supplied evidence found by both paths
    structuralHopMax: int = 0       # deepest graph expansion among the evidence
    pathAgreement: bool = False     # >= 1 evidence chunk supported by both paths
    evidenceCoverage: float = 1.0   # supplied to QA / selected as final evidence
    fusionEnabled: bool = False     # whether the dual-path pipeline ran
    pipelineVersion: str = "rag-v1" # which pipeline actually produced this answer


class AskResponse(BaseModel):
    answer: str
    confidence: float | None
    sources: list[SourceOut]
    insufficientContext: bool
    question: str
    reliability: ReliabilityEvidence
    outcome: str  # Application-level outcome classification

    # --- Additive: which engine produced this answer (never guessed) ---
    engine: str = "extractive"
    marks: int | None = None
    #: Deterministic verification summary for generative answers; ``None``
    #: means the extractive path produced the answer (not "verified").
    verification: dict | None = None
    warnings: list[str] = []


def _sources_from_chunks(chunks) -> list[SourceOut]:
    """Map retrieved chunks to the API source contract (one implementation)."""
    return [
        SourceOut(
            chunkId=chunk.chunk_id,
            content=chunk.content,
            score=round(max(0.0, float(getattr(chunk, "score", 0.0) or 0.0)), 4),
            documentId=chunk.document_id,
            documentName=chunk.document_name,
            page=chunk.page,
            headingPath=list(chunk.heading_path) if chunk.heading_path else None,
            section=chunk.section,
            elementType=chunk.element_type,
            tokenCount=chunk.token_count,
            chunkerVersion=chunk.chunker_version,
            retrievalPath=chunk.retrieval_path,
            fusionScore=chunk.fusion_score,
            structuralHops=chunk.structural_hops,
            evidenceKind=chunk.evidence_kind,
            tableElementId=chunk.table_element_id,
            rowIndex=chunk.row_index,
            headerRepeated=chunk.header_repeated,
            knowledgeGraphPath=getattr(chunk, "knowledge_graph_path", None),
            knowledgeGraphHops=getattr(chunk, "knowledge_graph_hops", None),
            knowledgeGraphPredicate=getattr(chunk, "knowledge_graph_predicate", None),
            knowledgeGraphQuote=getattr(chunk, "knowledge_graph_quote", None),
            spatialRegions=getattr(chunk, "spatial_regions", None),
        )
        for chunk in chunks
    ]


# ---------------------------------------------------------------------------
# Chat Session Schemas
# ---------------------------------------------------------------------------

class SessionOut(BaseModel):
    id: str
    createdAt: str
    preview: str  # first user message text, or empty
    workspace: Literal["student", "research"] = "student"


class SessionListResponse(BaseModel):
    sessions: list[SessionOut]


class CreateSessionRequest(BaseModel):
    title: str = ""
    workspace: Literal["student", "research"] = "student"


class CreateSessionResponse(BaseModel):
    id: str
    createdAt: str
    workspace: Literal["student", "research"] = "student"


class MessageOut(BaseModel):
    id: str
    sender: str  # 'user' or 'oracle'
    content: str
    createdAt: str
    metadata: dict | None = None


class MessageListResponse(BaseModel):
    messages: list[MessageOut]


class AddMessageRequest(BaseModel):
    sender: Literal["user", "oracle"]
    content: str = Field(min_length=1, max_length=8000)


class AddMessageResponse(BaseModel):
    id: str
    sender: str
    content: str
    createdAt: str


# ---------------------------------------------------------------------------
# GET /api/chat/sessions — list sessions for the current user
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    workspace: Literal["student", "research"] = "student",
):
    """Return all chat sessions for the current user, newest first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id, ChatSession.workspace == workspace)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

    out: list[SessionOut] = []
    for s in sessions:
        # Grab the first user message as preview
        msg_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == s.id, ChatMessage.sender == "user")
            .order_by(ChatMessage.created_at.asc())
            .limit(1)
        )
        first_msg = msg_result.scalar_one_or_none()
        preview = first_msg.content[:120] if first_msg else ""
        out.append(
            SessionOut(
                id=str(s.id),
                createdAt=s.created_at.isoformat() if s.created_at else "",
                preview=preview,
                workspace=s.workspace,
            )
        )

    return SessionListResponse(sessions=out)


# ---------------------------------------------------------------------------
# POST /api/chat/sessions — create a new session
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session for the current user."""
    session = ChatSession(user_id=current_user.id, workspace=body.workspace)
    db.add(session)
    await db.flush()
    return CreateSessionResponse(
        id=str(session.id),
        createdAt=session.created_at.isoformat() if session.created_at else "",
        workspace=session.workspace,
    )


# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    workspace: Literal["student", "research"] = "student",
):
    """Return all messages for a session, ordered chronologically."""
    # Validate UUIDs before passing them into the database driver.
    try:
        session_id = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.workspace == workspace,
        )
    )
    if sess_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return MessageListResponse(
        messages=[
            MessageOut(
                id=str(m.id),
                sender=m.sender,
                content=m.content,
                createdAt=m.created_at.isoformat() if m.created_at else "",
                metadata=getattr(m, "evidence_metadata", None),
            )
            for m in messages
        ]
    )


# ---------------------------------------------------------------------------
# POST /api/chat/sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/messages", response_model=AddMessageResponse, status_code=201)
async def add_message(
    session_id: str,
    body: AddMessageRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    workspace: Literal["student", "research"] = "student",
):
    """Persist a single message to a session."""
    try:
        session_id = str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.workspace == workspace,
        )
    )
    if sess_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msg = ChatMessage(
        session_id=session_id,
        sender=body.sender,
        content=body.content,
    )
    db.add(msg)
    await db.flush()

    return AddMessageResponse(
        id=str(msg.id),
        sender=msg.sender,
        content=msg.content,
        createdAt=msg.created_at.isoformat() if msg.created_at else "",
    )


# ---------------------------------------------------------------------------
# POST /api/chat/ask
# ---------------------------------------------------------------------------

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    workspace: Literal["student", "research"] = "student",
):
    from orchestration.service import require_session, ConversationSessionNotFound, SessionBusyError
    try:
        session = await require_session(db, str(current_user.id), session_id, workspace, lock=True)
    except ConversationSessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except SessionBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.delete(session)
    await db.flush()


async def _answer_with_provider(body: AskRequest, current_user, db: AsyncSession) -> AskResponse:
    from generation.types import GenerationUnavailableError
    from orchestration.service import answer_with_memory, source_payload
    session = ChatSession(user_id=current_user.id, workspace=body.workspace)
    db.add(session)
    await db.flush()
    try:
        result = await answer_with_memory(db, user_id=str(current_user.id), session_id=str(session.id),
            question=body.question, top_k=body.topK, answer_format=body.answerFormat,
            workspace=body.workspace, task=body.task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GenerationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    scores = [s.score for s in result.sources]
    return AskResponse(answer=result.answer, confidence=None,
        sources=[SourceOut(**source_payload(s)) for s in result.sources],
        insufficientContext=result.insufficient_context, question=body.question,
        reliability=ReliabilityEvidence(qaConfidence=None, retrievalScore=max(scores, default=0),
            avgRetrievalScore=sum(scores)/len(scores) if scores else 0,
            sourceCount=len(scores), uniqueDocuments=len({s.document_id for s in result.sources}),
            factualGrounded=False, insufficientContext=result.insufficient_context,
            pipelineVersion=result.pipeline_version),
        outcome=Outcome.INSUFFICIENT_EVIDENCE.value if result.abstained else Outcome.PARTIAL.value,
        engine=result.engine, marks=result.marks, verification=result.verification, warnings=result.warnings)

@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Answer with the configured provider and preserve the turn in its workspace."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Provider selection is server-side; requests cannot trigger cloud fallback.
    engine = (body.engine or "provider").strip().lower()
    if engine in ("provider", "generative"):
        return await _answer_with_provider(body, current_user, db)
    if engine == "extractive":
        raise HTTPException(status_code=410, detail="The custom extractive model has been retired. Use the configured answer provider.")
    raise HTTPException(status_code=400, detail="engine must be provider or generative")
