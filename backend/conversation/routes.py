"""Authenticated, workspace-scoped conversation and SSE delivery.

The service owns retrieval, provider selection and SQL persistence. Streamed
text is provisional; the final event replaces it after citation checks.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from chat.routes import SourceOut
from generation.types import AnswerFormat, GenerationUnavailableError
from generation.providers import probe_provider
from orchestration.service import (
    ConversationSessionNotFound, SessionBusyError, answer_with_memory,
    clear_conversation, conversation_history, conversation_status,
    require_session, stream_with_memory,
)
from session.store import InvalidConversationIdError, conversation_key
from storage.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversation", tags=["conversation"])
Workspace = Literal["student", "research"]
ConversationTask = Literal["answer", "explain", "revision", "practice", "synthesis", "comparison", "critique", "gaps"]
MAX_QUESTION_CHARS = 2000


class ConversationMessageOut(BaseModel):
    role: str
    content: str
    createdAt: str
    metadata: dict | None = None


class ConversationHistoryResponse(BaseModel):
    sessionId: str
    workspace: Workspace = "student"
    messages: list[ConversationMessageOut]
    memoryBackend: str
    memoryError: str | None = None


class AskConversationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    topK: int = Field(default=5, ge=1, le=20)
    answerFormat: str = Field(default="10", max_length=2)
    workspace: Workspace = "student"
    task: ConversationTask = "answer"


class ConversationAnswerResponse(BaseModel):
    sessionId: str
    workspace: Workspace = "student"
    task: str = "answer"
    question: str
    answer: str
    engine: str
    model: str
    hosted: bool = False
    marks: int
    answerFormat: str
    verification: dict
    warnings: list[str]
    sources: list[SourceOut]
    history: list[ConversationMessageOut]
    retrievalQuery: str
    followupResolved: bool
    rerank: dict
    insufficientContext: bool
    abstained: bool
    latencyMs: int
    firstTokenMs: int | None = None
    memoryBackend: str
    memoryError: str | None = None
    pipelineVersion: str


def _source_metadata_value(source, snake_name: str, wire_name: str):
    """Read graph provenance from retrieval objects or persisted wire metadata."""
    if isinstance(source, dict):
        if snake_name in source:
            return source[snake_name]
        return source.get(wire_name)
    value = getattr(source, snake_name, None)
    if value is not None:
        return value
    metadata = getattr(source, "metadata", None)
    return metadata.get(wire_name) if isinstance(metadata, dict) else None


def serialize_answer(answer) -> ConversationAnswerResponse:
    """One wire representation shared by normal requests and SSE finals."""
    sources = [SourceOut(
        chunkId=str(chunk.chunk_id), content=chunk.content,
        score=round(max(0.0, float(getattr(chunk, "score", 0.0) or 0.0)), 4),
        documentId=str(chunk.document_id), documentName=chunk.document_name,
        page=getattr(chunk, "page", None),
        headingPath=list(chunk.heading_path) if getattr(chunk, "heading_path", None) else None,
        section=getattr(chunk, "section", None), elementType=getattr(chunk, "element_type", None),
        tokenCount=getattr(chunk, "token_count", None), chunkerVersion=getattr(chunk, "chunker_version", None),
        retrievalPath=getattr(chunk, "retrieval_path", None), fusionScore=getattr(chunk, "fusion_score", None),
        structuralHops=getattr(chunk, "structural_hops", None), evidenceKind=getattr(chunk, "evidence_kind", None),
        tableElementId=getattr(chunk, "table_element_id", None), rowIndex=getattr(chunk, "row_index", None),
        headerRepeated=getattr(chunk, "header_repeated", None),
        knowledgeGraphPath=_source_metadata_value(chunk, "knowledge_graph_path", "knowledgeGraphPath"),
        knowledgeGraphHops=_source_metadata_value(chunk, "knowledge_graph_hops", "knowledgeGraphHops"),
        knowledgeGraphPredicate=_source_metadata_value(chunk, "knowledge_graph_predicate", "knowledgeGraphPredicate"),
        knowledgeGraphQuote=_source_metadata_value(chunk, "knowledge_graph_quote", "knowledgeGraphQuote"),
        spatialRegions=_source_metadata_value(chunk, "spatial_regions", "spatialRegions"),
    ) for chunk in answer.sources]
    return ConversationAnswerResponse(
        sessionId=answer.session_id, workspace=getattr(answer, "workspace", "student"),
        task=getattr(answer, "task", "answer"), question=answer.question, answer=answer.answer,
        engine=answer.engine, model=answer.model, hosted=getattr(answer, "hosted", False),
        marks=answer.marks, answerFormat=str(answer.marks), verification=answer.verification,
        warnings=answer.warnings, sources=sources,
        history=[ConversationMessageOut.model_validate(turn) for turn in answer.history],
        retrievalQuery=answer.retrieval_query, followupResolved=answer.followup_resolved,
        rerank=answer.rerank, insufficientContext=answer.insufficient_context, abstained=answer.abstained,
        latencyMs=answer.latency_ms, firstTokenMs=getattr(answer, "first_token_ms", None),
        memoryBackend=answer.memory_backend, memoryError=answer.memory_error,
        pipelineVersion=answer.pipeline_version,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidConversationIdError):
        return HTTPException(status_code=400, detail="Invalid session id")
    if isinstance(exc, ConversationSessionNotFound):
        return HTTPException(status_code=404, detail="Conversation not found in this workspace")
    if isinstance(exc, SessionBusyError):
        return HTTPException(status_code=409, detail="A response is already running in this conversation")
    if isinstance(exc, GenerationUnavailableError):
        if getattr(exc, "status_code", None) == 429:
            headers = None
            try:
                delay = float(getattr(exc, "retry_after_seconds", None))
                if math.isfinite(delay):
                    headers = {"Retry-After": str(math.ceil(max(0.0, min(300.0, delay))))}
            except (TypeError, ValueError):
                pass
            return HTTPException(
                status_code=429,
                detail="The answer service is temporarily rate limited. Please wait a moment and try again.",
                headers=headers,
            )
        return HTTPException(status_code=503, detail="The configured answer provider is unavailable. Check provider setup and try again.")
    return HTTPException(status_code=400, detail="Invalid conversation request")


_REQUEST_ERRORS = (ConversationSessionNotFound, SessionBusyError, GenerationUnavailableError, InvalidConversationIdError, ValueError)


def _turn_arguments(body: AskConversationRequest, user_id: str, session_id: str) -> dict:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        AnswerFormat.coerce(body.answerFormat)
        conversation_key(user_id, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation or answer format") from exc
    return dict(user_id=user_id, session_id=session_id, question=question, top_k=body.topK,
                answer_format=body.answerFormat, workspace=body.workspace, task=body.task)


@router.get("/status")
async def get_conversation_status(current_user: CurrentUser) -> dict:
    result = await conversation_status()
    result["conversationModel"] = await probe_provider()
    return result


@router.get("/{session_id}", response_model=ConversationHistoryResponse)
async def get_conversation(session_id: str, current_user: CurrentUser, workspace: Workspace = "student",
                           db: AsyncSession = Depends(get_db)) -> ConversationHistoryResponse:
    try:
        conversation_key(str(current_user.id), session_id)
        messages = await conversation_history(str(current_user.id), session_id, db=db, workspace=workspace)
    except _REQUEST_ERRORS as exc:
        raise _http_error(exc) from exc
    return ConversationHistoryResponse(
        sessionId=session_id, workspace=workspace,
        messages=[ConversationMessageOut.model_validate(m.as_dict()) for m in messages],
        memoryBackend="postgresql",
    )


@router.post("/{session_id}/messages", response_model=ConversationAnswerResponse)
async def ask_in_conversation(session_id: str, body: AskConversationRequest, current_user: CurrentUser,
                              db: AsyncSession = Depends(get_db)) -> ConversationAnswerResponse:
    try:
        answer = await answer_with_memory(db, **_turn_arguments(body, str(current_user.id), session_id))
        await db.commit()
        return serialize_answer(answer)
    except _REQUEST_ERRORS as exc:
        await db.rollback()
        raise _http_error(exc) from exc


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{session_id}/stream")
async def stream_in_conversation(session_id: str, body: AskConversationRequest, request: Request,
                                 current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    arguments = _turn_arguments(body, str(current_user.id), session_id)
    try:
        await require_session(db, str(current_user.id), session_id, body.workspace)
    except _REQUEST_ERRORS as exc:
        raise _http_error(exc) from exc

    async def events():
        stream = stream_with_memory(db, **arguments)
        try:
            async for item in stream:
                if await request.is_disconnected():
                    await db.rollback()
                    return
                event, data = item["event"], item["data"]
                if event == "final":
                    data = serialize_answer(data).model_dump()
                    await db.commit()
                yield _sse(event, data)
        except asyncio.CancelledError:
            await db.rollback()
            raise
        except _REQUEST_ERRORS as exc:
            await db.rollback()
            error = _http_error(exc)
            data = {"code": str(error.status_code), "message": error.detail}
            if error.headers and "Retry-After" in error.headers:
                data["retryAfterSeconds"] = int(error.headers["Retry-After"])
            yield _sse("error", data)
        except Exception:
            await db.rollback()
            logger.exception("Conversation stream failed")
            yield _sse("error", {"code": "stream_failed", "message": "The response could not be completed. Please try again."})
        finally:
            await stream.aclose()

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(session_id: str, current_user: CurrentUser, workspace: Workspace = "student",
                              db: AsyncSession = Depends(get_db)) -> Response:
    try:
        conversation_key(str(current_user.id), session_id)
        await clear_conversation(str(current_user.id), session_id, db=db, workspace=workspace)
        await db.commit()
    except _REQUEST_ERRORS as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
