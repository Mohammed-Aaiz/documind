# Structure RRF Prior Calibration — Sweep Report

**Experiment:** `structure_rrf_calibration`  
**Corpus:** `structure_discriminating_v1` (unchanged)  
**Runner:** `backend/evaluation/experiments/run_structure_rrf_calibration.py`  
**Machine-readable artifact:** `structure_rrf_calibration.json`  
**Nature:** evaluation experiment — only the RRF weights are varied, and only inside the evaluation harness.

---

## 1. Objective

Find the minimum structural RRF prior at which persisted `DocumentStructureElement` candidates can actually enter the production top-k, then determine whether that increased structural influence produces beneficial, neutral or harmful retrieval/answer changes. This does not test the structural hypothesis; it establishes whether the current architecture can expose structural evidence to ranking and what happens when its prior is calibrated.

---

## 2. Baseline

The prior measurement (unchanged) established:

* corpus `structure_discriminating_v1`, 72 questions (64 answerable); primary DISCRIMINATING subset 32.
* production RRF: semantic `0.70`, structural `0.30`, `k=60`, `top_k=5`.
* element candidates generated and contributed to structural RRF, but **zero** entered final top-k — mathematically expected because
  `max structural-only = 0.30/61 = 0.004918` < `weakest semantic top-5 = 0.70/65 = 0.010769`.
* top-k set never changed; one NOT_DISCRIMINATING question had an order-only swap (hybrid rank shift); no gold movement, harmful transition or answer change; both runs byte-identical.

This sweep keeps every one of those factors fixed and varies **only** the two fusion weights.

---

## 3. Experimental Matrix

Swept configurations (only the weights differ):

| config | semantic | structural | k | top_k | admission mathematically possible |
|---|---:|---:|---:|---:|---|
| `sw070_st030` | 0.70 | 0.30 | 60 | 5 | no |
| `sw055_st045` | 0.55 | 0.45 | 60 | 5 | no |
| `sw050_st050` | 0.50 | 0.50 | 60 | 5 | yes |
| `sw040_st060` | 0.40 | 0.60 | 60 | 5 | yes |

Fixed across all runs: corpus, question set, annotations, parser, persisted structure, chunker, embeddings, QA model, `k=60`, `top_k=5`, database, candidate-generation logic, evidence-fusion logic, evaluation metrics, and the CONTROL/TREATMENT definition (CONTROL disables only `retrieve_structural_element_candidates`).

### CONTROL/TREATMENT isolation verification

For every configuration the harness verifies that the two arms differ **only** in the element candidate stream: the semantic stream, the chunk-level structural stream and the element seed set are recorded identically for both arms, and CONTROL's element stream is empty.

| config | semantic identical | chunk-structural identical | element seeds identical | CONTROL element stream empty | arms differ only in element stream |
|---|---|---|---|---|---|
| `sw070_st030` | True | True | True | True | True |
| `sw055_st045` | True | True | True | True | True |
| `sw050_st050` | True | True | True | True | True |
| `sw040_st060` | True | True | True | True | True |

### Compact comparison across all four weights

| config | structural | element admission (n) | top-k set changed | rank order changed | gold changed | answer changed | harmful transitions | classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `sw070_st030` | 0.30 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| `sw055_st045` | 0.45 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| `sw050_st050` | 0.50 | 30 | 30 | 30 | 15 | 5 | 0 | PROMISING |
| `sw040_st060` | 0.60 | 41 | 41 | 41 | 21 | 7 | 0 | — |

---

## 4. Theoretical Threshold

For a structural-only candidate at structural rank 1: `structural_weight/(k+1)`.
For the weakest semantic candidate in top-k: `semantic_weight/(k+top_k)`.

With `k=60`, `top_k=5`, `semantic + structural = 1`, admission of a rank-1 structural-only candidate requires

```text
structural_weight / 61  >  (1 - structural_weight) / 65
structural_weight > (k+1)/(2k+top_k+1) = 61/126 = 0.484127
```

**Theoretical threshold: structural_weight > 0.484127** (equivalently semantic_weight < 0.515873).

Per-configuration theory:

| config | structural | st/(k+1) | sw/(k+top_k) | mathematically possible |
|---|---:|---:|---:|---|
| `sw070_st030` | 0.30 | 0.004918 | 0.010769 | no |
| `sw055_st045` | 0.45 | 0.007377 | 0.008462 | no |
| `sw050_st050` | 0.50 | 0.008197 | 0.007692 | yes |
| `sw040_st060` | 0.60 | 0.009836 | 0.006154 | yes |

Comparison with the empirical sweep (§5): the theoretical threshold is a lower bound on difficulty — it assumes the weakest top-k occupant is a pure rank-5 semantic candidate. In practice the top-5 often contains *hybrid* candidates whose fusion score exceeds `sw/65`, so real admission can require a higher structural prior than the threshold. The five stages are reported separately below:

* mathematically possible (§4);
* candidate actually generated (§5);
* candidate actually enters top-k (§5/§6);
* candidate changes gold evidence (§6);
* candidate changes answer quality (§8/§10).

---

## 5. Reachability Results

Funnel per configuration (counts of questions, TREATMENT / CONTROL).

### `sw070_st030` (semantic 0.70 / structural 0.30)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 72 | 72 |
| questions_with_persisted_structure | 64 | 64 |
| questions_with_structural_seed | 63 | 63 |
| questions_with_structural_candidates | 63 | 0 |
| questions_with_structural_candidate_rrf_contribution | 63 | 0 |
| questions_with_structure_element_in_final_top_k | 0 | 0 |
| questions_with_structure_element_supplied_to_qa | 72 | 72 |
| questions_where_supplied_structure_overlaps_gold_evidence | 62 | 62 |

* element admission (element in final top-k): **0** question(s) (rate 0.000000); ids none
* structural-only admission rate (eligible questions): 0.000000
* hybrid structural influence (rank-order changed via hybrid shift): 0.000000

### `sw055_st045` (semantic 0.55 / structural 0.45)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 72 | 72 |
| questions_with_persisted_structure | 64 | 64 |
| questions_with_structural_seed | 63 | 63 |
| questions_with_structural_candidates | 63 | 0 |
| questions_with_structural_candidate_rrf_contribution | 63 | 0 |
| questions_with_structure_element_in_final_top_k | 0 | 0 |
| questions_with_structure_element_supplied_to_qa | 72 | 72 |
| questions_where_supplied_structure_overlaps_gold_evidence | 62 | 62 |

* element admission (element in final top-k): **0** question(s) (rate 0.000000); ids none
* structural-only admission rate (eligible questions): 0.000000
* hybrid structural influence (rank-order changed via hybrid shift): 0.000000

### `sw050_st050` (semantic 0.50 / structural 0.50)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 72 | 72 |
| questions_with_persisted_structure | 64 | 64 |
| questions_with_structural_seed | 63 | 63 |
| questions_with_structural_candidates | 63 | 0 |
| questions_with_structural_candidate_rrf_contribution | 63 | 0 |
| questions_with_structure_element_in_final_top_k | 30 | 0 |
| questions_with_structure_element_supplied_to_qa | 72 | 72 |
| questions_where_supplied_structure_overlaps_gold_evidence | 63 | 63 |

* element admission (element in final top-k): **30** question(s) (rate 0.416667); ids ['ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'at_ds_1', 'at_mh_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_mh_1', 'fs_pg_1', 'fs_sec_1', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']
* structural-only admission rate (eligible questions): 0.476190
* hybrid structural influence (rank-order changed via hybrid shift): 0.416667

### `sw040_st060` (semantic 0.40 / structural 0.60)

| stage | TREATMENT | CONTROL |
|---|---:|---:|
| questions | 72 | 72 |
| questions_with_persisted_structure | 64 | 64 |
| questions_with_structural_seed | 63 | 63 |
| questions_with_structural_candidates | 63 | 0 |
| questions_with_structural_candidate_rrf_contribution | 63 | 0 |
| questions_with_structure_element_in_final_top_k | 41 | 0 |
| questions_with_structure_element_supplied_to_qa | 72 | 72 |
| questions_where_supplied_structure_overlaps_gold_evidence | 62 | 62 |

* element admission (element in final top-k): **41** question(s) (rate 0.569444); ids ['ac_tbl_2', 'ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'ar_sem_1', 'at_ds_1', 'at_mh_1', 'at_pg_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_1', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_ds_4', 'fs_mh_1', 'fs_pg_1', 'fs_pg_2', 'fs_sec_1', 'fs_sec_2', 'fs_sec_3', 'fs_tbl_4', 'fs_tbl_5', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_sem_1', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']
* structural-only admission rate (eligible questions): 0.650794
* hybrid structural influence (rank-order changed via hybrid shift): 0.569444

---

## 6. Ranking Influence

Explicitly separated (never collapsed into one metric):

| config | 1. element enters top-k | 2. indirect rank change | 3. top-k set changes | 4. gold evidence changes | 5. answer changes | beneficial | harmful |
|---|---:|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sw055_st045` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sw050_st050` | 30 | 0 | 30 | 15 | 5 | 0 | 0 |
| `sw040_st060` | 41 | 0 | 41 | 21 | 7 | 0 | 0 |

* `sw050_st050`: element enters top-k: ['ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'at_ds_1', 'at_mh_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_mh_1', 'fs_pg_1', 'fs_sec_1', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']; top-k set change: ['ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'at_ds_1', 'at_mh_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_mh_1', 'fs_pg_1', 'fs_sec_1', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']; gold change: ['ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'at_ds_1', 'at_mh_1', 'at_sec_1', 'at_sec_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'fs_ds_3', 'fs_mh_1', 'os_sec_2']; answer change: ['ac_tbl_5', 'at_sec_2', 'fs_mh_1', 'fs_sec_1', 'os_tbl_2']
* `sw040_st060`: element enters top-k: ['ac_tbl_2', 'ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'ar_sem_1', 'at_ds_1', 'at_mh_1', 'at_pg_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_1', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_ds_4', 'fs_mh_1', 'fs_pg_1', 'fs_pg_2', 'fs_sec_1', 'fs_sec_2', 'fs_sec_3', 'fs_tbl_4', 'fs_tbl_5', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_sem_1', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']; top-k set change: ['ac_tbl_2', 'ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'ar_sem_1', 'at_ds_1', 'at_mh_1', 'at_pg_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_sec_6', 'at_sem_1', 'at_sem_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'at_una_2', 'fs_ds_1', 'fs_ds_2', 'fs_ds_3', 'fs_ds_4', 'fs_mh_1', 'fs_pg_1', 'fs_pg_2', 'fs_sec_1', 'fs_sec_2', 'fs_sec_3', 'fs_tbl_4', 'fs_tbl_5', 'os_mh_6', 'os_pg_2', 'os_sec_2', 'os_sem_1', 'os_tbl_1', 'os_tbl_2', 'os_tbl_3', 'os_tbl_4', 'os_tbl_5']; gold change: ['ac_tbl_2', 'ac_tbl_3', 'ac_tbl_4', 'ac_tbl_5', 'ar_pg_2', 'ar_sem_1', 'at_ds_1', 'at_mh_1', 'at_pg_2', 'at_sec_1', 'at_sec_2', 'at_tbl_1', 'at_tbl_2', 'at_tbl_3', 'at_tbl_4', 'fs_ds_3', 'fs_ds_4', 'fs_mh_1', 'os_mh_6', 'os_pg_2', 'os_sec_2']; answer change: ['ac_tbl_5', 'at_tbl_2', 'fs_mh_1', 'fs_pg_2', 'fs_sec_1', 'os_mh_6', 'os_tbl_2']

Per-population ranking effects (CONTROL vs TREATMENT):

| config | population | n | top-k changed | rank order changed | gold entered | gold left | beneficial | harmful | neutral |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | DISCRIMINATING_answerable | 32 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 32 |
| `sw070_st030` | all_answerable | 64 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 64 |
| `sw070_st030` | all | 72 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 72 |
| `sw055_st045` | DISCRIMINATING_answerable | 32 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 32 |
| `sw055_st045` | all_answerable | 64 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 64 |
| `sw055_st045` | all | 72 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0 | 72 |
| `sw050_st050` | DISCRIMINATING_answerable | 32 | 0.531250 | 0.531250 | 0.156250 | 0.000000 | 0 | 0 | 32 |
| `sw050_st050` | all_answerable | 64 | 0.453125 | 0.453125 | 0.234375 | 0.000000 | 0 | 0 | 64 |
| `sw050_st050` | all | 72 | 0.416667 | 0.416667 | 0.208333 | 0.000000 | 0 | 0 | 72 |
| `sw040_st060` | DISCRIMINATING_answerable | 32 | 0.687500 | 0.687500 | 0.281250 | 0.000000 | 0 | 0 | 32 |
| `sw040_st060` | all_answerable | 64 | 0.625000 | 0.625000 | 0.328125 | 0.015625 | 0 | 0 | 64 |
| `sw040_st060` | all | 72 | 0.569444 | 0.569444 | 0.291667 | 0.013889 | 0 | 0 | 72 |

---

## 7. Retrieval Metrics

Primary gold view `evidence_unit`. Metric definitions unchanged (`evaluation/retrieval_metrics.py`).

### DISCRIMINATING_answerable

| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | CONTROL | 32 | 0.484375 | 0.268750 | 0.703125 | 0.485905 | 1.000000 |
| `sw070_st030` | TREATMENT | 32 | 0.484375 | 0.268750 | 0.703125 | 0.485905 | 1.000000 |
| `sw055_st045` | CONTROL | 32 | 0.484375 | 0.268750 | 0.635417 | 0.454407 | 1.000000 |
| `sw055_st045` | TREATMENT | 32 | 0.484375 | 0.268750 | 0.635417 | 0.454407 | 1.000000 |
| `sw050_st050` | CONTROL | 32 | 0.484375 | 0.268750 | 0.635417 | 0.451212 | 1.000000 |
| `sw050_st050` | TREATMENT | 32 | 0.554688 | 0.300000 | 0.635417 | 0.485581 | 1.000000 |
| `sw040_st060` | CONTROL | 32 | 0.484375 | 0.268750 | 0.614583 | 0.446770 | 1.000000 |
| `sw040_st060` | TREATMENT | 32 | 0.617188 | 0.325000 | 0.614583 | 0.512469 | 1.000000 |

### WEAKLY_DISCRIMINATING_answerable

| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | CONTROL | 24 | 0.491667 | 0.266667 | 0.743056 | 0.519087 | 1.000000 |
| `sw070_st030` | TREATMENT | 24 | 0.491667 | 0.266667 | 0.743056 | 0.519087 | 1.000000 |
| `sw055_st045` | CONTROL | 24 | 0.491667 | 0.266667 | 0.694444 | 0.496884 | 1.000000 |
| `sw055_st045` | TREATMENT | 24 | 0.491667 | 0.266667 | 0.694444 | 0.496884 | 1.000000 |
| `sw050_st050` | CONTROL | 24 | 0.491667 | 0.266667 | 0.680556 | 0.490194 | 1.000000 |
| `sw050_st050` | TREATMENT | 24 | 0.645833 | 0.350000 | 0.680556 | 0.573012 | 1.000000 |
| `sw040_st060` | CONTROL | 24 | 0.491667 | 0.266667 | 0.715278 | 0.505087 | 1.000000 |
| `sw040_st060` | TREATMENT | 24 | 0.666667 | 0.358333 | 0.715278 | 0.600953 | 1.000000 |

### NOT_DISCRIMINATING_answerable

| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | CONTROL | 8 | 0.500000 | 0.200000 | 0.770833 | 0.508217 | 1.000000 |
| `sw070_st030` | TREATMENT | 8 | 0.500000 | 0.200000 | 0.770833 | 0.508217 | 1.000000 |
| `sw055_st045` | CONTROL | 8 | 0.500000 | 0.200000 | 0.770833 | 0.508217 | 1.000000 |
| `sw055_st045` | TREATMENT | 8 | 0.500000 | 0.200000 | 0.770833 | 0.508217 | 1.000000 |
| `sw050_st050` | CONTROL | 8 | 0.500000 | 0.200000 | 0.791667 | 0.518252 | 1.000000 |
| `sw050_st050` | TREATMENT | 8 | 0.500000 | 0.200000 | 0.791667 | 0.518252 | 1.000000 |
| `sw040_st060` | CONTROL | 8 | 0.500000 | 0.200000 | 0.791667 | 0.518252 | 1.000000 |
| `sw040_st060` | TREATMENT | 8 | 0.562500 | 0.225000 | 0.791667 | 0.547902 | 1.000000 |

### all_answerable

| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | CONTROL | 64 | 0.489063 | 0.259375 | 0.726563 | 0.501137 | 1.000000 |
| `sw070_st030` | TREATMENT | 64 | 0.489063 | 0.259375 | 0.726563 | 0.501137 | 1.000000 |
| `sw055_st045` | CONTROL | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477062 | 1.000000 |
| `sw055_st045` | TREATMENT | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477062 | 1.000000 |
| `sw050_st050` | CONTROL | 64 | 0.489063 | 0.259375 | 0.671875 | 0.474210 | 1.000000 |
| `sw050_st050` | TREATMENT | 64 | 0.582031 | 0.306250 | 0.671875 | 0.522452 | 1.000000 |
| `sw040_st060` | CONTROL | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477575 | 1.000000 |
| `sw040_st060` | TREATMENT | 64 | 0.628906 | 0.325000 | 0.674479 | 0.550080 | 1.000000 |

### all

| config | arm | n | Recall@5 | Precision@5 | MRR | nDCG@5 | evidence coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| `sw070_st030` | CONTROL | 64 | 0.489063 | 0.259375 | 0.726563 | 0.501137 | 1.000000 |
| `sw070_st030` | TREATMENT | 64 | 0.489063 | 0.259375 | 0.726563 | 0.501137 | 1.000000 |
| `sw055_st045` | CONTROL | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477062 | 1.000000 |
| `sw055_st045` | TREATMENT | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477062 | 1.000000 |
| `sw050_st050` | CONTROL | 64 | 0.489063 | 0.259375 | 0.671875 | 0.474210 | 1.000000 |
| `sw050_st050` | TREATMENT | 64 | 0.582031 | 0.306250 | 0.671875 | 0.522452 | 1.000000 |
| `sw040_st060` | CONTROL | 64 | 0.489063 | 0.259375 | 0.674479 | 0.477575 | 1.000000 |
| `sw040_st060` | TREATMENT | 64 | 0.628906 | 0.325000 | 0.674479 | 0.550080 | 1.000000 |

DELTA (TREATMENT − CONTROL), `evidence_unit`:

| config | population | ΔRecall@5 | ΔPrecision@5 | ΔMRR | ΔnDCG@5 |
|---|---|---:|---:|---:|---:|
| `sw070_st030` | DISCRIMINATING_answerable | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw070_st030` | all_answerable | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw070_st030` | all | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw055_st045` | DISCRIMINATING_answerable | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw055_st045` | all_answerable | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw055_st045` | all | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| `sw050_st050` | DISCRIMINATING_answerable | 0.070313 | 0.031250 | 0.000000 | 0.034369 |
| `sw050_st050` | all_answerable | 0.092968 | 0.046875 | 0.000000 | 0.048242 |
| `sw050_st050` | all | 0.092968 | 0.046875 | 0.000000 | 0.048242 |
| `sw040_st060` | DISCRIMINATING_answerable | 0.132813 | 0.056250 | 0.000000 | 0.065699 |
| `sw040_st060` | all_answerable | 0.139843 | 0.065625 | 0.000000 | 0.072505 |
| `sw040_st060` | all | 0.139843 | 0.065625 | 0.000000 | 0.072505 |

---

## 8. Answer Metrics

| config | population | arm | EM | token F1 | accuracy | grounding | unsupported rate |
|---|---|---|---:|---:|---:|---:|---:|
| `sw070_st030` | DISCRIMINATING_answerable | CONTROL | 0.250000 | 0.499960 | 0.625000 | 1.000000 | — |
| `sw070_st030` | DISCRIMINATING_answerable | TREATMENT | 0.250000 | 0.499960 | 0.625000 | 1.000000 | — |
| `sw070_st030` | all_answerable | CONTROL | 0.265625 | 0.530941 | 0.718750 | 1.000000 | — |
| `sw070_st030` | all_answerable | TREATMENT | 0.265625 | 0.530941 | 0.718750 | 1.000000 | — |
| `sw070_st030` | unanswerable | CONTROL | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw070_st030` | unanswerable | TREATMENT | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw070_st030` | all | CONTROL | 0.265625 | 0.530941 | 0.718750 | 1.000000 | 1.000000 |
| `sw070_st030` | all | TREATMENT | 0.265625 | 0.530941 | 0.718750 | 1.000000 | 1.000000 |
| `sw055_st045` | DISCRIMINATING_answerable | CONTROL | 0.250000 | 0.497182 | 0.593750 | 1.000000 | — |
| `sw055_st045` | DISCRIMINATING_answerable | TREATMENT | 0.250000 | 0.497182 | 0.593750 | 1.000000 | — |
| `sw055_st045` | all_answerable | CONTROL | 0.265625 | 0.529552 | 0.703125 | 1.000000 | — |
| `sw055_st045` | all_answerable | TREATMENT | 0.265625 | 0.529552 | 0.703125 | 1.000000 | — |
| `sw055_st045` | unanswerable | CONTROL | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw055_st045` | unanswerable | TREATMENT | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw055_st045` | all | CONTROL | 0.265625 | 0.529552 | 0.703125 | 1.000000 | 1.000000 |
| `sw055_st045` | all | TREATMENT | 0.265625 | 0.529552 | 0.703125 | 1.000000 | 1.000000 |
| `sw050_st050` | DISCRIMINATING_answerable | CONTROL | 0.218750 | 0.502333 | 0.593750 | 1.000000 | — |
| `sw050_st050` | DISCRIMINATING_answerable | TREATMENT | 0.250000 | 0.511004 | 0.593750 | 1.000000 | — |
| `sw050_st050` | all_answerable | CONTROL | 0.250000 | 0.532127 | 0.703125 | 1.000000 | — |
| `sw050_st050` | all_answerable | TREATMENT | 0.265625 | 0.528650 | 0.687500 | 1.000000 | — |
| `sw050_st050` | unanswerable | CONTROL | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw050_st050` | unanswerable | TREATMENT | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw050_st050` | all | CONTROL | 0.250000 | 0.532127 | 0.703125 | 1.000000 | 1.000000 |
| `sw050_st050` | all | TREATMENT | 0.265625 | 0.528650 | 0.687500 | 1.000000 | 1.000000 |
| `sw040_st060` | DISCRIMINATING_answerable | CONTROL | 0.218750 | 0.486308 | 0.562500 | 1.000000 | — |
| `sw040_st060` | DISCRIMINATING_answerable | TREATMENT | 0.250000 | 0.486645 | 0.562500 | 1.000000 | — |
| `sw040_st060` | all_answerable | CONTROL | 0.250000 | 0.518995 | 0.687500 | 1.000000 | — |
| `sw040_st060` | all_answerable | TREATMENT | 0.265625 | 0.511262 | 0.671875 | 1.000000 | — |
| `sw040_st060` | unanswerable | CONTROL | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw040_st060` | unanswerable | TREATMENT | — | — | 0.000000 | 1.000000 | 1.000000 |
| `sw040_st060` | all | CONTROL | 0.250000 | 0.518995 | 0.687500 | 1.000000 | 1.000000 |
| `sw040_st060` | all | TREATMENT | 0.265625 | 0.511262 | 0.671875 | 1.000000 | 1.000000 |

---

## 9. Category Analysis

| config | category | n | EM | token F1 | accuracy | element in top-k |
|---|---|---:|---:|---:|---:|---:|
| `sw070_st030` | multi_hop_structural | 8 | 0.000000 | 0.245833 | 0.375000 | 0 |
| `sw070_st030` | page_crossing | 8 | 0.500000 | 0.583333 | 0.625000 | 0 |
| `sw070_st030` | section_heading | 12 | 0.500000 | 0.722222 | 0.916667 | 0 |
| `sw070_st030` | semantic_control | 8 | 0.500000 | 0.729167 | 0.875000 | 0 |
| `sw070_st030` | structural_distractor | 8 | 0.125000 | 0.354167 | 0.500000 | 0 |
| `sw070_st030` | table_row_cell | 20 | 0.100000 | 0.500677 | 0.800000 | 0 |
| `sw070_st030` | unanswerable | 8 | — | — | 0.000000 | 0 |
| `sw055_st045` | multi_hop_structural | 8 | 0.000000 | 0.201389 | 0.250000 | 0 |
| `sw055_st045` | page_crossing | 8 | 0.500000 | 0.616667 | 0.625000 | 0 |
| `sw055_st045` | section_heading | 12 | 0.500000 | 0.722222 | 0.916667 | 0 |
| `sw055_st045` | semantic_control | 8 | 0.500000 | 0.729167 | 0.875000 | 0 |
| `sw055_st045` | structural_distractor | 8 | 0.125000 | 0.354167 | 0.500000 | 0 |
| `sw055_st045` | table_row_cell | 20 | 0.100000 | 0.500677 | 0.800000 | 0 |
| `sw055_st045` | unanswerable | 8 | — | — | 0.000000 | 0 |
| `sw050_st050` | multi_hop_structural | 8 | 0.000000 | 0.239850 | 0.250000 | 3 |
| `sw050_st050` | page_crossing | 8 | 0.500000 | 0.616667 | 0.625000 | 4 |
| `sw050_st050` | section_heading | 12 | 0.500000 | 0.722222 | 0.916667 | 5 |
| `sw050_st050` | semantic_control | 8 | 0.500000 | 0.729167 | 0.875000 | 1 |
| `sw050_st050` | structural_distractor | 8 | 0.125000 | 0.354167 | 0.500000 | 4 |
| `sw050_st050` | table_row_cell | 20 | 0.100000 | 0.482407 | 0.750000 | 12 |
| `sw050_st050` | unanswerable | 8 | — | — | 0.000000 | 1 |
| `sw040_st060` | multi_hop_structural | 8 | 0.000000 | 0.175748 | 0.125000 | 3 |
| `sw040_st060` | page_crossing | 8 | 0.500000 | 0.583333 | 0.625000 | 6 |
| `sw040_st060` | section_heading | 12 | 0.500000 | 0.722222 | 0.916667 | 7 |
| `sw040_st060` | semantic_control | 8 | 0.500000 | 0.687500 | 0.875000 | 4 |
| `sw040_st060` | structural_distractor | 8 | 0.125000 | 0.354167 | 0.500000 | 5 |
| `sw040_st060` | table_row_cell | 20 | 0.100000 | 0.482407 | 0.750000 | 15 |
| `sw040_st060` | unanswerable | 8 | — | — | 0.000000 | 1 |

---

## 10. Transition Analysis

Correctness threshold `token F1 ≥ 0.5` (same as `answer_accuracy`).

| config | population | correct→correct | correct→wrong | wrong→correct | wrong→wrong |
|---|---|---:|---:|---:|---:|
| `sw070_st030` | DISCRIMINATING_answerable | 20 | 0 | 0 | 12 |
| `sw070_st030` | all_answerable | 46 | 0 | 0 | 18 |
| `sw070_st030` | all | 46 | 0 | 0 | 18 |
| `sw055_st045` | DISCRIMINATING_answerable | 19 | 0 | 0 | 13 |
| `sw055_st045` | all_answerable | 45 | 0 | 0 | 19 |
| `sw055_st045` | all | 45 | 0 | 0 | 19 |
| `sw050_st050` | DISCRIMINATING_answerable | 19 | 0 | 0 | 13 |
| `sw050_st050` | all_answerable | 44 | 1 | 0 | 19 |
| `sw050_st050` | all | 44 | 1 | 0 | 19 |
| `sw040_st060` | DISCRIMINATING_answerable | 18 | 0 | 0 | 14 |
| `sw040_st060` | all_answerable | 43 | 1 | 0 | 20 |
| `sw040_st060` | all | 43 | 1 | 0 | 20 |

---

## 11. Determinism

Two independent complete runs (user/ingest/measure/teardown), identical deterministic-id seed, with the existing normalisations preserved (model warm-up outside the id region; semantic stream re-sorted by `(-similarity, chunk_id)`).

* runs compared: **2**
* core payload byte-identical: **True**
* run 1 SHA-256: `4b09b8fa24b7af1d647f7983544661b5227ffe8bd6fbd8ae7e5fc7491a5105fd`
* run 2 SHA-256: `4b09b8fa24b7af1d647f7983544661b5227ffe8bd6fbd8ae7e5fc7491a5105fd`

---

## 12. Limitations

* **Weight injection is harness-side.** Production `chat/rag.py` fusion is untouched; the sweep calls the unmodified `fuse_dual_path` with explicit weights. Results therefore describe the current architecture with a different prior, not a modified production system.
* **Only the RRF prior is varied.** Candidate generation, gold annotations, evidence fusion and the corpus are unchanged, so a failure to improve cannot be attributed to those components — but it also cannot rule out that the corpus/question design or structural evidence quality is the limiting factor.
* **Shared augmentation stream.** The post-ranking `_augment_with_structure` element stream is present in both arms, so only the *ranked* element contribution is isolated.
* **Four discrete weights.** The exact crossover may lie between the swept points; the theoretical threshold is analytic, the sweep is coarse.
* **Single corpus, no evidence gate, one `top_k`.**

---

## 13. Selected Configuration

* theoretical threshold structural_weight > 0.484127
* configs with any element admission: ['sw050_st050', 'sw040_st060']
* **selected (smallest structural weight with non-zero element admission): `sw050_st050`**
* **classification: PROMISING**
* primary DISCRIMINATING retrieval delta: {"mrr": 0.0, "n": 0.0, "ndcg@5": 0.034369, "precision@5": 0.03125, "recall@5": 0.070313}
* primary answer delta: {"answer_accuracy": 0.0, "exact_match_rate": 0.03125, "factual_grounding_rate": 0.0, "n": 0.0, "n_answerable": 0.0, "token_f1": 0.008671, "unsupported_answer_rate": null}
* harmful transitions: 0, positive movement: True
* selected the smallest structural weight with non-zero element admission; classification is based on the primary DISCRIMINATING subset, not on admission count

---

## 14. Research Interpretation

This experiment does **not** prove the structural hypothesis. It establishes only whether the current architecture can expose structural evidence to ranking and what happens when its prior is calibrated.

**Observed:** at the selected prior, structural admission occurred with positive retrieval/answer movement and no harmful transitions on the primary DISCRIMINATING subset. This is a promising signal only — it is **not** proof of the structural hypothesis. Preserve the exact evidence and run a confirmation experiment before any conclusion.

---

## 15. Exact Next Experiment

**Confirmation experiment (single change, same corpus).** Repeat this CONTROL/TREATMENT measurement at the selected prior with two independent runs and a held-out question split of the same corpus (or a small second corpus with independently authored structural gold), keeping parser, embeddings, QA model, `k=60` and `top_k=5` fixed. Accept only if the primary DISCRIMINATING retrieval and answer gains reproduce with zero harmful transitions. Do not touch production weights until confirmed.

No parser, schema, corpus, QA-model or embeddings change is part of the next experiment.
