"""Workspace-authorized SQL conversations, shared by text and voice.

Only completed turns are persisted. Provider streaming never loads the legacy
QA model. Historical graph evaluation code is kept separate from this path.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from chat.models import ChatMessage, ChatSession
from generation.provider_prompt import prepare_prompt, select_evidence, validate_intent
from generation.providers import provider_status, stream_answer
from generation.types import AnswerFormat, EvidenceBlock, GenerationUnavailableError
from generation.verification import content_tokens, split_sentences
from orchestration.followup import resolve_followup
from session.store import ConversationMessage

PIPELINE_VERSION = "visual-spatial-dual-path-v3"
_CITATION = re.compile(r"\[(\d+)\]")


def _build_extractive_fallback(question: str, blocks: list[EvidenceBlock], marks: int) -> str:
    """Build a cited answer from exact retrieved sentences when synthesis fails.

    The local model may omit references or add unsupported details. In that
    case, quote only complete sentences that occur verbatim (whitespace
    normalized) in retrieved evidence and mention a term from the question.
    This fallback is intentionally extractive; it does not turn lexical overlap
    into a factual paraphrase.
    """
    terms = set(content_tokens(question))
    if not terms:
        return ""
    capitalized_terms = {
        token.casefold() for token in re.findall(r"\b[A-Z][a-z0-9]+\b", question)
        if token.casefold() in terms
    }
    focus_terms = capitalized_terms or terms
    limit = {5: 2, 10: 4, 15: 6}.get(marks, 4)
    candidates: list[tuple[int, int, int, str]] = []
    metadata = re.compile(r"\b(?:report id|revision|document pages)\b", re.IGNORECASE)
    article_anchor = re.compile(
        r"\b(?:the|a|an)\s+(?:" + "|".join(re.escape(term) for term in sorted(focus_terms, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )
    for block_rank, block in enumerate(blocks):
        source = re.sub(r"\s+", " ", block.content).strip()
        for sentence_rank, raw_sentence in enumerate(split_sentences(block.content)):
            sentence = re.sub(r"\s+", " ", raw_sentence).strip()
            if len(sentence) < 45 or not re.search(r"[.!?]$", sentence) or metadata.search(sentence):
                continue
            overlap = len(focus_terms & set(content_tokens(sentence)))
            if not overlap:
                continue
            anchor = article_anchor.search(sentence)
            # Strip a document heading prefix such as "Executive Overview The"
            # without cutting a later entity mention out of its sentence.
            if anchor and 0 < anchor.start() <= 40 and not re.search(r"[!?]", sentence[:anchor.start()]):
                sentence = sentence[anchor.start():]
            if sentence not in source:
                continue
            candidates.append((-overlap, block_rank, sentence_rank,
                               f"- {sentence} [{block.index}]"))
    candidates.sort(key=lambda item: item[:3])
    selected: list[str] = []
    seen: set[str] = set()
    for _, _, _, excerpt in candidates:
        fingerprint = re.sub(r"\W+", " ", excerpt.casefold()).strip()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append(excerpt)
        if len(selected) >= limit:
            break
    return "\n".join(selected)


class ConversationSessionNotFound(LookupError):
    """The caller cannot access this session in the requested workspace."""


class SessionBusyError(RuntimeError):
    """A turn is already running in this session."""


@dataclass(frozen=True)
class StoredConversationMessage(ConversationMessage):
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {**super().as_dict(), "metadata": self.metadata}


@dataclass(frozen=True)
class ConversationAnswer:
    session_id: str
    question: str
    retrieval_query: str
    followup_resolved: bool
    answer: str
    engine: str
    model: str
    marks: int
    verification: dict
    warnings: list[str] = field(default_factory=list)
    sources: list[Any] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    rerank: dict = field(default_factory=dict)
    insufficient_context: bool = False
    abstained: bool = False
    latency_ms: int = 0
    memory_backend: str = "postgresql"
    memory_error: str | None = None
    pipeline_version: str = PIPELINE_VERSION
    workspace: str = "student"
    task: str = "answer"
    first_token_ms: int | None = None
    hosted: bool = False
    timings: dict = field(default_factory=dict)


async def require_session(db: Any, user_id: str, session_id: str, workspace: str = "student", *, lock: bool = False) -> ChatSession:
    validate_intent(workspace, "answer")
    try:
        user_uuid, session_uuid = uuid.UUID(str(user_id)), uuid.UUID(str(session_id))
    except ValueError as exc:
        raise ConversationSessionNotFound("Session not found") from exc
    query = select(ChatSession).where(ChatSession.id == session_uuid,
        ChatSession.user_id == user_uuid, ChatSession.workspace == workspace)
    if lock:
        query = query.with_for_update(nowait=True)
    try:
        session = (await db.execute(query)).scalar_one_or_none()
    except DBAPIError as exc:
        origin = getattr(exc, "orig", None)
        if getattr(origin, "sqlstate", None) == "55P03" or getattr(origin, "pgcode", None) == "55P03":
            raise SessionBusyError("This chat already has a response in progress.") from exc
        raise
    if session is None:
        raise ConversationSessionNotFound("Session not found")
    return session


async def _read_history(db: Any, session_id: str, limit: int) -> list[StoredConversationMessage]:
    result = await db.execute(select(ChatMessage).where(ChatMessage.session_id == uuid.UUID(str(session_id)))
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(max(1, min(limit, 100))))
    rows = list(reversed(result.scalars().all()))
    return [StoredConversationMessage(role="assistant" if row.sender == "oracle" else "user",
        content=row.content, created_at=row.created_at.isoformat() if row.created_at else "",
        metadata=getattr(row, "evidence_metadata", None) or {}) for row in rows]


async def conversation_history(user_id: str, session_id: str, *, db: Any,
                               workspace: str = "student", limit: int | None = None) -> list[StoredConversationMessage]:
    await require_session(db, user_id, session_id, workspace)
    return await _read_history(db, session_id, limit or 100)


async def clear_conversation(user_id: str, session_id: str, *, db: Any, workspace: str = "student") -> None:
    await require_session(db, user_id, session_id, workspace, lock=True)
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == uuid.UUID(str(session_id))))
    await db.flush()


def source_payload(chunk: Any) -> dict:
    return {"chunkId": chunk.chunk_id, "content": chunk.content, "score": float(chunk.score or 0),
            "documentId": chunk.document_id, "documentName": chunk.document_name, "page": chunk.page,
            "headingPath": list(chunk.heading_path) if getattr(chunk, "heading_path", None) else None,
            "section": getattr(chunk, "section", None), "elementType": getattr(chunk, "element_type", None),
            "retrievalPath": getattr(chunk, "retrieval_path", None), "fusionScore": getattr(chunk, "fusion_score", None),
            "structuralHops": getattr(chunk, "structural_hops", None), "evidenceKind": getattr(chunk, "evidence_kind", None),
            "tableElementId": getattr(chunk, "table_element_id", None), "rowIndex": getattr(chunk, "row_index", None),
            "knowledgeGraphPath": getattr(chunk, "knowledge_graph_path", None),
            "knowledgeGraphHops": getattr(chunk, "knowledge_graph_hops", None),
            "knowledgeGraphPredicate": getattr(chunk, "knowledge_graph_predicate", None),
            "knowledgeGraphQuote": getattr(chunk, "knowledge_graph_quote", None),
            "spatialRegions": getattr(chunk, "spatial_regions", None)}


async def stream_with_memory(db: Any, *, user_id: str, session_id: str, question: str,
                             top_k: int = 5, answer_format: AnswerFormat | str | int | None = None,
                             workspace: str = "student", task: str = "answer") -> AsyncIterator[dict]:
    """Events: meta, provisional delta, final (ConversationAnswer). Errors propagate."""
    from config import get_settings
    from generation.service import retrieve_evidence, verified_supported_claims
    from generation.verification import verify_with_mode

    started = time.perf_counter()
    workspace, task = validate_intent(workspace, task)
    question = question.strip()
    if not question or len(question) > 2000:
        raise ValueError("Question must contain 1 to 2000 characters.")
    if not 1 <= int(top_k) <= 20:
        raise ValueError("topK must be between 1 and 20.")
    fmt = AnswerFormat.coerce(answer_format)
    await require_session(db, user_id, session_id, workspace, lock=True)
    settings = get_settings()
    history = await _read_history(db, session_id, int(settings.conversation_history_limit))
    history_data = [m.as_dict() for m in history]
    query, resolved = resolve_followup(question, history_data)
    status = provider_status(settings)
    yield {"event": "meta", "data": {"provider": status["provider"], "model": status["model"],
        "hosted": status["hosted"], "fallbackConfigured": status.get("fallbackConfigured", False),
        "workspace": workspace, "provisional": True}}
    retrieval_started = time.perf_counter()
    chunks = await retrieve_evidence(db, user_id, query, top_k=top_k,
                                    answer_format=fmt if workspace == "student" else AnswerFormat.FIFTEEN,
                                    query_routing=True)
    graph_rag_status = getattr(chunks, "knowledge_graph_status", "not_reported")
    routing = getattr(chunks, "routing", {})
    spatial_status = getattr(chunks, "spatial_status", "not_reported")
    learned_visual = False
    chunks, rerank = select_evidence(query, chunks, diversify=workspace == "research")
    if routing.get("reranker"):
        rerank = {**rerank, **routing["reranker"], "selectionSignal": rerank["signal"],
                  "applied": routing["reranker"]["status"] == "ready",
                  "scored": routing["reranker"]["candidates"] if routing["reranker"]["status"] == "ready" else 0}
    retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)
    sources, blocks, warnings = [], [], []
    answer = ""
    model = status["model"]
    provider_used = status["provider"]
    hosted_used = status["hosted"]
    fallback_used = False
    first_token_ms = None
    abstained = not chunks
    verification = {"verified": False, "method": "lexical-attribution", "citationReferencesValid": False,
                    "note": "Lexical checks do not establish factual correctness or academic completeness."}
    finish_reason = ""
    if chunks:
        context_tokens = int(getattr(settings, "groq_context_tokens", 8192))
        prepared = prepare_prompt(question, chunks, history_data, workspace=workspace, task=task,
                                  answer_format=fmt, context_tokens=context_tokens)
        sources, blocks = prepared.sources, prepared.blocks
        learned_visual = any(getattr(chunk, "evidence_kind", "") == "visual_patch" for chunk in sources)
        warnings.extend(prepared.warnings)
        graph_source_count = sum(
            1 for source in sources if getattr(source, "knowledge_graph_path", None)
        )
        if graph_source_count:
            graph_rag_status = "used"
        elif graph_rag_status == "retrieved":
            graph_rag_status = "retrieved_not_in_prompt"
        if not blocks:
            abstained = True
            warnings.append("No usable evidence fits the configured context window.")
        else:
            extractive_fallback = False
            try:
                async for delta in stream_answer(prepared.messages, max_tokens=prepared.max_tokens, settings=settings):
                    model = delta.model or model
                    provider_used = getattr(delta, "provider", "") or provider_used
                    hosted_used = provider_used == "groq"
                    fallback_used = bool(getattr(delta, "fallback_used", False))
                    if delta.text:
                        if first_token_ms is None:
                            first_token_ms = int((time.perf_counter() - started) * 1000)
                        answer += delta.text
                    if delta.done:
                        finish_reason = delta.finish_reason
            except GenerationUnavailableError as exc:
                hosted_used = bool(getattr(exc, "hosted_attempted", hosted_used))
                fallback = _build_extractive_fallback(query, blocks, fmt.marks)
                if not fallback:
                    raise
                answer = fallback
                model = "extractive-evidence-fallback"
                extractive_fallback = True
                warnings.append("The configured answer model was unavailable; exact relevant excerpts from the retrieved sources are shown instead.")
            answer = answer.strip()
            abstained = not extractive_fallback and "INSUFFICIENT_EVIDENCE" in answer.upper()
            citations = {int(match) for match in _CITATION.findall(answer)}
            valid_citations = bool(citations) and citations <= {block.index for block in blocks}
            if not extractive_fallback and (abstained or not valid_citations):
                fallback = _build_extractive_fallback(query, blocks, fmt.marks)
                if fallback:
                    answer = fallback
                    abstained = False
                    extractive_fallback = True
                    model = "extractive-evidence-fallback"
                    warnings.append("The generated draft could not be safely grounded, so the answer uses exact relevant excerpts from the retrieved sources.")
                else:
                    abstained = True
                    warnings.append("The generated draft lacked usable evidence references, and no directly relevant source excerpts were available.")
            if not abstained:
                citations = {int(match) for match in _CITATION.findall(answer)}
                valid_citations = bool(citations) and citations <= {block.index for block in blocks}
                report = verify_with_mode(answer, blocks, question=question)
                if not report.verified and not extractive_fallback:
                    answer, report, omitted = verified_supported_claims(answer, blocks, question)
                    if omitted:
                        warnings.append("Claims that could not be supported by the supplied evidence were omitted; the remaining answer was checked again.")
                if not report.verified and not extractive_fallback:
                    fallback = _build_extractive_fallback(query, blocks, fmt.marks)
                    if fallback:
                        answer = fallback
                        extractive_fallback = True
                        model = "extractive-evidence-fallback"
                        warnings.append("The generated draft contained claims the verifier could not support; it was replaced with exact relevant excerpts from the retrieved sources.")
                        citations = {int(match) for match in _CITATION.findall(answer)}
                        valid_citations = bool(citations) and citations <= {block.index for block in blocks}
                        report = verify_with_mode(answer, blocks, question=question)
                if not report.verified or not valid_citations:
                    abstained = True
                    warnings.append("The available evidence excerpts did not pass answer verification; the answer was withheld.")
                verification = {**report.summary(), "method": "extractive-source-excerpts" if extractive_fallback else "lexical-attribution",
                    "citationReferencesValid": valid_citations,
                    "note": "The extractive fallback quotes supplied source text. Generated answers use lexical support checks, which are not a guarantee of factual correctness."}
                if not report.verified:
                    warnings.append("Some claims could not be confirmed by lexical evidence checks. Review the sources before relying on this answer.")
                if finish_reason in ("length", "max_tokens"):
                    warnings.append("The provider reached its output limit; this answer may be incomplete.")
    if abstained:
        answer = "I don't have enough supported evidence to answer this reliably. Try a more specific question or add relevant documents."
    if graph_rag_status == "unavailable":
        warnings.append("Entity-relation graph retrieval was unavailable; this answer used the available dense and document-structure evidence only.")
    elif graph_rag_status == "available_no_match":
        warnings.append("No exact query-entity match was found in the entity-relation graph; dense and document-structure evidence was used.")
    elif graph_rag_status == "pending":
        warnings.append("Entity-relation extraction is still pending for this account's documents; dense and document-structure evidence was used.")
    elif graph_rag_status == "empty":
        warnings.append("No entity-relation graph has been built for this account's documents yet; dense and document-structure evidence was used.")
    if hosted_used:
        warnings.append("Groq was used or attempted for this answer; the provider request includes supplied evidence and bounded conversation context.")
    if fallback_used:
        warnings.append("Local Ollama inference failed or timed out; Groq generated the replacement draft.")
    if routing.get("hosted"):
        warnings.append("The query router used or attempted Groq to classify this question; routing sends the question, not document passages.")
    latency_ms = int((time.perf_counter() - started) * 1000)
    metadata = {"sources": [source_payload(chunk) for chunk in sources], "verification": verification,
                "engine": provider_used, "model": model, "workspace": workspace, "task": task,
                "marks": fmt.marks if workspace == "student" else 0, "warnings": warnings,
                "insufficientContext": abstained, "abstained": abstained, "latencyMs": latency_ms,
                "firstTokenMs": first_token_ms, "fallbackUsed": fallback_used,
                "retrievalRouting": routing, "spatialContext": {"status": spatial_status, "learnedVisualEmbeddings": learned_visual},
                "knowledgeGraph": {"status": graph_rag_status, "maxHops": 3,
                                   "sourceCountInPrompt": sum(1 for source in sources
                                       if getattr(source, "knowledge_graph_path", None))}}
    created = datetime.now(timezone.utc)
    user_message = ChatMessage(session_id=uuid.UUID(str(session_id)), sender="user", content=question, created_at=created)
    assistant_message = ChatMessage(session_id=uuid.UUID(str(session_id)), sender="oracle", content=answer, created_at=created + timedelta(microseconds=1))
    if hasattr(ChatMessage, "evidence_metadata"):
        assistant_message.evidence_metadata = metadata
    db.add_all([user_message, assistant_message])
    await db.flush()
    history = await _read_history(db, session_id, max(12, int(settings.conversation_history_limit)))
    from reliability.routes import store_query_reliability
    scores = [float(getattr(chunk, "score", 0) or 0) for chunk in sources]
    await store_query_reliability(user_id, {"question": question, "answer": answer,
        "retrievalScore": max(scores, default=0), "avgRetrievalScore": sum(scores) / len(scores) if scores else 0,
        "sourceCount": len(sources), "uniqueDocuments": len({s.document_id for s in sources}),
        "factualGrounded": False, "insufficientContext": abstained,
        "sources": [{"id": s.chunk_id, "documentId": s.document_id, "documentName": s.document_name,
                     "content": s.content, "page": s.page, "relevanceScore": s.score, "status": "UNVERIFIED"} for s in sources],
        "generation": metadata, "pipelineVersion": PIPELINE_VERSION}, db=db)
    result = ConversationAnswer(session_id=str(session_id), question=question, retrieval_query=query,
        followup_resolved=resolved, answer=answer, engine=provider_used, model=model,
        marks=fmt.marks if workspace == "student" else 0, verification=verification, warnings=warnings,
        sources=sources, history=[m.as_dict() for m in history], rerank=rerank,
        insufficient_context=abstained, abstained=abstained, latency_ms=latency_ms,
        workspace=workspace, task=task, first_token_ms=first_token_ms, hosted=hosted_used or bool(routing.get("hosted")),
        timings={"retrievalMs": retrieval_ms, "routingMs": routing.get("latencyMs", 0),
                 "firstTokenMs": first_token_ms, "totalMs": latency_ms})
    # Do not expose unverified provider text to the chat or voice client. The
    # validated answer is emitted as one final delta; token-level streaming
    # would leak hallucinated claims before the evidence gate can run.
    if not abstained:
        yield {"event": "delta", "data": {"text": answer, "provisional": False}}
    yield {"event": "final", "data": result}


async def answer_with_memory(db: Any, **kwargs) -> ConversationAnswer:
    async for event in stream_with_memory(db, **kwargs):
        if event["event"] == "final":
            return event["data"]
    raise GenerationUnavailableError("The conversation ended without a final answer.")


async def conversation_status() -> dict:
    return {"memory": {"backend": "postgresql", "available": None, "error": None},
            "conversationModel": provider_status(), "pipelineVersion": PIPELINE_VERSION}


__all__ = ["ConversationAnswer", "ConversationSessionNotFound", "SessionBusyError", "PIPELINE_VERSION",
           "answer_with_memory", "stream_with_memory", "require_session", "conversation_history",
           "clear_conversation", "conversation_status", "source_payload"]
