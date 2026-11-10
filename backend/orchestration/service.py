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
from generation.provider_prompt import (
    asks_for_diagram, extract_student_evidence_gaps, prepare_prompt, select_evidence,
    student_question_plan, validate_intent,
)
from generation.planning import _with_citation, filter_text_diagrams
from generation.providers import provider_status, stream_answer
from generation.topic_context import select_topic_heading_path
from generation.types import AnswerFormat, EvidenceBlock, GenerationUnavailableError
from generation.verification import content_tokens, split_sentences
from orchestration.followup import resolve_followup
from session.store import ConversationMessage

PIPELINE_VERSION = "visual-spatial-dual-path-v3"
_CITATION = re.compile(r"\[(\d+)\]")


def _build_extractive_fallback(question: str, blocks: list[EvidenceBlock], marks: int) -> str:
    """Build a cited answer from exact retrieved sentences when synthesis fails.

    The provider may omit references or add unsupported details. In that
    case, quote only complete sentences that occur verbatim (whitespace
    normalized) in retrieved evidence, including a bounded same-source
    continuation when concrete terms connect it to a question match. Persisted
    source headings also anchor steps split into separate topic passages.
    This fallback is intentionally extractive; it does not turn lexical overlap
    into a factual paraphrase.
    """
    terms = set(content_tokens(question))
    if not terms:
        return ""
    command_words = {"explain", "describe", "define", "discuss", "compare", "evaluate",
                     "what", "which", "how", "why", "with", "illustrate", "list"}
    _, parts = student_question_plan(question)
    part_terms = [set(content_tokens(part)) - command_words for part in parts]
    capitalized_terms = {
        token.casefold() for token in re.findall(r"\b[A-Z][a-z0-9]+\b", question)
        if token.casefold() in terms and token.casefold() not in command_words
    }
    focus_terms = set().union(*part_terms) if part_terms else capitalized_terms or terms
    limit = {5: 6, 10: 10, 15: 14}.get(marks, 10)
    candidates: list[tuple[int, int, int, str]] = []
    metadata = re.compile(r"\b(?:report id|revision|document pages)\b", re.IGNORECASE)
    for block_rank, block in enumerate(blocks):
        source = re.sub(r"\s+", " ", block.content).strip()
        raw_sentences = split_sentences(block.content)
        # Expanded working steps keep their own citations and may not repeat
        # the topic name in the body. Their persisted matching heading anchors
        # relevance without inventing a relationship between independent blocks.
        heading = select_topic_heading_path(
            question, block.heading_path or ((block.section,) if block.section else ()),
        )
        heading_overlap = len(focus_terms & set(content_tokens(" ".join(heading))))
        anchors: set[int] = set()
        for sentence_rank, raw_sentence in enumerate(raw_sentences):
            sentence = re.sub(r"\s+", " ", raw_sentence).strip()
            if len(sentence) < 45 or not re.search(r"[.!?]$", sentence) or metadata.search(sentence):
                continue
            overlap = max(heading_overlap, len(focus_terms & set(content_tokens(sentence))))
            if not overlap:
                continue
            if sentence not in source:
                continue
            anchors.add(sentence_rank)
            candidates.append((-overlap, block_rank, sentence_rank,
                               f"- {_with_citation(sentence, block.index)}"))
        # A process can continue after the last question-term match: "wind
        # turns a rotor. The rotor drives a shaft. The shaft drives a generator."
        # ponytail: concrete shared terms are a relevance heuristic, not an
        # entailment model. Keep at most two adjacent continuation sentences
        # from this source; never invent a link or bridge separate documents.
        generic = {"system", "process", "component", "operation", "energy", "unit", "document", "report"}
        def link_terms(value: str) -> set[str]:
            return {token.strip(".,;:!?/") for token in content_tokens(value)
                    if len(token.strip(".,;:!?/")) >= 4} - generic

        for anchor_rank in sorted(anchors):
            priority = -len(focus_terms & set(content_tokens(raw_sentences[anchor_rank])))
            for sentence_rank in range(anchor_rank + 1, min(anchor_rank + 3, len(raw_sentences))):
                if sentence_rank in anchors:
                    break
                sentence = re.sub(r"\s+", " ", raw_sentences[sentence_rank]).strip()
                if (len(sentence) < 45 or not re.search(r"[.!?]$", sentence) or metadata.search(sentence)
                        or sentence not in source or not (link_terms(sentence) & link_terms(raw_sentences[sentence_rank - 1]))):
                    break
                candidates.append((priority, block_rank, sentence_rank, f"- {_with_citation(sentence, block.index)}"))
    candidates.sort(key=lambda item: item[:3])
    # Give each explicitly requested part a relevant excerpt before allocating
    # the remaining capacity; many hits for part (a) must not crowd out part (b).
    promoted = []
    for terms_for_part in part_terms:
        if not candidates or not terms_for_part:
            continue
        best = max(range(len(candidates)), key=lambda i: len(terms_for_part & set(content_tokens(candidates[i][3]))))
        if terms_for_part & set(content_tokens(candidates[best][3])):
            promoted.append(candidates.pop(best))
    candidates = promoted + candidates
    selected: list[str] = []
    selected_order: list[tuple[int, int]] = []
    seen: dict[str, int] = {}
    for _, block_rank, sentence_rank, excerpt in candidates:
        # Citations differ between sources even when the quoted sentence is
        # identical. Deduplicate the text, while keeping each source reference.
        sentence_text = _CITATION.sub("", excerpt)
        fingerprint = re.sub(r"\W+", " ", sentence_text.casefold()).strip()
        if fingerprint in seen:
            index = seen[fingerprint]
            citation = _CITATION.search(excerpt)
            if citation:
                existing = {f"[{number}]" for number in _CITATION.findall(selected[index])}
                if citation.group() not in existing:
                    selected[index] = _with_citation(selected[index], int(citation.group(1)))
            continue
        if len(selected) >= limit:
            continue
        seen[fingerprint] = len(selected)
        selected.append(excerpt)
        selected_order.append((block_rank, sentence_rank))
    return "\n".join(item for _, item in sorted(zip(selected_order, selected)))


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
            "tokenCount": getattr(chunk, "token_count", None), "chunkerVersion": getattr(chunk, "chunker_version", None),
            "retrievalPath": getattr(chunk, "retrieval_path", None), "fusionScore": getattr(chunk, "fusion_score", None),
            "structuralHops": getattr(chunk, "structural_hops", None), "evidenceKind": getattr(chunk, "evidence_kind", None),
            "tableElementId": getattr(chunk, "table_element_id", None), "rowIndex": getattr(chunk, "row_index", None),
            "headerRepeated": getattr(chunk, "header_repeated", None),
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
    student_answer = workspace == "student" and task in ("answer", "explain")
    diagram_requested = student_answer and asks_for_diagram(question)
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
            if student_answer and not extractive_fallback:
                answer, gap_notes = extract_student_evidence_gaps(answer, question)
                warnings.extend(gap_notes)
            if diagram_requested:
                answer, kept_diagrams, omitted_diagrams = filter_text_diagrams(
                    answer, blocks, question=question
                )
                if omitted_diagrams:
                    warnings.append(
                        f"{omitted_diagrams} diagram figure(s) were omitted because they were malformed, "
                        "uncited, or unsupported by the supplied evidence."
                    )
                if not kept_diagrams:
                    warnings.append(
                        "The question requested a diagram, but the draft contained no evidence-supported figure."
                    )
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
                if extractive_fallback:
                    warnings.append("These excerpts may not cover every required step or detail; review the source passages.")
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
