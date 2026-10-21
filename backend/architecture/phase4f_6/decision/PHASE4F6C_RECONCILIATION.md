# DocuMind — Phase 4F.6-C-R Reconciliation Report

**Date:** 2026-09-23 · **Scope:** decision artifacts in `backend/architecture/phase4f_6/decision/` only · **Nature:** reconciliation only — no execution, no inference, no retrieval instrumentation, no E0 run, no training, no benchmark/dataset/production modification.

**New evidence reconciled:** `backend/phase4f/phase4f_5d/analysis/{a0_benchmark_v1.json, a1_benchmark_v1.json, a2_benchmark_v1.json, benchmark_comparison.json}` (P3 baseline re-evaluation, 2026-09-21) and `backend/phase4f/phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt` (derived summary).

**Recorded P3 results (analysis JSONs = source of record):**
- **A0·P3:** EM 2.1, F1 12.0, abstention **27/42 = 64.3%**, false abstention **78/140 = 55.7%**, spurious count **15** (rate: 15/182 = 8.2% of all, or 15/42 = 35.7% of unanswerable)
- **A1·P3:** EM 3.6, F1 21.3, abstention 0/42, false abstention 0/140, spurious 42 (42/42 = 100%; field 23.1 = of-all-182)
- **A2·P3:** EM 3.6, F1 19.4, abstention 0/42, false abstention 0/140, spurious 42 (field 23.1 = of-all-182)

**SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO — E0 EXECUTED: NO**

---

## Task 1 — Audit: claims invalidated or made incomplete

| # | Document | Invalidated / incomplete claim | Disposition |
|---|---|---|---|
| A-1 | `EXPERIMENT_CONTROL_MATRIX.md` | "Populations with actual A0 results: P1 and P2 only … No A0 result exists on P3" | **INVALID — corrected:** C0·P3 block added with explicit denominators; C0 row now P1/P2/P3 (aggregates only) |
| A-2 | `EXPERIMENT_CONTROL_MATRIX.md` | C1b had no P3 block (capacity evidence incomplete) | **INCOMPLETE — corrected:** C1b-P3 row added under `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED` + provenance paragraph |
| A-3 | `NEXT_EXPERIMENT_DECISION.md` §8.8 | "no A0 result exists on P3; a declared C0-P3 run would be required before any such claim" | **INVALID — corrected:** aggregates recorded; per-example outputs + provenance gaps stated; declared run still required for equivalence |
| A-4 | `ARCHITECTURE_MIGRATION_GATE.md` criterion 8 | "**no A0 result on P3 exists and none may be assumed** — C0-P3 is a declared future run" | **INVALID — corrected:** aggregates incorporated; bit-for-bit equivalence still requires a declared per-example run |
| A-5 | `DECISION_SAFETY_CHECK.json` | population-mixing evidence: "No A0-P3 result invented — C0 states P1/P2 only" | **INVALID — regenerated this phase** (Task 8) |
| A-6 | `QA_HYPOTHESIS_MATRIX.md` §5.2 | "no A0 result on P3 exists (control C0 has P1 and P2 rows only)" | **INVALID — corrected:** three-population pooling prohibition with P3 figures |
| A-7 | `QA_HYPOTHESIS_MATRIX.md` H-B1 | Unknown: "Whether abstention quality differs on P3 for A0 (no A0-P3 result exists)" | **INVALID — corrected:** now measured (55.7% false abstention on P3); remaining unknown reframed to Gate-2 adequacy |
| A-8 | `QA_HYPOTHESIS_MATRIX.md` H-A | P3 arm absent from the capacity evidence; unknown said "no P3 model-change arm exists" | **INCOMPLETE — corrected:** three-population statements + comparability qualifier (Task 4) |
| A-9 | `QA_HYPOTHESIS_MATRIX.md` §2.2 / §4 | Evaluation-count denominators (6/9, 9/9, 7/9 …) excluded three P3 evaluations | **INCOMPLETE — corrected:** extended to 12 reconciled evaluations (Task 6); exact counts below |
| A-10 | `EXPERIMENT_CANDIDATE_MATRIX.md` E0 feasibility (b) | "benchmark-level per-example availability UNVERIFIED" | **STALE (superseded by 4F.6-C findings) — corrected:** `raw_predictions_benchmark.json` (182/182) exists for F2/G; A0/A1/A2 P3 remain aggregates-only |
| A-11 | `EXPERIMENT_CANDIDATE_MATRIX.md` E0/E1 baselines & fixed controls | referenced only P1/P2 A0/A1/A2 and F2 per-category | **INCOMPLETE — corrected:** P3 aggregates noted as historical context; six-system per-category baselines listed |
| A-12 | `PHASE4F6B_RECONCILIATION.md` | Verification scope was P1/P2 + then-known P3 systems | **NOT INVALID (no absence claim inside) — addendum appended** pointing here |

---

## Task 2 — C0 reconciliation (done)

`EXPERIMENT_CONTROL_MATRIX.md` now records **C0·P3 (182, aggregates only)**: EM 2.1 / F1 12.0 · abstention **27/42** · false abstention **78/140** · spurious **15** with both rates stated (**15/182 = 8.2% of all examples**, **15/42 = 35.7% of unanswerable**) · source `phase4f_5d/analysis/a0_benchmark_v1.json` + `benchmark_comparison.json`. All absence statements about A0·P3 are removed from live documents (validation grep, Task 13). C0's role text updated: aggregates exist, but **C1 remains the canonical P3 control** (per-example predictions + reconciled provenance) and gate-criterion-8 equivalence still requires a declared per-example run.

**Denominator definitions recorded (never mixed):** abstention = abstained unanswerable ÷ **42**; false abstention = abstained answerable ÷ **140** (protocol); spurious = answered unanswerable, quotable over **42** or over **182**, always labeled.

**Report-vs-JSON discrepancy (recorded, historical artifact unmodified):** the hardening report states A0 false abstention **35.7% (count 50)** and different tier numbers; `a0_benchmark_v1.json` states **55.7% (count 78)**. **The analysis JSONs are the source of record** (internally consistent: 78 + 62 answered = 140; user-supplied authoritative figures match the JSONs); the report is a derived summary with its own arithmetic slips (e.g., "spurious … 3.5 unanswerable questions" = 8.2% misapplied to 42).

---

## Task 3 — A1/A2 P3 capacity evidence: comparability determination

**Attempted provenance verification (all local):**

| Required item | Finding |
|---|---|
| Exact checkpoint path | **NOT RECORDED** in `a1/a2_benchmark_v1.json` (fields: model label, counts, overall, by_category, by_tier only — no eval_version, no checkpoint) |
| Checkpoint identifier/hash | Not linked to this run. 4F.4-R `checkpoint_audit.json` records candidate hashes `cb923d7b63f8561b` (A1 `experiments/results/A1/checkpoint_best/`) and `536fc6edb9b9a884` (A2 `…/A2/checkpoint_best/`) — **for the 4F.4 run; linkage to the 4F.5-D P3 pass is unrecorded**; checkpoint dirs still exist on disk |
| Tokenizer provenance | **NOT RECORDED** for this run. 4F.4-R `evaluation_parity_matrix.json` records per-model tokenizers (A0 distilbert-base-uncased, A1 distilbert-base-cased, A2 bert-base-cased) — covers 4F.4 only |
| Evaluation script/harness | **ABSENT FROM THE TREE** — no `.py` anywhere under `backend/phase4f` emits `em_answerable`/`by_tier` (bash `grep -rln --include=*.py` → no match); `phase4f_5d/` contains only `build_benchmark.py`; the analysis JSONs carry no script id or eval_version (unlike `a0_test.json`'s `4F.5-eval-v1`) |
| Benchmark version/hash | **VERIFIED equivalent by counts:** per-category n (24/24/16/20/16/10/10/42) and totals match the frozen manifest exactly; report cites SHA-256 `1166bf4f…50a41d0` (same as recomputed) |
| Preprocessing parameters | **NOT RECORDED** for this run (family convention: max_length 384, greedy, max_answer_length 50/100 — recorded only for 4F.4/4F.5-F families) |
| Identical conditions A1 vs A2 | **Indicated but unverifiable:** single re-evaluation pass summarized by one report, identical artifact schema and timestamps (all 2026-09-21 02:59); no harness artifact exists to prove identical parameters |

**Verdict: `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`.** The P3 A1-vs-A2 comparison may be quoted only as a descriptive observation (equal EM 3.6; A1 F1 21.3 > A2 19.4). It is **not** labeled a controlled capacity comparison. **Model capacity is neither proven nor disproven** — capacity is also confounded with architecture, pretraining, and tokenizer casing by construction. Never pooled with C1b-P1/C1b-P2.

---

## Task 4 — H-A revised (all three populations, never pooled)

`QA_HYPOTHESIS_MATRIX.md` H-A now states exactly:
- **P1:** A1 0.7/6.9 vs A2 0.0/9.3 → **mixed by metric** (A2 lower EM, higher F1)
- **P2:** A1 1.8/14.4 vs A2 0.9/12.3 → **favors A1 on both metrics**
- **P3:** A1 3.6/21.3 vs A2 3.6/19.4 → **equal EM, higher F1 for A1** — `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`
- Mandatory qualifier carried: **exact checkpoint/evaluation comparability must be verified before causal capacity interpretation**
- Supporting evidence extended with P3 aggregates (A1/A2 exceed F2 and A0 descriptively; DIRECT_SPAN 16.7 vs 12.5); contradicting evidence extended: model swaps never moved structured-category EM — now across **all six P3 systems**
- Classification: **PARTIALLY_SUPPORTED** (conservative, unchanged)

---

## Task 5 — H-B revised (split preserved)

- **H-B1 = SUPPORTED** (unchanged classification; observation strengthened): A0·P3 abstention 27/42 = 64.3% **on the frozen benchmark** at 78/140 = 55.7% false abstention, spurious 15/42 — in-architecture abstention demonstrated on P3 itself; A1/A2·P3 answer 42/42 unanswerable (zero abstention). A0 abstention now observed on P1 (64.3% @ 49.9% FA), P2 (62.4% FA), and P3 (64.3% @ 55.7% FA).
- **H-B2 = UNVERIFIED** (unchanged, explicitly not converted): the A0·P3 result is further descriptive evidence that abstention arises **within** the existing architecture; the separate module remains never implemented/never evaluated; the ledger does not claim necessity. A supported problem is not a supported solution.

---

## Task 6 — Table/list claims rechecked (denominators established)

Reconciled evaluation universe is now **12** (P1: A0/A1/A2 · P2: A0/A1/A2 · P3: A0/A1/A2/F2/G/H1). Every claim carries its denominator:

| Claim | Exact statement |
|---|---|
| TABLE_ROW EM | **0.0 in all 12**; F1 0.0–22.1 (A0·P3 F1 also 0.0) |
| LIST_ITEM EM | **0.0 in all 12**; F1 9.1–16.0 |
| MULTI_CHUNK EM | **0.0 in all 12**; F1 0.9–22.1 |
| LONG_CONTEXT EM | **0.0 in all 9 evaluations containing it** (absent from P2); F1 0.0–12.0 |
| TABLE_CELL EM | **zero in 9 of 12**, never above 3.6%; **all six P3 systems 0.0**; F1 0.0–5.8 |
| SECTION_SPECIFIC EM | zero in **11 of 12** (only nonzero A0·P1 1.8); F1 0.0–27.4 |
| NUMERIC EM | nonzero in **10 of 12** (zeros: A2·P1, H1·P3) |
| DIRECT_SPAN EM | nonzero in **9 of 12** (zeros: A1·P1, A2·P1, H1·P3) |
| DATE / ENTITY | P1 only (96.0 / 63.6 · A0·P1) — **absent from P2 and P3** |
| TABLE_COMPARISON / LIST_ORDER / SUMMARY / MULTI_HOP | **no population contains them — UNMEASURED, not zero** |

Phrases like "all experiments" are not used; "universally zero" is only used with the explicit reconciled-evaluation denominator (12/12 or 9/9).

---

## Task 7 — Research ledger gap

**`LEDGER_SYNC_REQUIRED`.** Evidence: `grep` over `research_ledger.json` and `RESEARCH_LEDGER.md` finds **no** `a0_benchmark_v1` / `a1_benchmark_v1` / `a2_benchmark_v1` / `benchmark_comparison` / `em_answerable` references; the ledger's only `phase4f_5d` mention is the P3 benchmark source under populations — the P3 A0/A1/A2 *results* are absent from the ledger. The ledger was **not modified** (historical artifact preservation).

**Three-layer distinction maintained:**
1. **Source experiment artifact** — `phase4f_5d/analysis/*.json` (reconciled here; source of record)
2. **Derived summary** — `phase4f_5d/reports/phase4f_5d_benchmark_hardening_report.txt` (discrepancies recorded, unmodified)
3. **Research ledger claim** — currently silent on these results → sync required before the ledger is treated as complete

---

## Task 8 — Safety check regenerated

`DECISION_SAFETY_CHECK.json` regenerated with the eight required checks (artifact inventory, population completeness, A0 P3 discovery, A1/A2 P3 discovery, checkpoint comparability, numerical claims, denominators, causal language) plus benchmark/production protection and E0-status separation. `checkpoint_comparability_check = UNVERIFIED` (the Task 3 missing provenance).

---

## Task 9 — E0 status kept separate

**E0 remains `E0_PROTOCOL_BLOCKED`** (`E0_READINESS_CHECK.md` §A/§B unchanged): blockers **B-1** P3 retrieval traces, **B-2** P3 stored chunk corpus, **B-3** standalone source-document provenance are untouched by this phase. The newly discovered P3 aggregates are **not** evidence of readiness — they are historical evaluation results, not provenance/retrieval/chunk artifacts. E0 nomenclature corrected per Task 10 (`L0 = provenance/integrity gate`, not one of the five evidence levels) in `E0_PROTOCOL.md` §3 and `E0_SCHEMA.json`; **no E0 execution, retrieval run, inference, or prediction regeneration occurred.**

---

## Task 11/12 — Files

**Modified (existing decision documents, Task 12):** `QA_HYPOTHESIS_MATRIX.md`, `EXPERIMENT_CANDIDATE_MATRIX.md`, `EXPERIMENT_CONTROL_MATRIX.md`, `NEXT_EXPERIMENT_DECISION.md`, `ARCHITECTURE_MIGRATION_GATE.md`, `PHASE4F6B_RECONCILIATION.md` (addendum only), `E0_PROTOCOL.md`, `E0_SCHEMA.json`, `E0_READINESS_CHECK.md`.
**Created:** `PHASE4F6C_RECONCILIATION.md` (this file); **regenerated:** `DECISION_SAFETY_CHECK.json`.
**Untouched:** everything outside `backend/architecture/phase4f_6/decision/` — benchmark, datasets, model weights, production code, historical Phase 4F artifacts, research ledger.

---

## Final validation summary (Task 13)

- P3 benchmark: 182 lines / 42 `is_impossible` / sha256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **unchanged**
- Source dataset sha256 `a5175303…f2e97` — **unchanged**; model.safetensors sha256 `cb9f1dde…f69deb` — **unchanged**
- `git status`: only the two untracked documentation directories — **no production/benchmark/dataset/historical file changed**
- No execution: no retrieval run, no inference, no prediction regeneration, no training (no script run beyond read-only shell inspection)
- A0·P3 absence claims: **zero remaining** in live documents (only labeled "previous claim" quotations inside this report)
- A1/A2 P3 comparison labeled `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED` at every occurrence (control matrix C1b, QA matrix §2.1/H-A, this report)
- Denominators explicit everywhere: 27/42, 78/140, 15/182 vs 15/42, category n, 182/140/42
- No causal claims: capacity neither proven nor disproven; no pooled averages; hypothesis classifications unchanged except evidence-extension (H-A PARTIALLY_SUPPORTED, H-B1 SUPPORTED, H-B2 UNVERIFIED)
- E0 separation: `E0_PROTOCOL_BLOCKED` unchanged and cited as such
- Historical artifacts: research ledger, hardening report, analysis JSONs — all read-only, unmodified
- Network/GitHub: **not accessed**; commit/push: **none**

---

# `FINAL STATUS: PHASE4F6C_BLOCKED`

Reconciliation of all documents is complete (Tasks 1–12), **but the comparability determination for the P3 A1/A2 capacity comparison cannot be made from local artifacts.** The exact missing provenance:

1. **The evaluation harness script** that produced `phase4f_5d/analysis/a{0,1,2}_benchmark_v1.json` and `benchmark_comparison.json` — absent from the local tree (no `.py` under `backend/phase4f` emits `em_answerable`/`by_tier`; no script id or `eval_version` recorded in the artifacts).
2. **Checkpoint identifier actually used in that run** for A1 and A2 — not recorded in the artifacts; 4F.4-R hashes (`cb923d7b63f8561b` / `536fc6edb9b9a884`, `checkpoint_best/` dirs) exist but their linkage to the P3 pass is unrecorded.
3. **Tokenizer provenance for that run** — not recorded (4F.4-R parity audit covers 4F.4 only).
4. **Preprocessing parameters for that run** (max_length, max_answer_length, span-decoding strategy, normalization) — not recorded in the artifacts.
5. **A run-level manifest/eval_version record** for the 4F.5-D baseline re-evaluation — absent (analysis JSONs carry none; the inventory in `reconciliation/experiment_artifact_inventory.json` predates 4F.5-D; the hardening report contains no method section).

Until items 1–5 exist, the P3 A1-vs-A2 result remains **`DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED`** and must not be used as a controlled capacity comparison. No substitute provenance was invented.

---

```
GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
TRAINING RUN: NO
INFERENCE RUN: NO
RETRIEVAL INSTRUMENTATION RUN: NO
E0 EXECUTED: NO
PRODUCTION MODIFIED: NO
FROZEN DATASET MODIFIED: NO
BENCHMARK MODIFIED: NO
HISTORICAL ARTIFACT MODIFIED: NO
COMMIT: NO
PUSH: NO
```

---

## Phase 4F.6-D addendum — FIRST TASK: A-2 stale-value correction record (2026-09-23)

**Mandated correction:** "correct the A-2 summary discrepancy found in Phase 4F.6-C-R — authoritative P3 category values are A0 DIRECT_SPAN EM 4.2 / NUMERIC EM 10.0; A1 16.7 / 5.0; A2 16.7 / 5.0. Find the stale A-2 values in the reconciliation artifacts and correct them."

**Verification performed (exhaustive, before any edit):**

1. **Source of truth re-read:** `a0_benchmark_v1.json`, `a1_benchmark_v1.json`, `a2_benchmark_v1.json` and `benchmark_comparison.json` all state — A0 DIRECT_SPAN EM 4.2 (n=24) / NUMERIC EM 10.0 (n=20); A1 16.7 / 5.0; A2 16.7 / 5.0. The four artifacts agree with each other and with the authoritative values given in the 4F.6-D brief.
2. **Stale-value sweep over the decision artifacts:** `grep -rn "7\.5\|7\.1\|4\.7" backend/architecture/phase4f_6/decision/` → **zero matches** (also zero for the slash-forms `0.0/7.5/4.7` and `0.0/7.1/12.5`).
3. **Every A-2-adjacent citation audited line-by-line:** `QA_HYPOTHESIS_MATRIX.md` §2.2 grid (DIRECT_SPAN row: A0·P3 4.2 / A1·P3 16.7 / A2·P3 16.7; NUMERIC row: A0·P3 10.0 / A1·P3 5.0 / A2·P3 5.0), H-A row ("A1/A2 DIRECT_SPAN EM 16.7"), §2.1 bullet, `EXPERIMENT_CANDIDATE_MATRIX.md` E1 ("DIRECT_SPAN 4.2/16.7/16.7"), `DECISION_SAFETY_CHECK.json` numerical-claim evidence ("DIRECT_SPAN 4.2/16.7/16.7") — **all already match the authoritative source values.**

**Verification result:** the stale triplets `DIRECT_SPAN 0.0/7.5/4.7` and `NUMERIC 0.0/7.1/12.5` exist **only in the 4F.6-C-R chat summary text** (the A-2 row as rendered in conversation output), not in any repository artifact. Every on-disk citation already carries the authoritative values.

**Correction:** no decision-document figure required changing (zero stale values found in files — none were "repaired" that did not need it). This addendum + the safety-check entry below constitute the required record. The stale chat-summary figures are superseded by the authoritative triplet restated here: **A0 = 4.2 / 10.0 · A1 = 16.7 / 5.0 · A2 = 16.7 / 5.0 (DIRECT_SPAN EM / NUMERIC EM, P3, n=24 / n=20).**

**Scientific impact:** none — no artifact ever carried the stale values, so no claim, matrix, or decision changes. **E0 selection unchanged** (E0 prerequisite recovery proceeds per 4F.6-D; this is a records correction only).

**Underlying experiment artifacts: unmodified** (read-only verification).
