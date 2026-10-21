# DocuMind — Phase 1a Decision Record (2026-10-15)

**Owner:** COORDINATOR (this file is Coordinator-owned and **append-only** — correct by appending,
never by rewriting an earlier entry).
**Status:** active record. **Not** a master-plan revision: the authoritative plan remains
`DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R5_2026-10-14.md` (referred to below as **R5**).
No R6 is created by this file, and nothing here amends R5's text, numbering or gate identifiers.

**Why this file exists.** Phase 1a (per-page completeness accounting) was implemented and then
independently verified in the same session. Several decisions and one verification verdict exist
**only in that session's transcript**, and one owner decision (the value of `MIN_USABLE_CHARS`)
has been **reopened** for an evidence review. This record is the repository-traceable home for
those decisions, their scope, their rejected alternatives, their known limitations and the gates
they depend on.

---

## 1. Basis and integrity

| Fact | Value | How it was established |
| --- | --- | --- |
| Repository / branch | `main` | `git branch --show-current` (2026-10-15) |
| HEAD | `6baaa2a` | `git rev-parse --short HEAD` (2026-10-15) |
| Staged changes | none | `git diff --cached --stat` → empty |
| Unstaged / untracked | the pre-existing working tree (Phase 1a plus earlier work) | `git diff --stat`; `git status --porcelain` |
| Working-tree changes made by this task | **this file, `CONTEXT.md`, `ARCHITECTURE.md`** — no production code, no test, no config, no migration, no dependency | see §9 |
| Plan text amended | no | R5 digest unchanged; no file under `backend/architecture/**` was rewritten |

**Authoritative artifacts consulted:** R5 (§7.2.1 verdict function, §8.3 provenance options,
§14.2 phases 1a/1b, §18 gate register, §19 deferred capabilities); the Phase 1a implementation
(`backend/documents/processing.py`, `backend/documents/routes.py`); the Phase 1a test module
(`backend/tests/unit/documents/test_phase1a_page_completeness.py`); the frontend status contract
(`src/types/index.ts`, `src/context/WorkspaceContext.tsx`); `CONTEXT.md`, `ARCHITECTURE.md`,
`AGENTS.md`; `agents/*.md`; `backend/requirements.txt`; `backend/tests/conftest.py`;
`backend/tests/fixtures/pdf_layout.py`; the OCR capability audit
(`DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md`).

**Artifact gap recorded.** No Phase 1a *implementation report* and no Phase 1a *verification
report* exist as files in `backend/architecture/` (unlike Phase 0, which has
`PHASE0_CLOSURE_2026-10-09.md`). The verification verdict below is therefore recorded here from the
session in which it was produced; no file was invented to fill the gap.

---

## 2. Verification verdict carried into this record

**Phase 1a: `VERIFIED WITH LIMITATIONS`** (2026-10-15, independent verification pass). The verified
behaviour: a mixed PDF (some pages with a text layer, some scanned) is no longer reported `ready`
while pages are silently missing; coverage derives from each page's own native text; `ready` is
never set with an unaccounted page; `partial` is rendered by the UI as a warning, not as success;
the reason is transient and is not persisted or exposed; upload, dedupe and reprocess paths were
exercised end to end. The limitations recorded then are reproduced in §6 (they are the substance of
the reopened decision).

---

## 3. Decisions already made — **APPROVED** (recorded, not inferred)

All four were made by the owner in session on **2026-10-15**. Their scope is stated exactly; none of
them authorizes anything beyond its own row.

| ID | Gate | Decision | Scope — what it authorizes | What it does **not** authorize |
| --- | --- | --- | --- | --- |
| **D-1** | 4 | `partial` + `ready` redefinition **approved** | The status vocabulary `ready` \| `partial` \| `error` for documents: `ready` only when every page produced usable content (or the format has no pages); `partial` when ≥1 page is usable and ≥1 is not; `error` when no page is usable or a pipeline step raised. Implemented in `backend/documents/routes.py` (`_document_verdict`, `_process_document`). | Any further status value; any change to the `error` reason set; frontend work beyond D-2 |
| **D-2** | 4 (sub-decision, K-06) | Frontend **Option A** approved | The minimum coordinated frontend change inside Phase 1a: `partial` added to the status union in `src/types/index.ts` with an exhaustive mapper in `src/context/WorkspaceContext.tsx` (`unknown` for unrecognised values) — no compatibility window, no deferred UI work | Any other frontend change; any new UI state vocabulary |
| **D-3** | 23 | Reporting is **status-only**; the verdict reason is **transient** | No coverage field, no denominator, no persisted reason; the reason is returned by the processing result and logged for that run only (§7.2.3 / R2-04) | `sourcePageCount` / `pagesMissing` or any other added field; any durable reason |
| **D-4** | 24 (partial) | `MIN_USABLE_CHARS` **home** approved: a module constant in `backend/documents/processing.py`, **no configuration surface**; shipped **value 32** as implemented on 2026-10-15. Accepted `error` reason set = R5 §18's three (`pipeline_exception`, `no_text_layer_ocr_disabled`, `ocr_failed_all_pages`); only the first two are reachable in Phase 1a | **The value is now reopened by D-6.** The home decision stands and is unaffected | Any new reason string; any configuration knob |

**Reachability of the reason set (measured, 2026-10-15):** `pipeline_exception` and
`no_text_layer_ocr_disabled` are the only reasons the shipped code can return; `ocr_failed_all_pages`
is unreachable because OCR is not configured or approved (R5 §19). No reason is claimed that no code
path can produce.

---

## 4. Decisions **REJECTED** or **DEFERRED** (recorded so they are not silently revived)

| Item | Status | Note |
| --- | --- | --- |
| Per-page provenance storage, R5 §8.3 option A (new table) | **OPEN, not selected** (gate 3) | R5 §8.3 specifies the shape; no migration, model or column was added by Phase 1a. Options B and C remain open |
| Coverage reporting fields (gate 23 option "add the fields") | **REJECTED for Phase 1a** by D-3 | Revisit only through gate 23 |
| OCR engine selection (gate 2) | **OPEN — no engine selected** | §7 evaluates candidates; a comparison is explicitly **not** an engine choice |
| OCR implementation, figure extraction, diagram generation | **NOT AUTHORIZED** | R5 §19; unchanged by this record |
| Concurrency / run claim / leases / crash recovery / asset cleanup (gate 27) | **NOT AUTHORIZED, NOT INVESTIGATED** | Gate 27 remains unapproved; no locking, lease, run identifier or cleanup work was performed or designed here |
| Reprocessing algorithm change (preserve-then-replace ordering, R5 §9.2 / §10.5) | **NOT AUTHORIZED** | Owner instruction (D-6): not to be modified without separate authorization |
| Master-plan revision R6 | **REJECTED** | This record is deliberately not a plan revision |

---

## 5. D-6 — Owner instruction of 2026-10-15: the threshold evidence is **reopened**

Verbatim substance of the owner's instruction, kept as the governing constraint for the next step:

1. Use a **content-aware, evidence-based** threshold suitable for a RAG question-answering system.
2. Do **not** treat 32 characters as universally sufficient or necessary for a usable page.
3. Evaluate whether a page contains **meaningful extractable text**, distinguishing: substantive
   text; legitimate sparse pages (chapter titles, section dividers, reference headings); blank pages;
   image-only/scanned pages without a native text layer; pages where extraction fails.
4. A short page must **not** be treated as missing content solely because it falls below a fixed
   character count.
5. **Measure candidate thresholds against representative PDFs and report the trade-offs before
   changing the threshold or the status contract.**
6. Do not classify a document containing successfully extracted legitimate sparse text as an
   extraction failure merely because every page falls below the threshold.
7. Preserve page-level coverage accounting. Do not claim OCR has occurred when it has not.
8. **Do not introduce new status values or reason strings** without approval.
9. Investigate the interaction with reprocessing: an `error` verdict must not silently cause
   previously valid searchable content to be lost.
10. **Report the evidence and the recommended policy before making any code changes.**

**Consequences recorded now:** the shipped value (`32`), the `error` reason and the reprocessing
algorithm are all **unchanged**. §6 reports the measurement and §6.4 the recommended policy, which is
**RECOMMENDED — NOT AUTHORIZED**.

---

## 6. Measured evidence for the threshold decision (executed 2026-10-15)

Method: the project's own functions were used, not a re-implementation — `count_usable_chars` for the
measure, `page.get_text("text")` for the per-page source (exactly what `_extract_pdf_with_coverage`
reads), `PageCoverage` for the facts and `_document_verdict` for the verdict. Only the threshold
*value* was varied (the module constant can hold one value at a time). Documents were real generated
PDFs (`backend/tests/fixtures/pdf_layout.py`); the shipped fixture `backend/tests/fixtures/darwin_proper.pdf`
was measured as-is.

### 6.1 Measured per-page populations (non-whitespace alphanumeric characters)

| Page content | Chars | Real-world meaning |
| --- | --- | --- |
| punctuation only (`. . . -- .`) | **0** | no text layer |
| whitespace only | **0** | no text layer |
| empty string | **0** | no text layer |
| untouched page | **0** | blank page |
| image only (raster, no text) | **0** | scanned page |
| `iv`, `17` | **2** | folio / bare page number — **not content** |
| `Part I` | **5** | part divider — legitimate sparse text |
| `Figure 1` | **7** | figure label — legitimate sparse text |
| `Chapter 1` | **8** | chapter title — legitimate |
| `Appendix A` | **9** | section divider — legitimate |
| `References` | **10** | reference heading — legitimate |
| `Introduction`, `Bibliography` | **12** | heading — legitimate |
| `Lecture 3: Attention` | **17** | title — legitimate |
| one substantive paragraph | **82** | ordinary digital page |
| `darwin_proper.pdf` (3 pages) | **206 / 271 / 206** | ordinary digital document |

**Finding (measured): the in-code claim that the evidence set has "two populations and nothing
between them" is not true.** There is a measured middle population at **5–17 characters** of
legitimate sparse text, and a measured non-content floor at **2** (folio / page number). The
comment above `MIN_USABLE_CHARS` therefore needs correction **when the value is changed**; it is not
corrected by this record (production code is not touched by this task).

### 6.2 Document verdict at each candidate threshold (real verdict function)

| Document (per-page chars) | T=1 | T=4 | T=8 | T=12 | T=16 | T=24 | **T=32 (shipped)** | T=64 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| digital `[82, 82]` | ready | ready | ready | ready | ready | ready | **ready** | ready |
| mixed: substantive + scan `[82, 0]` | partial | partial | partial | partial | partial | partial | **partial** | partial |
| mixed: substantive + blank `[82, 0]` | partial | partial | partial | partial | partial | partial | **partial** | partial |
| title page + body `[8, 82]` | ready | ready | ready | partial | partial | partial | **partial** | partial |
| references page + body `[10, 82]` | ready | ready | ready | partial | partial | partial | **partial** | partial |
| two legitimate short pages `[8, 17]` | ready | ready | ready | partial | partial | **error** | **error** | error |
| folio-only document `[2]` | ready | error | error | error | error | error | **error** | error |
| image-only scan `[0, 0]` | error | error | error | error | error | error | **error** | error |
| blank-only `[0, 0]` | error | error | error | error | error | error | **error** | error |
| punctuation-only `[0]` | error | error | error | error | error | error | **error** | error |
| whitespace-only `[0]` | error | error | error | error | error | error | **error** | error |
| `darwin_proper.pdf` `[206, 271, 206]` | ready | ready | ready | ready | ready | ready | **ready** | ready |

Matching the shipped unit test's expectation (`test_threshold_is_the_owners_gate_24_decision` asserts
`MIN_USABLE_CHARS == 32`) the shipped column is the only one the code can currently produce.

### 6.3 Pipeline and reprocessing — executed, not inferred

Three probes were run through the real pipeline (real extraction, coverage accounting, chunking,
structure and graph persistence; only `embed_texts` stubbed, the project's convention for that
boundary), then the probe file was deleted. Input: a 2-page PDF with `Part I` and `Chapter 1`.

| Probe | Observation (verbatim) |
| --- | --- |
| 1 — shipped value | `MIN_USABLE_CHARS = 32` → `status='error' reason='no_text_layer_ocr_disabled' chunk_count=0 embedding_status='error'` |
| 2 — low presence boundary | `MIN_USABLE_CHARS=4` → `status='ready' reason=None chunk_count=2 embedding_status='ready'` |
| 3 — reprocess after indexing | `before reprocess: status='ready' chunk_count=2 rows=2` → `reprocess HTTP 200 -> status='error' chunkCount=0 rows_after=0` |

`3 passed, exit code 0` (probe file removed afterwards; `git status` clean of it).

**What probe 1 proves:** a document whose pages all carry successfully extracted, legitimate sparse
text is reported as an **extraction failure** (`no_text_layer_ocr_disabled`) although text was
extracted, and **its content is not chunked at all** (`chunk_count=0`) — i.e. pages the user can see
in the PDF are absent from the index.

**What probe 3 proves:** the interaction with reprocessing is a **data-loss path**, measured: a
document that was `ready` with 2 persisted chunk rows, reprocessed through the real
`POST /api/documents/{id}/reprocess`, ends `200` / `error` with `chunkCount=0` and **its
`document_chunks` rows are gone**.

**Attribution (kept explicit, as required):**

* **Phase 1a introduced** the per-page threshold verdict, and therefore the set of documents that can
  reach `error` on coverage grounds while carrying extracted text.
* **Pre-existing behaviour** (not introduced by Phase 1a): the reprocess route deletes old chunks and
  structure rows **before** running the pipeline (`routes.py`, "delete old chunks before
  reprocessing"), and the `error` verdict writes no chunks. Delete-first is not part of Phase 1a and
  has not been modified.
* **The interaction** is what produces the loss: under the shipped value a text-bearing sparse
  document now ends `error`, and the delete-first route has already removed the previous rows — so
  the loss is real for documents reprocessed today.
* **Tested vs inferred:** probes 1–3 are executed. The claim that this is a *sequentially* correct
  but content-destroying path is measured; **no claim is made about concurrent runs** (gate 27).
  Recovering this ordering (write → commit → sweep, R5 §9.2/§10.5) is **not authorized** and not done.

### 6.4 Recommended policy — **RECOMMENDED, NOT AUTHORIZED**

**Option B′ — content-aware presence accounting with a measured presence floor.**

* **Rule:** a page is *unaccounted* when its own native text contains fewer than **4** non-whitespace
  alphanumeric characters, or its extraction raised. Everything above that is accounted for, and no
  *quality* claim is made about it. Page-level coverage accounting is unchanged (R5 §7.2.1); the
  status vocabulary is unchanged; no new reason string is introduced.
* **Why 4 — it is measured, not invented:** the largest *no-content* page observed carries **2**
  characters (folio / bare page number); the smallest *legitimate sparse* page observed carries **5**
  (`Part I`). Any value in **3–4** sits inside that measured gap; the choice *within* that interval
  is not discriminated by the evidence and is presented for the owner to fix (4 is proposed: it is
  above the artefact population and below the shortest observed legitimate text).
* **What it fixes (measured):** the false `partial` for `[8, 82]` and `[10, 82]`; the false `error`
  for all-sparse legitimate documents (`[8, 17]` → `ready`, 2 chunks, embedding ready — probe 2);
  and with them the reprocess-induced loss of probe 3 (the document no longer reaches `error`).
* **What it keeps (measured):** blank, image-only, punctuation-only and whitespace-only pages still
  yield `error` when no page has text; mixed documents stay `partial`; `ready` still requires every
  page to be accounted for. The `error` reason becomes literally accurate for every case it is
  returned for, because a document only reaches `error` when no page carried extractable text above
  the floor.
* **Residual inaccuracy (stated, not hidden):** for a document whose pages carry **only** folios
  (`[2]`), text *was* extracted and the reason returned would still be
  `no_text_layer_ocr_disabled`. Making the reason exactly true there would require a new reason
  string (e.g. a "text extracted but below the presence floor" reason) — **new vocabulary, therefore
  an owner decision, and not proposed as part of B′**.
* **What it does not claim:** the floor is a *presence* guard, not a quality measure. A junk text
  layer carries many characters and remains undetected by any character count (this is Phase 1b's
  OCR-quality work, unchanged).

Alternatives, with measured consequences:

| Option | Measured result | Verdict |
| --- | --- | --- |
| **A — keep 32** | legitimate sparse pages misreported; all-sparse legitimate documents `error` with 0 chunks; reprocess destroys indexed content (probe 3) | Not recommended |
| **B′(1) — presence only, T=1** | same as B′ for every measured case **except** the folio-only document, which becomes `ready` while carrying 2 characters of content | Weaker than B′; falls to B′ if the owner prefers "any text at all" |
| **B′(8)** | identical to B′(4) on all measured documents, but draws a boundary that excludes the measured `Part I` (5) and `Figure 1` (7) pages — no measured case requires it | Not recommended |
| **B′(16)/B′(24)** | identical to 32 on the measured corpus for the legitimate-sparse documents (`[8, 17]` → still `error` at 24) | Not recommended |
| **C — separate text presence from page usability** | new reason and/or field distinguishing "text present but below the usability bar"; needs a contract change (status/reason vocabulary), a frontend and test change, a plan amendment and gates 3/23/24 | Correct long-term home for *quality* signals (Phase 1b); **requires owner approval of the new vocabulary** and is deliberately not proposed as the fix for this defect |

**Required code/contract changes if B′ is approved:** one numeric value and the rule wording in
`backend/documents/processing.py` (constant + docstring correction), the pinned-value assertion in
`backend/tests/unit/documents/test_phase1a_page_completeness.py`, and the gate-24 comment in
`backend/documents/routes.py` (which quotes the value's rationale). **No** API, schema, migration,
frontend or status-vocabulary change. Ownership: `documents/**` → BACKEND_AGENT; the pinned-value
test → TEST_AGENT; verification → VERIFIER. No new gate is introduced; this is the gate-24 value
decision itself.

---

## 7. OCR readiness — documentation-level evaluation only (gate 2 stays OPEN)

**Not done, by instruction:** no package was installed, no model downloaded, no virtual environment
changed, no deployment file touched, no document content sent anywhere, and nothing was benchmarked
by running an OCR engine. **OCR therefore remains NOT IMPLEMENTED** and no document may be described
as OCR-processed.

### 7.1 Measured environment facts (this machine, this venv)

| Fact | Value |
| --- | --- |
| `onnxruntime` | **1.30.0 — installed** |
| `torch` / `torchvision` | **2.13.0 / 0.28.0 — installed** (CPU) |
| `pymupdf` | **1.28.2 — installed** (the project's pinned raster/vector renderer) |
| `pillow` / `numpy` | 12.3.0 / 2.4.6 — installed |
| `pytesseract`, `tesserocr`, `easyocr`, `paddleocr`, `rapidocr*`, `cv2` (OpenCV) | **not installed** |
| `tesseract` on `PATH` | **no** |
| OCR code in `documents/` | none (strings `ocr`, `get_pixmap`, `get_images` absent — audit, re-checked) |

### 7.2 Candidate comparison

Evidence classes: **(measured)** this session, **(documentation)** from an authoritative source,
**(inferred)** from architecture, **(unknown)** not established.

| Dimension | Tesseract 5 (system binary) | RapidOCR (ONNX Runtime) | EasyOCR (PyTorch) |
| --- | --- | --- | --- |
| Licence | Apache-2.0 **(documentation)** | Apache-2.0 code **and** models derived from upstream PaddleOCR models, with sources/hashes documented in the project's model-licence file **(documentation)** | Not verified in this pass **(unknown)** — the repository README does not state it |
| Runtime requirement | a **system executable** installed outside pip **(documentation)**; `pytesseract` is a thin wrapper **(documentation)** | `onnxruntime` — **already installed (measured)** + the `rapidocr` wrapper package **(documentation)** | `torch` + `torchvision` — **already installed (measured)**; README requires them to be installed *first* on Windows **(documentation)** |
| Additional Python dependencies | `pytesseract` | wrapper + image/geometry helpers (OpenCV and, typically, pyclipper/shapely) **(documentation/inferred; exact set must be measured)** | `easyocr` + OpenCV, scikit-image, python-bidi, Shapely, pyclipper **(documentation)** |
| Offline after provisioning | yes, if `tessdata` files are present locally **(documentation)** | explicitly designed for offline deployment; models bundled/hosted with documented provenance **(documentation)** | **model weights are downloaded automatically on first use** unless fetched manually into `~/.EasyOCR/model` **(documentation)** |
| PyMuPDF 1.28.2 integration | PyMuPDF's own OCR recipe is built on Tesseract, which it documents as a separately installed application; it also documents OCR as roughly **a thousand times slower** than text extraction, and describes the trigger as a page fully covered by an image / carrying no text **(documentation; not executed on this version)** | no PyMuPDF integration claim; would be a render-then-call adapter (PyMuPDF renders the pixmap, the engine returns text) **(inferred)** | same adapter shape **(inferred)** |
| Rasterisation dependency | none beyond PyMuPDF (`get_pixmap`) — no poppler/`pdf2image` needed **(inferred from the installed renderer)** | same | same |
| CPU-only | CPU-only build exists **(documentation)** | official CPU (ONNX Runtime) container target **(documentation)** | `gpu=False` CPU mode documented **(documentation)** |
| Per-page latency | unknown for this machine; the only quantitative statement available is the ~1000× text-extraction ratio **(documentation)** | **unknown — not measured** | **unknown — not measured** |
| Peak memory | **unknown** | **unknown** | expected higher (detector + ResNet/LSTM recognition on torch) **(inferred)** |
| Rotation / low-quality scans | rotation must be handled (OSD or our own pre-pass); no vector-graphics recognition **(documentation/inferred)** | detection + angle classification typical of the PaddleOCR family **(inferred)** | CRAFT detector, good on dense text **(inferred)** |
| Table/layout-heavy pages | no layout understanding; cell text recovered as text only **(inferred)** | text recovered without table structure **(inferred)** | same **(inferred)** |
| Windows | official installer available **(documentation)** | wheels expected for CPython 3.11 on Windows — **must be verified before selection** **(unknown)** | Windows supported per README; torch CPU wheels already present here **(documentation; not executed)** |
| Container/deployment | adds a **system artifact** to the image → a deployment-file change → gate 22 (whose ownership is still unassigned, N-002) | pure-pip addition, no system binary **(inferred)** | pure-pip addition **(inferred)** |
| Supply chain | distribution package + language data files | package + ONNX model files with documented hashes | package + **weights fetched at runtime by default**, which also collides with the offline posture unless pre-provisioned |
| Provenance to record | engine + version + language data version | engine + version + model set | engine + version + model files |
| Interaction with `MIN_USABLE_CHARS` | measured analogue: a scanned page whose OCR returns a short header (e.g. `3 Methodology` ≈ 12 chars; measured `Lecture 3: Attention` = **17**) is **below the shipped 32** and would be counted *unaccounted* even though OCR succeeded — encoding the same defect into 1b | same | same |

### 7.3 Recommendation (a recommendation, **not** an engine selection)

**RapidOCR on the already-installed ONNX Runtime** is the candidate this record recommends for the
first *measured* evaluation, because: the runtime it needs is already installed and has no torch
dependency; its code and models are Apache-2.0 with documented model provenance/hashes; it is
designed for offline use; and it adds **no system binary**, which avoids the deployment-file change
that gate 22 (unowned, N-002) would otherwise force. **Tesseract** is recommended as the comparison
baseline *only* (its ecosystem maturity and PyMuPDF's native path are real advantages, but a system
binary is an operational and deployment cost here). **EasyOCR** is the least attractive of the three
in this environment: runtime weight downloads by default and the largest dependency set.
**This selects nothing.** Gate 2 requires *measured* coverage, CER, latency, memory, licence,
offline capability and Windows/container parity before any engine can be chosen, and none of those
was measured here.

**Critical dependency:** the threshold value should be decided **before** Phase 1b measures OCR
quality. Otherwise each scanned page that OCRs into a short header will be scored as unaccounted
against the same misleading number — the defect §6 measures, carried into OCR.

### 7.4 Reproducible benchmark protocol (for a separately authorized, separately provisioned run)

Not executed here; each row names the exact evidence that is missing.

1. **Environment.** A **separate scratch virtual environment** created by an operator (never
   `backend/venv`, which agents may not write), plus the operator's approval to download model files.
   Record: Python version, exact package versions, model file names + hashes, and whether a network
   connection existed during the run.
2. **Corpus (reproducible without external data).** Generate the scanned pages by rendering known
   text to a pixmap with the already-installed PyMuPDF and inserting it as an **image-only** page, so
   the ground-truth text is known by construction (this is a *synthetic* scan — real skew, noise,
   JPEG artefacts and multi-generation copies must be added deliberately at fixed seeds, and the
   limitation stated). Include: digital pages, mixed digital/scanned documents, rotated scans
   (0/90/180/270), low-quality scans, table-heavy pages, and the existing
   `backend/tests/fixtures/darwin_proper.pdf` as the digital control.
3. **Coverage.** Pages accounted before vs after OCR, per document, using the shipped coverage
   accounting and the §6.4 verdict function; the count of newly accounted pages and the new verdict
   for each fixture.
4. **Quality.** Character/word error rate against the known ground truth of the rasterised pages,
   reported per page class (clean / rotated / noisy / table-heavy), never as a single blended number.
5. **Latency and throughput.** Wall-clock per page (p50/p95) and pages/second, CPU-only, single
   process, with the cold-start model load reported separately.
6. **Memory.** Peak RSS for the process, and the model's footprint on disk.
7. **CPU/GPU.** CPU-only path exercised; GPU acceleration noted only as optional and not claimed.
8. **Offline behaviour.** The whole protocol re-run with network access disabled, to prove
   provisioning suffices.
9. **Windows/container parity.** Same corpus and metrics on Windows and in the container image;
   parity reported as measured or as untested.
10. **Failure handling.** Per-page timeout and resource limits, behaviour on a corrupt/oversized
    page, and confirmation that a failure produces a coverage outcome (unaccounted page) rather than
    a fabricated success.
11. **Security and licensing.** Package and model licences, model provenance/hashes, the permission
    granted by each licence, and the exact files that would enter the image. No document content
    leaves the deployment.
12. **Provenance and interaction.** Which per-page fields the engine can honestly supply (method,
    engine, version, languages, confidence, char count, rotation, failure reason) mapped onto R5
    §8.3 option A, and the resulting coverage under each candidate threshold — the measurement that
    ties gate 2 to gate 24.
13. **Harness location and owner.** A research measurement, not a production test:
    `backend/evaluation/experiments/run_ocr_engine_benchmark.py` (EVALUATION_AGENT). It must not
    modify production code and must not import from `backend/tests/`.
14. **Prerequisites that do not exist yet:** operator provisioning of a scratch environment; a
    scanned/rotated/noisy fixture set (generated, §2); authorization to run the benchmark at all
    (gate 2's evidence step); and a decision on the threshold (§6.4) for the interaction measurement.

**Smallest safe next experiment:** one engine (**RapidOCR/ONNX**) on **one** bounded corpus
(the generated rasterised pages + `darwin_proper.pdf`), CPU-only, single process, network disabled,
measuring **pages accounted before/after**, **CER vs known ground truth**, **p50/p95 per page** and
**peak RSS** — a half-day, read-only-with-respect-to-production measurement that either qualifies or
disqualifies the candidate before any wider comparison.

---

## 8. Gate status after this task (R5 identifiers preserved)

| Gate | Status now | Note |
| --- | --- | --- |
| 1 — Phase 1 scope | **UNVERIFIED / open** | Phase 1a is implemented and independently verified *with limitations*; no repository artifact records an owner approval of the Phase 1a scope itself |
| 2 — OCR engine + install + provisioning | **OPEN — blocked** | §7 is documentation-level only; no engine selected or installed; measured evidence outstanding (§7.4) |
| 3 — Provenance storage (A/B/C) | **OPEN** | Nothing stored; §8.3 option A not selected |
| 4 — `partial` + `ready` redefinition; frontend sub-decision | **APPROVED 2026-10-15** | D-1, D-2 |
| 13 — Deployment change for a new artifact | **OPEN** | No deployment file changed; no new artifact |
| 16 — Data-egress posture | **OPEN (posture unchanged: local-only)** | No egress added; no cloud OCR or external service used or proposed |
| 17 — Historical audit + reprocessing policy | **OPEN** | No audit run; no bulk reprocessing |
| 21 — Metric thresholds (incl. OCR accuracy) | **OPEN** | No threshold value invented; §7.4 defines the measurements that would produce one |
| 22 — Deployment-file ownership (N-002) | **OPEN** | Relevant only if a system-binary engine (Tesseract) were chosen — one reason §7.3 prefers a pip-only engine |
| 23 — Coverage reporting fields | **APPROVED (status-only) 2026-10-15** | D-3 |
| 24 — Usable-content minimum + reason taxonomy + home | **PARTIALLY DECIDED — value reopened** | Home and reason set: D-4. Value: D-6 reopened; §6.4 recommends, **nothing changed** |
| 25 / 26 — figure provenance / asset identity | **OPEN** | Untouched |
| 27 — Per-document run claim, run identity, cleanup exclusion | **OPEN — not approved, not investigated** | No lock, lease, run id, crash recovery or cleanup work was performed |

No gate was approved by recommendation, inference or silence. No gate identifier was renumbered.

---

## 9. Files changed by this task and verification of the change

| File | Change | Nature |
| --- | --- | --- |
| `backend/architecture/DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md` | new (this record) | documentation only |
| `CONTEXT.md` | §5 only: the status contract (`ready`/`partial`/`error`) with a pointer to this record, and the scanned-document wording in the NOT-IMPLEMENTED bullet | documentation only |
| `ARCHITECTURE.md` | status vocabulary + verdict source recorded under §05 Document Processing | documentation only |

**Not changed:** every file under `backend/documents/**`, `backend/tests/**`, `src/**`,
`backend/migrations/**`, `backend/requirements.txt`, `backend/config.py`, deployment files, model
weights, all R5 plan text and every other record in `backend/architecture/**`. No dependency was
added, no environment altered, no schema or migration touched, nothing staged, committed, pushed,
reset or reverted.

**Verification of this record:** the changed-file list was confirmed by diff inspection; the
recorded decisions were checked one by one against the owner's statements in the session that
produced them (D-1…D-6, no approval inferred from silence, no date backdated); the recorded gate
statuses were checked against R5 §18 (identifiers unchanged, no gate marked approved); the measured
numbers in §6 are copied from executed output (§6.1–§6.3), not from a prior summary; and the OCR
table in §7.2 labels each cell as measured, documentation-derived, inferred or unknown. No test
suite was re-run because no production or test file changed.

---

## 10. What remains prohibited until a further decision

* Changing `MIN_USABLE_CHARS`, the verdict rule, or the `error` reason set (§6.4 is a recommendation).
* Introducing a new status value or reason string.
* Modifying the reprocessing algorithm (delete-first ordering, R5 §9.2 / §10.5).
* Installing an OCR engine or any dependency; downloading model weights; altering the virtual
  environment or deployment files.
* Starting Phase 1b, figure extraction, diagram work, or any Phase 2+ item.
* Implementing any part of gate 27 (locks, leases, run identifiers, crash recovery, asset cleanup).
* Amending R5 or creating another master-plan revision.

**Next decision required from the owner (one item, two parts):**
**(a)** the gate-24 value — Option B′ (§6.4, a measured presence floor of 4, or 1 for "any text at
all") / keep 32 / Option C with new vocabulary; and
**(b)** whether to authorize the §7.4 benchmark step for gate 2 in a separately provisioned scratch
environment.

---

# Addendum 1 — 2026-10-15: Decision A implemented, isolated OCR benchmark executed

## 11. Authorization recorded in this addendum

**D-7 — Gate 24 value APPROVED: `MIN_USABLE_CHARS = 4`** (owner authorization, 2026-10-15).
Scope, exactly as granted: the page-usability threshold plus its directly related tests and
documentation. The owner's stated basis: the reported evidence table (which §6/§12 reproduce) and
the measured separation between the largest no-content example (2 characters) and the shortest
legitimate sparse example (5).

Explicitly **not** authorized by D-7 (owner's words, kept verbatim-in-substance): introducing new
document statuses or reason strings; changing API contracts or database schemas; implementing OCR;
changing the reprocessing algorithm; implementing concurrency, leases, run identifiers or asset
cleanup; modifying deployment configuration or model weights.

**D-8 — Isolated OCR benchmark APPROVED** (owner authorization, 2026-10-15) with these restrictions:
do not install OCR dependencies into DocuMind's existing virtual environment; do not download models
into project or user-data directories; do not alter production requirements, lockfiles, deployment
files or model configuration; do not modify schemas or migrations; do not upload documents to
external OCR services; do not use private user documents for external testing; do not commit or push;
preserve all existing tracked and untracked changes. A benchmark result **does not** select an engine:
selection, integration, provenance storage, deployment changes and implementation remain behind their
existing gates.

**Standing exclusion reconfirmed:** the reprocessing data-loss risk is **not** to be fixed in this
task; it is to be inspected, confirmed, recorded (§13) and a narrowly scoped preservation strategy
recommended. Gate 27 and all concurrency/asset-lifecycle work remain separate.

---

## 12. Decision A — implementation and focused verification

### 12.1 Files changed (implementation)

| File | Change | Owner |
| --- | --- | --- |
| `backend/documents/processing.py` | `MIN_USABLE_CHARS`: **32 → 4**; the misleading rationale replaced with the measured three-region evidence (§6.1) | BACKEND_AGENT |
| `backend/tests/unit/documents/test_phase1a_page_completeness.py` | pinned assertion **32 → 4**; module docstring updated; **10 new focused tests** (two new classes) | TEST_AGENT |
| this record; `CONTEXT.md`; `ARCHITECTURE.md` | decision + status-contract consistency | COORDINATOR |

No other production, test, config, migration, dependency, deployment or model file was touched. The
verdict function (`_document_verdict`), the status vocabulary (`ready` / `partial` / `error`), the
transient reason contract (gate 23) and the `error` reason set are unchanged — the approved change is
one value plus its rationale.

### 12.2 Before/after behaviour (measured, real extraction and real verdict function)

| Document (chars/page) | Before (32) | After (4) |
| --- | --- | --- |
| substantive digital pages `[82, 82]` | ready | ready (unchanged) |
| short title + substantive `[8, 82]` | partial | **ready** |
| references + substantive `[10, 82]` | partial | **ready** |
| two legitimate short pages `[8, 17]` | error + 0 chunks | **ready + chunks** |
| mixed digital + scanned `[82, 0]` | partial | partial (unchanged) |
| mixed digital + blank `[82, 0]` | partial | partial (unchanged) |
| blank-only / image-only / punctuation-only / whitespace-only `[0…]` | error / `no_text_layer_ocr_disabled` | error / same reason (unchanged) |
| folio-only `[2]` (`"17"`, `"iv"`) | error / same reason | error / same reason (unchanged) |
| `darwin_proper.pdf` `[206, 271, 206]` | ready | ready (unchanged) |

**Reason accuracy (requirement 7 of the authorization):** the reason returned is
`no_text_layer_ocr_disabled`, produced only when **no** page reached the presence floor. For every
unaccounted case in the measured corpus that is literally true (a scanned, blank, whitespace-only or
punctuation-only page carries zero alphanumeric characters). The one residual imprecision is a
**folio-only** document, which did extract two characters; making the reason exactly true there would
require a new reason string, which D-7 forbids. Recorded, not hidden.

### 12.3 Focused verification — commands and actual results

| Command (cwd `backend/`) | Result |
| --- | --- |
| `./venv/Scripts/python.exe -m pytest -q tests/unit/documents/test_phase1a_page_completeness.py` | **31 passed**, 1 warning, **exit 0** (was 21 before the 10 new tests) |
| same module, real upload-tree file count before/after | 1278 → 1278 files: the new tests touch **no** real upload artifact |
| `./venv/Scripts/python.exe -m pytest -q tests/unit tests/integration/documents` | **1485 passed, 23 skipped, 1 error, exit 1** (see below) |
| `./venv/Scripts/python.exe -m pytest -q "tests/integration/documents/test_table_row_persistence.py::TestIngestionServiceWiring::test_process_document_persists_row_evidence"` | **1 passed, exit 0** |

**The single error — pre-existing, explained, not caused by this change.** It is raised at **teardown**
by the session-scoped tripwire in `tests/unit/scripts/test_cleanup_orphan_uploads.py:168`:

```
AssertionError: tests modified the real upload tree: 1265 -> 1278 file(s)
```

It is a **test-isolation defect outside this task's scope**: some other test in the combined run
writes into the real upload tree when the unit and integration suites share one process. Evidence that
it is not this change: (a) the same single error was reported in this session's **pre-change**
verification run; (b) the test named in the report passes in isolation; (c) the newly added tests
leave the upload tree at 1278 before and after (row 2 above). No test, fixture or production file was
changed to make it pass.

### 12.4 Limitations of the evidence behind the approved value

* The corpus is **generated pages plus one shipped digital fixture** (`darwin_proper.pdf`, 206–271
  characters/page). It is not a sample of real-world documents.
* The measured gap is `2` (folio) versus `5` (`Part I`); **any value in 3–4 is equally supported**, and
  the choice of 4 within that interval is an owner decision, not a measurement outcome.
* A generated page's text layer is regular; a real scan's junk text layer (many characters, no
  content) is **not** detected by any character count — unchanged, and Phase 1b's problem.
* Sparse-page classification is measured in a **Latin-script, ASCII** corpus only.

---

## 13. Reprocessing data-loss risk — measured, still open, **not** fixed

### 13.1 What the code does today

The reprocess route deletes the document's chunks **and** its structure rows **before** running the
pipeline, in the same transaction that is committed afterwards (`backend/documents/routes.py`, "delete
old chunks before reprocessing"). The pipeline writes no chunks when the run ends `error` before
chunking, and writes chunks **without vectors** when it fails after chunking. Nothing preserves the
previously indexed version.

### 13.2 Measured (probe run 2026-10-15, then deleted; 2 passed, exit 0)

Real ASGI endpoints and the real pipeline; only `embed_texts` is stubbed (real 384-dim vectors for the
"indexed" state, then raised for the failure case).

| Case | Before | After reprocessing |
| --- | --- | --- |
| **A** sparse document (`Part I`, `Chapter 1`) | `ready`, 2 chunk rows, 2 embedded | HTTP 200, `ready`, chunkCount 2, 2 chunk rows, 2 embedded — **content survives** |
| **B** indexed document whose new run fails at the embedding step | `ready`, 2 chunk rows, 2 embedded, ids `0175061b…`, `9e042a8b…` | HTTP 200, `status='error'`, chunkCount **2**, 2 chunk rows, **0 embedded**, ids `78e908ba…`, `9038048a…` (disjoint) |

**Correction of §6.3 in this record.** §6.3 reported the pre-chunking shape (`chunkCount=0`, rows
gone) — that measurement stands for a coverage/`pipeline_exception` failure *before* chunking. Case B
shows the **post-chunking** shape, which that measurement did not cover: the previously indexed rows
are deleted and replaced by rows that carry **no vectors**, so the document is `error` while
`chunkCount` still reports 2. The honest signal is `embeddingStatus='error'`; `chunkCount` counts
chunks, not *searchable* chunks.

### 13.3 Status of the risk

* **Closed for the threshold cause:** case A is the case that used to end `error` and lose content;
  with the approved value it stays `ready` and survives a reprocess (measured).
* **Still open for every other failure cause** (embedding, structure or graph failure, transient I/O):
  the owner's desired invariant — *a failed reprocessing attempt must not silently destroy the last
  successfully indexed version* — is **still violated** (case B, measured).
* **Tested vs inferred:** A and B are executed. The claim that the delete happens before the rebuild is
  read from the route source and confirmed by the disjoint row ids; no claim is made about concurrent
  runs (gate 27).
* **Not changed:** no ordering fix, no preserve-then-replace, no claim, no lock, no rollback logic. The
algorithm is exactly as it was, because D-7/D-8 do not authorize a change and the owner required a
separate authorization.

### 13.4 Recommended preservation strategy (proposal only — **not authorized**)

1. **Reorder, smallest step:** make the replacement ordering write → commit → sweep (R5 §9.2/§10.5)
   so the pre-existing derived rows are superseded *by* the committed replacement rather than deleted
   before it exists. This is a transaction-shape change and needs explicit approval.
2. **Do not commit a degraded state:** when the run ends `error`, either keep the previous committed
   rows (do not let the failed run's delete reach the database) or record that the derived data is
   stale instead of overwriting it — never commit "error with no searchable content" over a
   previously `ready` document.
3. **Reporting honesty for the interim:** a document that is `error` after a run that wrote unembedded
   chunks should not report `chunkCount` as if those chunks were searchable. Which field carries that
   distinction is a **contract decision** (gate 23 territory), so it is proposed, not implemented.
4. **Scope discipline:** none of this is gate 27. Concurrency, leases, run identifiers, crash recovery
   and asset cleanup stay separate and unapproved.

---

## 14. OCR benchmark — isolated environment, measured results

### 14.1 Isolation, provisioning, network, cleanup (as proposed, then as executed)

| Item | Detail |
| --- | --- |
| Location | `%LOCALAPPDATA%\Temp\documind-ocr-bench\` — disposable, **outside the repository**; `venv\`, `corpus\`, `results\`, `models\` |
| Interpreter | its own virtual environment from `py -3.11` (Python 3.11.0); DocuMind's `backend/venv` was never used or modified |
| Network | PyPI reachable during provisioning only (`pypi.org/simple/` HTTP 200); model weights were **not** downloaded — RapidOCR 3.10.0 ships its three ONNX models inside the wheel |
| Model location | `…\documind-ocr-bench\venv\Lib\site-packages\rapidocr\models\` — inside the bench root; nothing was written to `%USERPROFILE%` (`~/.EasyOCR`) or to any project directory |
| Repository impact | none: no requirements, lockfile, deployment file, migration, model config or source file was touched; nothing staged, committed or pushed |
| Cleanup | delete the whole bench root (it holds the venv, corpus, models and result JSON); only the numbers below were copied into this record |
| Corpus | generated with PyMuPDF inside the bench env: digital control, clean scans (1 and 3 pages), rotated scans (90/180/270), a blurred/noisy/JPEG-45 low-quality variant, a ruled table page, a layout-heavy page (paragraph + table), and a mixed digital+scanned document — **ground truth known by construction** |

Provisioned versions (measured): `rapidocr 3.10.0`, `onnxruntime 1.31.0`, `opencv-python-headless 5.0.0.93`,
`pymupdf 1.28.2`, `numpy 2.4.6`, `pillow 12.3.0`, `shapely 2.2.0`, `pyclipper 1.4.0`, `omegaconf 2.4.0`,
`psutil` (bench-only, for RSS sampling). Hardware: this Windows workstation, CPU only (no GPU used).

### 14.2 Measured — coverage (21 pages, 150 dpi and 300 dpi agrees)

| Measure | Value |
| --- | --- |
| Pages usable from **native** text alone | **2** (the two digital pages) |
| Pages usable with OCR added | **21 of 21** |
| Pages **recovered by OCR** | **19** |

### 14.3 Measured — recognition quality (per page, order-sensitive CER / word error rate / word recall)

| Fixture | 150 dpi | 300 dpi |
| --- | --- | --- |
| clean scans, 3 pages | CER 0.203 / 0.241 / 0.203 | **CER 0.000 / 0.000 / 0.000**, WER 0.0, recall 1.0, conf 0.993 / 0.995 / 0.996 |
| single clean scan page | CER 0.223 | CER 0.210 (the one-line loss, §14.4) |
| blurred + noisy + JPEG-45 "low quality" scan | CER 0.000 ×3 | **CER 0.000 ×3**, conf 0.986 / 0.993 / 0.994 |
| ruled table page | CER 0.000 | **CER 0.000**, conf 0.998 |
| layout-heavy page (paragraph + table) | CER 0.212 | **CER 0.000**, conf 0.999 |
| rotated 90° | — | CER 0.645 / 0.565 / 0.641, recall 0.431 / 0.553 / 0.431 |
| rotated 180° | — | CER 0.711 / 0.730 / 0.711, recall 0.412 / 0.421 / 0.412 |
| rotated 270° | — | CER 0.674 / 0.523 / 0.674, recall 0.628 / **1.000** / 0.628, WER up to 0.941 |
| clean-scan aggregate (mean) | CER 0.222, WER 0.279 | **CER 0.070, WER 0.088** |

### 14.4 Measured — the resolution finding (the benchmark's most important result)

One page of the corpus lost **exactly one line of four** at whole-page input (`and answered from.
Retrieval fuses a semantic path over pgvector with a structural` → garbage) while its three
neighbouring lines scored CER 0.000. Isolating it:

| Input | Page CER |
| --- | --- |
| whole page, 150 dpi | 0.2234 |
| whole page, 300 dpi | 0.2096 |
| whole page, 400 dpi | 0.2062 |
| whole page, **600 dpi** | **0.0000** |
| **crop of the failing line alone**, 300 dpi | **0.0000** |
| same crop upscaled 3× | **0.0000** |

The line is fully recoverable; the loss is a **detector input-scale artefact** of whole-page inference at
150–400 dpi, not a recognition ceiling and not visible in the confidence score (that page's mean
confidence was 0.90). Practical consequence for Phase 1b: the input scale and the detector's internal
resize must be pinned and measured on *whole pages*, and **mild blur/JPEG degradation was not the
limiting factor** (the degraded variant scored CER 0.000 at both resolutions).

### 14.5 Measured — latency, memory, provisioning (CPU only)

| Measure | 150 dpi | 300 dpi |
| --- | --- | --- |
| Pages OCR'd | 21 | 21 |
| Latency p50 | 2.43 s | **2.58 s** |
| Latency p95 / max | 2.64 s / 2.89 s | 2.90 s / 3.00 s |
| Throughput (median) | 0.41 pages/s | **0.39 pages/s** |
| Peak RSS during inference | 806 MB | **1192 MB** |
| RSS before / after engine construction | 85.3 MB / 85.5 MB (models load lazily on first inference) | same |
| Engine construction | 0.013 s | — |
| Model files (bundled) | det 9.93 MB + rec 21.23 MB + cls 0.59 MB = **31.75 MB** | — |
| Offline after provisioning | **verified**: 600-dpi page OCR'd with `HTTP_PROXY`/`HTTPS_PROXY` pointed at `127.0.0.1:9` → alnum 239, **CER 0.0000**, no download attempted (log: "File exists and is valid") | — |

* **Cost implication:** ~2.5–3 s per page, ≈0.4 pages/s, ~0.8–1.2 GB peak RSS on this machine. A
  100-page scanned document is therefore roughly **4–5 minutes** of CPU inference for one ingestion,
  and concurrent ingestions would multiply memory.
* **Hardware/runtime:** Windows, CPU-only (`onnxruntime` CPU EP). GPU acceleration was **not** tested
  and is not claimed.

### 14.6 Candidate status

| Candidate | Status |
| --- | --- |
| **RapidOCR + ONNX Runtime** | **measured** (above). Bundled Apache-2.0 models, no system binary, fully offline after `pip install`, `opencv-python-headless` added |
| **Tesseract baseline** | **BLOCKED — cannot be provisioned safely here.** No `tesseract` binary on the machine (`Program Files`, `Program Files (x86)` and `PATH` all absent) and no package manager (`choco`, `winget`, `scoop` all absent). Installing it would mean a **system-wide installer**, which is neither an isolated environment nor a change DocuMind's agents may make. Reported rather than worked around |
| **EasyOCR** | torch 2.14.1 provisioned in the bench env; outcome appended in Addendum 2. Its weights are fetched at first use, so it must be given a `model_storage_directory` inside the bench root (never `~/.EasyOCR`) |

### 14.7 Recommendation (still a recommendation — **no engine selected**)

Measured, RapidOCR on the already-present ONNX Runtime is a **credible** candidate for Phase 1b on
digital-quality scans: after provisioning, a 300-dpi page is read at CER 0.000 including a blurred,
noisy JPEG variant, a ruled table and a layout-heavy page; it needs no system binary and no runtime
network. It is **not** usable as-is for rotated scans (CER 0.52–0.73, word recall 0.41–1.00) and its
~2.6 s/page, ~1.2 GB peak RSS must be reconciled with the ingestion budget. **Gate 2's evidence rule
is now partly satisfied for one candidate** — coverage, quality, latency, memory, licence, provisioning
and offline capability were measured here; Windows/container parity and a Tesseract baseline remain
outstanding. **Engine selection, integration, provenance storage (gate 3), deployment changes (gates
13/22) and implementation stay blocked.**

### 14.8 Evidence classes for §14

* **Measured:** every number in §14.1–14.5 (this machine, this bench env, this corpus).
* **Documentation-derived:** the bundled-model/Apache-2.0/provenance claims in §7.2 (engine docs and
  the wheel's own model files), and the EasyOCR first-use download behaviour.
* **Inferred:** memory/latency scaling to larger documents and to concurrency; the container-parity
  expectation.
* **Unknown / not measured:** Windows-vs-container parity; GPU behaviour; Tesseract on this hardware;
  quality on real (non-generated) scans; accuracy on non-Latin scripts; the effect of the detector
  resize setting being tuned instead of the DPI being raised.

---

## 15. Gate status after Addendum 1

| Gate | Status now | Change from §8 |
| --- | --- | --- |
| 1 — Phase 1 scope | UNVERIFIED / open | unchanged |
| 2 — OCR engine + install + provisioning | **OPEN, partially evidenced** | one candidate measured (§14); no engine selected; Tesseract blocked |
| 3 — Provenance storage (A/B/C) | OPEN | unchanged |
| 4 — `partial` + `ready` redefinition; frontend sub-decision | APPROVED 2026-10-15 | unchanged |
| 13 / 22 — deployment change, deployment-file ownership | OPEN | unchanged; a pip-only engine would avoid 22 |
| 16 — Data-egress posture | OPEN (local-only preserved) | no document left the machine; no external OCR service used |
| 17 — Historical audit + reprocessing policy | OPEN | unchanged |
| 21 — Metric thresholds (incl. OCR accuracy) | OPEN | measurements now exist to propose against (§14.3) |
| 23 — Coverage reporting fields | APPROVED (status-only) | unchanged |
| **24 — Usable-content minimum + reason taxonomy + home** | **APPROVED: value 4, home = module constant** | changed from "value reopened" |
| 25 / 26 — figure provenance / asset identity | OPEN | unchanged |
| 27 — run claim, run identity, cleanup exclusion | **OPEN — not approved, not investigated** | unchanged |

## 16. Integrity of Addendum 1

* Implementation diff inspected: `processing.py` (the constant and its comment) and the Phase 1a test
  module only; `git diff --cached` empty; nothing committed or pushed; all pre-existing tracked and
  untracked changes preserved.
* Both temporary probes (`tmp_probe_reprocess_risk.py`, and the earlier threshold probe) were deleted,
  including their bytecode; `find -name 'tmp_probe*'` → 0 files.
* The benchmark ran entirely outside the repository; the only artifact copied back is the text of
  §14. No result in §14 is estimated, and the one anomaly found was diagnosed to its cause rather than
  reported as a quality number.
* No browser, live-server, PostgreSQL, integration or E2E verification is claimed for this addendum.
  The end-to-end claims in §12 are SQLite-backed test runs plus direct pipeline execution.

---

# Addendum 2 — 2026-10-15: EasyOCR measured in the same isolated environment

## 17. EasyOCR 1.7.2 (PyTorch, CPU) — measured, same corpus, same 300 dpi pages

Provisioned in the same bench venv (`easyocr 1.7.2`, `torch 2.14.1`, `torchvision 0.29.1`, plus
`scipy`, `scikit-image`, `python-bidi`). Weights were **downloaded on first use** — the engine prints
"Downloading detection model / recognition model" — and were redirected into the bench root with
`model_storage_directory` + `user_network_directory`; the resulting files are
`models/easyocr/craft_mlt_25k.pth` and `models/easyocr/english_g2.pth` (**98.3 MB total**, measured).
Nothing was written to `~/.EasyOCR` or any project directory.

Head-to-head on the *same* five page classes at 300 dpi (CPU only, same machine):

| Page class | RapidOCR CER / latency / peak RSS | EasyOCR CER / latency / peak RSS |
| --- | --- | --- |
| clean scan page | 0.2096 (single-line artefact) / 2.81 s / 798 MB | **0.0412** / 15.76 s / 4300 MB |
| ruled table page | **0.0000** / 2.35 s / 1163 MB | 0.0312 / 13.74 s / 4365 MB |
| layout-heavy page | **0.0000** / 2.75 s / 1163 MB | 0.0099 / 14.62 s / 4407 MB |
| blurred/noisy/JPEG-45 scan | **0.0000** / 2.90 s / 1129 MB | 0.0598 / 14.74 s / 4418 MB |
| rotated 270° | **0.6744** (recall 0.63) / 2.68 s / 1148 MB | 0.8605 (recall 0.02) / 14.69 s / 4478 MB |
| rotated 180° | **0.7110** (recall 0.41) / 2.51 s / 1164 MB | 0.8272 (recall 0.02) / 14.93 s / 4515 MB |

Additional EasyOCR measurements: reader construction **including first model load 12.8 s**; RSS after
construction 540.6 MB; word recall on the four non-rotated pages 0.92–0.98 (vs 0.86–1.00 for RapidOCR);
mean confidence 0.78–0.95 on those pages, **0.20 on the 180° page** — i.e. it recognised that something
was there and was not confident about it.

## 18. What the two measurements actually say (no engine selected)

* **Neither candidate handles rotated scans.** Both degrade to CER 0.67–0.86 on 90/180/270 rotations;
  EasyOCR's word recall on rotated pages is **0.02** (it found essentially none of the words) and its
  confidence collapses to 0.20, while RapidOCR keeps ~0.41–0.63 recall with confident output — the
  more dangerous failure shape of the two. **Rotation handling must therefore be an explicit,
  separately measured step (a pre-pass or OSB/angle stage) in any OCR phase**, not an assumption.
* **On clean, degraded, table and layout pages at 300 dpi RapidOCR is exact** (CER 0.0000) once the
  single-line detector artefact is avoided (600 dpi, or a tuned detector resize); EasyOCR is never
  exact on those pages (CER 0.010–0.060) but *is* better on the one page where RapidOCR's artefact
  occurs (0.041 vs 0.210).
* **Cost is the decisive difference on this hardware:** RapidOCR ≈ 2.4–3.0 s/page at 0.8–1.2 GB peak
  RSS; EasyOCR ≈ 13.7–15.8 s/page at **4.3–4.5 GB peak RSS** and a 12.8 s cold start, with weights
  fetched from the network at first use. For a 100-page scan that is ~4–5 minutes vs ~25 minutes, and
  concurrency multiplies the memory.
* **Still not measured:** Windows/container parity for either engine; GPU behaviour; Tesseract (blocked,
  §14.6); quality on **real** scans and non-Latin scripts; whether tuning the detector resize setting
  (instead of raising the DPI) removes the RapidOCR artefact.

**Recommendation unchanged and still not a selection:** RapidOCR/ONNX is the candidate to carry into
Phase 1b's integration design on cost grounds, with EasyOCR as the accuracy fallback to revisit if
real-scan quality proves materially worse than this synthetic corpus suggests. **Gate 2 remains open:
no engine is selected, nothing is installed in `backend/venv`, no dependency, deployment file, schema
or model configuration has changed, and OCR implementation is still not authorized.**

## 19. Bench environment disposition (as authorized)

| Item | Value |
| --- | --- |
| Root | `%LOCALAPPDATA%\Temp\documind-ocr-bench\` (disposable, outside the repository) |
| Contents | `venv\` (interpreter + torch/onnxruntime, the bulk of the disk use), `corpus\` 630.4 MB / 33 files (generated PDFs incl. 600-dpi rasters), `models\` 98.3 MB / 2 EasyOCR weight files, `results\` 7 files (JSON + pip logs), 5 bench/diagnostic scripts |
| Result artifacts | `results/rapidocr_benchmark.json`, `results/easyocr_min.json` (full per-page rows) |
| Cleanup | delete the whole root (`rm -rf "$LOCALAPPDATA/Temp/documind-ocr-bench"`). It is Windows TEMP storage and **nothing in the repository references it**; the numbers above are the record's evidence, and the scripts are reproducible from §7.4/§14. The environment was left in place so the measurements can be inspected or re-run |
| Repository impact | none: no tracked or untracked project file was created, modified or deleted by the benchmark |
