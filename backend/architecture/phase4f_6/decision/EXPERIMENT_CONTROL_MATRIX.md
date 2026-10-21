# DocuMind — Experiment Control Matrix (Phase 4F.6-B, reconciled in 4F.6-BR)

> **Reconciliation status:** every figure below was re-verified against source artifacts on 2026-09-23. Corrections vs the initial 4F.6-B draft are itemized in `PHASE4F6B_RECONCILIATION.md` (C0 population statement, C1b two-population split, spurious/false-abstention definitions, G's stability population, production-model hash scopes).
> **Updated in 4F.6-C-R:** C0·P3 recorded (A0 results on P3 exist in `phase4f_5d/analysis/` — the earlier absence statement is superseded) and a C1b-P3 block added under `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`; see `PHASE4F6C_RECONCILIATION.md`.
>
> **SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO**

---

## 1. Evaluation Populations (reference)

| ID | Definition | Composition | Notes |
|---|---|---|---|
| P1 | Full derived dataset | 918 = 876 answerable + 42 unanswerable | 10 answerable categories incl. DATE, ENTITY |
| P2 | Corrected test split | 221 answerable, **0 unanswerable** | 7 categories; no DATE/ENTITY/LONG_CONTEXT; abstention & spurious undefined |
| **P3** | **Frozen benchmark** | **182 = 140 answerable + 42 unanswerable** | sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — FROZEN, UNCHANGED |
| P3-validation | Threshold calibration split of P3 | 85 answerable + 8 unanswerable | **Not a benchmark population** — threshold/stability results measured here must never be reported as P3 |
| P3-holdout | Remaining split | remainder | H1's holdout diagnostic was inflated (H1-R); not used for control numbers |
| DIAGNOSTIC | Any new annotation/expanded set | e.g., E0 element annotations | Labeled separately; never merged into 182/140/42 |

**Comparison rule:** metrics are compared only *within* a population column. Every reported figure carries its population tag; an untagged figure is a defect.

---

## 2. Controls

### C0 — Production baseline (A0)

| Property | Value |
|---|---|
| Model | Production `backend/models/documind-qa` (DistilBERT-family fine-tune) — **UNCHANGED** |
| Integrity (directory scope) | Research-ledger `frozen_artifact_integrity` records hash `df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac` with `Path: backend/models/documind-qa` (RESEARCH_LEDGER.md + research_ledger.json) |
| Integrity (file scope) | sha256 of `model.safetensors` = `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` (recomputed 2026-09-23 during 4F.6-BR; matches the earlier recorded value). Two scopes, two hashes — **both unchanged; both must be cited with their scope** |
| **Populations with actual A0 results** | **P1, P2, and P3** (below). P3 results are **aggregates only** — per-example predictions for that run were not stored |

**C0·P1 (918):** EM 7.8 / F1 14.4 · unanswerable abstention 64.3% (27/42) · false abstention **49.9%** (437/876, protocol definition) · spurious 15/42 = 35.7% of unanswerable (artifact field 1.6 = of-all-918) · per-category EM: DATE 96.0, ENTITY 63.6, NUMERIC 20.6, DIRECT_SPAN 5.8, SECTION_SPECIFIC 1.8, TABLE_CELL 1.1, all others 0.0.

**C0·P2 (221):** EM 3.2 / F1 8.6 · no unanswerable → abstention/spurious undefined · false abstention 62.4% (138/221, protocol) — A0 abstains even with zero unanswerable examples present.

**C0·P3 (182, aggregates only):** EM 2.1 / F1 12.0 (answerable) · unanswerable abstention **64.3% = 27/42** · false abstention **55.7% = 78/140** (protocol) · spurious count **15** — as a rate: **15/182 = 8.2% of all examples**, or **15/42 = 35.7% of unanswerable — the denominator must be stated every time and never mixed** · source: `phase4f_5d/analysis/a0_benchmark_v1.json` + `benchmark_comparison.json` (baseline re-evaluation, 2026-09-21). **Denominator definitions for this population:** abstention = abstained unanswerable ÷ 42; false abstention = abstained answerable ÷ 140; spurious = answered unanswerable, quotable over 42 or over 182 (never unlabeled). Provenance: the artifact records **no eval_version, harness id, checkpoint id, tokenizer id, or preprocessing parameters**, and the generator script is absent from the tree → OBSERVED aggregates with **limited run-level provenance** (missing-provenance list: `PHASE4F6C_RECONCILIATION.md`).

**Role:** production reference on P1, P2, and (as aggregates) P3. **C1 remains the canonical P3 control** for the extractive path because C1 has per-example predictions and fully reconciled provenance. Behavioral-equivalence output testing against C0 (gate criterion 8) still requires a **declared run capturing per-example C0·P3 outputs** — aggregates cannot serve bit-for-bit equivalence.

---

### C1 — Corrected extractive baseline on P3 (F2)

| Property | Value |
|---|---|
| Model | F2 — DistilBERT, 486 answerable + 20 unanswerable (506 total, reconciled) |
| Result (P3) | EM 2.9 / F1 19.7 · unanswerable abstention 0.0% · false abstention 0.0% · spurious 42/42 = 100% of unanswerable (artifact field 23.1 = of-all-182) · failures: EXTRACT 136, SPURIOUS 42, correct 4 |
| Role | **The canonical control for any new P3 result involving the extractive path** |

---

### C1b — Model-capacity evidence (A1 vs A2) — two separate population blocks, never pooled

| Block | Population | A1 (DistilBERT) | A2 (BERT-base) | Reading within the block |
|---|---|---|---|---|
| **C1b-P1** | P1 (918) | EM 0.7 / F1 6.9 | EM 0.0 / F1 9.3 | A2 lower EM, higher F1 — **mixed** |
| **C1b-P2** | P2 (221) | EM 1.8 / F1 14.4 | EM 0.9 / F1 12.3 | A1 higher on both |
| **C1b-P3** | P3 (182) | EM 3.6 / F1 21.3 | EM 3.6 / F1 19.4 | Equal EM, A1 higher F1 — **`DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`** |

- **Protocol note:** the P1 runs (4F.4 harness), P2 runs (`4F.5-eval-v1`), and the P3 baseline re-evaluation (4F.5-D, no recorded eval_version) are three different evaluation passes — recorded in the phase artifacts and ledger. **The blocks are never compared with each other, and none of them is a controlled capacity comparison.**
- **C1b-P3 provenance (why `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`):** comparability could **not** be verified from local artifacts — (a) the harness script that produced `phase4f_5d/analysis/*.json` is absent from the tree (no `.py` emits `em_answerable`/`by_tier`); (b) the artifacts record no eval_version, checkpoint path/hash, tokenizer id, or preprocessing parameters; (c) the 4F.4-R `evaluation_parity_matrix.json` and `cross_phase_evaluation_compatibility.json` cover **4F.4 only**. Candidate checkpoints exist (`experiments/results/A1/checkpoint_best/` hash `cb923d7b63f8561b`, `A2/checkpoint_best/` hash `536fc6edb9b9a884`, per 4F.4-R `checkpoint_audit.json`) but their linkage to the P3 pass is unrecorded. Capacity is additionally confounded with architecture, pretraining, and tokenizer casing by construction (distilbert-base-cased vs bert-base-cased). **Capacity is neither proven nor disproven by C1b-P3.**
- **Category detail within blocks:** TABLE_CELL/TABLE_ROW/LIST_ITEM/MULTI_CHUNK EM = 0.0 for A1 and A2 in **both** blocks (representation fixed, model varied → no EM movement); F1 did move (e.g., TABLE_ROW P1: 9.6 → 21.1).
- **Role:** bounded prior for E1 (model change). **Not a P3 control.** Cite only as C1b-P1 or C1b-P2.

---

### C2 — Historical collapse reference (H1, P3)

| Property | Value |
|---|---|
| Model | H1 — DistilBERT, 486 + 114 H20 negatives (600 total) |
| Result (P3) | EM 0.0 / F1 11.0 · unanswerable abstention 45.2% (19/42) · false abstention 10.7% (15/140) · spurious 23/42 = 54.8% of unanswerable *(artifact field denominator = of-unanswerable, unlike F2's field)* |
| Role | Documents the collapse behavior every intervention must be shown not to reproduce |
| Status | VALID_WITH_LIMITATIONS per H1-R (holdout diagnostic inflated; benchmark figures reliable) |

---

### C2b — Unstable-threshold reference (G, P3 + P3-validation)

| Property | Value |
|---|---|
| System | G — F2 weights + post-hoc null-score threshold 1.5705 (`decision_rule: null_score >= 1.5705`) |
| Benchmark result (P3) | EM 2.86 / F1 16.92 · unanswerable abstention 19.05% (8/42) · false abstention 27.86% (39/140) · spurious 34/42 = 80.95% |
| **Stability result (P3-validation, 85+8 — NOT the benchmark)** | `stability_analysis.json`: `max_abstention_shift: 25.0` points at ±0.1 threshold, `stable: false`; threshold selected on the validation split (`validation_calibration.json`) |
| Role | The instability pattern any threshold-based intervention must be tested against — **threshold stability must be reported, and its population tagged (validation vs benchmark)** |
| Note | G uses the same weights as F2: per-category EM is identical to F2's; the threshold changed abstention, not extraction |

---

## 3. Cross-Population & Definition Rules (normative)

1. **No cross-population metric comparison.** P1 vs P2 vs P3 numbers never appear in the same arithmetic. P2 contains no unanswerable examples — abstention/spurious there are undefined, not zero.
2. **false_abstention = protocol definition only** (`phase4f_5/evaluation/evaluation_protocol.json`: abstained answerable ÷ answerable). The `evaluate.py` variant ((answerable − correct) ÷ answerable) produced the 92.2 / 99.3 values in `experiments/phase4f_4_results.json` — those are mislabeled answerable *error rates* and must never be quoted as false abstention.
3. **spurious_rate raw fields are denominator-inconsistent across artifacts** (A0/A1/A2/F2 fields = of-all-examples; H1/G fields = of-unanswerable). Only the harmonized per-unanswerable rates may be compared: A0·P1 35.7%, A1·P1 100%, A2·P1 100%, F2·P3 100%, G·P3 81.0%, H1·P3 54.8% (P2 undefined).
4. **Every result identifies its evaluation population** in the same row as the metric.
5. **DIAGNOSTIC data never enters the 182/140/42 totals.**
6. Threshold/stability figures identify whether they were measured on P3-validation or P3.
7. **C0·P3 denominator triplet:** abstention **27/42**, false abstention **78/140**, spurious **15** (over 182 = 8.2% / over 42 = 35.7%). The 4F.5-D hardening report states different values for two of these (false abstention 35.7% with count 50; tier numbers) than `a0_benchmark_v1.json` (55.7%, count 78) — **the analysis JSONs are the source of record; the hardening report is a derived summary; the historical report is unmodified** (see `PHASE4F6C_RECONCILIATION.md`).

---

## 4. The Proposed-Intervention Slot

Exactly **one** architectural or model change per experiment. A new result may only be registered as a control row when it names:

| Field | Requirement |
|---|---|
| Change | The single intervention (model / gate / route / threshold — never two) |
| Control | Which existing control it compares to, **same population** (P3 unless explicitly declared otherwise) |
| Population | P3 (or explicitly declared P1/P2/DIAGNOSTIC) |
| Threshold | Pre-registered before evaluation; threshold-stability report required if threshold-based |
| Metrics | EM, F1, unanswerable abstention, false abstention (protocol), spurious (stated denominator) |
| Integrity | Benchmark hash and **both** production-model hashes (§2 C0) re-verified before/after; both unchanged |

No historical population may be mixed into the comparison to enlarge a favorable delta.

---

## 5. Frozen Artifacts (verified unchanged 2026-09-23)

| Artifact | Value | Verification |
|---|---|---|
| Frozen benchmark `qa_benchmark_v1.jsonl` | 182 lines (42 `is_impossible`), sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` | Recomputed this phase — matches ledger |
| Production model (directory scope) | `df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac` | Ledger-recorded; ledger unmodified |
| Production model (file scope) | `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` (`model.safetensors`) | Recomputed this phase — matches prior citation |

---

*Phase 4F.6-B decision artifact, reconciled 4F.6-BR. Planning only. No training. No benchmark change. No production change. No commit. No push.*
