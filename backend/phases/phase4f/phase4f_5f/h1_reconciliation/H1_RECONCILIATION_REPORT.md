# PHASE 4F.5-H1-R — H1 RECONCILIATION REPORT

**Date:** 2026-09-22
**Status:** VALID_WITH_LIMITATIONS
**Type:** Read-only audit — no production changes, no retraining, no code modifications

---

## 1. Executive Summary

The Phase 4F.5-H1 experiment (document-grounded negative training with 114 H20 unanswerable examples) was audited for protocol fidelity. The experiment was executed correctly on all primary evaluation surfaces (frozen benchmark: 182 examples). The holdout discrepancy (22 vs 14) is explained by a split-index mismatch in `get_holdout_examples()` and does not affect the benchmark conclusions. The model collapsed: EM dropped to 0.0% (from F2's 2.9%), F1 dropped to 11.0% (from 19.7%), and while abstention rose to 45.2%, spurious rate simultaneously rose to 54.8%. The null-score analysis confirms the CLS/no-answer signal is essentially random (mean null margin: -0.000344). H1 is **VALID_WITH_LIMITATIONS** — the benchmark results are reliable but the holdout diagnostic is slightly inflated.

---

## 2. H1 Protocol as Intended

| Parameter | Value |
|---|---|
| Model | distilbert-base-uncased (fresh init) |
| Tokenizer | distilbert-base-uncased |
| Max sequence length | 384 |
| Learning rate | 3e-5 |
| Epochs | 3 |
| Batch (physical/effective) | 8 / 64 |
| FP16 | Yes |
| Weight decay | 0.01 |
| Warmup ratio | 0.1 |
| Seed | 42 |
| Training: answerable | 486 |
| Training: unanswerable | 114 (H20) |
| Training: total | 600 |
| Validation: answerable | 85 |
| Validation: unanswerable | 8 |
| Validation: total | 93 |
| Holdout | 14 unanswerable (frozen) |
| Benchmark | 182 (140 answerable + 42 unanswerable) |
| Checkpoint selection | Best validation EM |
| No-answer decision | Raw argmax (no threshold) |

---

## 3. H1 Protocol as Actually Executed

All hyperparameters, data sources, and code paths match the intended protocol exactly. The three discrepancies are:

1. **Holdout count: 22 instead of 14** (see §4)
2. **Validation unanswerable IDs differ** from the F1 reconciliation specification (6 of 8 IDs differ)
3. **12 unanswerable examples** (indices 8-19 in sorted order) are placed in neither training, validation, nor holdout

All frozen artifact hashes are verified:
- Source dataset: ✅ VERIFIED
- Derived dataset: ✅ VERIFIED
- Benchmark: ✅ VERIFIED
- H20 pool: ✅ VERIFIED
- Production model: ✅ UNCHANGED

---

## 4. Holdout Discrepancy Investigation

### The Problem
The H1 report states: expected holdout = 14, actual holdout = 22.

### Root Cause
In `run_h1.py`, the function `get_holdout_examples()` has a default parameter `val_unanswerable_count=20` and returns `val_unanswerable_sorted[20:]`, yielding **42 − 20 = 22** holdout examples.

The F1 reconciliation protocol defines the split at index **28** (20 for experiment pool + 8 for validation), yielding **42 − 28 = 14** holdout examples.

The H1 code does not use the 20 derived unanswerable in training (H20 replaces them entirely), but it still uses the old split index of 20 as the boundary.

### Which 22 examples are in the holdout?
All 42 derived unanswerable, sorted by example_id:

| Index Range | Count | Placement |
|---|---|---|
| 0-7 | 8 | Validation (first 8 by ID) |
| 8-19 | 12 | **UNUSED** (neither training, validation, nor holdout) |
| 20-41 | 22 | Holdout |

The 12 unaccounted examples are: unans_20bbdfeb, unans_20e56903, unans_29bba51a, unans_2a3dd2f6, unans_39b0bf0c, unans_3a0430bc, unans_3b23eb33, unans_422d6ea0, unans_4725a75e, unans_496d4272, unans_520918ca, unans_63ece8c5.

### Effect on Conclusions
**LOW.** The benchmark evaluation (182 frozen examples) is completely independent of the holdout split. The holdout is a secondary diagnostic. If only the protocol-correct 14 examples are considered, the holdout abstention would be approximately 35.7% (5/14), directionally consistent with the reported 36.4% (8/22).

---

## 5. Dataset Count Reconciliation

| Metric | Expected | Actual | Diff | Explanation |
|---|---|---|---|---|
| Answerable train | 486 | 486 | 0 | F1 reconciled split |
| Unanswerable train | 114 | 114 | 0 | H20 document-grounded |
| Total train | 600 | 600 | 0 | 486 + 114 |
| Answerable validation | 85 | 85 | 0 | F1 reconciled split |
| Unanswerable validation | 8 | 8 | 0 | First 8 by ID |
| Total validation | 93 | 93 | 0 | 85 + 8 |
| Held-out unanswerable | 14 | 22 | +8 | Split index mismatch (20 vs 28) |
| Benchmark answerable | 140 | 140 | 0 | Frozen |
| Benchmark unanswerable | 42 | 42 | 0 | Frozen |
| Benchmark total | 182 | 182 | 0 | Frozen |

---

## 6. Leakage / Contamination Audit

| Pair | Example-Level Overlap | Status |
|---|---|---|
| Train ↔ Validation | 0 | ✅ CLEAN |
| Train ↔ Holdout | 0 | ✅ CLEAN |
| Train ↔ Benchmark | 0 | ✅ CLEAN |
| Validation ↔ Holdout | 0 | ✅ CLEAN |
| Validation ↔ Benchmark (answerable) | 0 | ✅ CLEAN |
| Validation ↔ Benchmark (unanswerable) | 8 | EXPECTED BY DESIGN |
| Holdout ↔ Benchmark (unanswerable) | 22 | EXPECTED BY DESIGN |

The validation-to-benchmark and holdout-to-benchmark overlaps are by design: the benchmark was constructed to include all 42 derived unanswerable examples, and validation/holdout sample from this same pool.

H20 training examples have **zero overlap** with any other split (validation, holdout, or benchmark).

**Overall: NO ILLEGAL LEAKAGE.**

---

## 7. Label Integrity Audit

### Answerable examples
- 571 total (486 train + 85 val) — all have `token_span.valid = True`
- 0 examples with `start_token = 0` (CLS) — no accidental CLS labeling
- 0 examples with `is_impossible = True`
- 4 excluded examples (invalid token_span) are correctly removed from all splits

### Unanswerable examples
- 114 H20 training: all have `answer=""`, `token_span=null`, `is_unanswerable=True`, `question_kind="UNANSWERABLE"`
- 8 derived validation: all have `answer=""`, `token_span=null`, `question_kind="UNANSWERABLE"`
- 22 derived holdout: all have `answer=""`, `token_span=null`, `question_kind="UNANSWERABLE"`
- No answer span accidentally supplied

**LABEL INTEGRITY: PASS**

---

## 8. No-Answer Decision Mechanism Audit

H1 uses **raw argmax** over start/end logits. The predicted answer is decoded from the token span between argmax start and end positions. If the decoded string is empty, the model abstains.

- **No threshold** is applied
- **No null-score comparison** is used for the decision
- **No margin rule** is used

The null_score (CLS start + CLS end) / 2 is computed and saved for diagnostics but plays no role in the answer/abstain decision.

### Decision Breakdown

| Split | Total | Correct Answer | False Abstain | Correct Abstain | Spurious |
|---|---|---|---|---|---|
| Validation | 93 | 0 | 0 | 4 | 4 |
| Holdout | 22 | — | — | 8 | 14 |
| Benchmark | 182 | 0 | 15 | 19 | 23 |

---

## 9. Metric Recalculation

All metrics from the saved prediction artifacts match the reported values exactly:

| Metric | Benchmark Reported | Recalculated | Match |
|---|---|---|---|
| EM | 0.0% | 0.0% | ✅ |
| F1 | 11.0% | 11.0% | ✅ |
| Answerable EM | 0.0% | 0.0% | ✅ |
| Answerable F1 | 11.0% | 11.0% | ✅ |
| Abstention (unanswerable) | 45.2% | 45.2% | ✅ |
| Spurious (unanswerable) | 54.8% | 54.8% | ✅ |
| False abstention | 10.7% | 10.7% | ✅ |

### By Category (Benchmark)

| Category | n | EM | F1 |
|---|---|---|---|
| DIRECT_SPAN | 24 | 0.0% | 13.0% |
| TABLE_CELL | 24 | 0.0% | 5.8% |
| TABLE_ROW | 16 | 0.0% | 18.0% |
| LIST_ITEM | 20 | 0.0% | 12.9% |
| NUMERIC | 20 | 0.0% | 22.6% |
| SECTION_SPECIFIC | 16 | 0.0% | 3.2% |
| MULTI_CHUNK | 10 | 0.0% | 3.0% |
| LONG_CONTEXT | 10 | 0.0% | 1.6% |
| UNANSWERABLE | 42 | 0.0% | 0.0% |

Categories absent from benchmark: DATE, ENTITY.

**METRIC RECALCULATION: PASS**

---

## 10. Null-Score Analysis

### Claimed vs Computed

| Metric | Claimed | Computed | Match |
|---|---|---|---|
| mean null_score (unanswerable) | 0.00395 | 0.003950 | ✅ |
| mean null_margin (unanswerable) | -0.000344 | -0.000344 | ✅ |

### Distributions

| Statistic | Answerable (n=140) | Unanswerable (n=42) |
|---|---|---|
| null_score mean | 0.003913 | 0.003950 |
| null_score median | 0.003917 | 0.003962 |
| null_score std | 0.000155 | 0.000140 |
| null_score min | 0.003462 | 0.003651 |
| null_score max | 0.004275 | 0.004308 |
| best_answer mean | 0.004521 | 0.004294 |
| null_margin mean | -0.000608 | -0.000344 |
| positive margin count | — | 3/42 (7.1%) |

### Interpretation

The null-score distributions for answerable and unanswerable examples are **nearly identical** (mean difference: 0.000037, less than 0.25 standard deviations). Only 3 out of 42 unanswerable examples have a positive null margin (CLS preferred over content). The CLS/no-answer signal is essentially random noise. No threshold or margin rule could achieve meaningful separation between answerable and unanswerable examples.

**NULL SIGNAL RECALCULATION: PASS** (reported values correct; no useful signal present)

---

## 11. Comparison with Prior Experiments

| Experiment | Training | EM | F1 | False Abstain | Unans. Abstain | Spurious | Status |
|---|---|---|---|---|---|---|---|
| A0 (Production) | Prod. set | 2.1% | 12.0% | — | 64.3% | 8.2% | Baseline |
| A1 (DistilBERT) | 571 answerable | 3.6% | 21.3% | 0.0% | 0.0% | 23.1% | No abstention |
| A2 (BERT-base) | 571 answerable | 0.0% | 9.3% | 0.0% | 0.0% | 4.6% | No abstention |
| F2 (reconciled) | 486 ans + 20 unans | 2.9% | 19.7% | 0.0% | 0.0% | 23.1% | No abstention |
| G (threshold) | F2 + threshold | 2.9% | 16.9% | 27.9% | 19.1% | 81.0% | Unstable threshold |
| H1 (grounded) | 486 ans + 114 H20 | 0.0% | 11.0% | 10.7% | 45.2% | 54.8% | Model collapsed |

### Tradeoff Description (No Ranking)

- **A0** has the best abstention/spurious balance (64.3%/8.2%) but this reflects production model bias, not learned abstention.
- **A1** has the highest answerable F1 (21.3%) but zero abstention — always predicts something.
- **F2** retains most of A1's F1 (19.7%) with zero abstention — 20 synthetic unanswerables had no effect.
- **H1** shows the highest abstention (45.2%) but with catastrophic spurious rate (54.8%) and complete answerable collapse (EM 0.0%, F1 11.0%).
- **G** shows that even with the best threshold, the F2 model cannot separate answerable/unanswerable distributions.

---

## 12. Evidence Classification

| Claim | Classification |
|---|---|
| "H10 negatives cause DistilBERT to collapse" | **SUPPORTED BY EVIDENCE** — EM drops from 2.9% to 0.0%, F1 from 19.7% to 11.0% |
| "114 H20 negatives improve abstention" | **SUPPORTED BY EVIDENCE** — abstention rises from 0% (F2) to 45.2% (H1) |
| "Improved abstention is targeted" | **NOT SUPPORTED** — spurious rate simultaneously rises from 23.1% to 54.8%, and 10.7% of answerable questions are falsely abstained |
| "The CLS/no-answer signal is useful" | **NOT SUPPORTED** — null margins are near-zero (mean -0.000344), distributions overlap completely |
| "DistilBERT is fundamentally incapable" | **NOT YET ESTABLISHED** — only tested with H20 negatives; other negative types or training strategies untested |
| "20 negatives are insufficient" | **PLAUSIBLE HYPOTHESIS** — F2 with 20 showed no effect; H1 with 114 showed catastrophic effect; the optimal count is unknown |
| "H20 negatives are too different from answerable" | **PLAUSIBLE HYPOTHESIS** — H20 questions span 17 documents with complex multi-step reasoning; DistilBERT may lack capacity to learn the distinction |
| "Hybrid QA is required" | **NOT YET ESTABLISHED** — no hybrid architecture tested |

---

## 13. What Is Proven

1. The H1 benchmark results (EM 0.0%, F1 11.0%, abstention 45.2%, spurious 54.8%) are **reproducible and correctly computed**.
2. The holdout discrepancy (22 vs 14) is **fully explained** by a split-index mismatch in `get_holdout_examples()`.
3. There is **no data leakage** between training and any evaluation set.
4. All labels are **correctly assigned** (answerable get real spans, unanswerable get CLS).
5. The H10 negatives **do not teach targeted abstention** — the model collapses.
6. The CLS/no-answer signal is **statistically random** with no separability between answerable and unanswerable.

---

## 14. What Is Only Hypothesized

1. That H20 negatives are "too different" for DistilBERT to learn from (plausible but untested with other models).
2. That a different negative count (e.g., 30-50) might find a productive middle ground (untested).
3. That a larger model (BERT-base, DeBERTa) might handle H20 negatives better (A2 tested BERT-base without negatives; not tested with H20).
4. That curriculum learning or category-subset training could help (untested).

---

## 15. Required Next Step

The H1 experiment conclusively demonstrates that naively adding 114 H20 document-grounded negatives to DistilBERT training causes model collapse without producing useful abstention. The next experiment should:

1. **Test with fewer negatives** (e.g., 20-30 from H20) to find the boundary between "no effect" (F2) and "catastrophic collapse" (H1).
2. **Test with a stronger model** (BERT-base or DeBERTa) to determine whether the collapse is capacity-limited.
3. **Test category-subset negatives** (e.g., only ABSENT_FACT and UNSUPPORTED_NUMBER, which are more similar to answerable questions).
4. **Fix the holdout split** to use index 28 instead of 20 for protocol consistency.
5. **Account for the 12 dropped unanswerable examples** — either include them in the experiment pool or explicitly document their exclusion.

---

## 16. Evidence Summary

```
PHASE: 4F.5-H1-R
STATUS: VALID_WITH_LIMITATIONS

H1_HOLDOUT_EXPECTED: 14
H1_HOLDOUT_ACTUAL: 22

TRAIN_EXPECTED: 600
TRAIN_ACTUAL: 600

VALIDATION_EXPECTED: 93
VALIDATION_ACTUAL: 93

BENCHMARK_EXPECTED: 182
BENCHMARK_ACTUAL: 182

TRAIN_VALIDATION_LEAKAGE: 0
TRAIN_HOLDOUT_LEAKAGE: 0
TRAIN_BENCHMARK_LEAKAGE: 0
VALIDATION_HOLDOUT_LEAKAGE: 0
VALIDATION_BENCHMARK_LEAKAGE: 0 (answerable), 8 (unanswerable, by design)
HOLDOUT_BENCHMARK_LEAKAGE: 22 (unanswerable, by design)

LABEL_INTEGRITY: PASS
METRIC_RECALCULATION: PASS
NULL_SIGNAL_RECALCULATION: PASS

SUPPORTED_CONCLUSION:
H1 conclusively demonstrates that adding 114 H20 document-grounded
unanswerable negatives to DistilBERT training causes answerable
performance collapse (EM 0.0%, F1 11.0%) while producing untargeted
abstention (45.2% abstention but 54.8% spurious rate). The CLS/no-answer
signal is statistically indistinguishable from noise (mean null margin:
-0.000344). H20 negatives in their current form are not providing useful
training signal for DistilBERT.

UNRESOLVED:
Whether the collapse is caused by insufficient model capacity (DistilBERT
vs BERT-base), excessive negative count (114 vs 20-30), or fundamental
dissimilarity between H20 questions and answerable questions. These are
hypotheses requiring additional experiments. The 12 dropped unanswerable
examples and the holdout split discrepancy should be corrected in future
experiments.

NEXT_EXPERIMENT:
Test H20 negatives at reduced counts (20, 30, 50) on both DistilBERT and
BERT-base to find the productive operating range. Fix the holdout split
to use index 28. Consider category-subset negatives (ABSENT_FACT,
UNSUPPORTED_NUMBER) which are more similar to answerable questions.

PRODUCTION_MODEL_CHANGED: NO
FROZEN_DATASET_CHANGED: NO
FROZEN_BENCHMARK_CHANGED: NO
PRODUCTION_CHECKSUM_CHANGED: NO

NO COMMIT.
NO PUSH.
```

---

**Generated:** 2026-09-22
**Audit tool:** Phase 4F.5-H1-R reconciliation (read-only)
**Integrity:** All frozen artifacts verified unchanged. No code modified.
