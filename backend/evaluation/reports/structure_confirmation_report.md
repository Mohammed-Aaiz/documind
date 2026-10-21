# Structure Held-Out Confirmation Experiment

**Experiment:** `structure_confirmation`  
**Corpus:** `structure_discriminating_v1` (unchanged, no new questions)  
**Configuration:** semantic 0.50 / structural 0.50, k=60, top_k=5  
**Runner:** `backend/evaluation/experiments/run_structure_confirmation.py`  
**Machine-readable artifact:** `structure_confirmation.json`

---

## 1. Objective

Test whether the structural benefit observed at the calibrated prior (0.50/0.50) survives on a genuinely held-out question set, comparing exactly CONTROL (element candidate stream disabled) vs TREATMENT (production element retrieval enabled), everything else frozen.

---

## 2. Why Held-Out Confirmation Is Required

The calibration result is promising evidence, not proof. The prior 0.50/0.50 and the PROMISING label were selected while observing the full corpus, so the same questions cannot independently confirm the effect. A held-out confirmation checks whether the effect is consistent on questions not used to *develop* the evidence, before any claim is made. It also guards against a weight chosen for admission geometry incidentally overfitting to specific questions.

**Honesty note:** the earlier calibration *execution* measured all 72 questions. This split is held-out from the designated development population (outcome-blind, see §3), not never-before-seen data. The confirmation therefore tests effect consistency on a designated held-out subset, not generalisation to unseen data.

---

## 3. Split Methodology

**Rule:** stratum = (str(discrimination_label), category); within each stratum sort question IDs ascending and assign even sorted positions to confirmation (held-out), odd to development. Outcome-blind: depends only on question IDs and stratum labels, never on measured results.

* confirmation (held-out) questions: **38**
* development questions: **34**
* total: **72**
* no overlap: **True** (overlap ids: none)
* covers all questions: **True**

Per-stratum assignment (auditable):

| stratum (discrimination | category) | n | confirmation | development |
|---|---:|---|---|
| DISCRIMINATING|multi_hop_structural | 8 | at_mh_1, os_mh_1, os_mh_3, os_mh_5 | fs_mh_1, os_mh_2, os_mh_4, os_mh_6 |
| DISCRIMINATING|page_crossing | 8 | ar_pg_1, at_pg_1, fs_pg_1, os_pg_1 | ar_pg_2, at_pg_2, fs_pg_2, os_pg_2 |
| DISCRIMINATING|section_heading | 3 | fs_sec_1, fs_sec_3 | fs_sec_2 |
| DISCRIMINATING|structural_distractor | 8 | ar_ds_1, fs_ds_1, fs_ds_3, os_ds_1 | at_ds_1, fs_ds_2, fs_ds_4, os_ds_2 |
| DISCRIMINATING|table_row_cell | 5 | os_tbl_1, os_tbl_3, os_tbl_5 | os_tbl_2, os_tbl_4 |
| NOT_DISCRIMINATING|semantic_control | 8 | ar_sem_1, at_sem_1, fs_sem_1, os_sem_1 | ar_sem_2, at_sem_2, fs_sem_2, os_sem_2 |
| None|unanswerable | 8 | ar_una_8, at_una_2, at_una_4, fs_una_6 | at_una_1, at_una_3, fs_una_5, os_una_7 |
| WEAKLY_DISCRIMINATING|section_heading | 9 | ar_sec_1, at_sec_2, at_sec_4, at_sec_6, os_sec_2 | at_sec_1, at_sec_3, at_sec_5, os_sec_1 |
| WEAKLY_DISCRIMINATING|table_row_cell | 15 | ac_tbl_1, ac_tbl_3, ac_tbl_5, at_tbl_2, at_tbl_4, fs_tbl_1, fs_tbl_3, fs_tbl_5 | ac_tbl_2, ac_tbl_4, at_tbl_1, at_tbl_3, at_tbl_5, fs_tbl_2, fs_tbl_4 |

**Confirmation question IDs (38):** `ac_tbl_1, ac_tbl_3, ac_tbl_5, ar_ds_1, ar_pg_1, ar_sec_1, ar_sem_1, ar_una_8, at_mh_1, at_pg_1, at_sec_2, at_sec_4, at_sec_6, at_sem_1, at_tbl_2, at_tbl_4, at_una_2, at_una_4, fs_ds_1, fs_ds_3, fs_pg_1, fs_sec_1, fs_sec_3, fs_sem_1, fs_tbl_1, fs_tbl_3, fs_tbl_5, fs_una_6, os_ds_1, os_mh_1, os_mh_3, os_mh_5, os_pg_1, os_sec_2, os_sem_1, os_tbl_1, os_tbl_3, os_tbl_5`

**Development question IDs (34):** `ac_tbl_2, ac_tbl_4, ar_pg_2, ar_sem_2, at_ds_1, at_pg_2, at_sec_1, at_sec_3, at_sec_5, at_sem_2, at_tbl_1, at_tbl_3, at_tbl_5, at_una_1, at_una_3, fs_ds_2, fs_ds_4, fs_mh_1, fs_pg_2, fs_sec_2, fs_sem_2, fs_tbl_2, fs_tbl_4, fs_una_5, os_ds_2, os_mh_2, os_mh_4, os_mh_6, os_pg_2, os_sec_1, os_sem_2, os_tbl_2, os_tbl_4, os_una_7`

---

## 4. Held-Out Population

Primary held-out evaluation population: **confirmation DISCRIMINATING** (17 questions):

`ar_ds_1, ar_pg_1, at_mh_1, at_pg_1, fs_ds_1, fs_ds_3, fs_pg_1, fs_sec_1, fs_sec_3, os_ds_1, os_mh_1, os_mh_3, os_mh_5, os_pg_1, os_tbl_1, os_tbl_3, os_tbl_5`

Stratified so category representation is preserved across the split (multi_hop_structural, page_crossing, section_heading, structural_distractor, table_row_cell all appear in confirmation), and answerable/unanswerable is preserved (unanswerable questions form their own stratum, split the same way).

---

## 5. Experimental Controls

Frozen: corpus documents, held-out questions, gold annotations, parser, chunker, embeddings, QA model, database contents/schema, `k=60`, `top_k=5`, weights `0.50/0.50`, candidate-generation logic, evidence fusion logic, evaluation metrics.

Weights injected strictly inside the harness (wrapping `chat.rag.fuse_dual_path`), as in the completed calibration. Nothing was tuned using held-out results; the split is outcome-blind. Production RRF configuration and production code are unmodified.

---

## 6. Reachability

Funnel on the held-out confirmation population (and all-question reference):

### confirmation_DISCRIMINATING (n=17)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 17 | 17 |
| questions_with_persisted_structure | 17 | 17 |
| questions_with_structural_seed | 17 | 17 |
| questions_with_structural_candidates | 17 | 0 |
| questions_with_structural_candidate_rrf_contribution | 17 | 0 |
| questions_with_structure_element_in_final_top_k | 8 | 0 |
| questions_with_structure_element_supplied_to_qa | 17 | 17 |
| questions_where_supplied_structure_overlaps_gold_evidence | 17 | 17 |

* structural-element admission (element in final top-k): **8**

### development_DISCRIMINATING (n=15)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 15 | 15 |
| questions_with_persisted_structure | 15 | 15 |
| questions_with_structural_seed | 15 | 15 |
| questions_with_structural_candidates | 15 | 0 |
| questions_with_structural_candidate_rrf_contribution | 15 | 0 |
| questions_with_structure_element_in_final_top_k | 9 | 0 |
| questions_with_structure_element_supplied_to_qa | 15 | 15 |
| questions_where_supplied_structure_overlaps_gold_evidence | 15 | 15 |

* structural-element admission (element in final top-k): **9**

### confirmation_all (n=38)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 38 | 38 |
| questions_with_persisted_structure | 34 | 34 |
| questions_with_structural_seed | 36 | 36 |
| questions_with_structural_candidates | 36 | 0 |
| questions_with_structural_candidate_rrf_contribution | 36 | 0 |
| questions_with_structure_element_in_final_top_k | 16 | 0 |
| questions_with_structure_element_supplied_to_qa | 38 | 38 |
| questions_where_supplied_structure_overlaps_gold_evidence | 33 | 33 |

* structural-element admission (element in final top-k): **16**

---

## 7. Ranking Influence

Distinguished effects on the held-out confirmation population:

| metric | count |
|---|---:|
| element enters top-k directly | 8 |
| element changes rank indirectly | 0 |
| top-k set changed | 8 |
| gold evidence changed | 4 |
| answer changed | 2 |
| rank-order changed (any) | 8 |
| beneficial | 0 |
| harmful | 0 |

Question IDs — top-k set changed: ['at_mh_1', 'fs_ds_1', 'fs_ds_3', 'fs_pg_1', 'fs_sec_1', 'os_tbl_1', 'os_tbl_3', 'os_tbl_5']; gold changed: ['fs_sec_1', 'os_tbl_1', 'os_tbl_3', 'os_tbl_5']; answer changed: ['fs_ds_3', 'fs_sec_1']

---

## 8. Retrieval Results

CONTROL vs TREATMENT (evidence_unit gold view + evidence coverage).

| population | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| confirmation_DISCRIMINATING | CONTROL | 17 | 0.500000 | 0.270588 | 0.794118 | 0.528218 | 1.000000 |
| confirmation_DISCRIMINATING | TREATMENT | 17 | 0.573529 | 0.317647 | 0.794118 | 0.568822 | 1.000000 |
| development_DISCRIMINATING | CONTROL | 15 | 0.466667 | 0.266667 | 0.688889 | 0.472341 | 1.000000 |
| development_DISCRIMINATING | TREATMENT | 15 | 0.500000 | 0.293333 | 0.688889 | 0.492477 | 1.000000 |
| confirmation_all_answerable | CONTROL | 34 | 0.494118 | 0.270588 | 0.754902 | 0.520669 | 1.000000 |
| confirmation_all_answerable | TREATMENT | 34 | 0.580882 | 0.323529 | 0.754902 | 0.569618 | 1.000000 |
| confirmation_all | CONTROL | 38 | 0.494118 | 0.270588 | 0.754902 | 0.520669 | 1.000000 |
| confirmation_all | TREATMENT | 38 | 0.580882 | 0.323529 | 0.754902 | 0.569618 | 1.000000 |

DELTA (TREATMENT − CONTROL), evidence_unit:

| population | ΔRecall@5 | ΔPrecision@5 | ΔMRR | ΔnDCG@5 |
|---|---:|---:|---:|---:|
| confirmation_DISCRIMINATING | 0.073529 | 0.047059 | 0.000000 | 0.040604 |
| development_DISCRIMINATING | 0.033333 | 0.026666 | 0.000000 | 0.020136 |
| confirmation_all_answerable | 0.086764 | 0.052941 | 0.000000 | 0.048949 |
| confirmation_all | 0.086764 | 0.052941 | 0.000000 | 0.048949 |

---

## 9. Answer Results

| population | arm | EM | token F1 | accuracy | grounding | unsupported rate |
|---|---|---:|---:|---:|---:|---:|
| confirmation_DISCRIMINATING | CONTROL | 0.235294 | 0.556755 | 0.647059 | 1.000000 | — |
| confirmation_DISCRIMINATING | TREATMENT | 0.294118 | 0.565158 | 0.647059 | 1.000000 | — |
| development_DISCRIMINATING | CONTROL | 0.200000 | 0.428889 | 0.533333 | 1.000000 | — |
| development_DISCRIMINATING | TREATMENT | 0.200000 | 0.428889 | 0.533333 | 1.000000 | — |
| confirmation_unanswerable | CONTROL | — | — | 0.000000 | 1.000000 | 1.000000 |
| confirmation_unanswerable | TREATMENT | — | — | 0.000000 | 1.000000 | 1.000000 |
| confirmation_all | CONTROL | 0.235294 | 0.527833 | 0.676471 | 1.000000 | 1.000000 |
| confirmation_all | TREATMENT | 0.264706 | 0.532035 | 0.676471 | 1.000000 | 1.000000 |

---

## 10. Transition Analysis

| population | correct→correct | correct→wrong | wrong→correct | wrong→wrong |
|---|---:|---:|---:|---:|
| confirmation_DISCRIMINATING | 11 | 0 | 0 | 6 |
| development_DISCRIMINATING | 8 | 0 | 0 | 7 |
| confirmation_all_answerable | 23 | 0 | 0 | 11 |
| confirmation_all | 23 | 0 | 0 | 11 |

No regression is hidden behind aggregates: any correct→wrong flip on the held-out population is reported above and counted as a harmful transition.

---

## 11. Category Analysis

Per-category answer metrics on the held-out confirmation questions (TREATMENT) with CONTROL comparison:

| category | n | EM (C→T) | token F1 (C→T) | accuracy (C→T) | element in top-k |
|---|---:|---|---|---|---:|
| multi_hop_structural | 4 | 0.000000→0.000000 | 0.276923→0.276923 | 0.250000→0.250000 | 1 |
| page_crossing | 4 | 0.500000→0.500000 | 0.666667→0.666667 | 0.750000→0.750000 | 1 |
| section_heading | 7 | 0.428571→0.571429 | 0.693878→0.714286 | 0.857143→0.857143 | 4 |
| semantic_control | 4 | 0.250000→0.250000 | 0.583333→0.583333 | 0.750000→0.750000 | 0 |
| structural_distractor | 4 | 0.000000→0.000000 | 0.333334→0.333334 | 0.500000→0.500000 | 2 |
| table_row_cell | 11 | 0.181818→0.181818 | 0.513468→0.513468 | 0.727273→0.727273 | 7 |
| unanswerable | 4 | —→— | —→— | 0.000000→0.000000 | 1 |

---

## 12. Determinism

Two independent complete runs (user/ingest/measure/teardown), identical deterministic-id seed, existing normalisations preserved (model warm-up outside the id region; semantic stream re-sorted by `(-similarity, chunk_id)`). No timestamps, random UUIDs, absolute paths or nondeterministic ordering in canonical outputs.

* runs compared: **2**
* core payload byte-identical: **True**
* run 1 SHA-256: `94747ad8bf4d00d97ee54db74136131c4f7f2cdc650310037ef134208f92b371`
* run 2 SHA-256: `94747ad8bf4d00d97ee54db74136131c4f7f2cdc650310037ef134208f92b371`

---

## 13. Isolation Verification

CONTROL/TREATMENT must differ only in the element candidate stream.

| check | result |
|---|---|
| semantic stream identical | True |
| chunk-structural stream identical | True |
| element seed metadata identical | True |
| CONTROL element stream empty | True |
| arms differ only in element stream | True |

Questions compared: 72; first mismatch: none

---

## 14. Comparison with Calibration Result

Calibration reported on the full DISCRIMINATING set (32 questions) at 0.50/0.50:

* Recall@5 0.070313, Precision@5 0.03125, MRR 0.0, nDCG@5 0.034369, EM 0.03125, token-F1 0.008671, harmful 0, admission 30

Held-out confirmation result on the confirmation DISCRIMINATING subset (17 questions):

* ΔRecall@5 0.073529, ΔPrecision@5 0.047059, ΔMRR 0.000000, ΔnDCG@5 0.040604, ΔEM 0.058824, Δtoken-F1 0.008403, harmful 0, admission 8

Development subset effect (for reference): ΔRecall@5 0.033333, ΔnDCG@5 0.020136

Verdict: **POSITIVE**

---

## 15. Research Interpretation

This distinguishes: structural **admission** (did elements enter top-k), **ranking influence** (did the fused order change), **retrieval improvement**, **answer-quality improvement**, and **replication of the prior effect**.

**Observed:** structural elements were admitted into the held-out top-k and the primary DISCRIMINATING retrieval/answer deltas on the held-out subset are positive with no harmful transitions. This is **replicated evidence** on a designated held-out subset — not universal proof of the structural hypothesis, and not causality beyond what the experiment supports. Because the corpus was fully measured during calibration, this confirms effect *consistency* on an outcome-blind held-out subset rather than generalisation to unseen data.

---

## 16. Limitations

* **Not never-seen data.** The calibration execution measured all 72 questions; the held-out split is outcome-blind and disjoint from the designated development set, but not independent of the calibration run. A fully independent confirmation requires new, independently authored questions.
* **Split size.** The held-out DISCRIMINATING subset is small; metric deltas are coarse and individual question flips are visible.
* **Weight is harness-injected**, not a production change; results describe the current architecture at 0.50/0.50.
* **Shared augmentation stream** present in both arms (only the ranked element contribution isolated).
* **Single corpus, one `top_k`, no evidence gate.**

---

## 17. Exact Next Step

Run a **fully independent replication**: author a small, independently written structure-discriminating question set (new wording, same document corpus) with gold annotations prepared without reference to these results, then repeat this CONTROL vs TREATMENT comparison at 0.50/0.50 on that unseen set. Accept only if the positive effect reproduces with zero harmful transitions. Do not change production weights until independently replicated.

No parser, schema, corpus, QA-model or embeddings change is part of the next step.
