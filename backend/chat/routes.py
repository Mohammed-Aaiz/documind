from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from storage.database import get_db
from chat.models import ChatSession, ChatMessage
from chat.qa_model import is_model_available, get_model_status
from chat.rag import dual_path_enabled
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
    #: Answer engine for this request.  ``extractive`` (default) preserves the
    #: existing contract; ``generative`` uses the approved local Flan-T5 path
    #: through the same retrieval pipeline.  The default does not change
    #: silently (DOCUMIND_PROJECT_CONTEXT.md §0.8).
    engine: str = "extractive"
    #: Academic answer format for the generative engine: 5, 10 or 15 marks.
    answerFormat: str = "10"


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
    """"semantic", "structural" or "hybrid" — which retrieval path(s) found
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
    confidence: float
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
        )
        for chunk in chunks
    ]


async def _answer_with_generation(
    body: AskRequest, current_user, db: AsyncSession
) -> AskResponse:
    """Serve ``/api/chat/ask`` with the approved local generative engine.

    Retrieval, verification and reliability persistence are delegated to
    ``generation.service`` — the same code path ``/api/generation/answer``
    uses — so the two API surfaces cannot drift apart.  The extractive default
    is untouched: this only runs when the caller explicitly selects it.
    """
    from generation.engine import get_generator_status
    from generation.service import persist_generation, run_generation
    from generation.types import AnswerFormat, GenerationUnavailableError

    question = body.question.strip()
    try:
        answer_format = AnswerFormat.coerce(body.answerFormat)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_id = str(current_user.id)
    try:
        chunks, result = await run_generation(
            db, user_id, question, top_k=body.topK, answer_format=answer_format
        )
    except GenerationUnavailableError as exc:
        status = get_generator_status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DocuMind generative model is not available",
                "message": str(exc),
                "model": status.get("model"),
            },
        ) from exc

    # Persist before responding: a failure here must not look like an answer.
    await persist_generation(db, user_id, question, chunks, result, answer_format)

    supplied_ids = {b.chunk_id for b in result.blocks if b.chunk_id}
    supplied = [c for c in chunks if str(getattr(c, "chunk_id", "")) in supplied_ids]
    if not supplied:
        supplied = list(chunks)

    scores = [max(0.0, float(getattr(c, "score", 0.0) or 0.0)) for c in supplied]
    paths = [getattr(c, "retrieval_path", None) for c in supplied]
    verification = result.verification

    reliability = ReliabilityEvidence(
        qaConfidence=0.0,  # the generative engine produces no extractive span
        retrievalScore=round(max(scores, default=0.0), 4),
        avgRetrievalScore=round(sum(scores) / len(scores), 4) if scores else 0.0,
        sourceCount=len(result.blocks),
        uniqueDocuments=len({b.document_id for b in result.blocks if b.document_id}),
        factualGrounded=bool(verification.get("verified")),
        insufficientContext=result.insufficient_context,
        retrievedSourceCount=len(chunks),
        omittedSourceCount=max(0, len(chunks) - len(supplied)),
        semanticSourceCount=paths.count("semantic"),
        structuralSourceCount=paths.count("structural"),
        structuralElementSourceCount=sum(
            1 for c in supplied if getattr(c, "evidence_kind", None) == "structure_element"
        ),
        hybridSourceCount=paths.count("hybrid"),
        structuralHopMax=max(
            (int(getattr(c, "structural_hops", 0) or 0) for c in supplied), default=0
        ),
        pathAgreement="hybrid" in paths,
        evidenceCoverage=(
            len(supplied) / len(chunks) if chunks else 1.0
        ),
        fusionEnabled=dual_path_enabled(),
        pipelineVersion=(
            "generative-dual-path-v1" if dual_path_enabled() else "generative-semantic-v1"
        ),
    )

    return AskResponse(
        answer=result.answer,
        confidence=0.0,  # honest: the generative engine has no span confidence
        sources=_sources_from_chunks(supplied),
        insufficientContext=result.insufficient_context,
        question=question,
        reliability=reliability,
        outcome=(
            Outcome.INSUFFICIENT_EVIDENCE.value
            if result.insufficient_context
            else Outcome.SUCCESS.value
        ),
        engine="generative",
        marks=result.marks,
        verification=verification,
        warnings=list(result.warnings),
    )


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

    # 0. Explicit engine selection.  The extractive Brain path below remains the
    # default; ``generative`` is opt-in per request (DOCUMIND_PROJECT_CONTEXT.md
    # §0.8) and reuses the shared generation service rather than duplicating it.
    engine = (body.engine or "extractive").strip().lower()
    if engine == "generative":
        return await _answer_with_generation(body, current_user, db)
    if engine != "extractive":
        raise HTTPException(
            status_code=400,
            detail="engine must be 'extractive' or 'generative'",
        )

    # 1. Create real service adapters wired to this request's db session
    registry = create_registry(db)
    brain = Brain(registry)

    # 2. Build execution context from the API boundary
    ctx = ExecutionContext(
        user_id=str(current_user.id),
        raw_question=body.question,
        top_k=body.topK,
    )
    # The reported pipeline version reflects the pipeline that will actually run
    # for this request — the dual-path (semantic + document-structure) pipeline
    # when it is active, otherwise the original semantic-only pipeline.  It is
    # never advanced merely because the code exists.
    ctx.pipeline_version = (
        "dual-path-graph-rag-v1" if dual_path_enabled() else "rag-v1"
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
            retrievalPath=s.retrieval_path,
            fusionScore=s.fusion_score,
            structuralHops=s.structural_hops,
            evidenceKind=s.evidence_kind,
            tableElementId=s.table_element_id,
            rowIndex=s.row_index,
            headerRepeated=s.header_repeated,
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
        semanticSourceCount=br.reliability.get("semanticSourceCount", 0),
        structuralSourceCount=br.reliability.get("structuralSourceCount", 0),
        structuralElementSourceCount=br.reliability.get(
            "structuralElementSourceCount", 0
        ),
        hybridSourceCount=br.reliability.get("hybridSourceCount", 0),
        structuralHopMax=br.reliability.get("structuralHopMax", 0),
        pathAgreement=br.reliability.get("pathAgreement", False),
        evidenceCoverage=br.reliability.get("evidenceCoverage", 1.0),
        fusionEnabled=br.reliability.get("fusionEnabled", False),
        pipelineVersion=ctx.pipeline_version,
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
        # Evidence-sufficiency / provenance signals, persisted so the Reliability
        # Center reads exactly the values that were returned to the client.
        "semanticSourceCount": br.reliability.get("semanticSourceCount", 0),
        "structuralSourceCount": br.reliability.get("structuralSourceCount", 0),
        "structuralElementSourceCount": br.reliability.get(
            "structuralElementSourceCount", 0
        ),
        "hybridSourceCount": br.reliability.get("hybridSourceCount", 0),
        "structuralHopMax": br.reliability.get("structuralHopMax", 0),
        "pathAgreement": br.reliability.get("pathAgreement", False),
        "evidenceCoverage": br.reliability.get("evidenceCoverage", 1.0),
        "fusionEnabled": br.reliability.get("fusionEnabled", False),
        "pipelineVersion": ctx.pipeline_version,
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
