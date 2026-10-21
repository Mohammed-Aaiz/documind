# DocuMind --- System Architecture

## 01. Architectural Goal

DocuMind follows a deterministic, evidence-first document intelligence
architecture.

Core pipeline:

UPLOAD → EXTRACT → CHUNK → EMBED → RETRIEVE → UNDERSTAND → ANSWER →
PROVIDE EVIDENCE → MEASURE RELIABILITY

The architecture favors explicit services and contracts over
uncontrolled agent autonomy.

## 02. High-Level Architecture

``` text
React + TypeScript + Vite
            │
            │ HTTP / JSON
            ▼
        FastAPI API
            │
    ┌───────┼───────────────┐
    ▼       ▼               ▼
  Auth   Documents        Brain
            │               │
            ▼               ▼
      Extraction        Retrieval
            │          ┌────┴─────┐
            ▼          ▼          ▼
        Chunking    pgvector   Graph
            │          │          │
            └──────────┬┴──────────┘
                       ▼
                 Evidence Fusion
                       │
                       ▼
                 Custom QA Model
                       │
                       ▼
               Evidence + Reliability
                       │
                       ▼
                  API Response
```

## 03. Backend

Technology: - Python - FastAPI - SQLAlchemy async - Alembic -
PostgreSQL - pgvector

Major feature areas: - auth - user (**ORM models only — no HTTP routes;
`/api/user/*` was removed**) - settings - documents - chat - embeddings -
brain - graph - reliability - verification - storage

## 04. Database

PostgreSQL is the application database.

pgvector is the production vector retrieval mechanism.

Alembic is the sanctioned schema-creation and migration path.

Migration history must remain a single linear chain.

## 05. Document Processing

Supported ingestion: - PDF - DOCX - TXT

Processing: 1. extraction; 2. structure-aware chunking; 3. embedding; 4.
graph construction; 5. persistence; 6. READY state.

Failure at a required stage prevents READY.

Document verdicts are computed from per-page coverage (Phase 1a):

-   `ready` — every page produced usable content, or the format has no
    pages;
-   `partial` — searchable, but at least one page produced no usable text;
-   `error` — no page produced usable content, or a stage raised.

The verdict exists in exactly one place, `_document_verdict` in
`backend/documents/routes.py`, and reads per-page facts measured in
`backend/documents/processing.py`. `partial` is never READY, and an
incomplete document is never reported as complete.

The page-usability threshold (approved by the owner on 2026-10-15 as
`MIN_USABLE_CHARS = 4`), its measured evidence, the unresolved reprocessing
data-loss risk and the isolated OCR readiness benchmark are recorded in
`backend/architecture/DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md`.
OCR is **NOT IMPLEMENTED** and no engine is selected: the benchmark measured a
candidate outside the repository and selects nothing. The threshold value, the
verdict rule and the `error` reason set must not change without owner approval.

## 06. Structure-Aware Chunking

Chunk metadata may include: - `heading_path` - `section` -
`element_type` - `chunker_version` - `token_count` - page information.

Preserve meaningful headings, lists, tables, and page/section
relationships without excessive fragmentation.

## 07. Dual-Path Retrieval

### Semantic path

``` text
Question
  ↓
Question embedding
  ↓
pgvector
  ↓
Top-K semantic chunks
```

### Structural path

``` text
Question / semantic seeds
  ↓
Document structure
  ↓
Graph traversal
  ↓
Structural candidates
```

Current document-native graph relations: - NEXT - PREV - SAME_PAGE -
SAME_SECTION

The graph does not require an external graph database or LLM.

## 08. Fusion

The current deterministic fusion approach is reciprocal-rank based.

Semantic and structural rankings are combined while preserving semantic
similarity, retrieval path, fusion score, structural hops, and
structural relation.

The fusion algorithm must not silently change without an explicit
design/experiment decision.

## 09. Brain

The Brain is deterministic orchestration:

``` text
Question
  ↓
Classify intent
  ↓
Plan
  ↓
Execute capability
  ↓
Gate evidence
  ↓
Produce response
```

Known document intents include DOCUMENT_QUESTION, DOCUMENT_SEARCH,
DOCUMENT_SUMMARY, and MEDIA_VERIFICATION.

Capability-unavailable states remain unavailable.

## 10. QA Model (current baseline vs. planned answer engine)

The project uses its own trained DistilBERT QA model:

`backend/models/documind-qa`

The model is an **extractive span** model. It is the **current production
answer engine and the permanent comparison baseline**, not the final
long-form answer solution. The model directory is read-only. No external
fallback model may be substituted.

**Grounded generative answering is an additive, PARTIALLY IMPLEMENTED path**
(2026-10-17, `DOCUMIND_PROJECT_CONTEXT.md` §0.8): local, offline
`google/flan-t5-base` in `backend/generation/`, exposed as
`POST /api/generation/answer`, sharing the production retrieval pipeline and
adding deterministic claim/citation verification. It does **not** replace the
extractive engine: `/api/chat/ask` is extractive by default and only uses the
generator when the request explicitly sets `"engine": "generative"`, in which
case it delegates to the same `generation.service` request path. The frontend
falls back to the extractive route with a visible notice when generation
returns 503.

Mark depth is produced deterministically rather than by prompting: 10 and 15 marks
add further *evidence sentences* (relevant, non-duplicate, entity-checked, each
cited) to the model's direct answer, measured at 17 / 49 / 73 mean words with
key-fact recall 0.62 / 0.77 / 0.93 (2026-10-17, `mark_depth_2026-10-17`). Depth is
bounded by evidence breadth, so where only one point is supported the formats
still coincide. Two limits remain architectural: the generator is still below the
extractive baseline on frozen P3 (EM 0.129 vs 0.157; F1 0.257 vs 0.387), and
verification is attribution rather than entailment.

Verification has two implementations behind one entry point
(`generation.verification.verify_with_mode`). The **default** is the lexical verifier
(word overlap + number/entity checks). An **opt-in** relation-aware verifier
(`generation/verification_relations.py`, `DOCUMIND_VERIFIER=relations`) adds a
three-way claim verdict (`SUPPORTED` / `CONTRADICTED` / `INSUFFICIENT_EVIDENCE`),
clause-wise support, and explicit guards against a universal claim, a causal claim, or
an added qualifier being accepted on word/semantic resemblance. It is measured
(`DOCUMIND_EVIDENCE_VERIFICATION_2026-10-17.md`) but **not** the default: on the frozen
benchmark it leaves EM and the spurious-answer rate unchanged, lowers token F1 by 0.027,
and lowers the unsupported-claim rate from 0.198 to 0.165. Neither verifier proves
factual correctness; `verified=true` means every claim is attributed to evidence that
contains it.
Hosted providers and data egress remain **not approved**; the architecture gate
is **NOT OPEN** (§59). Do not draw the generative path into the §02 diagram as
if it replaced the QA model.

The extractive pipeline's measured ceiling is recorded in §54.1/§54.5 and the
historical H1 record in §0.7.

## 11. Reliability

Reliability is based on actual retrieval, evidence, and QA signals.

Reliability persistence is implemented: the latest query snapshot is
upserted into the PostgreSQL `reliability_logs` table (one row per user,
migration `001_add_reliability_logs.py`) and read back by
`GET /api/reliability/last-query`, so it survives server restarts and is
consistent across workers.

Do not invent confidence.

## 12. Research Evaluation

Research evaluation is physically separated:

``` text
backend/evaluation/
├── datasets/
├── baselines/
├── experiments/
├── metrics/
└── reports/
```

Evaluation code is not production code and is not a pytest test suite.
It must be executed explicitly.

## 13. Test Architecture

``` text
backend/tests/
├── unit/
├── integration/
├── e2e/
├── fixtures/
└── conftest.py
```

Production modules must never import from tests.

## 14. Frontend

The frontend lives at repository root:

``` text
src/
```

Stack: - React 18 - TypeScript - Vite - Tailwind - Three.js - Material
Symbols

Central API client: `src/lib/api.ts`

There is no `frontend/` directory in the current architecture.

## 15. Security Boundaries

-   authentication is server-side;
-   ownership is derived from authenticated identity;
-   frontend IDs are untrusted;
-   secrets remain in `.env`;
-   trained model weights are read-only;
-   runtime uploads are not source-controlled;
-   SQL uses safe parameterized mechanisms;
-   user errors do not leak sensitive internals.

## 16. Architecture Change Rule

Before changing architecture: 1. inspect current implementation; 2.
identify contract changes; 3. identify consumers; 4. identify migration
implications; 5. identify test/evaluation impact; 6. implement the
smallest coherent change; 7. validate; 8. update architecture
documentation.

Do not refactor for aesthetics alone.

## 17. Direction Reset (2026-10-09)

The current agreed direction and the permanent **Phase 0–9** roadmap are in
[`DOCUMIND_PROJECT_CONTEXT.md`](./DOCUMIND_PROJECT_CONTEXT.md) **Part 0 (§0)**; the 2026-10-09
lecturer requirements, capability matrix and original Phase 0–7 roadmap remain preserved in
**Part II (§50–§63)**, with §57's numbering mapped by §0.4.1. Read Part 0 first, then the
Part II sections it references, before planning any architecture change. The historical
research record (populations, H1 metrics, F2/G/H1/H1-R/E0) is §0.7 and is **not** current
status.

Two clarifications that matter for architecture reading:

- The existing graph (§07) is a **document-native structure graph**, not a knowledge
graph. Entity–relation GraphRAG is **NOT IMPLEMENTED**.
- The architecture approval gate
(`backend/architecture/phase4f_6/decision/ARCHITECTURE_MIGRATION_GATE.md`) is
**NOT OPEN** — 0 of 10 criteria are fully met. Do not begin schema-changing or major
retrieval/model work without an approved ADR and gate review.
