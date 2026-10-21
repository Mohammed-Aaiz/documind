# DocuMind --- Product Requirements Document

## 01. Purpose

DocuMind is a production-oriented multimodal, structure-aware document
analysis and question-answering system.

The product must ingest real PDF, DOCX, and TXT documents; preserve
meaningful document structure; retrieve evidence using semantic and
structural signals; expose evidence and reliability signals honestly; and
remain traceable, testable, secure, and measurable.

**Answer generation — current vs target (do not conflate).** The engine
implemented today is the project's own trained DistilBERT **extractive** QA
model. **Grounded generative AI is the DECIDED primary answer engine** for the
product (with 5-, 10- and 15-mark academic answer requirements), but it is
**PLANNED and NOT IMPLEMENTED** — see §07 and
`DOCUMIND_PROJECT_CONTEXT.md` §0.1 / §0.4 Phase 2–3. Nothing in this PRD
authorizes building it.

The research contribution is not merely GraphRAG. The intended
contribution is a structure-aware dual-path evidence retrieval framework
combining semantic retrieval with document-structure traversal to
improve evidence sufficiency and traceability for structure-dependent
and multi-hop document questions.

## 02. Problem

Traditional document QA commonly reduces documents to plain text, chunks
them, embeds chunks, and performs dense vector retrieval. This can lose
useful relationships among headings, sections, pages, tables, figures,
and neighboring evidence.

DocuMind addresses this through document-native structure and two
evidence paths: 1. semantic/vector retrieval; 2. structure-aware
traversal.

The system must prove whether this improves evidence sufficiency and
answer quality through controlled evaluation rather than assuming
improvement.

## 03. Target Users

### Primary

-   students and researchers working with academic documents;
-   professionals who need grounded answers from internal documents;
-   users who need traceable evidence rather than unsupported generated
    answers.

### Secondary

-   project evaluators and researchers studying document retrieval and
    QA;
-   developers extending the document intelligence pipeline.

## 04. Product Scope

### In scope

-   authentication and user ownership;
-   document upload, processing, listing, detail, deletion, and
    reprocessing;
-   PDF/DOCX/TXT extraction;
-   structure-aware chunking;
-   384-dimensional sentence-transformer embeddings;
-   PostgreSQL + pgvector retrieval;
-   document-native graph edges;
-   dual-path retrieval and deterministic fusion;
-   custom DistilBERT QA model (the **current extractive baseline**);
-   evidence/provenance signals;
-   reliability state and diagnostics;
-   research evaluation and ablation infrastructure;
-   five approved product pages.

### Out of scope unless explicitly approved

-   arbitrary autonomous agent behavior inside the product;
-   external LLM fallback when the local QA model is unavailable;
-   grounded generative answering, the 5-/10-/15-mark answer engine and
    knowledge-graph GraphRAG **until their phases are authorized**
    (`DOCUMIND_PROJECT_CONTEXT.md` §0.4, §59, §61) — recording them as
    direction is not authorization;
-   FAISS or SQLite as production retrieval substitutes;
-   a graph database;
-   fake media verification;
-   invented confidence, retrieval, or evaluation metrics;
-   additional UI pages without approval.

## 05. Product Pages

Exactly five pages are currently approved: 1. Login 2. Home / AI
Workspace 3. Media Verification 4. Reliability Center 5. Settings /
Account

Do not add pages without explicit approval.

## 06. Core User Flow

UPLOAD → EXTRACT → CHUNK → EMBED → RETRIEVE → UNDERSTAND → ANSWER →
PROVIDE EVIDENCE → MEASURE RELIABILITY

## 07. Functional Requirements

### Authentication

-   real email/password authentication;
-   JWT-based sessions;
-   authenticated ownership checks;
-   user-owned resources scoped by authenticated identity.

### Ingestion

-   process supported document formats;
-   persist document metadata and chunks;
-   generate embeddings;
-   construct structure-aware graph edges;
-   mark READY only after complete processing succeeds;
-   mark ERROR on processing failure;
-   support reprocessing.

### Retrieval

Production retrieval uses PostgreSQL + pgvector.

Semantic path: question → embedding → pgvector → ranked chunks.

Structural path: question/semantic seeds → document structure → graph
traversal → structural candidates.

Fusion remains deterministic and preserves provenance metadata.

### Answer Generation

**CURRENT (implemented).** Use the project's own trained DistilBERT QA model at
`backend/models/documind-qa`. It is an **extractive span** model: it returns a
span from retrieved evidence, not a composed long-form answer. If unavailable,
report unavailable. Never substitute another model or hardcode an answer. Its
trained weights are read-only and must not be modified.

**TARGET (DECIDED, PLANNED — not implemented, not authorized).** Grounded
generative answering is the intended **primary** engine
(`DOCUMIND_PROJECT_CONTEXT.md` §0.1, §0.4 Phase 2). The required workflow is:
question analysis → retrieval-query rewrite where justified → evidence
retrieval (semantic + structural) → evidence selection/ranking → context
construction → generation → claim verification against evidence → citation/
provenance → abstain when evidence is insufficient → record reliability.
Retries are bounded; repeated generation is not proof of correctness.

**Academic answer formats (DECIDED, PLANNED).** The product must support three
meaningfully different formats, driven by answer planning rather than word
count: **5 marks** = concise, complete coverage of the essential concepts;
**10 marks** = developed explanation with structure and supporting detail;
**15 marks** = comprehensive treatment with deeper analysis and relevant
subsections. Marks are not a universal word count and do not guarantee an
examiner score.

### Reliability

Reliability output must use actual evidence and model/retrieval signals.
No fabricated confidence or source information.

### Media Verification

If unavailable, the UI and API must show the real unavailable state.

## 08. Research Requirements

Primary question:

> Does combining semantic vector retrieval with document-structure
> traversal improve evidence sufficiency and answer quality for
> structure-dependent and multi-hop document questions compared with
> vector-only retrieval?

Comparison families: 1. Vector-only retrieval 2. Structure-only
retrieval 3. Dual-path retrieval 4. Dual-path retrieval with evidence
gating, when implemented

Metrics may include Recall@K, Precision@K, MRR, nDCG, Exact Match, token
F1, answer accuracy, evidence coverage, unsupported answer rate, factual
grounding, path agreement, retrieval latency, graph latency, and total
latency.

No expected result may be presented as measured.

## 09. Non-Functional Requirements

### Security

Enforce authentication and authorization server-side, scope user-owned
resources, validate inputs, protect secrets, avoid unsafe dynamic SQL,
and do not expose internal stack traces.

### Reliability

Use deterministic orchestration where possible, explicit
unavailable/failed states, reproducible evaluation, and versioned
processing provenance.

### Performance

Avoid unnecessary heavyweight ML loading and preserve measurable latency
without weakening correctness.

### Maintainability

Use clear module ownership, no production imports from tests, migrations
as the sanctioned schema path, and minimal coherent changes.

## 10. Definition of Done

A feature is done only when the requirement is implemented, current
architecture was inspected, ownership boundaries were respected,
production/test/evaluation separation is intact, appropriate validation
passes, security implications were considered, actual evidence is
reported, unavailable functionality remains unavailable, and affected
documentation/contracts are updated.

## 11. Lecturer Feedback and Redefined Direction (2026-10-09)

The lecturer raised concerns about usefulness, answer reliability, answer
completeness, mathematical reasoning, scanned-document support, and overall
technical direction. The requirements are recorded verbatim in
`DOCUMIND_PROJECT_CONTEXT.md` Part II §51 and are summarised here as product
direction (all **PLANNED** unless the repository proves otherwise):

- grounded generative answering that is complete but never invents unsupported facts;
- exam-style answers for **5-, 10- and 15-mark** questions, controlled by answer planning,
  not by answer length;
- an evaluated mathematical reasoning path using deterministic calculation tools;
- OCR and layout-aware ingestion for scanned pages, tables, charts and multicolumn text;
- separate treatment of **content extraction** vs **document-manipulation detection**
  (OCR, retrieval and GraphRAG cannot prove authenticity);
- dense retrieval combined with knowledge-graph relationship traversal for multi-hop
  questions, designed as evidence-grounded retrieval, not a reasoning guarantee;
- measured local hardware and inference requirements, with no external model API fallback.

The current capability status (implemented / partial / unverified / planned / blocked /
absent) is the matrix in `DOCUMIND_PROJECT_CONTEXT.md` **Part II §55** (labels: §63). The
roadmap is **Part 0 §0.4 — Phase 0–9** (Phase 0, baseline reproduction, first); the original
Phase 0–7 roadmap in §57 is preserved and mapped by §0.4.1. **No roadmap phase is authorized
by this PRD.** The historical research record these phases build on (populations P1/P2/P3,
H1 metrics, F2/G/H1/H1-R/E0) is preserved in **§0.7** and is **HISTORICAL**, not current
measurement.
