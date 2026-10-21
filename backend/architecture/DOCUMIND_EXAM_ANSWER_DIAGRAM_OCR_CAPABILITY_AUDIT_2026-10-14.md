# DOCUMIND — STEP 1: EXAM-ANSWER, DIAGRAM AND OCR CAPABILITY AUDIT

**Report ID:** `DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT`
**Date:** 2026-10-14
**Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (branch `main`)
**Kind:** read-only capability audit and evidence-based gap analysis. No production code was modified.
**Integrity:** the report digest is recorded on its own line immediately below. That line is excluded from its own hash, so the value stays reproducible after substitution:

Report SHA-256: `7eba56719ab1e186db8b27c064a04c4b044d4869168f9539edf37c76ba341951`

---

## 1. Executive Summary

DocuMind is an **extractive** document-QA system over a **pgvector** store, served by a **fine-tuned DistilBERT span-extraction model**. It is not a generative system. Every capability this audit was asked to evaluate lands on the wrong side of that boundary, and the audit establishes that with direct execution evidence rather than inference.

**Verified findings (all negative unless stated otherwise):**

1. **Mark-wise answers (6/8/10/15): NOT IMPLEMENTED.** The answer endpoint accepts only `question` and `topK` (`backend/chat/routes.py:26-28`). No frontend control exists. The settings "Analysis Depth 1–5" slider is persisted but **never read by the answer path** — it is cosmetic with respect to generation. The model is extractive: run directly, it answered "Which embedding model does DocuMind use?" with the single token `all-MiniLM-L6-v2` (16 chars) and "How many dimensions do the embeddings have?" with `384-dimensional` (15 chars). It cannot produce a 15-mark structured answer at any setting, because it does not generate — it selects one contiguous span of the supplied context.
2. **Diagram requirement detection: NOT IMPLEMENTED.** No detection logic anywhere in backend or frontend. A question containing "draw a neat diagram" is processed as ordinary text by the same extractive path.
3. **Existing diagram retrieval: NOT IMPLEMENTED.** `documents/processing.py:249` explicitly **skips PDF image blocks** (`if block.get("type") == 1: continue`). No image is ever extracted, stored, captioned, indexed or referenced. `figure` exists only in the parser *vocabulary* (`documents/parser.py:156,169`) and is **never emitted** (`EMITTED_ELEMENT_TYPES = {section, paragraph, table, text_block}` — confirmed at runtime).
4. **New diagram generation: NOT IMPLEMENTED.** No Mermaid, Graphviz, PlantUML, SVG-generation, plotting or image-generation library is installed or importable (`graphviz`, `pydot`, `matplotlib`, `plotly`, `mermaid`, `diagrams` all `find_spec → False`), and the frontend renders message text as raw text with no diagram renderer (`src/pages/WorkspacePage.tsx:525` `{msg.text}`; dependencies are only `react`, `react-dom`, `three`).
5. **Oracle answer quality (the reason marks matter) — direct evidence:** for a question the context does **not** support ("What is the capital of France?") the model returned `'Doc'` with `score = 0.0`. The evidence gate treats a zero-probability span as "no answer" and abstains (`backend/brain/gate.py`), so missing-evidence handling is honest — but it also shows the ceiling of the answering mechanism.
6. **Scanned PDFs / OCR: NOT IMPLEMENTED.** No OCR engine is installed (`pytesseract`, `tesserocr`, `easyocr`, `paddleocr`, `ocrmypdf` all absent), none is in `backend/requirements.txt`, and `documents/processing.py` contains no OCR or image-decoding code. Direct probe: a scanned (image-only) PDF produced **0 elements**; the document is then marked `error` (`backend/documents/routes.py`, extraction step).
7. **Mixed PDFs: PARTIALLY IMPLEMENTED — and silently lossy.** Direct probe of a 2-page PDF (page 1 digital text + ruled table + embedded figure; page 2 image-only scan) extracted only page 1's content (4 elements, `pages seen = [1]`). The scanned page vanished **without any warning**, and the document would still reach `ready`.
8. **Tables: IMPLEMENTED AND VERIFIED (extraction), PARTIALLY VERIFIED (retrieval).** PyMuPDF `find_tables()` extraction is real and preserved: the probe recovered a 4×3 grid with verbatim cells. Row-level evidence (`document_table_rows`, migration `007`) exists but its retrieval band is **default-OFF** behind `DOCUMIND_TABLE_EVIDENCE` (`backend/chat/rag.py:643-678`).
9. **Equations: NOT IMPLEMENTED.** No LaTeX/MathML/symbol reconstruction (no `sympy`, `latex`, MathML path). Equation glyphs survive only as ordinary text if the PDF stores them as text; rendered math images/Type3 glyphs are dropped like any other non-text object.
10. **Source grounding and page citations: IMPLEMENTED; verified at code and API-test level, NOT verified end-to-end.** Chunk `page` is persisted, selected (`chat/rag.py:185 dc.page`) and rendered (`WorkspacePage.tsx:540,548` → `p.${src.page}`). The live end-to-end citation check (real PostgreSQL + running server) is **BLOCKED** in this environment.

**Verdict: CONDITIONAL PASS** for the audit itself (§17). The most important structural conclusion is that **items 1, 2, 3, 4, 6 and 9 are not "gaps in a RAG pipeline"; they are absent capabilities whose implementation requires an architectural decision (a generative model, an OCR engine, and an image/diagram pipeline) that the current extractive, text-only architecture does not contain.** The project's own documentation already records several of these honestly (`CONTEXT.md:152`, `README.md:106`, `DOCUMIND_PROJECT_CONTEXT.md:1680,1716`), and this audit confirms them independently.

---

## 2. Audit Scope and Safety Constraints

**In scope:** determining, with direct repository inspection and reproducible evidence, whether the system supports (a) 6/8/10/15-mark answers, (b) explicit and implicit diagram requirement detection, (c) retrieval of diagrams already in documents, (d) new diagram generation, (e) OCR for scanned documents, (f) mixed-PDF processing, (g) tables/equations/structure preservation, and (h) reliable retrieval, source grounding and page-level citations.

**Explicitly out of scope:** implementing, fixing or designing any of the above. §18's authorization gate is respected — nothing was built.

**Constraints honoured (all verified in §18):**

* No production source file, frontend file, prompt, config or dependency was modified.
* Nothing was installed, upgraded, downgraded or removed.
* No model weights were altered or downloaded (the existing local QA model was **read** by loading it for inference; that is read-only use).
* No environment variable or config file was written. `.env` was never read or printed.
* No migration was run; no database row was created, updated or deleted. **No database was contacted at all** (see §13).
* No uploaded document, generated file, user data or model artifact was deleted. No cleanup script was run.
* No `git reset`/`clean`/checkout; nothing was staged, committed, pushed, merged or rebased.
* No existing report was overwritten (the required path did not exist — verified in §3).

**Temporary artifacts:** all probe fixtures were created inside a single `tempfile.mkdtemp(prefix="documind_audit_6ag_")` directory and removed by that script (`TMPDIR removed: True`, §18). No artifact was created inside the repository.

**Honesty rule applied:** where end-to-end verification was impossible, the capability is reported as **NOT VERIFIED** or **BLOCKED**, never as missing or working. Distinctions between *code exists*, *code runs*, and *behaviour verified end-to-end* are kept explicit throughout (§14, §17).

---

## 3. Repository Baseline and Git State

Captured **before** any test or probe, from `backend/`:

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Staged changes | **0** |
| Unstaged (tracked) modifications | **330** |
| Untracked files | **716** |
| `git status --porcelain` entries | **385** |
| Required output path already exists? | **No** — `architecture/DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md` did not exist, so the required exact path is used and nothing was overwritten |

The working tree was **not clean** at baseline (330 modified tracked files + 716 untracked, largely `__pycache__`/`uploads`/report artifacts). This is pre-existing state and is **not** attributed to this audit. `git status` also emits CRLF conversion warnings (`LF will be replaced by CRLF`) for ~30 tracked files — a pre-existing Windows checkout condition, not a content change.

`backend/architecture/` already contains the STEP 1.6AA–1.6AF safety series (filesystem/POSIX/Windows-API gates) up to `STEP1_6AF_WINDOWS_API_LINUX_READINESS_AND_INDEPENDENT_REVIEW_2026-10-14.md`. This audit is a **separate deliverable** in that evidence directory and is not part of the 1.6x filesystem-safety series.

---

## 4. Architecture and Execution-Path Overview

**Production stack (verified from source, not from README):**

* FastAPI application; routers registered in `backend/main.py:103-111`: `auth`, `documents`, `chat`, `verification`, `reliability`, `user`, `embeddings`, `settings`, `voice`. **No generative/LLM route exists.**
* PostgreSQL + pgvector is the production store (`backend/config.py:43`), SQLAlchemy async ORM, Alembic migrations `000`–`007`.
* Extraction: PyMuPDF 1.28.2 (PDF), python-docx 1.2.0 (DOCX), UTF-8 (TXT) — `backend/requirements.txt:14-15`, `backend/documents/processing.py:34-36`.
* Embeddings: `sentence-transformers` `all-MiniLM-L6-v2`, 384-dim (`backend/embeddings/model.py`).
* Answering: **local fine-tuned DistilBERT extractive QA** at `backend/models/documind-qa` (`backend/chat/qa_model.py`). No external fallback model.

**Ingestion path (traceable, with references):**

```
POST /api/documents/upload                     documents/routes.py:336
  → extension + magic-byte validation          routes.py:372-388 (ALLOWED_TYPES = pdf|docx|txt, routes.py:62)
  → user-scoped storage + SHA-256 dedupe       storage/file_store.py
  → _process_document                          routes.py:180-320
      Step 1 extract_text(path, type)          documents/processing.py:633 (dispatch) → extract_pdf:187 / extract_docx / extract_txt
      Step 2 chunk                             routes.py:214-231  (resolve_chunker_version → default "legacy" → chunk_text:658)
      Step 3 embed                             routes.py:238-248  (embeddings.model.embed_texts)
      Step 4 structure elements (PDF only)     routes.py:255-278 (documents/parser.parse_pdf → replace_document_structure)
      Step 5 structural graph                  routes.py:290-308 (graph.service.replace_document_graph)
      Step 6 status = ready                    routes.py:310-314
   any step fails → status = "error"           routes.py:198-208, 216-233, 248-253, 277-282, 305-308, 315-320
```

**PDF extraction detail — the decisive omission:**

```
extract_pdf                                    documents/processing.py:187
  for table in page.find_tables():             line 203   ← tables ARE extracted (verbatim cell grid)
  for index, block in enumerate(page_dict["blocks"]):
      if block.get("type") == 1: continue      line 249   ← IMAGE BLOCKS ARE SKIPPED, unconditionally
```

There is no second pass over `page.get_images()`, no `page.get_pixmap()`, and no OCR fallback. `documents/processing.py` contains none of the strings `tesseract`, `ocr`, `get_images`, `extract_image`, `get_pixmap` (verified by source inspection at runtime).

**Question-answering path:**

```
POST /api/chat/ask                             chat/routes.py:314
  AskRequest = { question: str, topK: int = 5 } chat/routes.py:26-28
  → Brain.process(ctx)                          brain/__init__.py (classify → plan → retrieve → context → QA → gate → outcome)
      semantic retrieval (pgvector cosine)      chat/rag.py:163-205  ("ORDER BY dc.embedding <=> CAST(:embedding AS vector)")
      structural retrieval + RRF fusion         chat/rag.py:1070-1146 (fuse_dual_path), 1149-1202 (retrieve_dual_path)
      context budgeting in TOKENS from the QA window  chat/rag.py:363-440, get_max_input_length() = 384
      extractive span selection                 chat/qa_model.py:answer_question (n_best=20, max_answer_length=100)
      evidence gate → Outcome                   brain/gate.py (SUCCESS | PARTIAL | INSUFFICIENT_EVIDENCE | UNAVAILABLE | FAILED)
  → AskResponse { answer, confidence, sources[], insufficientContext, question, reliability, outcome }
```

**Frontend path:** `src/lib/api.ts` (typed client, JWT from `localStorage`) → `src/context/WorkspaceContext.tsx` → `src/pages/WorkspacePage.tsx` renders `{msg.text}` as **raw text**, an "Insufficient context…" notice (`:522-526`), and up to **three** sources with document name + `p.{page}` + retrieval path (`:527-560`).

**Conclusion of the path trace:** the pipeline is text-in → text-span-out. Images, scans, equations-as-images and diagrams have no representation at any stage, and there is no generation step that could produce an exam-length answer or a new diagram.

---

## 5. Mark-Wise Answer Generation Audit

**Verdict: NOT IMPLEMENTED.** No part of the requested behaviour exists. Answers are single extracted spans; there is no mechanism by which mark count could change them.

Answers to the ten required questions:

| # | Question | Finding | Evidence |
| --- | --- | --- | --- |
| 1 | Can a user select the marks? | **No** | No marks/length control in `src/pages/WorkspacePage.tsx`; the only depth-like control is Settings → "ANALYSIS DEPTH" 1–5 (`src/pages/SettingsPage.tsx:281-288`) |
| 2 | Does the selected value reach the backend? | **Not for answers.** The settings depth is persisted (`settings/routes.py:174-175` → `UserSettings.processing_depth`) but **no answer-path module reads it** — `processingDepth`/`processing_depth` appears only in the settings routes, the model, and settings tests | grep across `backend/**/*.py` (§18) |
| 3 | Is the selected value validated? | **Marks: N/A.** The one real answer-path knob, `topK`, is **unvalidated** (`chat/routes.py:28` `topK: int = 5`, no `Field(ge=…, le=…)`), so an arbitrary integer can be requested | `chat/routes.py:26-28` |
| 4 | Does it affect the actual generation instructions? | **No generation instructions exist.** There is no prompt, no LLM, no template; the model selects a span | `chat/qa_model.py` (module docstring: "This does NOT fall back to any external pre-trained model") |
| 5 | Does it affect retrieval depth or context selection? | **No.** Retrieval depth is fixed by `topK` (default 5) and the context budget is a hard function of the model window (`384` tokens, `chat/rag.py:381-386`) | `get_max_input_length() → 384` (runtime) |
| 6 | Does output become meaningfully more detailed as marks increase? | **No — impossible.** Direct inference produced 16-char and 15-char answers to factual questions (single tokens) | runtime probe (§13, §18) |
| 7 | Does it avoid repetition and irrelevant filler? | **Not applicable** — no generation, so no filler; but also no elaboration | — |
| 8 | Does it preserve technical accuracy and source grounding? | Grounding yes (span must exist in supplied context: `context[start:end] == answer` verified `True` in all three probe questions); elaboration no | runtime probe |
| 9 | Does it distinguish a short answer from a complete exam-ready answer? | **No.** There is only one output mode: a single span | `AskResponse` has no length/depth field |
| 10 | What happens when sources are insufficient? | The gate abstains honestly; the UI shows "Insufficient context in documents to answer this question." | `brain/gate.py`; `WorkspacePage.tsx:522-526`; probe returned `score=0.0` → `INSUFFICIENT_EVIDENCE` |

**Direct inference evidence (this audit, read-only, §13 T1/T2):**

| Question | Answer | Score | Exact substring of context | Chars | Words |
| --- | --- | --- | --- | --- | --- |
| Which embedding model does DocuMind use? | `all-MiniLM-L6-v2` | 0.2024 | ✅ | 16 | 1 |
| How many dimensions do the embeddings have? | `384-dimensional` | 0.5401 | ✅ | 15 | 1 |
| What is the capital of France? | `Doc` | 0.0 | ✅ | 3 | 1 |

**Answer-length ceiling:** `max_answer_length = 100` **tokens** and `max_input_length = 384` tokens (`backend/models/documind-qa/inference_config.json`). Both are modelling limits of span extraction, not formatting choices; even at 100 tokens, the output is one contiguous quote rather than an organised answer with headings, components, examples, limitations or a conclusion.

**Assessment against the requested structures:** the 6/8/10/15-mark shapes (introduction → explanation → components → example → conclusion) are **not achievable** with this architecture, and no partial credit is warranted: not one of the four shapes has a partial implementation, because there is no answer-composition stage at all.

**Unresolved question (recorded, not answered by this audit):** whether the product intends marks to drive *retrieval breadth* only (e.g. `topK`) or true answer composition. Answering it requires an architecture decision (§16 P4), and it is the single largest determinant of the roadmap.

---

## 6. Diagram Requirement Detection Audit

**Verdict: NOT IMPLEMENTED** — for **both** explicit and implicit detection. The six capabilities are reported separately as required:

| # | Capability | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Explicit diagram-request detection ("draw a neat diagram", "illustrate the architecture", "represent the working using a flowchart") | **NOT IMPLEMENTED** | No keyword/intent/classifier branch for diagrams. The request classifier (`backend/brain/classifier.py`) produces no diagram intent, and `AskRequest` carries no diagram flag (`chat/routes.py:26-28`) |
| 2 | Diagram necessity / usefulness assessment (diagram would materially help) | **NOT IMPLEMENTED** | No reasoning over question content beyond extraction; no code path evaluates "would a diagram help" |
| 3 | Retrieval of an existing diagram | **NOT IMPLEMENTED** | §7 |
| 4 | Generation of a new diagram | **NOT IMPLEMENTED** | §8 |
| 5 | Rendering / delivery of a diagram to the user | **NOT IMPLEMENTED** | Message text is rendered as raw text (`WorkspacePage.tsx:525`); no renderer dependency in `package.json` |
| 6 | Explanation of the diagram in the answer | **NOT IMPLEMENTED** | No composition stage (§5) |

**Why a prompt would not change this:** adding the words "include a diagram" to any instruction would not create a capability. There is no prompt template in the repository at all (the QA model is invoked directly with `(question, context)` — `chat/qa_model.py`), so there is nothing that could even carry such an instruction. Any future detection would have to be a genuine new component.

**Risk:** because there is no detection, a student asking "draw a neat diagram of the ingestion pipeline" receives a short extracted text span (possibly a sentence describing the pipeline) with no acknowledgement that a diagram was requested. The response is not *wrong*; it is silently non-responsive to the request's primary requirement.

---

## 7. Existing Diagram Retrieval Audit

**Verdict: NOT IMPLEMENTED.** Diagrams embedded in uploaded documents are neither preserved nor retrievable.

| Required inspection point | Finding | Evidence |
| --- | --- | --- |
| PDF image extraction | **Absent** — image blocks are skipped before any use | `documents/processing.py:249` |
| Figure / caption association | **Absent** — a caption is extracted as plain paragraph text with no link to any image. The probe's "Figure 1: …" text was extracted as ordinary text while the adjacent image was discarded | runtime probe (§13 T4) |
| Page-number preservation | Present for text (1-based page on every element; `ExtractedElement.page`), but no figure has a page because no figure exists | `documents/processing.py:44-46`, probe `pages seen` |
| Image storage / references | **Absent** — no image bytes are written, and no column/table holds an image reference (`documents/models.py`, migrations `000`–`007` inspected) | — |
| Figure descriptions / multimodal representations | **Absent** — no vision model, no caption model, no image embeddings | module availability probe: no vision/multimodal packages |
| Retrieval metadata | **Absent** for figures. Note `evidence_kind` supports only `chunk`, `structure_element`, `table_row` (`chat/routes.py:66-70`) | — |
| Text-chunk ↔ figure association | **Absent** | — |
| Frontend display | **Absent** — no `<img>` for document content; `ChatSource` has no image field (`src/types/index.ts:26-45`) | — |
| Source attribution for figures | **Absent** | — |

**Detailed probe (this audit, §13 T4):** a page containing a ruled table, paragraph text, a caption "Figure 1: Architecture of the ingestion pipeline.", and a 7,429-byte embedded PNG yielded exactly 4 elements: `{heading: 1, paragraph: 2, table: 1}`. The caption was recovered as text; the image contributed nothing and produced no element. The token rendered inside the raster image (`SCANNEDONLY ALPHA TOKEN`) was absent from the extracted text — confirming that no image content passes through any decoding step.

**Can the system distinguish the correct figure from unrelated figures?** **No** — there is nothing to distinguish; no figure reaches retrieval. Consequently, the honest statement is: **only text (including captions as ordinary paragraphs) is indexed; original diagrams cannot be displayed.**

---

## 8. Diagram Generation Audit

**Verdict: NOT IMPLEMENTED** for every method in the requested list.

| Method | Status | Evidence |
| --- | --- | --- |
| Flowchart generation | NOT IMPLEMENTED | no library, no code |
| System architecture diagrams | NOT IMPLEMENTED | same |
| Block diagrams | NOT IMPLEMENTED | same |
| UML / sequence diagrams | NOT IMPLEMENTED | same |
| Graph / plot generation | NOT IMPLEMENTED | `matplotlib`, `plotly` not installed |
| Mermaid or other text-to-diagram | NOT IMPLEMENTED | no `mermaid` package; no mermaid string emitted anywhere in `backend/` or `src/` |
| Programmatic SVG generation | NOT IMPLEMENTED | `graphviz`, `pydot` absent; no SVG writer in `backend/` |
| Image-generation integration | NOT IMPLEMENTED | no image-generation endpoint or model; no generative client (`openai`, `anthropic`, `google.generativeai`, `litellm`, `ollama` all absent) |
| Frontend rendering of generated diagrams | NOT IMPLEMENTED | frontend deps are `react`, `react-dom`, `three` only; no renderer; text-only message body |

**The four-way distinction the task requires, honestly reported:**

* **Textual description of a diagram** — possible only incidentally, and only if the source document literally contains such a description as text (e.g. a sentence beginning "Figure 1: …"). This is retrieval of source prose, **not** diagram authoring.
* **Diagram source code** — never produced.
* **A successfully rendered diagram** — never produced.
* **A technically correct diagram appropriate to the question** — never produced.

Runtime module-availability probe result (`find_spec`): `graphviz False`, `pydot False`, `matplotlib False`, `plotly False`, `mermaid False`, `diagrams False`.

---

## 9. Scanned PDF and OCR Audit

**Verdict: NOT IMPLEMENTED — verified negative by direct execution.**

| Required inspection point | Finding |
| --- | --- |
| PDF text extraction | Implemented (PyMuPDF text blocks) — `documents/processing.py:221,230` |
| Page-level extraction fallback **to OCR** | **Absent.** The only fallback is from `get_text("dict")` to `get_text("text")` (plain text, same engine, no OCR) — `documents/processing.py:227-242` |
| OCR engine integration | **Absent.** `pytesseract`, `tesserocr`, `easyocr`, `paddleocr`, `ocrmypdf` are all not installed (`find_spec → False`) and none appears in `backend/requirements.txt`. No OCR code string exists in `documents/processing.py` |
| OCR invocation conditions | **Do not exist** — nothing detects "little or no usable text" per page; there is no per-page text-density check |
| OCR language configuration | **Absent** (no engine to configure) |
| Image preprocessing | **Absent** — no deskew/denoise/binarisation; `pdf2image` also absent |
| Rotation / orientation handling | **Absent** |
| Multi-column reading order | Partially addressed for **digital** text only, via PyMuPDF bounding-box ordering `(y0, x0)` (`documents/processing.py:183-246`, documented in `evaluation/reports/structural_retrieval_fix_report.md`). It does not apply to image content |
| Confidence scores | **Absent** |
| OCR error handling | **Absent** |
| Unsupported / corrupted file handling | **Implemented and tested** (`ALLOWED_TYPES` + magic-byte validation; `tests/integration/documents/test_file_validation.py` passed in the integration run) |
| Page-number tracking | Implemented for digital pages (1-based) |
| Indexing of OCR-derived text | **N/A** — no OCR text exists |
| Retrieval of OCR-derived content | **N/A** |
| Is OCR actually invoked when text extraction returns little/no text? | **No — verified.** Extraction of an image-only page returns nothing, and there is no OCR call to make |

**Direct evidence — scanned-only PDF (image pages only):**

```
--- SCANNED-ONLY pdf (image pages only) ---
  element count: 0
  element types: {}
  page numbers seen: []
  total extracted chars: 0
  legacy chunk_text -> chunks: 0
```

**Consequence in the ingestion pipeline (traced):** `extract_text` returns `[]` → `_process_document` sets `status = "error"`, `embedding_status = "error"`, `chunk_count = 0` (`backend/documents/routes.py:198-208`). The failure is **honest** (no fabricated success, no fabricated text), but **the capability is entirely absent**: a scanned lecture note or an image-based question paper cannot be ingested at all.

**Dependency ≠ capability:** this audit confirms there is not even a dependency to mistake for capability. `backend/requirements.txt` was inspected in full; the only image-related package is `pillow` (used by Media Verification, `backend/verification/`, which is a deepfake-screening feature for standalone image uploads at `/api/verification/analyze` and is **unrelated** to document OCR — it neither reads documents nor writes text into the document corpus).

---

## 10. Mixed-Document Processing Audit

**Verdict: PARTIALLY IMPLEMENTED for ingestion, but silently lossy — the highest-severity functional risk found by this audit.**

**Direct evidence — mixed PDF (page 1 digital text + ruled 4×3 table + embedded PNG; page 2 image-only scan):**

```
--- MIXED pdf ---
  element count: 4
  element types: {'heading': 1, 'paragraph': 2, 'table': 1}
  page numbers seen: [1]           ← page 2 (the scan) produced nothing
  table elements: 1 | table_data rows: [4] | cols: [3]
  raster-image text present? (SCANNEDONLY): False
  any 'figure' element: False
  total extracted chars: 246
  legacy chunk_text -> chunks: 4 · max chunk 128 chars
```

**What works:** every digital page is extracted together with its structure (headings, paragraphs, tables) into a single ordered element stream, and page numbers are preserved per element.

**What is lost, and why it matters:** the scanned page contributes **zero** elements. Because pages 1..n are processed independently inside `extract_pdf` and the caller only checks whether the *whole* document produced **any** elements (`routes.py:198-208`), a mixed document with at least one digital page proceeds to embedding, structure and graph construction and is marked **`ready`** (`routes.py:310-314`). The user therefore receives a searchable document that is **silently missing an unknown subset of its pages** — with `chunkCount`, `pagesRepresented` and insights all looking healthy. This is the "half-truth the project forbids" pattern already named in its own code comments (`routes.py:296-303`), occurring here at the page level.

**Unresolved question:** whether the product prefers (a) per-page OCR so mixed documents are complete, or (b) a per-page "unreadable page" record surfaced to the user/provenance. Both are acceptable; silently marking the document `ready` is not.

---

## 11. Table, Equation, and Structure Preservation Audit

For each structure type, the four required questions (preserved in extraction? in metadata? available to retrieval? used by generation? displayed/cited?) are answered from source + probes.

| Structure | Extracted representation | Metadata | Retrieval | Used by answer | Displayed / cited | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **Table boundaries + cell relationships** | Yes — `find_tables()` → `table_data` rows×cells, verbatim (`processing.py:203-214`); aggregate text joined with `" \| "` (`_pdf_table_element`) | Yes — `ExtractedElement.table_data`, `ParsedElement.table_data`, `document_table_rows` (migration `007`) | Partially — tables are persisted as one aggregate `table` structure element **and** as per-row records, but the row band is **default-OFF** (`DOCUMIND_TABLE_EVIDENCE`, `rag.py:643-678`) | Only as text within a chunk | Cited as a chunk/structure element with page; **not** rendered as a table in the UI (`{msg.text}`, plain text) | **PARTIALLY IMPLEMENTED** |
| **Row/column headers, merged cells** | Header row is preserved as data; the row serializer repeats the header only when a table has >1 row (`documents/tables.py:109`). Merged cells are neither detected nor reconstructed — PyMuPDF cell text only | `is_header` flag (`documents/models.py:108`) | As above | As above | No | **PARTIALLY IMPLEMENTED** |
| **Equations / mathematical notation** | **No** — no LaTeX/MathML/symbolic reconstruction; math rendered as vector/Type3 glyphs or images is dropped with other non-text objects | No | No | No | No | **NOT IMPLEMENTED** |
| **Code blocks** | Only incidentally, as monospace paragraph text; no language detection or fenced-block preservation | No | As plain text | As plain text | Plain text | **NOT IMPLEMENTED as a structure type** |
| **Headings / section hierarchy** | Yes — PDF via font-size/bold heuristics (labelled INFERRED in source, `processing.py:139-157`); DOCX via `Heading N` styles (authoritative); TXT via Markdown `#`; `heading_path` maintained and prepended for embedding context | `heading_path`, `section`, `heading_level` on elements, chunks and structure elements | Yes — `heading_path`/`section` selected and returned; `RETRIEVAL_STRUCTURAL` element stream | Yes (as context text) | Yes — shown in the source trail (`WorkspacePage.tsx:536-544`) | **IMPLEMENTED** |
| **Figure captions** | Captions are extracted as ordinary paragraph text; **no link to any figure** (no figure exists) | No association | Only as text | Only as text | As text | **NOT IMPLEMENTED (as figure metadata)** |
| **Page references** | Yes — 1-based page per element/chunk (`processing.py:44-46`) | Yes — `DocumentChunk.page`, `DocumentStructureElement.page_number` | Yes — `dc.page` selected (`rag.py:185`) | Indirect (context) | Yes — `p.{page}` in sources | **IMPLEMENTED** |
| **Reading order** | Yes for digital PDF — merged table/text event stream sorted by real PyMuPDF `(y0, x0)` bounding boxes with deterministic tie-breaks (`processing.py:183-246`). Note: known non-determinism across PyMuPDF versions for two-column layouts (recorded in the project's own evaluation, `phases/phase3f_evaluation_report.json:4053`) | Ordering = `sequence_index` | Yes | Yes | Order in which sources appear | **IMPLEMENTED (documented caveat for multi-column)** |
| **Figure/table ↔ surrounding paragraph relationships** | Table → heading ancestry via `heading_path`/`parent_source_id` (`parser.py:_build_elements`). Figure → nothing | Partial | Partial | Partial | No | **PARTIALLY IMPLEMENTED** |

**Chunking caveat (verified):** the configured production chunker is **`legacy`** — `settings.chunker_version = "legacy"` (runtime) → `chunk_text` (1000 chars / 200 overlap, `processing.py:658`). The structure-aware chunker `chunk_elements` (`documents/chunking.py`, with `table_atomic` / `table_rows` strategies at `:632-697`) exists and is tested, but is **not the default** and is not exercised by the probe path. Under the legacy chunker a table can be split mid-grid by the 1000-char window; the probe's small table survived intact in one chunk, but that is a property of the fixture, not a guarantee.

**Not structure-aware merely because embeddings exist:** confirmed — the embedding step (`routes.py:238-248`) embeds chunk text only; it conveys no table/equation/figure structure beyond the text itself.

---

## 12. Source Grounding and Citation Audit

**Verdict: IMPLEMENTED and code/API-verified; NOT verified end-to-end (no live database or server in this environment).**

| Inspection point | Finding | Evidence |
| --- | --- | --- |
| Retrieval results | Real pgvector cosine over `document_chunks` scoped to the authenticated user (`chat/rag.py:163-205`); dual-path semantic + document-graph with RRF fusion (`:1070-1202`) | source + `tests/unit/graph/test_structural_retrieval.py` etc. (passed in the unit run) |
| Context assembly | Token-budgeted, sentence-aligned truncation against the QA window (`chat/rag.py:323-440`); budget = `max_input_length(384) − overhead − safety margin` | `get_max_input_length() → 384` (runtime) |
| Source metadata | `SourceOut` carries `chunkId, content, score, documentId, documentName, page, headingPath, section, elementType, tokenCount, chunkerVersion, retrievalPath, fusionScore, structuralHops, evidenceKind, tableElementId, rowIndex, headerRepeated` (`chat/routes.py:33-85`) | source |
| **Page-number preservation** | End-to-end in code: extractor sets `page` → `DocumentChunk.page` → `dc.page` selected → `SourceOut.page` → UI `p.{src.page}` | `processing.py:44-46`; `rag.py:185`; `chat/routes.py:49`; `WorkspacePage.tsx:540,548` |
| Citation generation | Chunk-level provenance only; **no sentence-level or claim-level citation**, and no figure citation | `SourceOut` has no span/claim field |
| Citation rendering | UI shows **at most three** sources per answer (`msg.sources.slice(0, 3)`, `WorkspacePage.tsx:530`) with document name, page, retrieval path and a heading/chunk trail | source |
| Missing-evidence handling | The gate abstains on no-evidence, empty answer, and a zero-probability span (`score <= 0.0`) — `brain/gate.py:126-137`; the response sets `insufficientContext` and the UI states it explicitly | source + probe (`score = 0.0` for the unsupported question) |
| Hallucination controls | Strong: the answer is **required to be a substring of the supplied context** (`answer_span.py` + `chat/qa_model.py:211-260`); an extractive model cannot invent text. Verified: `context[start:end] == answer` was `True` for all three probe questions | runtime probe |
| Confidence / reliability indicators | Real, not fabricated: `qaConfidence`, `retrievalScore`, `avgRetrievalScore`, `sourceCount`, `factualGrounded`, `insufficientContext`, path counts, `evidenceCoverage`, `pipelineVersion` (`chat/routes.py:88-110`); persisted for the Reliability Center | source + `tests/integration/reliability/*` (passed) |

**Honest limits of the citation claim:** (a) a page number is *recorded at ingestion* and *reported*, but this audit could not observe a full answer-to-page check against a real document because the end-to-end path needs PostgreSQL + pgvector + a running server, which is **BLOCKED** here (§13); (b) the extractive span is *not* attributed to a specific sentence inside the chunk, so "this sentence on this page supports this claim" is not expressible; (c) the UI's three-source cap hides additional retrieved sources, which the reliability payload does still count (`omittedSourceCount`).

**Answers present vs absent in the source:** absent-answer behaviour is verified at model+gate level (probe: score 0.0 → abstention rule). Present-answer behaviour is verified for the model in isolation (two correct single-token spans) and for retrieval at unit/integration level, but **not** in one live end-to-end run.

---

## 13. Test Environment and Test Results

**Environment (probed):** Windows, MSYS/MINGW64 bash; `backend/venv/Scripts/python.exe` (the project virtualenv). **No PostgreSQL server is reachable and none was contacted** — the integration fixtures that need one self-skip or refuse (`tests/fixtures/integration_db.py:294`, `tests/fixtures/disposable_db.py:36`). No live backend server was started, so browser E2E tests skip (`tests/fixtures/live_server.py:37`). No dependency was installed; only packages already present in `backend/venv` were imported.

### 13.1 Existing suites actually executed

| Suite | Command | Collected | Result | Exit |
| --- | --- | --- | --- | --- |
| Unit | `venv/Scripts/python.exe -m pytest -q tests/unit` | 1368 | **1345 passed, 23 skipped**, 1 warning | **0** |
| Integration | `venv/Scripts/python.exe -m pytest -q tests/integration` | 275 | **274 passed, 1 error, 0 failed** | **1** |
| E2E (browser) | `venv/Scripts/python.exe -m pytest -q tests/e2e` | 6 | **6 skipped** (live server unreachable) | **0** |

**The single integration error is the project's own fail-closed safety guard, not a defect in the feature under audit:** `tests/integration/rag/test_real_e2e_validation.py::test_real_e2e_validation` errors at fixture setup with

```
evaluation.isolation.UnsafeEvaluationTarget: REFUSING the isolated database fixture:
missing enforceable create authorization. A valid isolated URL and an absent database name
do not authorize creation.
```

This is deliberately by design (`backend/evaluation/isolation.py:415-437`) and it also satisfies this audit's own prohibition on database creation/mutation. Reported as **BLOCKED**, never as a pass.

**The 23 unit skips** are environment-conditional and were not counted as passes; they include descriptor-relative deletion tests needing POSIX `dir_fd` (`tests/unit/scripts/test_descriptor_relative_deletion.py:42`), race/windows-junction tests needing symlink or `mklink` privileges (`test_pycache_prune_safety.py:58-68`, `test_race_substitution_deterministic.py:245`), tokenizer-dependent tests (`test_phase3d_chunking.py:511`, `test_answer_span.py:47`), and evaluation tests with no artifacts present.

**No frontend tests exist** to run: 0 files match `*.test.*` / `*.spec.*` under `src/`, and `package.json` declares no test runner (no vitest/jest). Reported as **NOT APPLICABLE / NOT AVAILABLE**, not as "frontend verified".

### 13.2 Test matrix (T1–T14)

| ID | Case | Fixture used | Method | Observed result | Exit | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Marks selection 6/8/10/15 | — | none possible | No marks parameter, no control, no composition stage; model returns one span regardless | n/a | **NOT IMPLEMENTED** |
| T2 | Missing marks value / validation | — | source inspection | Marks N/A. The answer path's only knob `topK` has a default of 5 and **no range validation** (`chat/routes.py:28`) | n/a | **NOT IMPLEMENTED (marks) / DEFECT (topK unvalidated)** |
| T3 | Explicit diagram request | synthetic question | source inspection (no detection code exists) | Question treated as plain text; no diagram flag accepted or produced | n/a | **NOT IMPLEMENTED** |
| T4 | Diagram retrieval from a document | synthetic PDF with caption + embedded 7,429-byte PNG | `extract_text(path,"pdf")` in an isolated temp dir | 4 elements `{heading, paragraph×2, table}`; caption recovered as text; image contributed nothing; `figure` element: **False**; raster token absent | 0 | **NOT IMPLEMENTED** |
| T5 | Diagram generation | runtime `find_spec` for graphic libs | module availability probe | `graphviz/pydot/matplotlib/plotly/mermaid/diagrams` all **False**; no SVG writer; text-only UI | 0 | **NOT IMPLEMENTED** |
| T6 | Digitally generated PDF (text extraction) | synthetic digital PDF (text + ruled table + image) | `extract_text` probe + unit suites | Text, heading, table extracted with page numbers preserved. Full retrieve→answer path not run (needs DB) | 0 | **PARTIALLY VERIFIED** (extraction verified; end-to-end BLOCKED) |
| T7 | Fully scanned PDF (OCR → index → retrieve → answer) | synthetic image-only PDF | `extract_text` probe | **0 elements, 0 chunks**; pipeline marks the document `error` | 0 | **NOT IMPLEMENTED** (verified negative) |
| T8 | Mixed PDF (digital + scanned pages) | synthetic 2-page mixed PDF | `extract_text` probe | Only the digital page extracted (`pages seen = [1]`); scan silently dropped; document would still become `ready` | 0 | **PARTIALLY IMPLEMENTED — silently lossy** |
| T9 | Table question | synthetic ruled 4×3 table + `tests/unit/documents/test_table_rows.py`, `tests/integration/documents/test_table_row_persistence.py` | probe + suites | Grid extracted verbatim (4 rows × 3 cols); row evidence persistence tests passed; retrieval band default-OFF | 0 | **PARTIALLY VERIFIED** |
| T10 | Equation question | — | source inspection | No equation extraction or notation handling anywhere | n/a | **NOT IMPLEMENTED** |
| T11 | Missing evidence | synthetic unsupported question ("capital of France") + `brain/gate.py` | direct model inference + source | Model returned `'Doc'` with `score = 0.0`; gate rule abstains on zero-probability spans and sets `insufficientContext` | 0 | **PARTIALLY VERIFIED** (model+gate verified; full API path BLOCKED) |
| T12 | Page citations correct document + page | — | source trace (`page` → `dc.page` → `SourceOut.page` → UI) | Code path complete and consistent; live end-to-end correctness **not observable** without DB/server | n/a | **IMPLEMENTED BUT UNVERIFIED (end-to-end)** |
| T13 | Corrupted / unsupported file rejection | in-repo tests: `tests/integration/documents/test_file_validation.py` | pytest | Passed within the 274 passing integration tests | 0 | **PASS** (API level) |
| T14 | Existing regression suites | `tests/unit`, `tests/integration`, `tests/e2e` | pytest | see §13.1 (1 error by design, 6 e2e skips, 23 unit skips) | 0 / 1 / 0 | **PASS with documented BLOCKED rows** |

**Tests deliberately NOT treated as evidence:** no test was written that merely asserts a function or dependency exists, and no substitute test was used to claim a skipped case passed.

### 13.3 Direct capability probes (this audit's own execution)

All probes ran in one isolated `tempfile.mkdtemp(prefix="documind_audit_6ag_")` directory, removed afterwards. Full outputs are reproduced in §18.

1. **Raster generation:** PNG of a page containing `SCANNEDONLY ALPHA TOKEN`, 7,429 bytes.
2. **Mixed PDF / scanned-only PDF extraction** — results in §7, §9, §10 above.
3. **QA model direct inference** — `model available: True`, load 8.4 s, three questions, results in §5 (answers are exact context substrings; single words).
4. **Module availability** — OCR / generative-LLM / diagram libraries all absent.
5. **`get_max_input_length() → 384`**; configured chunker `legacy`.

---

## 14. Evidence-Based Capability Matrix

| Capability | Existing implementation | Direct evidence | Test status | Gap | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| 6-mark answers | None | `AskRequest{question, topK}` `chat/routes.py:26-28`; span answers 16/15 chars (§5 probe) | NOT IMPLEMENTED | No composition stage; extractive model | Exam questions unanswerable in required form | Phase 4: architecture decision for a generative answer model |
| 8-mark answers | None | as above | NOT IMPLEMENTED | as above | as above | Phase 4 |
| 10-mark answers | None | as above | NOT IMPLEMENTED | as above | as above | Phase 4 |
| 15-mark answers | None | as above; `max_input_length 384`, `max_answer_length 100` | NOT IMPLEMENTED | as above | as above | Phase 4 |
| Mark-selection validation | None (marks); `topK` unvalidated | `chat/routes.py:26-28` | NOT IMPLEMENTED / DEFECT | No parameter, no validation | Unbounded `topK` tolerated | Add validated marks/length contract **after** Phase 4 decision |
| Diagram requirement detection | None | no intent/flag anywhere; classifier has no diagram intent | NOT IMPLEMENTED | Whole capability | Silently non-responsive answers | Phase 5 |
| Existing diagram retrieval | None — images skipped | `processing.py:249`; probe: no `figure` element, image contributes nothing | NOT IMPLEMENTED | Image extraction, storage, caption link, retrieval metadata | Diagram questions unanswerable from source | Phase 2 (extraction) → Phase 5 (retrieval) |
| New diagram generation | None | `find_spec` all False; no SVG/mermaid emitter | NOT IMPLEMENTED | Whole capability + renderer | as above | Phase 6 |
| OCR for scanned PDFs | None | no engine installed/pinned; probe: 0 elements; pipeline → `error` | NOT IMPLEMENTED | OCR engine, per-page detection, preprocessing, indexing | Scanned notes/question papers unusable | Phase 1 (highest priority) |
| Mixed PDF processing | Digital pages only; scans dropped **silently** | probe: `pages seen = [1]` yet document becomes `ready` | PARTIALLY IMPLEMENTED | Per-page OCR or explicit unreadable-page provenance | **High** — silently incomplete corpus presented as ready | Phase 1, including the honest `ready` rule |
| Table preservation | Extraction + row persistence real; row band default-OFF; legacy chunker splits by chars | `processing.py:203-214`; `chunking.py:632-697`; `rag.py:643-678`; probe 4×3 grid | PARTIALLY VERIFIED | Enable/default policy; table rendering in UI | Table answers may miss rows | Phase 2/3 |
| Equation preservation | None | no math library or notation path | NOT IMPLEMENTED | Whole capability | Formula-based questions unsupported | Phase 2 |
| Page-level citations | Implemented in code, end-to-end unverified | `processing.py:44-46`, `rag.py:185`, `routes.py:49`, `WorkspacePage.tsx:540` | IMPLEMENTED BUT UNVERIFIED | Live verification; per-claim attribution | Mis-citation would be invisible without a live check | Phase 8 verification |
| Source grounding | Strong (extractive; answer ⊆ context) | probe: `context[start:end] == answer` True ×3; `answer_span.py` | PARTIALLY VERIFIED | End-to-end run | Low (hallucination structurally limited) | Phase 8 |
| Error handling | Strong: unsupported/corrupted rejected; failed pipeline → `error`, never `ready` | `ALLOWED_TYPES` + magic bytes; `routes.py:198-208`; T13 tests passed | PASS (API level) | Page-level honesty for mixed/scan pages | Silent partial ingestion | Phase 1 |
| Frontend integration | Upload/ask/sources UI real; no marks or diagram UI; 3-source cap | `WorkspacePage.tsx:495-560`; `package.json` deps | NOT VERIFIED (no frontend tests exist) | Marks + figure/diagram rendering | Users cannot express or receive the required output | Phase 7 |
| End-to-end behaviour | Not demonstrated in this environment | integration needs PostgreSQL (fixture refuses by design); e2e server absent | **BLOCKED** | Live end-to-end evidence | Unknown residual behaviour | Phase 8 on an authorized host |

**Classification key used:** IMPLEMENTED AND VERIFIED / PARTIALLY IMPLEMENTED / IMPLEMENTED BUT UNVERIFIED / NOT IMPLEMENTED / BLOCKED. `NOT IMPLEMENTED` is used only where inspection or execution provides sufficient evidence of absence (as in items 2–4, 6, 9, 10), never where the status is merely unknown.

---

## 15. Confirmed Defects, Risks, and Unknowns

**Confirmed defects / gaps (each with reproduction):**

* **D-1 (High) — Mixed and scanned PDFs are processed without OCR, and mixed PDFs are marked `ready` while silently missing pages.** Reproduction: §10 probe. The document-level `ready` rule checks only "any element extracted" (`routes.py:198-208`), never per-page coverage.
* **D-2 (High) — No figure/image preservation.** `processing.py:249` skips every image block; no images are stored, captioned, linked or indexed. Diagram retrieval is therefore impossible even for documents that contain the exact diagram the student needs.
* **D-3 (High) — Exam-mark answers are architecturally impossible.** The answering mechanism is single-span extraction (§5), and the "analysis depth" setting is inert for answers.
* **D-4 (Medium) — No diagram request detection or generation or rendering** (§6, §7, §8).
* **D-5 (Medium) — No equation/notation preservation** (§11). Mathematical content survives only when the PDF stores it as plain text.
* **D-6 (Medium) — `topK` is unvalidated on the answer endpoint** (`chat/routes.py:28`), and the UI caps displayed sources at three while the payload counts omissions (`omittedSourceCount`) — a user cannot see all supporting sources.
* **D-7 (Medium) — Settings "Analysis Depth 1–5" is presented as affecting AI processing but has no effect on retrieval or answers** (`settings/routes.py:174-175`; no consumer). Misleading UI affordance rather than a functional bug, but it is exactly the kind of "frontend control without working backend integration" the audit was told to distrust.
* **D-8 (Low) — `legacy` char chunker is the production default**, so the richer table/structure-aware chunker (`documents/chunking.py`) is not exercised in production despite existing and being tested (`config.py:63-68`).
* **D-9 (Low) — multi-column PDF reading order is documented as non-deterministic across PyMuPDF versions** (`phases/phase3f_evaluation_report.json:4053`), which affects layout-heavy exam material.

**Risks:**

* Students using exam material will receive short extracted spans for questions that explicitly demand diagrams and long structured answers; the system's honest abstention behaviour does not make this capability gap visible, because the answer is "not insufficient" — it is simply inadequate to the question type.
* Because images are dropped, a *caption* may be retrieved and cited as evidence for a diagram question while the diagram itself is absent — a citation that is technically real but materially misleading.
* Enabling OCR later without a per-page provenance model risks compounding D-1 rather than fixing it.

**Unknowns (not resolvable in this environment):**

* Whether the live end-to-end answer→page citation mapping is exactly correct (T12) — needs PostgreSQL + server.
* Behaviour on real scanner output (skew, noise, handwriting, multi-column scans) — no OCR exists to test.
* Whether the product intends marks to influence retrieval breadth only or true answer composition (§5 unresolved question) — an architecture decision, not discoverable from code.
* Whether a generative model is permitted by the project's constraints (the repo repeatedly forbids external fallback models for QA: `chat/qa_model.py` module docstring) — this constrains Phase 4 design and must be resolved by the owner.

---

## 16. Prioritized Implementation Roadmap

Ordering is driven by direct evidence: because nothing downstream can work on content that is never extracted, **parsing/OCR and structure preservation come first**, and mark-aware generation (which requires an architecture decision and a new model class) comes after the evidence foundation exists. This is a **proposal only**; §18 forbids implementation.

### Phase 1 — Document parsing and OCR reliability (Complexity: **High**) — highest priority
* **Verified problem solved:** scanned-only PDFs yield 0 elements → document `error` (T7); mixed PDFs silently lose pages yet become `ready` (T8/D-1).
* **Relevant existing components:** `documents/processing.py:extract_pdf` (per-page loop already exists), `routes.py` per-page status handling, `storage/` for original file retention.
* **Files likely to require modification:** `backend/documents/processing.py`, `backend/documents/routes.py`, `backend/requirements.txt`, `backend/config.py`, plus new `backend/documents/ocr.py`.
* **Proposed approach:** per-page text-density check → conditional OCR (engine to be chosen by the owner; must be local, pinned, and language-configured) → merge OCR text into the existing element stream with `page` preserved, marked as OCR-derived in metadata; if a page still yields nothing, record it and **do not** mark the document `ready` without surfacing it.
* **Dependencies and risks:** engine/weights provisioning; CPU cost and ingestion latency; tesseract language packs; must not weaken the "never fabricate text" rule.
* **Acceptance criteria:** scanned-only PDF ingests to `ready` with ≥1 chunk whose content matches the image text; mixed PDF's every page is accounted for; an unreadable page is either OCR'd or explicitly reported, never silently dropped.
* **Tests required:** synthetic scanned-only PDF, mixed PDF, rotated page, corrupted image inside a PDF, plus a negative control proving no OCR is attempted on digital pages.
* **Preconditions / unresolved:** engine choice; whether OCR runs at ingest or lazily; whether `ready` requires full-page coverage.

### Phase 2 — Structure, tables, figures, page metadata (Complexity: **High**)
* **Verified problem solved:** images are skipped (`processing.py:249`); captions are orphaned; equations are lost (D-2, D-5, §11).
* **Relevant existing components:** `ExtractedElement` metadata, `documents/parser.py` (already declares `figure` but never emits it), `documents/tables.py`, migration pattern `006`/`007`.
* **Files likely to require modification:** `documents/processing.py` (image/`get_images` enumeration + caption association), `documents/parser.py` (emit `figure`), new image storage module, `documents/models.py`, a new migration, `documents/chunking.py`.
* **Proposed approach:** enumerate page images with their bounding boxes; associate the nearest caption text by geometry; persist a stable reference (path/hash + page + bbox) and a text proxy for retrieval; add optional equation handling (keep math text if the PDF provides it; otherwise record the region as math without inventing notation); consider promoting `structure-v2` once validated.
* **Dependencies and risks:** storage lifecycle and deletion rules (`storage/file_store.py` is a hardened, audited area — changes there touch prior safety work); image-identity/provenance integrity.
* **Acceptance criteria:** a figure is persisted with page + bbox + caption link; it is retrievable by text and by caption; the figure's page matches the source.
* **Tests required:** figure extraction and caption association on synthetic PDFs; no-figure regression; storage cleanup safety.
* **Preconditions / unresolved:** where images live (filesystem vs DB) and retention policy.

### Phase 3 — Retrieval quality and source grounding (Complexity: **Medium**)
* **Verified problem solved:** the table-row evidence band is default-OFF; figure evidence has no representation; `topK` is unvalidated; only three sources are shown.
* **Relevant existing components:** `chat/rag.py` (RRF, bands), `graph/service.py`, `SourceOut`.
* **Files likely to require modification:** `chat/rag.py`, `graph/service.py`, `chat/routes.py`, `src/pages/WorkspacePage.tsx`.
* **Proposed approach:** decide and document the default for `DOCUMIND_TABLE_EVIDENCE` on measured evidence (the project's discipline: no default change without a measurement); add a figure evidence kind alongside `chunk`/`structure_element`/`table_row`; validate `topK`; surface all cited sources (not just three) behind a disclosure control.
* **Dependencies and risks:** a figure evidence kind depends on Phase 2 having persisted figures; enabling the table band by default would change production retrieval behaviour, so it must not be flipped without the measurement the project requires; over-broad `topK` limits risk degrading answer quality for short queries.
* **Acceptance criteria:** table questions retrieve row-level evidence in the default configuration (if the measurement supports it); `topK` rejects out-of-range values; every cited source is reachable in the UI.
* **Tests required:** per-band retrieval tests, RRF determinism tests, API validation tests.
* **Preconditions / unresolved:** needs Phase 2 for figure evidence; a measurement run comparable to `evaluation/experiments/run_table_evidence_measurement.py`.

### Phase 4 — Mark-aware answer generation (Complexity: **High**; requires an ADR)
* **Verified problem solved:** no marks parameter and no composition stage; extractive span answers of 15–16 chars (D-3).
* **Relevant existing components:** `chat/qa_model.py` (extractive), `brain/` orchestration, `AskRequest`/`AskResponse`, `answer_span.py` (keep for grounding).
* **Files likely to require modification:** `chat/routes.py`, `brain/adapters.py`, a new provisioning path for any new model, `src/types/index.ts`, `src/pages/WorkspacePage.tsx`.
* **Proposed approach:** architectural decision first — either (a) introduce a permitted local generative model to compose answers *grounded in* the extractive spans, with the extractive path retained as the grounding/verification layer, or (b) accept that marks only tune retrieval breadth and document the limitation explicitly. Do not silently substitute an external API (the project forbids external fallbacks for QA).
* **Dependencies and risks:** model provisioning/size/licence; must not weaken the no-hallucination property (keep span-level grounding and refuse to invent); prompt/structure policy for 6/8/10/15 shapes; latency.
* **Acceptance criteria:** for one question and one document set, four answers differ in a way that matches the requested depth rubric, each claim traceable to retrieved sources, with abstention preserved when sources are insufficient.
* **Tests required:** a rubric-based evaluation set (the repo has `evaluation/datasets/` infrastructure to extend), grounding/abstention regression, marks validation.
* **Preconditions / unresolved:** **owner decision** on generative-model permission; the repo's own constraint that the QA path must not fall back to external models.

### Phase 5 — Diagram detection and existing-diagram retrieval (Complexity: **Medium**, after Phases 2–3)
* **Verified problem solved:** no detection of explicit/implicit diagram needs; figures unretrievable (D-2, D-4).
* **Relevant existing components:** `backend/brain/classifier.py` (transparent rule-based intent classification), `backend/brain/adapters.py` (retrieval adapters), the `figure` vocabulary already declared in `documents/parser.py`.
* **Files likely to require modification:** `backend/brain/classifier.py`, `backend/brain/adapters.py`, `backend/chat/routes.py` (diagram-required flag on the request/response), `src/types/index.ts`.
* **Proposed approach:** an explicit, inspectable detector (keyword/intent rules first, consistent with `brain/classifier.py`'s transparent style) that marks "diagram required" and prefers retrieving the matching source figure when one exists; never fabricate a figure.
* **Dependencies and risks:** entirely dependent on Phase 2 (no figure exists to retrieve until then) and Phase 3 (figure evidence must be a first-class band); a rule-based detector can be over-eager, so detection must record its trigger and never convert a false positive into a fabricated diagram.
* **Acceptance criteria:** an explicit diagram request sets a diagram-required flag; when the matching figure exists it is returned with correct document + page; when it does not exist the system says so instead of silently returning prose.
* **Tests required:** detection table (explicit phrasings from §6), fixture document with two figures where only one is correct, negative control (no figure present).
* **Preconditions / unresolved:** Phase 2 delivered; how much of "implicit necessity" is in scope; must the system refuse rather than degrade?

### Phase 6 — Diagram generation and rendering (Complexity: **High**)
* **Verified problem solved:** no generator, no renderer (D-4).
* **Relevant existing components:** **none** — no diagram-generation or rendering component exists at any layer (verified by `find_spec` and by source inspection of `backend/` and `src/`).
* **Files likely to require modification:** new backend diagram module, `backend/chat/routes.py` (delivery of the rendered artifact), `backend/requirements.txt`, `src/types/index.ts`, `src/pages/WorkspacePage.tsx`.
* **Proposed approach:** a text-to-diagram representation the project can render safely (e.g. a text format with server-side rendering to an image/SVG served to the client), with the diagram **derived from retrieved source content** and cited; rendering must be sanitised (no arbitrary HTML/JS from model output).
* **Acceptance criteria:** one diagram-producing question yields a rendered, correct diagram appropriate to the source, with a source citation; a question that cannot be diagrammed does not produce a fabricated one.
* **Tests required:** rendering unit tests, sanitisation tests (untrusted model output), source-fidelity checks.
* **Dependencies and risks:** depends on Phases 2, 3 and 5; the dominant risk is **arbitrary code/markup execution** from model-produced diagram source, so rendering must be sanitised and server-side, following the project's existing "no unsafe shell / no arbitrary code execution" rules; a further risk is a technically valid but conceptually wrong diagram, which must be prevented by grounding the diagram in retrieved source content rather than in model invention.
* **Preconditions / unresolved:** owner decision on whether generated diagrams are in product scope at all; choice of diagram format and renderer.

### Phase 7 — Frontend integration (Complexity: **Medium**)
* **Verified problem solved:** no marks control, no figure/diagram rendering, three-source cap, and an inert depth slider (D-6, D-7).
* **Relevant existing components:** `src/pages/WorkspacePage.tsx` (answer + source rendering), `src/lib/api.ts` (typed client), `src/types/index.ts`, `src/context/WorkspaceContext.tsx`, `src/pages/SettingsPage.tsx` (depth slider to wire or remove).
* **Proposed approach:** add an explicit marks selector bound to the new request field; render retrieved figures and generated diagrams with their citations; disclose all cited sources; and either connect the depth setting to the answer path or stop presenting it as affecting processing.
* **Files likely to require modification:** `src/pages/WorkspacePage.tsx`, `src/types/index.ts`, `src/lib/api.ts`, `src/pages/SettingsPage.tsx` (either wire the depth setting or stop presenting it as affecting answers).
* **Acceptance criteria:** marks selection is explicit and reaches the backend; loading/empty/error/unavailable states are represented; generated or retrieved figures render with citations; the inert affordance is either wired or removed.
* **Tests required:** none exist today — a frontend test runner (e.g. vitest) must be introduced as part of this phase, with component-level tests for marks selection, source/citation rendering, and figure/diagram rendering states.
* **Dependencies and risks:** depends on the backend contracts settled in Phases 1–6; the frontend must keep representing loading, empty, error and unavailable states rather than assuming success, and must never hardcode backend data.
* **Preconditions / unresolved:** the marks contract must be fixed by the Phase 4 decision before the selector can be built; a test runner must be added to `package.json` (currently none).

### Phase 8 — End-to-end evaluation, regression and monitoring (Complexity: **Medium**, continuous)
* **Verified problem solved:** the live end-to-end path (T12/T6/T11) is unverified
* **Relevant existing components:** `tests/e2e/browser/` (6 tests, currently skipped for lack of a live server), `tests/integration/rag/test_real_e2e_validation.py` (blocked by the isolation guard), `evaluation/datasets/` corpus infrastructure, `evaluation/reports/`.
* **Files likely to require modification:** new evaluation corpora under `backend/evaluation/datasets/`, new runners under `backend/evaluation/experiments/`, and the ingestion monitoring surface (`backend/documents/insights.py`, `documents/schemas.py`) for per-page coverage. and the E2E suite cannot run without an authorized database and server (T14).
* **Proposed approach:** run the existing E2E/browser suites on an authorized host with a disposable authorized database, extend `evaluation/datasets/` with scanned/mixed/figure/marks corpora, and add per-page coverage to ingestion monitoring.
* **Acceptance criteria:** E2E suites execute with recorded exit codes; citation correctness (document + page) verified against known fixtures; ingestion reports per-page coverage.
* **Dependencies and risks:** depends on every preceding phase; running the E2E suites requires an authorized disposable database and a live server, which is exactly the authorization the current guard refuses; there is a risk of mistaking a skipped suite for a passing one, so skips must be reported explicitly.
* **Tests required:** the existing E2E/browser suites executed with recorded exit codes, citation-correctness fixtures with known document + page, scanned/mixed/figure/marks corpora, and a per-page ingestion-coverage assertion.
* **Preconditions / unresolved:** explicit authorization for disposable database creation (currently refused by design) — this is an owner/handoff item, not something this audit may grant.

---

## 17. Final Verdict and Outstanding Verification

**Overall verdict: CONDITIONAL PASS.**

The audit itself was completed with sufficient evidence for every capability classification reported. It is **not** a PASS because two verification categories remain outstanding and are not resolvable in this environment:

1. **Live end-to-end verification (BLOCKED).** PostgreSQL + pgvector are unavailable here and the project's own isolation guard refuses to create a disposable database without enforceable authorization (`evaluation/isolation.py:415-437`). Consequently T6/T11/T12 are verified only in code/model/gate isolation, and the browser E2E suite (6 tests) skipped for lack of a live server.
2. **Frontend runtime behaviour (NOT VERIFIED).** No frontend test runner exists, so UI statements in §5/§12 rest on source inspection.

It is **not** BLOCKED, because the material capability questions this audit was asked (marks, diagram detection/retrieval/generation, OCR, mixed documents, tables/equations, grounding/citations) were each answered with direct evidence — six of them with **definitive negatives** proven by execution, not by absence of a search hit.

**Capability summary:**

* **Mark-wise answers:** NOT IMPLEMENTED (extractive, single-span; no marks contract; depth setting inert).
* **Diagram detection:** NOT IMPLEMENTED (no explicit or implicit detection).
* **Diagram retrieval:** NOT IMPLEMENTED (images skipped at `processing.py:249`; `figure` declared but never emitted).
* **Diagram generation:** NOT IMPLEMENTED (no library, no generator, no renderer).
* **Scanned PDF OCR:** NOT IMPLEMENTED (no engine; image-only PDF → 0 elements → document `error`).
* **Mixed PDF processing:** PARTIALLY IMPLEMENTED and **silently lossy** (digital pages only; scanned pages dropped while the document still becomes `ready`).
* **Table and equation handling:** tables IMPLEMENTED/PARTIALLY VERIFIED (verbatim grid + row persistence, row band default-OFF, legacy chunker default); equations NOT IMPLEMENTED.
* **Source grounding and citations:** grounding IMPLEMENTED (extractive, answer ⊆ context, verified); page citations IMPLEMENTED in code and rendered, end-to-end correctness NOT VERIFIED.

**Testing:**

* Tests passed: **1619** (unit 1345 + integration 274 + e2e 0).
* Tests failed: **0**.
* Tests skipped: **29** (unit 23 + e2e 6).
* Tests blocked: **1** (integration `test_real_e2e_validation`, fail-closed database-authorization guard; not a feature failure).
* Tests not verified: T6/T9/T11 (end-to-end halves), T12; plus frontend behaviour (no test runner).

**Repository safety:**

* Production files changed: **no** (see §18 verification).
* Database changes: **none** (no database was contacted; no migration executed).
* Destructive operations: **none**; all probe fixtures were inside one temp directory, removed after use.
* Git state preserved: **yes** — HEAD `6baaa2a…`, 0 staged, and the tracked/untracked counts are unchanged from the baseline recorded in §3 (re-verified in §18).

**Report:** path and digest in the header and §18.

**Most important findings (in priority order):** (1) mixed/scanned PDFs lose content silently, with mixed documents still marked `ready`; (2) no image/figure preservation, so diagram retrieval is impossible even when the diagram is in the corpus; (3) exam-mark answers are architecturally impossible with an extractive model, and the visible "depth" control does not influence answers; (4) OCR, equation handling and diagram generation/detection/rendering are wholly absent, and the project's own docs already say so for OCR.

**Recommended next step:** authorize **Phase 1** (parsing/OCR reliability, including the honest `ready` rule) as a scoped implementation task, and in parallel obtain the owner decision on Phase 4's generative-answer question — because that decision determines whether the marks requirement is achievable at all.

---

## 18. Appendix: Evidence, Commands, File References, and Integrity Checks

### 18.1 Source references used

| Reference | Path:line |
| --- | --- |
| Answer request contract (no marks) | `backend/chat/routes.py:26-28` |
| Answer response contract | `backend/chat/routes.py:88-110` (reliability), `:113-119` (`AskResponse`) |
| Source fields incl. `page` | `backend/chat/routes.py:33-85` (`SourceOut.page` at `:49`) |
| Image blocks skipped | `backend/documents/processing.py:249` |
| Table extraction | `backend/documents/processing.py:203-214` |
| PDF read order by bbox | `backend/documents/processing.py:183-246` |
| Legacy chunker default | `backend/config.py:63-68`; `backend/documents/processing.py:658`; `backend/documents/routes.py:106-133` |
| Extraction dispatch / allowed types | `backend/documents/processing.py:633-642`; `backend/documents/routes.py:62,372-388` |
| Failure → `error` (never fake ready) | `backend/documents/routes.py:198-208, 216-233, 248-253, 277-282, 305-308, 315-320` |
| `ready` only after all steps | `backend/documents/routes.py:310-314` |
| Parser vocabulary; `figure` never emitted | `backend/documents/parser.py:46-50, 156, 169`; runtime `EMITTED_ELEMENT_TYPES` |
| Extractive QA model | `backend/chat/qa_model.py` (module docstring, `answer_question`) |
| Model limits | `backend/models/documind-qa/inference_config.json` |
| Retrieval + RRF | `backend/chat/rag.py:163-205, 1070-1146, 1149-1202` |
| Context budget | `backend/chat/rag.py:323-440`; `chat/qa_model.py:get_max_input_length` |
| Table evidence kill switch | `backend/chat/rag.py:643-678` |
| Table row serialisation | `backend/documents/tables.py:109`; `backend/documents/chunking.py:632-697` |
| Evidence gate / abstention | `backend/brain/gate.py:56-63, 118-160` |
| Settings depth (stored, unused by answers) | `backend/settings/routes.py:174-175` |
| UI answer/citation rendering; 3-source cap | `src/pages/WorkspacePage.tsx:522-560` |
| UI depth slider | `src/pages/SettingsPage.tsx:281-288` |
| Frontend dependency set | `package.json` (`react`, `react-dom`, `three`) |
| Project's own OCR declarations | `CONTEXT.md:152`; `README.md:106`; `DOCUMIND_PROJECT_CONTEXT.md:1680,1716`; `backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md:205` |
| Prior multi-column caveat | `backend/phases/phase3f_evaluation_report.json:4053` |

### 18.2 Commands executed (verbatim, with observed results)

**Baseline**

```
cd backend
git rev-parse --abbrev-ref HEAD                     → main
git rev-parse HEAD                                  → 6baaa2a0773df66e5fb26814afbe67647fb43435
git diff --cached --name-status | wc -l             → 0
git diff --name-status | wc -l                      → 330
git ls-files --others --exclude-standard | wc -l    → 716
git status --porcelain | wc -l                      → 385
ls architecture/DOCUMIND_..._AUDIT_2026-10-14.md    → No such file or directory  (required path free)
```

**Suites**

```
set -o pipefail
venv/Scripts/python.exe -m pytest -q tests/unit          → 1345 passed, 23 skipped in 65.86s   UNIT_EXIT=0
venv/Scripts/python.exe -m pytest -q tests/integration   → 274 passed, 1 error in 206.61s     INTEGRATION_EXIT=1
venv/Scripts/python.exe -m pytest -q tests/e2e           → 6 skipped in 15.18s                E2E_EXIT=0
collect-only counts: unit 1368 · integration 275 · e2e 6
```

Exit statuses were captured explicitly with `PIPESTATUS[0]` while the output was filtered through `tail`; the filter did not mask the tested command's status.

**Integration error detail (BLOCKED, by design)**

```
venv/Scripts/python.exe -m pytest -q tests/integration/rag/test_real_e2e_validation.py
→ ERROR tests/integration/rag/test_real_e2e_validation.py::test_real_e2e_validation
  evaluation.isolation.UnsafeEvaluationTarget: REFUSING the isolated database fixture:
  missing enforceable create authorization. A valid isolated URL and an absent database name
  do not authorize creation.        (backend/evaluation/isolation.py:437)
```

**Direct capability probes** (single `tempfile.mkdtemp(prefix="documind_audit_6ag_")`, deleted afterwards)

```
MIXED pdf (digital page + table + embedded image | scanned page)
  element count: 4 · types {heading 1, paragraph 2, table 1} · pages seen [1]
  table_data rows [4] · cols [3] · raster text present? False · any 'figure' element: False
  legacy chunk_text -> chunks 4 · max 128 chars
SCANNED-ONLY pdf (image pages only)
  element count: 0 · types {} · pages seen [] · total chars 0 · chunks 0
module availability: pytesseract/tesserocr/easyocr/paddleocr/ocrmypdf/pdf2image = False; PIL = True
  openai/anthropic/google.generativeai/litellm/ollama = False
  graphviz/pydot/matplotlib/plotly/mermaid/diagrams = False
documents/processing.py keywords: tesseract False · ocr False · get_images False
  extract_image False · get_pixmap False
EMITTED_ELEMENT_TYPES: ['paragraph','section','table','text_block'] · figure emitted: False
get_max_input_length(): 384
inference_config.json: {n_best 20, max_answer_length 100, max_input_length 384}
settings.chunker_version: legacy
TMPDIR removed: True
```

```
QA model direct inference (read-only load of the local model; no network, no DB)
model available: True | load 8.4s
Q: Which embedding model does DocuMind use?   → 'all-MiniLM-L6-v2' score 0.2024 · exact substring True · 16 chars
Q: How many dimensions do the embeddings have? → '384-dimensional'  score 0.5401 · exact substring True · 15 chars
Q: What is the capital of France?             → 'Doc'              score 0.0    · exact substring True · 3 chars
```

**Frontend test availability**

```
find ../src -name "*.test.*" -o -name "*.spec.*" | wc -l   → 0
grep -c "vitest\|jest" ../package.json                     → 0
```

### 18.3 Integrity checks (§16 requirements)

1. **No production source file modified.** The only file created by this audit is this report, inside `backend/architecture/` (the evidence directory). No file under `backend/**` production packages, `src/**`, prompts, configs or `requirements.txt` was written.
2. **No database mutation or migration.** No database connection was opened by any command in this audit; `alembic` was not invoked; the only DB-touching test errored at fixture setup with the project's own refusal guard.
3. **No destructive cleanup.** No cleanup script (`scripts/cleanup_path.py`, `cleanup_orphan_uploads.py`) was run. The single temp directory created by the probe script was removed by that script and its removal was verified (`TMPDIR removed: True`).
4. **Git state re-checked after all work** — see §18.4.
5. **Audit-created differences explained:** this report is the only new path attributable to the audit; all other untracked/modified entries were present at baseline.
6. **Temporary files:** the report temporarily stores the digest line; no other artifact remains. (`TMPDIR` confirmation above.)
7. **Report exists at the required exact path** (verified by re-read and by the digest computation below).
8. **Report SHA-256 recorded.** The digest line is a single physical line; the value covers every other byte of the file and excludes the digest line itself, so it is reproducible after substitution:
   `grep -v '^Report SHA-256' backend/architecture/DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md | sha256sum`
9. **Directly tested vs inspected vs inferred** is distinguished throughout: execution evidence = the probes and pytest runs (§13); source inspection = references in §18.1; inference is labelled as such (e.g. heading detection heuristics are marked INFERRED in the source itself).
10. **Blocked and unverified items are listed explicitly** in §13.1 (1 integration error, 23 unit skips, 6 e2e skips) and §14 (`BLOCKED` / `IMPLEMENTED BUT UNVERIFIED` rows), and repeated in §17.

### 18.4 Post-audit git state (to be confirmed identical to baseline)

| Item | Baseline | After audit | Difference |
| --- | --- | --- | --- |
| Branch | `main` | `main` | none |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | `6baaa2a0773df66e5fb26814afbe67647fb43435` | none |
| Staged | 0 | 0 | none |
| Unstaged (tracked) | 330 | 330 | none |
| Tracked-modified outside `architecture/` | 330 | 330 | none |
| Untracked files | 716 | **717** | **+1 — this report** |
| `git status --porcelain` entries | 385 | **385** | none (see note) |

The **only** difference is the addition of this report. No tracked file was created, modified or deleted by this audit; the 330 pre-existing tracked modifications are byte-identical to the baseline count and none of them lies outside pre-existing state.

**Note on the porcelain count being unchanged:** `backend/architecture/` was already untracked **as a directory** at baseline, and Git reports an entirely-untracked directory as a single `??` entry rather than one entry per file. Adding this report therefore increases the untracked *file* count from 716 to 717 while the porcelain entry count stays at 385; the directory is reported as `?? backend/architecture/`. This is stated explicitly rather than claiming "the Git state is unchanged": the file count did change, by exactly one audit-created file, and nothing else changed.
