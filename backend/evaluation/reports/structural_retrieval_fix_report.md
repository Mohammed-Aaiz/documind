# Structural Retrieval Fix Report

**Date:** 2026-10-04
**Scope:** Smallest coherent fix making persisted `DocumentStructureElement`
evidence genuinely reachable for retrieval/ranking, plus the PDF table/heading
attribution correction it depends on. No A/B/C/D ablation was rerun. The corpus
was not expanded. No trained model, `.env`, migration, or unrelated worktree
change was touched.

Companion artifacts: `structural_retrieval_reachability_audit.md` (root-cause
audit), `structure_discriminating_ablation_report.md` (prior null result,
reinterpreted by the audit).

---

## Claim boundary (read first)

| Claim | Status in this task |
|---|---|
| **Technical reachability** — a persisted structure element can become a ranked retrieval candidate and reach the QA context | **Demonstrated** (deterministic fixture + regression tests) |
| **Ranking influence** — structural evidence receives a legitimate rank contribution and changes the final candidate ordering | **Demonstrated** (deterministic fixture; see limitation in §12) |
| **Retrieval improvement** — structure improves Recall/Precision/nDCG | **NOT measured** — no claim |
| **Answer-quality improvement** — structure improves EM/F1/accuracy | **NOT measured** — no claim |

---

## 1. Root cause

Two independent defects (per the reachability audit):

1. **Parser attribution** — `documents.processing.extract_pdf` emitted *all*
   `page.find_tables()` tables before walking any `get_text("dict")` blocks, so
   every table inherited the heading state as of the **page start** (or the
   previous page). A table under "Secondary Loop > Pump Specifications" was
   attributed to "Primary Loop > Pump Specifications", and element order was
   tables-then-text rather than read order.
2. **Element retrieval disconnect** — persisted `DocumentStructureElement`
   evidence had no query-conditioned candidate generation. Production
   `_augment_with_structure` appended the first 20 elements per document in
   sequence order **after** chunk RRF had already selected top-k, with
   `score=0.0`, so element evidence could never influence retrieval ordering.
   `graph.evidence.fuse_evidence` preserves provenance but performs no ranking.

## 2. Parser correction

**File:** `backend/documents/processing.py` (BACKEND scope).

`extract_pdf` now merges detected tables and text blocks into **one per-page
event stream sorted by the actual PyMuPDF bounding boxes `(y0, x0)`** before the
heading state is applied. Each table inherits the heading context current *at
its own read position*. Ties at identical coordinates break deterministically
(text blocks before tables, then original extraction index). Only
PyMuPDF-provided coordinates are used — no layout is invented. Text blocks that
substantially overlap a detected table are still skipped (`_bbox_overlaps_table`
unchanged), so table text is not duplicated. The degenerate fallback (dict
extraction failure) keeps its historical deterministic order.

Preserved contracts (regression-tested): `parse_pdf(...)` signature and return
type, element vocabulary (`section` / `paragraph` / `table` / `text_block`),
contiguous deterministic `sequence_index`, 1-based page numbers, parent
resolution from heading paths, and malformed input still raising (not
swallowed). Determinism: identical bytes → identical `structural_dict()`.

## 3. Retrieval design selected

**Option A — direct structure-element candidate stream.**

A persisted element becomes a retrieval candidate with the stable identity
`structure:<element uuid>`, receives a rank-based contribution in the *existing*
RRF fusion, and enters the same final top-k process as semantic chunks.

The candidate mechanism reuses the architecture's established structural
machinery rather than inventing a paradigm:

* **Seeds** — same structural-name term matching as the chunk path
  (`find_section_seed_matches`): an element seeds when its own section name
  (`heading_path[-1]`) contains a question term. Element **content is never
  matched** (the chunk path's documented rule: "seed matching reads structure,
  never text"). Deeper sections are reached by traversal, not by ancestor-name
  matching.
* **Expansion** — bounded breadth-first walk over the authoritative `parent_id`
  tree (`PARENT_OF`, ≤ 2 hops, ≤ 40 nodes), user-scoped and document-scoped at
  every level, mirroring `expand_from_seeds`.
* **Ranking** — the existing graph-distance score
  `structural_score = relation_weight / (1 + hops)` (seed = 1.0). No lexical
  score is used for ranking; matched-term counts only bound which seeds enter,
  exactly as in the chunk path.

## 4. Why alternatives were rejected

* **Option B — element→chunk mapping:** no durable mapping exists;
  `structure-v2` carries only process-local source spans and would change chunk
  texts, IDs and embeddings (reprocessing + re-embedding). Mapping legacy chunks
  post hoc would be guesswork. Rejected as a larger, riskier change than needed.
* **Option C — graph expansion from semantic seeds:** semantic seeds are chunk
  IDs; the element tree has no chunk linkage, so this collapses into Option B's
  mapping problem. Rejected.
* **Row/cell nodes:** the audit showed they are not required for the minimum
  fix; aggregate table content is retrievable as one element. Not implemented.
* **Arbitrary lexical relevance scores:** forbidden by the honesty contract and
  unnecessary — rank-based fusion over an honest candidate ordering is the
  mechanism the architecture already justifies (RRF over the chunk structural
  path).

## 5. Schema impact

**Migration: NOT REQUIRED.** `DocumentStructureElement` already carries
`id`, `document_id`, `parent_id`, `sequence_index`, `heading_path`, `content`,
a unique `(document_id, sequence_index)` and indexes on `document_id` /
`parent_id` — sufficient for deterministic identity, document-scoped candidate
lookup and tree traversal. `graph/models.py` and Alembic are untouched.

## 6. Candidate generation

**Files:** `backend/graph/service.py` (AI scope) — `find_element_seed_matches`,
`expand_element_seeds`, `load_element_candidates`; `backend/chat/rag.py` —
`retrieve_structural_element_candidates`.

Flow: query → `terms_from_question` → seed elements by section name →
bounded `parent_id` expansion → user-scoped element load (foreign ids silently
absent) → `SourceChunk(chunk_id="structure:<uuid>", evidence_kind="structure_element",
retrieval_path="structural", score=0.0, structural_hops/relation/score)`
ordered by `(-structural_score, chunk_id)`, bounded at 10 candidates (seeds ≤ 8).

## 7. Ranking mechanism

`chat.rag.retrieve_dual_path` now merges chunk-level structural candidates and
element candidates into **one structural ranking stream** ordered by the same
graph-distance score, then fuses it with semantic chunks via the unchanged
rank-based RRF (`semantic_weight=0.70`, `structural_weight=0.30`, `k=60`). A
structural candidate's contribution is `0.30 / (60 + rank)` — a rank
contribution derived from the real candidate ordering, **never** a similarity.
`score` stays `0.0` for elements and is never presented as relevance;
`fusion_score` and `structural_score` are labelled as rank and graph distance.
Tie-breaks are fully deterministic (fusion desc, similarity desc, id asc).

## 8. Evidence fusion

* RRF fusion (`fuse_dual_path`) preserves all provenance fields through
  `dataclasses.replace`: `retrieval_path`, `evidence_kind`,
  `structural_hops/relation/score`; a candidate found by both paths is
  `hybrid`, elements are always `structural`.
* `brain.adapters.retrieval_adapter` carries `evidence_kind="structure_element"`
  into `SourceRef`, so `Brain._collect_evidence` counts element evidence
  separately (existing `structuralElementSourceCount` machinery).
* `_augment_with_structure` (the legacy post-ranking element stream) is
  retained for elements the ranked path did not select, and now **skips any
  element already present as a ranked candidate** — no duplicate identities.
* `graph.evidence.fuse_evidence` is unchanged: it remains provenance-preserving
  normalization and still invents no score.

## 9. Reachability fixture

**File:** `backend/tests/integration/graph/test_structure_reachability.py`
(small deterministic fixture — not the research corpus).

Fixture: one one-page PDF with three sections — `Instrument Calibration` (H1),
`Rig Setup` (H2, child), `Field Supplies` (H1) — a ruled table
`Kestrel frame | reference rig` under `Rig Setup` (the target element whose
content represents the answer) and an irrelevant paragraph under `Field
Supplies`, plus **one declared** irrelevant high-ranked semantic candidate
(`semantic-irrelevant`, score 0.93 — a labelled test double in the established
`test_graph_rag_flow` pattern, not a measured pgvector result). Query: *"What
is the Kestrel frame calibrated against in the Instrument Calibration
section?"* (terms: kestrel, frame, calibrated, instrument, calibration).

**Recorded trace** (real parser → real persister → real candidate SQL → real
fusion → real QA context builder):

```text
semantic candidates   semantic-irrelevant (score 0.9300)
structural candidates structure:section   hops 0  relation None      structural_score 1.000000
                      structure:subsection hops 1  relation PARENT_OF structural_score 0.500000
                      structure:table      hops 2  relation PARENT_OF structural_score 0.333333
                      (each: score 0.0, evidence_kind=structure_element)
rank contributions    semantic_rank_1   0.01147541   (= 0.70 / 61)
                      structural_rank_1 0.00491803   (= 0.30 / 61)
                      structural_rank_2 0.00483871   (= 0.30 / 62)
                      structural_rank_3 0.00476190   (= 0.30 / 63)
final top-k (k=5)     1 semantic-irrelevant
                      2 structure:section
                      3 structure:subsection
                      4 structure:table        <- target enters top-k
QA supplied evidence  all four candidates; context contains
                      "Kestrel frame | reference rig"
                      and NOT the unmatched section's paragraph
```

The semantic-only baseline for the same input is `[semantic-irrelevant]` alone:
the structural candidates **change the final candidate ordering**, and their
relative order is determined by tree distance (section > subsection > table)
despite the table holding the answer. The trace is asserted value-for-value in
the test, so the numbers above are verified, not illustrative.

## 10. Before vs after behavior

| Stage | Before | After |
|---|---|---|
| PDF table heading attribution | stale page-start / previous-page heading | heading current at the table's read position |
| Element candidate generation | none (first-20 sequence append) | query-seeded + bounded tree expansion |
| Element identity | `structure:<uuid>` appended post-ranking | `structure:<uuid>` ranked candidate |
| Rank contribution | none (score 0.0, after top-k) | `0.30/(60+rank)` in the shared RRF |
| Enters final top-k | never | when the fused budget admits it |
| Changes final ordering | never | yes (fixture-verified) |
| Survives into QA context | if token space remained after chunks | as ranked evidence (`included_ids`) |
| Document isolation | document-scoped | document-scoped + user-scoped at every query |
| Semantic-only baseline | unchanged | unchanged (`DOCUMIND_DUAL_PATH_RAG=0` or no elements) |

## 11. Regression tests

All behavioral, against real persisted rows / real PDFs (no mock assertions):

| Suite | Result |
|---|---|
| `tests/unit/documents/test_pdf_read_order.py` (new, 8) | **8 passed** — read-order, cross-page staleness, parent resolution, vocabulary, determinism, malformed input |
| `tests/unit/graph/test_structure_element_retrieval.py` (new, 14) | **14 passed** — generation, content-never-seeds, bounding, user isolation, unready docs, stable identity, deterministic order, hop ordering, exact RRF contributions, top-k entry, ordering change, augmentation dedup, no fabricated values |
| `tests/integration/graph/test_structure_reachability.py` (new, 3) | **3 passed** — recorded trace, semantic-only baseline, reproducibility |
| `tests/unit/documents` (full) | **113 passed** |
| `tests/unit/graph` (full) | **71 passed** |
| `tests/integration/graph` (full) | **28 passed** |
| `tests/unit/evaluation` | **120 passed** |
| `tests/unit/chat` + `tests/unit/brain` | **232 passed** |
| `tests/unit` (all) | **559 passed** |
| `tests/integration` (all) | **222 passed** |

Test-layer change: `tests/conftest.py` now registers
`DocumentStructureElement`/`DocumentStructureEdge` in `_patch_pg_columns`
(conftest contract: every ORM model must be listed); before this, element rows
could not be written under SQLite because unpatched UUID columns bound in a
different string form than `documents.id` (FK failure). Also new:
`tests/fixtures/pdf_layout.py` (shared real-PDF builders for the test layer).

## 12. Remaining limitations

* **Weight asymmetry:** under the declared 0.70/0.30 prior, a structural-only
  candidate cannot displace a full semantic top-k; it enters when the fused
  budget admits it (sparse semantic results, larger top-k). The fixture is
  constructed accordingly. Whether elements deserve a different weight is an
  open research question — deliberately not tuned here.
* **Seeds need structural names:** an element with no heading context (e.g. a
  table before any heading) or whose section name shares no query term is not a
  candidate; deep sections are only reached within the 2-hop / 40-node bounds.
* **No row/cell nodes:** table content is one aggregate element; cell-level
  retrieval remains unimplemented (audit: not required for this fix).
* **Legacy chunk metadata:** production `legacy` chunks still lack
  `heading_path`/`section`, so the *chunk-level* heading-seed branch remains
  inert; `structure-v2` remains a candidate, not production default.
* **SQLite tests** do not exercise pgvector, the real QA model or Alembic; the
  declared semantic candidate is a labelled test double.
* Table extraction still depends on `find_tables()` detecting ruled tables;
  borderless tables may yield no table element (pre-existing behavior).

## 13. Exact next experiment

A **small pre-registered reachability/measurement run on the existing corpus**
(no expansion, no large ablation yet) that records per question:

```text
parsed element ids → persisted ids → selected seeds → traversed candidates
→ rank contributions → fused top-k → QA-included ids
```

comparing semantic-only vs element-ranked conditions on the same questions and
QA model, reporting table / section / multi-hop categories separately, with
candidate survival counts retained (the audit's observability gap). Only after
this run is interpretable should the full structure-discriminating A/B/C/D be
rerun (next decision point: whether element rank weight needs calibration, and
whether row/cell nodes are required for table questions).

---

**Final status:**

FINAL STATUS: CROSS-AGENT FIX VERIFIED
