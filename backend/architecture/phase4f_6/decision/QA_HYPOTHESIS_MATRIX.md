# DocuMind — QA Hypothesis Matrix (Phase 4F.6-B, reconciled in 4F.6-BR)

> **Reconciliation status:** every numerical claim below was re-verified against the underlying Phase 4F artifacts during Phase 4F.6-BR (2026-09-23). Corrections applied to the initial 4F.6-B wording are itemized in `PHASE4F6B_RECONCILIATION.md`. No source artifact was modified.
> **Updated in 4F.6-C-R:** P3 A0/A1/A2 results (`phase4f_5d/analysis/`) incorporated; all earlier absence statements superseded; evaluation-count denominators extended from 9 to 12 reconciled evaluations — see `PHASE4F6C_RECONCILIATION.md`.
>
> **SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO**

---

## 1. Evaluation Populations (never mixed)

| Population | Definition | Composition | Source artifacts |
|---|---|---|---|
| **P1** | Full derived dataset | 918 = 876 answerable (10 categories incl. DATE, ENTITY) + 42 unanswerable | `backend/phase4f/experiments/results/` |
| **P2** | Corrected test split | 221 answerable, **0 unanswerable** (7 categories; no DATE, no ENTITY, no LONG_CONTEXT) | `backend/phase4f/phase4f_5/results/` (eval_version `4F.5-eval-v1`) |
| **P3** | **Frozen benchmark** | 182 = 140 answerable (8 categories) + 42 unanswerable; sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — FROZEN, UNCHANGED | `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` |
| **P3-validation / P3-holdout** | Threshold-calibration splits used by the F2/G/H1 threshold work (93 = 85 answerable + 8 unanswerable / remainder) | **Not benchmark results**; never reported as P3 | `phase4f_5f/f2/threshold_experiment/` |
| **DIAGNOSTIC** | Any annotation or expanded set created for E0 | Labeled separately; never merged into the 182/140/42 totals | (does not exist yet) |

**Rule:** no metric crosses a population boundary. DATE/ENTITY figures exist only on P1. P2 has no unanswerable examples, so abstention/spurious metrics are undefined there.

---

## 2. Verified Evidence Base (reconciled source artifacts only)

### 2.1 Overall metrics per population

| System | Pop | EM | F1 | Unanswerable abstention | False abstention (protocol) | Spurious (harmonized: of unanswerable) | Source artifact |
|---|---|---|---|---|---|---|---|
| A0 (production) | P1 (918) | 7.8 | 14.4 | 64.3% (27/42) | 49.9% (437/876) | 15/42 = 35.7% *(field 1.6 = of-all-918)* | `experiments/results/A0/evaluation_results.json` |
| A0 (production) | P2 (221) | 3.2 | 8.6 | *undefined (0 unanswerable)* | 62.4% (138/221) | *undefined* | `phase4f_5/results/a0_test.json` |
| A1 (DistilBERT) | P1 (918) | 0.7 | 6.9 | 0.0% (0/42) | 0.0% | 42/42 = 100% *(field 4.6 = of-all)* | `experiments/results/A1/evaluation_results.json` |
| A1 (DistilBERT) | P2 (221) | 1.8 | 14.4 | *undefined* | 0.0% | *undefined* | `phase4f_5/results/a1_test.json` |
| A2 (BERT-base) | P1 (918) | 0.0 | 9.3 | 0.0% (0/42) | 0.0% | 42/42 = 100% *(field 4.6 = of-all)* | `experiments/results/A2/evaluation_results.json` |
| A2 (BERT-base) | P2 (221) | 0.9 | 12.3 | *undefined* | 0.0% | *undefined* | `phase4f_5/results/a2_test.json` |
| A0 (production) | **P3 (182)** | 2.1 | 12.0 | 64.3% (27/42) | 55.7% (78/140) | 15/42 = 35.7% *(field 8.2 = of-all-182)* | `phase4f_5d/analysis/a0_benchmark_v1.json` |
| A1 (DistilBERT) | **P3 (182)** | 3.6 | 21.3 | 0.0% (0/42) | 0.0% (0/140) | 42/42 = 100% *(field 23.1 = of-all-182)* | `phase4f_5d/analysis/a1_benchmark_v1.json` |
| A2 (BERT-base) | **P3 (182)** | 3.6 | 19.4 | 0.0% (0/42) | 0.0% (0/140) | 42/42 = 100% *(field 23.1 = of-all-182)* | `phase4f_5d/analysis/a2_benchmark_v1.json` |
| F2 (486+20) | **P3 (182)** | 2.9 | 19.7 | 0.0% (0/42) | 0.0% | 42/42 = 100% *(field 23.1 = of-all-182)* | `phase4f_5f/f2/evaluation/f2_benchmark.json` |
| G (F2 + threshold 1.5705) | **P3 (182)** | 2.86 | 16.92 | 19.05% (8/42) | 27.86% (39/140) | 34/42 = 80.95% | `phase4f_5f/f2/threshold_experiment/benchmark_result.json` |
| H1 (486+114 H20) | **P3 (182)** | 0.0 | 11.0 | 45.2% (19/42) | 10.7% (15/140) | 23/42 = 54.8% | `phase4f_5f/h1_reconciliation/h1_metric_recalculation.json`, `research_ledger.json` |

**A2 vs A1 — population-specific, as required (never pooled):**
- **P1 (918):** A1 EM 0.7 / F1 6.9 vs A2 EM 0.0 / F1 9.3 → A2 lower EM, higher F1 (**mixed**).
- **P2 (221):** A1 EM 1.8 / F1 14.4 vs A2 EM 0.9 / F1 12.3 → A1 higher on both.
- The P1 runs (4F.4 harness), P2 runs (`4F.5-eval-v1`), and the P3 baseline re-evaluation (4F.5-D, **no recorded eval_version**) are three different evaluation passes — their checkpoints/harness/params differences are recorded in the phase artifacts and ledger, and the P3 pass's provenance is **unrecorded** (script absent from tree; no checkpoint/tokenizer/params in the artifacts).
- **P3 (182):** A1 EM 3.6 / F1 21.3 vs A2 EM 3.6 / F1 19.4 → **equal EM, higher F1 for A1** — classified **`DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`**.
- The three blocks are **never pooled**, and none is a controlled capacity experiment. **P1 is mixed by metric; P2 favors A1 on both metrics; P3 has equal EM and higher F1 for A1. Exact checkpoint/evaluation comparability must be verified before causal capacity interpretation. No consistent capacity advantage of BERT-base over DistilBERT is established in any direction.**

### 2.2 Per-category EM% — all reconciled evaluations (columns are separate populations)

| Category (n: P1 / P2 / P3) | A0·P1 | A1·P1 | A2·P1 | A0·P2 | A1·P2 | A2·P2 | A0·P3 | A1·P3 | A2·P3 | F2·P3 | G·P3 | H1·P3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DATE (25 / — / —) | 96.0 | 4.0 | 0.0 | absent | absent | absent | absent | absent | absent | absent | absent | absent |
| ENTITY (22 / — / —) | 63.6 | 0.0 | 0.0 | absent | absent | absent | absent | absent | absent | absent | absent | absent |
| DIRECT_SPAN (86 / 25 / 24) | 5.8 | 0.0 | 0.0 | 4.0 | 8.0 | 4.0 | 4.2 | 16.7 | 16.7 | 12.5 | 12.5 | 0.0 |
| NUMERIC (97 / 20 / 20) | 20.6 | 4.1 | 0.0 | 10.0 | 10.0 | 5.0 | 10.0 | 5.0 | 5.0 | 5.0 | 5.0 | 0.0 |
| SECTION_SPECIFIC (55 / 14 / 16) | 1.8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TABLE_CELL (362 / 111 / 24) | 1.1 | 0.3 | 0.0 | 3.6 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| TABLE_ROW (82 / 25 / 16) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| LIST_ITEM (106 / 19 / 20) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| MULTI_CHUNK (26 / 7 / 10) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| LONG_CONTEXT (15 / — / 10) | 0.0 | 0.0 | 0.0 | absent | absent | absent | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| UNANSWERABLE (42 / 0 / 42) | 0 | 0 | 0 | — | — | — | 0 | 0 | 0 | 0 | 0 | 0 |

*(EM on UNANSWERABLE rows is 0 by construction — EM is computed over answerable examples only.)*

**Evidence-accurate table/list statements (replaces every "0% EM across all experiments" claim):**

- **TABLE_ROW — universally zero across the 12 reconciled evaluations:** 0.0% in **all 12** (every system × P1, P2, P3). F1 0.0%–22.1% — A0·P3 F1 is also 0.0 (the only table evaluation with zero token overlap).
- **LIST_ITEM — universally zero across the 12 reconciled evaluations:** 0.0% in **all 12** (F1 9.1%–16.0%).
- **MULTI_CHUNK — universally zero across the 12:** 0.0% in **all 12** (F1 0.9%–22.1%).
- **LONG_CONTEXT — universally zero across the 9 evaluations containing it:** 0.0% (P1 and P3; absent from P2; F1 0.0%–12.0%).
- **TABLE_CELL — zero in 9 of 12, never above 3.6%:** nonzero only for A0·P1 (1.1%, n=362), A1·P1 (0.3%, n=362), A0·P2 (3.6%, n=111). **On P3 specifically, all six evaluated systems (A0, A1, A2, F2, G, H1) are 0.0 EM.** F1 range 0.0%–5.8% (A0·P3 F1 also 0.0).
- **SECTION_SPECIFIC:** zero in **11 of 12** (only nonzero: A0·P1 = 1.8); F1 0.0%–27.4%.
- **NUMERIC:** nonzero in **10 of 12** (zeros only: A2·P1, H1·P3); up to 20.6 (A0·P1); on P3: A0 10.0, A1/A2/F2/G 5.0.
- **DIRECT_SPAN:** nonzero in **9 of 12** (zeros: A1·P1, A2·P1, H1·P3); on P3 the top EM is A1/A2 16.7 vs F2/G 12.5 (`DESCRIPTIVE_ONLY` for A1/A2).
- **Not universal zeros:** DATE (96.0·A0·P1), ENTITY (63.6·A0·P1) — both **absent from P2 and P3**.
- **Unmeasured on P3:** DATE, ENTITY (absent from the benchmark). **No population at all contains TABLE_COMPARISON, LIST_ORDER, SUMMARY, or MULTI_HOP** — every statement about them is UNMEASURED, not zero.
- G's per-category EM equals F2's because G uses the same weights — the threshold changed abstention behavior, not extraction (G retained all 4 EM-correct answers and additionally abstained on 39 wrong ones).

### 2.3 Answerability / abstention evidence (verified)

- **F2 (P3):** 0/42 abstention; all 42 unanswerable answered spuriously; false abstention 0.
- **G (P3):** threshold 1.5705 → 8/42 abstained (19.05%), 34/42 spurious (80.95%), 39/140 false abstention (27.86%). **Stability was measured on P3-validation (85 answerable + 8 unanswerable), not the benchmark:** `stability_analysis.json` records `max_abstention_shift: 25.0` at ±0.1 threshold and `stable: false`.
- **H1 (P3):** 19/42 abstained (45.2%) **but** 23/42 spurious (54.8%) **and** answerable EM 0.0 with 15/140 false abstention (10.7%) → abstention is non-targeted; H1-R records null-score mean margin −0.000344, only 3/42 unanswerable with positive margin, class overlap < 0.25 SD; H1's holdout diagnostic was inflated — benchmark figures are the reliable ones.
- **A0 (P1):** abstains on 27/42 unanswerable (64.3%) **at the cost of** 437/876 false abstention (49.9%) and 15/42 spurious (35.7%). **A0 (P2):** false abstention 62.4% (138/221) **even with zero unanswerable examples present**.
- **A0 (P3, aggregates):** abstention 27/42 (64.3%) at false abstention 78/140 (55.7%), spurious 15/42 (35.7%; field 8.2 = of-all-182) — in-architecture abstention demonstrated **on the frozen benchmark itself**, still far above Gate 2. **A1/A2 (P3):** 0/42 abstention with 42/42 spurious — both fine-tuned extractive models answer **every** unanswerable example on P3.
- **No tested system meets ADR Gate 2** (classifier accuracy > 80%, abstention > 50%, false abstention < 20%).

**Metric-definition warnings (evaluation limitations, recorded here so no document mixes them):**
1. *false_abstention* has two coexisting local definitions: the **protocol definition** (`phase4f_5/evaluation/evaluation_protocol.json`: abstained answerable ÷ answerable → A0·P1 = **49.9**) and an `evaluate.py` computation ((answerable − correct) ÷ answerable → A0·P1 = **92.2**, A1 = 99.3, appearing in `experiments/phase4f_4_results.json` and the 4F.4 report text). The 92.2/99.3 figures are mislabeled answerable *error rates*. **All decision documents use protocol values.**
2. *spurious_rate* fields use inconsistent denominators across artifacts (A0/A1/A2/F2 fields are of-all-examples; H1/G fields are of-unanswerable). **Only the harmonized per-unanswerable column in §2.1 may be compared across systems.**
3. The 4F.5-D hardening report (`phase4f_5d/reports/`) is a **derived summary that disagrees with the analysis JSONs it summarizes** (A0·P3 false abstention stated as 35.7% / count 50 vs the JSON's 55.7% / count 78; tier numbers differ). **The `analysis/*.json` files are the source of record; the historical report is unmodified.**

---

## 3. Hypothesis → Evidence Matrix

Allowed classifications only: `SUPPORTED` · `PARTIALLY_SUPPORTED` · `HYPOTHESIS` · `NOT_SUPPORTED` · `UNVERIFIED`. No scores, no ranking.

| Hypothesis | Supporting evidence | Contradicting evidence | Unknown | Classification |
|---|---|---|---|---|
| **H-A — A stronger/better-trained extractive model could materially improve the benchmark while preserving the RAG structure** | F2 on P3: DIRECT_SPAN EM 12.5 / F1 47.4, NUMERIC 5.0 / 39.8 — span extraction works non-trivially on the benchmark. A0 on P1: DATE 96.0, ENTITY 63.6, NUMERIC 20.6 — training recipe/data move category outcomes substantially. **P3 aggregates: A1 (3.6 / 21.3) and A2 (3.6 / 19.4) exceed F2 (2.9 / 19.7) and A0 (2.1 / 12.0) on answerable EM/F1; A1/A2 DIRECT_SPAN EM 16.7 vs F2 12.5 — `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED` (run provenance unrecorded).** A1/A2 P2: F1 14.4 / 12.3; A2·P1 TABLE_ROW F1 21.1 and A1·P3 22.1 show capacity moves partial token overlap. | **Population-specific capacity results, never pooled:** on **P1**, A2 EM 0.0 < A1 0.7 while A2 F1 9.3 > A1 6.9 (**mixed by metric**); on **P2**, A1 is higher on both (1.8 > 0.9; 14.4 > 12.3); on **P3**, equal EM (3.6 = 3.6) with A1 higher F1 (21.3 > 19.4) — and the P3 pass records no eval_version/checkpoint/tokenizer/params with its script absent from the tree, so **exact checkpoint/evaluation comparability must be verified before any causal capacity interpretation** (ledger Direction B itself records "matches on P1, slightly worse on P2"). Model swaps with representation held fixed left TABLE_CELL/TABLE_ROW/LIST_ITEM/MULTI_CHUNK EM at 0.0 — now across **all six P3 systems** (A0, A1, A2, F2, G, H1) → capacity alone did not unlock structured categories. 4F.4 reports A3 (DeBERTa) collapsed with NaN loss — **the ledger has not reconciled A3**; not citable as settled evidence. Ledger Direction A (unanswerable handling): "extraction is not the bottleneck." | Whether a provenance-controlled model change beats C1 (F2) on P3 under identical, recorded conditions — the P3 A1/A2 delta cannot answer this until the missing provenance is supplied. A3 reconciliation. Stage attribution of P3 failures (E0 pending) — extraction vs retrieval vs representation shares unmeasured, so even H-A's target set is undefined. | **PARTIALLY_SUPPORTED** (supported descriptively for span-like categories; no evidence it addresses structured/synthesis categories; capacity evidence mixed, population-bound, and comparability-limited) |
| **H-B1 — Answerability is an important, distinct, unresolved problem** | F2: 0/42 abstention, 42/42 spurious (P3, OBSERVED). G: 8/42 abstain with 34/42 spurious, false abstention 39/140, and validation-stability failure (`stable: false`, ±0.1 → 25-point shift) (OBSERVED). H1: abstention 45.2% non-targeted — EM collapsed to 0.0 with 10.7% false abstention (OBSERVED); H1-R: null-score margins are noise (mean −0.000344, 3/42 positive, overlap < 0.25 SD) (OBSERVED). A0: abstention exists yet is unreliable — 64.3% at 49.9% false abstention on P1, 62.4% on P2, and **64.3% at 55.7% false abstention (78/140) on P3 itself** (OBSERVED, aggregates). **A1/A2·P3: 0/42 abstention with 42/42 spurious — both fine-tuned extractive models answer every unanswerable example on P3 (OBSERVED).** No tested system meets ADR Gate 2. Ledger Direction C ranks class-balanced answerability redesign as its own highest-information direction. | None observed refutes the *importance/distinctness* of the problem. Note the scope limit: A0 demonstrates that abstention behavior arises **within the existing architecture** (now on P1, P2, and P3 alike), so the evidence establishes a behavioral problem, not an architectural one. | Whether class-balanced (50%) or focal-loss training meets Gate 2 (ledger Direction C — untested). Whether **any** configuration meets Gate 2 — A0's P3 false abstention (55.7%) is ~2.8× the < 20% criterion. | **SUPPORTED** |
| **H-B2 — A separately implemented answerability module is required (separate ownership, not just a separate concern)** | Indirect only: ADR records separation as **DECIDED** on H1/F2/G evidence; G shows naive post-hoc thresholding insufficient; H1-R shows the CLS/no-answer mechanism is noise in the tested regime → in-model ownership is *unproven in tested configurations*. | **Zero direct evidence:** no separate answerability module has ever been implemented or evaluated anywhere in the local record. A0 abstains inside the existing architecture (separation not shown necessary) — now demonstrated on P3 as well (27/42 at 55.7% false abstention, aggregates), which is **further descriptive evidence against necessity framing and does NOT convert H-B2 to SUPPORTED**. The ledger does not claim necessity — its claim audit records "20 negatives are insufficient" = PARTIALLY_SUPPORTED and "H20 negatives are too different" = HYPOTHESIS, so count/distribution remain live alternatives; ledger Direction C's proposed fix is an **in-model training redesign** (ratio/loss), which if successful would remove the stated reason for a separate module. A supported *problem* is not a supported *solution*. | Comparative outcome of a separate gate (E2) vs class-balanced in-model training. Whether any gate meets Gate 2 thresholds (classifier accuracy > 80%). | **UNVERIFIED** |
| **H-C — Tables, lists, numeric, comparison and aggregation questions require specialized/structured workflows rather than generic span extraction** | Structure is absent by construction: CURRENT_ARCHITECTURE §5.4 documents the flat chunk model — no table rows, cells, list items, or section identity exist in the representation (design fact). The failure pattern is **category-shaped**: TABLE_ROW/LIST_ITEM/MULTI_CHUNK EM 0.0 in all 9 evaluations while span categories reach 12.5–96.0. A **representation-fixed, model-varied contrast**: swapping A1→A2 changed nothing on table/list EM (0.0 both, P1 and P2) → capacity did not unlock structured categories (weak attribution evidence toward the representation/context side). QUESTION_WORKFLOW_MATRIX: arithmetic/compare questions are not expressible as single spans by construction. ADR §10 records structured representation as HYPOTHESIS; architecture audit §5.4 as PARTIALLY_SUPPORTED. | **No experiment has varied document representation while holding the model fixed** — the causal claim remains unproven. E0's presence levels are unrun: "gold evidence reached the model" has never been measured, so retrieval/context failure could produce the same zeros. A scoring/serialization component exists in the EM failures: F2 raw predictions show digit-spaced near-misses (`"91. 4 percent"` vs gold `"91.4 percent"`) and pipe-joined cells (`"450 | grams"` vs gold `"450"`) — part of the zero-EM surface is output-format/normalization, not necessarily structure absence (validation-split raw predictions; benchmark-level raw-prediction availability unverified). F1 is nonzero in every category (e.g., MULTI_CHUNK up to 21.7) → models partially localize structured tokens. | Table/list/section detection accuracy on P3 source documents (ADR Gate 3 unmeasured). Conditional extraction success when structure is preserved (E0 Level 5). Yield of deterministic table lookup. The retrieval-presence share (E0 Levels 1–3). | **PARTIALLY_SUPPORTED** |
| **H-D — Some tasks are better served by grounded generation from retrieved evidence** | Architectural argument only: LONG_CONTEXT and MULTI_CHUNK target behavior (synthesis) is not expressible as single-span extraction; SUMMARY and MULTI_HOP have no benchmark representation at all. | Research ledger Direction D verbatim: evidence for = "None from current experiments. No generative model has been tested."; the ledger ranks it "not the highest-information next step." No generative model, pipeline, or evaluation exists locally (ADR §9 DEFERRED). Grounded generation would require a new model, new pipeline, and new evaluation design simultaneously. | Everything measurable: answer quality, grounding fidelity, latency, evaluation design, any local category comparison. | **HYPOTHESIS** |
| **H-E — DocuMind requires routing between multiple answering strategies (hybrid architecture)** | **Observed:** question categories behave differently under one engine (A0·P1 DATE 96.0 vs TABLE_ROW 0.0). **Supported hypothesis:** some categories may benefit from specialized structured workflows (inherited from H-C's PARTIALLY_SUPPORTED status). The Question Workflow Matrix defines 15 workflow types, giving routing a defined *design* surface. | **Unverified:** research ledger claim audit line 270 records "Hybrid QA is required" = **UNVERIFIED** — "No hybrid architecture has been tested. This is pure speculation." No router exists; **zero specialized answer engines exist to route to** (TARGET_ARCHITECTURE §7.2: all non-extractive modules are PLANNED). P3 category labels ≠ workflow types — routing labels are an imperfect proxy (evaluation limitation). Observing that "a router would improve the benchmark" has no supporting artifact. | Router accuracy against workflow types. Whether any single route yields a per-category P3 delta. Interaction effects between routes. Whether incremental introduction preserves equivalence. | **UNVERIFIED** |

**H-B split note:** the initial 4F.6-B matrix carried a single H-B row classified SUPPORTED. That conflated two different claims. H-B1 (the problem is real and distinct) is what the evidence supports; H-B2 (a separately implemented module is *required*) has never been directly tested. The ADR's separation decision is a design decision on indirect evidence — legitimate as a design, but not an experimental result.

---

## 4. Model Failure vs Architecture Failure (per failure class)

For each observed class: could another architecture (with the same document representation) solve it without changing the underlying model? **All attributions below are UNMEASURED until E0 runs** — the observations are verified, the causes are not.

| Failure class | Verified observation (population, metric) | Retrieval could explain? | Structure representation could solve? | Different extractive model could solve? | Deterministic/structured handler could solve? | Attribution status |
|---|---|---|---|---|---|---|
| **TABLE_CELL** | EM 0.0 in 9/12 evaluations (including **all six P3 systems**: A0, A1, A2, F2, G, H1), max 3.6 (A0·P2); F1 0.0–5.8 (A0·P3 F1 also 0.0) | Possible — gold table content may never be retrieved (never measured) | Plausible — no cell identity in chunks (§5.4); anchor/row/column context absent from representation | Weak evidence **against** on EM: A1→A2 swap left EM 0.0 (representation fixed); F1 did move (2.7→4.0 on P1) | Untested; raw predictions show serialization artifacts (`"450 | grams"` vs `"450"`) that a normalization/lookup layer would fix — some failures may be scoring/format, not structure | **UNMEASURED (E0)** |
| **TABLE_ROW** | EM 0.0 in **all 12** evaluations; F1 0.0–22.1 (A0·P3 = 0.0) | Same as above | Plausible — row identity absent by construction | No EM movement observed under model swap; F1 moved (9.6→21.1 P1) | Untested | **UNMEASURED (E0)** |
| **TABLE_COMPARISON** | **No population contains this class** | n/a | n/a | n/a | n/a | **UNMEASURED (no data)** |
| **LIST_ITEM** | EM 0.0 in **all 12** evaluations; F1 9.1–16.0 | Possible (never measured) | Plausible — list boundaries/order not represented | No EM movement under model swap | Untested | **UNMEASURED (E0)** |
| **LIST_ORDER** | **No population contains this class** | n/a | n/a | n/a | n/a | **UNMEASURED (no data)** |
| **NUMERIC** | Nonzero in 10/12 (up to 20.6 A0·P1; P3: A0 10.0, A1/A2/F2/G 5.0); zero only A2·P1 and H1·P3 | Possible | Limited relevance for simple lookups; relevant for table-sourced numbers | Mixed movement (A1 4.1 → A2 0.0 on P1) | Arithmetic/aggregation **by construction** outside span extraction (QUESTION_WORKFLOW_MATRIX) — but the arithmetic subset of the benchmark is unannotated, so its size is unknown | **PARTIALLY UNMEASURED (E0 must split look-up vs compute)** |
| **MULTI_CHUNK** | EM 0.0 in all 12; F1 0.9–22.1 | **Primary suspect — never measured** | Secondary (cross-chunk linking absent) | No EM movement under model swap | Bounded evidence workflow designed but nonexistent | **UNMEASURED (E0)** |
| **LONG_CONTEXT** | EM 0.0 in all 9 evaluations containing it; F1 0–12 | Primary suspect — never measured | Truncation/context-window share unknown (L4 would measure it) | Not tested at this scale | Nonexistent | **UNMEASURED (E0)** |
| **UNANSWERABLE** | Spurious (of 42): A1 42 and A2 42 on **both** P1 and P3; A0 15 on P1 and 15 on P3; F2 42, G 34, H1 23 (P3). A0's 64.3% abstention costs 49.9% false abstention on P1 and 55.7% on P3 | Not the binding axis — this is an answerability-decision failure (H-B1 OBSERVED) | Not applicable | Count/loss variations observed to fail (F2 zero, H1 collapse) but alternatives untested (Direction C) | **H-B2 UNVERIFIED** — separate module never implemented; A0 abstains in-architecture | **Problem OBSERVED; solution UNVERIFIED** |
| **DIRECT_SPAN** | Success reference class: 16.7 EM (A1/A2·P3, `DESCRIPTIVE_ONLY`), 12.5 EM / 47.4 F1 (F2·P3), up to 96.0 (DATE·A0·P1) | Unmeasured but currently the class where the pipeline works best | Not required | H-A's target class | Not needed (default route) | **Extraction demonstrably functional here** |
| **SECTION_SPECIFIC** | 0.0 in 11/12 (only A0·P1 = 1.8); F1 0.0–27.4 | Possible — section routing/anchors unmeasured | Plausible — section identity absent from chunks | No movement under model swap | Section detection untested (Gate 3 unmeasured) | **UNMEASURED (E0)** |

**Do not collapse these rows into "QA model weakness."** Each row's cause is currently unknown; that unknown is exactly E0's subject.

---

## 5. What Must NOT Be Inferred From This Matrix

Carried forward in substance from research ledger §16 and claim-strength audit §14, plus 4F.6-BR corrections:

1. Do NOT infer that any tested model is fundamentally incapable of learning no-answer behavior — only specific counts, one negative pool (H20), one learning rate, one epoch count were tested. A0's 64.3% P1 abstention shows abstention is attainable within the architecture.
2. Do NOT pool A0 across populations: P1 (7.8/14.4, false abstention 49.9%), P2 (3.2/8.6, 62.4%), and **P3 (2.1/12.0, 55.7%, aggregates only — `phase4f_5d/analysis/`) are three separate evaluations.** All three false-abstention values are far above Gate 2's < 20% criterion; C0·P3 per-example outputs were not stored, and its run provenance is unrecorded (see `PHASE4F6C_RECONCILIATION.md`).
3. Do NOT pool P1/P2/P3, do NOT compare raw `spurious_rate` or `false_abstention` fields across artifacts without the §2.3 definitions, and do NOT read A2's P1 result against A1's P2 result.
4. Do NOT treat H-B1's SUPPORTED status as support for H-B2. **The problem being real does not prove the separately-implemented module is required.**
5. Do NOT read universally-zero table/list EM as proof that structure is the cause — attribution is unmeasured (E0), and a scoring/serialization component is documented in the raw predictions.
6. Do NOT cite A3 (DeBERTa) as settled evidence in either direction — it is unreconciled in the ledger (4F.4 reports a NaN-loss collapse).
7. Do NOT convert category-dependent behavior (Observed) or workflow design (Supported hypothesis) into the claim that a hybrid architecture is required or would improve the benchmark (both UNVERIFIED).
8. Do NOT use any classification here as a ranking; no hypothesis is ranked, and no numerical confidence exists.

---

*Phase 4F.6-B decision artifact, reconciled 4F.6-BR. Planning only. No training. No benchmark change. No production change. No commit. No push.*
