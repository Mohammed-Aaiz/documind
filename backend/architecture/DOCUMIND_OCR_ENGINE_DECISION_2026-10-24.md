# DocuMind — OCR engine decision and implementation (2026-10-24)

**Status:** IMPLEMENTED — MEASURED (local, CPU-only engine).
**Resolves:** `DOCUMIND_PROJECT_CONTEXT.md` §61.6 (OCR approach) **for the local
scope only**. It does not open the architecture gate, does not change a schema,
and does not authorize a hosted OCR API or a vision-language model.

---

## 1. The question, and what was actually missing

Before this change a scanned PDF — and every scanned page of a mixed one — had
no text layer, so native extraction returned nothing for those pages. The
pipeline reported them correctly (`partial` / `error`,
`no_text_layer_ocr_disabled`) and their content was unreachable: not chunked,
not embedded, not retrievable, not citable. That is a capability gap, not a
weight-tuning problem, and no amount of retrieval work can close it.

The evidence base for the gap, unchanged by this record:
`DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md` §9 (probe: a
scanned PDF produced 0 elements) and `DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md`
§7 (engine comparison, no engine selected) and §14/§17 (RapidOCR and EasyOCR
measured in an isolated bench).

## 2. Decision

**RapidOCR (`rapidocr` 3.10.0) on the already-pinned ONNX Runtime, CPU only, as
the default OCR engine for pages that produce no usable text layer.**

Invocation is per page and conditional: OCR runs only for a page whose native
text carries fewer than `MIN_USABLE_CHARS` alphanumeric characters. A digital
document therefore pays nothing — no engine load, no inference, no latency
change (measured below).

Configuration (`backend/config.py`, environment variables are the upper-case
field names):

| setting | default | meaning |
|---|---|---|
| `OCR_ENGINE` | `rapidocr` | `off`/`none`/`disabled` turns the fallback off; pages are then reported unaccounted |
| `OCR_DPI` | `300` | render resolution for OCR |
| `OCR_PAGE_TIMEOUT_SECONDS` | `25.0` | one page's ceiling |
| `OCR_DOCUMENT_BUDGET_SECONDS` | `180.0` | one document's total ceiling; the rest of the pages stay unaccounted and the document is `partial` |

## 3. Measured on this machine (2026-10-24)

Environment: `rapidocr 3.10.0`, `onnxruntime 1.30.0`,
`opencv-python-headless 5.0.0.93`, Python 3.11, Windows, CPU only, **0 VRAM**.
Models ship inside the wheel (PP-OCRv6 det/rec/cls, 31.75 MB measured
previously in §14.5 of the Phase 1a record) — no system binary, no download at
run time.

| Measurement | Result |
|---|---|
| Recognition on a 300-dpi digital-quality scan | **CER 0.000**, mean line confidence 0.996-0.999 |
| Latency, 3-page scanned PDF, cold process | 8.77 s wall = **2.92 s/page ≈ 20.5 pages/min** |
| Peak RSS during that run | **745 MiB** |
| VRAM | **0 MiB** (no GPU is touched) |
| Digital page in a mixed PDF | **no OCR call, no engine load** |
| Sideways page (90°/270°) | median line-box w/h **0.07-0.08** vs **12.6** upright → detected and re-read correctly |
| Upside-down page (180°) | minimum line confidence **0.623** without the engine's line-angle classifier vs **0.998** upright → detected and re-read correctly at 0.999 |
| Handwriting, tables, formulas | **not measured — not claimed** |

Reproduce with the fixtures in `tests/integration/documents/test_ocr_scanned_pdf.py`
(they rasterise real text into image-only PDFs, so no font file is needed).

## 4. What the market's best is, and why it is not this choice (yet)

Recorded for the owner's question, with sources and dates, because "best OCR"
is not one number.

* **Frontier on page-parsing benchmarks (OmniDocBench v1.6, Sept 2026):**
  small document VLMs lead — TeleOCR 96.91, OvisOCR2 96.47, PaddleOCR-VL-1.6
  96.34 (0.9B, Apache-2.0, ~2 GB VRAM at FP16), MinerU2.5-Pro 95.75, GLM-OCR
  95.22; larger models: DeepSeek-OCR 2 (3B) 90.25. On olmOCR-Bench the leaders
  are Chandra OCR 2 (85.8) and olmOCR 2 (82.4) — a different benchmark, not
  comparable.
* **Enterprise managed APIs:** third-party comparisons report Azure Document
  Intelligence leading on printed text (~93% invoice field accuracy, ~82.7% on
  complex tables), AWS Textract ~78% fields / 80.9% tables at $1.50 per 1,000
  pages, Google Document AI ~82% fields / 64.6% tables. These numbers come from
  vendor-adjacent benchmarks and different documents; they are not a controlled
  comparison with the figures in §3.
* **Where the benchmark gap actually is:** the OmniDocBench overall score
  averages text, tables and formulas. On clean printed text the classical
  PP-OCR family already reaches CER ≈ 0 (§3), so the frontier advantage is
  concentrated in tables, formulas, handwriting, multi-column layout and
  **photographed** pages (Wild-OmniDocBench: PaddleOCR-VL fell from 91.93 to
  72.19 on photos).

**Why RapidOCR is the right engine for this product now:** the requirement is
text from scanned documents, offline, on a laptop, without competing with the
conversation model for VRAM. A 0.9B–3B VLM would add ~2–8 GB of VRAM or several
seconds per page on CPU, for gains that land in the categories this pipeline
does not read anyway (tables/formulas are handled by deterministic readers on
the *text* path, and scanned tables would need a table model, not just OCR).

**Recorded as future options, not adopted:** PaddleOCR-VL-1.6 for layout/table
structure on scanned pages, and an orientation/layout pre-pass. Either requires
a new decision record, a dependency and VRAM budget, and a measured comparison
against this baseline — the same rule the generative path follows.

## 5. Implementation

| File | Change |
|---|---|
| `backend/documents/ocr.py` | **new** — engine adapter, orientation correction, per-page timeout, per-document budget, line filtering, honest failure types |
| `backend/documents/processing.py` | per-page OCR fallback inside `_extract_pdf_with_coverage`; `PageCoverage` gained `ocr_pages`, `ocr_failed_pages`, `ocr_attempted`, `ocr_unavailable`, `ocr_engine`; `extract_document(..., ocr_policy=...)` |
| `backend/documents/routes.py` | verdict reason now distinguishes `ocr_failed_all_pages` (OCR ran, nothing readable) from `no_text_layer_ocr_disabled` (OCR off/unavailable); `_process_document(..., ocr_policy=...)` for tests |
| `backend/config.py` | the four OCR settings |
| `backend/requirements.txt` | `rapidocr==3.10.0`, `opencv-python-headless==5.0.0.93` |

### 5.1 Per-page provenance (added later the same day)

§7 item 4 below used to say that nothing about a page's extraction survived the
run. That is no longer true: every page the extractor handles now writes one
`page_extractions` row, so the API and UI can answer "which pages were OCR'd"
after the fact.

| File | Change |
|---|---|
| `backend/migrations/versions/009_add_page_extractions.py` | **new** — additive table, `down_revision = "008"`, no backfill |
| `backend/documents/models.py` | `PageExtraction` ORM row (one per page per document, `UNIQUE (document_id, page_number)`) |
| `backend/documents/page_extractions.py` | **new** — `replace_page_extractions(...)` writes the run's records, `document_pages_with_ocr(...)` aggregates the stored truth |
| `backend/documents/processing.py` | `ExtractionResult.page_extractions` carries the per-page records; nothing is inferred outside the extractor |
| `backend/documents/insights.py`, `routes.py`, `schemas.py` | `GET /api/documents/{id}/insights` gained a `pages` block |
| `src/lib/api.ts`, `src/components/common/DocumentInsightsPanel.tsx` | `pages` typed and rendered (counts, OCR engine(s), per-page table) |

What is stored per page: `page_number`, `method` (`native` / `ocr` / `none`),
`text_chars`, and — OCR pages only — `ocr_engine`, `ocr_engine_version`,
`ocr_confidence`, `ocr_rotation`, `ocr_seconds`. A page that failed carries a
`failure_reason` (`no_text_layer`, `ocr_disabled`, `ocr_unavailable`,
`ocr_budget_exhausted`, `ocr_failed`). Rows are written in the same finalising
transaction as the chunks, so a re-ingest replaces the previous run's rows
rather than accumulating stale ones.

Honest scope of this addition: it is **evidence only**. The rows are read by the
insights endpoint and the document panel; nothing in retrieval, ranking or the
answer path reads them. Documents ingested before revision 009 have no rows and
report an empty page list — there is no backfill, and none is planned, because
the per-page facts cannot be reconstructed from the chunks after the fact.

Behaviour contract, in order of precedence:

1. A page with a usable text layer is never OCR'd.
2. A page OCR reads becomes **one `text` element** carrying that page number and
   the heading context in effect. No heading levels, table cells or list
   structure are invented — OCR cannot support them.
3. A page OCR cannot read stays unaccounted; the document is `partial` when at
   least one other page is usable, `error` / `ocr_failed_all_pages` when none is.
4. OCR is attempted only while the document budget lasts; every page after it
   is reported unaccounted, never silently skipped as "read".
5. A missing engine is reported (`ocr_unavailable`) and the verdict falls back
   to `no_text_layer_ocr_disabled` — no exception escapes ingestion.

## 6. Verification

| Command | Result |
|---|---|
| `pytest tests/unit/documents/test_ocr_fallback.py -q` | **15 passed** |
| `pytest tests/integration/documents/test_ocr_scanned_pdf.py -q` | **8 passed** |
| `pytest tests/unit/documents -q` | **191 passed, 1 skipped** |
| `pytest tests/integration/documents -q` | **129 passed** |

The integration tests use real image-only PDFs (text rasterised into an image),
run the real engine, and assert the recognised text reaches the **chunk graph**
— not just the coverage counter. `tests/unit/documents/test_phase1a_page_completeness.py`
now passes `OcrPolicy.disabled()` explicitly, because it measures the accounting
rule and must not start depending on a provisioned engine.

## 7. Limitations — do not overstate

1. **Not a document parser.** OCR returns text lines. It does not recover
   tables, columns, reading order within a page beyond line order, headings or
   formulas. Scanned tables remain text, not structure.
2. **Handwriting and photographed pages are unmeasured** here and are the
   weakest case for any classical OCR engine.
3. **Rotation correction is bounded to 90/180/270**, and a page that is skewed
   by a few degrees (not a multiple of 90) is not deskewed.
4. **Per-page provenance is persisted only for new ingestions** (§5.1). Rows
   exist for every page of a document processed after revision 009; documents
   ingested earlier report an empty page list, because the per-page facts are
   not recoverable from chunks. The stored `ocr_confidence` is the engine's mean
   line confidence — it is not a calibrated probability and must not be
   presented as an accuracy figure.
5. **The structure parser (`documents/parser.py`) still sees only native text.**
   OCR'd pages contribute chunks and the chunk-derived structure graph, but no
   `document_structure_elements` rows.
6. **Retrieval is unchanged and unmeasured for OCR text.** OCR text enters the
   same chunk → embed path as native text; no OCR-specific retrieval metric has
   been produced.
7. **Single engine, no comparison run in production.** RapidOCR vs EasyOCR was
   measured in the isolated bench (§14/§17, Phase 1a record); no second engine
   is wired in, so a regression here would be caught by these tests, not by a
   live A/B.

## 8. Gate status after this task

| Gate | Status |
|---|---|
| §61.6 OCR approach | **RESOLVED for the local RapidOCR scope** (this record); a VLM/table-model tier remains open |
| Gate 23 (per-page coverage/provenance field) | **RESOLVED by owner request 2026-10-24 — option A (persist) implemented in §5.1**: provenance is stored per page and reported by `GET /api/documents/{id}/insights`; the document verdict itself is unchanged |
| §59.10 architecture gate | **NOT OPEN**; the OCR work itself landed no schema change, and the later `page_extractions` table (§5.1) is additive evidence metadata read by one endpoint — it changes no retrieval behaviour, no ranking, no model and nothing in the answer path |
| §60 Gate 3 (structure extraction recall) | **Unchanged / unmeasured** — this record does not measure table or section recall |
| Deployment | pip-only; `Dockerfile` needs no OS package; no network at run time after install |
