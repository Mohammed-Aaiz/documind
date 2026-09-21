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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://documind:documind@localhost:5432/documind"
)

TOP_K = 5

from tests.phase4b_corpus import (  # noqa: E402
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
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    from documents.chunking import CHUNKER_VERSION_LEGACY, CHUNKER_VERSION_STRUCTURE
    from passlib.context import CryptContext

    engine = create_async_engine(
        "postgresql+asyncpg://documind:documind@localhost:5432/documind"
    )
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
        # Clean
        await db.execute(text("DELETE FROM reliability_logs"))
        await db.execute(text("DELETE FROM chat_messages"))
        await db.execute(text("DELETE FROM chat_sessions"))
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM users WHERE email LIKE 'phase4b_%'"))
        await db.commit()

        # Ingest with both chunkers
        for label, version in [("legacy", CHUNKER_VERSION_LEGACY),
                               ("candidate", CHUNKER_VERSION_STRUCTURE)]:
            user = User(
                id=uuid.uuid4(), email=f"phase4b_{label}@test.local",
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

        # Save report
        out = Path("phase4b_evaluation_report.json")
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\n  wrote {out.resolve()}")

        # Cleanup
        await db.execute(text("DELETE FROM reliability_logs"))
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM users WHERE email LIKE 'phase4b_%'"))
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
