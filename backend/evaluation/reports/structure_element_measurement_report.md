# Structure-Element Measurement — CONTROL vs TREATMENT

**Experiment:** `structure_element_measurement`
**Corpus:** `structure_discriminating_v1` (unchanged)
**Runner:** `backend/evaluation/experiments/run_structure_element_measurement.py`
**Machine-readable deliverables:**
`structure_element_measurement_control.json`,
`structure_element_measurement_treatment.json`,
`structure_element_measurement_analysis.json`
**Nature:** measurement experiment — no parser, graph-schema, retrieval
architecture, RRF-weight, QA-model or corpus change was made.

---

## 1. Executive Summary

The persisted `DocumentStructureElement` **ranking** path is technically
reachable but changes **no retrieved candidate** and (in the primary
population) **no ranking order** on the unchanged corpus under the current
production configuration (RRF `semantic_weight=0.70`,
`structural_weight=0.30`, `k=60`, `top_k=5`).

* Every DISCRIMINATING answerable question produced structural seeds and
  structural element candidates in the TREATMENT arm (32/32).
* **No** element candidate ever entered the final top-k (0/32), and the fused
  top-k **set** was identical between CONTROL and TREATMENT for all 72
  questions (`top_k_changed_rate = 0` on every population). The ordered list
  was identical for 71/72; one NOT_DISCRIMINATING question (`fs_sem_1`) had two
  tied hybrid candidates swap position with no change to the set, gold rank or
  answer (see §9). The primary population had zero ranking change of any kind.
* Consequently every retrieval metric and every answer metric is identical
  between arms (delta `0.0` on all populations and categories).
* The element evidence that *does* reach the QA model arrives through the
  arm-independent `brain.adapters._augment_with_structure` stream, present in
  both CONTROL and TREATMENT; this experiment isolates only the **ranked**
  element contribution and therefore cannot credit that stream to the new path.
* Structural-only admission is not merely unobserved — it is **mathematically
  impossible** at these weights: the strongest structural-only candidate scores
  at most `0.30/(60+1) = 0.004918`, while the weakest top-5 occupant scores at
  least `0.70/(60+5) = 0.010769`.

**Decision gate: (B) CALIBRATE STRUCTURAL RANKING BEFORE FULL A/B/C/D.**

---

## 2. Objective & Scope

Determine whether the already-verified persisted-element retrieval/ranking
path contributes useful evidence on the existing corpus, and decide the next
research step. This is a **measurement**, not an implementation. It does not
re-run the large A/B/C/D ablation, does not expand the corpus, and does not
change the parser, graph schema, retrieval architecture, RRF weights, QA model
or embeddings.

The measurement separates four questions that are easy to conflate:

1. **Technical reachability** — are element candidates generated at all?
2. **Ranking influence** — do they change the fused ranking?
3. **Retrieval improvement** — do retrieval metrics move?
4. **Answer-quality improvement** — do answer metrics move?

---

## 3. Guardrails — What Was Not Changed

* Corpus `structure_discriminating_v1` — unchanged (4 documents, 72 questions).
* Parser (`documents/parser.py`, `documents/processing.py`) — unchanged.
* Graph schema and `graph/service.py` — unchanged.
* Retrieval architecture (`chat/rag.py`) — unchanged; the CONTROL switch only
  stubs `retrieve_structural_element_candidates` to return `[]` for the arm.
* RRF constants, embeddings, chunker, QA model — unchanged (recorded in
  `*.configuration` in the JSON).
* Production code was **not** modified. The only harness-side normalisations
  (model warm-up and semantic tie-break) are described in §16 and applied
  identically to both arms.

---

## 4. Measurement Design — CONTROL vs TREATMENT

| | CONTROL | TREATMENT |
|---|---|---|
| New persisted-element ranking stream | disabled (`retrieve_structural_element_candidates → []`) | production |
| Chunk-level structural path | production | production |
| Post-ranking element augmentation (`_augment_with_structure`) | production | production |
| Everything else | identical | identical |

The instrument spies on the production functions and captures their exact
output; it never reimplements retrieval. After each question the captured
semantic and structural streams are re-fused with the production
`chat.rag.fuse_dual_path` and must equal the production `retrieve_dual_path`
output exactly, or the run aborts with a **MEASUREMENT INTEGRITY ERROR**. No
integrity error occurred in either run.

---

## 5. Corpus & Populations

Corpus verified by running the corpus module: 4 documents, 210 authored
elements, 72 questions (64 answerable, 8 unanswerable).

| Population | n |
|---|---|
| DISCRIMINATING (answerable) — **primary** | 32 |
| WEAKLY_DISCRIMINATING (answerable) | 24 |
| NOT_DISCRIMINATING (answerable) | 8 |
| all answerable | 64 |
| unanswerable | 8 |
| all | 72 |

Category counts: table_row_cell 20, section_heading 12, page_crossing 8,
multi_hop_structural 8, structural_distractor 8, semantic_control 8,
unanswerable 8.

---

## 6. Environment & Configuration

Production configuration recorded in the deliverable JSON
(`configuration` block): corpus `structure_discriminating_v1`, chunker
`chunk-v1-legacy-chars-1000-200`, `top_k=5`, `rrf_k=60`,
`semantic_weight=0.7`, `structural_weight=0.3`,
`structural_element_candidate_limit=10`, `structural_candidate_limit=15`,
element augmentation `5` documents × `20` elements. No evidence gate is
applied (identical in both arms) so the experiment isolates the element
*ranking* contribution only.

Ingested per run: 46 chunks, 46 persisted structure elements, 72 questions.
The parser emitted 29 parsed element source ids; `replace_document_structure`
returned a source-id → ORM-element map covering them.

---

## 7. Reachability Funnel

Primary population — DISCRIMINATING answerable (n=32):

| Funnel stage | CONTROL | TREATMENT |
|---|---:|---:|
| questions | 32 | 32 |
| with persisted structure | 32 | 32 |
| with structural seed | 32 | 32 |
| with structural candidates | **0** | **32** |
| with structural-candidate RRF contribution | **0** | **32** |
| with structure element in final top-k | **0** | **0** |
| with structure element supplied to QA | 32 | 32 |
| where supplied structure overlaps gold evidence | 31 | 31 |

All answerable (n=64): candidates 0 → 61; in final top-k 0 → 0; supplied to QA
64 → 64. All questions (n=72): seeds 63; candidates 0 → 63; in top-k 0 → 0.

Reading: seeds and candidates are produced (reachability ✓), but the funnel
terminates at the top-k boundary (ranking influence ✗). The
"supplied to QA" figure is identical in both arms because it is driven by the
augmentation stream, not the ranked stream.

---

## 8. Candidate Generation & Structural Seeds

* Answerable questions with a structural seed: 61/64; mean seeds/question
  4.6–4.9, max 8–10 (the CONTROL figure is computed post-hoc for the trace,
  since its stream is disabled).
* TREATMENT element candidates: mean 6.27/question, max 10
  (`STRUCTURAL_ELEMENT_CANDIDATE_LIMIT`), non-zero for 61/64.
* Candidate construction is production: section-name leaf seed match → bounded
  `parent_id` BFS expansion → deterministic ordering by
  `(-structural_score, chunk_id)`. No element content is ever matched to the
  question; `score` stays `0.0` (no fabricated similarity).

Example (`at_tbl_1`, TREATMENT): 5 element candidates with
`structural_hops` `[0, 0, 1, 2, 2]` and `structural_scores`
`[1.0, 1.0, 0.5, 0.333333, 0.333333]`; their RRF structural contributions
(`0.30/(60+rank)`) are `[0.004687, 0.004615, 0.004286, 0.004110, 0.004054]`.

---

## 9. Ranking Influence

Ranking-effect comparison by population:

| Metric | DISCRIM (32) | WEAK (24) | NOT (8) | all answerable (64) | all (72) |
|---|---:|---:|---:|---:|---:|
| top-k changed rate (set) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| rank-order changed rate | 0.0 | 0.0 | 0.125 | 0.015625 | 0.013889 |
| gold entered top-k | 0 | 0 | 0 | 0 | 0 |
| gold left top-k | 0 | 0 | 0 | 0 | 0 |
| gold-rank delta (mean) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| beneficial / harmful / neutral | 0 / 0 / 32 | 0 / 0 / 24 | 0 / 0 / 8 | 0 / 0 / 64 | 0 / 0 / 72 |

The CONTROL and TREATMENT `fused_candidate_ids` are equal **as sets** for all
72 questions, and equal **as ordered lists** for 71/72. The single exception is
`fs_sem_1` (NOT_DISCRIMINATING): two candidates that are `hybrid` in both arms
(`31e2c7a2…` and `e01f2609…`) exchange places. The element candidates are
merged into the same structural ranking stream as the chunk-level candidates,
so adding them shifts the **structural ranks** of existing chunk candidates and
thereby their RRF contributions — an indirect, order-only effect. In this case
the set is unchanged, no gold evidence enters or leaves, the gold rank stays 3,
the classification is `neutral`, and the answer is unchanged.

Net: the ranked element contribution has **no material ranking effect**. The
only nonzero signal is one order-only swap on a question explicitly labelled
NOT_DISCRIMINATING, with no consequential change to evidence or answers.

---

## 10. Structural Saturation & Why Admission Is Impossible

Definition (recorded in the analysis JSON): a question is *eligible* when the
semantic path already supplies at least `top_k` candidates and the structural
(path) stream is non-empty; the admission rate is the share of eligible
questions where a structural-only candidate appears in the final top-k.

| Population | eligible n | structural-only admissions (observed) | element-only admissions | admission mathematically possible |
|---|---:|---:|---:|---:|
| DISCRIMINATING answerable | 32 | 0 | 0 | 0 |
| overall | 63 | 0 | 0 | 0 |

Closed-form reason, verified per question in the trace: a structural-only
candidate's fusion score is **only** its structural term, bounded above by
`0.30/(60+1) = 0.004918`. The weakest candidate already inside top-5 has fusion
score at least the 5th semantic contribution `0.70/(60+5) = 0.010769`
(semantic always fills all 5 slots on this corpus). Since
`0.004918 < 0.010769` in every measured question, element candidates cannot
enter top-k at these weights regardless of their quality. Example
(`at_tbl_1`): `highest_structural_only_contribution = 0.004687` vs
`lowest_fusion_score_in_top_k = 0.010769`.

This distinguishes the finding from "candidates are bad": candidate generation
works and candidates would be admissible if the structural prior were large
enough to overcome the semantic prior when top-k is saturated.

---

## 11. Retrieval Metrics

Metric definitions are the project's existing ones
(`evaluation/retrieval_metrics.py`) applied unchanged. Three gold views:

* **evidence_unit** (primary) — retrieved = final top-k (all retrieval units,
  elements included); gold = every ingested unit whose text contains the
  question's gold evidence substring (one rule for chunks and elements alike).
* **chunk_only** (legacy comparability) — retrieved = chunk units in top-k;
  gold = gold chunks.
* **authored_gold** — gold = gold chunks plus authored gold elements that
  resolve to a persisted element (91/125 authored entries resolved; 34 with no
  unique persisted counterpart are excluded, not guessed).

DISCRIMINATING answerable (n=32) — CONTROL = TREATMENT for every cell
(DELTA 0.0):

| View | Recall@5 | Precision@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|
| evidence_unit | 0.484375 | 0.268750 | 0.703125 | 0.485905 |
| chunk_only | 0.968750 | 0.268750 | 0.703125 | 0.781721 |
| authored_gold | 0.437500 | 0.268750 | 0.703125 | 0.448185 |

Evidence Coverage (QA-supplied ÷ top-k): `1.0` in both arms and all
populations (nothing selected is dropped).

Other populations (evidence_unit, CONTROL = TREATMENT): all answerable (64)
Recall@5 0.489063 / P@5 0.259375 / MRR 0.726563 / nDCG@5 0.501137; WEAK (24)
0.491667 / 0.266667 / 0.743056 / 0.519087; NOT (8) 0.500000 / 0.200000 /
0.770833 / 0.508217.

---

## 12. Answer Metrics

Answer metrics are identical between arms on every population
(DELTA 0.0), consistent with the identical top-k membership (the single
order-only swap does not change the evidence set or its relevance) and identical
QA-supplied evidence.

| Population | EM | token F1 | answer accuracy | factual grounding | unsupported rate |
|---|---:|---:|---:|---:|---:|
| DISCRIMINATING (32) | 0.250000 | 0.499960 | 0.625000 | 1.0 | — |
| WEAKLY_DISCRIMINATING (24) | 0.208333 | 0.506173 | 0.791667 | 1.0 | — |
| NOT_DISCRIMINATING (8) | 0.500000 | 0.729167 | 0.875000 | 1.0 | — |
| all answerable (64) | 0.265625 | 0.530941 | 0.718750 | 1.0 | — |
| unanswerable (8) | — | — | — | 1.0 | 1.0 |

The `unsupported_answer_rate` of `1.0` on the unanswerable population means
every unanswerable question received an answer; this is expected because the
evidence gate is not applied in this measurement and is identical in both
arms.

---

## 13. Answer Transitions

Correctness threshold `token F1 ≥ 0.5` (same threshold as `answer_accuracy`).

| Population | correct→correct | correct→wrong | wrong→correct | wrong→wrong |
|---|---:|---:|---:|---:|
| DISCRIMINATING (32) | 20 | 0 | 0 | 12 |
| WEAKLY_DISCRIMINATING (24) | 19 | 0 | 0 | 5 |
| NOT_DISCRIMINATING (8) | 7 | 0 | 0 | 1 |
| all answerable (64) | 46 | 0 | 0 | 18 |

There are **no** corrected→wrong or wrong→correct flips anywhere: the ranked
element path neither helps nor harms answers at the current weights.

---

## 14. Category Analysis

CONTROL = TREATMENT in every category for top-k membership, gold rank and all
retrieval/answer metrics (0 beneficial / 0 harmful / neutral = n in every
category; `top_k_change_rate = 0`). `semantic_control` is the only category
with a nonzero rank-order-change rate (0.125) because it contains `fs_sem_1`,
the single order-only swap described in §9; its metrics are still identical
because the swapped pair has equal relevance. Answer metrics per category
(identical in both arms):

| Category | n | EM | token F1 | accuracy | element in top-k |
|---|---:|---:|---:|---:|---:|
| table_row_cell | 20 | 0.100 | 0.500677 | 0.800 | 0 |
| section_heading | 12 | 0.500 | 0.722222 | 0.916667 | 0 |
| page_crossing | 8 | 0.500 | 0.583333 | 0.625 | 0 |
| multi_hop_structural | 8 | 0.000 | 0.245833 | 0.375 | 0 |
| structural_distractor | 8 | 0.125 | 0.354167 | 0.500 | 0 |
| semantic_control | 8 | 0.500 | 0.729167 | 0.875 | 0 |
| unanswerable | 8 | — | — | 0.000 | 0 |

No category gained or lost evidence or answers. The categories that the corpus
designed to depend on structure (table_row_cell, multi_hop_structural,
structural_distractor) see no benefit from the ranked element stream under the
current weights.

---

## 15. Per-Question Trace

Every question carries a full trace in the CONTROL and TREATMENT JSON files
(63 fields per trace), including: persisted/parsed element ids and the exact
parsed→persisted map; semantic candidate ids/scores/RRF contributions;
structural seed ids, matched terms and match counts; element candidate ids,
hops, relations, structural scores, RRF contributions and rank-in-stream;
chunk-level structural stream; fused ids/ranks/paths/fusion scores and
top-k; saturation inputs; QA-supplied/omitted ids with provenance; gold
views; predicted answer, QA score, grounding and EM/token-F1.

---

## 16. Determinism & Reproducibility

The experiment runs twice (independent user/ingest/measure/teardown cycles) and
the three machine-readable payloads must be byte-identical.

Two run-to-run noise sources were found during development and removed
**without changing production**:

1. **Lazy model loading consumed the deterministic-id counter.** The embedding
   model consumes three real `uuid.uuid4()` calls while loading (measured).
   Because it loaded during the first run's ingestion but not the second, all
   later generated row ids shifted between runs, which changed chunk-id
   tie-breaks. Fixed by warming the embedding and QA models *before* the
   deterministic-id region.
2. **The production vector query has no secondary sort key.** Two chunks with
   exactly equal cosine similarity (`0.4599`) could be returned in either
   order depending on physical row order after re-ingestion; that flipped
   their RRF ranks and the fused order. This is a pre-existing production
   tie-break gap, not an element-path effect. The harness re-sorts the semantic
   stream by `(-similarity, chunk_id)` — same evidence, same scores, applied
   identically to both arms — so the measurement is reproducible. Production
   was not modified.

Determinism verdict for the recorded run (`analysis.determinism`):

| Payload | run 1 SHA-256 | run 2 SHA-256 | byte-identical |
|---|---|---|---|
| control | `ea95021dee8ff08ed9137eb76881c502362cb9fffa854d73fcb6c991fb865485` | same | **true** |
| treatment | `61b87b889df1fe89bb2a5b5c1d751c338beffe598af364cbd4ecea8f94d5bb55` | same | **true** |
| analysis | `f4adf26af7cb8e5c468fc4d94a192753af3feffb44b1586bb6908172a93a553e` | same | **true** |

`analysis_final_byte_identical` is also `true` (the analysis payload, including
its own determinism block and the decision gate, renders identically from both
runs). All payloads deliberately exclude timestamps and latencies. SHA-256
hashes above are over the canonical JSON
(`json.dumps(..., sort_keys=True) + "\n"`).

---

## 17. Limitations

* **Scope of the measured effect.** CONTROL keeps the post-ranking
  `_augment_with_structure` element stream, so this experiment measures only
  the **ranked** element contribution. It cannot attribute any answer quality
  to the ranked path; the element evidence reaching QA (mean ~14 elements per
  question in both arms) comes from the shared augmentation stream.
* **Corpus-specific admission impossibility.** The impossibility argument in
  §10 holds whenever the semantic path fills all `top_k` slots and structural
  candidates are disjoint from semantic ids — which is structurally true here
  — but the exact numbers are for this corpus and configuration.
* **Gold definition sensitivity.** Retrieval numbers are reported under three
  gold views; the primary (`evidence_unit`) applies one substring rule to both
  unit types. 34 authored gold elements have no unique persisted counterpart
  and are excluded from `authored_gold` rather than guessed.
* **No evidence gate.** Unanswerable questions are not gated, so
  `unsupported_answer_rate = 1.0`; this affects both arms equally and is not a
  ranking finding.
* **One configuration point.** The experiment measures the current untuned
  RRF weights only; it does not sweep weights, `top_k`, or reserve a
  structural slot.

---

## 18. Decision Gate

Applied to the pre-declared primary population (DISCRIMINATING answerable) by
measured values only:

* candidates produced: **32/32** (candidate generation is not the problem),
* element top-k admission: **0/32**, admission mathematically possible:
  **0**,
* retrieval MRR delta (evidence_unit): **0.0**,
* answer token-F1 delta: **0.0**, beneficial / harmful changes: **0 / 0**.

### (B) CALIBRATE STRUCTURAL RANKING BEFORE FULL A/B/C/D

The element path is reachable and produces candidates, but the current
`0.70/0.30` RRF prior makes it impossible for an element to be admitted when
the semantic path fills `top_k`. Do **not** proceed to the full A/B/C/D
ablation yet — first calibrate the structural prior (see §19).

---

## 19. Exact Next Experiment

**RRF structural-prior calibration on the unchanged corpus.**

Re-run this same CONTROL/TREATMENT measurement with a single swept variable:
`semantic_weight ∈ {0.70, 0.55, 0.50, 0.40}` with
`structural_weight = 1 − semantic_weight`, holding `k = 60`, `top_k = 5`, the
corpus, parser, embeddings and QA model fixed. For each weight record:
element top-k admission rate; observed vs mathematically-possible admission;
ranking-effect classification counts; retrieval deltas (evidence_unit MRR,
nDCG@5, Recall@5); and answer metric deltas with answer transitions.

Acceptance: identify the **smallest** structural prior at which element
admission becomes possible and non-zero, and confirm retrieval and answer
metrics are non-negative with no correct→wrong transitions. Only if such a
weight exists proceed to the full A/B/C/D ablation; otherwise retain the null
result and revisit candidate scope/slot reservation rather than weights.

*No parser, schema, corpus, QA-model or embeddings change is part of this next
experiment.*
