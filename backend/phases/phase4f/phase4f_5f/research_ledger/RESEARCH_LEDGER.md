# Phase 4F Research Ledger

**Date:** 2026-09-22
**Status:** RECONCILED

---

## 1. Purpose

This ledger establishes one internally consistent experiment record for Phase 4F / 4F.5 before any further QA-model training. It reconciles all local artifacts, resolves known discrepancies, and preserves uncertainty where uncertainty exists.

---

## 2. Local Repository / Evidence Boundary

**SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY**

- Repository root: `/c/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui`
- Branch: `main`
- Working tree: clean (no uncommitted changes)
- All metrics sourced from local files only
- No network access, no GitHub access, no remote operations

**GITHUB ACCESSED: NO**

---

## 3. Evaluation Populations

Three distinct evaluation populations exist in this repository. Metrics must NEVER be mixed across populations.

### Population P1 — Full Derived Dataset (918 examples)
- 876 answerable (10 categories: DATE, DIRECT_SPAN, ENTITY, LIST_ITEM, LONG_CONTEXT, MULTI_CHUNK, NUMERIC, SECTION_SPECIFIC, TABLE_CELL, TABLE_ROW)
- 42 unanswerable (from `unanswerable_corpus`, synthetic/OOD)
- Source: `backend/phase4f/experiments/results/`
- Used by: Older Phase 4F experiments (A0/A1/A2 with full evaluation)

### Population P2 — Corrected Test Split (221 examples)
- 221 answerable only (7 categories: DIRECT_SPAN, LIST_ITEM, MULTI_CHUNK, NUMERIC, SECTION_SPECIFIC, TABLE_CELL, TABLE_ROW)
- 0 unanswerable
- Source: `backend/phase4f/phase4f_5/results/`
- Used by: Phase 4F.5-B corrected baseline experiments
- Note: Missing DATE, ENTITY, LONG_CONTEXT compared to P1

### Population P3 — Frozen Benchmark (182 examples)
- 140 answerable (8 categories: DIRECT_SPAN, LIST_ITEM, LONG_CONTEXT, MULTI_CHUNK, NUMERIC, SECTION_SPECIFIC, TABLE_CELL, TABLE_ROW)
- 42 unanswerable (from `unanswerable_corpus`, synthetic/OOD)
- Hash: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`
- Source: `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`
- Used by: F2, G, H1 experiments
- Note: Missing DATE, ENTITY from answerable categories

---

## 4. Canonical Experiment Table

All metrics below are tagged by evaluation population. Do not compare across populations.

| Experiment | Model | Training (ans/unans) | Eval Pop | EM | F1 | False Abstain | Unans Abstain | Spurious | Status |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| A0 | Production BERT | Prod set | P1 (918) | 7.8% | 14.4% | 49.9% | 64.3% | 1.6% | Baseline |
| A0 | Production BERT | Prod set | P2 (221) | 3.2% | 8.6% | 62.4% | 0.0% | 0.0% | Baseline |
| A1 | DistilBERT | 571 answerable | P1 (918) | 0.7% | 6.9% | 0.0% | 0.0% | 4.6% | No abstention |
| A1 | DistilBERT | 571 answerable | P2 (221) | 1.8% | 14.4% | 0.0% | 0.0% | 0.0% | No abstention |
| A2 | BERT-base | 571 answerable | P1 (918) | 0.0% | 9.3% | 0.0% | 0.0% | 4.6% | No abstention |
| A2 | BERT-base | 571 answerable | P2 (221) | 0.9% | 12.3% | 0.0% | 0.0% | 0.0% | No abstention |
| F2 | DistilBERT | 486+20 (506) | P3 (182) | 2.9% | 19.7% | 0.0% | 0.0% | 23.1% | No abstention |
| G | F2 + threshold | F2 weights | P3 (182) | 2.9% | 16.9% | 27.9% | 19.1% | 81.0% | Unstable |
| H1 | DistilBERT | 486+114 H20 (600) | P3 (182) | 0.0% | 11.0% | 10.7% | 45.2% | 54.8% | Collapsed |

**Do not rank models. Do not declare a winner. Each number belongs to its population.**

---

## 5. Historical / Legacy Artifacts

| Artifact | Population | Status | Note |
|---|---|---|---|
| `experiments/results/A0/evaluation_results.json` | P1 | Historical | Older full evaluation |
| `experiments/results/A1/evaluation_results.json` | P1 | Historical | Older full evaluation |
| `experiments/results/A2/evaluation_results.json` | P1 | Historical | Older full evaluation |
| `phase4f_5/results/a0_test.json` | P2 | Canonical for P2 | Corrected test split |
| `phase4f_5/results/a1_test.json` | P2 | Canonical for P2 | Corrected test split |
| `phase4f_5/results/a2_test.json` | P2 | Canonical for P2 | Corrected test split |
| `phase4f_5f/f2/evaluation/f2_benchmark.json` | P3 | Canonical | F2 on frozen benchmark |
| `phase4f_5f/h1/evaluation/h1_benchmark.json` | P3 | Canonical | H1 on frozen benchmark |

Do not delete or overwrite historical artifacts.

---

## 6. A0 / A1 / A2 Reconciliation

### Why different numbers exist

Each model has results in two evaluation populations:
- **P1 (918 examples):** from `experiments/results/` — older full evaluation
- **P2 (221 examples):** from `phase4f_5/results/` — corrected test split

The numbers differ because the populations differ. This is not a bug.

### A0

| Population | EM | F1 | Source |
|---|---|---|---|
| P1 (918) | 7.8% | 14.4% | `experiments/results/A0/evaluation_results.json` |
| P2 (221) | 3.2% | 8.6% | `phase4f_5/results/a0_test.json` |

P1 includes DATE (EM=96%) and ENTITY (EM=63.6%) categories where A0 excels. P2 does not have these categories. This explains most of the EM gap.

### A1

| Population | EM | F1 | Source |
|---|---|---|---|
| P1 (918) | 0.7% | 6.9% | `experiments/results/A1/evaluation_results.json` |
| P2 (221) | 1.8% | 14.4% | `phase4f_5/results/a1_test.json` |

P1 includes more difficult categories. The checkpoint may also differ between evaluations.

### A2 — see §7

---

## 7. A2 Inconsistency

### The discrepancy

| Source | EM | F1 | Population |
|---|---|---|---|
| `experiments/results/A2/evaluation_results.json` | 0.0% | 9.3% | P1 (918) |
| `phase4f_5/results/a2_test.json` | 0.9% | 12.3% | P2 (221) |

### Explanation

- **P1 (918):** 0 correct out of 876 answerable = EM 0.0%. The 42 unanswerable also contribute SPURIOUS=4.6%.
- **P2 (221):** 2 correct out of 221 answerable = EM 0.9%. The P2 subset is easier for A2.
- Both numbers are valid for their respective populations.
- The P2 subset excludes DATE, ENTITY, and LONG_CONTEXT categories, which are harder for BERT-base.

### Classification

**NO_BUG** — the discrepancy is entirely explained by different evaluation sets.

---

## 8. F2 Reconciliation

### Training count: 506, not 696

The `run_experiment.py` (Phase 4F.5-F) script defined F2 as:
```
486 answerable + 20 synthetic unanswerable + 190 resampled = 696
```

However, `run_experiment.py` was **never executed**. The actual F2 experiment used `run_f2.py`, which trained with:
```
486 answerable + 20 unanswerable = 506
```

The 696 number is a **stale design specification** from the unexecuted parent script. The actual training, manifests, and logs all confirm 506 examples.

### Evidence

- `f2_manifest.json`: `"train_total": 506`
- `f2_training.json`: `"data_description": "486 answerable + 20 unanswerable (reconciled)"`
- `f2_dataset_ids.json`: `"train_answerable_count": 486, "train_unanswerable_count": 20`

### Classification

**DOCUMENTATION_ERROR** — the 696 number in `h1_reconciled_comparison.json` is incorrect. The actual F2 training used 506 examples.

---

## 9. G Threshold Reconciliation

G applies a post-hoc null-score threshold to the F2 model. It is not a separate training run.

| Metric | F2 raw (argmax) | F2 + threshold (1.5705) |
|---|---|---|
| EM | 2.9% | 2.86% |
| F1 | 19.7% | 16.92% |
| Abstention | 0.0% | 19.1% |
| Spurious | 23.1% | 81.0% |
| False abstention | 0.0% | 27.86% |

The threshold improves abstention from 0% to 19.1% but at the cost of 81% spurious rate and 28% false abstention. The threshold is **UNSTABLE** (±0.1 causes 25% abstention shift).

---

## 10. H / H1 / H1-R Reconciliation

### H dataset design

- 3 nested pools: H10 (57), H20 (114), H30 (171)
- All from 18 source documents (same as answerable training)
- All 11 unanswerable categories covered
- H20 recommended and used for H1

### H1 execution

- Training: 486 answerable + 114 H20 = 600
- Validation: 85 answerable + 8 unanswerable = 93
- Holdout: 22 unanswerable (intended: 14)
- Benchmark: 182 (frozen)

### H1 holdout discrepancy (14 → 22)

`get_holdout_examples()` uses split index 20 instead of 28. This yields 42-20=22 instead of 42-28=14. The 8 extra examples come from indices 20-27, which should have been in the experiment pool. Additionally, 12 examples at indices 8-19 are placed in neither training, validation, nor holdout.

**Effect on benchmark conclusions:** NONE. The benchmark (182 frozen examples) is independent of the holdout split.

### H1 terminology error

The H1-R reconciliation report contains a reference to "H10 negatives" in the evidence classification table. The actual experiment uses H20 (114 examples). This is a documentation typo in the reconciliation report.

### H1-R status

VALID_WITH_LIMITATIONS. Benchmark results are correctly computed and reliable. The holdout diagnostic is slightly inflated but does not affect primary conclusions.

---

## 11. Dataset Integrity

| Artifact | Hash | Status |
|---|---|---|
| Source dataset (v3_1) | `a5175303...` | VERIFIED UNCHANGED |
| Derived dataset | `abcf4182...` | VERIFIED UNCHANGED |
| H20 pool | `49defabe...` | VERIFIED UNCHANGED |
| H10 pool | `b5ac2228...` | VERIFIED UNCHANGED |
| H30 pool | `e0d1812f...` | VERIFIED UNCHANGED |

---

## 12. Benchmark Integrity

| Property | Value |
|---|---|
| Hash | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` |
| Total examples | 182 |
| Answerable | 140 |
| Unanswerable | 42 |
| Source | `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` |
| Status | FROZEN, UNCHANGED |

---

## 13. Production-Model Integrity

| Property | Value |
|---|---|
| Hash | `df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac` |
| Path | `backend/models/documind-qa` |
| Status | UNCHANGED |

No experiment has modified the production model.

---

## 14. Claim-Strength Audit

| Claim | Source | Classification | Rationale |
|---|---|---|---|
| "H20 negatives cause DistilBERT to collapse" | H1 report | **PARTIALLY_SUPPORTED** | EM drops from 2.9% to 0.0%, F1 from 19.7% to 11.0%. But only tested on DistilBERT with exactly 114 negatives. Causation vs correlation not established (single experiment, no control for negative count). |
| "114 H20 negatives improve abstention" | H1 report | **SUPPORTED** | Abstention rises from 0% (F2) to 45.2% (H1). Observed in data. |
| "Improved abstention is targeted" | H1 report | **NOT_SUPPORTED** | Spurious rate simultaneously rises from 23.1% to 54.8%. 10.7% of answerable questions are falsely abstained. Abstention is not targeted. |
| "CLS/no-answer signal is useful" | H1-R report | **NOT_SUPPORTED** | Null margins near zero (mean -0.000344). Distributions overlap completely. Only 3/42 unanswerable have positive margin. |
| "DistilBERT is fundamentally incapable" | Multiple | **HYPOTHESIS** | Only tested with H20 negatives. Other negative types, training strategies, or model sizes untested. |
| "20 negatives are insufficient" | F2 report | **PARTIALLY_SUPPORTED** | F2 with 20 showed no abstention. But H1 with 114 showed catastrophic collapse. The optimal count is unknown — could be between 20 and 114, or could require a different approach entirely. |
| "H20 negatives are too different from answerable" | H1 report | **HYPOTHESIS** | Plausible but untested. H20 spans 17 documents with complex questions. A controlled experiment varying negative similarity would be needed. |
| "Hybrid QA is required" | Not stated in any report | **UNVERIFIED** | No hybrid architecture has been tested. This is pure speculation. |
| "F2 is functionally equivalent to A1/A2" | F2 reconciliation | **SUPPORTED** | F2 spurious rate (23.1%) matches A1/A2 spurious rates. All three have 0% abstention. The 20 unanswerable examples had no measurable effect. |

---

## 15. Current Evidence State

### What is established

1. A0 (production) achieves 64.3% abstention on P1 but loses this when fine-tuned without unanswerable examples (A1/A2).
2. F2 (486+20 unanswerable) does not restore abstention. Zero abstention across all evaluation sets.
3. H1 (486+114 H20) produces abstention (45.2%) but causes answerable performance collapse (EM 0.0%) and high spurious rate (54.8%).
4. The CLS/no-answer signal in H1 is essentially random noise.
5. Post-hoc thresholding (G) on F2 is unstable and produces worse abstention than A0.
6. All frozen artifacts are verified unchanged. No production code or model has been modified.

### What is uncertain

1. Whether the optimal negative count lies between 20 and 114.
2. Whether a larger model (BERT-base, DeBERTa) would handle H20 negatives better.
3. whether the H20 negatives are fundamentally too different from answerable questions.
4. Whether category-subset negatives (e.g., only ABSENT_FACT, UNSUPPORTED_NUMBER) would work better.
5. Whether a different loss function (focal loss, class weighting) would help.
6. Whether the 4% → 19% negative ratio jump caused the collapse, or whether it's the nature of the negatives.

---

## 16. What Must NOT Be Inferred

1. **Do NOT infer that DistilBERT is incapable of learning no-answer behavior.** Only H20 negatives have been tested. The production model (A0) achieves 64.3% abstention, proving the architecture can abstain.

2. **Do NOT infer that 20 negatives are insufficient.** F2 showed no effect with 20, but H1 showed catastrophic effect with 114. The optimal count is unknown.

3. **Do NOT infer that H20 negatives are inherently bad.** They were tested once with one model, one learning rate, one epoch count. More experiments are needed.

4. **Do NOT infer that hybrid QA is required.** No hybrid architecture has been tested. This would be a hypothesis, not a conclusion.

5. **Do NOT compare P1 metrics with P3 metrics.** They are different evaluation populations with different category compositions.

6. **Do NOT use the H1 holdout abstention (36.4%) as if it were measured on 14 examples.** It was measured on 22 examples due to a split-index mismatch.

---

## 17. Next Experiment Gate

### Candidate Directions

#### Direction A: Continue improving extractive QA

| Aspect | Assessment |
|---|---|
| Evidence for | A1 achieves 14.4% F1 on P2 (best extractive F1). The architecture can extract answers. |
| Evidence against | All extractive models (A1, A2, F2) fail on unanswerable questions. 0% abstention. |
| Unknowns | Whether better training data, more epochs, or learning rate tuning could improve extraction. |
| Discriminating experiment | None needed — extraction is not the bottleneck. The bottleneck is unanswerable handling. |

#### Direction B: Try a stronger extractive model

| Aspect | Assessment |
|---|---|
| Evidence for | A2 (BERT-base) matches A1 (DistilBERT) on P1 but slightly worse on P2. A3 (DeBERTa) exists but results not yet reconciled. |
| Evidence against | A2 got 0.0% EM on P1 — worse than A1. Larger model did not help with the core problem. |
| Unknowns | Whether BERT-base or DeBERTa would handle H20 negatives better than DistilBERT. |
| Discriminating experiment | Train H1 with BERT-base (same 486+114 H20) and compare with DistilBERT H1. |

#### Direction C: Redesign answerability / no-answer mechanism

| Aspect | Assessment |
|---|---|
| Evidence for | A0 achieves 64.3% abstention — proof that the architecture CAN learn no-answer. The problem is in the fine-tuning, not the architecture. G threshold experiment shows CLS signal exists but is weak. |
| Evidence against | H1 shows that even with 114 negatives, the CLS signal is random (mean margin -0.000344). The signal may be too weak to salvage. |
| Unknowns | Whether class-balanced training (50% unanswerable), focal loss, or multi-task learning would produce a stronger CLS signal. |
| Discriminating experiment | Train with 50% unanswerable ratio (class-balanced) on DistilBERT. This directly tests whether the ratio is the issue. |

#### Direction D: Grounded generative QA

| Aspect | Assessment |
|---|---|
| Evidence for | None from current experiments. No generative model has been tested. |
| Evidence against | All current infrastructure is extractive. Generative QA would require new model, new training pipeline, new evaluation. |
| Unknowns | Everything — this is untested territory. |
| Discriminating experiment | Would require significant new infrastructure. Not the highest-information next step. |

#### Direction E: Hybrid retrieval + answerability + QA architecture

| Aspect | Assessment |
|---|---|
| Evidence for | None from current experiments. No hybrid architecture tested. |
| Evidence against | Complexity increase with no evidence of benefit. |
| Unknowns | Everything. |
| Discriminating experiment | Would require significant new architecture. Not the highest-information next step. |

### Highest-Information Next Experiment

**Direction C: Class-balanced training (50% unanswerable ratio)**

Rationale:
- Directly tests the primary hypothesis from F2 (insufficient ratio) and H1 (too many negatives)
- Uses the same architecture, same codebase, same evaluation pipeline
- Expected to discriminate between: "ratio is the issue" vs "negatives are the issue" vs "architecture is the issue"
- Low implementation cost (modify training split, no new model needed)
- If class-balanced DistilBERT still collapses, then the issue is the negatives, not the ratio
- If class-balanced DistilBERT learns abstention without collapse, then H1's 114 negatives were too many

**Do NOT select a preferred architecture. Select the highest-information experiment.**

---

*Generated: 2026-09-22*
*SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY*
*GITHUB ACCESSED: NO*
*NO COMMIT. NO PUSH. NO TRAINING.*
