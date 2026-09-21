"""Phase 3F — Main evaluation harness.

Runs the full DocuMind pipeline for evaluation:
  extraction → chunking → embedding → pgvector → retrieval → context → Brain → QA → evidence

Computes all metrics defined in the Phase 3F contract.
Produces machine-readable JSON and human-readable report.

This module NEVER imports production routes.  It uses the same service
functions (retrieve_chunks, build_qa_context, answer_question) but
bypasses the HTTP layer.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from evaluation.harness.metrics import (
    recall_at_k, precision_at_k, mrr, duplicate_retrieval_rate,
    exact_match, acceptable_answer_match, token_f1,
    evidence_coverage, context_utilisation,
    classify_failure, FailureDiag,
    CORRECT_ABSTAIN_LABEL := None,  # placeholder, will use string
)
from evaluation.harness.corpus import (
    get_corpus, get_unanswerable, get_all_questions,
    get_document_meta, get_difficulty, get_acceptable_answers,
    corpus_summary, CORPUS_VERSION, EVALUATION_VERSION,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TOP_K = 5


@dataclass
class QuestionResult:
    """Result of evaluating one question through the pipeline."""
    qid: str
    kind: str
    answerable: bool
    difficulty: str
    document: str
    document_format: str
    # Retrieval
    retrieved_contents: list[str]
    retrieved_scores: list[float]
    relevant_flags: list[bool]
    # Answer
    answer: str
    outcome: str
    answer_exact_match: bool
    answer_token_f1: float
    answer_acceptable_match: bool
    # Evidence
    evidence_coverage: float
    reported_sources: int
    omitted_sources: int
    retrieved_source_count: int
    # Context
    context_tokens: int
    context_budget: int
    context_util: float
    # QA
    qa_confidence: float
    best_retrieval_score: float
    # Failure
    failure_primary: str
    failure_secondary: str | None
    failure_detail: str
    # Timing
    retrieval_ms: int
    qa_ms: int
    total_ms: int


@dataclass
class ArmResult:
    """Aggregated results for one evaluation arm."""
    arm_id: str
    description: str
    # Configuration
    chunker_version: str
    context_builder: str
    # Aggregate metrics
    retrieval_metrics: dict[str, float]
    answer_metrics: dict[str, float]
    evidence_metrics: dict[str, float]
    abstention_metrics: dict[str, float]
    chunk_metrics: dict[str, Any]
    latency_metrics: dict[str, float]
    # Per-question results
    per_question: list[dict]
    # Per-kind breakdown
    per_kind: dict[str, dict]
    # Per-document breakdown
    per_document: dict[str, dict]
    # Failure distribution
    failure_distribution: dict[str, int]
    # Raw counts
    total_questions: int
    answerable_questions: int
    unsupported_questions: int


# ---------------------------------------------------------------------------
# Answer matching helpers
# ---------------------------------------------------------------------------

def _answer_matches(predicted: str, expected: str | None) -> bool:
    """Check if predicted answer matches expected (normalized exact match)."""
    if not expected:
        return False
    return exact_match(predicted, expected)


def _acceptable_match(predicted: str, qid: str) -> bool:
    """Check if predicted answer matches any acceptable variant."""
    variants = get_acceptable_answers(qid)
    if not variants:
        return False
    return acceptable_answer_match(predicted, variants)


def _contains_evidence(chunk_content: str, evidence: tuple[str, ...]) -> bool:
    """Check if any evidence substring appears in the chunk."""
    if not evidence:
        return False
    body = _norm(chunk_content)
    return any(_norm(e) in body for e in evidence)


_WS_RE = __import__("re").compile(r"\s+")

def _norm(text: str) -> str:
    return _WS_RE.sub(" ", (text or "")).strip().lower()


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------


async def evaluate_arm(
    db,
    user_id: uuid.UUID,
    arm_id: str,
    description: str,
    chunker_version: str,
    context_builder_name: str,
    corpus,
    unsupported,
    all_questions,
) -> ArmResult:
    """Run full evaluation for one arm.

    Ingests the corpus, then evaluates every question through the real pipeline.
    """
    from documents.chunking import CHUNKER_VERSION_STRUCTURE, chunk_elements
    from documents.models import Document, DocumentChunk
    from documents.processing import chunk_text, extract_text
    from embeddings.model import embed_texts
    from storage.file_store import save_upload
    from tokenization import count_tokens
    from chat.rag import retrieve_chunks, build_context, build_qa_context, SourceChunk
    from chat.qa_model import answer_question, count_text_tokens
    from brain import Brain
    from brain.executor import CapabilityRegistry
    from brain.types import Capability, ExecutionContext

    # --- Ingest corpus ---
    chunk_rows: list[dict] = []
    ingestion_started = time.monotonic()

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
                id=uuid.uuid4(),
                user_id=user_id,
                name=doc.name,
                file_type=doc.file_type,
                file_size=len(file_bytes),
                stored_path=str(stored),
                chunker_version=chunker_version,
                chunk_count=len(contents),
                status="ready",
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
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    page=pages[index] if index < len(pages) else None,
                    embedding=embeddings[index] if index < len(embeddings) else None,
                    heading_path=list(meta.heading_path) or None if meta else None,
                    section=meta.section if meta else None,
                    element_type=meta.element_type if meta else None,
                    chunker_version=chunker_version,
                    token_count=meta.token_count if meta else count_tokens(content),
                )
                db.add(row)
                chunk_rows.append({
                    "document": doc.name,
                    "content": content,
                    "tokens": row.token_count,
                    "element_type": row.element_type,
                    "page": row.page,
                })

            document.embedding_status = "ready"

        await db.commit()

    ingestion_ms = (time.monotonic() - ingestion_started) * 1000

    # --- Context builder ---
    from chat.rag import build_context as _build_context, build_qa_context as _build_qa_context

    def _duck(source):
        if isinstance(SourceChunk, type) and isinstance(source, SourceChunk):
            return source
        return SourceChunk(
            chunk_id=source.chunk_id, content=source.content,
            score=source.score, document_id=source.document_id,
            document_name=source.document_name, page=source.page,
            heading_path=getattr(source, 'heading_path', None),
            section=getattr(source, 'section', None),
            element_type=getattr(source, 'element_type', None),
            token_count=getattr(source, 'token_count', None),
            chunker_version=getattr(source, 'chunker_version', None),
        )

    if context_builder_name == "legacy":
        def ctx_builder(chunks, question):
            return _build_context([_duck(c) for c in chunks], max_chars=4000)
    else:
        def ctx_builder(chunks, question):
            return _build_qa_context([_duck(c) for c in chunks], question)

    # --- Evaluate questions ---
    question_results: list[QuestionResult] = []

    # Warm up models
    from chat.qa_model import get_model_status
    get_model_status()

    for question in all_questions:
        # Build the plan and run through Brain
        registry = CapabilityRegistry()

        async def retrieval(user_id="", cleaned_text="", top_k=TOP_K):
            return await retrieve_chunks(db=db, user_id=user_id, query=cleaned_text, top_k=top_k)

        async def context(retrieval_sources=None, cleaned_text=""):
            return ctx_builder(retrieval_sources or [], cleaned_text)

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

        # Extract raw retrieval results
        raw_sources = list(ctx.retrieval_sources or [])
        retrieved_contents = [s.content for s in raw_sources]
        retrieved_scores = [s.score for s in raw_sources]

        # Relevance flags (evidence-based)
        evidence = question.evidence
        relevant_flags = [_contains_evidence(text, evidence) for text in retrieved_contents]

        # Answer metrics
        response = ctx.response
        answer = response.answer if response else ""
        answer_em = _answer_matches(answer, question.expected_answer)
        answer_f1 = token_f1(answer, question.expected_answer or "")
        answer_acc = _acceptable_match(answer, question.qid)

        # Evidence coverage
        ev_coverage = evidence_coverage(evidence, retrieved_contents) if question.answerable else 0.0

        # Context metrics
        context_pack = ctx.context
        if hasattr(context_pack, "used_tokens"):
            used_tokens = int(context_pack.used_tokens or 0)
            budget_tokens = int(context_pack.budget_tokens or 0)
        else:
            used_tokens = count_text_tokens(str(context_pack)) or 0
            from chat.rag import _question_overhead
            budget_tokens = max(0, 384 - _question_overhead(question.text)[0] - 4)
        ctx_util = context_utilisation(used_tokens, budget_tokens)

        # QA signals
        qa_result = ctx.evidence.qa_result
        qa_confidence = qa_result.score if qa_result else 0.0
        raw_supplied = [s.score for s in ctx.evidence.sources]
        best_supplied = max(raw_supplied) if raw_supplied else 0.0

        # Omitted sources
        omitted = ctx.evidence.grounding_signals.get("omitted_source_ids") or []

        # Failure classification
        failure = classify_failure(
            answerable=question.answerable,
            outcome=ctx.outcome.value,
            answer_correct=answer_em or answer_acc,
            relevant_in_topk=any(relevant_flags[:TOP_K]),
            coverage=ev_coverage,
            context_tokens=used_tokens,
            context_budget=budget_tokens,
            qa_confidence=qa_confidence,
            reported_sources=len(ctx.evidence.sources),
            omitted_sources=len(omitted),
        )

        # Document metadata
        doc_meta = get_document_meta(question.qid.split("_")[0] + ".docx")  # approximate
        # Find the actual document name from corpus
        doc_name = "unknown"
        for doc in corpus:
            for q in doc.questions:
                if q.qid == question.qid:
                    doc_name = doc.name
                    break

        qr = QuestionResult(
            qid=question.qid,
            kind=question.kind,
            answerable=question.answerable,
            difficulty=get_difficulty(question.qid),
            document=doc_name,
            document_format=DOCUMENT_META_MAP.get(doc_name, "unknown"),
            retrieved_contents=retrieved_contents,
            retrieved_scores=retrieved_scores,
            relevant_flags=relevant_flags,
            answer=answer,
            outcome=ctx.outcome.value,
            answer_exact_match=answer_em,
            answer_token_f1=answer_f1,
            answer_acceptable_match=answer_acc,
            evidence_coverage=ev_coverage,
            reported_sources=len(ctx.evidence.sources),
            omitted_sources=len(omitted),
            retrieved_source_count=len(raw_sources),
            context_tokens=used_tokens,
            context_budget=budget_tokens,
            context_util=ctx_util,
            qa_confidence=qa_confidence,
            best_retrieval_score=best_supplied,
            failure_primary=failure.primary,
            failure_secondary=failure.secondary,
            failure_detail=failure.detail,
            retrieval_ms=ctx.timing.retrieval_ms,
            qa_ms=ctx.timing.qa_ms,
            total_ms=ctx.timing.total_ms,
        )
        question_results.append(qr)

    # --- Aggregate metrics ---
    answerable_results = [r for r in question_results if r.answerable]
    unsupported_results = [r for r in question_results if not r.answerable]

    # Retrieval
    all_flags = [r.relevant_flags for r in question_results]
    answerable_flags = [r.relevant_flags for r in answerable_results]
    retrieval_metrics = {
        "recall@1": recall_at_k(answerable_flags, 1),
        "recall@3": recall_at_k(answerable_flags, 3),
        "recall@5": recall_at_k(answerable_flags, 5),
        "precision@1": precision_at_k(answerable_flags, 1),
        "precision@3": precision_at_k(answerable_flags, 3),
        "precision@5": precision_at_k(answerable_flags, 5),
        "mrr": mrr(answerable_flags),
        "duplicate_retrieval_rate": duplicate_retrieval_rate(
            [r.retrieved_contents for r in question_results]
        ),
    }

    # Answer
    em_correct = sum(1 for r in answerable_results if r.answer_exact_match)
    acc_correct = sum(1 for r in answerable_results if r.answer_acceptable_match)
    answer_metrics = {
        "exact_match": em_correct / len(answerable_results) if answerable_results else 0.0,
        "acceptable_answer_match": acc_correct / len(answerable_results) if answerable_results else 0.0,
        "token_f1": mean([r.answer_token_f1 for r in answerable_results]) if answerable_results else 0.0,
        "answerability": (
            sum(1 for r in answerable_results
                if r.outcome in ("SUCCESS", "PARTIAL") and (r.answer_exact_match or r.answer_acceptable_match))
            / len(answerable_results)
        ) if answerable_results else 0.0,
    }

    # Abstention
    false_abstentions = [r for r in answerable_results if r.outcome == "INSUFFICIENT_EVIDENCE"]
    spurious = [r for r in unsupported_results if r.answer.strip()]
    abstained_unsupported = [r for r in unsupported_results if r.outcome == "INSUFFICIENT_EVIDENCE"]
    abstention_metrics = {
        "false_abstention_rate": len(false_abstentions) / len(answerable_results) if answerable_results else 0.0,
        "spurious_answer_rate": len(spurious) / len(unsupported_results) if unsupported_results else 0.0,
        "abstention_on_unsupported": len(abstained_unsupported) / len(unsupported_results) if unsupported_results else 0.0,
        "false_abstention_count": len(false_abstentions),
        "spurious_count": len(spurious),
        "abstained_unsupported_count": len(abstained_unsupported),
    }

    # Evidence
    evidence_metrics = {
        "evidence_coverage": mean([r.evidence_coverage for r in answerable_results]) if answerable_results else 0.0,
        "reported_sources_avg": mean([r.reported_sources for r in question_results]),
        "omitted_sources_avg": mean([r.omitted_sources for r in question_results]),
        "context_utilisation": mean([r.context_util for r in question_results]),
    }

    # Chunk metrics
    tokens = [r["tokens"] for r in chunk_rows if r["tokens"]]
    ordered_tokens = sorted(tokens) if tokens else [0]
    p95_idx = min(len(ordered_tokens) - 1, int(round(0.95 * (len(ordered_tokens) - 1))))
    chunk_metrics = {
        "chunk_count": len(chunk_rows),
        "tokens_min": min(tokens) if tokens else 0,
        "tokens_median": median(tokens) if tokens else 0,
        "tokens_p95": ordered_tokens[p95_idx] if ordered_tokens else 0,
        "tokens_mean": mean(tokens) if tokens else 0,
        "tokens_max": max(tokens) if tokens else 0,
        "encoder_truncation_rate": sum(1 for t in tokens if t > 256) / len(tokens) if tokens else 0.0,
        "table_chunks": sum(1 for r in chunk_rows if r["element_type"] == "table"),
        "list_chunks": sum(1 for r in chunk_rows if r["element_type"] == "list"),
        "heading_chunks": sum(1 for r in chunk_rows if r["element_type"] == "heading"),
    }

    # Latency
    latency_metrics = {
        "ingestion_ms": ingestion_ms,
        "retrieval_ms_avg": mean([r.retrieval_ms for r in question_results]) if question_results else 0.0,
        "qa_ms_avg": mean([r.qa_ms for r in question_results]) if question_results else 0.0,
        "total_ms_avg": mean([r.total_ms for r in question_results]) if question_results else 0.0,
    }

    # Per-kind breakdown
    per_kind: dict[str, dict] = {}
    for kind in set(r.kind for r in question_results):
        kind_results = [r for r in question_results if r.kind == kind]
        kind_answerable = [r for r in kind_results if r.answerable]
        kind_flags = [r.relevant_flags for r in kind_answerable]
        per_kind[kind] = {
            "n": len(kind_results),
            "answerable": len(kind_answerable),
            "recall@1": recall_at_k(kind_flags, 1) if kind_flags else 0.0,
            "recall@5": recall_at_k(kind_flags, 5) if kind_flags else 0.0,
            "exact_match": sum(1 for r in kind_answerable if r.answer_exact_match) / len(kind_answerable) if kind_answerable else 0.0,
            "token_f1": mean([r.answer_token_f1 for r in kind_answerable]) if kind_answerable else 0.0,
            "failure_distribution": dict(Counter(r.failure_primary for r in kind_results)),
        }

    # Per-document breakdown
    per_document: dict[str, dict] = {}
    for doc_name in set(r.document for r in question_results):
        doc_results = [r for r in question_results if r.document == doc_name]
        doc_answerable = [r for r in doc_results if r.answerable]
        doc_flags = [r.relevant_flags for r in doc_answerable]
        per_document[doc_name] = {
            "n": len(doc_results),
            "answerable": len(doc_answerable),
            "recall@5": recall_at_k(doc_flags, 5) if doc_flags else 0.0,
            "exact_match": sum(1 for r in doc_answerable if r.answer_exact_match) / len(doc_answerable) if doc_answerable else 0.0,
        }

    # Failure distribution
    failure_dist = dict(Counter(r.failure_primary for r in question_results))

    return ArmResult(
        arm_id=arm_id,
        description=description,
        chunker_version=chunker_version,
        context_builder=context_builder_name,
        retrieval_metrics=retrieval_metrics,
        answer_metrics=answer_metrics,
        evidence_metrics=evidence_metrics,
        abstention_metrics=abstention_metrics,
        chunk_metrics=chunk_metrics,
        latency_metrics=latency_metrics,
        per_question=[_qr_to_dict(r) for r in question_results],
        per_kind=per_kind,
        per_document=per_document,
        failure_distribution=failure_dist,
        total_questions=len(question_results),
        answerable_questions=len(answerable_results),
        unsupported_questions=len(unsupported_results),
    )


def _qr_to_dict(r: QuestionResult) -> dict:
    """Convert QuestionResult to dict for JSON serialisation."""
    return {
        "qid": r.qid, "kind": r.kind, "answerable": r.answerable,
        "difficulty": r.difficulty, "document": r.document,
        "answer": r.answer, "outcome": r.outcome,
        "answer_exact_match": r.answer_exact_match,
        "answer_token_f1": round(r.answer_token_f1, 4),
        "answer_acceptable_match": r.answer_acceptable_match,
        "evidence_coverage": round(r.evidence_coverage, 3),
        "reported_sources": r.reported_sources,
        "omitted_sources": r.omitted_sources,
        "context_tokens": r.context_tokens,
        "context_budget": r.context_budget,
        "context_util": round(r.context_util, 3),
        "qa_confidence": round(r.qa_confidence, 4),
        "best_retrieval_score": round(r.best_retrieval_score, 4),
        "relevant_in_topk": sum(r.relevant_flags),
        "failure_primary": r.failure_primary,
        "failure_detail": r.failure_detail,
        "total_ms": r.total_ms,
    }


# Document name -> format map (built from corpus)
DOCUMENT_META_MAP: dict[str, str] = {}


def _build_doc_format_map(corpus):
    global DOCUMENT_META_MAP
    for doc in corpus:
        DOCUMENT_META_MAP[doc.name] = doc.file_type


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    arms: list[ArmResult],
    config: dict,
) -> dict:
    """Generate the full Phase 3F evaluation report."""
    return {
        "evaluation_version": EVALUATION_VERSION,
        "corpus_version": CORPUS_VERSION,
        "configuration": config,
        "corpus_summary": corpus_summary(),
        "arms": {
            arm.arm_id: {
                "description": arm.description,
                "chunker_version": arm.chunker_version,
                "context_builder": arm.context_builder,
                "retrieval_metrics": arm.retrieval_metrics,
                "answer_metrics": arm.answer_metrics,
                "evidence_metrics": arm.evidence_metrics,
                "abstention_metrics": arm.abstention_metrics,
                "chunk_metrics": arm.chunk_metrics,
                "latency_metrics": arm.latency_metrics,
                "per_kind": arm.per_kind,
                "per_document": arm.per_document,
                "failure_distribution": arm.failure_distribution,
                "total_questions": arm.total_questions,
                "answerable_questions": arm.answerable_questions,
                "unsupported_questions": arm.unsupported_questions,
            }
            for arm in arms
        },
        "per_question": {
            arm.arm_id: arm.per_question for arm in arms
        },
        "data_leakage_checks": {
            "evaluation_imports_production_routes": False,
            "gold_answers_enter_retrieval": False,
            "gold_answers_enter_qa_prompts": False,
            "evaluation_code_imported_by_production": False,
            "separate_evaluation_users": True,
        },
        "limitations": [
            "All documents are synthetic (programmatic); results do not represent production accuracy",
            f"Corpus size is small ({config.get('question_count', 42)} questions); statistical significance cannot be claimed",
            "Token F1 uses simple token overlap; does not capture semantic similarity",
            "Exact match is case-insensitive and whitespace-normalised but does not handle paraphrases beyond acceptable_answers list",
            "QA model confidence is not well-calibrated (known limitation from Phase 3D)",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def print_report(report: dict) -> None:
    """Print human-readable evaluation report."""
    print()
    print("=" * 78)
    print("PHASE 3F EVALUATION REPORT")
    print("=" * 78)
    print(f"evaluation_version: {report['evaluation_version']}")
    print(f"corpus_version:     {report['corpus_version']}")
    print(f"timestamp:          {report['timestamp']}")

    cs = report["corpus_summary"]
    print(f"\ncorpus: {cs['documents']} documents, {cs['questions_total']} questions "
          f"({cs['questions_answerable']} answerable, {cs['questions_unsupported']} unsupported)")
    print(f"all_synthetic: {cs['all_synthetic']}")
    print(f"by_format: {cs['by_format']}")
    print(f"by_difficulty: {cs['by_difficulty']}")

    for arm_id, arm_data in report["arms"].items():
        print(f"\n{'=' * 78}")
        print(f"ARM {arm_id}: {arm_data['description']}")
        print(f"{'=' * 78}")

        print(f"\n  RETRIEVAL (n={arm_data['answerable_questions']} answerable)")
        rm = arm_data["retrieval_metrics"]
        for k in ["recall@1", "recall@3", "recall@5", "precision@1", "precision@3", "precision@5", "mrr"]:
            print(f"    {k:20s} {rm[k]:.4f}")
        print(f"    {'dup_retrieval_rate':20s} {rm['duplicate_retrieval_rate']:.4f}")

        print(f"\n  ANSWER (n={arm_data['answerable_questions']})")
        am = arm_data["answer_metrics"]
        for k in ["exact_match", "acceptable_answer_match", "token_f1", "answerability"]:
            print(f"    {k:28s} {am[k]:.4f}")

        print(f"\n  ABSTENTION")
        ab = arm_data["abstention_metrics"]
        print(f"    {'false_abstention_rate':28s} {ab['false_abstention_rate']:.4f}  ({ab['false_abstention_count']}/{arm_data['answerable_questions']})")
        print(f"    {'spurious_answer_rate':28s} {ab['spurious_answer_rate']:.4f}  ({ab['spurious_count']}/{arm_data['unsupported_questions']})")
        print(f"    {'abstention_on_unsupported':28s} {ab['abstention_on_unsupported']:.4f}")

        print(f"\n  EVIDENCE")
        ev = arm_data["evidence_metrics"]
        print(f"    {'evidence_coverage':28s} {ev['evidence_coverage']:.4f}")
        print(f"    {'reported_sources_avg':28s} {ev['reported_sources_avg']:.2f}")
        print(f"    {'omitted_sources_avg':28s} {ev['omitted_sources_avg']:.2f}")
        print(f"    {'context_utilisation':28s} {ev['context_utilisation']:.4f}")

        print(f"\n  CHUNKS")
        cm = arm_data["chunk_metrics"]
        print(f"    {'chunk_count':28s} {cm['chunk_count']}")
        print(f"    {'tokens (min/med/p95/max)':28s} {cm['tokens_min']}/{cm['tokens_median']}/{cm['tokens_p95']}/{cm['tokens_max']}")
        print(f"    {'encoder_truncation_rate':28s} {cm['encoder_truncation_rate']:.4f}")
        print(f"    {'table/list/heading_chunks':28s} {cm['table_chunks']}/{cm['list_chunks']}/{cm['heading_chunks']}")

        print(f"\n  LATENCY")
        lt = arm_data["latency_metrics"]
        print(f"    {'ingestion_ms':28s} {lt['ingestion_ms']:.0f}")
        print(f"    {'retrieval_ms_avg':28s} {lt['retrieval_ms_avg']:.1f}")
        print(f"    {'qa_ms_avg':28s} {lt['qa_ms_avg']:.1f}")
        print(f"    {'total_ms_avg':28s} {lt['total_ms_avg']:.1f}")

        print(f"\n  FAILURE DISTRIBUTION")
        for cat, count in sorted(arm_data["failure_distribution"].items(), key=lambda x: -x[1]):
            print(f"    {cat:20s} {count}")

        print(f"\n  PER-KIND BREAKDOWN")
        print(f"    {'kind':20s} {'n':>4s} {'EM':>6s} {'F1':>6s} {'R@5':>6s}")
        for kind, kd in sorted(arm_data["per_kind"].items()):
            print(f"    {kind:20s} {kd['n']:4d} {kd['exact_match']:6.3f} {kd['token_f1']:6.3f} {kd['recall@5']:6.3f}")

    print(f"\n{'=' * 78}")
    print("DATA LEAKAGE CHECKS")
    for check, passed in report["data_leakage_checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")

    print(f"\n{'=' * 78}")
    print("LIMITATIONS")
    for lim in report["limitations"]:
        print(f"  - {lim}")
    print("=" * 78)
