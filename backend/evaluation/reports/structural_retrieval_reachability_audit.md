# Structural Retrieval Reachability Audit

**Audit date:** 2026-10-04  
**Scope:** Read-only architecture audit of the current repository and existing `structure_discriminating_v1` artifacts. No production code, configuration, schema, migrations, models, or embeddings were changed. No new A/B/C/D run was performed.

## 1. Executive summary

DocuMind has two distinct paths that the code calls structural:

1. **Chunk-level dual-path retrieval** is genuinely on the production request path. Semantic pgvector results seed bounded traversal over `document_graph_edges`; the resulting chunk candidates receive real RRF contributions and can change the top-k chunk ordering.
2. **Element-level structure evidence** is persisted for PDFs and appended after retrieval, but it is not ranked. It is fetched as the first 20 structure elements in document order for each returned document, assigned `score=0.0`, then offered to the QA-context builder after all ranked chunks. It can enter QA context if space permits, and is counted as source evidence, but it cannot change retrieval top-k ordering.

For the actual experiment’s 4 generated PDFs, fresh parser extraction returned **46 elements** (19 sections, 19 paragraphs, 8 tables); **43** parser elements had heading paths and **39** had parent references. Table cell text existed in the parser/extractor’s aggregate table content / `table_data` but no parser emitted `table_row` or `table_cell` nodes. The production-default `legacy` chunk builder produced **46 chunks** with document IDs and page values but **0/46** with persisted `section`, `heading_path`, or `element_type` metadata. It does retain heading text in the chunk content for **24/46** chunks, and it embeds the entire table serialization in **8/8** table chunks.

The DB is reachable, but the exact four evaluation PDFs are not present after the experiment’s scoped teardown: their current stored counts are **0 documents, 0 chunks, 0 structure elements, and 0 structure edges**. Current DB-wide counts are 8 documents, 36 chunks, 0 structure elements and 0 structure edges. Consequently, current stored retrieval/fusion/final-ranking counts for those selected PDFs are unavailable (not zero). Existing frozen runner artifacts establish that path-agreement was true on 64/64 answerable questions in C/D, but those artifacts do not retain per-question candidate IDs, structural candidate counts, element counts, or source survival; they cannot substantiate an actual element-stream ranking contribution.

**Answer to the primary question:** the chunk graph is production-retrieval reachable and its chunk candidates can affect ranking. The persisted element graph’s parent tree is reachable through graph-service traversal primitives, but the production retrieval adapter does not call those primitives; its separate element stream is document-wide and post-ranking. The current structure-discriminating experiment therefore tested chunk-level graph RRF under a weak chunk metadata signal, plus unranked structure text in answer context. It did **not** test row/cell-aware element retrieval or element-based ranking. The null result is not a valid test of the full structure-aware hypothesis.

Required research wording: **“No benefit was observed under the current production structural signal/retrieval configuration.”** This is not evidence that structure-aware retrieval in general does not work.

## 2. Research context

The frozen report records the pre-registered 32-question `DISCRIMINATING` population: A/C Recall@5 `0.9531`/`0.9531`, Precision@5 `0.2625`/`0.2625`, A/C nDCG@5 `0.7711`/`0.7661`, Token F1 `0.5413`/`0.5029`, and Answer Accuracy tied at `0.5938`. All 32 tied on Precision@5. The frozen artifacts also report D abstaining on all 8 unsupported questions while A/C answered all 8. These values are historical experiment results; this audit did not rerun them.

The dataset has four programmatically authored but real PDFs and 210 authored conceptual elements. Its authored structure includes 41 conceptual table rows and 123 conceptual table cells; those are annotations/specification nodes, not parser or persisted production elements. The primary experiment record reports 46 ingested chunks. Do not conflate its conceptual 210-node tree with the actual parsed stream of 46 elements.

## 3. End-to-end architecture trace

Production upload/processing (`documents.routes._process_document`) follows:

```text
extract_text(file)
  → resolve settings.chunker_version (default legacy)
  → _build_chunk_objects
  → embed_texts(chunk.content)
  → for PDFs: parse_pdf + replace_document_structure
  → replace_document_graph(chunk views)
  → mark document ready
```

For chat QA (`chat.routes.ask` → `Brain.process`):

```text
classify → deterministic plan → retrieval_adapter
  → retrieve_chunks (pgvector, top_k)
  → retrieve_dual_path
      → retrieve_structural_candidates (section/path matches and semantic chunk seeds)
      → chunk graph expansion (max 2 hops, max 40 visited nodes)
      → fuse_dual_path (RRF, return top_k chunks)
  → _augment_with_structure (first 20 persisted structure elements / document)
  → context_adapter/build_qa_context → QA adapter → Brain evidence collection/gate/response
```

The element rows are appended only after `retrieve_dual_path` returns its already-truncated top-k. No element candidate enters the RRF union or the chunk-level retrieval metric IDs.

### Representative questions

- **Table:** `os_tbl_1`, “What is the flow recorded for Pump A in the Primary Pumps table?” Authored gold is section → table → row → cell. The PDF parser emits the table as one aggregate `table` with serialized rows; it emits no row/cell nodes. The parser’s first Oslo table has no heading context or parent because its table appears before its heading in PDF page extraction order; later two tables are both parented to “Primary Loop > Pump Specifications.”
- **Section:** `fs_sec_1`, “In the Instrument Calibration section, what is the Kestrel frame calibrated against?” Parser emits the heading and paragraph with path `Meridian Field Survey > Instrument Calibration`; the paragraph’s parser parent is the section source ID. Legacy chunk content includes its heading prefix, but its chunk metadata columns remain null.
- **Multi-hop:** `os_mh_1`, “In the Secondary Loop, what is the flow of Pump B?” Authored path is Secondary Loop → Pump Specifications → table row → cell. Parser output contains the Secondary Loop and subsection headings, but the secondary table is extracted with the heading of the immediately preceding primary table region (`Primary Loop > Pump Specifications`); it has no native rows/cells. The parser graph therefore cannot represent the requested authored parent/table/cell chain correctly.

The question texts/paths above were read from the current dataset builder and PDF parser outputs were freshly measured. No synthetic structure nodes were inserted into production.

## 4. Parser inspection

`documents.parser.parse_pdf` delegates to `documents.processing.extract_pdf`, assigns deterministic `source_id`s, maps headings to `section` and text to `text_block` when present, and derives parent source IDs from the current heading path. `extract_pdf` detects PDF headings heuristically by font properties and extracts each detected table into one `ExtractedElement(element_type="table")` with both `table_data: list[list[str]]` and pipe/newline serialized content.

The parser supports the vocabulary `page`, `section`, `paragraph`, `text_block`, `table`, `table_row`, `table_cell`, `figure`, `list`, `list_item`; the PDF extractor emits only `section`, `paragraph`, and `table` on these PDFs. (No `text_block` occurred in the selected four outputs.) It never emits `table_row` or `table_cell`. The extraction stream retains rows/cells as nested in-memory table data, but `ParsedElement` has no table-data field, so the structure persistence boundary drops the nested `table_data` and retains only serialized text on the aggregate table element.

### Fresh parser measurements (four selected PDFs)

| PDF | Pages | Parsed elements | Sections | Paragraphs | Tables | Text blocks | Heading-path populated | Parent-source populated | Extracted table rows/cells |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `atlas_propulsion.pdf` | 3 | 12 | 5 | 5 | 2 | 0 | 11 | 10 | 12 / 36 |
| `field_survey.pdf` | 3 | 14 | 4 | 8 | 2 | 0 | 13 | 12 | 12 / 36 |
| `oslo_reactor.pdf` | 3 | 12 | 7 | 2 | 3 | 0 | 11 | 10 | 18 / 54 |
| `archive_records.pdf` | 2 | 8 | 3 | 4 | 1 | 0 | 8 | 7 | 7 / 21 |
| **Total** | **11** | **46** | **19** | **19** | **8** | **0** | **43** | **39** | **49 / 147** |

`rows/cells` counts above are measured from `ExtractedElement.table_data`, not parser nodes. Authored conceptual row/cell totals are different: 41 rows / 123 cells. The PDF table extractor detected 49 rows / 147 cells; this mismatch is further evidence that synthetic authored structural IDs are not persisted parser identities.

Parser examples from the Oslo PDF:

```text
seq 0: table, page 1, heading_path=None, parent=None (Pump table)
seq 1: section “Oslo Reactor Handbook”
seq 2: section “Primary Loop” parent=section:1:1
seq 3: section “Pump Specifications” parent=section:1:2
seq 4: table (Seal schedule) parent=section:1:3
seq 5: table (Pump A–E, 95 L/s for Pump B) parent=section:1:3
seq 7: section “Secondary Loop” parent=section:1:1
seq 8: section “Pump Specifications” parent=section:2:7
```

Thus for `os_mh_1`, the parser’s detected 95 L/s table is under the primary path (section source `section:1:3`) and the secondary subsection has no table child. This is a PDF extraction/layout/heading-state limitation, before persistence or retrieval.

## 5. Structure persistence inspection

`documents.structure.replace_document_structure` persists each `ParsedElement` one-to-one into `DocumentStructureElement`, including type, sequence, page, heading level/path, content and parser version. It resolves `parent_source_id` to the database UUID `parent_id` inside an atomic nested transaction. The parser-local source ID is discarded after parent resolution. Therefore the freshly measured parser counts would yield 46 persisted elements, 39 parent links and 0 row/cell elements if ingested. This is an inferred persistence count from the one-to-one implementation, **not a current live DB measurement**.

`DocumentStructureElement` has a self-referential `parent_id` and supports row/cell type strings. `DocumentStructureEdge` schema exists, but a read-only code search of `documents/`, `graph/`, `chat/`, and `brain/` found no production construction or query of `DocumentStructureEdge`; `replace_document_structure` only creates element rows/parent links. Element traversal uses `parent_id`, not edge rows.

Current DB was probed read-only: PostgreSQL query succeeded; schema tables exist; `documents` 8, `document_chunks` 36, `document_structure_elements` 0, `document_structure_edges` 0. None of the four structure-discriminating filenames occurs in the DB. The runner source explicitly tears down its scoped evaluation user/documents at the end, which explains why this audit cannot query those evaluation rows now. Current counts cannot be substituted for historical per-run counts.

## 6. Chunker inspection

Current configuration is `Settings.chunker_version = "legacy"`, resolving to `chunk-v1-legacy-chars-1000-200`. Production `_build_chunk_objects` calls `processing.chunk_text` for this version, producing 1000-character sliding windows with 200-character overlap. It persists the `document_id`, page, `chunker_version`, and `token_count`; it leaves chunk `heading_path`, `section`, and `element_type` null. The builder has no fields for structure-element ID, parent-element ID, or table/row/cell identity.

Legacy `chunk_text` does prepend `heading_path` text to non-heading extracted elements before embedding. In the fresh corpus smoke, 24/46 emitted chunks had an actual heading prefix in their text; all 8 table elements became 8 chunks containing serialized row/column text. That is semantic text content, not persisted structured metadata or a chunk-to-element relation. The runner resolves labels by substring against ingested chunk text, not by persisted structure node identity.

Fresh `_build_chunk_objects` smoke (no database writes):

| Version | Chunks | Document ID | Page | Non-null section | Non-null heading path | Non-null element type | Structure-element ID | Parent-element ID | Table chunks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Legacy production | 46 | 46 | 46 | 0 | 0 | 0 | 0 | 0 | 0* |
| Existing `structure-v2` candidate | 27 | 27 | 27 | 24 | 24 | 27 | 0 | 0 | 8 |

`table chunks` in the legacy metadata table is 0 because `element_type` is null; the separate text-level check measured 8 legacy table-derived content chunks. For structure-v2, its pure builder emits separate atomic table chunks and repeats headers/keeps row boundaries when oversized, but it still does not assign row/cell IDs or structure-element IDs. Fresh content check confirmed 8/8 v2 table chunks retain pipe-separated row/cell text.

`structure-v2` is existing and unit-tested (`tests/unit/documents/test_phase3d_chunking.py`): it groups by heading path/page/type, prepends heading context, uses token budgets (target 200/min 40/max 256, encoder-capped), separates tables and preserves table rows in chunk text. Switching configuration would populate section/path/type and alter chunk count/IDs/content; because ingestion embeds the resulting chunk text, it changes embedding inputs and requires reprocessing/re-embedding documents to take effect. Tests exist, but no evidence in this audit certifies production rollout safety. Enabling v2 does **not** create row/cell graph nodes, element links, or make element evidence rankable. No migration is required for the existing metadata columns; whether production should adopt it requires an independently planned validation/rollout and is not recommended as the whole fix here.

## 7. Structural retrieval inspection

`chat.rag.retrieve_structural_candidates` starts from up to 8 matching section/path chunk IDs and up to 3 semantic chunk seed IDs, then expands the `document_graph_edges` chunk graph at most 2 hops, capped at 40 visited nodes. Query scope is authenticated `user_id` through the owning document; graph edges are per-document. It loads chunk candidates, assigns graph-distance structural score `relation_weight / (1 + hops)` (seed hop 0 receives 1.0), and sorts by that score then chunk ID. These candidate counts cannot be measured for the selected current corpus because those documents no longer exist in the DB.

`retrieve_dual_path` always receives semantic chunks in Brain; it obtains structural chunk candidates and calls `fuse_dual_path`. That function unions chunk IDs and computes weighted RRF using current defaults `semantic_weight=0.7`, `structural_weight=0.3`, `k=60`. Structural-only hits have semantic `score=0.0`; the distinct `fusion_score` is nonzero and sorting is by fusion score descending, then cosine score, then chunk ID, truncated to top-k. Thus chunk-level structural candidates can affect ordering. Expressions like `score or 0.0` appear in deterministic sort/gate adapters, but these do not overwrite RRF contribution. For an undefined/non-semantic structural similarity, source score is explicitly zero by contract, not a converted cosine.

Heading/section seed discovery requires `DocumentChunk.section` or `heading_path`; production legacy chunks have neither, so this seed branch is inert for newly produced legacy chunks. The semantic seed anchor plus chunk graph edges can still run, but its structure is page/order proximity rather than document-native hierarchy. `plan_edges` for the measured 46 legacy chunks would create 154 chunk edges (42 NEXT, 42 PREV, 70 SAME_PAGE; 0 SAME_SECTION due to null paths). These are freshly planned counts, not persisted DB rows.

## 8. Evidence fusion inspection

`graph.evidence.fuse_evidence` supports merging semantic `EvidenceItem`s and structural element `EvidenceItem`s. Semantic items keep real similarity scores; structural items keep `score=None`, identity and provenance. The generic function preserves ordered streams (semantic first, structural second) and does not create a ranking score.

`fuse_document_evidence` can accept explicit structure element IDs and gather each element’s parent chain for heading context. However, a bounded repository-wide search found no production caller of `fuse_document_evidence`; it is a callable service primitive, not the endpoint’s current element-candidate generator.

The production `_augment_with_structure` instead calls `collect_document_structure_evidence` for each document represented among the already-ranked chunks, selecting at most the first 20 elements in sequence order (max 5 docs), then `fuse_evidence` on the structural-only stream. It converts content-bearing elements to `SourceChunk(chunk_id="structure:<uuid>", score=0.0, retrieval_path="structural", evidence_kind="structure_element")` and appends them to the ranked chunks. This fusion is provenance normalization/list concatenation; it does not fuse scores or rerank.

## 9. Final ranking inspection

There are two meanings of “final ranking” here:

- **Final retrieval ranking (chunk-level):** structural chunk candidates participate in RRF before top-k, so they can move into/out of top-k or reorder it. This makes the chunk structural path genuinely ranking-reachable.
- **Element evidence order/context:** persisted elements are appended after top-k in document sequence order; no structure relevance score, query term match, tree distance, or rank is applied. They follow the chunks in the input to `build_qa_context`, so ranked chunks are considered first. Elements may be included in QA context if token space remains. The question-invariant first-elements policy can omit later target structures, including tables if they fall after the first 20 elements.

`Brain._collect_evidence` restricts reported evidence to IDs actually included in `ContextPack.included_ids`, tracking omitted items; the gate and response receive only supplied sources. For elements the model IDs carry the `structure:` prefix and evidence kind `structure_element`. If included, elements can influence answer context, but cannot affect the prior retrieval ordering. The evaluator’s `Pipeline.retrieve` deliberately removes these `structure:` IDs from the chunk retrieval-score list while retaining them in answer evidence/context, so retrieval metrics do not score element ranking.

Frozen experiment files store metrics and per-question path-agreement booleans, not candidate IDs or element source details. In those artifacts, C/D have path agreement true 64/64 answerable (72/72 including unsupported) and A/B 0/64; `path_agreement` means at least one QA-supplied chunk has `retrieval_path="hybrid"`. This proves a shared chunk was tagged from both paths; it does not prove the element stream contributed to RRF or that the right structural element entered/survived top-k. Here it is provenance/match coverage, not a measure of ranking benefit.

## 10. Table row/cell capability

The `DocumentStructureElement` model vocabulary accepts `table_row` and `table_cell`, but the production PDF parser does not emit them. `extract_pdf` retains table structure in the transient `ExtractedElement.table_data` and serialized text. `ParsedElement` lacks the nested data field and is persisted as one `table` node; no code found emits individual row/cell nodes. Consequently:

```text
table → table_row → table_cell
```

is not a graph shape reachable from current PDF ingestion. A table’s cells can be read as text in table content or legacy/v2 chunks; graph traversal cannot address or select individual cells. The row/cell gold IDs in this corpus are authored conceptual annotations, not database IDs. No row/cell nodes were fabricated for this audit.

## 11. Structure-v2 assessment

- **Heading paths:** yes, the chunker preserves metadata and embeds heading context from `ExtractedElement.heading_path`.
- **Structure-aware chunks:** yes; fresh deterministic corpus probe: 27 chunks, 24 with non-null heading path/section, 27 with element type, 8 table chunks.
- **Table relationships:** keeps table rows/headers together in table chunk text and stratifies large tables by intact rows; no relational row/cell nodes or identities.
- **Structural candidate generation:** not by itself. The current chunk retriever can then use populated section/path metadata for seeds, but v2 does not implement a new structure-element candidate generator.
- **Production-safe:** not established by this audit. It is a candidate selectable via configuration and has unit tests; changed chunk boundaries/content/IDs and re-embedding implications remain operationally material.
- **Migration:** no migration to use existing nullable chunk metadata; row/cell or chunk→element identity would require schema design only if decided later.
- **Embedding behavior:** changed inputs/chunks; reprocessing regenerates embeddings.
- **Chunk IDs:** builder creates one new ID per output chunk; different count/boundaries mean new IDs on ingestion/reprocess.
- **QA effects:** can change vector neighborhood, RRF seeds and context ordering; impact is unmeasured here. Do not enable on the basis of this audit.

## 12. Quantitative reachability counts

For rows marked “measured parser/build” numbers are freshly computed from generated PDFs in a temporary directory, without persistence or embeddings. “Frozen report” comes from stored 2026-10-04 experiment artifacts. “Unavailable” means the source documents were torn down and exact live counts cannot be reconstructed from the aggregate metrics.

| Stage | Structural signal | Count | Reachable? |
|---|---|---:|---|
| Authored conceptual PDF elements | sections / paragraphs / tables / rows / cells | 19 / 19 / 8 / 41 / 123 | authored only |
| Parser output (4 PDFs) | total; sections / paragraphs / tables / text blocks | 46; 19 / 19 / 8 / 0 | yes; parser measured |
| Parser output | table rows/cells as graph nodes | 0 / 0 | no |
| Transient extractor table payload | table rows/cells | 49 / 147 | yes as in-memory data/text only |
| Parser hierarchy | non-null heading paths / parent source IDs | 43 / 39 | yes; persisted by mapping |
| Persisted element rows predicted from one-to-one persister | elements / parent_id links / heading paths | 46 / 39 / 43 | implementation-inferred; no current rows |
| Persisted structure edges | actual after current ingest pipeline | 0 constructed by production; current DB 0 | no edge-based tree path; parent_id traversal exists |
| Production chunker | resolved version | `chunk-v1-legacy-chars-1000-200` | yes |
| Current legacy chunks from selected PDFs | total / doc ID / page | 46 / 46 / 46 | measured builder |
| Legacy chunks with persisted structure metadata | any structure columns / section / heading path / element type | 0 / 0 / 0 / 0 | no |
| Legacy chunk embedding text | heading prefixes / table-derived text chunks | 24 / 46 / 8 | yes; text only |
| Chunk graph (legacy plan) | chunk edges total: NEXT / PREV / SAME_PAGE / SAME_SECTION | 154: 42 / 42 / 70 / 0 | yes; RRF traversal |
| `structure-v2` candidate build | chunks / section / heading path / element type / table chunks | 27 / 24 / 24 / 27 / 8 | candidate only; not production configuration |
| Selected evaluation docs in current DB | docs / chunks / elements / structure edges | 0 / 0 / 0 / 0 | unavailable after teardown |
| Selected corpus structural chunk candidates per question | exact candidates | unavailable | no retained IDs/logs |
| Selected corpus element evidence after augmentation | exact fused/included elements | unavailable | no retained IDs/logs |
| Frozen C/D experiment | path-agreement true, answerable questions | 64 / 64 | shared hybrid chunk provenance only |
| Frozen C/D experiment | element evidence entering final ranking | 0 by design | elements are outside chunk RRF |
| Frozen C/D experiment | element evidence surviving RRF top-k | 0 by design | not in RRF candidate type/ID set |
| Live production QA survival counts for selected PDFs | element evidence supplied to QA / reported | unavailable | selected PDFs absent; no per-question run trace |

“Actual persisted structure edges = 0” refers specifically to `DocumentStructureEdge` production writes and current DB. The chunk graph is a different table and does have planned edges as shown above. No assertion is made that the selected test run persisted 0 chunk graph edges; its runner tears data down after evaluation.

## 13. Exact structural signal loss point

There is not one universal loss point; it depends on what is meant by structural information:

1. **PDF table hierarchy loss starts in extraction:** parser emits an aggregate `table` with text only, no row/cell nodes. In the Oslo multi-hop example, PDF reading/extraction order also associates the 95 L/s table with the preceding Primary Loop heading rather than Secondary Loop; the Secondary Loop has no parsed table child. Persistence faithfully stores this incorrect/missing structure; it is not a persistence drop.
2. **Chunk metadata loss occurs at the legacy chunk builder:** parser/extractor heading ancestry becomes heading-prefix text but `DocumentChunk.section`, `heading_path`, and `element_type` are left NULL. That disables production heading/section seed matching and SAME_SECTION chunk edges for those chunks. Page/order chunk edges and semantic-seeded traversal remain active.
3. **Element graph-to-production retrieval disconnect occurs at candidate generation:** parent/child traversal APIs exist, but production `retrieval_adapter` invokes only chunk graph dual-path retrieval and then the document-wide `_augment_with_structure`; it does not select element seeds or traverse element parent/descendant neighborhoods for ranking.
4. **Element ranking loss occurs at fusion boundary:** `fuse_evidence` orders streams and preserves provenance but does not score them; `_augment_with_structure` appends elements after the RRF top-k. The QA context sees them only after ranked chunks, when there is remaining context budget. Thus element-level evidence cannot influence retrieval top-k or its order.
5. **Experiment observability limitation:** frozen report output drops retrieved/source IDs from `QuestionResult.to_dict`. It has path-agreement booleans and aggregate metrics only; cannot answer exact per-question structural-candidate/element-in-context survival retrospectively.

## 14. Minimal architectural fix

```text
Current loss point:
Element hierarchy has no query-to-element candidate generator in the production Brain adapter; current element collection is document-order augmentation after chunk RRF. Row/cell targets are not represented by parser nodes, and legacy chunks also discard searchable heading metadata.

Evidence:
Fresh parse: 46 elements, 43 paths, 39 parent links, 0 row/cell nodes; legacy: 46 chunks, 0 persisted section/path/type; current retrieval code RRFs chunk IDs only; _augment_with_structure appends the first 20 element rows by sequence after top-k; frozen reports retain no IDs or element survival counts.

Minimal fix:
For the next controlled research iteration, implement an opt-in structure-element candidate generator at the AI/retrieval boundary: seed from parser-persisted section/table elements using query terms and/or semantic chunk anchors, walk document-scoped parent/child links to a bounded neighborhood, then give returned element evidence an explicit, calibrated ranking/fusion contribution before top-k/context selection. First ensure the parser correctly associates tables with their real section; add native row/cell emission only as a separate, specifically validated extension if table-cell paths are a target. Preserve provenance and instrument candidates → fused → top-k → QA-supplied element IDs.

Why this fix:
It addresses the observed architecture gap—no query-conditioned element selection/ranking—without asserting that chunk RRF is globally broken. Merely switching to structure-v2 restores chunk metadata and can make section seeds active, but leaves element traversal/ranking and table row/cell identities absent. Emitting rows/cells alone would still not make them candidates or rank them.

Files likely affected:
AI_AGENT-owned `backend/brain/adapters.py`, `backend/chat/rag.py`, `backend/graph/service.py`, `backend/graph/evidence.py`; parser corrections in `backend/documents/processing.py` and `backend/documents/parser.py` need the owning backend agent. Evaluation instrumentation/reporting in `backend/evaluation/experiments/run_dual_path_ablation.py` belongs to evaluation. Do not cross ownership boundaries without Coordinator/owning-agent handoff.

Migration required:
Not for a query-conditioned bounded traversal over existing `DocumentStructureElement.parent_id` nodes. A persistent chunk→element foreign key or row/cell nodes would require a separately reviewed migration; neither is necessary for a first bounded read-time traversal.

Embedding regeneration required:
No, not for an element candidate generator that scores persisted elements at query time. Yes if adopting structure-v2 because chunk text/boundaries and embeddings change. Row/cell text can be query-scored without embedding regeneration if no new vector field is introduced; an embedding-based row/cell index would require generation/storage design and embeddings.

Expected research impact:
Makes the full structure path observable and capable of changing ranked evidence, permitting a later pre-registered experiment to test the structure hypothesis. It does not predict or guarantee a positive result.

Risk:
Potential false positives and harmful rank shifts; document isolation, candidate bounds, dedup identity, score calibration, context budget, PDF heading/table association errors, and increased latency need focused tests and an opt-in shadow/ablation before production activation.
```

The recommendations are architectural findings only; no fix is implemented here.

## 15. Risks and migration impact

- Do not activate v2 or change settings based on these counts alone: it changes chunk texts/IDs and hence vector neighbors and answer context; reprocessing/regeneration is required.
- A new element ranking signal needs explicit score semantics; element evidence currently has no similarity and `fuse_evidence` intentionally invents none.
- Parsing PDF tables before headings (as current extractor ordering does) can create root tables or attach tables to a previous section. Adding row/cell nodes without fixing table/heading association would faithfully persist bad hierarchy at finer granularity.
- An opt-in query-time traversal over current parent IDs avoids migration, but existing row/cell granularity remains absent.
- Current ownership/security filters are valuable: element retrieval must scope every query by authenticated document ownership and must not trust question-provided document IDs.
- Audit left `.env`, database rows, embeddings, runtime config, models, and existing evaluation reports untouched.

## 16. Research interpretation

The frozen experiment did exercise a real chunk-level production dual path: structural chunk candidates entered RRF when they were generated from section/path seeds or semantic anchors, and hybrid matches existed on all answerable C/D questions. Thus it would be inaccurate to say “no structural retrieval ran.” But legacy metadata makes explicit section-name seeds/SAME_SECTION edges unavailable, and the tree-based element graph did not drive query-conditioned candidates or ranking. The unranked element stream can still expose structural text to QA context, but it is not a test of structure-ranked element retrieval or row/cell-aware GraphRAG.

Therefore: **No benefit was observed under the current production structural signal/retrieval configuration.** The result is informative about the measured production chunk-RRF + appended-element-context configuration, but it is **not a valid test of the full structure-aware hypothesis** (especially native row/cell retrieval/ranking). It also does not establish that structure-aware retrieval fails generally.

## 17. Recommended next experiment

Do not expand the corpus yet. First implement the minimal opt-in, query-conditioned element candidate path and instrumentation under owning-agent review, plus correct table-to-heading association and tests. Then run a small, pre-registered smoke/ablation on the existing corpus (not an expansion) that records exact IDs/counts at each boundary:

```text
parsed element IDs → persisted IDs → selected seeds → traversed candidates
→ fused evidence and scores → top-k ranks → QA-included IDs
```

Report table, section, and multi-hop categories separately, compare semantic-only and element-ranked conditions, preserve the same question set/answer model, and verify the actual QA interface receives target evidence. Only after that test is interpretable should corpus size be reconsidered. If implementation choices around whether row/cell nodes are required or whether v2 is a separate arm are to be made, ask the Coordinator/AI/backend owners before editing.

## 18. Files inspected/changed

**Changed:**

- `backend/evaluation/reports/structural_retrieval_reachability_audit.md` — this report only.

**Inspected for this audit:**

- `AGENTS.md`, `CONTEXT.md`, `DOCUMIND_PROJECT_CONTEXT.md`
- `agents/ai-agent.md`, `agents/evaluation-agent.md`
- `backend/evaluation/README.md`
- `backend/evaluation/reports/structure_discriminating_ablation_report.md`
- `backend/evaluation/reports/structure_discriminating_v1_audit.md`
- `backend/evaluation/reports/structure_discriminating_analysis.json`
- `backend/evaluation/reports/ablation_structure_discriminating_{A,B,C,D}.json`
- `backend/evaluation/reports/ablation_structure_discriminating_config.json`
- `backend/evaluation/experiments/run_dual_path_ablation.py`
- `backend/evaluation/experiments/synthesize_structure_discriminating.py`
- `backend/evaluation/datasets/structure_discriminating_v1.py`
- `backend/evaluation/runner.py`, `schemas.py`, `qa_metrics.py`
- `backend/documents/parser.py`, `processing.py`, `structure.py`, `chunking.py`, `routes.py`, `models.py`, `config.py`
- `backend/graph/models.py`, `service.py`, `evidence.py`
- `backend/chat/rag.py`, `routes.py`
- `backend/brain/__init__.py`, `adapters.py`, `planner.py`, `executor.py`, `gate.py`, `response.py`, `types.py`
- Relevant document and graph unit/integration tests; `backend/tests/conftest.py`, `backend/tests/fixtures/graph_data.py`
- `backend/migrations/versions/005_add_document_graph.py`, `006_add_structure_elements.py`

No production, database, model, config, migration, or test files were edited. At task start, the worktree already had extensive unrelated changes; this audit did not revert or stage them.

## 19. Verification

Fresh read-only probes (all used temporary generated PDFs or read-only DB SELECTs):

- `./venv/Scripts/python.exe -m pytest tests/unit/evaluation -q` — **120 passed**, 1 warning.
- `./venv/Scripts/python.exe -m pytest tests/unit/graph -q` — **57 passed**, 1 warning.
- `./venv/Scripts/python.exe -m pytest tests/integration/graph -q` — **25 passed**, 1 warning.
- Additional `./venv/Scripts/python.exe -m pytest tests/unit/documents -q` — **105 passed**.
- Re-generated the four corpus PDFs in temporary directories and called the actual `parse_pdf`, `extract_text`, `chunk_text`, structure-v2 `chunk_elements`, production `_build_chunk_objects`, and chunk-graph `plan_edges`; counts are recorded above. No persistent writes, embedding generation, or DB inserts were made by these probes.
- Read-only PostgreSQL probe succeeded and confirmed schema tables; selected structure-discriminating PDFs absent; current DB aggregate 8 documents/36 chunks/0 element rows/0 element-edge rows.
- Existing experiment artifacts inspected directly; no runner or synthesis script was executed.
- A first isolated chunk-builder probe failed because SQLAlchemy relationship mappers had not yet loaded their dependent models; the corrected read-only probe imported registered model classes and completed successfully. No source changes were made to address this probe setup issue.
- A code-search executable was unavailable in this host shell, so relevant paths were checked with targeted repository reads and a Python source scan; this did not affect the pytest or parser/DB probes.

Warnings were pytest-asyncio event-loop deprecation warnings. No A/B/C/D rerun, corpus expansion, package installation, model change, embedding regeneration, or production configuration change occurred.

## 20. Final status

FINAL STATUS: STRUCTURAL PATH PARTIALLY REACHABLE — FIX REQUIRED
