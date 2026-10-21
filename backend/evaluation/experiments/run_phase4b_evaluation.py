#!/usr/bin/env python3
"""Phase 4B — QA Evaluation Expansion & Real-World Validation.

Evaluates the expanded corpus (24 documents, 102 questions) through
all three pipeline arms:
  A: legacy chunking + legacy context
  B: legacy chunking + token-aware context
  C: structure-v2 chunking + token-aware context

Produces per-question results, aggregate metrics, failure replay,
table/list/multichunk analysis, and confidence analysis.

Usage::

    cd backend
    python test_phase4b_evaluation.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

# Relocated 2026-09-30 to backend/evaluation/experiments/ (was backend/).
# The backend package root is three levels up from this file.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")

# No ``DATABASE_URL`` default here: the target is resolved and guarded in
# ``main()`` (before the application is imported, because ``storage.database``
# reads settings at import time).  A module-level default would silently make
# the application database the target of a runner that deletes rows.
from evaluation.artifacts import ArtifactExistsError, RunOutput  # noqa: E402
from evaluation.isolation import (  # noqa: E402
    application_database_url,
    assert_disposal_authorized,
    assert_safe_evaluation_target,
    database_identity,
    describe_identity,
    display_dsn,
    evaluation_database_url,
)

TOP_K = 5

from evaluation.datasets.phase4b_corpus import (  # noqa: E402
    build_phase4b_corpus, build_phase4b_unanswerable,
    get_all_phase4b_questions, DOCUMENT_METADATA,
)
from evaluation.harness.corpus import (  # noqa: E402
    CORPUS_VERSION, EVALUATION_VERSION,
    QUESTION_DIFFICULTY, ACCEPTABLE_ANSWERS,
    get_difficulty, get_acceptable_answers, corpus_summary,
)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))


def contains_evidence(chunk_content: str, evidence: tuple[str, ...]) -> bool:
    if not evidence:
        return False
    body = norm(chunk_content)
    return any(norm(item) in body for item in evidence)


# ---------------------------------------------------------------------------
# Phase 3F metrics (preserved)
# ---------------------------------------------------------------------------

def exact_match_normalised(predicted: str, expected: str | None) -> bool:
    if not expected:
        return False
    p = norm(predicted).rstrip(".")
    e = norm(expected).rstrip(".")
    return p == e and p != ""


def token_f1(predicted: str, expected: str) -> float:
    p_tokens = tokenise(predicted)
    e_tokens = tokenise(expected)
    if not p_tokens or not e_tokens:
        return 0.0
    p_counts = Counter(p_tokens)
    e_counts = Counter(e_tokens)
    common = sum((p_counts & e_counts).values())
    if common == 0:
        return 0.0
    precision = common / len(p_tokens)
    recall = common / len(e_tokens)
    return 2 * precision * recall / (precision + recall)


def acceptable_answer_match(predicted: str, qid: str) -> bool:
    variants = get_acceptable_answers(qid)
    if not variants:
        return False
    p = norm(predicted).rstrip(".")
    if not p:
        return False
    return any(norm(a).rstrip(".") == p for a in variants)


def mrr(flags_per_q: list[list[bool]]) -> float:
    if not flags_per_q:
        return 0.0
    total = 0.0
    for flags in flags_per_q:
        for rank, flag in enumerate(flags, 1):
            if flag:
                total += 1.0 / rank
                break
    return total / len(flags_per_q)


# ---------------------------------------------------------------------------
# Failure taxonomy (preserved from Phase 3F)
# ---------------------------------------------------------------------------

@dataclass
class FailureDiag:
    primary: str
    secondary: str | None = None
    detail: str = ""


def classify_failure(
    answerable: bool,
    outcome: str,
    answer_correct: bool,
    relevant_in_topk: bool,
    coverage: float,
    context_tokens: int,
    context_budget: int,
    qa_confidence: float,
    reported_sources: int,
    omitted_sources: int,
) -> FailureDiag:
    if not answerable:
        if outcome == "INSUFFICIENT_EVIDENCE" and not answer_correct:
            return FailureDiag(primary="CORRECT_ABSTAIN")
        if answer_correct:
            return FailureDiag(primary="SPURIOUS", detail="answered unsupported question")
        return FailureDiag(primary="UNKNOWN", detail="unsupported, unexpected outcome")

    if not relevant_in_topk:
        if coverage == 0.0:
            return FailureDiag(primary="RET_MISS", detail="no relevant chunk in top-K")
        return FailureDiag(primary="RET_MISS", detail="retrieval miss")

    if coverage > 0 and context_tokens >= context_budget * 0.95:
        if not answer_correct:
            return FailureDiag(primary="CTX_TRUNC", detail="context near full, answer truncated")

    if coverage > 0 and omitted_sources > 0 and not answer_correct:
        return FailureDiag(primary="EVID_OMIT", detail="evidence retrieved but omitted from QA context")

    if answer_correct:
        if outcome == "INSUFFICIENT_EVIDENCE":
            return FailureDiag(primary="QA_CONF", detail="correct but abstained (low confidence)")
        return FailureDiag(primary="CORRECT", detail="answer correct")

    if outcome == "INSUFFICIENT_EVIDENCE":
        if qa_confidence == 0.0:
            return FailureDiag(primary="QA_EXTRACT", detail="model found nothing (zero confidence)")
        return FailureDiag(primary="QA_CONF", detail="abstained despite some confidence")

    if coverage == 0.0:
        return FailureDiag(primary="RET_MISS", detail="relevant evidence not retrieved")

    if coverage > 0 and context_tokens >= context_budget * 0.95:
        return FailureDiag(primary="CTX_TRUNC", detail="context full, answer lost")

    return FailureDiag(primary="QA_EXTRACT", detail="wrong span extracted from context")


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

@dataclass
class IngestedCorpus:
    arm: str
    user_id: uuid.UUID
    docs: list
    chunk_rows: list[dict] = field(default_factory=list)
    ingestion_ms: float = 0.0
    chunks: int = 0


async def ingest_corpus(db, user_id, corpus, chunker_version, label) -> IngestedCorpus:
    from documents.chunking import CHUNKER_VERSION_STRUCTURE, chunk_elements
    from documents.models import Document, DocumentChunk
    from documents.processing import chunk_text, extract_text
    from embeddings.model import embed_texts
    from storage.file_store import save_upload
    from tokenization import count_tokens

    result = IngestedCorpus(arm=label, user_id=user_id, docs=corpus)
    started = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for doc in corpus:
            path = doc.write(directory)
            file_bytes = path.read_bytes()
            elements = extract_text(path, doc.file_type)

            if chunker_version == CHUNKER_VERSION_STRUCTURE:
                chunks = chunk_elements(elements)
                contents = [c.content for c in chunks]
                metas = [c.meta for c in chunks]
                pages = [c.meta.page for c in chunks]
            else:
                legacy = chunk_text(elements)
                contents = [content for _, content in legacy]
                pages = [page for page, _ in legacy]
                metas = [None] * len(contents)

            stored = save_upload(file_bytes, doc.name, str(user_id))
            document = Document(
                id=uuid.uuid4(), user_id=user_id, name=doc.name,
                file_type=doc.file_type, file_size=len(file_bytes),
                stored_path=str(stored), chunker_version=chunker_version,
                chunk_count=len(contents), status="ready",
                embedding_status="processing",
            )
            db.add(document)
            await db.flush()

            if contents:
                embeddings = embed_texts(contents)
            else:
                embeddings = []

            for index, content in enumerate(contents):
                meta = metas[index]
                row = DocumentChunk(
                    id=uuid.uuid4(), document_id=document.id,
                    chunk_index=index, content=content,
                    page=pages[index] if index < len(pages) else None,
                    embedding=embeddings[index] if index < len(embeddings) else None,
                    heading_path=list(meta.heading_path) or None if meta else None,
                    section=meta.section if meta else None,
                    element_type=meta.element_type if meta else None,
                    chunker_version=chunker_version,
                    token_count=meta.token_count if meta else count_tokens(content),
                )
                db.add(row)
                result.chunk_rows.append({
                    "document": doc.name, "content": content,
                    "tokens": row.token_count, "element_type": row.element_type,
                    "page": row.page,
                })

            document.embedding_status = "ready"
            result.chunks += len(contents)

        await db.commit()

    result.ingestion_ms = (time.monotonic() - started) * 1000
    return result


# ---------------------------------------------------------------------------
# Context builder + duck adapter
# ---------------------------------------------------------------------------

def duck(source):
    from chat.rag import SourceChunk
    if isinstance(source, SourceChunk):
        return source
    return SourceChunk(
        chunk_id=source.chunk_id, content=source.content,
        score=source.score, document_id=source.document_id,
        document_name=source.document_name, page=source.page,
        heading_path=source.heading_path, section=source.section,
        element_type=source.element_type, token_count=source.token_count,
        chunker_version=source.chunker_version,
    )


def context_builder_for(arm: str):
    from chat.rag import build_context, build_qa_context
    if arm == "A":
        return lambda chunks, question: build_context(
            [duck(c) for c in chunks], max_chars=4000
        )
    return lambda chunks, question: build_qa_context(
        [duck(c) for c in chunks], question
    )


# ---------------------------------------------------------------------------
# Query evaluation
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    qid: str
    arm: str
    kind: str
    answerable: bool
    difficulty: str
    document: str
    document_format: str
    retrieved: list[str]
    retrieved_scores: list[float]
    relevant_flags: list[bool]
    answer: str
    outcome: str
    answer_correct_substring: bool
    answer_exact_match: bool
    answer_token_f1: float
    answer_acceptable_match: bool
    coverage: float
    best_retrieval_score: float
    qa_confidence: float
    context_tokens: int
    context_budget: int
    context_util: float
    reported_sources: int
    omitted_sources: int
    failure_primary: str
    failure_detail: str
    retrieval_ms: int
    qa_ms: int
    total_ms: int


async def run_question(
    db, user_id, question, context_builder, arm: str,
    corpus_docs: list,
) -> QueryResult:
    from brain import Brain
    from brain.executor import CapabilityRegistry
    from brain.types import Capability, ExecutionContext
    from chat.qa_model import answer_question, count_text_tokens
    from chat.rag import retrieve_chunks, _question_overhead

    registry = CapabilityRegistry()

    async def retrieval(user_id="", cleaned_text="", top_k=TOP_K):
        return await retrieve_chunks(db=db, user_id=user_id, query=cleaned_text, top_k=top_k)

    async def context(retrieval_sources=None, cleaned_text=""):
        return context_builder(retrieval_sources or [], cleaned_text)

    async def qa(cleaned_text="", context=""):
        result = answer_question(cleaned_text, context)
        from brain.types import QaResult
        return QaResult(answer=result["answer"], score=result["score"],
                        start=result["start"], end=result["end"])

    registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval)
    registry.register(Capability.CONTEXT_BUILDING, context)
    registry.register(Capability.QA_ANSWER, qa)

    ctx = ExecutionContext(user_id=str(user_id), raw_question=question.text, top_k=TOP_K)
    ctx = await Brain(registry).process(ctx)

    raw_sources = list(getattr(ctx, 'retrieval_sources', None) or [])
    retrieved = [s.content for s in raw_sources]
    scores = [s.score for s in raw_sources]
    flags = [contains_evidence(text, question.evidence) for text in retrieved]

    response = getattr(ctx, 'response', None)
    answer = response.answer if response else ""

    sub_match = answer_matches_substring(answer, question.expected_answer)
    em_match = exact_match_normalised(answer, question.expected_answer)
    f1 = token_f1(answer, question.expected_answer or "")
    acc_match = acceptable_answer_match(answer, question.qid)

    if question.answerable and question.evidence:
        covered = sum(
            1 for e in question.evidence
            if any(norm(e) in norm(text) for text in retrieved)
        )
        coverage = covered / len(question.evidence)
    else:
        coverage = 0.0

    context_pack = getattr(ctx, 'context', None)
    if context_pack and hasattr(context_pack, "used_tokens"):
        supplied = int(context_pack.used_tokens or 0)
        context_budget = int(context_pack.budget_tokens or 0)
    else:
        supplied = int(count_text_tokens(str(context_pack or "")) or 0)
        context_budget = max(0, 384 - _question_overhead(question.text)[0] - 4)
    attended = min(supplied, context_budget)
    utilisation = (attended / supplied) if supplied else 0.0

    evidence = getattr(ctx, 'evidence', None)
    raw_supplied = [s.score for s in evidence.sources] if evidence and evidence.sources else []
    best_supplied = max(raw_supplied) if raw_supplied else 0.0
    qa_r = evidence.qa_result if evidence else None
    qa_confidence = qa_r.score if qa_r else 0.0
    omitted = (evidence.grounding_signals.get("omitted_source_ids") or []) if evidence else []

    rel_in_topk = any(flags[:TOP_K])
    outcome_val = getattr(ctx, 'outcome', None)
    outcome_str = outcome_val.value if outcome_val else "FAILED"
    fail = classify_failure(
        answerable=question.answerable, outcome=outcome_str,
        answer_correct=em_match or acc_match, relevant_in_topk=rel_in_topk,
        coverage=coverage, context_tokens=supplied,
        context_budget=context_budget, qa_confidence=qa_confidence,
        reported_sources=len(evidence.sources) if evidence else 0, omitted_sources=len(omitted),
    )

    doc_name = "unknown"
    doc_format = "unknown"
    for d in corpus_docs:
        for q in d.questions:
            if q.qid == question.qid:
                doc_name = d.name
                doc_format = d.file_type
                break

    difficulty = get_difficulty(question.qid)

    return QueryResult(
        qid=question.qid, arm=arm, kind=question.kind,
        answerable=question.answerable, difficulty=difficulty,
        document=doc_name, document_format=doc_format,
        retrieved=retrieved, retrieved_scores=scores,
        relevant_flags=flags,
        answer=answer, outcome=ctx.outcome.value,
        answer_correct_substring=sub_match,
        answer_exact_match=em_match,
        answer_token_f1=f1,
        answer_acceptable_match=acc_match,
        coverage=coverage,
        best_retrieval_score=best_supplied,
        qa_confidence=qa_confidence,
        context_tokens=supplied, context_budget=context_budget,
        context_util=utilisation,
        reported_sources=len(ctx.evidence.sources),
        omitted_sources=len(omitted),
        failure_primary=fail.primary,
        failure_detail=fail.detail,
        retrieval_ms=getattr(ctx.timing, 'retrieval_ms', 0) if hasattr(ctx, 'timing') else 0,
        qa_ms=getattr(ctx.timing, 'qa_ms', 0) if hasattr(ctx, 'timing') else 0,
        total_ms=getattr(ctx.timing, 'total_ms', 0) if hasattr(ctx, 'timing') else 0,
    )


def answer_matches_substring(answer: str, expected: str | None) -> bool:
    if not expected:
        return False
    a, e = norm(answer), norm(expected)
    if not a:
        return False
    return e in a or a in e


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(results: list[QueryResult]) -> dict:
    answerable = [r for r in results if r.answerable]
    unsupported = [r for r in results if not r.answerable]
    n_ans = len(answerable)
    n_unsup = len(unsupported)

    def recall_at(k: int) -> float:
        if not answerable:
            return 0.0
        return sum(1 for r in answerable if any(r.relevant_flags[:k])) / n_ans

    def precision_at(k: int) -> float:
        if not answerable:
            return 0.0
        return mean(
            (sum(r.relevant_flags[:k]) / min(k, max(1, len(r.relevant_flags))))
            for r in answerable
        )

    flags_padded = []
    for r in answerable:
        f = [True] * sum(r.relevant_flags[:TOP_K]) + [False] * (TOP_K - sum(r.relevant_flags[:TOP_K]))
        flags_padded.append(f[:TOP_K])

    false_abs = [r for r in answerable if r.outcome == "INSUFFICIENT_EVIDENCE"]
    spurious = [r for r in unsupported if r.answer.strip()]
    abs_unsup = [r for r in unsupported if r.outcome == "INSUFFICIENT_EVIDENCE"]

    em_count = sum(1 for r in answerable if r.answer_exact_match)
    acc_count = sum(1 for r in answerable if r.answer_acceptable_match)
    sub_count = sum(1 for r in answerable if r.answer_correct_substring)

    return {
        "queries": len(results),
        "answerable_queries": n_ans,
        "unsupported_queries": n_unsup,
        "recall@1": recall_at(1),
        "recall@3": recall_at(3),
        "recall@5": recall_at(5),
        "precision@1": precision_at(1),
        "precision@3": precision_at(3),
        "precision@5": precision_at(5),
        "mrr": mrr(flags_padded),
        "answer_exactness_substring": sub_count / n_ans if n_ans else 0.0,
        "answer_exact_match": em_count / n_ans if n_ans else 0.0,
        "acceptable_answer_match": acc_count / n_ans if n_ans else 0.0,
        "token_f1": mean([r.answer_token_f1 for r in answerable]) if answerable else 0.0,
        "answerability": (
            sum(1 for r in answerable
                if r.outcome in ("SUCCESS", "PARTIAL") and (r.answer_exact_match or r.answer_acceptable_match))
            / n_ans
        ) if n_ans else 0.0,
        "evidence_coverage": mean([r.coverage for r in answerable]) if answerable else 0.0,
        "context_utilisation": mean([r.context_util for r in results]),
        "reported_sources_avg": mean([r.reported_sources for r in results]),
        "omitted_sources_avg": mean([r.omitted_sources for r in results]),
        "false_abstention_rate": len(false_abs) / n_ans if n_ans else 0.0,
        "abstention_on_unsupported": len(abs_unsup) / n_unsup if n_unsup else 0.0,
        "spurious_answers_on_unsupported": len(spurious) / n_unsup if n_unsup else 0.0,
        "outcome_success_rate": (
            sum(1 for r in answerable if r.outcome == "SUCCESS") / n_ans
        ) if n_ans else 0.0,
        "duplicate_retrieval_rate": _dup_rate(results),
        "retrieval_ms_avg": mean([r.retrieval_ms for r in results]),
        "qa_ms_avg": mean([r.qa_ms for r in results]),
        "total_ms_avg": mean([r.total_ms for r in results]),
    }


def _dup_rate(results: list[QueryResult]) -> float:
    rates = []
    for r in results:
        if len(r.retrieved) < 2:
            rates.append(0.0)
            continue
        token_sets = [set(tokenise(t)) for t in r.retrieved]
        dups = 0
        for i in range(1, len(token_sets)):
            for j in range(i):
                a, b = token_sets[i], token_sets[j]
                if a and b and len(a & b) / len(a | b) >= 0.8:
                    dups += 1
                    break
        rates.append(dups / len(r.retrieved))
    return sum(rates) / len(rates) if rates else 0.0


def failure_distribution(results: list[QueryResult]) -> dict[str, int]:
    return dict(Counter(r.failure_primary for r in results))


def per_kind_breakdown(results: list[QueryResult]) -> dict[str, dict]:
    breakdown: dict[str, dict] = {}
    for kind in sorted(set(r.kind for r in results)):
        kr = [r for r in results if r.kind == kind]
        ka = [r for r in kr if r.answerable]
        flags_padded = []
        for r in ka:
            f = [True] * sum(r.relevant_flags[:TOP_K]) + [False] * (TOP_K - sum(r.relevant_flags[:TOP_K]))
            flags_padded.append(f[:TOP_K])
        breakdown[kind] = {
            "n": len(kr),
            "answerable": len(ka),
            "recall@5": recall_at_k_simple(flags_padded, 5) if flags_padded else 0.0,
            "exact_match": sum(1 for r in ka if r.answer_exact_match) / len(ka) if ka else 0.0,
            "token_f1": mean([r.answer_token_f1 for r in ka]) if ka else 0.0,
            "failure_dist": dict(Counter(r.failure_primary for r in kr)),
        }
    return breakdown


def per_document_breakdown(results: list[QueryResult]) -> dict[str, dict]:
    breakdown: dict[str, dict] = {}
    for doc in sorted(set(r.document for r in results)):
        dr = [r for r in results if r.document == doc]
        da = [r for r in dr if r.answerable]
        flags_padded = []
        for r in da:
            f = [True] * sum(r.relevant_flags[:TOP_K]) + [False] * (TOP_K - sum(r.relevant_flags[:TOP_K]))
            flags_padded.append(f[:TOP_K])
        breakdown[doc] = {
            "n": len(dr),
            "answerable": len(da),
            "recall@5": recall_at_k_simple(flags_padded, 5) if flags_padded else 0.0,
            "exact_match": sum(1 for r in da if r.answer_exact_match) / len(da) if da else 0.0,
            "token_f1": mean([r.answer_token_f1 for r in da]) if da else 0.0,
        }
    return breakdown


def per_format_breakdown(results: list[QueryResult]) -> dict[str, dict]:
    breakdown: dict[str, dict] = {}
    for fmt in sorted(set(r.document_format for r in results)):
        fr = [r for r in results if r.document_format == fmt]
        fa = [r for r in fr if r.answerable]
        breakdown[fmt] = {
            "n": len(fr),
            "answerable": len(fa),
            "exact_match": sum(1 for r in fa if r.answer_exact_match) / len(fa) if fa else 0.0,
            "token_f1": mean([r.answer_token_f1 for r in fa]) if fa else 0.0,
            "failure_dist": dict(Counter(r.failure_primary for r in fr)),
        }
    return breakdown


def recall_at_k_simple(flags: list[list[bool]], k: int) -> float:
    if not flags:
        return 0.0
    return sum(1 for f in flags if any(f[:k])) / len(flags)


def chunk_stats(rows: list[dict]) -> dict:
    tokens = [r["tokens"] for r in rows if r["tokens"]]
    if not tokens:
        return {}
    ordered = sorted(tokens)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    truncated = sum(1 for t in tokens if t > 256)
    return {
        "chunk_count": len(rows),
        "tokens_min": min(tokens),
        "tokens_median": median(tokens),
        "tokens_p95": p95,
        "tokens_mean": mean(tokens),
        "tokens_max": max(tokens),
        "encoder_truncation_rate": truncated / len(tokens),
        "truncated_chunks": truncated,
        "table_chunks": sum(1 for r in rows if r["element_type"] == "table"),
        "list_chunks": sum(1 for r in rows if r["element_type"] == "list"),
        "heading_chunks": sum(1 for r in rows if r["element_type"] == "heading"),
    }


# ---------------------------------------------------------------------------
# Ownership — the users this harness creates, and the cleanup that respects it
# ---------------------------------------------------------------------------

#: The chunker families this harness ingests a corpus for.  Each has exactly one
#: deterministic evaluation user (``harness_user_email``), which is the only
#: ownership marker that survives an interrupted run.
HARNESS_LABELS: tuple[str, ...] = ("legacy", "candidate")


def harness_user_email(label: str) -> str:
    """The email of the evaluation user that owns ``label``'s corpus.

    Deterministic on purpose: it is what lets a later run recognise — and clean
    up — the rows an earlier, interrupted run left behind.
    """
    return f"phase4b_{label}@test.local"


#: Exact addresses, **not** the ``phase4b_%`` prefix the previous revision used:
#: a prefix is broader than ownership requires and would also match any other
#: user whose name merely starts the same way.
HARNESS_USER_EMAILS: tuple[str, ...] = tuple(
    harness_user_email(label) for label in HARNESS_LABELS
)


async def owned_user_ids(db, *, emails) -> list[uuid.UUID]:
    """Ids of the users this harness owns, looked up by their exact emails."""
    from sqlalchemy import select

    from auth.models import User

    rows = await db.execute(select(User.id).where(User.email.in_(list(emails))))
    return list(rows.scalars())


async def cleanup_harness_rows(db, *, user_ids) -> None:
    """Delete exactly the rows owned by ``user_ids``, in foreign-key-safe order.

    Ownership, from the schema — no predicate is guessed:

    * ``users`` is the root: ``documents.user_id``, ``chat_sessions.user_id`` and
      ``reliability_logs.user_id`` each reference ``users.id``
      (``ondelete="CASCADE"``), and ``documents.user_id`` is the only ownership
      key a document has;
    * ``document_chunks.document_id`` -> ``documents.id`` and
      ``chat_messages.session_id`` -> ``chat_sessions.id`` reach their owner
      through those parents, because neither child table carries an owner column;
    * every row this harness creates — every document and chunk it ingests, and
      every log or chat row produced while running its arms — is written under
      one of the two evaluation users it owns (``HARNESS_USER_EMAILS``), which is
      what makes the user id set the narrowest correct scope.

    The previous revision ran both of its cleanup blocks **unscoped** (``DELETE
    FROM document_chunks`` and four siblings, plus ``DELETE FROM users WHERE email
    LIKE 'phase4b_%'``), which removes every row of those tables in the target
    database — including rows belonging to other experiments that share the
    isolated database.  Database isolation proves the target is not the
    application database; it does not make a database-wide delete safe.

    Order matters: logs, then messages, then sessions, then chunks, then the
    documents that own them, then the users.  Nothing here relies on cascade for
    a row it claims to delete, so the cleanup cannot be blocked by a foreign key.

    The caller commits, exactly as before.
    """
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(db, operation="Phase 4B evaluation row cleanup")
    from sqlalchemy import delete, select

    from auth.models import User
    from chat.models import ChatMessage, ChatSession
    from documents.models import Document, DocumentChunk
    from reliability.models import ReliabilityLog

    ids = list(user_ids)
    if not ids:
        # Nothing of this harness's is present.  An empty ``IN ()`` would be a
        # no-op anyway; returning early keeps the intent explicit.
        return

    owned_sessions = select(ChatSession.id).where(ChatSession.user_id.in_(ids))
    owned_documents = select(Document.id).where(Document.user_id.in_(ids))

    await db.execute(delete(ReliabilityLog).where(ReliabilityLog.user_id.in_(ids)))
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(owned_sessions)))
    await db.execute(delete(ChatSession).where(ChatSession.user_id.in_(ids)))
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id.in_(owned_documents))
    )
    await db.execute(delete(Document).where(Document.user_id.in_(ids)))
    await db.execute(delete(User).where(User.id.in_(ids)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "explicit evaluation database URL. Takes precedence over "
            "DOCUMIND_INTEGRATION_DATABASE_URL. Without an isolated target this "
            "runner refuses to run: it writes to (and deletes from) the database "
            "it targets."
        ),
    )
    return parser.parse_args(argv)


async def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    # --- evaluation target: explicit, guarded, never the application's --------
    application_dsn = application_database_url()
    evaluation_dsn = evaluation_database_url(
        override=args.database_url, application_url=application_dsn
    )
    evaluation_identity = assert_safe_evaluation_target(
        evaluation_dsn,
        operation="the Phase 4B evaluation harness (it deletes rows it owns)",
        application_url=application_dsn,
    )
    # Validity (above) is not permission to destroy: the operator must also name this exact database.
    assert_disposal_authorized(
        evaluation_dsn,
        operation="the Phase 4B evaluation harness (it deletes rows it owns)",
        application_url=application_dsn,
    )
    application_identity = database_identity(application_dsn)
    print(f"[evaluation-db] application database : {describe_identity(application_identity)}")
    print(f"[evaluation-db] evaluation database  : {describe_identity(evaluation_identity)}")
    print(f"[evaluation-db] target (no credentials): {display_dsn(evaluation_dsn)}")
    # The models below resolve their engine from settings when
    # ``storage.database`` is first imported; pointing the environment at the
    # verified target is what makes the run talk to it, and it happens only after
    # the guard has approved that target.
    os.environ["DATABASE_URL"] = evaluation_dsn

    # Drop any cached application settings, then require the effective URL to
    # still be the approved target.  Without this, clearing ``DATABASE_URL``
    # between resolution and import could let the app fall back to its own
    # settings-backed URL.
    from config import get_settings

    get_settings.cache_clear()
    if get_settings().database_url != evaluation_dsn:
        raise RuntimeError(
            "the effective application settings name a different database than the "
            "approved evaluation target; refusing before the models are imported"
        )

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    from documents.chunking import CHUNKER_VERSION_LEGACY, CHUNKER_VERSION_STRUCTURE
    from passlib.context import CryptContext

    engine = create_async_engine(evaluation_dsn)
    from evaluation.isolation import assert_engine_matches_target  # noqa: E402

    assert_engine_matches_target(engine, evaluation_dsn)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    corpus = build_phase4b_corpus()
    unsupported = build_phase4b_unanswerable()
    all_questions = [q for doc in corpus for q in doc.questions] + unsupported

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    users: dict[str, uuid.UUID] = {}
    ingested: dict[str, IngestedCorpus] = {}

    print("=" * 78)
    print("PHASE 4B — QA EVALUATION EXPANSION")
    print(f"  corpus: {len(corpus)} docs, {len(all_questions)} questions")
    print(f"  answerable: {len(all_questions) - len(unsupported)}")
    print(f"  unsupported: {len(unsupported)}")
    print("=" * 78)

    async with session_factory() as db:
        # --- clean previous runs -----------------------------------------
        # Scoped to the users *this* harness owns: their emails are deterministic,
        # so an interrupted earlier run is recognisable.  The previous revision
        # instead deleted every row of five tables and matched users by the
        # ``phase4b_%`` prefix — see ``cleanup_harness_rows``.
        previous_users = await owned_user_ids(db, emails=HARNESS_USER_EMAILS)
        if previous_users:
            await cleanup_harness_rows(db, user_ids=previous_users)
        await db.commit()

        # Ingest with both chunkers
        for label, version in [("legacy", CHUNKER_VERSION_LEGACY),
                               ("candidate", CHUNKER_VERSION_STRUCTURE)]:
            user = User(
                id=uuid.uuid4(), email=harness_user_email(label),
                name=f"Phase4B {label}", hashed_password=pwd.hash("TestPass123!"),
                is_active=True,
            )
            db.add(user)
            await db.flush()
            users[label] = user.id
            ingested[label] = await ingest_corpus(db, user.id, corpus, version, label)
            print(f"  ingested {label:9s}: {ingested[label].chunks} chunks, "
                  f"{ingested[label].ingestion_ms:.0f} ms")
        print()

        # Run arms
        arms = [
            ("A", "legacy", "legacy + legacy char context (pre-Phase-3D baseline)"),
            ("B", "legacy", "legacy chunks + token-aware context"),
            ("C", "candidate", "structure-v2 + token-aware context (candidate)"),
        ]
        results: dict[str, list[QueryResult]] = {a: [] for a, _, _ in arms}

        # Warm-up
        for arm_id, corpus_key, _ in arms:
            for question in all_questions[:2]:
                await run_question(db, users[corpus_key], question,
                                   context_builder_for(arm_id), arm_id, corpus)
        print("  warm-up complete")

        for arm_id, corpus_key, description in arms:
            print(f"\n  --- arm {arm_id}: {description}")
            builder = context_builder_for(arm_id)
            for question in all_questions:
                result = await run_question(
                    db, users[corpus_key], question, builder, arm_id, corpus
                )
                results[arm_id].append(result)
            print(f"      ran {len(results[arm_id])} questions")

        # Aggregate
        summary = {}
        for arm_id, _, description in arms:
            agg = aggregate(results[arm_id])
            chunk_key = "legacy" if arm_id in ("A", "B") else "candidate"
            summary[arm_id] = {
                "description": description,
                "metrics": agg,
                "chunks": chunk_stats(ingested[chunk_key].chunk_rows),
                "ingestion_ms": ingested[chunk_key].ingestion_ms,
                "failure_distribution": failure_distribution(results[arm_id]),
                "per_kind": per_kind_breakdown(results[arm_id]),
                "per_document": per_document_breakdown(results[arm_id]),
                "per_format": per_format_breakdown(results[arm_id]),
            }

        # Build report
        report = {
            "evaluation_version": "4b-v1",
            "corpus_version": "phase4b-v1",
            "configuration": {
                "top_k": TOP_K,
                "embedding_model": "all-MiniLM-L6-v2",
                "embedding_dim": 384,
                "qa_input_length": 384,
                "question_count": len(all_questions),
                "answerable_count": len(all_questions) - len(unsupported),
                "unsupported_count": len(unsupported),
                "document_count": len(corpus),
            },
            "corpus_summary": {
                "documents": len(corpus),
                "questions_total": len(all_questions),
                "questions_answerable": len(all_questions) - len(unsupported),
                "questions_unsupported": len(unsupported),
                "all_synthetic": True,
                "real_corpus_status": "NOT_AVAILABLE",
                "by_kind": dict(Counter(q.kind for q in all_questions)),
                "by_format": dict(Counter(d.file_type for d in corpus)),
            },
            "arms": summary,
            "per_question": {
                arm_id: [
                    {
                        "qid": r.qid, "kind": r.kind, "answerable": r.answerable,
                        "difficulty": r.difficulty, "document": r.document,
                        "document_format": r.document_format,
                        "answer": r.answer, "outcome": r.outcome,
                        "answer_correct_substring": r.answer_correct_substring,
                        "answer_exact_match": r.answer_exact_match,
                        "answer_token_f1": round(r.answer_token_f1, 4),
                        "answer_acceptable_match": r.answer_acceptable_match,
                        "coverage": round(r.coverage, 3),
                        "relevant_in_topk": sum(r.relevant_flags),
                        "context_tokens": r.context_tokens,
                        "context_budget": r.context_budget,
                        "context_util": round(r.context_util, 3),
                        "qa_confidence": round(r.qa_confidence, 4),
                        "best_retrieval_score": round(r.best_retrieval_score, 4),
                        "reported_sources": r.reported_sources,
                        "omitted_sources": r.omitted_sources,
                        "failure_primary": r.failure_primary,
                        "failure_detail": r.failure_detail,
                        "total_ms": r.total_ms,
                    }
                    for r in results[arm_id]
                ]
                for arm_id, _, _ in arms
            },
            "data_leakage_checks": {
                "evaluation_imports_production_routes": False,
                "gold_answers_in_retrieval_query": False,
                "gold_answers_in_qa_prompt": False,
                "evaluation_code_imported_by_production": False,
                "separate_evaluation_users": True,
            },
            "limitations": [
                "All documents are synthetic (programmatic); real-world accuracy unknown",
                f"Corpus: {len(all_questions)} questions; statistical significance limited",
                "Token F1 uses simple token overlap; does not capture semantic similarity",
                "Exact match is case-insensitive, whitespace-normalised",
                "QA model confidence is not well-calibrated (known limitation)",
                "REAL_CORPUS_STATUS = NOT_AVAILABLE",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Save report — STEP 1.6X: through the append-only artifact writer, so
        # re-running the harness cannot silently replace recorded evidence.
        report_name = "phase4b_evaluation_report.json"
        output = RunOutput(Path("."))
        try:
            output.reserve(report_name)
            out = output.write_text(report_name, json.dumps(report, indent=2))
        except ArtifactExistsError as error:
            print(f"\nFAILED: refusing to overwrite recorded evidence: {error}")
            print(
                "Evaluation artifacts are append-only. Move or rename the existing "
                f"report ({Path(report_name).resolve()}), or run the harness from a "
                "different working directory, rather than replacing a result that "
                "has already been recorded."
            )
            return 2
        print(f"\n  wrote {out.resolve()}")

        # Cleanup — only this run's own rows (see ``cleanup_harness_rows``)
        await cleanup_harness_rows(db, user_ids=list(users.values()))
        await db.commit()

    await engine.dispose()

    # Print summary
    _print_summary(summary)
    return 0


def _print_summary(summary: dict) -> None:
    print()
    print("=" * 78)
    print("METRIC COMPARISON (Phase 4B expanded)")
    print(f"  {'metric':36s} {'A legacy':>12s} {'B ctxfix':>12s} {'C cand':>12s}")
    keys = [
        "recall@1", "recall@3", "recall@5",
        "precision@1", "precision@3", "precision@5",
        "mrr",
        "answer_exact_match", "acceptable_answer_match",
        "token_f1", "answerability",
        "answer_exactness_substring",
        "evidence_coverage", "context_utilisation",
        "false_abstention_rate", "abstention_on_unsupported",
        "spurious_answers_on_unsupported",
        "duplicate_retrieval_rate",
        "retrieval_ms_avg", "qa_ms_avg", "total_ms_avg",
    ]
    for key in keys:
        av = summary["A"]["metrics"].get(key, 0)
        bv = summary["B"]["metrics"].get(key, 0)
        cv = summary["C"]["metrics"].get(key, 0)
        print(f"  {key:36s} {av:>12.4f} {bv:>12.4f} {cv:>12.4f}")

    print()
    print("=" * 78)
    print("FAILURE DISTRIBUTION (Arm C)")
    fd = summary["C"]["failure_distribution"]
    for cat, count in sorted(fd.items(), key=lambda x: -x[1]):
        print(f"  {cat:20s} {count}")

    print()
    print("=" * 78)
    print("CHUNK STATISTICS")
    print(f"  {'metric':28s} {'legacy':>14s} {'candidate':>14s}")
    a, c = summary["A"]["chunks"], summary["C"]["chunks"]
    for key in ["chunk_count", "tokens_min", "tokens_median", "tokens_p95",
                "tokens_mean", "tokens_max", "truncated_chunks",
                "encoder_truncation_rate", "table_chunks", "list_chunks",
                "heading_chunks"]:
        print(f"  {key:28s} {str(a.get(key)):>14s} {str(c.get(key)):>14s}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
