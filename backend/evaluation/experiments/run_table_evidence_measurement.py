#!/usr/bin/env python3
"""Table-row evidence measurement — PHASE 4 (CONTROL vs TREATMENT).

Research code (EVALUATION_AGENT-owned).  Run explicitly from ``backend/``:

    ./venv/Scripts/python.exe evaluation/experiments/run_table_evidence_measurement.py

Goal
----
Measure whether the Phase 3 compact table-row evidence band
(``DOCUMIND_TABLE_EVIDENCE``) actually changes the real production QA outcome
for the teacher-demo document — nothing else is changed.

CONTROL
    ``DOCUMIND_TABLE_EVIDENCE=0`` — the pre-Phase-3 production behaviour.

TREATMENT
    ``DOCUMIND_TABLE_EVIDENCE=1`` — the Phase 3 behaviour.

Both arms run the **actual production retrieval/context/QA code path**:

    brain.adapters.retrieval_adapter     (semantic pgvector → dual-path RRF →
                                          structure augmentation → gated table
                                          band → band ordering)
    brain.adapters.context_adapter       (chat.rag.build_qa_context)
    brain.adapters.qa_adapter            (chat.qa_model.answer_question)

This is *not* the legacy A/B/C/D evaluation harness.  Production code is used
verbatim and is never modified to make the experiment work; the only handle the
experiment pulls is the existing kill switch.

Three clearly separated layers
------------------------------
* **real production code** — ``chat.rag``, ``brain.adapters``, ``graph.service``,
  ``documents.*`` (ingestion/projection), ``chat.qa_model``.  Read-only here.
* **evaluation harness** — this file: orchestration, tracing, hashing, metrics.
* **fixture / database setup** — an *isolated local* PostgreSQL + pgvector
  database (see ``Database`` below).  The remote Timescale database is never
  touched, and the running backend is never restarted.

Database
--------
Point the experiment at a local PostgreSQL + pgvector database via
``DOCUMIND_PHASE4_DATABASE_URL`` (default: ``Settings.database_url``).  The
runner **refuses to run against a non-loopback host**, so it can never write
ingestion rows into the remote/production database, and it refuses to run when
the ``document_table_rows`` schema (migration ``007``) is absent.  Schema is
created by the project's own linear migrations
(``python -m alembic upgrade head``) against that isolated database; the runner
does not create tables itself.

Determinism
-----------
The experiment is executed twice (two independent user/ingest/measure/teardown
cycles).  All ingested row ids are generated through a counter-seeded
``uuid5`` stand-in for ``uuid.uuid4`` inside a fixed-seed window, and the
embedding/QA models are warmed *before* that window (model loading consumes
``uuid4``).  Payloads are serialised with ``sort_keys=True`` and contain no
timestamps or elapsed times, so two runs are byte-identical; both runs are kept
in each artifact and compared directly.

Honesty
-------
No answer is inferred from an expected answer: the local model is invoked and
its raw output recorded.  Every field that cannot be measured is ``null`` with
a reason, never fabricated.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from evaluation import qa_metrics  # noqa: E402

# Import every ORM model so the mappers configure fully (the experiment uses the
# real ``User`` table for scoped setup/teardown).  Mirrors ``migrations/env.py``.
def _import_all_models() -> None:  # noqa: D401
    from auth.models import User  # noqa: F401
    from chat.models import ChatMessage, ChatSession  # noqa: F401
    from documents.models import (  # noqa: F401
        Document,
        DocumentChunk,
        DocumentTableRow,
    )
    from graph.models import (  # noqa: F401
        DocumentGraphEdge,
        DocumentStructureEdge,
        DocumentStructureElement,
    )
    from reliability.models import ReliabilityLog, SourceRef  # noqa: F401
    from user.models import UserSettings  # noqa: F401
    from verification.models import VerificationResult  # noqa: F401


REPORTS_DIR = Path(_BACKEND_DIR) / "evaluation" / "reports"
DEMO_PDF = (
    Path(_BACKEND_DIR).parent / "Field_Robotics_Deployment_and_Maintenance_Report.pdf"
)

#: Dedicated eval identity.  All setup/teardown deletes are scoped to this email.
EVAL_EMAIL = "phase4_table_evidence@eval.local"

#: Existing production kill switch (never modified by the experiment).
TABLE_EVIDENCE_ENV = "DOCUMIND_TABLE_EVIDENCE"

#: Local test-database override; falls back to ``Settings.database_url``.
EVAL_DB_ENV = "DOCUMIND_PHASE4_DATABASE_URL"

CONTROL = "CONTROL"
TREATMENT = "TREATMENT"

TOP_K = 5
RUNS = 2

#: The QA model's input window (asserted unchanged, never used to change it).
QA_WINDOW = 384

#: The five production questions and their accepted answers.  ``expected`` is the
#: set of answers a correct response may take; the primary form is first.
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "Q1",
        "text": (
            "What is the Kestrel frame calibrated against in the "
            "Sensor Calibration section?"
        ),
        "expected": ["reference rig"],
    },
    {
        "id": "Q2",
        "text": (
            "What calibration interval does the Maintenance Schedule give "
            "for the lidar array?"
        ),
        "expected": ["250 h", "250 operating hours", "every 250 operating hours",
                     "250 hours"],
    },
    {
        "id": "Q3",
        "text": (
            "According to Sensor Calibration and Power Management, which power "
            "rail supplies the inertial measurement unit?"
        ),
        "expected": ["primary battery rail", "battery rail"],
    },
    {
        "id": "Q4",
        "text": (
            "How long does the survey team wait after landing before "
            "initiating the lidar sweep?"
        ),
        "expected": ["four minutes", "4 minutes", "four minute"],
    },
    {
        "id": "Q5",
        "text": (
            "What maximum wind speed is permitted under the Safety Procedures?"
        ),
        "expected": ["12 metres per second", "12 meters per second", "12 m/s",
                     "12 metres/second"],
    },
]

CONTROL_REPORT = REPORTS_DIR / "table_evidence_measurement_control.json"
TREATMENT_REPORT = REPORTS_DIR / "table_evidence_measurement_treatment.json"
ANALYSIS_REPORT = REPORTS_DIR / "table_evidence_measurement_analysis.json"
MARKDOWN_REPORT = REPORTS_DIR / "table_evidence_measurement_report.md"

_DET_NAMESPACE = uuid.UUID("6f1c6ba7-5b67-4f5e-9f5c-0d5a2a9c0d1e")


# ---------------------------------------------------------------------------
# Deterministic serialisation / hashing
# ---------------------------------------------------------------------------

def canonical(obj: Any) -> str:
    """Deterministic JSON used for every machine-readable payload and hash."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_deterministic(path: Path, text: str) -> None:
    """Write ``text`` with LF newlines so the file bytes equal ``sha256_of(text)``.

    ``Path.write_text`` performs platform newline translation on Windows
    (``\\n`` → ``\\r\\n``), which would make the recorded SHA-256 disagree with
    the artifact's actual bytes.  The explicit ``newline="\\n"`` disables it.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class DeterministicUUIDs:
    """Counter-seeded ``uuid5`` stand-in for ``uuid.uuid4`` (see module docstring)."""

    def __init__(self, run_seed: str):
        self.run_seed = run_seed
        self.count = 0

    def __call__(self) -> uuid.UUID:
        self.count += 1
        return uuid.uuid5(_DET_NAMESPACE, f"{self.run_seed}:{self.count}")

    def __enter__(self):
        self._real = uuid.uuid4
        uuid.uuid4 = self
        return self

    def __exit__(self, *exc):
        uuid.uuid4 = self._real
        return False


# ---------------------------------------------------------------------------
# Database selection (isolated local test database only)
# ---------------------------------------------------------------------------

def _resolve_database_url() -> tuple[str, dict]:
    """Resolve and guard the evaluation target, then import storage.

    Each step runs before the next: an explicit target (no application fallback),
    the central isolation guard, the local-only check, export of the approved DSN
    with the settings cache cleared, and an effective-settings check.  Only then
    is ``storage.database`` imported, so the engine it builds uses the approved
    target.  No connection is opened here.
    """
    from config import get_settings
    from evaluation.isolation import (
        application_database_url,
        assert_disposal_authorized,
        assert_safe_evaluation_target,
        database_identity,
        describe_identity,
        evaluation_database_url,
    )

    explicit = os.environ.get(EVAL_DB_ENV)
    if explicit is None or not explicit.strip():
        raise SystemExit(
            f"REFUSING TO RUN: {EVAL_DB_ENV} must name an isolated database. The "
            "application database is never used as a fallback."
        )
    application_dsn = application_database_url()
    target = evaluation_database_url(override=explicit, application_url=application_dsn)
    identity = assert_safe_evaluation_target(
        target,
        operation=(
            "the table-row evidence measurement (it ingests a demo document and "
            "deletes its rows)"
        ),
        application_url=application_dsn,
    )
    _assert_local(target)
    print(
        "[evaluation-db] application database : "
        f"{describe_identity(database_identity(application_dsn))}"
    )
    print(f"[evaluation-db] evaluation database  : {describe_identity(identity)}")

    os.environ["DATABASE_URL"] = target
    get_settings.cache_clear()
    if get_settings().database_url != target:
        raise RuntimeError(
            "the effective application settings name a different database than the "
            "approved evaluation target; refusing before any engine is built"
        )

    from storage.database import _asyncpg_engine_args  # noqa: E402

    return _asyncpg_engine_args(target)


def _assert_local(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(
            "REFUSING TO RUN: the measurement database is not loopback "
            f"(host={host!r}).  This experiment ingests the demo document and "
            "must never write to a remote/production database.  Set "
            f"{EVAL_DB_ENV} to an isolated local PostgreSQL+pgvector database."
        )


async def _ensure_schema(engine) -> str:
    """Refuse to run unless the demo's table-row schema (007) is present."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        exists = await conn.scalar(
            text(
                "SELECT to_regclass('public.document_table_rows') IS NOT NULL"
            )
        )
        revision = None
        try:
            revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            revision = None
    if not exists:
        raise SystemExit(
            "REFUSING TO RUN: document_table_rows is missing.  Apply the project's "
            "linear migrations to the isolated local database first:\n"
            "  alembic upgrade head\n"
            f"(revision seen: {revision!r})"
        )
    return revision


# ---------------------------------------------------------------------------
# Ingestion (production-aligned)
# ---------------------------------------------------------------------------

async def warm_models() -> dict[str, Any]:
    """Load the embedding + QA models *before* the deterministic-id window."""
    from chat.qa_model import answer_question, is_model_available
    from embeddings.model import embed_texts

    embed_texts(["warmup"])
    available = bool(is_model_available())
    if available:
        answer_question("warmup question", "warmup context")
    return {"qa_model_available": available}


async def ingest_demo(db: AsyncSession, *, chunker_version: str) -> dict[str, Any]:
    """Ingest the teacher-demo PDF exactly as production does.

    Mirrors ``documents.processing`` + ``documents.routes``: the production
    legacy chunker, the production embedding model, the production parser
    (which now carries ``table_data``) and ``replace_document_structure`` (which
    persists ``document_table_rows``), plus ``replace_document_graph``.
    """
    from auth.models import User
    from documents.models import Document
    from documents.parser import parse_pdf
    from documents.processing import extract_text
    from documents.routes import _build_chunk_objects, _chunk_views
    from documents.structure import replace_document_structure
    from embeddings.model import embed_texts
    from graph.service import replace_document_graph
    from passlib.context import CryptContext

    if not DEMO_PDF.exists():
        raise SystemExit(f"teacher-demo PDF not found: {DEMO_PDF}")

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        id=uuid.uuid4(),
        email=EVAL_EMAIL,
        name="Phase 4 Table Evidence Eval",
        hashed_password=pwd_ctx.hash("Phase4-Eval-Password-1!"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    file_bytes = DEMO_PDF.read_bytes()
    contents_elements = extract_text(DEMO_PDF, "pdf")

    document = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        name=DEMO_PDF.name,
        file_type="pdf",
        file_size=len(file_bytes),
        # Reference the demo PDF in place: the experiment never needs a copy on
        # disk, and this deliberately avoids writing into ``backend/uploads/**``,
        # which is a read-only/forbidden path for every agent.
        stored_path=str(DEMO_PDF),
        chunker_version=chunker_version,
        chunk_count=0,
        status="ready",
        embedding_status="processing",
    )
    db.add(document)
    await db.flush()

    chunk_objects = _build_chunk_objects(
        contents_elements, document.id, chunker_version, db
    )
    await db.flush()

    contents = [c.content for c in chunk_objects]
    embeddings = embed_texts(contents) if contents else []
    for index, obj in enumerate(chunk_objects):
        obj.embedding = embeddings[index] if index < len(embeddings) else None

    document.chunk_count = len(chunk_objects)
    document.embedding_status = "ready"
    await db.flush()

    parsed = parse_pdf(DEMO_PDF)
    by_source = await replace_document_structure(db, document.id, parsed)
    await replace_document_graph(db, document.id, _chunk_views(chunk_objects))

    # Parsed table element(s) — for the provenance chain only (never fabricated).
    parsed_tables = [
        {
            "source_id": el.source_id,
            "sequence_index": el.sequence_index,
            "page_number": el.page_number,
            "heading_path": list(el.heading_path or ()),
            "table_row_count": len(el.table_data or []),
            "table_column_count": len(el.table_data[0]) if el.table_data else 0,
        }
        for el in parsed.elements
        if el.element_type == "table"
    ]

    await db.commit()

    return {
        "user_id": str(user.id),
        "document_id": str(document.id),
        "document_name": document.name,
        "chunker_version": chunker_version,
        "chunk_count": len(chunk_objects),
        "element_count": len(parsed.elements),
        "parser_version": parsed.parser_version,
        "parsed_tables": parsed_tables,
        "element_source_ids": {
            el.source_id: str(by_source[el.source_id].id)
            for el in parsed.elements
            if el.source_id in by_source
        },
    }


async def load_persisted_rows(db: AsyncSession, user_id: str, document_id: str) -> list[dict]:
    """Persisted ``document_table_rows`` via the production loader (read-only)."""
    from graph.service import load_table_rows

    rows = await load_table_rows(db, user_id, [document_id])
    return [
        {
            "row_id": str(r.id),
            "document_id": str(r.document_id),
            "table_element_id": str(r.table_element_id),
            "row_index": int(r.row_index),
            "is_header": bool(r.is_header),
            "header_repeated": bool(r.header_repeated),
            "cells": list(r.cells or []),
            "content": r.content or "",
            "page_number": r.page_number,
            "heading_path": list(r.heading_path or ()),
            "section": r.section,
            "token_count": r.token_count,
            "parser_version": r.parser_version,
        }
        for r in rows
    ]


async def teardown(db: AsyncSession) -> None:
    """Delete only the eval user's rows (FK cascade removes everything owned)."""
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(db, operation="table evidence row cleanup")
    from auth.models import User

    await db.execute(delete(User).where(User.email == EVAL_EMAIL))
    await db.commit()


# ---------------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------------

def _trace(ref) -> dict[str, Any]:
    return {
        "chunk_id": ref.chunk_id,
        "content": ref.content,
        "score": ref.score,
        "fusion_score": ref.fusion_score,
        "retrieval_path": ref.retrieval_path,
        "evidence_kind": getattr(ref, "evidence_kind", "chunk"),
        "document_id": ref.document_id,
        "document_name": ref.document_name,
        "page": ref.page,
        "section": ref.section,
        "heading_path": list(ref.heading_path or ()),
        "token_count": ref.token_count,
        "table_element_id": getattr(ref, "table_element_id", None),
        "row_index": getattr(ref, "row_index", None),
        "header_repeated": getattr(ref, "header_repeated", None),
    }


def _partition(refs: Sequence) -> tuple[list, list, list]:
    """Split the production evidence stream into its three bands, in order.

    Ranked chunks are ``evidence_kind == "chunk"`` (semantic / hybrid /
    chunk-level structural); table rows are ``"table_row"``; the unranked
    document-order tail is ``"structure_element"``.  The partition must
    reconstruct the stream exactly — that is what proves the band order.
    """
    ranked = [r for r in refs if getattr(r, "evidence_kind", "chunk") == "chunk"]
    rows = [r for r in refs if getattr(r, "evidence_kind", "chunk") == "table_row"]
    tail = [
        r for r in refs if getattr(r, "evidence_kind", "chunk") == "structure_element"
    ]
    if [*ranked, *rows, *tail] != list(refs):
        raise RuntimeError(
            "MEASUREMENT INTEGRITY ERROR: evidence bands are not contiguous in "
            "the documented order (ranked chunks → table rows → element tail)"
        )
    return ranked, rows, tail


def _count_text(text: str) -> int:
    from chat.rag import _count_text as count

    return count(text)[0]


def _path_counts(refs: Sequence) -> dict[str, int]:
    counts = {"semantic": 0, "structural": 0, "hybrid": 0}
    for ref in refs:
        if ref.retrieval_path in counts:
            counts[ref.retrieval_path] += 1
    return counts


# ---------------------------------------------------------------------------
# Per-question measurement (one arm)
# ---------------------------------------------------------------------------

async def measure_question(
    db: AsyncSession,
    *,
    user_id: str,
    question: dict[str, Any],
    arm: str,
    gate_open: bool,
    qa_available: bool,
) -> dict[str, Any]:
    """Run one (question, arm) through the real production path."""
    from brain.adapters import context_adapter, qa_adapter, retrieval_adapter
    from chat.rag import EVIDENCE_KIND_STRUCTURE_ELEMENT

    refs = await retrieval_adapter(
        db=db, user_id=user_id, cleaned_text=question["text"], top_k=TOP_K
    )
    ranked, rows, tail = _partition(refs)

    pack = await context_adapter(
        retrieval_sources=refs, cleaned_text=question["text"]
    )
    context_text = str(pack)
    included = set(pack.included_ids)

    # Band token accounting (tokens of items actually supplied to QA).
    ranked_tokens = sum(
        _count_text(r.content) for r in ranked if r.chunk_id in included
    )
    row_tokens = sum(_count_text(r.content) for r in rows if r.chunk_id in included)
    tail_tokens = sum(_count_text(r.content) for r in tail if r.chunk_id in included)
    omitted_row_tokens = sum(
        _count_text(r.content) for r in rows if r.chunk_id not in included
    )

    answer: dict[str, Any] = {
        "available": False,
        "text": None,
        "score": None,
        "start": None,
        "end": None,
        "reason": "qa model unavailable" if not qa_available else None,
    }
    if qa_available:
        result = await qa_adapter(cleaned_text=question["text"], context=context_text)
        answer = {
            "available": True,
            "text": result.answer,
            "score": result.score,
            "start": result.start,
            "end": result.end,
            "reason": None,
        }

    return {
        "question_id": question["id"],
        "question": question["text"],
        "arm": arm,
        "gate_state": "OPEN" if gate_open else "CLOSED",
        "gate_open": gate_open,
        "ranked_chunks": [_trace(r) for r in ranked],
        "ranked_path_counts": _path_counts(ranked),
        "table_rows": [_trace(r) for r in rows],
        "selected_table_row_ids": [r.chunk_id for r in rows],
        "element_tail": [_trace(r) for r in tail],
        "structure_element_kind": EVIDENCE_KIND_STRUCTURE_ELEMENT,
        "context": {
            "text": context_text,
            "sha256": sha256_of(context_text),
            "included_ids": list(pack.included_ids),
            "omitted_ids": list(pack.omitted_ids),
            "truncated_ids": list(pack.truncated_ids),
            "budget_tokens": int(pack.budget_tokens),
            "used_tokens": int(pack.used_tokens),
            "exact": bool(pack.exact),
        },
        "band_tokens": {
            "ranked_chunk_tokens": ranked_tokens,
            "table_row_tokens": row_tokens,
            "structure_tail_tokens": tail_tokens,
            "total_supplied_tokens": int(pack.used_tokens),
            "omitted_table_row_tokens": omitted_row_tokens,
        },
        "answer": answer,
    }


# ---------------------------------------------------------------------------
# One full run
# ---------------------------------------------------------------------------

async def run_once(engine, *, run_index: int, chunker_version: str) -> dict[str, Any]:
    from evaluation.isolation import assert_cleanup_execution_authorized

    assert_cleanup_execution_authorized(engine, operation="table evidence engine-taking execution")
    from brain.adapters import retrieval_adapter  # noqa: F401  (import guard)
    from chat.rag import table_gate_open
    from graph.service import terms_from_question

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        await teardown(db)

    warm = await warm_models()

    with DeterministicUUIDs(f"phase4-run"):
        async with session_factory() as db:
            info = await ingest_demo(db, chunker_version=chunker_version)
            rows = await load_persisted_rows(db, info["user_id"], info["document_id"])

            header_rows = [r["cells"] for r in rows if r["is_header"]]

            arm_payloads: dict[str, list[dict]] = {CONTROL: [], TREATMENT: []}
            for arm, value in ((CONTROL, "0"), (TREATMENT, "1")):
                os.environ[TABLE_EVIDENCE_ENV] = value
                for question in QUESTIONS:
                    terms = terms_from_question(question["text"])
                    gate_open = table_gate_open(header_rows, terms)
                    record = await measure_question(
                        db,
                        user_id=info["user_id"],
                        question=question,
                        arm=arm,
                        gate_open=gate_open,
                        qa_available=warm["qa_model_available"],
                    )
                    arm_payloads[arm].append(record)
            os.environ.pop(TABLE_EVIDENCE_ENV, None)

        await teardown(db)

    return {
        "run": run_index,
        "ingest": info,
        "persisted_rows": rows,
        "qa_model_available": warm["qa_model_available"],
        "control": arm_payloads[CONTROL],
        "treatment": arm_payloads[TREATMENT],
    }


# ---------------------------------------------------------------------------
# Assembly / analysis
# ---------------------------------------------------------------------------

def _ranked_signature(records: Sequence[dict]) -> list[tuple]:
    return [
        (
            r["chunk_id"],
            r["content"],
            r["score"],
            r["fusion_score"],
            r["retrieval_path"],
            r["evidence_kind"],
        )
        for r in records
    ]


def analyse(run: dict) -> dict[str, Any]:
    """Per-question CONTROL/TREATMENT comparison for one run."""
    control = {r["question_id"]: r for r in run["control"]}
    treatment = {r["question_id"]: r for r in run["treatment"]}

    per_question: list[dict[str, Any]] = []
    for question in QUESTIONS:
        qid = question["id"]
        c = control[qid]
        t = treatment[qid]

        ranked_identical = _ranked_signature(c["ranked_chunks"]) == _ranked_signature(
            t["ranked_chunks"]
        )
        tail_identical = [x["chunk_id"] for x in c["element_tail"]] == [
            x["chunk_id"] for x in t["element_tail"]
        ]
        context_identical = c["context"]["sha256"] == t["context"]["sha256"]

        c_ans = c["answer"]["text"] or ""
        t_ans = t["answer"]["text"] or ""
        c_exact = qa_metrics.exact_match_any(c_ans, question["expected"])
        t_exact = qa_metrics.exact_match_any(t_ans, question["expected"])
        c_f1 = qa_metrics.token_f1_any(c_ans, question["expected"])
        t_f1 = qa_metrics.token_f1_any(t_ans, question["expected"])

        c_incl = set(c["context"]["included_ids"])
        t_incl = set(t["context"]["included_ids"])
        # Ranked chunks must never be displaced by the table band.
        c_ranked_incl = [r["chunk_id"] for r in c["ranked_chunks"] if r["chunk_id"] in c_incl]
        t_ranked_incl = [r["chunk_id"] for r in t["ranked_chunks"] if r["chunk_id"] in t_incl]
        ranked_inclusion_identical = c_ranked_incl == t_ranked_incl

        if c_exact and not t_exact:
            result = "regressed"
        elif not c_exact and t_exact:
            result = "improved"
        else:
            result = "unchanged"

        per_question.append(
            {
                "question_id": qid,
                "question": question["text"],
                "expected_answers": question["expected"],
                "gate_state": t["gate_state"],
                "gate_open": bool(t["gate_open"]),
                "ranked_chunks_identical": ranked_identical,
                "ranked_path_counts_control": c["ranked_path_counts"],
                "ranked_path_counts_treatment": t["ranked_path_counts"],
                "ranked_inclusion_identical": ranked_inclusion_identical,
                "structure_tail_stream_identical": tail_identical,
                "structure_tail_offered_count_control": len(c["element_tail"]),
                "structure_tail_offered_count_treatment": len(t["element_tail"]),
                "control_context_tail_included": len(
                    [x for x in c["element_tail"] if x["chunk_id"] in c_incl]
                ),
                "treatment_context_tail_included": len(
                    [x for x in t["element_tail"] if x["chunk_id"] in t_incl]
                ),
                "table_rows_selected": len(t["table_rows"]),
                "table_rows_in_context": len(
                    [x for x in t["table_rows"] if x["chunk_id"] in t_incl]
                ),
                "table_rows_truncated": len(
                    [x for x in t["table_rows"] if x["chunk_id"] in t["context"]["truncated_ids"]]
                ),
                "context_identical": context_identical,
                "context_differs": not context_identical,
                "control_context_sha256": c["context"]["sha256"],
                "treatment_context_sha256": t["context"]["sha256"],
                "control_context_tokens": c["context"]["used_tokens"],
                "treatment_context_tokens": t["context"]["used_tokens"],
                "control_budget_tokens": c["context"]["budget_tokens"],
                "treatment_budget_tokens": t["context"]["budget_tokens"],
                "budget_within_window": (
                    c["context"]["budget_tokens"] <= QA_WINDOW
                    and t["context"]["budget_tokens"] <= QA_WINDOW
                ),
                "context_within_budget": (
                    c["context"]["used_tokens"] <= c["context"]["budget_tokens"]
                    and t["context"]["used_tokens"] <= t["context"]["budget_tokens"]
                ),
                "control_answer": c_ans,
                "treatment_answer": t_ans,
                "control_answer_available": c["answer"]["available"],
                "treatment_answer_available": t["answer"]["available"],
                "control_exact_match": c_exact,
                "treatment_exact_match": t_exact,
                "control_token_f1": round(c_f1, 6),
                "treatment_token_f1": round(t_f1, 6),
                "answer_changed": qa_metrics.normalize_text(c_ans)
                != qa_metrics.normalize_text(t_ans),
                "exact_match_delta": int(t_exact) - int(c_exact),
                "token_f1_delta": round(t_f1 - c_f1, 6),
                "result": result,
                "harmful_regression": bool(c_exact and not t_exact),
            }
        )
    return {"questions": per_question}


def compute_metrics(analysis: dict) -> dict[str, Any]:
    qs = analysis["questions"]
    n = len(qs)

    def rate(count: int) -> float:
        return round(count / n, 6) if n else 0.0

    def mean(values: Sequence[float]) -> float:
        return round(sum(values) / len(values), 6) if values else 0.0

    gate_open = sum(1 for q in qs if q["gate_open"])
    admitted = sum(1 for q in qs if q["table_rows_selected"] > 0)
    ctx_admitted = sum(1 for q in qs if q["table_rows_in_context"] > 0)
    selected_rows = [q["table_rows_selected"] for q in qs]
    row_tokens = [q["treatment_table_row_tokens"] for q in qs if q["table_rows_selected"] > 0]
    ranked_identity = sum(1 for q in qs if q["ranked_chunks_identical"])
    context_identity = sum(1 for q in qs if q["context_identical"])
    improvements = sum(1 for q in qs if q["result"] == "improved")
    regressions = sum(1 for q in qs if q["result"] == "regressed")
    harmful = sum(1 for q in qs if q["harmful_regression"])
    unchanged = sum(1 for q in qs if q["result"] == "unchanged")
    answer_changed = sum(1 for q in qs if q["answer_changed"])

    return {
        "question_count": n,
        "retrieval_context": {
            "gate_open_count": gate_open,
            "gate_open_rate": rate(gate_open),
            "table_row_admission_count": admitted,
            "table_row_admission_rate": rate(admitted),
            "table_row_qa_context_admission_count": ctx_admitted,
            "table_row_qa_context_admission_rate": rate(ctx_admitted),
            "avg_selected_table_rows": mean(selected_rows),
            "avg_table_row_token_count": mean(row_tokens),
            "ranked_chunk_identity_count": ranked_identity,
            "ranked_chunk_identity_rate": rate(ranked_identity),
            "context_identity_count": context_identity,
            "context_identity_rate": rate(context_identity),
        },
        "qa": {
            "control_exact_match_count": sum(1 for q in qs if q["control_exact_match"]),
            "treatment_exact_match_count": sum(1 for q in qs if q["treatment_exact_match"]),
            "control_exact_match_rate": rate(sum(1 for q in qs if q["control_exact_match"])),
            "treatment_exact_match_rate": rate(
                sum(1 for q in qs if q["treatment_exact_match"])
            ),
            "control_mean_token_f1": mean([q["control_token_f1"] for q in qs]),
            "treatment_mean_token_f1": mean([q["treatment_token_f1"] for q in qs]),
            "answer_changed_count": answer_changed,
            "answer_changed_rate": rate(answer_changed),
            "improvement_count": improvements,
            "regression_count": regressions,
            "harmful_regression_count": harmful,
            "unchanged_count": unchanged,
            "unchanged_rate": rate(unchanged),
        },
    }


def build_integrity(run: dict, analysis: dict) -> dict[str, Any]:
    """Aggregate the hard retrieval-integrity invariants for one run."""
    from chat.rag import (
        EVIDENCE_KIND_TABLE_ROW,
        RRF_K,
        RRF_SEMANTIC_WEIGHT,
        RRF_STRUCTURAL_WEIGHT,
    )

    qs = analysis["questions"]
    ranked_changed = any(not q["ranked_chunks_identical"] for q in qs)
    tail_changed = any(not q["structure_tail_stream_identical"] for q in qs)
    rows_added = any(q["table_rows_selected"] > 0 for q in qs)

    # No table row may carry an RRF fusion score, and every row must be
    # provenance-complete.
    rows_in_rrf: list[str] = []
    provenance_gaps: list[str] = []
    for record in run["treatment"]:
        for row in record["table_rows"]:
            if row["fusion_score"] is not None:
                rows_in_rrf.append(row["chunk_id"])
            if (
                row["evidence_kind"] != EVIDENCE_KIND_TABLE_ROW
                or not row["table_element_id"]
                or row["row_index"] is None
                or row["content"] is None
            ):
                provenance_gaps.append(row["chunk_id"])

    truncated_rows = any(q["table_rows_truncated"] > 0 for q in qs)
    context_within_budget = all(q["context_within_budget"] for q in qs)
    budget_within_window = all(q["budget_within_window"] for q in qs)

    return {
        "RRF_K": RRF_K,
        "RRF_SEMANTIC_WEIGHT": RRF_SEMANTIC_WEIGHT,
        "RRF_STRUCTURAL_WEIGHT": RRF_STRUCTURAL_WEIGHT,
        "rrf_config_unchanged": (
            RRF_K == 60
            and RRF_SEMANTIC_WEIGHT == 0.70
            and RRF_STRUCTURAL_WEIGHT == 0.30
        ),
        "rrf_changed": ranked_changed,
        "ranked_chunks_changed": ranked_changed,
        "table_rows_added": rows_added,
        "structure_tail_changed": tail_changed,
        "table_rows_in_rrf": rows_in_rrf,
        "table_rows_in_rrf_count": len(rows_in_rrf),
        "provenance_gaps": provenance_gaps,
        "provenance_gap_count": len(provenance_gaps),
        "table_rows_truncated": truncated_rows,
        "context_within_budget": context_within_budget,
        "budget_within_qa_window": budget_within_window,
    }


def build_provenance(run: dict) -> dict[str, Any]:
    """PDF → parsed table → persisted row → table element id chain (verified)."""
    ingest = run["ingest"]
    rows = run["persisted_rows"]
    persisted_by_key = {
        (r["table_element_id"], r["row_index"]): r for r in rows
    }
    chain: list[dict[str, Any]] = []
    for record in run["treatment"]:
        for row in record["table_rows"]:
            key = (row["table_element_id"], row["row_index"])
            persisted = persisted_by_key.get(key)
            chain.append(
                {
                    "question_id": record["question_id"],
                    "pdf": str(DEMO_PDF),
                    "parsed_tables": ingest["parsed_tables"],
                    "table_element_id": row["table_element_id"],
                    "persisted_row_id": persisted["row_id"] if persisted else None,
                    "row_index": row["row_index"],
                    "page": row["page"],
                    "section": row["section"],
                    "evidence_kind": row["evidence_kind"],
                    "header_repeated": row["header_repeated"],
                    "content": row["content"],
                    "content_equals_persisted": (
                        persisted is not None and persisted["content"] == row["content"]
                    ),
                    "cells_verbatim_in_content": (
                        persisted is not None
                        and all(
                            cell in row["content"]
                            for cell in persisted["cells"]
                            if cell
                        )
                    ),
                }
            )
    return {"source_chunks": chain}


def build_determinism(run_a: dict, run_b: dict) -> dict[str, Any]:
    a_control = canonical(run_a["control"])
    b_control = canonical(run_b["control"])
    a_treatment = canonical(run_a["treatment"])
    b_treatment = canonical(run_b["treatment"])
    return {
        "run1_equals_run2_control": a_control == b_control,
        "run1_equals_run2_treatment": a_treatment == b_treatment,
        "run1_equals_run2": a_control == b_control and a_treatment == b_treatment,
        "run1_control_sha256": sha256_of(a_control),
        "run2_control_sha256": sha256_of(b_control),
        "run1_treatment_sha256": sha256_of(a_treatment),
        "run2_treatment_sha256": sha256_of(b_treatment),
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    m = payload["metrics"]
    qs = payload["questions"]
    integ = payload["production_invariants"]
    det = payload["determinism"]
    rc = m["retrieval_context"]
    qa = m["qa"]

    lines.append("# Table-Row Evidence Measurement — Phase 4")
    lines.append("")
    lines.append(
        "Production-behaviour measurement of the Phase 3 compact table-row "
        "evidence band on the teacher-demo document. **Not** a statistically "
        "powered research claim: five questions, one document."
    )
    lines.append("")
    lines.append("## Experiment")
    lines.append("")
    lines.append(f"- Control: `{TABLE_EVIDENCE_ENV}=0`")
    lines.append(f"- Treatment: `{TABLE_EVIDENCE_ENV}=1`")
    lines.append(f"- Teacher-demo PDF: `{DEMO_PDF.name}`")
    lines.append(f"- Questions: {', '.join(q['question_id'] for q in qs)}")
    lines.append(f"- Database: isolated local PostgreSQL+pgvector (revision "
                 f"{payload['database']['revision']})")
    lines.append("- Production path: `brain.adapters.retrieval_adapter` → "
                 "`context_adapter` → `qa_adapter`")
    lines.append("")
    lines.append("## Per-question results")
    lines.append("")
    lines.append("| Q | Gate | Rows | In ctx | Context identical | Control ans | Treatment ans | Exact Δ | Result |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for q in qs:
        lines.append(
            f"| {q['question_id']} | {q['gate_state']} | {q['table_rows_selected']} | "
            f"{q['table_rows_in_context']} | {q['context_identical']} | "
            f"`{q['control_answer']}` | `{q['treatment_answer']}` | "
            f"{q['exact_match_delta']:+d} | {q['result']} |"
        )
    lines.append("")
    lines.append("## Retrieval integrity")
    lines.append("")
    lines.append(f"- RRF (K/weights): {integ['RRF_K']} / "
                 f"{integ['RRF_SEMANTIC_WEIGHT']} / {integ['RRF_STRUCTURAL_WEIGHT']} "
                 f"(unchanged: {integ['rrf_config_unchanged']})")
    lines.append(f"- RRF_CHANGED = {integ['rrf_changed']}")
    lines.append(f"- RANKED_CHUNKS_CHANGED = {integ['ranked_chunks_changed']}")
    lines.append(f"- TABLE_ROWS_ADDED = {integ['table_rows_added']}")
    lines.append(f"- STRUCTURE_TAIL_CHANGED = {integ['structure_tail_changed']}")
    lines.append(f"- table rows in RRF: {integ['table_rows_in_rrf_count']}")
    lines.append(f"- provenance gaps: {integ['provenance_gap_count']}")
    lines.append(f"- table rows truncated: {integ['table_rows_truncated']}")
    lines.append("")
    lines.append("## Context budget")
    lines.append("")
    for q in qs:
        lines.append(
            f"- {q['question_id']}: budget {q['treatment_budget_tokens']}, "
            f"ranked {q['control_ranked_chunk_tokens']}→{q['treatment_ranked_chunk_tokens']} tok, "
            f"table row {q['treatment_table_row_tokens']} tok, tail "
            f"{q['control_structure_tail_tokens']}→{q['treatment_structure_tail_tokens']} tok, "
            f"total {q['control_context_tokens']}→{q['treatment_context_tokens']} tok, "
            f"omitted row tok {q['omitted_table_row_tokens']}"
        )
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append(f"- Gate-open: {rc['gate_open_count']}/{m['question_count']} "
                 f"({rc['gate_open_rate']})")
    lines.append(f"- Table-row admission: {rc['table_row_admission_count']}/"
                 f"{m['question_count']} ({rc['table_row_admission_rate']})")
    lines.append(f"- QA-context admission: {rc['table_row_qa_context_admission_count']}/"
                 f"{m['question_count']} ({rc['table_row_qa_context_admission_rate']})")
    lines.append(f"- Avg selected rows: {rc['avg_selected_table_rows']}; "
                 f"avg row tokens: {rc['avg_table_row_token_count']}")
    lines.append(f"- Ranked-chunk identity: {rc['ranked_chunk_identity_count']}/"
                 f"{m['question_count']} ({rc['ranked_chunk_identity_rate']})")
    lines.append(f"- Context identity: {rc['context_identity_count']}/"
                 f"{m['question_count']} ({rc['context_identity_rate']})")
    lines.append(f"- Exact match: control {qa['control_exact_match_count']}/"
                 f"{m['question_count']}, treatment {qa['treatment_exact_match_count']}/"
                 f"{m['question_count']}")
    lines.append(f"- Improvements: {qa['improvement_count']}; regressions: "
                 f"{qa['regression_count']}; harmful regressions: "
                 f"{qa['harmful_regression_count']}; unchanged: {qa['unchanged_count']}")
    lines.append("")
    lines.append("## Determinism")
    lines.append("")
    lines.append(f"- Run 1 == Run 2: {det['run1_equals_run2']}")
    lines.append(f"- Control SHA-256: `{payload['shas']['control']}`")
    lines.append(f"- Treatment SHA-256: `{payload['shas']['treatment']}`")
    lines.append(f"- Analysis SHA-256: `{payload['shas']['analysis']}`")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    for item in payload["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"## Final status: {payload['final_status']}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def amain() -> dict[str, Any]:
    from evaluation.isolation import assert_engine_matches_target  # noqa: E402

    url, connect_args = _resolve_database_url()
    # Validity is not permission to destroy: the operator must also name this exact database.
    from evaluation.isolation import assert_disposal_authorized as _authorize_disposal  # noqa: E402
    from evaluation.isolation import application_database_url as _application_dsn  # noqa: E402

    _authorize_disposal(
        url,
        operation="the table-row evidence measurement (it ingests a demo document and deletes its rows)",
        application_url=_application_dsn(),
    )
    _import_all_models()

    engine = create_async_engine(url, echo=False, pool_pre_ping=True,
                                 connect_args=connect_args)
    assert_engine_matches_target(engine, url)
    try:
        revision = await _ensure_schema(engine)
        from config import get_settings

        chunker_version = get_settings().chunker_version

        print("=" * 72)
        print("TABLE-ROW EVIDENCE MEASUREMENT — PHASE 4")
        print("=" * 72)
        print(f"database      : {urlsplit(url).hostname}:{urlsplit(url).port or 5432}"
              f"/{urlsplit(url).path.lstrip('/')}")
        print(f"revision      : {revision}")
        print(f"chunker       : {chunker_version}")
        print(f"demo pdf      : {DEMO_PDF}")
        print(f"control       : {TABLE_EVIDENCE_ENV}=0")
        print(f"treatment     : {TABLE_EVIDENCE_ENV}=1")
        print("")

        runs: list[dict] = []
        for index in (1, 2):
            print(f"--- run {index}/{RUNS} ---")
            run = await run_once(engine, run_index=index,
                                 chunker_version=chunker_version)
            runs.append(run)
            print(f"run {index}: ingested {run['ingest']['chunk_count']} chunks, "
                  f"{run['ingest']['element_count']} elements, "
                  f"{len(run['persisted_rows'])} table rows; "
                  f"QA model available={run['qa_model_available']}")
    finally:
        await engine.dispose()

    run_a, run_b = runs[0], runs[1]

    analysis_a = analyse(run_a)
    analysis_b = analyse(run_b)

    # Leaf-level per-question band token counts (needed by the budget analysis
    # and by the metrics that average table-row tokens).
    for q in analysis_a["questions"]:
        qid = q["question_id"]
        control_rec = next(r for r in run_a["control"] if r["question_id"] == qid)
        treatment_rec = next(r for r in run_a["treatment"] if r["question_id"] == qid)
        q["control_ranked_chunk_tokens"] = control_rec["band_tokens"]["ranked_chunk_tokens"]
        q["treatment_ranked_chunk_tokens"] = treatment_rec["band_tokens"]["ranked_chunk_tokens"]
        q["treatment_table_row_tokens"] = treatment_rec["band_tokens"]["table_row_tokens"]
        q["control_structure_tail_tokens"] = control_rec["band_tokens"]["structure_tail_tokens"]
        q["treatment_structure_tail_tokens"] = treatment_rec["band_tokens"]["structure_tail_tokens"]
        q["omitted_table_row_tokens"] = treatment_rec["band_tokens"]["omitted_table_row_tokens"]

    metrics = compute_metrics(analysis_a)
    integrity = build_integrity(run_a, analysis_a)
    provenance = build_provenance(run_a)
    determinism = build_determinism(run_a, run_b)

    control_payload = {
        "experiment": "table_evidence_measurement",
        "arm": CONTROL,
        "kill_switch": {TABLE_EVIDENCE_ENV: "0"},
        "questions": [q["id"] for q in QUESTIONS],
        "qa_model_available": run_a["qa_model_available"],
        "runs": {"1": run_a["control"], "2": run_b["control"]},
    }
    treatment_payload = {
        "experiment": "table_evidence_measurement",
        "arm": TREATMENT,
        "kill_switch": {TABLE_EVIDENCE_ENV: "1"},
        "questions": [q["id"] for q in QUESTIONS],
        "qa_model_available": run_a["qa_model_available"],
        "runs": {"1": run_a["treatment"], "2": run_b["treatment"]},
    }

    control_text = canonical(control_payload)
    treatment_text = canonical(treatment_payload)
    control_sha = sha256_of(control_text)
    treatment_sha = sha256_of(treatment_text)

    limitations: list[str] = []
    if not run_a["qa_model_available"]:
        limitations.append(
            "The DocuMind QA model was unavailable; answers are null, not fabricated."
        )
    limitations.append(
        "This is a five-question teacher-demo measurement on one document; it is "
        "not a statistically powered claim, not evidence of general table "
        "reasoning, and not proof of production-wide improvement."
    )
    limitations.append(
        "Measured on an isolated local PostgreSQL+pgvector database with the "
        "production schema (migration 007). The remote Timescale database was "
        "not migrated and the running backend was not restarted, so this is not "
        "a measurement of the live remote stack."
    )

    # --- stop conditions -------------------------------------------------
    q3 = next(q for q in analysis_a["questions"] if q["question_id"] == "Q3")
    blocked = (
        not q3["context_identical"]
        or integrity["ranked_chunks_changed"]
        or not integrity["rrf_config_unchanged"]
        or integrity["table_rows_in_rrf_count"] > 0
        or integrity["table_rows_truncated"]
        or not integrity["provenance_gap_count"] == 0
        or not integrity["budget_within_qa_window"]
        or not determinism["run1_equals_run2"]
    )
    final_status = "BLOCKED" if blocked else "PASS"

    limitations.append(
        "Q2's decoded answer depends on the local extractive DistilBERT QA model; "
        "the Phase 3/4 guarantee is that the compact row reaches the QA *input* "
        "whole and within budget, which is measured directly."
    )

    analysis_payload = {
        "experiment": "table_evidence_measurement",
        "database": {
            "host": urlsplit(url).hostname,
            "port": urlsplit(url).port or 5432,
            "database": urlsplit(url).path.lstrip("/"),
            "revision": revision,
            "isolated_local": True,
        },
        "ingest": {
            "chunker_version": run_a["ingest"]["chunker_version"],
            "chunk_count": run_a["ingest"]["chunk_count"],
            "element_count": run_a["ingest"]["element_count"],
            "parser_version": run_a["ingest"]["parser_version"],
            "persisted_table_row_count": len(run_a["persisted_rows"]),
            "parsed_tables": run_a["ingest"]["parsed_tables"],
        },
        "production_invariants": integrity,
        "questions": analysis_a["questions"],
        "metrics": metrics,
        "retrieval_integrity": {
            "RRF_CHANGED": integrity["rrf_changed"],
            "RANKED_CHUNKS_CHANGED": integrity["ranked_chunks_changed"],
            "TABLE_ROWS_ADDED": integrity["table_rows_added"],
            "STRUCTURE_TAIL_CHANGED": integrity["structure_tail_changed"],
        },
        "provenance": provenance,
        "determinism": determinism,
        "shas": {"control": control_sha, "treatment": treatment_sha},
        "limitations": limitations,
        "final_status": final_status,
    }

    analysis_text = canonical(analysis_payload)
    analysis_sha = sha256_of(analysis_text)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_deterministic(CONTROL_REPORT, control_text)
    _write_deterministic(TREATMENT_REPORT, treatment_text)
    _write_deterministic(ANALYSIS_REPORT, analysis_text)
    # The analysis file's own SHA cannot live inside the bytes it hashes without
    # being circular; it is therefore reported in the Markdown report and on the
    # terminal (the .json holds the control/treatment SHAs only).
    analysis_payload["shas"]["analysis"] = analysis_sha
    _write_deterministic(MARKDOWN_REPORT, render_markdown(analysis_payload))

    print("")
    print("=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"gate open / 5            : {metrics['retrieval_context']['gate_open_count']}")
    print(f"rows admitted / 5        : {metrics['retrieval_context']['table_row_admission_count']}")
    print(f"rows in QA context / 5   : {metrics['retrieval_context']['table_row_qa_context_admission_count']}")
    print(f"ranked-chunk identity  /5: {metrics['retrieval_context']['ranked_chunk_identity_count']}")
    print(f"context identity / 5     : {metrics['retrieval_context']['context_identity_count']}")
    print(f"exact match control/trt  : {metrics['qa']['control_exact_match_count']}/"
          f"{metrics['qa']['treatment_exact_match_count']}")
    print(f"improve/regress/harmful  : {metrics['qa']['improvement_count']}/"
          f"{metrics['qa']['regression_count']}/{metrics['qa']['harmful_regression_count']}")
    print(f"Q3 context identical     : {q3['context_identical']}")
    print(f"Q3 answers control/trt   : {q3['control_answer']!r} / {q3['treatment_answer']!r}")
    print(f"determinism run1==run2   : {determinism['run1_equals_run2']}")
    print(f"shas: control={control_sha[:16]} treatment={treatment_sha[:16]} "
          f"analysis={analysis_sha[:16]}")
    print(f"artifacts written to     : {REPORTS_DIR}")
    print(f"FINAL STATUS             : {final_status}")

    return analysis_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    asyncio.run(amain())


if __name__ == "__main__":
    main()
