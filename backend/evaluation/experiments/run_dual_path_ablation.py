#!/usr/bin/env python3
"""Dual-path retrieval — ablation matrix A–D, measured on a labelled corpus.

Research code.  Run explicitly from ``backend/``:

    ./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py
    ./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py --corpus heading

Production alignment (P0 hardening)
-----------------------------------
Earlier revisions ingested the corpus with the **structure-v2** chunker while
production defaults to **legacy**, so the measurement did not describe the
deployed system.  This revision evaluates the **production configuration by
default**: the chunker comes from ``settings.chunker_version`` (production
default ``legacy``), chunks are built by the same
``documents.routes._build_chunk_objects`` production uses, the structure-element
graph is persisted for PDFs exactly as ``_process_document`` does, and variants
C/D run the **exact production retrieval composition**:

    retrieve_chunks (pgvector)
      -> retrieve_dual_path (heading/section seeds -> chunk-graph expansion -> RRF)
      -> brain.adapters._augment_with_structure (document_structure_elements stream)

Variant D adds the **real production evidence gate** (``brain.gate.evaluate``)
driven by a real ``ExecutionContext``/``EvidenceBundle`` — not a runner-local
threshold.

What it measures
----------------
  A  vector only                 — production semantic retrieval
  B  structure only              — production structural path, without vectors
  C  vector + structure          — exact production dual-path composition
  D  vector + structure + gate   — C plus the production evidence gate

Every number comes from the real pipeline (the production embedding model, the
structural graph in PostgreSQL and the trained QA model).  Nothing is simulated,
and B2 (vector + reranking) is deliberately absent — this runner uses
:mod:`evaluation.runner`, which reports B2 as ``not_measured`` because no
reranker exists in the project.

Metric granularity (read before comparing variants)
---------------------------------------------------
Gold evidence is **chunk-level** (derived from ingested chunk text), so the
retrieval metrics (Recall@K / Precision@K / MRR / nDCG@K) score **chunk-level**
evidence only.  The element-level structure stream carries
``document_structure_elements`` ids, which are not chunks and cannot match
chunk-level gold; including them in the retrieval ranking would depress
Precision@K for C/D for a reason unrelated to retrieval quality.  They are
therefore included in the **answer context** (as production does) but excluded
from the retrieval ranking.  Answer/grounding metrics are computed over the full
production context.

Gold labels
-----------
A question's gold chunk set is derived *after* ingestion by matching its
``evidence`` substrings against the ingested chunk text.  Gold labels are
therefore independent of every retrieval strategy being scored.

Corpus selection
----------------
``--corpus`` chooses the labelled corpus (default ``phase3d``):

  ``phase3d``  ``evaluation.datasets.phase3d_corpus`` (mixed DOCX/TXT/PDF)
  ``heading``  ``evaluation.datasets.heading_corpus`` (PDFs with real font-
               detected headings and sections that continue across pages)

Each corpus writes its own reports (``ablation_*`` vs ``ablation_heading_*``),
so the two measurements are never confused with each other.

A null result is acceptable and is reported as such.

Data safety
-----------
The run owns a single, dedicated user (``ablation_eval@test.local``).  All
setup and teardown deletes are scoped to that user id — the runner never issues
an unscoped ``DELETE`` and never touches another account's rows.

**Database isolation (required).**  The runner creates and deletes rows, so it
must target an explicitly isolated database:

    DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://…/documind_integration
    ./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py \
        --corpus phase3d --out /tmp/ablation_run_1

or ``--database-url <dsn>``, which takes precedence over the variable.  When
neither is set the application DSN is used — the behaviour that existed before —
and the safety guard then refuses to run, because the target is the application
database.  ``evaluation/isolation.py`` owns that check; it runs before the first
connection and refuses to guess when an identity cannot be established.

Reports are append-only.  ``--out`` is required and its files must not already
exist: a run never replaces a recorded report, and never writes into
``evaluation/reports/`` (the historical measurements).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from evaluation.artifacts import (  # noqa: E402
    MANIFEST_NAME,
    ArtifactExistsError,
    RunOutput,
    collect_run_manifest,
    model_provenance,
    new_run_id,
    write_manifest,
)
from evaluation.isolation import (  # noqa: E402
    UnsafeEvaluationTarget,
    assert_engine_matches_target,
    assert_disposal_authorized,
    assert_safe_evaluation_target,
    application_database_url,
    database_identity,
    describe_identity,
    display_dsn,
    evaluation_database_url,
)

# NOTE: ``storage.database`` is deliberately imported inside ``main()``, *after*
# the guarded evaluation DSN has been selected and placed in the environment.
# Importing it here would freeze the application's engine at import time and
# make the evaluated target unselectable.  The engine is still built by
# ``storage.database`` (so the ``sslmode`` -> ``ssl`` translation for asyncpg is
# the production code path) — it just points at the verified target.

EVAL_EMAIL = "ablation_eval@test.local"
TOP_K = 5

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


# ---------------------------------------------------------------------------
# Ingestion (production-aligned)
# ---------------------------------------------------------------------------

async def ingest_corpus(
    db: AsyncSession, user_id, corpus, chunker_version: str
) -> dict[str, dict]:
    """Ingest every corpus document the way production does.

    Reuses the production building blocks so the evaluated corpus is the one the
    deployed system would actually create:

    * ``documents.routes._build_chunk_objects`` — production chunk builder;
    * ``documents.parser.parse_pdf`` + ``documents.structure.replace_document_structure``
      — production Step 4, persisted for PDFs only;
    * ``graph.service.replace_document_graph`` — production Step 5;
    * ``embeddings.model.embed_texts`` — the production embedding model.

    Returns ``{document_name: {"document_id", "chunk_ids", "contents"}}``.
    """
    from documents.models import Document
    from documents.parser import parse_pdf
    from documents.processing import extract_text
    from documents.routes import _build_chunk_objects, _chunk_views
    from documents.structure import replace_document_structure
    from embeddings.model import embed_texts
    from graph.service import replace_document_graph
    from storage.file_store import save_upload

    summary: dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for doc in corpus:
            path = doc.write(directory)
            file_bytes = path.read_bytes()
            contents_elements = extract_text(path, doc.file_type)

            document = Document(
                id=uuid.uuid4(),
                user_id=user_id,
                name=doc.name,
                file_type=doc.file_type,
                file_size=len(file_bytes),
                stored_path=str(save_upload(file_bytes, doc.name, str(user_id))),
                chunker_version=chunker_version,
                chunk_count=0,
                status="ready",
                embedding_status="processing",
            )
            db.add(document)
            await db.flush()

            # --- Step 2 (production): chunk with the configured chunker ------
            chunk_objects = _build_chunk_objects(
                contents_elements, document.id, chunker_version, db
            )
            await db.flush()  # assigns chunk ids

            contents = [c.content for c in chunk_objects]
            embeddings = embed_texts(contents) if contents else []
            for index, obj in enumerate(chunk_objects):
                obj.embedding = embeddings[index] if index < len(embeddings) else None

            document.chunk_count = len(chunk_objects)
            document.embedding_status = "ready"
            await db.flush()

            # --- Step 4 (production): persist structure elements (PDF only) --
            if doc.file_type == "pdf":
                try:
                    parsed = parse_pdf(path)
                    await replace_document_structure(db, document.id, parsed)
                except Exception as exc:  # noqa: BLE001 — mirror production
                    print(f"    structure extraction failed for {doc.name}: {type(exc).__name__}")

            # --- Step 5 (production): build the chunk graph -------------------
            await replace_document_graph(db, document.id, _chunk_views(chunk_objects))

            summary[doc.name] = {
                "document_id": str(document.id),
                "chunk_ids": [str(c.id) for c in chunk_objects],
                "contents": contents,
            }

        await db.commit()

    return summary


# ---------------------------------------------------------------------------
# Labelled questions
# ---------------------------------------------------------------------------

def _category_for(question):
    """Map a corpus question kind onto the framework's question category."""
    from evaluation.schemas import QuestionCategory

    if question.kind == "table":
        return QuestionCategory.TABLE_DEPENDENT
    if question.kind == "section":
        return QuestionCategory.SECTION_DEPENDENT
    if question.kind == "cross_page":
        return QuestionCategory.PAGE_CROSS_PAGE
    return QuestionCategory.DIRECT


def build_questions(corpus, unsupported, ingested, acceptable=None) -> list:
    """Build ``EvalQuestion`` objects with evidence-derived gold chunk ids."""
    from evaluation.harness.corpus import get_acceptable_answers
    from evaluation.schemas import EvalQuestion, QuestionCategory

    questions = []
    for doc in corpus:
        info = ingested[doc.name]
        for question in doc.questions:
            gold_chunks: list[str] = []
            for chunk_id, content in zip(info["chunk_ids"], info["contents"]):
                body = norm(content)
                if question.evidence and any(norm(e) in body for e in question.evidence if e):
                    gold_chunks.append(chunk_id)

            accepted = get_acceptable_answers(question.qid)
            if acceptable:
                accepted = list(dict.fromkeys([*accepted, *acceptable.get(question.qid, [])]))
            candidates = [question.expected_answer, *accepted]
            gold_answers = tuple(dict.fromkeys([a for a in candidates if a]))

            questions.append(
                EvalQuestion(
                    question_id=question.qid,
                    question=question.text,
                    category=_category_for(question),
                    document_id=info["document_id"],
                    gold_answers=gold_answers,
                    gold_chunk_ids=tuple(gold_chunks),
                    answerable=bool(question.answerable),
                )
            )

    for question in unsupported:
        questions.append(
            EvalQuestion(
                question_id=question.qid,
                question=question.text,
                category=QuestionCategory.DIRECT,
                gold_answers=("__no_answer_expected__",),
                gold_chunk_ids=(),
                answerable=False,
            )
        )

    return questions


# ---------------------------------------------------------------------------
# Pipeline wiring
# ---------------------------------------------------------------------------

class Pipeline:
    """Retrieval + answer functions for one ablation variant.

    Retrieval is the **production** composition:

    * ``vector``    — ``chat.rag.retrieve_chunks`` (pgvector)
    * ``structure`` — ``chat.rag.retrieve_dual_path`` (structural candidates +
      RRF fusion) followed by ``brain.adapters._augment_with_structure``
      (the element-level ``document_structure_elements`` stream)
    * ``evidence_gate`` — the real ``brain.gate.evaluate`` over a real
      ``ExecutionContext``/``EvidenceBundle``
    """

    def __init__(self, db: AsyncSession, user_id, flags: dict[str, bool]):
        self.db = db
        self.user_id = str(user_id)
        self.flags = flags
        # Full production evidence per question, captured by ``retrieve`` and
        # consumed by ``answer`` (so retrieval is never paid for twice).
        self.evidence: dict[str, list] = {}

    async def retrieve(self, question) -> list[str]:
        from chat.rag import (
            retrieve_chunks,
            retrieve_dual_path,
            retrieve_structural_candidates,
        )

        vector, structure = self.flags["vector"], self.flags["structure"]

        if vector and not structure:
            chunks = await retrieve_chunks(
                self.db, self.user_id, question.question, top_k=TOP_K
            )
        elif structure and not vector:
            chunks = await retrieve_structural_candidates(
                self.db, self.user_id, question.question, limit=TOP_K
            )
        else:
            # --- Exact production composition --------------------------------
            from brain.adapters import _augment_with_structure

            semantic = await retrieve_chunks(
                self.db, self.user_id, question.question, top_k=TOP_K
            )
            fused = await retrieve_dual_path(
                self.db,
                self.user_id,
                question.question,
                top_k=TOP_K,
                semantic_chunks=semantic,
            )
            chunks = await _augment_with_structure(self.db, fused)

        self.evidence[question.question_id] = chunks
        # The retrieval ranking is chunk-level gold-scored: the element stream
        # is excluded here but retained for the answer context (see module doc).
        return [
            c.chunk_id
            for c in chunks
            if not str(c.chunk_id).startswith("structure:")
        ]

    def _gate_outcome(self, chunks, answer: str, score: float, grounded: bool):
        """Run the real production evidence gate over a real ExecutionContext."""
        from brain.gate import evaluate as gate_evaluate
        from brain.types import EvidenceBundle, ExecutionContext, QaResult, SourceRef

        sources = [
            SourceRef(
                chunk_id=c.chunk_id,
                content=c.content,
                score=float(c.score or 0.0),
                document_id=c.document_id,
                document_name=c.document_name,
                page=c.page,
                heading_path=c.heading_path,
                section=c.section,
                retrieval_path=c.retrieval_path or "semantic",
                fusion_score=c.fusion_score,
                structural_hops=c.structural_hops,
                structural_relation=c.structural_relation,
                structural_score=c.structural_score,
                evidence_kind=getattr(c, "evidence_kind", "chunk"),
            )
            for c in chunks
        ]
        bundle = EvidenceBundle(
            sources=sources,
            retrieval_scores=[float(c.score or 0.0) for c in chunks],
            qa_result=QaResult(answer=answer, score=float(score or 0.0), start=0, end=0),
            factual_grounded=bool(grounded),
        )
        return gate_evaluate(ExecutionContext(evidence=bundle, errors=[]))

    async def answer(self, question, chunk_ids: list[str]) -> dict:
        from chat.qa_model import answer_question
        from chat.rag import build_qa_context

        chunks = self.evidence.get(question.question_id, [])
        paths = [c.retrieval_path or "semantic" for c in chunks]
        hops = [c.structural_hops for c in chunks]

        pack = build_qa_context(chunks, question.question)
        context = str(pack)  # ContextPack subclasses str
        result = (
            answer_question(question.question, context)
            if context.strip()
            else {"answer": "", "score": 0.0}
        )
        answer = result.get("answer", "") or ""
        score = float(result.get("score", 0.0) or 0.0)
        grounded = bool(answer) and norm(answer) in norm(context)

        if self.flags["evidence_gate"]:
            from outcomes import Outcome

            outcome = self._gate_outcome(chunks, answer, score, grounded)
            if outcome == Outcome.INSUFFICIENT_EVIDENCE:
                return {
                    "answer": "",
                    "confidence": 0.0,
                    "insufficient_context": True,
                    "factual_grounded": False,
                    "supplied_chunk_ids": (),
                    "retrieval_paths": tuple(paths),
                    "structural_hops": tuple(hops),
                }

        return {
            "answer": answer,
            "confidence": score,
            "insufficient_context": not context.strip(),
            "factual_grounded": grounded,
            "supplied_chunk_ids": tuple(pack.included_ids),
            "retrieval_paths": tuple(paths),
            "structural_hops": tuple(hops),
        }


# ---------------------------------------------------------------------------
# Corpus selection / statistics / configuration record
# ---------------------------------------------------------------------------

CORPUS_CHOICES = ("phase3d", "heading", "structure_discriminating")


def load_corpus(name: str):
    """Return ``(corpus, unsupported, acceptable_answers, report_prefix)``."""
    if name == "heading":
        from evaluation.datasets import heading_corpus

        return (
            heading_corpus.build_corpus(),
            heading_corpus.unanswerable_questions(),
            heading_corpus.ACCEPTABLE_ANSWERS,
            "ablation_heading",
        )

    if name == "structure_discriminating":
        from evaluation.datasets import structure_discriminating_v1 as corpus_module

        corpus = corpus_module.build_corpus()
        acceptable = {
            q.qid: list(q.acceptable_answers)
            for q in corpus.questions
            if q.acceptable_answers
        }
        return (
            corpus,
            corpus_module.unanswerable_questions(),
            acceptable,
            "ablation_structure_discriminating",
        )

    from evaluation.datasets.phase3d_corpus import build_corpus, unanswerable_questions

    return build_corpus(), unanswerable_questions(), {}, "ablation"


def corpus_statistics(corpus, questions) -> dict:
    """Deterministic, path-free corpus statistics for the record."""
    categories: dict[str, int] = {}
    for question in questions:
        categories[question.category.value] = categories.get(question.category.value, 0) + 1
    return {
        "documents": len(corpus),
        "questions": len(questions),
        "answerable": sum(1 for q in questions if q.answerable),
        "unanswerable": sum(1 for q in questions if not q.answerable),
        "withGoldChunks": sum(1 for q in questions if q.gold_chunk_ids),
        "categories": dict(sorted(categories.items())),
    }


def production_configuration(chunker_version: str) -> dict:
    """Record the exact production configuration this run evaluates."""
    from brain import gate
    from brain.adapters import (
        STRUCTURE_EVIDENCE_MAX_DOCUMENTS,
        STRUCTURE_EVIDENCE_PER_DOCUMENT,
    )
    from chat import rag
    from config import get_settings
    from embeddings.model import get_dimensions
    from graph.service import MAX_HOPS

    settings = get_settings()
    return {
        "productionAligned": True,
        "chunker": {
            "configuredValue": settings.chunker_version,
            "resolvedVersion": chunker_version,
            "note": (
                "Production default is 'legacy' (chunk_text). Under legacy the "
                "chunk rows carry NULL heading_path/section, so heading/section "
                "seeding in the structural path is inert; the structure signal "
                "that remains active is the element-level stream."
            ),
        },
        "retrieval": {
            "topK": TOP_K,
            "rrfK": rag.RRF_K,
            "rrfSemanticWeight": rag.RRF_SEMANTIC_WEIGHT,
            "rrfStructuralWeight": rag.RRF_STRUCTURAL_WEIGHT,
            "semanticSeedCount": rag.SEMANTIC_SEED_COUNT,
            "structuralSeedLimit": rag.STRUCTURAL_SEED_LIMIT,
            "structuralCandidateLimit": rag.STRUCTURAL_CANDIDATE_LIMIT,
            "graphMaxHops": MAX_HOPS,
            "dualPathEnabled": rag.dual_path_enabled(),
            "elementStreamPerDocument": STRUCTURE_EVIDENCE_PER_DOCUMENT,
            "elementStreamMaxDocuments": STRUCTURE_EVIDENCE_MAX_DOCUMENTS,
            "composition": (
                "retrieve_chunks -> retrieve_dual_path (RRF) -> "
                "_augment_with_structure (element stream)"
            ),
        },
        "model": {
            "embeddingModel": "all-MiniLM-L6-v2",
            "embeddingDimensions": get_dimensions(),
            "qaModelPath": os.environ.get("QA_MODEL_NAME", "./models/documind-qa"),
        },
        "gate": {
            "implementation": "brain.gate.evaluate",
            "qaConfidenceStrong": gate.QA_CONFIDENCE_STRONG,
            "retrievalStrong": gate.RETRIEVAL_STRONG,
            "qaConfidenceNone": gate.QA_CONFIDENCE_NONE,
        },
    }


def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--corpus",
        choices=CORPUS_CHOICES,
        default="phase3d",
        help="labelled corpus to ingest and measure (default: phase3d)",
    )
    parser.add_argument(
        "--chunker",
        default="production",
        help="chunker to evaluate; 'production' uses settings.chunker_version",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "explicit evaluation database URL (Django-style DSN, e.g. "
            "postgresql+asyncpg://user:pass@host:port/db). Takes precedence over "
            "DOCUMIND_INTEGRATION_DATABASE_URL. Required in practice: without an "
            "isolated target the runner refuses to touch the application database."
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        help=(
            "directory for this run's artifacts (reports + run_manifest.json). "
            "Must be new or empty of colliding file names — evaluation artifacts "
            "are append-only and are never overwritten."
        ),
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    # --- 1. Evaluation target: explicit, guarded, never the application's -----
    # Resolved and proven different *before* any import that builds an engine
    # (``documents.models`` -> ``storage.database`` reads settings at import
    # time), and before the first connection.
    application_dsn = application_database_url()
    evaluation_dsn = evaluation_database_url(
        override=args.database_url, application_url=application_dsn
    )
    evaluation_identity = assert_safe_evaluation_target(
        evaluation_dsn,
        operation="the dual-path ablation run (it creates and deletes rows)",
        application_url=application_dsn,
    )
    # Validity (above) is not permission to destroy: the operator must also name this exact database.
    assert_disposal_authorized(
        evaluation_dsn,
        operation="the dual-path ablation run (it creates and deletes rows)",
        application_url=application_dsn,
    )
    application_identity = database_identity(application_dsn)
    print(f"[evaluation-db] application database : {describe_identity(application_identity)}")
    print(f"[evaluation-db] evaluation database  : {describe_identity(evaluation_identity)}")
    print(f"[evaluation-db] target (no credentials): {display_dsn(evaluation_dsn)}")
    os.environ["DATABASE_URL"] = evaluation_dsn

    # storage.database reads the settings once, at import.  Drop any cached value,
    # then require the effective setting to be the approved target before any
    # database-dependent module is imported.
    from config import get_settings

    get_settings.cache_clear()
    if get_settings().database_url != evaluation_dsn:
        raise RuntimeError(
            "the effective application settings name a different database than the "
            "approved evaluation target; refusing before any engine is built"
        )

    from documents.chunking import resolve_chunker_version
    from evaluation.runner import run_ablation, write_report
    from evaluation.schemas import ABLATION_MATRIX, Ablation

    if args.chunker == "production":
        chunker_version = resolve_chunker_version(get_settings().chunker_version)
    else:
        chunker_version = resolve_chunker_version(args.chunker)

    corpus, unsupported, acceptable, report_prefix = load_corpus(args.corpus)

    # --- 2. Output plan: reserve every artifact before the run starts ---------
    # A name collision must fail the whole run, not half-write it.
    run_id = new_run_id()
    output = RunOutput(args.out)
    report_names = [
        f"{report_prefix}_{name}.{ext}"
        for name in ("A", "B", "C", "D")
        for ext in ("json", "md")
    ]
    config_name = f"{report_prefix}_config.json"
    output.reserve(*report_names, config_name, MANIFEST_NAME)

    from auth.models import User  # noqa: F401
    from chat.models import ChatMessage, ChatSession  # noqa: F401
    from documents.models import Document, DocumentChunk  # noqa: F401
    from graph.models import DocumentGraphEdge  # noqa: F401
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401
    from storage.database import async_session, engine

    assert_engine_matches_target(engine, evaluation_dsn)

    from passlib.context import CryptContext

    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # --- 3. Run, then record what was measured ------------------------------
    run_result: dict = {"status": "incomplete"}
    dataset_record: dict | None = None
    configuration: dict | None = None
    model_record: dict | None = None

    try:
        async with async_session() as db:
            # --- scoped cleanup (this eval user only) ---
            existing = (
                await db.execute(select(User).where(User.email == EVAL_EMAIL))
            ).scalar_one_or_none()
            if existing is not None:
                await _delete_user_data(db, existing.id)
                await db.execute(delete(User).where(User.id == existing.id))
                await db.commit()

            user = User(
                id=uuid.uuid4(),
                email=EVAL_EMAIL,
                name="Ablation Eval",
                hashed_password=pwd.hash("TestPass123!"),
                is_active=True,
            )
            db.add(user)
            await db.flush()

            print("=" * 78)
            print("DUAL-PATH ABLATION A-D (production-aligned)")
            print(f"  corpus: {args.corpus} — {len(corpus)} documents, "
                  f"{len([q for d in corpus for q in d.questions])} answerable + "
                  f"{len(unsupported)} unsupported questions")
            print(f"  chunker: {chunker_version}")
            print("=" * 78)

            ingested = await ingest_corpus(db, user.id, corpus, chunker_version)
            total_chunks = sum(len(v["chunk_ids"]) for v in ingested.values())
            print(f"  ingested {total_chunks} chunks across {len(ingested)} documents")

            questions = build_questions(corpus, unsupported, ingested, acceptable)
            labelled = sum(1 for q in questions if q.gold_chunk_ids)
            print(f"  labelled questions with gold chunks: {labelled}/{len(questions)}")

            stats = corpus_statistics(corpus, questions)
            print(f"  corpus statistics: {json.dumps(stats, sort_keys=True)}")
            # Recorded in the run manifest.  ``version`` is reported as
            # unavailable rather than invented: the labelled corpora carry no
            # version constant.
            dataset_record = {
                "identifier": args.corpus,
                "version": "unavailable",
                "chunker": chunker_version,
                "goldChunkLabels": "derived after ingestion from question evidence substrings",
                **stats,
            }

            def build(variant: Ablation):
                pipeline = Pipeline(db, user.id, ABLATION_MATRIX[variant])
                return pipeline.retrieve, pipeline.answer

            reports = await run_ablation(build, questions, top_k=TOP_K)

            print()
            header = (
                f"  {'variant':<8} {'vec':>4} {'struct':>7} {'gate':>5} "
                f"{'R@5':>7} {'P@5':>7} {'MRR':>7} {'nDCG@5':>7} "
                f"{'EM':>6} {'F1':>6} {'ECov':>6} {'PathAgr':>8}"
            )
            print(header)
            for name in ("A", "B", "C", "D"):
                report = reports.get(name)
                if report is None:
                    continue
                m = report.metrics
                flags = ABLATION_MATRIX[Ablation(name)]
                print(
                    f"  {name:<8} "
                    f"{'Y' if flags['vector'] else 'n':>4} "
                    f"{'Y' if flags['structure'] else 'n':>7} "
                    f"{'Y' if flags['evidence_gate'] else 'n':>5} "
                    f"{m.get('recall@5', 0):>7.4f} {m.get('precision@5', 0):>7.4f} "
                    f"{m.get('mrr', 0):>7.4f} {m.get('ndcg@5', 0):>7.4f} "
                    f"{m.get('exact_match', 0):>6.4f} {m.get('token_f1', 0):>6.4f} "
                    f"{m.get('evidence_coverage', 0):>6.4f} "
                    f"{m.get('path_agreement', 0):>8.4f}"
                )

            # ``include_detail`` adds the per-question diagnostics (predicted /
            # expected answers, retrieved + supplied evidence with ranks, outcome
            # and failure attribution) that the aggregate metrics are means over.
            for name, report in reports.items():
                write_report(
                    report,
                    f"{report_prefix}_{name}",
                    out_dir=output,
                    include_detail=True,
                )
                print(f"\n  wrote {output.path(f'{report_prefix}_{name}.json')} (+ .md)")

            configuration = production_configuration(chunker_version)
            model_record = model_provenance(
                configuration["model"]["qaModelPath"],
                embedding_model=configuration["model"]["embeddingModel"],
                embedding_dimensions=configuration["model"]["embeddingDimensions"],
            )

            record = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "corpus": args.corpus,
                "corpusStatistics": stats,
                "ingestedChunkCount": total_chunks,
                "labelledQuestionCount": labelled,
                "productionConfiguration": configuration,
                "variants": {
                    "A": {"vector": True, "structure": False, "evidence_gate": False},
                    "B": {"vector": False, "structure": True, "evidence_gate": False},
                    "C": {"vector": True, "structure": True, "evidence_gate": False},
                    "D": {"vector": True, "structure": True, "evidence_gate": True},
                },
                "runId": run_id,
                "database": {
                    "evaluation": describe_identity(evaluation_identity),
                    "application": describe_identity(application_identity),
                },
                "reportPrefix": report_prefix,
            }
            output.write_json(config_name, record, reserved=True)
            print(f"  wrote {output.path(config_name)}")

            # --- scoped teardown ---
            await _delete_user_data(db, user.id)
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()

        run_result = {
            "status": "completed",
            "questions": len(questions),
            "reports": [f"{report_prefix}_{name}" for name in reports],
        }

    finally:
        # Written last and always: a run that fails still leaves a truthful
        # record (``status: failed`` + the exception type) instead of a bare
        # output directory.
        failure = sys.exc_info()[1]
        result = (
            {"status": "failed", "errorType": type(failure).__name__}
            if failure is not None
            else run_result
        )
        write_manifest(
            output,
            collect_run_manifest(
                run_id=run_id,
                runner="evaluation/experiments/run_dual_path_ablation.py",
                protocol=(
                    f"dual-path ablation A-D, production-aligned, corpus={args.corpus}, "
                    f"chunker={chunker_version}"
                ),
                output=output,
                result=result,
                database={
                    "evaluation": describe_identity(evaluation_identity),
                    "application": describe_identity(application_identity),
                    "isolated": True,
                    "operation": "creates and deletes rows for the runner's own eval user",
                },
                dataset=dataset_record,
                configuration=configuration,
                model=model_record or model_provenance(),
            ),
        )
        print(f"  wrote {output.path(MANIFEST_NAME)}")

    await engine.dispose()
    return 0


async def _delete_user_data(db: AsyncSession, user_id) -> None:
    """Delete only the eval user's rows (never an unscoped DELETE)."""
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(db, operation="dual-path ablation row cleanup")
    from documents.models import Document, DocumentChunk
    from graph.models import DocumentGraphEdge
    from graph.models import DocumentStructureEdge, DocumentStructureElement

    doc_ids = (
        await db.execute(select(Document.id).where(Document.user_id == user_id))
    ).scalars().all()
    if not doc_ids:
        return

    await db.execute(
        delete(DocumentStructureEdge).where(DocumentStructureEdge.document_id.in_(doc_ids))
    )
    await db.execute(
        delete(DocumentStructureElement).where(
            DocumentStructureElement.document_id.in_(doc_ids))
    )
    await db.execute(
        delete(DocumentGraphEdge).where(DocumentGraphEdge.document_id.in_(doc_ids))
    )
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
    )
    await db.execute(delete(Document).where(Document.id.in_(doc_ids)))
    await db.flush()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (UnsafeEvaluationTarget, ArtifactExistsError) as error:
        # A refused run is a clean stop, not a crash: one actionable,
        # credential-free line, and exit status 2.  Nothing was connected to and
        # nothing was written.
        print(f"\nERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error