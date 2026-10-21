# Table Evidence Architecture — Design & Audit

**Audit date:** 2026-10-06
**Scope:** Read-only production architecture investigation and design for how DocuMind should
represent and retrieve table evidence so that a relevant table can reach the QA model without
increasing the QA token budget, truncating evidence, changing RRF weights, weakening semantic
evidence, regressing other answers, or special-casing the teacher-demo document.
**Status:** No production code, schema, migration, model, `.env`, existing test or evaluation report
was changed. No phase is implemented. This document is a plan for the next agent.

**Path convention:** this file lives in `backend/evaluation/reports/` (EVALUATION_AGENT-owned), next
to the existing `structural_retrieval_reachability_audit.md` and `structural_retrieval_fix_report.md`,
and follows the same `# Title` + `**Audit date:**` + numbered-section layout. The alternative location
`backend/architecture/` is append-only Coordinator-owned evidence, which is why the requested
evaluation-reports path was chosen.

**Evidence basis.** Every number below was measured read-only against the running production stack
and the real database on 2026-10-06: `documents.processing.extract_pdf` on the real demo PDF,
`chat.rag` retrieval/fusion/context functions on the real document, direct SQL over
`document_structure_elements` / `document_chunks` / `document_graph_edges`, and live
`POST /api/chat/ask` responses. Nothing here is estimated from memory; nothing was fabricated.

---

## 1. Executive Summary

The previous attempt at this problem failed for a reason that the design must respect: **retrieval
already reaches the table — representation and budget policy are the blockers.**

Measured on the real teacher-demo document (`ada99ed5-e95a-439f-8700-261535b9dfa5`):

* the persisted aggregate `table` element (sequence 34, page 4, 230 tokens) **is** a production
  structure-element retrieval candidate — position 6 of 10 for the Q2 question;
* it is **not** in the fused top-5 (`retrieve_dual_path` top-5 contains only chunks), so it is
  appended by `_augment_with_structure` as an unranked tail entry;
* `build_qa_context` may only truncate the **rank-1** item, so every later item must fit *whole*;
  the five ranked chunks already consume 266 of the 362-token budget, and 230 > 96;
* hence `266 + 230 = 496 > 362` — the aggregate table can never be supplied intact, in any order.

Two further measured facts shape the fix:

* the extractor **already has** row/cell data (`ExtractedElement.table_data` from PyMuPDF
  `find_tables()`), and the structure-aware chunker already knows how to emit header-repeated
  table rows — but the **public parser contract discards `table_data`**, so `table_row` /
  `table_cell` nodes are never persisted, and the production chunker default is still the
  legacy 1000-char chunker, which persists no chunk structure metadata at all;
* a faithful compact row representation is cheap: header = 15 tokens, header + one row = 36–48
  tokens, one labelled `column = value` fact ≈ 4–10 tokens, versus 230 tokens for the aggregate.

**Recommended architecture (hybrid, additive):** persist per-row table evidence as *compact,
header-repeated row records and row/column-labelled cell facts* in a **dedicated
`document_table_rows` store** (Option A's granularity without renumbering the element stream),
**linked** to the aggregate table element, its parent section and (where derivable) the embedding
chunk (Option C), and surfaced by a **query-gated, additive "table evidence band"** inside the
existing QA-context budget (Option B). The band is inserted after the ranked chunks and before the
unranked document-order element tail, sized from a bounded per-query reservation, and it drops only
*unranked structural tail entries* — it never reorders, removes or re-ranks chunks, and it is
**completely inert when the question has no table dimension match**, which is what makes the Q3
regression structurally impossible rather than merely tested against.

**Status: BLOCKED at the aggregate-element level (unchanged), DESIGN READY at the architecture level.**
The table still does not reach QA today, and this document does not claim otherwise.

---

## 2. Current Production Behavior

### 2.1 End-to-end trace (verified in code)

| Stage | Implementation | Observed behaviour for the demo document |
| --- | --- | --- |
| PDF → parser | `documents/processing.py::extract_pdf` → `documents/parser.py::parse_pdf` | 45 parser elements; **1** aggregate `table` element |
| row/cell data at extraction | `processing.py::_pdf_table_element` (`ExtractedElement.table_data`) | 9 rows × 5 columns present in memory |
| persisted structure elements | `documents/structure.py::replace_document_structure` | 45 rows: 9 `section`, 35 `paragraph`, 1 `table`; **0** `table_row`, **0** `table_cell`; `bbox_*` all NULL; `document_structure_edges` = 0 |
| document chunks | `documents/routes.py::_build_chunk_objects` with `resolve_chunker_version(...)` over the configured value (`config.py`: `chunker_version = "legacy"`) | 45 chunks, version `chunk-v1-legacy-chars-1000-200`; `element_type`/`heading_path`/`section` NULL on **45/45** |
| chunk graph | `graph/service.py` (`replace_document_graph`) | `document_graph_edges` = 238 rows (chunk-level; non-empty) |
| semantic retrieval | `chat.rag.retrieve_chunks` (pgvector, `top_k=5`) | for Q2: 5 chunks, 266 tokens total |
| structural chunk retrieval | `chat.rag.retrieve_structural_candidates` (seeds: heading/section terms + top-3 semantic ids; traversal `MAX_HOPS` imported as `GRAPH_MAX_HOPS`, `STRUCTURAL_CANDIDATE_LIMIT=15`) | contributes the hybrid chunks; no table |
| structure-element retrieval | `chat.rag.retrieve_structural_element_candidates` (`STRUCTURAL_ELEMENT_CANDIDATE_LIMIT=10`; seeds from `heading_path[-1]` names; BFS over `parent_id`, `MAX_ELEMENT_HOPS=2`, `MAX_ELEMENT_NODES=40`) | 10 candidates; **table is candidate #6** |
| RRF fusion | `chat.rag.fuse_dual_path` / `RRF_K=60`, `RRF_SEMANTIC_WEIGHT=0.70`, `RRF_STRUCTURAL_WEIGHT=0.30` | top-5 returned: 3 hybrid + 2 semantic chunks; **table absent** |
| augmentation | `brain/adapters.py::_augment_with_structure(db, chunks)` → `graph/evidence.py::collect_document_structure_evidence(per_document_limit=20)` | 25 stream entries = 5 chunks + **20 elements in document order** (sequences 0–19); table (34) **absent** |
| QA context | `chat.rag.build_qa_context` (budget = `get_max_input_length()` − question overhead − `QA_TOKEN_SAFETY_MARGIN`) | budget 362; used 359; 13 supplied (5 chunks = 266 tokens + 8 elements = 93 tokens); 12 omitted |
| QA model | `chat/qa_model.py` (local DistilBERT, `_DEFAULT_MAX_INPUT_LENGTH = 384`) | answer `'every 250 operating hours'`, confidence 0.0653, `factualGrounded=true` |
| answer source (live) | `AskResponse.sources` = the *kept* (supplied) set only (`brain/__init__.py` restricts to `ContextPack.included_ids`) | answer span lives in **chunk 0096e99e… (kind=chunk, path=hybrid, page 4, 65 tokens)** — the paragraph that repeats the table fact |
| Reliability Center | `reliability/routes.py` (`GET /api/reliability/last-query`) | returns `structuralElementSourceCount` and per-source `evidenceKind`; **no** `section`, `elementType`, row or table fields |

### 2.2 Why tables are persisted as one aggregate `table` element

`processing.py::_pdf_table_element` builds **one** `ExtractedElement` per detected table:

```python
content="\n".join(" | ".join(row) for row in table_data),
element_type="table",
table_data=table_data,          # rows/cells retained IN MEMORY only
```

`parser.py::_build_elements` then performs a documented one-to-one mapping and **synthesises
nothing**:

```python
elements.append(ParsedElement(source_id=…, element_type=element_type, …, content=…))
```

`ParsedElement` has no `table_data` field, and `EMITTED_ELEMENT_TYPES` is explicitly
`{section, paragraph, table, text_block}` — the module docstring states that `table_row`,
`table_cell`, `page`, `figure`, `list` and `list_item` are "part of the supported vocabulary but
are **not** emitted for PDF". `structure.py` persists exactly one `DocumentStructureElement` per
`ParsedElement`. The row/cell structure therefore exists at extraction time and is discarded at the
parser boundary — it is not missing from the extractor.

### 2.3 Why `table_row` / `table_cell` nodes are not emitted

Three separate, deliberate gates, all of which must be opened for row/cell nodes to exist:

1. `processing.py` retains rows only as `table_data` on the aggregate element;
2. `parser.py::_build_elements` never splits an element, and `ELEMENT_TYPE_MAP` has no mapping for
   `table_row`/`table_cell` (an unmapped internal type raises `ParserValidationError` rather than
   being silently reclassified);
3. `structure.py` persists one element per parser element, so the vocabulary in
   `graph/models.py::ELEMENT_TYPES` is a *supported* vocabulary, not an emitted one.

Additionally, `documents/chunking.py::_emit_table` **does** implement row-level serialization
(`table_atomic` when the serialized table fits `CHUNK_MAX_TOKENS = 256`, otherwise `table_rows`
with the header row repeated in every sub-chunk, strategy recorded in `ChunkMeta.strategy`), but it
is only reachable with `chunker_version = "structure-v2"`, and `config.py` defaults to
`chunker_version = "legacy"`. The demo document was ingested with the legacy chunker, so its table
exists in the chunk stream as one 234-token blob chunk (index 34) with NULL structure metadata.

---

## 3. Exact Root Cause

Five independent causes; fixing only one of them cannot work (this is exactly why the reverted
attempt failed).

**C1 — Representation granularity.** The only persisted table evidence is a single aggregate
element of 230 tokens (`processing.py` → `parser.py` → `structure.py`). No row or cell evidence
exists to retrieve.

**C2 — The aggregate cannot fit the residual budget.** `build_qa_context` budget for Q2 is 362
tokens; the five ranked chunks consume 266; the aggregate needs 230. `266 + 230 = 496 > 362`. This
is arithmetic, not ordering.

**C3 — Post-ranking, unranked, document-ordered augmentation.** `_augment_with_structure` appends
`collect_document_structure_evidence(document_ids, per_document_limit=20)` — the document's first 20
elements by `sequence_index ASC, id ASC` — with `score=0.0`, `retrieval_path="structural"`,
`evidence_kind="structure_element"`. The table is element sequence 34 and is therefore never even
appended to the stream.

**C4 — Truncation eligibility is rank-1 only.** `build_qa_context` truncates **only** the first
item (`if parts: omitted.append(...); continue`); every later item must fit *whole*. A 230-token
item appended after the chunks can therefore never be included, no matter how it is ordered within
the tail.

**C5 — No usable chunk→structure linkage exists today.** `document_chunks` for this document has
`element_type`, `heading_path` and `section` NULL on 45/45 rows (legacy chunker), so a retrieved
chunk cannot resolve its section or its table from chunk metadata. `document_structure_edges` is 0
rows, so the element graph has no edges to traverse (only `parent_id` links, which
`expand_element_seeds` already walks).

---

## 4. Token-Budget Analysis

### 4.1 Where the budget comes from

| Quantity | Value | Source |
| --- | --- | --- |
| QA model maximum input length | **384** tokens | `chat/qa_model.py::get_max_input_length()` (`_DEFAULT_MAX_INPUT_LENGTH = 384`, overridden by inference config) |
| Question + special-token overhead | ≈ 18 tokens | `chat/rag.py::_question_overhead` via the model tokenizer |
| Safety margin | 4 tokens | `chat/rag.py::QA_TOKEN_SAFETY_MARGIN` |
| **Effective context budget (Q2)** | **362 tokens** | measured live: `contextBudgetTokens = 362` |

The 384-token window is a property of the **trained project QA model**, which must not be changed.
There is no slack to reclaim: `266 + 230 > 362` is a hard wall, which is why "increase the budget"
and "make the aggregate fit" are both invalid directions.

### 4.2 Measured composition of the live Q2 context

| Band | Items | Tokens | Cumulative |
| --- | --- | --- | --- |
| Ranked fused chunks | 5 | **266** | 266 |
| Unranked structure elements (document order, first 20 of 45) | 8 fitted of 20 appended | **93** | 359 / 362 |
| Aggregate table element | 0 (not appended) | 230 needed | — |

The 8 fitted element entries are, in order: 6, 12, 11, 28, 10, 1, 4, 21 tokens — cover-page title,
platform subtitle, "Prepared by", document-ID/revision, classification, "Abstract", a section
heading, and one executive-overview sentence. They are demonstrably not answer-bearing for Q2 and
they are the only droppable mass in the context.

### 4.3 Measured cost of the faithful alternatives (real table, 9 rows × 5 columns)

| Representation | Tokens | Fits residual 96? |
| --- | --- | --- |
| Aggregate table element (today) | **230** | **no** (`266 + 230 = 496 > 362`) |
| Header row alone | 15 | yes |
| **Header + one row** (row-stratified unit, header repeated) | **36–48** (min 36, max 48) | **yes** |
| One row without header | 21–33 | yes, but ungroundable (columns unnamed) |
| One labelled cell fact, e.g. `Calibration Interval = 250 h` | **4–10** | yes (fits even in single-digit slack) |

Measured rows of the real table (`Lidar Array LR-9 | 250 h | 0-80 m | > 2.5 mm error | Recalibrate on
reference rig`) show that a header-repeated row is *both* small and self-contained — the same
correctness argument the structure-aware chunker already records for `table_rows`: an extractive
span such as `250 h` is ungroundable without the column name, and a dense embedding of a headerless
row does not match table questions.

### 4.4 Consequence

A row-level evidence unit (36–48 tokens) fits the measured residual; the aggregate (230) never can.
**The fix is a representation-size fix plus a bounded reservation policy — not a budget increase and
not a re-ranking of the existing element stream.**

---

## 5. Why Relevance Ordering Alone Failed

The reverted attempt changed `_augment_with_structure` to select relevance-first (seeding from
`retrieve_structural_element_candidates`) while keeping the same per-document bound. Measured
outcome on the real document:

* the table **was** appended — at stream position 10 of the 25-entry augmented list (after the five
  fused chunks and four element entries of 4/17/6/45/24 tokens);
* it was **still not supplied** to QA: the preceding entries consumed the remaining ~96 tokens
  against a 362-token budget, and rule C4 (only rank-1 is truncatable) forbids including it
  partially;
* the supplied counts changed (15→13, 13→10, 16→12, 13→10, 16→17) and one answer regressed (§6).

Structural reasons the approach could not work, independent of the specific heuristic:

1. The element stream is **post-ranking**: elements are appended *after* `retrieve_dual_path`, so
   ordering inside that stream cannot change the ranked top-k, cannot grant truncation eligibility
   (C4), and can only shuffle which small tail entries fit.
2. The whole tail is worth ~93 tokens against a 230-token need; re-ordering inside a 93-token budget
   cannot make a 230-token item fit.
3. Re-ordering a *shared, size-limited* window changes which **unranked** entries are included,
   which changes the QA context string — a change with no benefit but real regression risk (§6).

**Conclusion:** ordering is the wrong lever. Granularity (C1) and budget policy (C2/C4) are the
levers.

---

## 6. Q3 Regression Analysis

**Observed (measured, before the revert):** for
`According to Sensor Calibration and Power Management, which power rail supplies the inertial
measurement unit?` the answer changed from the correct `battery rail` to the wrong `solar bus`
(confidence 0.0521 → 0.0606, supplied 16 → 12), with RRF untouched and the fused chunk set
unchanged.

**Mechanism, as far as the evidence supports:**

1. The QA model is **extractive over a single context string**. `build_qa_context` concatenates
   `ContextPack.included_ids` in list order; changing which unranked tail entries are included
   changes that string, and a changed string can change the decoded span even when the ranked
   chunks are identical. The change was therefore *plausible* without any chunk being displaced —
   which is exactly why "we only reordered the tail" was not a safety argument.
2. The failure is semantically adjacent, and the table itself contains the trap: the demo table has
   row 4 `Primary Battery Rail` and row 5 `Auxiliary Solar Bus` — the same two candidates as the
   Q3 confusion. Any design that injects table rows for a power-rail question measurably increases
   the chance the model picks the solar row, because both keys are then present in the same window.

**Design consequences (binding):**

* the table-evidence path must be **inert unless the question matches the table's own dimension
  (header) terms** — for Q3 no header term matches (`Component`, `Calibration Interval`, `Operating
  Range`, `Failure Threshold`, `Recommended Action` vs. "power rail / supplies / inertial
  measurement unit"), so the context stays byte-identical to today and Q3 cannot change;
* table evidence must be **additive**: the ranked chunk list, its order and its inclusion must be
  provably untouched (`included_ids` for chunks unchanged) — only unranked structural tail entries
  may be dropped, and every dropped id must be reported through the existing
  `omitted_source_ids` / `omittedSourceCount` provenance;
* the specific Q3 question must be a **hard regression gate** in the test suite (§19) and in the
  live acceptance run (§20), with the pre-change answer `battery rail` as the expected value.

---

## 7. Option A — Row/Cell Graph Representation

**Persist** `table → table_row → table_cell` as first-class nodes.

*Parser changes (BACKEND_AGENT, `documents/`):*
* extend the public contract so `ParsedElement` carries the extractor's `table_data`
  (`processing.py::_pdf_table_element` already builds it);
* emit row nodes and cell nodes with the existing deterministic `source_id` scheme
  (`{element_type}:{page}:{sequence_index}`) and parent links from the table element;
* keep `ELEMENT_TYPE_MAP` strict — unmapped internal types must keep raising.

*DB changes (DATABASE_AGENT):* `document_structure_elements` already supports the vocabulary
(`graph/models.py::ELEMENT_TYPES` includes `table_row`/`table_cell`). Two schema realities bite:
`UniqueConstraint(document_id, sequence_index)` makes `sequence_index` the *only* document-order
key, and `collect_document_structure_evidence` + `_augment_with_structure` select "the first 20" by
it. Emitting 9 rows + 45 cells inline therefore **renumbers every later element** (`sequence_index`
must stay contiguous 0..N−1 per `parser.validate_parsed_document`) and shifts the document-order
window: for this document the element stream would grow 45 → 99, and the first-20 window would be
dominated by table cells. Existing invariants (`45 elements`, `9 sections / 35 paragraphs / 1
table`, "first 20 in document order") and several existing tests would change meaning.

*Retrieval/evidence:* rows and cells become retrievable candidates through the existing element
candidate path (`retrieve_structural_element_candidates` → RRF), i.e. they can enter the fused
top-k and thus become truncatable rank-1 items. Provenance is native (`parent_id`, `page_number`,
`heading_path`, `element_type`).

*Token efficiency:* excellent for cells (4–10) and rows (21–33), but **without header repetition**
a row is ungroundable and a cell has no column name — so the retrieval unit must still be a
serialized window (header + row), i.e. §8's representation.

*Migration/rollback:* element-stream renumbering is a **data-shape change**: all structure rows are
rebuilt on reprocess (`replace_document_structure` deletes and reinserts), so it is not destructive
to chunks, but it changes element identity/ordering and requires re-verifying the augmentation
window. Rollback = revert code + reprocess (row/cell nodes simply stop being emitted; the aggregate
table element can be restored).

*Risks:* highest of the three — perturbs the existing element stream and its window, changes
existing test invariants, requires touching the unique constraint if rows share a sequence slot, and
multiplies element rows by ~2× (99 vs 45 for one table).

---

## 8. Option B — Compact Table Evidence

**Keep the aggregate `table` node; create a compact retrieval representation** of only the relevant
rows/cells, keeping original provenance.

*How relevance is determined (proposed, deterministic, no new scoring model):*
1. **Gate (dimension match):** the question's meaningful terms (`graph/service.py::terms_from_question`)
   must match the table's **header** cells (the dimension the table describes). For Q2, "calibration
   interval" matches the `Calibration Interval` header → gate open. For Q3, no header matches → gate
   closed, path inert.
2. **Row selection (pivot match):** among the gated table's rows, select rows whose row-key/first
   cell matches question terms (`Lidar Array LR-9` for "lidar array"); if no row key matches, select
   the rows whose cells contain the matched terms; ordering is `(matched-term count desc,
   row_index asc)` — deterministic, and bounded by `TABLE_EVIDENCE_MAX_ROWS` (suggest 2).
3. **Unit form:** prefer the **cell fact** `"{header[c]} = {cell}"` when exactly one (gated row,
   matched column) pair is identified (≈4–10 tokens); otherwise the **header-repeated row**
   (36–48 tokens).

*How provenance is preserved:* every unit records `document_id`, `table_element_id`, `row_index`,
the 1-based `column_index`, the verbatim header and cell strings, `page_number`,
`heading_path`/`section` of the table, and `parser_version`. The unit's `content` is a deterministic
*serialization of verbatim cells* (`{header} = {cell}` or `header | row`), never paraphrase,
normalization, unit conversion or inference.

*How it avoids fabricated facts:* the payload contains only cell strings that exist in the stored
table; the derivation is a labelled join of two stored cells; no value is computed, rounded or
"corrected". If a value cell is empty the row is unusable and is dropped (never filled). If the gate
or the row selection yields nothing, **no** table evidence is added — the path degrades to today's
behaviour and says so in provenance.

*Does it require new persisted representations?* Yes, minimally and additively: a dedicated row
store (§11/§12) so rows do **not** enter `document_structure_elements` and therefore do **not**
renumber the element stream. Alternatively rows could be derived at query time from the aggregate
element's content (its `" | "`-serialized lines are lossless for the demo table), which needs *no*
schema change at all but relies on re-splitting serialized text; that is the fallback shape if the
schema must not change in the same sprint.

*Risks:* the gate is term-based, so paraphrase recall is imperfect (a question that never names a
header word will not surface the table); mitigated by measuring the gate on the real corpus before
flipping any default, and by the fact that a closed gate is a *no-op*, never a wrong answer.

---

## 9. Option C — Chunk ↔ Structure Linkage

**Create explicit linkage between semantic chunks and structure elements** so a retrieved chunk
deterministically exposes its corresponding section/table evidence.

*Mapping strategy (measured feasibility on the real document, existing data only):*
* content-span containment: `element.content.strip()[:60] in chunk.content` — resolves
  **45/45** structure elements to ≥1 chunk (9 ambiguous, i.e. >1 matching chunk), and maps the
  **table element unambiguously to chunk 34**;
* page + heading-text signals as tie-breakers (24/46 chunks retain heading text in their content per
  the existing reachability audit);
* with the structure chunker (`chunk-v2-structure-tokens`) the mapping is exact — `ChunkMeta`
  already computes `source_indices` / `source_start` / `source_end`, but these are process-local and
  **not persisted**, so exactness would require either persisting spans or accepting content-span
  matching for legacy chunks.

*Parser requirements:* none for content-span linking; exact spans require the structure chunker.

*Schema impact:* none if linkage is derived by content-span at retrieval/insertion time; a
`table_row_id` / `structure_element_id` column on `document_chunks` (or a link table) if linkage must
be persisted. Persisting linkage is attractive but only exact for structure-v2 chunks.

*Retrieval behaviour:* a retrieved chunk can surface (a) its section's structure element and
(b) that section's table rows. **Measured caveat:** for Q2 the table's own chunk (34, 234 tokens) is
*not* in the top-5, so linkage from the retrieved chunks does **not** reach the table by itself. The
useful linkage is transitive: rank-1 chunk 32 belongs to section `5. Maintenance Schedule`, and the
table element's `parent_id` is that same section element — so `chunk → section → table children →
rows` *does* reach the table for Q2. For this legacy-chunked document that hop must be content-based
(the chunk's `section` column is NULL), which is feasible but fragile compared with Option B's
header gate.

*Context construction:* unchanged — linkage decides *which* row units exist, the budget policy (§16)
decides whether they fit.

*Multi-page / multi-table handling:* linkage is per document and per `parent_id` subtree;
`page_number` on both sides disambiguates tables that span pages; tables with no chunk (e.g. a table
whose text was fully absorbed into a neighbouring block) simply produce no linkage and are still
reachable through the structure-element path and Option B's row store.

*Value:* primarily **provenance and reachability explanation** ("this row came from the table in the
section your top chunk came from"), secondarily a ranking signal. Alone it does not satisfy the
invariant for Q2.

---

## 10. Comparative Decision Matrix

| Criterion | A — Row/Cell graph in element stream | B — Compact table evidence | C — Chunk↔structure linkage | Recommended hybrid (A-granularity + B-serialization + C-provenance, dedicated store) |
| --- | --- | --- | --- | --- |
| Makes a table unit fit the 362-token budget | yes (rows/cells small) | **yes** (36–48 or 4–10) | n/a (does not change size) | **yes** |
| Keeps the aggregate blocker (C2) solved | yes | yes | no | yes |
| Element-stream perturbation | **high** (45 → 99 elements, window shifts) | none | none | none |
| Schema change required | constraint/semantics change | new additive table | none (derived) or additive link table | **one additive table** |
| RRF weight change | not required | not required | not required | not required |
| Can be inert for non-table questions | only with a gate | **yes (gate)** | yes (no linkage hit) | **yes (gate)** |
| Provenance honesty | native | explicit row/col ids | good with exact spans | explicit row/col ids + element id |
| Determinism | needs a second ordering key | `(matched terms desc, row_index, column_index)` | content-span ties | same as B |
| Regression risk (Q3) | high (rows present for power questions) | low (gate closed → byte-identical) | low | **lowest** |
| Migration/rollback cost | medium-high (reprocess + re-verify) | low (reprocess to backfill) | low | low |
| Meets "no fabricated evidence" | yes | yes (verbatim cells only) | yes | yes |

---

## 11. Recommended Architecture

**Hybrid: compact, header-repeated row evidence in a dedicated store, linked by provenance, surfaced
through a query-gated additive evidence band.**

```
question ──▶ terms_from_question (existing)
                    │
                    ├─ (gate) header/cell term match against document_table_rows  ── no match ─▶ path inert
                    │                                                                        (context byte-identical)
                    ▼ match
        select ≤ TABLE_EVIDENCE_MAX_ROWS rows  (deterministic: matched terms desc, row_index asc)
                    │
                    ▼
        serialize verbatim cells:  "Header | row"   or   "Header[c] = cell"   (never paraphrased)
                    │
                    ▼
   build_qa_context(chunks, question, table_evidence=[...], table_reserve_tokens=…)
        band order:  ranked chunks (unchanged)  →  table evidence (whole, never truncated)
                     →  unranked structure-element tail (document order, drops first)
                    │
                    ▼
   SourceRef(evidence_kind="table_row"|"table_cell", retrieval_path="structural",
             score=0.0, fusion_score=None, page, section, heading_path,
             + tableElementId / rowIndex / columnIndex provenance)
```

**Why this satisfies the invariant** ("when a query requires information contained in a table, the
relevant table evidence can reach the QA model within the existing context budget without
displacing essential semantic evidence or introducing fabricated/truncated evidence"):

* **Within budget:** measured 36–48-token row units (or 4–10-token cell facts) against a measured
  ≤ 96-token residual; the aggregate 230-token blob is never used as a retrieval unit.
* **Without displacing semantic evidence:** the ranked chunk list is emitted first, in order, with
  identical inclusion (asserted in tests and visible in `semanticSourceCount` / `hybridSourceCount`);
  only unranked structure-element tail entries are dropped, and each drop is reported.
* **Without truncation:** table units must fit whole; the rank-1-only truncation rule is unchanged
  and no table unit is ever truncated.
* **Without fabrication:** payloads are verbatim cell strings joined by a deterministic label;
  empty cells drop the row; a closed gate adds nothing.
* **Without the Q3 regression:** for any question that does not match the table's header terms the
  path is inert, so the QA context string is identical to today's; the Q3 question is a hard test.
* **Without special-casing the demo:** the gate and row selection use only generic signals (question
  terms, header cells, row-key cells, row indices). No document id, page, sequence number or
  document-specific string appears in production logic.

**Fallback shape if the schema must stay frozen in the same sprint:** derive row units at query time
by splitting the aggregate element's `"\n"`/`" | "` serialization (the aggregate content is a
lossless rendering of `table_data` for this document). This is strictly worse (re-parsing text
rather than reading structured rows, and it cannot expose `column_index` reliably when a cell itself
contains `|`) but needs **no** migration. It should be treated as an explicitly-marked temporary
step, not the target architecture.

---

## 12. Required Schema Changes

Owner: **DATABASE_AGENT.** One additive migration, next in the linear chain (`007_…` after the
current head `006_add_structure_elements`). No existing column, constraint or row is modified.

New table `document_table_rows` (proposed):

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID PK` | `uuid4`, database-generated |
| `document_id` | `UUID FK documents.id ON DELETE CASCADE`, indexed | ownership chain unchanged: `row → document → user` |
| `table_element_id` | `UUID FK document_structure_elements.id ON DELETE CASCADE`, indexed | links to the aggregate `table` element (Option C provenance) |
| `page_number` | `INTEGER NULL` | copied from the table element (page 4 for the demo table) |
| `heading_path` | `JSON NULL` | copied from the table element (`["5. Maintenance Schedule"]`) |
| `section` | `VARCHAR(512) NULL` | `heading_path[-1]` |
| `row_index` | `INTEGER NOT NULL` | 0-based row index **including** the header row |
| `is_header` | `BOOLEAN NOT NULL DEFAULT false` | exactly one header row per table today; no header invented if the extractor produced none |
| `cells` | `JSON NOT NULL` | verbatim cell strings, in column order |
| `content` | `TEXT NOT NULL` | deterministic serialization: header-repeated row (`"h1 | h2\nc1 | c2"`) or labelled cell fact |
| `header_repeated` | `BOOLEAN NOT NULL DEFAULT true` | provenance: whether `content` embeds the header |
| `token_count` | `INTEGER NULL` | measured with the project tokenizer, recorded (never assumed) |
| `parser_version` | `VARCHAR(64) NULL` | ingestion provenance |
| `created_at` | `TIMESTAMP TZ` | `server_default=now()` |

Constraints/indexes: `UniqueConstraint(document_id, table_element_id, row_index)`; index
`(document_id, table_element_id, row_index)`; optional FK-integrity check that
`table_element_id.element_type = 'table'` is enforced in the ingestion code (PostgreSQL cannot
express it as a simple check).

**Why a separate table rather than rows in `document_structure_elements`:** it preserves
`UniqueConstraint(document_id, sequence_index)` semantics, keeps the element count (45) and
document order identical, keeps the existing first-20 augmentation window byte-identical, and needs
no change to any existing column. Option A's granularity is retained; only its storage location
differs.

*Optional (only if linkage must be persisted):* add nullable
`structure_element_id UUID` to `document_chunks`, or a `document_chunk_structure_links` table. Defer
until the linkage is exact (structure-v2 chunks).

---

## 13. Required Parser Changes

Owner: **BACKEND_AGENT** (`backend/documents/**`), coordinated with DATABASE_AGENT on the model.

1. `documents/processing.py` — no behaviour change; `_pdf_table_element` already provides
   `table_data` per table, with the table's own `page`, `heading_path` and `section` resolved at its
   real position in the page's reading order.
2. `documents/parser.py` — extend the **public contract** so `ParsedElement` can carry
   `table_data` (rows), or add a sibling `ParsedTable`/row view. Rules to preserve: `parsed.elements`
   stays a one-to-one, ordered view of the extractor output (`sequence_index` unchanged, contiguous,
   no synthesis); `EMITTED_ELEMENT_TYPES` stays `{section, paragraph, table, text_block}` unless
   Option A is explicitly adopted later; `ELEMENT_TYPE_MAP` keeps raising on unmapped types.
3. New deterministic row projection (e.g. `documents/tables.py::compact_table_rows(parsed_element,
   *, header_repeated=True, count_tokens=…)`) producing, for each row: `row_index`, `is_header`,
   verbatim `cells`, `content` (header-repeated serialization or labelled cell fact), `token_count`
   and the parent table element identity. It must be pure, deterministic and free of DB access —
   mirroring the existing `parser.py` module boundary.
4. `documents/structure.py` (or a sibling writer) — persist the projection into
   `document_table_rows` inside the existing `SAVEPOINT`/replace transaction, so a reprocess
   atomically replaces rows with the structure elements they belong to. Failure to persist must
   follow the existing pipeline rule: the document is **not** marked READY (no silent degradation).
5. Do **not** change `config.chunker_version` (stays `legacy`), `CHUNK_*` budgets, or chunk content
   in this sprint. Row evidence is added *alongside* chunks, not instead of them.

---

## 14. Required Retrieval Changes

Owner: **AI_AGENT** (`backend/graph/**` except `models.py`, `backend/chat/**` except `models.py`).

1. `graph/service.py` — add bounded, deterministic row retrieval scoped by `user_id` at the
   database (same join-to-`documents` pattern as `expand_element_seeds`):
   `table_rows_for_documents(db, user_id, document_ids, terms, *, max_rows, max_tables)`
   and, if the linking variant is used, `section_ids_for_chunks(...)`. No new scoring model: the
   ordering key is `(matched-term count DESC, row_index ASC)` with a documented tie-break.
2. `chat/rag.py` — add the **gate + selection** step:
   * reuse `terms_from_question` (no new tokenizer, no new embedding);
   * gate = at least one meaningful question term matches a stored table **header** cell (exact
     case-insensitive term match, plus the existing substring/plural handling used by
     `find_element_seed_matches`); if the gate is closed, return `[]` and do nothing else;
   * selection = rows whose row key or cells match question terms, bounded by
     `TABLE_EVIDENCE_MAX_ROWS` (suggest 2) and `TABLE_EVIDENCE_MAX_TABLES` (suggest 2);
   * serialization per row = header-repeated row, or labelled cell fact when a single
     (row, matched column) pair is identified;
   * hard per-item cap `TABLE_EVIDENCE_MAX_TOKENS` (suggest 64) — an over-cap unit is **not**
     truncated, the row is skipped and recorded as omitted.
3. `chat/rag.py::retrieve_dual_path` — **unchanged** (no new stream enters RRF). Table units are
   never RRF-ranked in this design, so `RRF_K=60`, `RRF_SEMANTIC_WEIGHT=0.70`,
   `RRF_STRUCTURAL_WEIGHT=0.30`, `STRUCTURAL_CANDIDATE_LIMIT=15` and
   `STRUCTURAL_ELEMENT_CANDIDATE_LIMIT=10` all stay as they are.
4. Kill switch — mirror the existing `DOCUMIND_DUAL_PATH_RAG` convention with
   `DOCUMIND_TABLE_EVIDENCE` (default **off** until Phase 4 measurement passes, then flipped as a
   documented decision per `ARCHITECTURE.md` §16).
5. `brain/adapters.py::_augment_with_structure` — extend the *signature* additively to accept the
   already-computed table units (`_augment_with_structure(db, chunks, *, table_evidence=())`) and
   keep the existing document-order element behaviour **exactly** as it is today for the element
   stream. Do not reintroduce query-dependent element re-ordering (the reverted change).
6. Document isolation — every row query joins `documents` on `user_id`; rows carry
   `document_id` and are only ever fetched for documents that the caller's own retrieval returned.
   Determinism — ordering is fully specified by `(matched terms, row_index, id)`; no set iteration
   order, no timestamps, no randomness.

---

## 15. Required Evidence/Fusion Changes

Owner: **AI_AGENT.**

* **New evidence kind:** `evidence_kind = "table_row"` (and `"table_cell"` for the labelled-fact
  form), distinct from `"chunk"` and `"structure_element"`, so the Reliability Center can separate
  it. `retrieval_path` stays `"structural"` (it is graph/document-structure evidence, not a
  similarity hit); `score = 0.0` and `fusion_score = None` (no similarity, no RRF contribution
  exists — reporting one would be fabrication).
* **New optional provenance fields** on the evidence object and the API: `tableElementId`,
  `rowIndex`, `columnIndex` (nullable), `headerRepeated`, `tokenCount`. All optional so existing
  clients keep working.
* `graph/evidence.py::fuse_evidence` — **unchanged**, and table units do **not** pass through it:
  `fuse_evidence`'s contract is single-document, dedup-by-identity and stream-bounded; inserting a
  third stream there would change the fusion contract. Table units are a separate, explicitly
  bounded band carried next to the fused evidence (the same architectural pattern Feature #13 used
  for the element stream: "a separate stream, per the Feature #12 contract", appended after fusion).
* Dedup: a table unit is deduplicated against the fused evidence by `table_element_id + row_index`,
  and against itself by identity; if the aggregate `table` element is already present as
  `structure_element` evidence, the row unit is still emitted (different identity, different
  granularity) but the Reliability Center must show both without double-counting the document.
* Counting: extend the existing per-source counters (`semanticSourceCount`, `structuralSourceCount`,
  `structuralElementSourceCount`, `hybridSourceCount`) with `tableRowSourceCount` (and
  `tableCellSourceCount` if both forms exist). All counts must partition `sources` exactly, as the
  existing counters do.

---

## 16. Required QA Context Changes

Owner: **AI_AGENT** (`backend/chat/rag.py::build_qa_context`).

Minimal, additive change that preserves every existing guarantee:

1. New optional parameters: `table_evidence: Sequence[SourceChunk] = ()` and
   `table_reserve_tokens: int | None = None` (bounded by the caller, suggested cap
   `min(96, budget // 4)`).
2. **Band order:** ranked `chunks` (unchanged order, unchanged inclusion) → table evidence units
   (each must fit **whole**) → the remaining `chunks` tail (the existing unranked structure-element
   entries, in their existing document order).
   In practice: iterate the ranked chunks first exactly as today; then attempt the table units; then
   continue the remaining chunks. Because table units are checked *after* the ranked chunks and
   *before* the tail elements, dropping tail entries is the only way the reservation is satisfied.
3. **Reservation semantics:** the reservation is a *priority*, not a budget increase. The budget is
   still `model_window − question_overhead − QA_TOKEN_SAFETY_MARGIN` (measured 362 for Q2) — never
   raised. If the units do not fit even after the tail is exhausted, they are omitted and reported;
   they are never truncated, and a ranked chunk is **never** dropped to make room.
4. **Truncation rule unchanged:** only the existing rank-1 item may be truncated. Table units are
   exempt from truncation by design (all-or-nothing).
5. **Reporting:** extend `ContextPack` participation so that `included_ids` contains table-unit ids
   when included and `omitted_ids` contains them when not; the Brain already restricts reported
   sources to `included_ids`, so `AskResponse.sources` stays truthful with no new mechanism.
6. **Inertness guarantee:** with no gate match, `table_evidence` is empty, `table_reserve_tokens`
   is 0, and `build_qa_context` returns a `ContextPack` **identical** to today's for the same
   inputs. This is the property that makes the Q3 regression impossible and is asserted directly in
   tests.
7. **Implementation note:** the three bands are already distinguishable inside the flat list the
   Brain passes down — the ranked chunks have `retrieval_path` `semantic`/`hybrid`, the table units
   carry `evidence_kind` `table_row`/`table_cell`, and the document-order element tail carries
   `evidence_kind` `structure_element`. So the band order can be implemented either with the new
   optional parameters above or by partitioning on `evidence_kind` inside the context adapter;
   either way the band order, the reservation and the all-or-nothing rule are the contract.

---

## 17. Reliability Center Changes

Owner: **BACKEND_AGENT** (`backend/chat/routes.py`, `backend/reliability/routes.py`) and
**FRONTEND_AGENT** (`src/lib/api.ts`, `src/types/index.ts`, `src/pages/ReliabilityPage.tsx`).
Design intent follows `DESIGN.md` §05 (Evidence UX) and §06 (State Design).

* `AskResponse.sources` / `ReliabilitySourceRef`: add optional `tableElementId`, `rowIndex`,
  `columnIndex`, `headerRepeated`; extend `evidenceKind` with the new values
  (`table_row`, `table_cell`) alongside `chunk` and `structure_element`. All optional → no client
  breakage.
* `ReliabilityQueryData`: add `tableRowSourceCount` (and `tableCellSourceCount` if used) next to
  `structuralElementSourceCount`, derived the same way (partition of `sources`), never recomputed
  from a guess.
* Reliability Center UI: a new evidence-breakdown tile for the table band (count + tokens), a
  `TABLE ROW` badge in the four-way path/badge row, and a provenance sub-line showing
  `page · section · row N · column M (header repeated: yes/no)` plus the verbatim cell values, so a
  user can see exactly which stored cells produced the evidence. The existing static
  "PRODUCTION RRF CONFIG" block stays as-is and must remain labelled as static configuration, not a
  measurement of the query.
* The aggregate table element remains visible as its own `structure_element` evidence with its own
  token cost, so the aggregate-vs-row story is auditable in the UI.

---

## 18. Migration Strategy

* **Schema:** one additive migration (`007_…`) creating `document_table_rows`; no column, constraint
  or row of any existing table is altered; schema history stays a single linear chain
  (`alembic heads` must show exactly one head). Never `create_all` for application schema, never
  downgrade/drop a live database without explicit permission.
* **Backfill:** rows are produced at ingestion, so existing documents need **reprocessing** (the
  content-hash dedup means re-uploading the same PDF returns the existing READY document without
  reprocessing — the operator must use the existing explicit reprocess path, or accept that
  table-evidence coverage starts with newly processed documents). Absent rows are simply "no table
  evidence", which is the same as a closed gate: no fabrication, no silently wrong behaviour.
* **No chunker flip:** `config.chunker_version` remains `legacy`. Switching the production chunker to
  `structure-v2` changes every chunk and embedding of newly ingested documents and is a separate,
  measured decision — explicitly out of scope here.
* **No element-stream change:** `document_structure_elements` keeps its rows, ordering,
  `sequence_index` values and the existing first-20 augmentation behaviour. This is what makes the
  migration low-risk: nothing that today's retrieval depends on is touched.
* **Rollback:** the feature is inert without its kill switch, so rollback is
  `DOCUMIND_TABLE_EVIDENCE=0` (behaviour returns to today's), plus optionally
  `alembic downgrade -1` to drop the new table (permission-gated; the table holds no production
  truth).
* **Provenance/audit:** the migration must be recorded in the DB-owned migration chain and reflected
  in `ARCHITECTURE.md` (structure/evidence section) when implemented — per `ARCHITECTURE.md` §16
  ("update architecture documentation").

---

## 19. Testing Strategy

Owner: **TEST_AGENT** (`backend/tests/**`). Research measurement belongs to EVALUATION_AGENT and is
not pytest. A green SQLite suite does not prove pgvector, the real model or migrations.

**Unit — gating and selection (no DB, pure functions):**
1. header-match gate opens for a question naming a header dimension, closes for one that names
   none (must include the exact Q3 question shape as a *closed* case);
2. row selection is deterministic and bounded: `(matched terms desc, row_index asc)`, ≤
   `TABLE_EVIDENCE_MAX_ROWS`, ties broken by row index then id;
3. serialization fidelity: `content` is composed only of verbatim cells from the stored row;
   an empty cell drops the row; a cell containing `|` does not corrupt the header-repeated form;
4. token cap: an over-cap row is skipped (never truncated) and reported;
5. no demo vocabulary: assert the production modules contain none of the demo strings
   (`maintenance schedule`, `lidar`, `reference rig`, `primary battery rail`, `solar bus`,
   the document id, `sequence 34`, `page 4`).

**Unit — QA context policy:**
6. with `table_evidence=()` and no reservation, `build_qa_context` output is byte-identical to the
   current implementation for the same inputs (regression guard for inertness);
7. with a table unit present, ranked chunks keep identical inclusion and order, and only tail
   structure-element entries are dropped; `included_ids`/`omitted_ids` account for every input id;
8. table units are never truncated, and a rank-1 chunk is still the only truncatable item;
9. budget is never exceeded: `used_tokens <= budget_tokens` for adversarial inputs (a table unit
   larger than the whole budget).

**Unit — RRF/fusion invariants (unchanged):**
10. `RRF_K == 60`, `RRF_SEMANTIC_WEIGHT == 0.70`, `RRF_STRUCTURAL_WEIGHT == 0.30`;
11. `fuse_dual_path` output for a fixed input is unchanged, including the hybrid marking and the
    `fusion_score` arithmetic.

**Integration — isolation, determinism, provenance (SQLite fixtures):**
12. document isolation: another user's table rows are never returned; rows from a document that was
    not retrieved are never returned;
13. cross-document saturation: with `max_documents` tables present, selection never mixes documents
    and stays bounded;
14. provenance completeness: every table unit carries `document_id`, `table_element_id`,
    `row_index`, `page`, `section`, `heading_path`, `headerRepeated`, `token_count`;
15. adapter wiring: `retrieval_adapter` passes table units through and the Brain's source
    restriction admits them only when included;
16. inertness: with the kill switch off, and with the gate closed, the produced `ContextPack` and
    the reported `sources` are identical to the pre-change behaviour.

**End-to-end / live (real stack, real model):**
17. **Q3 regression gate (hard):** `According to Sensor Calibration and Power Management, which
    power rail supplies the inertial measurement unit?` must answer `battery rail` (not
    `solar bus`), with the table band reported as *not* engaged;
18. Q1/Q2/Q4/Q5 behaviour: Q1 `reference rig`, Q2 `every 250 operating hours`, Q4 `four minutes`,
    Q5 `12 metres per second` — with Q2 additionally required to show a `table_row` source whose
    `page`/`section` provenance is truthful;
19. no fabricated values: every table-unit content string must be reconstructible from the stored
    row cells (assert by substring, not by exact equality with a hard-coded expected value);
20. degraded states: document with no table rows, table with an empty value cell, table larger than
    `TABLE_EVIDENCE_MAX_TOKENS`, QA model unavailable → honest omission, never a fabricated source.

**Evaluation (research, EVALUATION_AGENT):** a table-targeted slice (questions whose answer lives in
a table) measured as explicit variants (semantic-only, dual-path today, dual-path + compact table
evidence, dual-path + compact table evidence + linkage) with Recall@K, evidence coverage, grounding,
answer accuracy and per-question regression diff against the frozen baseline. No improvement may be
claimed for any variant that has not been measured.

---

## 20. Teacher Demo Acceptance Criteria

The teacher-demo question must eventually be answered **from table evidence**, not merely from the
paragraph that repeats the fact:

> What calibration interval does the Maintenance Schedule give for the lidar array?

Acceptance (to be verified against the live `POST /api/chat/ask` response, not a harness):

| # | Criterion | Expected |
| --- | --- | --- |
| 1 | table row evidence is a retrieval candidate | yes (today: the aggregate element is candidate 6 of 10) |
| 2 | row evidence reaches the **supplied** QA evidence | yes — must appear in `AskResponse.sources` (which is restricted to `ContextPack.included_ids`) |
| 3 | `evidenceKind` | `table_row` (or `table_cell` for the labelled-fact form) — never `chunk` |
| 4 | provenance is truthful | `page = 4`, `section = "5. Maintenance Schedule"`, `headingPath = ["5. Maintenance Schedule"]`, `rowIndex` = the real row index of `Lidar Array LR-9` (row 1, 0-based, including the header), `headerRepeated = true`, `tableElementId = 95bd5383-db27-48f6-a001-0ba57094ad4a` |
| 5 | evidence content is verbatim | contains the stored header `Calibration Interval` and the stored cell `250 h`; no invented text, no unit conversion, no rounding |
| 6 | no fabricated scores | `score = 0.0`, `fusionScore = null` (no similarity exists for table evidence) |
| 7 | answer grounded in the row | the answer states the 250-operating-hour interval and `factualGrounded = true`; the row may be *co-present* with the paragraph, but the table row must be in the supplied set |
| 8 | semantic evidence not displaced | the five ranked chunks remain included, in the same order (`semanticSourceCount`/`hybridSourceCount` unchanged) |
| 9 | budget respected | `contextUsedTokens <= contextBudgetTokens` (362 for this question), no increase to the 384-token model window |
| 10 | honest reporting | if the row cannot fit, it is omitted **and** counted in `omittedSourceCount`; nothing is truncated into the context |
| 11 | no demo special-casing | the behaviour is produced by generic header/row matching; the production diff contains no document id, page, sequence number or demo string |

**Explicit non-claims:** this document does not claim the table reaches QA today; it does not claim
the teacher-demo issue is fixed; it does not claim any architecture is implemented; and it does not
claim that adding table evidence will improve answers — that requires the measurement in §19.

---

## 21. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Gate is too permissive → table rows injected for questions the table does not answer (Q3-class regression) | medium | high | header-dimension gate (not "any cell term"); Q3 as a hard closed-gate test; `/api/chat/ask` diffs on all five demo questions before/after |
| Gate is too strict → table evidence never fires | medium | medium | measure gate recall on a table-targeted evaluation slice before flipping the default; keep the row store and selection usable by future signals (linkage, query classification) without a redesign |
| Extractive model prefers a neighbouring table row (e.g. `Auxiliary Solar Bus` next to `Primary Battery Rail`) | medium | high | prefer the smallest faithful unit (labelled cell fact) when a single (row, column) pair matches; cap rows at 2; never include the whole table; regression diff per question |
| Table unit chosen but does not fit → silent loss | medium | medium | explicit `omitted_ids` accounting (already surfaced as `omittedSourceCount`), plus a unit test that asserts omission is reported |
| Legacy chunk metadata (45/45 NULL) makes linkage-based reasoning fragile | high | medium | Option B does not depend on chunk metadata; linkage is optional/provenance-only in Phase 1–4; exact spans only with `structure-v2` (separate decision) |
| Reprocessing requirement leaves existing documents without rows | high (short term) | low | closed gate = inert, never wrong; document coverage grows with new ingests; an operator-approved reprocess run is optional |
| New table grows unbounded on table-heavy documents | low | medium | rows are bounded by the document's own table cells; index `(document_id, table_element_id, row_index)`; selection is bounded by `max_tables`/`max_rows` |
| Provenance double-counting (fused element + row of the same table) | medium | low | distinct `evidenceKind` values, `tableElementId + rowIndex` dedup key, and explicit UI wording |
| Migration/rollback surprises on the live DB | low | high | additive-only migration, single linear head, kill switch default-off, no existing column touched, downgrade permission-gated |
| Scope creep into chunker/embedding changes | medium | high | `chunker_version` stays `legacy`; changing it is a separate measured decision (it re-chunks and re-embeds everything) |

---

## 22. Exact Implementation Sprint Order

**Phase 1 — Contract, measurement freeze and kill switch scaffolding**
* *Owner:* COORDINATOR (approval) + EVALUATION_AGENT (measurement) + VERIFIER (baseline).
* *Files:* `backend/evaluation/reports/table_evidence_architecture.md` (this document);
  an optional frozen baseline artifact under `backend/evaluation/reports/` recording the current
  Q1–Q5 answers/confidences, supplied counts and the `document_structure_elements` /
  `document_table_rows` counts.
* *Dependencies:* none.
* *Verification:* re-run the read-only audit (element/chunk counts, candidate position, live Q1–Q5);
  `alembic heads` shows one head (= `006`); RRF constants read as 0.70/0.30/60.
* *Rollback:* delete the added artifact; no production impact.

**Phase 2 — Row evidence persistence (schema + parser projection + ingestion)**
* *Owner:* DATABASE_AGENT (migration + `documents/models.py`) with BACKEND_AGENT (`documents/parser.py`,
  new `documents/tables.py` projection, `documents/structure.py` / ingestion wiring);
  TEST_AGENT (tests).
* *Files:* `backend/migrations/versions/007_add_table_rows.py`,
  `backend/documents/models.py`, `backend/documents/parser.py`, `backend/documents/tables.py` (new),
  `backend/documents/structure.py`, `backend/documents/routes.py` (persist rows in the existing
  SAVEPOINT; keep "not READY on failure").
* *Dependencies:* Phase 1 approval.
* *Verification:* `alembic heads`/`history` linear; ingest the real PDF into a scratch document and
  assert 9 rows (1 header + 8 body), per-row tokens in the measured 21–48 range, header-repeated
  content, `page = 4`, `heading_path` carried; assert the existing 45 element rows and their
  `sequence_index` values are **unchanged**; unit tests for cell fidelity/empty cells.
* *Rollback:* `alembic downgrade -1` (permission-gated) or leave the table populated but unused (the
  retrieval switch is still off).

**Phase 3 — Retrieval, gate and QA-context band**
* *Owner:* AI_AGENT.
* *Files:* `backend/graph/service.py` (scoped row queries),
  `backend/chat/rag.py` (gate + selection + `build_qa_context` band/reservation + env kill switch),
  `backend/brain/adapters.py` (additive parameter pass-through; **no** change to element selection),
  `backend/brain/types.py` (optional provenance fields), `backend/brain/__init__.py` (counter).
* *Dependencies:* Phase 2 rows present for the test documents.
* *Verification:* §19 unit/integration items 1–16 with the switch **off by default**; explicit
  byte-identical context assertion for the no-gate/switch-off paths; RRF constants test unchanged.
* *Rollback:* `DOCUMIND_TABLE_EVIDENCE=0` (default) → today's behaviour; revert code.

**Phase 4 — Live measurement on the real stack (no default flip yet)**
* *Owner:* EVALUATION_AGENT (measurement) + VERIFIER (independent re-run).
* *Files:* none in production; measurement artifacts under `backend/evaluation/reports/`.
* *Dependencies:* Phase 3 merged with the switch still off; operator-approved reprocess of the demo
  document so its rows exist.
* *Verification:* live `POST /api/chat/ask` for Q1–Q5 with the switch on, versus the frozen Phase 1
  baseline: Q3 must be `battery rail`; Q1/Q4/Q5 unchanged; Q2 must show a `table_row` source in the
  supplied set with truthful provenance; token accounting honest. Recorded, not asserted as an
  improvement.
* *Rollback:* switch off (one env change, no deploy of new code).

**Phase 5 — Reliability Center/API provenance, then the default decision**
* *Owner:* BACKEND_AGENT (routes) + FRONTEND_AGENT (UI) + EVALUATION_AGENT (decision record) +
  COORDINATOR (approval to flip the default).
* *Files:* `backend/chat/routes.py`, `backend/reliability/routes.py`, `src/lib/api.ts`,
  `src/types/index.ts`, `src/pages/ReliabilityPage.tsx`, `ARCHITECTURE.md` (documented change per
  §16).
* *Dependencies:* Phase 4 results.
* *Verification:* `npm run typecheck`, `npm run build`, live payload field-name match, tile/badge
  values re-derived from the real JSON; only then flip `DOCUMIND_TABLE_EVIDENCE` default and re-run
  the end-to-end gate (Q3 + all five questions).
* *Rollback:* revert the env default (and the UI commit); the API fields are additive and optional.

**Phase 6 (optional, separate decision) — Option A element-tree form and exact links**
* Only if the dedicated row store proves insufficient: emit `table_row`/`table_cell` into
  `document_structure_elements` (requires the sequence/unique-constraint redesign and re-verifying
  the first-20 window) and/or persist exact chunk spans by adopting `chunker_version=structure-v2`.
  *Owner:* DATABASE_AGENT + BACKEND_AGENT + AI_AGENT, with EVALUATION_AGENT measuring the chunker
  change in isolation. Not part of Phases 1–5.

---

## 23. What MUST NOT be changed

1. **RRF**: `RRF_K = 60`, `RRF_SEMANTIC_WEIGHT = 0.70`, `RRF_STRUCTURAL_WEIGHT = 0.30` — no
   0.50/0.50, no fitted weights, no weight change in this work.
2. **QA model**: no model swap, no retrain, no change to `_DEFAULT_MAX_INPUT_LENGTH` / the 384-token
   window, no external fallback model.
3. **Budget behaviour**: no blind budget increase, no truncation of arbitrary evidence; rank-1-only
   truncation stays; table units are all-or-nothing.
4. **Existing element stream**: the document-order "first 20" augmentation selection and the 45
   persisted elements of the demo document stay byte-identical, including `sequence_index` values
   and the absence of `table_row`/`table_cell` rows in `document_structure_elements`.
5. **Chunker default**: `config.chunker_version` stays `legacy`; `CHUNK_*` budgets unchanged.
6. **Semantic retrieval**: no change to `retrieve_chunks`, the embedding model, or pgvector usage.
7. **Isolation and authorization**: every new query is scoped to the authenticated `user_id` and to
   documents the caller's own retrieval returned; no client-supplied ownership.
8. **Determinism**: total ordering everywhere (`(matched terms, row_index, id)`), no randomness, no
   timestamps in ordering, no set iteration.
9. **No fabricated evidence**: no similarity for table evidence, no computed/normalized values,
   verbatim cells only, omissions reported.
10. **No demo special-casing**: no document id, file name, page, sequence number, or demo string in
    production logic.
11. **No weakening of tests** to make anything pass, and no production imports from tests.
12. **`.env`, model artifacts, `venv`, `node_modules`, `dist`, uploads**: untouched; no package
    installs.
13. **Evaluation artifacts**: existing reports/corpora are not rewritten; new measurements are added
    as new artifacts.

---

## 24. Final Recommendation

Adopt the **hybrid** design in §11, implemented in the Phase 1–5 order of §22, and treat
`DOCUMIND_TABLE_EVIDENCE` as default-off until Phase 4 measurement demonstrates, on the real
production stack, that (a) the teacher-demo question is answered with a `table_row` source in the
supplied evidence, (b) Q1/Q2/Q4/Q5 behaviour is unchanged or improved, and (c) the Q3 question still
answers `battery rail`.

Rationale in one line each:

* **Granularity beats ordering** — 36–48-token header-repeated rows (or 4–10-token labelled cell
  facts) fit the measured ≤ 96-token residual; the 230-token aggregate never can
  (`266 + 230 = 496 > 362`).
* **Additive beats re-ranked** — table evidence enters as its own bounded band after the ranked
  chunks and before the unranked tail; ranked chunks keep identical inclusion and order, so semantic
  evidence cannot be displaced.
* **Gated beats always-on** — a header-dimension gate makes the path inert for questions the table
  does not answer, which is what makes the Q3 regression structurally impossible rather than merely
  tested for.
* **A dedicated store beats renumbering the element tree** — equal granularity benefit, zero
  perturbation of the existing element stream, its first-20 window, and the tests that assert them.
* **Measured beats claimed** — nothing is declared an improvement until the evaluation in §19 and
  the live gate in §20 produce it.

**Honest current status:** the teacher-demo table does **not** reach the QA model today; the
aggregate-element approaches are **BLOCKED** by the token arithmetic and by the rank-1-only
truncation rule; this document is the architecture required to remove that blocker, and no part of
it is implemented.

---

### Appendix A — Measured baseline (2026-10-06, read-only)

* Document: `ada99ed5-e95a-439f-8700-261535b9dfa5` (6 pages, legacy chunker
  `chunk-v1-legacy-chars-1000-200`), 45 chunks, 45 structure elements (9 `section`, 35 `paragraph`,
  1 `table`), `document_graph_edges = 238`, `document_structure_edges = 0`, `bbox_*` NULL.
* Aggregate table element: id `95bd5383-db27-48f6-a001-0ba57094ad4a`, `sequence_index = 34`,
  `page_number = 4`, `heading_path = ["5. Maintenance Schedule"]`, `parent_id` = the section element
  at sequence 31, content 230 tokens; extractor `table_data` = 9 rows × 5 columns, header 15 tokens,
  body rows 21–33 tokens, header+row 36–48 tokens, labelled cell fact ≈ 4–10 tokens.
* Table row for the demo question: `Lidar Array LR-9 | 250 h | 0-80 m | > 2.5 mm error |
  Recalibrate on reference rig`.
* Chunk stream: chunk 32 (65 tokens, page 4) contains the paragraph that repeats the fact
  (`… The lidar array requires recalibration every 250 operating hours. …`); chunk 34 (234 tokens,
  page 4) contains the table serialization; the table element maps unambiguously to chunk 34 by
  content span.
* Q2 live: `retrieve_structural_element_candidates` → 10 candidates, table at position 6;
  `retrieve_dual_path(top_k=5)` → 5 chunks, no table; `_augment_with_structure` → 25 stream entries
  (20 elements, table absent); `build_qa_context` → budget 362, used 359, supplied 13
  (5 chunks = 266 tokens, 8 elements = 93 tokens), omitted 12, retrieved 25; answer
  `'every 250 operating hours'`, confidence 0.0653, `factualGrounded = true`; answer span in chunk
  `0096e99e…` (kind `chunk`, path `hybrid`, page 4).
* Q1 `'reference rig'` 0.1286 · Q2 `'every 250 operating hours'` 0.0653 · Q3 `'battery rail'` 0.0521 ·
  Q4 `'four minutes'` 0.8475 · Q5 `'12 metres per second'` 0.5388; supplied counts 15 / 13 / 16 / 13 /
  16; all `factualGrounded = true`; single document each.
* Environment: QA model available and local; PostgreSQL 18.6 with pgvector 0.8.6 (remote managed
  instance, not localhost); alembic head `006_add_structure_elements`.
