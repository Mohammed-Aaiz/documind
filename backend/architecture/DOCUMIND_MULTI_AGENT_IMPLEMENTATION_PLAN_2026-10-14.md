# DOCUMIND — MULTI-AGENT ENGINEERING PROGRAM: PHASE 0 RECONNAISSANCE AND IMPLEMENTATION PLAN

**Report ID:** `DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN`
**Date:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Kind:** Phase 0 reconnaissance and planning only. **No production code, schema, dependency, frontend, or configuration was modified.** Nothing was installed, no model was downloaded, no migration was run, no commit was made.
**Predecessor:** `backend/architecture/DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md` (this plan re-verified that audit's findings before relying on them — §1.2)
**Integrity:** the digest is recorded on its own line immediately below. That line is excluded from its own hash, so the value stays reproducible after substitution:

Report SHA-256: `464d517763a32586ee3e28f8d258ef9bd659185cb7abbb21a115838df90546fc`

---

## 1. Verified Current State

### 1.1 Repository baseline (recorded before any inspection command that could write)

| Item | Value |
| --- | --- |
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged changes | **0** |
| Unstaged (tracked) modifications | **330** (pre-existing; not attributable to this work) |
| Untracked files | **717** at baseline — this already includes the predecessor audit report; creating this plan raises the count to **718** (the only change this execution makes) |
| Required output path status | **Free** — `architecture/DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_2026-10-14.md` did not exist, so nothing was overwritten |
| Python | **3.11.0** (`backend/venv/Scripts/python.exe`) |
| Dataset volume already present | `backend/uploads/` holds **1126** entries (read-only; untouched) |
| Free disk | ~81 GB on `C:` |

**Runtime packages already installed and relevant to this plan:** `torch 2.13.0`, `transformers 5.16.1`, `torchvision 0.28.0`, `onnxruntime 1.30.0`, `sentence-transformers 6.0.1`, `numpy 2.4.6`, `scipy 1.17.1`, `pillow 12.3.0`, `pymupdf 1.28.2`, `faster-whisper 1.2.1`, `pgvector 0.5.0`, `sqlalchemy 2.0.36`, `alembic 1.14.1`, `asyncpg 0.30.0`, `fastapi 0.115.6`.

**Runtime packages that are absent (this is the crux of the plan):** `pytesseract`, `tesserocr`, `easyocr`, `paddleocr`, `ocrmypdf`, `docling`, `unstructured`, `rapidocr_onnxruntime`, `openai`, `anthropic`, `litellm`, `ollama`, `graphviz`, `matplotlib`, `mermaid` — **all confirmed absent by `find_spec`** (§1.2).

### 1.2 Independent re-verification of the predecessor audit

Every load-bearing finding was re-checked in this execution with fresh fixtures in a single `tempfile.mkdtemp(prefix="documind_phase0_")` directory (removed afterwards; `temp removed: True`).

| # | Audit finding | Re-verification method | Observed result this execution | Status |
| --- | --- | --- | --- | --- |
| 1 | Scanned PDFs are not OCR'd | `extract_text(image_only.pdf, "pdf")` | **0 elements** | **CONFIRMED** |
| 2 | Mixed PDFs silently lose scanned pages | `extract_text(mixed.pdf, "pdf")` (page 1 digital text + ruled table; page 2 image-only) | element types `{heading: 1, paragraph: 1, table: 1}`, **pages `[1]`** — page 2 absent, no warning | **CONFIRMED** |
| 3 | PDF image blocks are skipped | source inspection of `documents/processing.py` | branch `if block.get("type") == 1` **present** | **CONFIRMED** |
| 4 | No OCR code in the extractor | token search in `documents/processing.py` | `tesseract`/`ocr`/`get_images`/`extract_image`/`get_pixmap` **all False** | **CONFIRMED** |
| 5 | `figure` is declared but never produced | `documents.parser.EMITTED_ELEMENT_TYPES` | `['paragraph', 'section', 'table', 'text_block']` — no `figure` | **CONFIRMED** |
| 6 | No OCR / generative / diagram capability installed | `find_spec` over 15 module names | **all False** | **CONFIRMED** |
| 7 | Answers are single extracted spans | `chat.qa_model.answer_question(...)` on a 5-sentence context | "Which embedding model does DocuMind use?" → `all-MiniLM-L6-v2`, score 0.4523, **16 chars** | **CONFIRMED** |
| 8 | Unsupported questions produce no scorable answer | same call, "What is the capital of France?" | returned a question-echo span with **score 0.0** | **CONFIRMED** |
| 9 | Context window is 384 tokens | `get_max_input_length()` | **384** | **CONFIRMED** |

The audit's findings therefore stand against the current repository. The audit's three "not verified / blocked" items (live end-to-end citation correctness, live end-to-end abstention, frontend runtime behaviour) are also unchanged: no PostgreSQL instance is reachable and no live server was started in this execution.

### 1.3 What already exists and must **not** be rebuilt

The system is not a stub. The plan reuses:

* **Hardened upload** — extension allowlist (`pdf|docx|txt`), magic-byte/MIME validation, empty + size rejection, SHA-256 dedupe, UUID user-scoped storage, orphan cleanup on DB failure, READY only after every step succeeds, ERROR otherwise, stale-PROCESSING recovery (`documents/routes.py:336-465`).
* **Six-step ingestion pipeline** — extract → chunk → embed → structure elements (PDF) → structural graph → READY (`documents/routes.py:180-320`).
* **Structured extraction** — PyMuPDF text with bounding-box read order, `find_tables()` cell grids, heading heuristics, DOCX styles/tables/lists, TXT with Markdown headings (`documents/processing.py`).
* **Typed parser boundary** — `documents/parser.py` with `ParsedElement`/`ParsedDocument`, deterministic `source_id`, hierarchy via `parent_source_id`, and a **`figure` element type already declared in the public vocabulary**.
* **Persistence** — `documents`, `document_chunks` (with `page`, `heading_path`, `section`, `element_type`, `chunker_version`, `token_count`, 384-dim `embedding`), `document_structure_elements` (with `element_type`, `page_number`, `bbox_x0..y1`, `parser_version`), `document_structure_edges`, `document_graph_edges`, `document_table_rows` (per-row cells, `is_header`, `header_repeated`), `reliability_logs`, `user_settings`, `verification_results`, `chat_sessions`, `chat_messages`.
* **Two chunkers** — legacy (default, `CHUNKER_VERSION=legacy`) and structure-aware `chunk_elements` with `table_atomic` / `table_rows` strategies.
* **Retrieval** — pgvector cosine, structural candidate expansion, Reciprocal Rank Fusion, token-budgeted context assembly, `DOCUMIND_TABLE_EVIDENCE` gated row band, provenance-rich `SourceOut`.
* **Evidence gate** — SUCCESS / PARTIAL / INSUFFICIENT_EVIDENCE / UNAVAILABLE / FAILED with a non-invented zero-confidence abstention rule (`brain/gate.py`).
* **Reliability Center data** — real measured signals persisted per query.
* **Storage containment primitives** — `storage/file_store.py` (`save_upload`, `delete_upload`, `cleanup_new_file`) with symlink/reparse-point refusal and root containment.
* **Tests** — 61 unit files, 23 integration files, 6 browser E2E files (1368 / 275 / 6 collected).
* **Deployment** — `compose.yaml` (db + backend + frontend, loopback-only API, `no-new-privileges`, healthchecks), `backend/Dockerfile` (python:3.11-slim + `libgomp1`, models mounted read-only at `/app/models`), `Dockerfile.frontend` (Vite build → nginx).

### 1.4 Confirmed capability status (five-value vocabulary, no inflation)

| Capability | Status | Basis |
| --- | --- | --- |
| Digital PDF / DOCX / TXT ingestion | **IMPLEMENTED AND VERIFIED** | executed probe + 1619 passing tests |
| Table extraction (cells/rows) | **IMPLEMENTED AND VERIFIED** (extraction) / **PARTIALLY IMPLEMENTED** (retrieval: row band default-OFF) | probe recovered a 3×2 and 4×3 grid |
| Heading/section structure, page provenance | **IMPLEMENTED AND VERIFIED** | probe + unit/integration tests |
| Retrieval, RRF, context budgeting, abstention | **IMPLEMENTED** / end-to-end **IMPLEMENTED BUT UNVERIFIED** | needs PostgreSQL + live server |
| Page-level citations | **IMPLEMENTED BUT UNVERIFIED** (end-to-end) | code path complete; live check blocked |
| Scanned PDF / OCR | **NOT IMPLEMENTED** | executed probe: 0 elements |
| Mixed PDF completeness | **PARTIALLY IMPLEMENTED — silently lossy** | executed probe: page 2 dropped, document still reaches `ready` |
| Figures / diagrams in documents | **NOT IMPLEMENTED** | image blocks skipped; `figure` never emitted |
| Figure captions as figure metadata | **NOT IMPLEMENTED** | captions survive only as ordinary paragraph text |
| Equations / math notation | **NOT IMPLEMENTED** | no math library, no notation path |
| Mark-wise answers (6/8/10/15) | **NOT IMPLEMENTED** | no request field, no UI, extractive model |
| Diagram requirement detection | **NOT IMPLEMENTED** | no detector |
| New diagram generation / rendering | **NOT IMPLEMENTED** | no generator, no renderer, no renderer dependency |
| Live end-to-end verification | **BLOCKED** | no PostgreSQL; fail-closed DB create guard |

---

## 2. Existing-Component Reuse Matrix

**Rule applied:** extend what exists; introduce something new only where the audit proved nothing exists. "New" in this table means a new module, never a second competing pipeline.

| Capability needed | Existing component to reuse | Decision | Notes / limits |
| --- | --- | --- | --- |
| Per-page text extraction | `documents/processing.py:extract_pdf` page loop | **Extend** | the loop already iterates pages; add a per-page completeness decision inside it |
| Scanned-page detection | `page.get_text("dict")`/`("text")` results | **Extend** | decide "insufficient text" from real extracted characters, not from file-level heuristics |
| OCR engine invocation | *nothing exists* | **New** (`documents/ocr.py`) | must be an adapter behind one interface so the engine is a configuration decision, not a rewrite |
| Page extraction record | `document_structure_elements.page_number`, `DocumentStructureInsights.pagesRepresented/pageCount` | **Extend** + likely one additive table | reuse the existing per-page provenance fields; a per-page OCR record is additive |
| Table cell/row evidence | `documents/processing.py:find_tables()`, `documents/tables.py`, `document_table_rows` (migration `007`) | **Reuse as-is** | already faithful and tested; the gap is retrieval default, not extraction |
| Figure extraction | `documents/processing.py` image-skip branch; `page.get_images()`/`get_pixmap()` (PyMuPDF, already pinned) | **Extend** | replace the unconditional skip with enumeration + persistence |
| Figure element type | `documents/parser.py:ELEMENT_TYPE_FIGURE`, `graph/models.py:ELEMENT_TYPE_FIGURE` | **Reuse** | the vocabulary already exists; emit it rather than inventing a new one |
| Caption association | extracted text blocks with bounding boxes | **Extend** | geometric association (nearest caption below/above) using PyMuPDF boxes already collected |
| Figure asset storage | `storage/file_store.py` containment primitives | **Extend** | needs a new read/serve path; `delete_upload` containment rules are the model to follow |
| Equation preservation | *nothing exists* | **New** (`documents/equations.py`) | must not claim understanding; only preserve what the source gives |
| Canonical representation | `ExtractedElement` → `ParsedElement` → ORM rows | **Reuse** | extend fields; do **not** add a parallel document model |
| Chunking integration | `documents/chunking.py:chunk_elements` (structure-v2) and legacy `chunk_text` | **Reuse** | enablement of structure-v2 is an evidence-based decision, not a prerequisite |
| Embedding/indexing | `embeddings/model.py` (`all-MiniLM-L6-v2`, 384-d) | **Reuse unchanged** | OCR text enters the existing chunk→embed path; no new embedding model |
| Retrieval | `chat/rag.py` (pgvector + structural + RRF + bands) | **Extend** | add a `figure` evidence source and preserve `extractionMethod` provenance |
| Context assembly | `chat/rag.py` token budgeting + `chat/qa_model.py:get_max_input_length` | **Reuse** for extractive | the generative path needs its **own** budget function (Contract D) |
| Answer orchestration | `brain/` (classify → plan → retrieve → context → QA → gate → outcome) | **Extend** | a new capability adapter, not a new orchestrator |
| Marks handling | `chat/routes.py:AskRequest` + `src/lib/api.ts:apiAskQuestion` | **Extend** | add one validated field; regenerate types |
| Extractive QA | `chat/qa_model.py`, `answer_span.py` | **Reuse as grounding/verification layer** | its 384-token/100-token limits stay; it does not become the long-form generator |
| Generation model | `.env.example` already reserves `LLM_API_KEY` / `LLM_MODEL` | **New adapter** (approval) | the reserved config surface already exists; nothing reads it |
| Diagram detection | `brain/classifier.py` (transparent rule-based intents) | **Extend** | keep the inspectable style; record the trigger |
| Diagram rendering | *nothing exists* | **New** (approval) | prefer the option needing no system binary (see §8.3) |
| Answer/citation UI | `WorkspacePage.tsx`, `WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts` | **Extend** | existing loading/empty/error patterns and source trail already exist |
| Settings depth control | `settings/routes.py`, `SettingsPage.tsx`, `WorkspaceContext` | **Extend or remove** | currently persisted but unused by the answer path; must not remain a decorative control |
| Evaluation corpora | `evaluation/datasets/`, `evaluation/harness/`, `evaluation/experiments/` | **Extend** | builds on the existing corpus/rubric conventions |
| Deployment | `compose.yaml`, `backend/Dockerfile`, `Dockerfile.frontend` | **Extend** | an OCR choice with a system binary would require Dockerfile OS packages |

**Explicitly rejected by this plan:** a second parser, a second retrieval pipeline, a FAISS/SQLite substitute, an external fallback for the existing QA path, a mock/stub "diagram generator", or any fabricated capability reporting.

---

## 3. Specialist-Agent Responsibilities

The repository defines nine real agents (`agents/*.md`). The programme's ten roles below are **mapped onto those agents**; several user-listed specialists are grouped, and each keeps a distinct deliverable and a distinct reviewer.

| Programme role | Executing agent(s) in this repo | Responsibility completed | Must not do |
| --- | --- | --- | --- |
| **AGENT 0** Engineering Coordinator | `COORDINATOR` | orchestration, ownership resolution, dependency tracking, approval gates, integration, final reporting, this plan | modify application implementation, tests, `.env`, or weights (`agents/coordinator.md`) |
| **AGENT 1** Repository & Architecture Auditor | `COORDINATOR` + `VERIFIER` (read-only) | architecture/dependency map, reuse matrix, gap confirmation, risk register, sequence | write production code during recon |
| **AGENT 2** Ingestion & OCR Engineer | `BACKEND_AGENT` (schema parts to `DATABASE_AGENT`) | per-page detection, OCR adapter, mixed-PDF completeness, honest status, page provenance | touch `chat/**`, `brain/**`, `graph/**`, migrations, frontend (`agents/backend-agent.md`) |
| **AGENT 3** Structure & Multimodal Extraction Engineer | `BACKEND_AGENT` + `DATABASE_AGENT` (models/migration) | canonical representation, tables/figures/captions/equations, bbox, extraction-quality metadata | create a competing document model; add a second parser |
| **AGENT 4** Retrieval & Evidence Engineer | `AI_AGENT` | index OCR text, figure/table evidence, provenance survival, abstention, retrieval-vs-answer separation | replace pgvector; touch ORM models/migrations |
| **AGENT 5** Exam Answer Generation Engineer | `AI_AGENT` (+ `BACKEND_AGENT` for any new HTTP surface) | model decision record, mark-aware generation, grounding, abstention, answer evaluation | download weights, add a paid service, or bypass the gate without approval |
| **AGENT 6** Diagram Intelligence Engineer | `AI_AGENT` (detection, retrieval-in-answer) + `BACKEND_AGENT` (render service, new module) | detection, existing-figure retrieval, generation, validation, safe rendering | present diagram source as a rendered diagram; allow unsafe markup |
| **AGENT 7** Frontend & Product Integration Engineer | `FRONTEND_AGENT` | marks selector, exam-answer rendering, figures/diagrams, citations, OCR/partial warnings, a11y | touch `backend/**`, add decorative controls, unsafe HTML rendering |
| **AGENT 8** Testing, Evaluation & Security Engineer | `TEST_AGENT` (tests) + `EVALUATION_AGENT` (evaluation) + `SECURITY_AGENT` (independent audit; remediation routed to the owning agent) | the §10 plan, executed suites, metrics, independent security findings | edit production implementation to make tests pass (`agents/security-agent.md`) |
| **Independent verification** | `VERIFIER` (owns nothing) | verify changed files, actual test execution, real behaviour, limitations | write any file |

**Non-negotiable coordination rules carried from the programme contract:** one writer per file at a time; interfaces agreed before parallel work; **no database schema change until separately approved**; the Coordinator reviews cross-agent dependencies before integration; no agent introduces a competing parsing/retrieval/model architecture; integration is tested against the real implementation, never against an agent's summary.

---

## 4. File Ownership Matrix

Ownership follows the repository's own contracts exactly. **No ownership change is proposed here without an explicit approval item (§13).**

| # | Proposed change | Owner | Files | Interfaces affected | Depends on | Tests owned by | Reviewer | Approval? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-1 | Per-page extraction status + OCR adapter | `BACKEND_AGENT` | `backend/documents/ocr.py` *(new)*, `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/requirements.txt` | internal extractor API; `Document.status`; `DocumentOut` | C-2 schema decision only if a page table is added | `TEST_AGENT` | `SECURITY_AGENT` (untrusted documents), `VERIFIER` | **YES** — dependency install + model provisioning (§8.1) |
| C-2 | Per-page OCR provenance persistence | `DATABASE_AGENT` | `backend/documents/models.py`, `backend/migrations/versions/008_*.py` *(new)* | ORM model; migration head | — | `TEST_AGENT` | `COORDINATOR` + `VERIFIER` | **YES** — schema change |
| C-3 | Figure/image extraction + caption association + asset storage | `BACKEND_AGENT` (+ `DATABASE_AGENT` for any column) | `backend/documents/figures.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py`, `backend/documents/routes.py`, `backend/storage/file_store.py` | `ParsedElement` (emit `figure`); new asset-serve route | C-2 pattern | `TEST_AGENT` | `SECURITY_AGENT` (path traversal, tenant isolation), `VERIFIER` | **YES** if a column/table is added |
| C-4 | Equation preservation | `BACKEND_AGENT` | `backend/documents/equations.py` *(new)*, `backend/documents/processing.py`, `backend/documents/parser.py` | element vocabulary (no new type unless approved) | C-3 | `TEST_AGENT` | `VERIFIER` | NO (if no schema/element-type change) |
| C-5 | Canonical representation field extensions | `DATABASE_AGENT` | `backend/documents/models.py`, migration | ORM + API schemas | C-2 | `TEST_AGENT` | `COORDINATOR` | **YES** — schema change |
| C-6 | Figure/OCR evidence in retrieval | `AI_AGENT` | `backend/chat/rag.py`, `backend/graph/service.py`, `backend/chat/routes.py`, `backend/brain/adapters.py` | `SourceChunk`, `SourceOut`, `AskResponse` | C-1, C-3 | `TEST_AGENT` | `VERIFIER` | NO |
| C-7 | Marks request field + validation | `AI_AGENT` | `backend/chat/routes.py` | `AskRequest`, `AskResponse` | C-8 decision | `TEST_AGENT` | `VERIFIER` | **YES** — behaviour/contract change |
| C-8 | Generation model adapter + answer composition | `AI_AGENT` | `backend/chat/answer_composer.py` *(new)*, `backend/chat/routes.py`, `backend/brain/adapters.py`, `backend/config.py` *(BACKEND_AGENT consultation for config)* | `AskResponse.answer`, readiness/health | §8.2 approval | `TEST_AGENT` + `EVALUATION_AGENT` | `SECURITY_AGENT` (egress), `VERIFIER` | **YES** — model + provider + weights |
| C-9 | Diagram detection | `AI_AGENT` | `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py` | request/response flags | C-7 | `TEST_AGENT` | `VERIFIER` | NO |
| C-10 | Diagram rendering service | `BACKEND_AGENT` | `backend/diagrams/render.py` *(new package)*, `backend/main.py`, `backend/requirements.txt` | new route; response schema | §8.3 approval | `TEST_AGENT` | `SECURITY_AGENT` (XSS/injection), `VERIFIER` | **YES** — new package ownership + renderer dependency |
| C-11 | Frontend marks/diagram/partial-state UI | `FRONTEND_AGENT` | `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json` | backend contracts C-7, C-9, C-10, C-12 | C-7 | `FRONTEND_AGENT` (introduces a runner) | `VERIFIER` | **YES** — adds a frontend test runner dependency |
| C-12 | Processing-status contract (`partial`) | `BACKEND_AGENT` + `DATABASE_AGENT` | `backend/documents/routes.py`, `backend/documents/schemas.py`, `backend/documents/insights.py` | `Document.status`, `DocumentOut`, insights | C-1 | `TEST_AGENT` | `COORDINATOR` | **YES** — status/contract semantics |
| C-13 | Test suites and fixtures | `TEST_AGENT` | `backend/tests/**` | none (tests only) | each phase | `TEST_AGENT` | `VERIFIER` | NO |
| C-14 | Evaluation corpora, runners, metrics | `EVALUATION_AGENT` | `backend/evaluation/**` | none (research layer) | C-1, C-3, C-8 | `EVALUATION_AGENT` | `VERIFIER` | NO |
| C-15 | Ownership amendment for the new diagram package | `COORDINATOR` | `agents/backend-agent.md` (Owns list) | agent contract | C-10 | — | user | **YES** — ownership change |
| C-16 | Documentation and evidence records | `COORDINATOR` | `backend/architecture/**` (append-only), `CONTEXT.md`, `ARCHITECTURE.md` | docs | all | — | user | NO |

**Forbidden for everyone (AGENTS.md §03):** `backend/models/documind-qa/**`, `backend/venv/**`, `backend/phases/phase4f_gpu/**`, `backend/uploads/**`, `backend/.env`, `.env`, `dist/`, `node_modules/`.

**Single-writer conflicts resolved up front:** `backend/documents/processing.py` is written only by C-1 then C-3 then C-4 (sequential, same owner `BACKEND_AGENT`). `backend/chat/routes.py` is touched by C-6, C-7, C-9 — all `AI_AGENT`, sequential. `backend/requirements.txt` is touched by C-1 and C-10 — both `BACKEND_AGENT` (per `agents/backend-agent.md`: only BACKEND_AGENT may modify it), and the two edits must be one ordered change, not parallel.

---

## 5. Proposed Contracts (A–F)

All contracts below are **PROPOSED**. Nothing here is implemented. Each is additive and backwards-compatible by default (nullable/optional fields), so existing clients and stored rows keep working.

### Contract A — Canonical document representation
**Principle:** one representation, extending the existing chain `ExtractedElement` → `ParsedElement` → ORM rows. No second document model.

| Concern | Representation (proposed) |
| --- | --- |
| Document identifier | existing `Document.id` / `user_id` ownership chain |
| Page number | existing 1-based `page` / `page_number` (`None` for DOCX/TXT) |
| Element type | existing vocabulary `page, section, paragraph, text_block, table, table_row, table_cell, figure, list, list_item`; `figure` becomes **emitted** (not new) |
| Content | existing `content` (text) |
| Section hierarchy | existing `heading_path` / `section` / `heading_level` / `parent_source_id` |
| Figure/table identifier | existing deterministic `source_id` (`{type}:{page}:{seq}`) |
| Caption | **new field** `caption: str \| None` on the figure element; association recorded, never invented |
| Bounding box | existing `bbox_x0/y0/x1/y1` columns — currently always `None` for text; populated for figures and (where available) tables |
| Extraction method | **new field** `extraction_method: "native" \| "ocr"` (+ engine name/version) |
| Confidence / quality | **new field** `extraction_confidence: float \| None` (OCR mean confidence; `None` for native text) |
| Source provenance | existing `parser_version`; **extended** with `ocr_engine`, `ocr_engine_version`, `ocr_languages` |
| Ordering | existing `sequence_index` (unchanged, still unique per document) |

### Contract B — OCR result representation
**Principle:** OCR text is evidence, not truth. It enters the pipeline through the same element/chunk path as native text, tagged as OCR-derived with a confidence, and is never silently promoted to native quality.

```
PageExtraction (proposed record, one per page)
  document_id      : uuid        # ownership via documents.user_id
  page_number      : int         # 1-based, matches native page provenance
  method           : "native" | "ocr" | "none"
  ocr_engine       : str | None  # e.g. engine name
  ocr_engine_version: str | None
  languages        : str | None  # comma-joined language codes actually used
  mean_confidence  : float | None
  char_count       : int         # characters obtained for this page
  rotation_applied : int | None  # degrees, only when detected and applied
  failure_reason   : str | None  # populated when method = "none"
  parser_version   : str | None
```

* **Invocation condition (proposed, deterministic):** OCR runs for a page only when native extraction yields fewer than a declared threshold of *alphanumeric* characters on that page. The threshold is a named constant with a recorded rationale, not a magic number buried in a condition.
* **Never sent to OCR unnecessarily:** a page with adequate native text is never re-processed through OCR (an explicit, tested negative control).
* **Failure:** an OCR failure leaves `method="none"` with a `failure_reason`; it never aborts the whole document silently and never fabricates text.
* **Freshness:** OCR output is recomputed on reprocess exactly like structure and graph data (the project's existing "rebuilt from scratch" rule).

### Contract C — Evidence representation
Extends the existing `SourceChunk` / `SourceOut` contract additively.

| Field | Change |
| --- | --- |
| `evidenceKind` | extend the closed set `chunk \| structure_element \| table_row` with **`figure`** |
| `extractionMethod` | **new**, nullable: `native \| ocr` — lets a citation say "OCR-derived text" honestly |
| `page` | unchanged (already 1-based and rendered) |
| `figureRef` | **new**, nullable: asset reference for a figure source (Contract E), never a remote URL |
| `caption` | **new**, nullable: the caption associated with a figure source |
| `section`, `headingPath`, `elementType`, `chunkerVersion`, `tokenCount` | unchanged |
| `score` / `fusionScore` / `structuralHops` / `retrievalPath` | unchanged; **no fabricated similarity for a figure** (a figure match carries its retrieval path and graph/AI score, or `None`) |
| Abstention | unchanged: the evidence gate remains the only authority on SUCCESS/PARTIAL/INSUFFICIENT_EVIDENCE |

### Contract D — Answer request and response
```
AskRequest (proposed, additive)
  question  : str                 # unchanged, must be non-empty
  topK      : int = 5             # NOW validated (ge=1, le=<declared ceiling>)
  marks     : int | None = None   # one of {6, 8, 10, 15}; None = current behaviour
  includeDiagram : bool | None = None   # optional preference; NOT a promise (see below)
```
```
AskResponse (proposed, additive)
  answer               : str        # unchanged field
  answerFormat         : "extractive" | "exam"   # NEW — which mechanism produced it
  marks                : int | None              # NEW — echoed back
  diagram              : DiagramPayload | None   # NEW — Contract E
  confidence           : float
  sources              : SourceOut[]
  insufficientContext  : bool
  question             : str
  reliability          : ReliabilityEvidence
  outcome              : str
  generation           : { model: str, degraded: bool, reason: str | None }  # NEW, honest failure reporting
```
* **Supported marks:** exactly `{6, 8, 10, 15}`; anything else → `422` with an explicit message. `None` preserves today's extractive behaviour (no silent change for existing clients).
* **Depth, not word count:** the four modes differ in required sections (definition/explanation/example/conclusion), evidence breadth, and structure — never by padding.
* **Grounding rules:** every generated claim must be traceable to retrieved evidence; the system must **not** invent textbook facts, citations, equations, or results; when evidence is insufficient it abstains or discloses, using the existing `insufficientContext`/outcome contract.
* **No score promises:** the response never claims an examination grade.
* **Generation failure:** a generation failure returns an honest error/`UNAVAILABLE` state with `degraded: true` — never a fabricated answer and never a silently truncated one presented as complete.
* **Context budget:** the generative path gets its **own** declared budget function; the extractive 384-token window stays exactly as it is for the grounding/verification step.
* `includeDiagram` is included **only** because the programme asks whether a preference is justified. Justification recorded: it is *optional*, defaults to `None`, and must never cause a diagram to be produced where none is warranted — a request is a preference, not an instruction to decorate an answer.

### Contract E — Diagram representation
```
DiagramPayload (proposed)
  origin        : "retrieved_figure" | "generated"
  # retrieved
  documentId    : str | None      # server-resolved from the JWT-scoped evidence
  page          : int | None
  elementId     : str | None
  assetRef      : str | None      # opaque reference; served through an authorised route
  caption       : str | None
  # generated
  format        : "mermaid" | "svg" | None
  source        : str | None      # validated diagram source (generated only)
  validated     : bool            # validation actually ran and passed
  validationNote: str | None      # why it failed, when it did
  renderer      : "client" | "server" | None
  attribution   : str | None      # "derived from <document> p.<page>" for generated, when derived
```
**Rules (binding):**
* A retrieved figure keeps its real document/page and is **never** substituted with an unrelated image.
* A generated diagram is **never** presented as an authoritative diagram of a source document; it is labelled as generated/derived.
* Validation must run before rendering: reject unsafe content, no embedded scripts, no remote fetches, no arbitrary HTML/JS from model output.
* A rendering failure is reported as a failure — diagram *source text* is never claimed to be a rendered diagram.
* The frontend renders only sanitised, structured output (never `dangerouslySetInnerHTML`).

### Contract F — Processing status
| Status | Meaning (proposed) | Set when |
| --- | --- | --- |
| `uploaded` | stored, not yet processed | unchanged |
| `processing` | pipeline running | unchanged |
| `ready` | **every page produced usable content** (or the format has no pages) and all downstream steps succeeded | unchanged wording, **new definition** |
| `partial` | **NEW** — at least one page produced usable content and at least one page did not (OCR unavailable/failed, or genuinely no text) | all downstream steps succeeded for the pages that did produce content |
| `error` | no page produced usable content, or a pipeline step failed | unchanged |

* The definition change is the honesty fix: a mixed PDF must **not** be `ready` while pages are unaccounted for.
* `partial` is a *success with disclosure*: the document is searchable, and the UI must state which pages are missing or OCR-derived.
* Representation: a machine-readable per-document coverage summary (pages total / pages with content / pages OCR-derived / pages failed) exposed through the existing insights endpoint family (`documents/insights.py`, `documents/schemas.py`), plus the status value itself.
* `Document.status` is `String(20)`, so the value itself needs no DDL — but the **contract** change (§13 item) is what must be approved.

---

## 6. Dependency Graph

```
Phase 0  Reconnaissance ....................... DONE (this report)
   │
   ├──────────────┬───────────────────────────────┐
   ▼              ▼                               ▼
Phase 1        (parallel research,                (parallel research,
Ingestion &     no production change)              no production change)
OCR            OCR engine evaluation             Generation-model evaluation
   │           §8.1                                §8.2   ──► decision required
   │
   ├──────────────────────────────────────────────► Phase 4 (Exam answers) needs both:
   ▼                                                  1) retrieval of OCR'd evidence, and
Phase 2                                               2) an approved generation model
Structure preservation
(figures, captions, equations, page provenance, canonical rep)
   │                                    ▲
   ▼                                    │
Phase 3                              Phase 5 (Diagram intelligence)
Evidence retrieval                   detection → needs Phase 2 figures
   │                                 retrieval → needs Phase 3 figure evidence
   │                                 generation → needs §8.3 decision
   ▼
Phase 6  Frontend integration   ◄── needs Contracts C-7, C-9, C-10, C-12
   │
   ▼
Phase 7  Integration & verification (regression, E2E, security review, independent review, docs)
```

**Hard dependency edges (production implementation only):** 1 → 2 → 3 → 6 → 7; 2 → 5; 3 → 5; and **(1 ∧ 3 ∧ §8.2 approval) → 4**. Phase 4 must not start before the extraction/retrieval foundation exists, or the answer quality would be measured against a lossy corpus. Phase 5 must not start before Phase 2, or "retrieve the existing figure" has nothing to retrieve. Research (e.g. the OCR and model decision records of §8) may run in parallel with Phase 1 because it changes no production file.

**Schema gate:** `C-2`, `C-5` and any other migration-dependent item sit behind a single, separately-approved migration review. Phase 1 can ship **without** a migration if per-page OCR provenance is carried in existing structure-element rows; the plan offers both options so the migration is a deliberate choice rather than a hidden dependency.

---

## 7. Phase-by-Phase Implementation Plan

### Phase 0 — Reconnaissance — **COMPLETE (this report)**
Objective: establish the real architecture, confirm the gaps, define owners, contracts, sequence, and gates. Deliverables: §1–§13 of this report. No production change.

### Phase 1 — Document ingestion and OCR
* **Objective:** every page of every supported document is either extracted natively or OCR'd, and incompleteness is visible.
* **Deliverables:** per-page completeness decision; one OCR adapter interface with a selected engine; per-page extraction records; `partial` status + coverage summary; honest failure reporting.
* **Files:** `backend/documents/{ocr.py(new), processing.py, routes.py, schemas.py, insights.py}`, `backend/config.py`, `backend/requirements.txt`, plus the migration if C-2 is approved.
* **Acceptance criteria (from the programme, all mandatory):** (1) digital PDFs still work; (2) scanned-only PDFs produce searchable content when OCR is available; (3) mixed PDFs preserve content from both page kinds; (4) OCR failures are visible and recoverable; (5) empty/partially-extracted documents are never falsely complete; (6) existing formats remain supported; (7) regression tests pass.
* **Risks:** engine licensing/quality; CPU latency on 50 MB documents; Windows + container parity; language packs; resource exhaustion on hostile PDFs (page bombs, decompression bombs).
* **Complexity:** **High.** **Approval required before implementation:** the dependency install and the OCR model/engine provisioning (§8.1), plus the `partial` status contract (C-12).

### Phase 2 — Structure preservation
* **Objective:** figures, captions, equations, and the canonical representation survive extraction, persistence and chunking.
* **Deliverables:** emitted `figure` elements with caption + page + bbox + asset reference; equation preservation policy implemented and labelled; extraction method/quality metadata; existing tables unchanged.
* **Files:** `backend/documents/{figures.py(new), equations.py(new), processing.py, parser.py, chunking.py}`, `backend/storage/file_store.py`, `backend/documents/models.py` + migration (`DATABASE_AGENT`).
* **Acceptance criteria:** text extraction unchanged; table retrieval unaffected; figure↔caption relationship retained; page provenance survives chunking/indexing; equations preserved as accurately as the chosen method supports (and **labelled** as such — surviving text is not "understanding"); failures observable; no damage to existing data.
* **Risks:** asset storage volume; deleting a document must remove its assets (cascade + containment rules); bbox correctness.
* **Complexity:** **High.** **Approval required:** any schema change (C-2/C-5).

### Phase 3 — Evidence retrieval
* **Objective:** OCR text, figures and tables all become traceable evidence.
* **Deliverables:** OCR-derived chunks retrieved like native ones with `extractionMethod` provenance; `figure` evidence kind; figure retrieval returns the correct document + page; abstention preserved.
* **Files:** `backend/chat/{rag.py, routes.py}`, `backend/brain/adapters.py`, `backend/graph/service.py`.
* **Acceptance criteria:** questions retrieve content from scanned pages; table evidence remains available; figure retrieval returns the right document and page; context assembly respects the model's constraints; citations reference real elements; unsupported questions still abstain; retrieval regressions pass.
* **Risks:** OCR text polluting semantic ranking with low-quality text (mitigation: provenance + optional confidence floor, measured not assumed).
* **Complexity:** **Medium.** **Approval required:** none beyond C-1/C-3.

### Phase 4 — Exam-answer generation
* **Objective:** genuinely different, source-grounded answers for 6/8/10/15 marks.
* **Deliverables:** approved model decision record (§8.2) → implementation; mark-aware composition; marks validation; grounding/abstention rules; answer evaluation harness.
* **Files:** `backend/chat/answer_composer.py(new)`, `backend/chat/routes.py`, `backend/brain/adapters.py`, `backend/config.py`; evaluation under `backend/evaluation/**`.
* **Acceptance criteria:** all four levels work end to end; the same question yields meaningfully different depth for different marks; answers stay grounded; missing evidence handled honestly; existing citations intact; tests cover completeness/accuracy/relevance/redundancy; **the implementation does not merely relabel short extractive spans as examination answers**.
* **Risks:** hallucination — mitigated by keeping the extractive path as a grounding/verification layer and by refusing unsupported claims; latency; context-window pressure for 15 marks; privacy if a hosted model is chosen.
* **Complexity:** **High.** **Approval required:** model/weights/provider, and the marks contract (C-7).

### Phase 5 — Diagram intelligence
* **Objective:** detect diagram needs, retrieve the right existing figure, and generate/render only when justified and safe.
* **Deliverables:** detection with recorded trigger; figure retrieval with caption+page; a validated generation path; safe rendering; explicit failures.
* **Files:** `backend/brain/{classifier.py, adapters.py}`, `backend/chat/routes.py`, `backend/diagrams/render.py(new)`, `backend/main.py`, `backend/requirements.txt`.
* **Acceptance criteria:** explicit diagram requests are detected; relevant existing figures are retrievable; generated diagrams render; the answer explains the diagram; sources are cited for retrieved figures; invalid output fails safely; existing frontend behaviour remains intact.
* **Risks:** unsafe generated markup (the dominant risk); invented architectures presented as authoritative (mitigated by labelling + grounding); renderer deployment weight (a headless browser would be a large runtime addition).
* **Complexity:** **High.** **Approval required:** renderer choice + new package ownership (C-10, C-15).

### Phase 6 — Frontend integration
* **Objective:** the user can request marks, read an exam-style answer, see figures/diagrams and page citations, and understand OCR/partial states.
* **Deliverables:** marks selector wired to the backend; exam-answer rendering (headings/lists/equations/code where applicable); figure and diagram display; page-level source references; OCR/partial warnings; error/retry and loading states; a frontend test runner.
* **Files:** `src/pages/WorkspacePage.tsx`, `src/context/WorkspaceContext.tsx`, `src/lib/api.ts`, `src/types/index.ts`, `src/pages/SettingsPage.tsx`, `package.json`.
* **Acceptance criteria:** marks reach the backend and are reflected in the answer; figures/diagrams render; citations identify the source; OCR/extraction failures are communicated; keyboard navigation and accessibility remain functional; the build and relevant checks pass.
* **Risks:** rendering model output unsafely (forbidden); adding dependencies for convenience (forbidden); leaving the inert depth control in place (must be wired or removed).
* **Complexity:** **Medium.** **Approval required:** frontend test-runner dependency.

### Phase 7 — Integration and verification
* **Objective:** demonstrate end-to-end behaviour and safety, not just green unit tests.
* **Deliverables:** executed regression + E2E suites with recorded exit codes, evaluation report, independent security review, independent verification, updated documentation and the implementation report.
* **Files:** `backend/tests/**` (TEST_AGENT), `backend/evaluation/**` (EVALUATION_AGENT), `backend/architecture/**` and `CONTEXT.md`/`ARCHITECTURE.md` (COORDINATOR, append-only).
* **Acceptance criteria:** every capability carries one of the five statuses backed by observed evidence; failures investigated rather than hidden; anything unrunnable marked **BLOCKED**; security findings carry severity, evidence and remediation.
* **Blocked-by-environment items to expect:** live E2E requires an authorised disposable database (the project's own guard currently refuses creation) and a running server.
* **Complexity:** **Medium (continuous).**

---

## 8. Model and OCR Decisions Requiring Approval

**No engine or model was selected, installed, or downloaded. Everything below is a decision record to be approved.** The format follows this repository's existing dependency-decision precedent in `agents/backend-agent.md` (Scope / Status / Why / constraints / version traps), which was used for `faster-whisper`.

### 8.1 OCR engine decision — **REQUIRES APPROVAL (blocking Phase 1)**

**Scope:** per-page OCR fallback for pages whose native extraction is insufficient, for PDF (and, if image uploads are in scope, standalone images).

**Status: NOT SELECTED — no engine installed, no weights or language data downloaded.**

**Candidate evaluation (to be measured, not assumed):**

| Candidate | Runtime fit in this repo | System binary? | Offline after provisioning | Confidence output | Notes / risks |
| --- | --- | --- | --- | --- | --- |
| **Tesseract via `pytesseract`** | new Python package + **system `tesseract` binary** | **YES — required** | yes | per-word/per-line confidence | **Precedent risk:** this project already rejected a system-binary dependency once (Whisper required `ffmpeg`, absent → `faster-whisper` chosen instead). The Docker image (`python:3.11-slim` + `libgomp1` only) would need OS packages + language data; the Windows dev host needs a separate installer. Deterministic and licence-clean (Apache-2.0) |
| **RapidOCR (`rapidocr-onnxruntime`)** | reuses **already-installed `onnxruntime 1.30.0`** | **no** | yes (model files provisioned once) | per-line confidence | No new framework; wheels are small; model files must be provisioned locally; language coverage narrower than Tesseract's |
| **EasyOCR** | reuses installed `torch 2.13.0`/`torchvision` | no | yes (per-language weights) | per-line confidence | Heavier inference; weights per language; good multilingual coverage |
| **PaddleOCR** | separate framework (`paddlepaddle`) + weights | no | yes | yes | Strong layout/table recognition; largest new dependency footprint; independent of torch |
| **docling** | pulls a parsing/OCR pipeline stack | depends on chosen backend | yes | partial | Modern layout-aware pipeline; large dependency surface; overlaps with the existing PyMuPDF extraction (risk of a **competing parser**, explicitly forbidden by the programme) |
| **Hosted document-intelligence API** (see 8.4) | HTTP call from the backend | no | **no — requires network** | yes | Sends user documents to a third party; paid; needs an API key; conflicts with the local-first posture and would require explicit data-egress approval |

**Required evaluation method before selection (no production change):** build a fixture set (digital PDF, scanned-only PDF, mixed PDF, rotated page, table-heavy document, equation-heavy document, image-based question paper, corrupt file) in an isolated temp directory, and measure for each candidate: per-page character coverage vs ground truth, character/word error rate, table cell fidelity, mean latency per page, peak memory, licence, offline capability, and Windows/container parity. The candidate is scored on **measured** results; the recommendation is written into this report as an addendum before any install.

**Version / environment traps to verify at selection time:** CPython **3.11** wheel availability for both Windows and Linux (the `av<19` trap in `agents/backend-agent.md` is the precedent for checking this explicitly); the Docker image's missing OS packages; and no conflict with the pinned `torch 2.13.0` / `transformers 5.16.1`.

**Approval requested:** permission to (a) install the chosen OCR wheels into `backend/venv`, (b) declare them in `backend/requirements.txt`, (c) provision its model/language data locally under an operator-approved path, and (d) if the chosen engine needs a system binary, modify `backend/Dockerfile`.

### 8.2 Generation model decision — **REQUIRES APPROVAL (blocking Phase 4)**

**Scope:** source-grounded composition of 6/8/10/15-mark answers, replacing single-span extraction as the *answer* mechanism while keeping the extractive model as the grounding/verification layer.

**Status: NOT SELECTED — no provider configured, no weights downloaded, no API key present.** (`.env.example` already reserves commented `LLM_API_KEY` / `LLM_MODEL` placeholders under "LLM (Phase 2)" — the configuration surface exists and is unused; the file itself was not modified.)

| Candidate class | Fit | Data egress | Cost | Notes / risks |
| --- | --- | --- | --- | --- |
| **Local open-weight instruct model served via the installed `transformers`/`torch` stack** | reuses installed runtime; no new framework | **none** | hardware only | Requires weight provisioning (approval) and CPU/GPU capacity; latency must be measured; keeps the project's no-egress property; no per-request cost |
| **Hosted API** (catalog contains OpenAI, Anthropic, Google AI Studio, Mistral, Together, Groq, Fireworks, DeepInfra, Cerebras, OpenRouter, AWS Bedrock, Google Vertex, Azure OpenAI) | fastest to integrate, best quality per token | **documents leave the machine** | per token | Directly conflicts with the project's existing "no external fallback" rule for the QA path; requires an ADR/rule change, a data-egress decision, key management, and cost control |
| **Gateway** (catalog: OpenRouter, LiteLLM, Portkey) | adds routing/fallback | depends on upstream | depends | Justified only if multiple providers or failover are genuinely required; adds an indirection whose failure modes must be handled. **Not recommended at this stage** (simplest safe approach first) |
| **Serving platform** (catalog: Baseten, Modal, RunPod, Cerebrium, Lambda, CoreWeave, Vast.ai) | managed self-hosted inference | configurable | GPU per hour | A middle path if local capacity is insufficient; still an external dependency and a paid service |

**Decisive local constraint discovered:** the extractive window is **384 tokens** and `max_answer_length` is **100 tokens**. A 15-mark answer cannot be produced inside that window; the generation path needs its own, explicitly declared context budget (Contract D) — this is a design requirement, not a tuning parameter.

**Required decision record before implementation (per the programme):** candidate models and their constraints; reusable existing infrastructure; cost and latency implications; privacy implications; context-window requirements; evaluation methodology; and the reasons for the recommendation.

**Recommended sequencing:** decide **after** Phases 1–3, so the model is evaluated against a corpus that actually contains scanned pages and figures — measuring a generation model against today's lossy corpus would produce a misleading result.

**Approval requested:** the model/provider choice, the weights (or API key) provisioning path, the permitted data-egress posture, and the corresponding update to the project's "no external model" rule if a hosted provider is chosen.

### 8.3 Diagram rendering decision — **REQUIRES APPROVAL (blocking Phase 5 generation/rendering)**

**Status: NOT SELECTED — no renderer installed; no diagram library present (`graphviz`, `matplotlib`, `mermaid` all absent).**

| Option | Dependency cost | Safety profile | Notes |
| --- | --- | --- | --- |
| **Validated diagram source (e.g. Mermaid) + client-side rendering** | one frontend dependency | acceptable **only** with strict validation + a CSP + no raw HTML injection | smallest backend footprint; the rendering happens in the browser; the backend must still validate the source it hands over |
| **Server-side rendering to SVG** | a renderer runtime (a headless browser or an image with a CLI) | safest content type (a static image), but the **largest** deployment addition | heavy for this repo's slim image; needs a new system dependency |
| **Own deterministic structured → SVG renderer** | none (stdlib + existing deps) | **highest** (we control the output; no arbitrary input) | limited diagram vocabulary (blocks, flows, simple sequences/plots) but zero supply-chain and no arbitrary code path; best match for the project's conservative posture |
| **`python-graphviz`/`matplotlib`** | new packages + (graphviz) a system binary | moderate | graphviz needs a system binary (same class of blocker as §8.1 Tesseract); matplotlib generates plots, not architectures |

**Recommended default (subject to approval):** generation restricted to a validated, declarative representation rendered through the option with the smallest supply-chain and injection surface, with a documented diagram vocabulary; unsafe content rejected and reported. **A generated diagram is never a substitute for a retrieved source figure, and diagram source text is never reported as a rendered diagram.**

### 8.4 Catalog findings (discovery, honestly reported)

A service discovery pass was run for both needs. **Both searches returned no recommendation**, because the catalog contains no OCR engine and no LLM provider that satisfies the constraints (local/offline, no external data transfer, no paid service, no weight download without approval). Recorded honestly rather than papering over with a recommendation:

* **No OCR/document-intelligence engine** exists in the catalog (`browse` for OCR/document extraction returned **0 services**).
* **Hosted document-parsing APIs that do exist** — **Reducto**, **LlamaParse/LlamaCloud**, **Unstructured** (API) — would send user documents to a third party and are paid. They are recorded as *available alternatives requiring explicit data-egress approval*, not as recommendations.
* **LLM providers/serving platforms** are plentiful in the catalog (OpenAI, Anthropic, Google AI Studio, Mistral, Together, Groq, Fireworks, DeepInfra, Cerebras, OpenRouter, AWS Bedrock, Google Vertex, Azure OpenAI, Baseten, Modal, RunPod, Cerebras/Cerebrium/Lambda/CoreWeave/Vast). None satisfies the no-egress/no-cost constraints without an explicit owner decision.

**Consequence for the plan:** the local-first options in §8.1/§8.2/§8.3 are the primary path; every hosted option is an approval item with a named privacy and cost consequence, never a silent default.

---

## 9. Security and Privacy Assessment

Documents are **untrusted input** (AGENTS.md §05). Every new capability adds attack surface; the table records what this programme must address **before** each phase is accepted.

| Threat | Relevance to this programme | Existing control | Required new control | Owning agent | Phase |
| --- | --- | --- | --- | --- | --- |
| Malicious/corrupt documents | OCR and figure extraction parse attacker-controlled structures | magic-byte validation, format allowlist, error → `error` status | per-page timeout + bounded page count; reject hostile structures without crashing the worker | `BACKEND_AGENT` | 1–2 |
| Resource exhaustion (page bombs, decompression bombs, giant images) | OCR and image decode are the most expensive operations added | 50 MB upload cap | explicit page/pixel/time ceilings; OCR skipped beyond bounds; memory ceiling measured, not assumed | `BACKEND_AGENT` | 1–2 |
| **Data egress** | a hosted OCR or LLM service would transmit user documents | nothing leaves the machine today | egress must be an explicit, recorded owner decision; if adopted, disclosure in the UI and no silent fallback | `COORDINATOR` + `SECURITY_AGENT` | 1 / 4 |
| Prompt injection inside uploaded documents | retrieved text reaches a generative model | extractive model cannot be instructed by text | treat retrieved text as data, never as instructions; instruction/data separation; injection tests; the model must not gain tool or network access | `AI_AGENT` | 4 |
| Hidden/white-on-white text manipulation | poisoned OCR/text could bias answers | none | detect and flag anomalous text layers; never let a document's own text redefine system behaviour | `BACKEND_AGENT` | 2 |
| Cross-tenant access to figure assets | a new asset-serving route is a classic IDOR/BOLA target | JWT-derived identity; ownership via `documents.user_id` | resolve ownership server-side on every asset request; never accept a client-supplied path or id as authority; 404 (not 403) for foreign documents | `BACKEND_AGENT` | 2–3 |
| Path traversal in asset storage/serving | new file paths are created and served | `storage/file_store.py` containment + symlink/reparse refusal (audited in the 1.6x series) | reuse those primitives for reading/serving; no new ad-hoc path joining; assets inside the upload root only | `BACKEND_AGENT` | 2 |
| XSS / unsafe rendering of model or diagram output | diagram source and generated answers reach the browser | none (no generated HTML today) | never `dangerouslySetInnerHTML`; sanitise/validate diagram source; strict CSP; render structured data only | `FRONTEND_AGENT` | 5–6 |
| Unsafe generated diagram source (script/remote fetch/HTML) | a renderer is an arbitrary-content path | none | allowlist grammar; reject scripts/links/remote refs; validation must fail closed and be reported | `BACKEND_AGENT` | 5 |
| Secrets exposure | a new provider introduces a key | secrets only from env; `.env` never printed | key only via env; never logged; never returned in errors; `.env.example` documents names only | `BACKEND_AGENT` | 4 |
| Logging sensitive document content | OCR/generation pipelines are chatty by nature | existing logging is error-oriented | log counts/ids/status, never extracted document text or prompts containing user content | all | 1–6 |
| Provenance manipulation | OCR text and figures must not be mistakable for native evidence | explicit provenance fields | `extractionMethod` + engine/confidence on every OCR element; figure source always carries document+page | `AI_AGENT` | 2–3 |
| Supply chain (new wheels + OCR/generation weights) | several new dependencies and model artifacts | pip pins; models mounted read-only | pin exact versions; record hashes of provisioned artifacts; prefer already-installed runtimes; licence review recorded | `BACKEND_AGENT` + `SECURITY_AGENT` | 1 / 2 / 5 |
| Answer integrity | generated text must not become fabricated "truth" | extractive answer ⊆ context; evidence gate | generated claims traceable to evidence; refuse unsupported claims; never promise an exam score; the extractive path remains the verifier | `AI_AGENT` | 4 |

**Privacy posture:** the default recommendation is that **no user document leaves the deployment** (local OCR, local generation). Any deviation is a named approval item with a disclosure requirement. Audio/voice and media-verification subsystems are untouched by this programme.

---

## 10. Test and Evaluation Plan

Builds on the existing suites (1368 unit / 275 integration / 6 E2E collected) rather than duplicating them. New tests are owned by `TEST_AGENT`; research evaluation by `EVALUATION_AGENT`; security testing by `SECURITY_AGENT` with remediation routed to the owning implementation agent.

### 10.1 Document-processing tests
| Case | Status today | Target |
| --- | --- | --- |
| Digital PDF | covered, passing | must keep passing unchanged |
| Scanned PDF | **fails today** (0 elements) | searchable extract or explicit `partial`/`error` with reason |
| Mixed PDF | **fails today** (silent loss) | every page accounted for; no false `ready` |
| Rotated page | not covered | rotation detected/handled or explicitly reported |
| Image-based question paper | not covered | ingests with OCR provenance |
| Table-heavy document | partially covered (`find_tables`, row persistence) | unchanged + no regression |
| Equation-heavy document | not covered | equations preserved as accurately as the method supports, and labelled |
| Corrupted/unsupported file | covered, passing | unchanged |
| OCR failure | not covered | `partial` with visible reason; no fabricated text |
| Empty extraction | covered (→ `error`) | unchanged |
| Partial extraction | not covered | `partial` + coverage summary |

### 10.2 Answer-generation tests
Same question at 6/8/10/15 marks (four measurably different structures); sufficient-evidence questions; insufficient-evidence questions; contradictory sources; table-based questions; multi-section questions; calculation/equation questions; diagram-required questions. Metrics: answer accuracy, evidence coverage, grounding, unsupported-answer rate, structural completeness against the requested mode, **redundancy** (repeated content), and latency. **Depth is never measured by word count alone.**

### 10.3 Diagram tests
Explicit-request detection; existing-figure retrieval correctness (right document + page, and the correct figure where several exist); new generation; invalid diagram source (must fail closed); rendering failure (must be reported, never presented as success); citation correctness.

### 10.4 End-to-end tests
The full path: upload → parse/OCR → structure extraction → chunking → indexing → retrieval → answer generation → diagram handling → frontend rendering → source citation, executed against a real authorised database and a live server.

### 10.5 Security tests
File validation, upload size limits, malformed documents, parser resource exhaustion, path traversal, tenant/document authorization (IDOR/BOLA on the new asset route), prompt injection inside uploaded documents, unsafe generated diagram source, XSS/unsafe HTML rendering, secret exposure, sensitive-content logging, and dependency/model supply-chain review. **No destructive database tests and no production data.**

### 10.6 Environment reality (already observed)
* Integration tests that need PostgreSQL **self-skip** or refuse (`tests/fixtures/integration_db.py:294`, `tests/fixtures/disposable_db.py:36`).
* `test_real_e2e_validation` errors by design: `UnsafeEvaluationTarget: REFUSING … missing enforceable create authorization`.
* Browser E2E skips without a live server (`tests/fixtures/live_server.py:37`); all 6 skipped in the audit run.
* **Therefore:** Phase 7 must report live E2E as **BLOCKED** unless an authorised disposable database and server are provided. A skipped suite is never reported as a pass.

---

## 11. Resource and Deployment Requirements

| Requirement | Fact / implication |
| --- | --- |
| CPU runtime | The deployment is CPU-oriented; `compose.yaml` sets `OMP_NUM_THREADS=2`. OCR and any local generation are CPU-bound and must be measured before being adopted. |
| GPU availability | **Not established in this environment.** `backend/phases/phase4f_gpu/**` is an archived virtualenv and is read-only/forbidden for every agent — it must not be used as a runtime. Any GPU-dependent option needs a separate capacity decision. |
| Uvicorn worker model | **A single worker** (model singletons are per-process, `backend/Dockerfile`). Long OCR/LLM work must therefore be offloaded off the event loop (thread/executor) or it will block every other request. |
| Backend image | `python:3.11-slim` + `libgomp1` only. A system-binary OCR engine would require Dockerfile OS packages + language data (image growth); an ONNX/`torch`-based engine reuses the installed runtime and **avoids** an image change. |
| Model provisioning path | Weights are operator assets mounted read-only at `/app/models` and must never be baked into a layer; the embedding model is pre-fetched to `/opt/documind-models` (outside the mount). New OCR/generation artifacts follow the **same** pattern and need an operator-approved provisioning step (agents cannot write `backend/venv/**` or the weights directories). |
| Storage | Uploads are a named volume (`uploads:/app/uploads`). Figure assets add volume growth and **must** be deleted with their document (containment rules already exist in `storage/file_store.py`). |
| Disk | ~81 GB free on the dev host; production sizing for assets + model weights must be computed from measured per-document asset size. |
| Database | PostgreSQL + pgvector only; any new table is Alembic-managed with a **single linear head** (currently `007_add_table_rows`). Migrations run at container start via the entrypoint. |
| Latency budgets | Not yet measured. Expect: OCR per page, figure extraction per page, generation per answer. Each phase must record measured p50/p95 before acceptance; the plan deliberately contains **no invented numbers**. |
| Frontend | Vite + React 18 + Tailwind; nginx runtime; same-origin `/api` proxy (no CORS in the compose stack). A marks selector and diagram rendering need no new backend port or CORS change. |
| Memory | Local generation is the largest unknown (a multi-billion-parameter model on CPU requires several GB and may be impractical here) — this is a primary input to the §8.2 decision and must be measured, not assumed. |

---

## 12. Unresolved Questions

Each requires an owner decision; none is answered by this reconnaissance.

1. **Partial status semantics** — is `partial` acceptable as a first-class status, or must mixed documents fail until OCR is complete? (Affects Contract F and the honesty rule.)
2. **Marks → depth policy** — do marks drive *answer composition only*, or also *retrieval breadth* (`topK`/context budget)? This is the largest single input to Phase 4.
3. **Generation posture** — local open-weight (no egress, needs capacity) vs hosted API (best quality, egress + cost)? Requires an explicit privacy decision and possibly an update to the project's "no external fallback" rule.
4. **Model capacity** — is there a GPU (or enough CPU/RAM) for a local generative model at acceptable latency? Not established.
5. **OCR engine** — Tesseract (system binary, mature) vs RapidOCR/ONNX (no new framework, reuses installed `onnxruntime`) vs another; and which languages must be supported.
6. **OCR provenance strictness** — should OCR-derived text be eligible for citations by default, or only above a confidence floor? (Measured decision.)
7. **Equation scope** — preserve math as text only, or attempt a notation representation (LaTeX/MathML)? The programme forbids claiming understanding merely because equation-like text survives.
8. **Figure asset storage** — filesystem inside the upload root vs database rows; and the retention/deletion policy on reprocess and document delete.
9. **Schema change authorisation** — is a new per-page/migration path approved at all, or must Phase 1 fit into existing columns?
10. **Diagram scope** — is generated-diagram capability in product scope, given it is the highest-risk item and the only one with no source-of-truth? Alternatively: detect + retrieve existing figures only.
11. **Inert depth control** — wire `processingDepth` to the answer path, or remove the affordance from Settings?
12. **structure-v2 chunker** — keep `legacy` as the default, or promote `structure-v2` on measured evidence? (Interacts with figures/tables reaching retrieval.)
13. **Image uploads** — are standalone image documents (photographed pages, question papers) in scope for upload, or PDF/DOCX/TXT only? This changes `ALLOWED_TYPES`, validation, and the OCR surface.
14. **Live E2E authorisation** — will a disposable database + server be provided for Phase 7, or will end-to-end verification remain permanently BLOCKED?

---

## 13. Explicit Approval Checklist

Nothing in Phases 1–7 may begin until the corresponding item is approved. Checked items = approved by the owner.

| # | Approval required | Blocking | Owner decision | Notes |
| --- | --- | --- | --- | --- |
| 1 | **Phase 1 scope** — per-page OCR with honest `partial` status (C-1, C-12) | Phase 1 | ☐ | includes the mixed-PDF honesty fix |
| 2 | **OCR engine + dependency install + model/language-data provisioning** (C-1, §8.1) | Phase 1 | ☐ | engine chosen on measured evidence, not preference |
| 3 | **Any database schema change** (C-2/C-5 migration, single linear head) | Phase 1/2 | ☐ | or approve a no-migration fallback |
| 4 | **`partial` status contract** in `DocumentOut`/insights and its UI representation | Phase 1/6 | ☐ | definition change for `ready` |
| 5 | **Figure/equation scope** — emit `figure`, captions, equation policy (C-3, C-4) | Phase 2 | ☐ | bbox population + asset storage policy |
| 6 | **Retrieval evidence extensions** — `figure` kind + `extractionMethod` (C-6) | Phase 3 | ☐ | additive contract change |
| 7 | **Generation model decision** — model/provider, weights or key, egress posture, and any rule change (C-7, C-8, §8.2) | Phase 4 | ☐ | must include the decision record |
| 8 | **Marks contract** — `{6,8,10,15}`, `topK` validation, `answerFormat` (C-7) | Phase 4 | ☐ | backwards-compatible default = current behaviour |
| 9 | **Diagram scope decision** — detect+retrieve only, or include generation (C-9, C-10) | Phase 5 | ☐ | highest-risk capability |
| 10 | **Diagram renderer choice + its dependency** (§8.3) | Phase 5 | ☐ | prefer no system binary |
| 11 | **New package ownership** for the diagram render service (C-10, C-15) | Phase 5 | ☐ | requires a `COORDINATOR`-owned contract amendment, as the 1.6L precedent shows |
| 12 | **Frontend test-runner dependency** (C-11) | Phase 6 | ☐ | currently no runner exists |
| 13 | **Deployment changes** — Dockerfile OS packages and/or image growth if required by §8.1/§8.3 | Phase 1/5 | ☐ | only if the chosen engine needs it |
| 14 | **Authorised disposable database + server for Phase 7** | Phase 7 | ☐ | otherwise E2E remains BLOCKED |
| 15 | **Image uploads in scope?** (Q13) | Phase 1/2 | ☐ | changes validation + OCR surface |
| 16 | **Data-egress posture** — confirm "no user document leaves the deployment" or authorise a specific hosted service | Phase 1/4 | ☐ | if authorised, requires UI disclosure |

---

**Closing statement.** This is **Phase 0 only**. No production file, schema, dependency, frontend asset, or configuration was modified by this work; no model was downloaded; no migration or database operation was performed; nothing was staged, committed or pushed. The only file created is this report (plus the predecessor audit report produced in the same programme), both inside the `COORDINATOR`-owned, append-only `backend/architecture/` evidence directory.

**Stop and wait for explicit authorization before beginning Phase 1.**
