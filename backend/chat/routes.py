from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from storage.database import get_db
from chat.models import ChatSession, ChatMessage
from chat.qa_model import is_model_available, get_model_status
from brain import Brain
from brain.adapters import create_registry
from brain.types import ExecutionContext
from outcomes import Outcome
from reliability.routes import store_query_reliability  # async, takes db=

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    topK: int = 5


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


class ReliabilityEvidence(BaseModel):
    """Real evidence from the RAG pipeline — no fabricated metrics.

    Phase 3D: ``sourceCount`` now counts the sources that were actually
    supplied to the QA model (not merely retrieved), and the extra fields make
    omissions and the token budget explicit rather than silent.  They have
    defaults so existing clients are unaffected.
    """
    qaConfidence: float          # QA model confidence score
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


class AskResponse(BaseModel):
    answer: str
    confidence: float
    sources: list[SourceOut]
    insufficientContext: bool
    question: str
    reliability: ReliabilityEvidence
    outcome: str  # Application-level outcome classification


# ---------------------------------------------------------------------------
# Chat Session Schemas
# ---------------------------------------------------------------------------

class SessionOut(BaseModel):
    id: str
    createdAt: str
    preview: str  # first user message text, or empty


class SessionListResponse(BaseModel):
    sessions: list[SessionOut]


class CreateSessionRequest(BaseModel):
    title: str = ""


class CreateSessionResponse(BaseModel):
    id: str
    createdAt: str


class MessageOut(BaseModel):
    id: str
    sender: str  # 'user' or 'oracle'
    content: str
    createdAt: str


class MessageListResponse(BaseModel):
    messages: list[MessageOut]


class AddMessageRequest(BaseModel):
    sender: str  # 'user' or 'oracle'
    content: str


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
):
    """Return all chat sessions for the current user, newest first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
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
    session = ChatSession(user_id=current_user.id)
    db.add(session)
    await db.flush()
    return CreateSessionResponse(
        id=str(session.id),
        createdAt=session.created_at.isoformat() if session.created_at else "",
    )


# ---------------------------------------------------------------------------
# GET /api/chat/sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return all messages for a session, ordered chronologically."""
    # Verify session belongs to user
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
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
):
    """Persist a single message to a session."""
    # Verify session belongs to user
    sess_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
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

@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Answer a question using the Brain over the user's documents.

    The Brain orchestrates: classify → plan → retrieve → context → QA →
    evidence gate → outcome.  Services execute; Brain decides.
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # 1. Create real service adapters wired to this request's db session
    registry = create_registry(db)
    brain = Brain(registry)

    # 2. Build execution context from the API boundary
    ctx = ExecutionContext(
        user_id=str(current_user.id),
        raw_question=body.question,
        top_k=body.topK,
    )

    # 3. Let the Brain process the request
    ctx = await brain.process(ctx)

    # 4. Handle model unavailability as explicit 503 (preserves existing contract)
    if ctx.outcome == Outcome.UNAVAILABLE:
        # Check if it's specifically a model issue
        model_errors = [
            e for e in ctx.errors
            if "qa_answer" in e.service.lower() or "model" in e.message.lower()
        ]
        if model_errors or not is_model_available():
            status = get_model_status()
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "DocuMind QA model is not available",
                    "message": status.get("error", "Unknown error"),
                    "model_path": status.get("model_path"),
                },
            )

    # 5. Translate BrainResponse → AskResponse (existing Pydantic contract)
    br = ctx.response
    assert br is not None  # Brain always sets response

    sources = [
        SourceOut(
            chunkId=s.chunk_id,
            content=s.content,
            score=round(max(0.0, s.score), 4),
            documentId=s.document_id,
            documentName=s.document_name,
            page=s.page,
            headingPath=list(s.heading_path) if s.heading_path else None,
            section=s.section,
            elementType=s.element_type,
            tokenCount=s.token_count,
            chunkerVersion=s.chunker_version,
        )
        for s in br.sources
    ]

    reliability = ReliabilityEvidence(
        qaConfidence=br.reliability.get("qaConfidence", 0.0),
        retrievalScore=br.reliability.get("retrievalScore", 0.0),
        avgRetrievalScore=br.reliability.get("avgRetrievalScore", 0.0),
        sourceCount=br.reliability.get("sourceCount", 0),
        uniqueDocuments=br.reliability.get("uniqueDocuments", 0),
        factualGrounded=br.reliability.get("factualGrounded", False),
        insufficientContext=br.reliability.get("insufficientContext", True),
        retrievedSourceCount=br.reliability.get("retrievedSourceCount", 0),
        omittedSourceCount=br.reliability.get("omittedSourceCount", 0),
        contextBudgetTokens=br.reliability.get("contextBudgetTokens", 0),
        contextUsedTokens=br.reliability.get("contextUsedTokens", 0),
    )

    # 6. Store reliability data for the Reliability Center page
    reliability_evidence = {
        "question": body.question,
        "answer": br.answer,
        "qaConfidence": br.reliability.get("qaConfidence", 0.0),
        "retrievalScore": br.reliability.get("retrievalScore", 0.0),
        "avgRetrievalScore": br.reliability.get("avgRetrievalScore", 0.0),
        "sourceCount": br.reliability.get("sourceCount", 0),
        "uniqueDocuments": br.reliability.get("uniqueDocuments", 0),
        "factualGrounded": br.reliability.get("factualGrounded", False),
        "insufficientContext": br.reliability.get("insufficientContext", True),
        "sources": br.reliability.get("sources", []),
    }
    await store_query_reliability(str(current_user.id), reliability_evidence, db=db)

    return AskResponse(
        answer=br.answer,
        confidence=br.confidence,
        sources=sources,
        insufficientContext=br.insufficient_context,
        question=body.question,
        reliability=reliability,
        outcome=br.outcome.value,
    )
