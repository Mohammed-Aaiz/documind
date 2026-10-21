# E0 SOURCE PROVENANCE — Phase 4F.6-D (Tasks 1–6)

**Date:** 2026-09-23 · **Diagnostic version:** `e0-prerequisite-v1` · **Nature:** prerequisite recovery and verification only — **E0 was not executed**; no failure-stage attribution, no bottleneck conclusion, no hypothesis verdict is drawn here (Task 15).

**Frozen input (verified this phase, read-only):**
- Benchmark `qa_benchmark_v1.jsonl`: **182 lines / 140 answerable / 42 unanswerable / 6 documents**, sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches the frozen hash** (recomputed, unchanged).
- Source dataset `training_data_v3_1.jsonl`: sha256 `a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97` — matches `benchmark_manifest.json.source_dataset_hash` (unchanged).
- Production `model.safetensors`: sha256 `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` — unchanged.
- Per-document example counts recomputed from the benchmark match `benchmark_manifest.json` exactly for all six identities.

---

## Task 1 — Six P3 document identities (verified from the frozen benchmark/manifest)

| # | document_id | benchmark examples | answerable / unanswerable |
|---|---|---|---|
| 1 | `unanswerable_corpus` | 42 | 0 / 42 |
| 2 | `company_history_eta` | 44 | 44 / 0 |
| 3 | `financial_report_q3` | 38 | 38 / 0 |
| 4 | `api_docs_lambda` | 20 | 20 / 0 |
| 5 | `dataset_desc_mu` | 22 | 22 / 0 |
| 6 | `legal_contract_epsilon` | 16 | 16 / 0 |
| | **total** | **182** | **140 / 42** |

`six_identities_verified: true`, `document_counts_match_manifest: true`, `counts_match_expected: true` (`diagnostics/summary.json` → `frozen_verification`).

---

## Task 2 — Source-document recovery (outcomes A / B / C only)

**Result: 6 × `DETERMINISTIC_SOURCE_RECONSTRUCTIBLE` (B) — no `STANDALONE_SOURCE_EXISTS` (A), no `SOURCE_UNRESOLVED` (C).** No document text was invented: every byte comes from static local definitions or from the frozen benchmark records themselves.

| document_id | classification | generator path | symbols / function | required inputs | seed | reconstruction method | document sha256 (CANON-v1 text) | bytes |
|---|---|---|---|---|---|---|---|---|
| company_history_eta | **B** | `backend/phase4f/dataset/expand_and_audit.py` | `DOCUMENTS`, `_add_doc` (literal `_add_doc("company_history_eta"` present in source: yes) | module import only | seed 42 affects example sampling only — **document text is static data, no RNG** | CANON-v1 serialization of the static section tree | `c8425307f982eadce5340c4a666ad794e6afa0a64576f09d77b9d74ca9466f97` | 3148 |
| financial_report_q3 | **B** | same | same | same | same | same | `0044c58e37e49c05b55288a620ce450c594d2c640962ef11988efb4b0f818cd4` | 2213 |
| api_docs_lambda | **B** | same | same | same | same | same | `4f209f437655d07fbe0d86d4754e966e142473dbdea726cd6bf9faa9dff64586` | 1912 |
| dataset_desc_mu | **B** | same | same | same | same | same | `97ae7a648bafcc06dda856fa36ea474b4d621b13b01a651710c3a5d47d51a6c4` | 2008 |
| legal_contract_epsilon | **B** | same | same | same | same | same | `b767a129ac560c3f800c6fe79f187c70ccbcaafc1dc1ce4d42179c708e3db567` | 2158 |
| unanswerable_corpus | **B (virtual corpus)** | same file | `ExampleGenerator.gen_unanswerable` static `unanswerable_pairs` | benchmark records (authoritative carrier) + generator source (cross-check) | n/a — static list | `document_text` = the 42 benchmark distractor contexts in benchmark order; **all 42 context literals verified present in the generator source file** | `ca0ef7ab95eb818636af8a217a065ec585835f07b17fca26830ee961e82821a5` | 2892 |

Notes:
- `unanswerable_corpus` is **not a coherent document**: its 42 contexts are standalone distractor sentences. It is reconstructed as the ordered union of its benchmark-carried texts (deterministic, no invention) and is flagged `virtual: true` everywhere. No gold evidence is asserted for its examples.
- Per-document `document_sha256` values are recorded in `E0_CORPUS_MANIFEST.json`; full records (including text) live in `e0_diagnostics/source_corpus/<doc_id>.json`.
- Historical artifacts (`expand_and_audit.py`, datasets, benchmark) were **read only**.

## Task 2b — CANON-v1 canonical serialization (defined before measuring)

```text
section block = "\n\n".join([heading?] + paragraphs + [table blocks] + [list blocks])   # DOCUMENTS key order
table block   = "\n".join(" | ".join(row) for row in [headers] + rows)
list block    = expand_and_audit._list_str(list)      # heading + items, newline-joined (exact copy, line 926)
document text = "\n\n".join(section blocks)
section-body stream (generator view) = "\n\n".join(_section_text(s))   # heading + paragraphs ONLY (line 934)
```

CANON-v1 is a **diagnostic definition**, validated empirically by Task 4 — not an assumption: where contexts fail to match, the failure mechanism is identified against the generator's own construction code (§4).

---

## Task 4 — Benchmark → source provenance (denominator: **140 answerable**)

**Class counts:** `SOURCE_SPAN_VERIFIED` **86/140 (61.4%)** · `SOURCE_SPAN_NOT_FOUND` **54/140** · `SOURCE_MAPPING_AMBIGUOUS` **0/140** · `SOURCE_UNRESOLVED` **0/140**.

| Category (n) | VERIFIED | NOT_FOUND | mechanism of NOT_FOUND (measured) |
|---|---|---|---|
| DIRECT_SPAN (24) | **24** | 0 | — |
| SECTION_SPECIFIC (16) | **16** | 0 | — |
| LIST_ITEM (20) | **20** | 0 | — |
| LONG_CONTEXT (10) | **10** | 0 | — |
| TABLE_ROW (16) | 3 | 13 | `synthetic_header_row_pair`: generator builds context as `header_line + "\n" + row_line` for **every** row (`expand_and_audit.gen_table_row`), but only row 1 is contiguous in the natural table text |
| TABLE_CELL (24) | 4 | 20 | same header+row-pair construction (`gen_table_cell`) |
| NUMERIC (20) | 3 | 17 | `static_fact_fragment`: context is a hand-written fact fragment (`gen_numeric.numeric_facts`), not a span of the paragraph |
| MULTI_CHUNK (10) | 6 | 4 | `synthetic_section_body_concatenation`: context built from `_section_text` stream (excludes tables/lists), so intervening structural blocks break contiguity in CANON-v1 text |

**Context-nature totals (denominator 140):** `one_source_span` 86 · `synthetic_header_row_pair` 33 · `static_fact_fragment` 17 · `synthetic_section_body_concatenation` 4.

**MULTI_CHUNK three-way nature (Task 4 requirement, denominator 10):**
- one source span: **6/10** (canonical span, includes cross-section-boundary windows where no structural block intervenes)
- multiple source spans: **0/10**
- synthetic concatenation: **4/10** (section-body-stream span with tables/lists excluded — flagged `synthetic_section_body_concatenation`, stream position and boundary-crossing recorded per example in `provenance_results.jsonl`)

**Structural provenance verified separately (Task 4 requirement):**
- Tables: **40/40** table examples (24 cell + 16 row) resolve to a unique `(table id, row index[, column])` via exact header-line + serialized-row membership in the reconstructed document's generator tables.
- Lists: **20/20** list-item examples resolve to a unique `(list id, item index)`.
- **Cross-document context ambiguity: 0/140** — no context string of any answerable example occurs in any other of the six documents.

**Offset derivability:** gold `source span = context position + answer_start/end` is exact for the **86** uniquely-located contexts (`source_offset_match` verified by re-slicing: 86/86 consistent). For the 54 non-contiguous contexts, offsets are correctly **unavailable** (reason recorded per example: `context_not_a_source_span_offsets_unavailable`) — presence checks then run at answer level (§5).

**What Task 4 does NOT say (Task 15):** the 54 NOT_FOUND results are *documented generator construction mechanisms*, not failure attributions. They say the benchmark context is an extracted/assembled view — not that retrieval, representation, or extraction fails. No architecture or hypothesis claim follows from this table.

---

## Tasks 5–6 — Isolated chunk corpus and gold-evidence presence (summary)

Full detail: `E0_CHUNK_MANIFEST.json` + `e0_diagnostics/diagnostics/chunk_evidence_results.jsonl`.

**Chunk corpus (existing production legacy chunker, config recorded before execution):** `chunk-v1-legacy-chars-1000-200` (`config.py chunker_version="legacy"` default; `documents/processing.py:607-608` CHUNK_SIZE=1000 / CHUNK_OVERLAP=200; heading enrichment via `_prepend_heading_context`). **93 chunks** across the six documents (51 content + 42 virtual-corpus), **source offsets resolved 93/93**, per-chunk structure ids (section/table/row/cell/list/item) computed by span intersection. Production storage, database, and chunker code untouched.

**Gold-evidence presence (denominator 140 answerable, multi-criterion NORM-v1-style: textual N1 / numeric N2–N3 / structural N4):**

| Measure | Count / denominator |
|---|---|
| gold answer present in reconstructed source document | **140 / 140** |
| gold answer present in isolated stored chunks | **140 / 140** |
| gold span fully contained inside one chunk | **140 / 140** |
| gold span crossing a chunk boundary | **0 / 140** |
| exact context-position offsets usable (`source_offset_match`) | **86 / 140** (equals VERIFIED count; 54 have no contiguous context — expected) |
| structural context (table header / list heading) present in the covering chunk — TABLE_CELL | **24 / 24** |
| same — TABLE_ROW | **16 / 16** |
| same — LIST_ITEM | **20 / 20** |
| examples carrying ≥1 ambiguity flag (multi-occurrence answer/numeric candidate) | **34 / 140** (flagged, not resolved silently) |

Per-category in-source / in-chunk rates are 140/140 across all eight categories (`summary.json` → `task6_chunk_evidence.per_category`).

**Unanswerable examples (42):** no gold evidence invented; no L3–L5-style presence assertions computed; their contexts are recorded as virtual-corpus texts only (Task 5 of the 4F.6-C protocol preserved).

---

## Reproducibility

- Builder: `e0_diagnostics/tools/build_e0_prereqs.py` (deterministic; `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` forced before imports — **no network access possible**).
- Environment: Python 3.11.0 · transformers 5.16.1 · tokenizers 0.23.1 · torch 2.13.0+cpu · sentence-transformers 6.0.1 (Windows 10).
- Per-example records: `e0_diagnostics/diagnostics/provenance_results.jsonl` (140) and `chunk_evidence_results.jsonl` (140); aggregates: `diagnostics/summary.json`.
- Corpus/chunk artifacts: `e0_diagnostics/source_corpus/` (6), `e0_diagnostics/chunks/` (6 jsonl).

## Boundary declarations

```
GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
TRAINING RUN: NO
INFERENCE RUN: NO (one tokenizer-only model-input capability probe, no forward pass)
RETRIEVAL RUN: NO — traces NOT created (see E0_RETRIEVAL_RUN_MANIFEST.json)
E0 EXECUTED: NO
PRODUCTION MODIFIED: NO
FROZEN DATASET MODIFIED: NO
BENCHMARK MODIFIED: NO
HISTORICAL ARTIFACT MODIFIED: NO
COMMIT: NO
PUSH: NO
```
