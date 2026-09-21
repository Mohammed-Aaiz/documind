"""Phase 3D — CHUNKING / RETRIEVAL evaluation harness (not ingestion E2E).

Scope
-----
This harness deliberately writes ``DocumentChunk`` rows directly, after running
the real extractors and the real chunker in-process.  The bypass is intentional:
it isolates the two variables under test (chunker, context builder) from the
HTTP ingestion route, so a difference between arms cannot be caused by upload,
validation or storage behaviour.

What IS real here: real corpus documents, real extractors
(``documents.processing.extract_text``), the real chunkers, the real embedding
model, real PostgreSQL + pgvector retrieval, the real context builders, the real
Brain (executor + evidence gate + response assembler) and the real DocuMind QA
model.  Nothing is mocked and no metric is hardcoded.

What is NOT covered here: the HTTP ingestion path.  For real
upload → validation → extraction → chunking → embedding → retrieval → Brain → QA
validation use ``test_phase3d_upload_integration.py``.  This file must not be
cited as full ingestion E2E evidence.

Arms
----
A  legacy chunks       + legacy character context builder  (pre-Phase-3D context
                                                          baseline: the Brain
                                                          no longer uses this
                                                          builder)
B  legacy chunks       + token-aware context builder       (isolates the fix)
C  structure-v2 chunks + token-aware context builder       (the candidate)

Metrics are computed from the results, never asserted:

  Recall@1/3/5, Precision@1/3/5, evidence coverage, answerability,
  false-abstention rate, abstention on unsupported questions, duplicate
  retrieval rate, chunk count, token distribution, encoder truncation,
  QA context utilisation, ingestion / retrieval / QA latency.

Usage::

    cd backend
    python test_phase3d_evaluation.py
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
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DOCUMIND_DEV", "1")
os.environ.setdefault("QA_MODEL_NAME", "./models/documind-qa")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://documind:documind@localhost:5432/documind"
)

TOP_K = 5

from tests.phase3d_corpus import CorpusDoc, Question, build_corpus, unanswerable_questions  # noqa: E402


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def tokens_of(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", norm(text)))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def contains_evidence(chunk_content: str, evidence: tuple[str, ...]) -> bool:
    if not evidence:
        return False
    body = norm(chunk_content)
    return any(norm(item) in body for item in evidence)


def answer_matches(answer: str, expected: str | None) -> bool:
    if not expected:
        return False
    a, e = norm(answer), norm(expected)
    if not a:
        return False
    return e in a or a in e


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

@dataclass
class IngestedCorpus:
    arm: str
    user_id: uuid.UUID
    docs: list[CorpusDoc]
    chunk_rows: list[dict] = field(default_factory=list)
    ingestion_ms: float = 0.0
    chunks: int = 0


async def ingest_corpus(db, user_id, corpus, chunker_version, label) -> IngestedCorpus:
    """Extract, chunk, embed and store an entire corpus under one user."""
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
                result.chunk_rows.append(
                    {
                        "document": doc.name,
                        "content": content,
                        "tokens": row.token_count,
                        "element_type": row.element_type,
                        "strategy": meta.strategy if meta else "legacy",
                        "page": row.page,
                    }
                )

            document.embedding_status = "ready"
            result.chunks += len(contents)

        await db.commit()

    result.ingestion_ms = (time.monotonic() - started) * 1000
    return result


# ---------------------------------------------------------------------------
# Query evaluation
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    qid: str
    arm: str
    kind: str
    answerable: bool
    retrieved: list[str]
    retrieved_scores: list[float]
    relevant_flags: list[bool]
    coverage: float
    answer: str
    outcome: str
    answer_correct: bool
    best_retrieval_score: float
    qa_confidence: float
    context_tokens: int
    context_budget: int
    context_util: float
    reported_sources: int
    omitted_sources: int
    retrieval_ms: int
    qa_ms: int
    total_ms: int


def metrics_for_question(question: Question, retrieved, retrieval_scores) -> dict:
    evidence = question.evidence
    flags = [contains_evidence(text, evidence) for text in retrieved]
    if question.answerable and evidence:
        covered = {
            item for item in evidence
            if any(norm(item) in norm(text) for text in retrieved)
        }
        coverage = len(covered) / len(evidence)
    else:
        coverage = 0.0
    return {"flags": flags, "coverage": coverage}


def duplicate_rate(retrieved: list[str]) -> float:
    """Fraction of top-K chunks that repeat an earlier chunk's substance."""
    if len(retrieved) < 2:
        return 0.0
    token_sets = [tokens_of(text) for text in retrieved]
    duplicates = 0
    for i in range(1, len(token_sets)):
        for j in range(i):
            if jaccard(token_sets[i], token_sets[j]) >= 0.8:
                duplicates += 1
                break
    return duplicates / len(retrieved)


async def run_question(db, user_id, question: Question, context_builder, arm: str) -> QueryResult:
    """Run one question through the real Brain with a chosen context builder."""
    from brain import Brain
    from brain.executor import CapabilityRegistry
    from brain.types import Capability, ExecutionContext
    from chat.qa_model import answer_question
    from chat.rag import retrieve_chunks

    registry = CapabilityRegistry()

    async def retrieval(user_id="", cleaned_text="", top_k=TOP_K):
        return await retrieve_chunks(
            db=db, user_id=user_id, query=cleaned_text, top_k=top_k
        )

    async def context(retrieval_sources=None, cleaned_text=""):
        return context_builder(retrieval_sources or [], cleaned_text)

    async def qa(cleaned_text="", context=""):
        result = answer_question(cleaned_text, context)
        from brain.types import QaResult

        return QaResult(
            answer=result["answer"], score=result["score"],
            start=result["start"], end=result["end"],
        )

    registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval)
    registry.register(Capability.CONTEXT_BUILDING, context)
    registry.register(Capability.QA_ANSWER, qa)

    ctx = ExecutionContext(user_id=str(user_id), raw_question=question.text, top_k=TOP_K)
    ctx = await Brain(registry).process(ctx)

    # Retrieval metrics must use everything retrieval returned, not the subset
    # that survived context construction, otherwise arms B/C would appear to
    # have worse retrieval for a context-window reason.
    raw_sources = list(ctx.retrieval_sources or [])
    retrieved = [s.content for s in raw_sources]
    scores = [s.score for s in raw_sources]
    info = metrics_for_question(question, retrieved, scores)

    # Context utilisation = share of the *supplied* context the model actually
    # reads.  The legacy builder supplies ~1000 tokens into a 384-token window
    # (so most is discarded); the token-aware builder should supply only what
    # fits.
    from chat.qa_model import count_text_tokens
    from chat.rag import _question_overhead  # internal, used for accounting only

    context_pack = ctx.context
    window = 384
    if hasattr(context_pack, "used_tokens"):
        supplied = int(context_pack.used_tokens or 0)
        context_budget = int(context_pack.budget_tokens or 0)
    else:
        supplied = int(count_text_tokens(str(context_pack)) or 0)
        context_budget = max(0, window - _question_overhead(question.text)[0] - 4)
    attended = min(supplied, context_budget)
    utilisation = (attended / supplied) if supplied else 0.0
    context_tokens = supplied

    response = ctx.response
    answer = response.answer if response else ""

    # Raw signals, recorded so abstention can be interpreted rather than
    # guessed at: best supplied-chunk similarity and the model's own score.
    raw_supplied = [s.score for s in ctx.evidence.sources]
    best_supplied = max(raw_supplied) if raw_supplied else 0.0
    qa = ctx.evidence.qa_result
    qa_confidence = qa.score if qa else 0.0

    return QueryResult(
        qid=question.qid,
        arm=arm,
        kind=question.kind,
        answerable=question.answerable,
        retrieved=retrieved,
        retrieved_scores=scores,
        relevant_flags=info["flags"],
        coverage=info["coverage"],
        answer=answer,
        outcome=ctx.outcome.value,
        answer_correct=answer_matches(answer, question.expected_answer),
        best_retrieval_score=best_supplied,
        qa_confidence=qa_confidence,
        context_tokens=context_tokens,
        context_budget=context_budget,
        context_util=utilisation,
        reported_sources=len(ctx.evidence.sources),
        omitted_sources=len(ctx.evidence.grounding_signals.get("omitted_source_ids", []) or []),
        retrieval_ms=ctx.timing.retrieval_ms,
        qa_ms=ctx.timing.qa_ms,
        total_ms=ctx.timing.total_ms,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(results: list[QueryResult]) -> dict:
    answerable = [r for r in results if r.answerable]
    unsupported = [r for r in results if not r.answerable]

    def recall_at(k: int) -> float:
        if not answerable:
            return 0.0
        hits = sum(1 for r in answerable if any(r.relevant_flags[:k]))
        return hits / len(answerable)

    def precision_at(k: int) -> float:
        if not answerable:
            return 0.0
        return mean(
            (sum(r.relevant_flags[:k]) / min(k, max(1, len(r.relevant_flags))))
            for r in answerable
        )

    false_abstention = [
        r for r in answerable if r.outcome == "INSUFFICIENT_EVIDENCE"
    ]
    abstained_unsupported = [
        r for r in unsupported if r.outcome == "INSUFFICIENT_EVIDENCE"
    ]
    answered_unsupported = [r for r in unsupported if r.answer.strip()]

    return {
        "queries": len(results),
        "answerable_queries": len(answerable),
        "recall@1": recall_at(1),
        "recall@3": recall_at(3),
        "recall@5": recall_at(5),
        "precision@1": precision_at(1),
        "precision@3": precision_at(3),
        "precision@5": precision_at(5),
        "evidence_coverage": mean([r.coverage for r in answerable]) if answerable else 0.0,
        "answerability": (
            sum(1 for r in answerable if r.outcome in ("SUCCESS", "PARTIAL") and r.answer_correct)
            / len(answerable)
        ) if answerable else 0.0,
        "answer_exactness": (
            sum(1 for r in answerable if r.answer_correct) / len(answerable)
        ) if answerable else 0.0,
        "false_abstention_rate": (
            len(false_abstention) / len(answerable)
        ) if answerable else 0.0,
        "outcome_success_rate": (
            sum(1 for r in answerable if r.outcome == "SUCCESS") / len(answerable)
        ) if answerable else 0.0,
        "abstention_on_unsupported": (
            len(abstained_unsupported) / len(unsupported)
        ) if unsupported else 0.0,
        "spurious_answers_on_unsupported": (
            len(answered_unsupported) / len(unsupported)
        ) if unsupported else 0.0,
        "duplicate_retrieval_rate": mean([duplicate_rate(r.retrieved) for r in results]),
        "context_utilisation": mean([r.context_util for r in results]),
        "reported_sources_avg": mean([r.reported_sources for r in results]),
        "omitted_sources_avg": mean([r.omitted_sources for r in results]),
        "retrieval_ms_avg": mean([r.retrieval_ms for r in results]),
        "qa_ms_avg": mean([r.qa_ms for r in results]),
        "total_ms_avg": mean([r.total_ms for r in results]),
    }


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


def context_builder_for(arm: str):
    from chat.rag import build_context, build_qa_context

    if arm == "A":
        return lambda chunks, question: build_context(
            [duck(c) for c in chunks], max_chars=4000
        )
    return lambda chunks, question: build_qa_context(
        [duck(c) for c in chunks], question
    )


def duck(source):
    """Adapt a Brain SourceRef to the service SourceChunk the builders expect."""
    from chat.rag import SourceChunk

    if isinstance(source, SourceChunk):
        return source
    return SourceChunk(
        chunk_id=source.chunk_id,
        content=source.content,
        score=source.score,
        document_id=source.document_id,
        document_name=source.document_name,
        page=source.page,
        heading_path=source.heading_path,
        section=source.section,
        element_type=source.element_type,
        token_count=source.token_count,
        chunker_version=source.chunker_version,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Import every model so SQLAlchemy can resolve all relationships.
    from auth.models import User  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from chat.models import ChatSession, ChatMessage  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401

    from documents.chunking import CHUNKER_VERSION_LEGACY, CHUNKER_VERSION_STRUCTURE, chunk_contract_info
    from embeddings.model import get_dimensions
    from tokenization import get_encoder_limits
    from passlib.context import CryptContext

    engine = create_async_engine(
        "postgresql+asyncpg://documind:documind@localhost:5432/documind"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    corpus = build_corpus()
    unsupported = unanswerable_questions()
    all_questions = [q for doc in corpus for q in doc.questions] + unsupported

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    users: dict[str, uuid.UUID] = {}
    ingested: dict[str, IngestedCorpus] = {}

    print("=" * 78)
    print("PHASE 3D EVALUATION — real documents, embeddings, pgvector, QA model")
    print("=" * 78)
    print("chunk contract:", json.dumps(chunk_contract_info()))
    print("encoder limits :", json.dumps(get_encoder_limits()))
    print("embedding dims :", get_dimensions())
    print(f"corpus         : {len(corpus)} documents, {len(all_questions)} questions")
    print()

    async with session_factory() as db:
        # --- clean previous runs -----------------------------------------
        await db.execute(text("DELETE FROM reliability_logs"))
        await db.execute(text("DELETE FROM chat_messages"))
        await db.execute(text("DELETE FROM chat_sessions"))
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM users WHERE email LIKE 'phase3d_%'"))
        await db.commit()

        for arm, version in (("legacy", CHUNKER_VERSION_LEGACY),
                             ("candidate", CHUNKER_VERSION_STRUCTURE)):
            user = User(
                id=uuid.uuid4(),
                email=f"phase3d_{arm}@test.local",
                name=f"Phase3D {arm}",
                hashed_password=pwd.hash("TestPass123!"),
                is_active=True,
            )
            db.add(user)
            await db.flush()
            users[arm] = user.id
            ingested[arm] = await ingest_corpus(
                db, user.id, corpus, version, arm
            )
            print(
                f"ingested {arm:9s}: {len(corpus)} docs, "
                f"{ingested[arm].chunks} chunks, "
                f"{ingested[arm].ingestion_ms:.0f} ms"
            )
        print()

        # --- run all arms -------------------------------------------------
        arms = [
            ("A", "legacy", "legacy + legacy char context (pre-Phase-3D baseline)"),
            ("B", "legacy", "legacy chunks + token-aware context"),
            ("C", "candidate", "structure-v2 + token-aware context (candidate)"),
        ]
        results: dict[str, list[QueryResult]] = {a: [] for a, _, _ in arms}

        # Warm-up: remove model/connection cold-start bias from the latency
        # figures before the measured pass.
        warmup = all_questions[:2]
        for arm_id, corpus_key, _ in arms:
            for question in warmup:
                await run_question(
                    db, users[corpus_key], question, context_builder_for(arm_id), arm_id
                )
        print("warm-up complete\n")

        for arm_id, corpus_key, description in arms:
            print(f"--- arm {arm_id}: {description}")
            builder = context_builder_for(arm_id)
            for question in all_questions:
                result = await run_question(
                    db, users[corpus_key], question, builder, arm_id
                )
                results[arm_id].append(result)
            print(f"    ran {len(results[arm_id])} questions")

        summary = {}
        print()
        for arm_id, _, description in arms:
            summary[arm_id] = {
                "description": description,
                "metrics": aggregate(results[arm_id]),
                "chunks": chunk_stats(ingested[
                    "legacy" if arm_id in ("A", "B") else "candidate"
                ].chunk_rows),
                "ingestion_ms": ingested[
                    "legacy" if arm_id in ("A", "B") else "candidate"
                ].ingestion_ms,
            }

        # --- per-question comparison --------------------------------------
        report = {
            "arms": summary,
            "per_question": {
                arm_id: [
                    {
                        "qid": r.qid, "kind": r.kind, "answerable": r.answerable,
                        "outcome": r.outcome, "answer": r.answer,
                        "answer_correct": r.answer_correct,
                        "best_retrieval_score": round(r.best_retrieval_score, 4),
                        "qa_confidence": round(r.qa_confidence, 4),
                        "coverage": round(r.coverage, 3),
                        "relevant_in_topk": sum(r.relevant_flags),
                        "context_tokens": r.context_tokens,
                        "context_budget": r.context_budget,
                        "reported_sources": r.reported_sources,
                        "omitted_sources": r.omitted_sources,
                        "duplicate_rate": round(duplicate_rate(r.retrieved), 3),
                        "total_ms": r.total_ms,
                    }
                    for r in results[arm_id]
                ]
                for arm_id, _, _ in arms
            },
        }

        out = Path("phase3d_evaluation_report.json")
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {out.resolve()}")

        # --- cleanup ------------------------------------------------------
        await db.execute(text("DELETE FROM reliability_logs"))
        await db.execute(text("DELETE FROM document_chunks"))
        await db.execute(text("DELETE FROM documents"))
        await db.execute(text("DELETE FROM users WHERE email LIKE 'phase3d_%'"))
        await db.commit()

    await engine.dispose()

    print_summary(summary)
    return 0


def print_summary(summary: dict) -> None:
    print()
    print("=" * 78)
    print("CHUNK STATISTICS")
    print("=" * 78)
    print(f"{'metric':28s} {'legacy':>14s} {'candidate':>14s}")
    a, c = summary["A"]["chunks"], summary["C"]["chunks"]
    for key in [
        "chunk_count", "tokens_min", "tokens_median", "tokens_p95", "tokens_mean",
        "tokens_max", "truncated_chunks", "encoder_truncation_rate",
        "table_chunks", "list_chunks", "heading_chunks",
    ]:
        print(f"{key:28s} {str(a.get(key)):>14s} {str(c.get(key)):>14s}")
    print(f"{'ingestion_ms':28s} {summary['A']['ingestion_ms']:>14.0f} {summary['C']['ingestion_ms']:>14.0f}")

    print()
    print("=" * 78)
    print("METRIC COMPARISON")
    print("=" * 78)
    keys = [
        "recall@1", "recall@3", "recall@5",
        "precision@1", "precision@3", "precision@5",
        "evidence_coverage", "answerability", "answer_exactness",
        "outcome_success_rate", "false_abstention_rate",
        "abstention_on_unsupported", "spurious_answers_on_unsupported",
        "duplicate_retrieval_rate", "context_utilisation",
        "reported_sources_avg", "omitted_sources_avg",
        "retrieval_ms_avg", "qa_ms_avg", "total_ms_avg",
    ]
    print(f"{'metric':32s} {'A legacy':>12s} {'B ctxfix':>12s} {'C cand':>12s}")
    for key in keys:
        av = summary["A"]["metrics"].get(key, 0)
        bv = summary["B"]["metrics"].get(key, 0)
        cv = summary["C"]["metrics"].get(key, 0)
        print(f"{key:32s} {av:>12.4f} {bv:>12.4f} {cv:>12.4f}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
