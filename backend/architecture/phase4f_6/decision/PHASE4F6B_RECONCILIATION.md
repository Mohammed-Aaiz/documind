# DocuMind — Phase 4F.6-BR Reconciliation Report

**Date:** 2026-09-23 · **Scope:** `backend/architecture/phase4f_6/decision/` only (five documents corrected; two created) · **Nature:** read-only research/documentation correction — the 4F.6-B documents were treated as claims requiring verification, and every numerical statement was traced to its underlying artifact, its evaluation population, and its metric definition.

**SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO — PRODUCTION UNCHANGED — BENCHMARK UNCHANGED — NO COMMIT — NO PUSH**

---

## Part 1 — Correction register

Format: **Previous claim → Evidence source → Verification result → Correction → Scientific impact → Changes E0 selection?**

### R1 — A2 vs A1 stated as a blanket negative

- **Previous claim:** "A2 (BERT-base, larger capacity) did not exceed A1: EM 0.0% vs 0.7% on P1, 0.9% vs 1.8% on P2. Larger model alone changed nothing."
- **Evidence source:** `experiments/results/A0|A1|A2/evaluation_results.json` (P1, 918), `phase4f_5/results/a0|a1|a2_test.json` (P2, 221), `research_ledger.json` (Direction B).
- **Verification result:** Numbers correct per population, claim wrong in framing. **P1:** A1 EM 0.7 / F1 6.9 vs A2 EM 0.0 / F1 9.3 → A2 lower EM but **higher F1** (mixed). **P2:** A1 EM 1.8 / F1 14.4 vs A2 EM 0.9 / F1 12.3 → A1 higher on both. P1/P2 runs carry protocol differences (different checkpoints / eval harness versions) — the ledger's own Direction B records "matches on P1, slightly worse on P2." P1 and P2 are different evaluations.
- **Correction:** All A2-vs-A1 language rewritten as population-specific mixed results; cross-population pooling forbidden (QA matrix §2.1, control matrix C1b-P1/C1b-P2 as two never-pooled blocks).
- **Scientific impact:** The capacity question remains **untested as a controlled variable** rather than "disproved" — H-A's contradicting column now says exactly that; no classification changed.
- **Changes E0 selection?** **NO.**

### R2 — "TABLE_CELL and TABLE_ROW are 0% EM across all experiments / all populations containing them"

- **Previous claim:** universal zero for both categories.
- **Evidence source:** the nine per-category result files (`A0/A1/A2 evaluation_results.json`, `a0/a1/a2_test.json`, `f2_benchmark.json`, `benchmark_result.json`, `h1_metric_recalculation.json`).
- **Verification result:** **False as stated for TABLE_CELL:** nonzero EM in A0·P1 1.1% (n=362), A1·P1 0.3% (n=362), A0·P2 3.6% (n=111) — zero in 6 of 9 evaluations, never above 3.6%. **True for TABLE_ROW:** 0.0% EM in all 9 evaluations containing it.
- **Correction:** Wording replaced by exact forms (QA matrix §2.2): TABLE_ROW/LIST_ITEM/MULTI_CHUNK universally zero (9/9 each), LONG_CONTEXT 6/6, TABLE_CELL "frequently zero, never above 3.6%" — each with population and n. All "table QA is impossible"-style phrasings removed.
- **Scientific impact:** The category-shaped failure pattern survives (it now rests on TABLE_ROW/LIST_ITEM/MULTI_CHUNK rather than on TABLE_CELL universality), so H-C's classification (**PARTIALLY_SUPPORTED**) is unchanged; the evidence is no longer overstated.
- **Changes E0 selection?** **NO.**

### R3 — "LIST_ITEM is not documented at 0% EM"

- **Previous claim:** uncertainty caveat implying LIST_ITEM may not be zero.
- **Evidence source:** same nine per-category files.
- **Verification result:** Opposite of the caveat — **LIST_ITEM EM 0.0% in all 9 evaluations** (F1 9.1–16.0%).
- **Correction:** Caveat replaced by the verified universal-zero statement (QA matrix §2.2).
- **Scientific impact:** Strengthens the category-pattern observation; still an observation, not causal attribution — H-C unchanged at **PARTIALLY_SUPPORTED**.
- **Changes E0 selection?** **NO.**

### R4 — Single H-B row classified SUPPORTED (problem conflated with solution)

- **Previous claim:** "H-B — Separate answerability … SUPPORTED."
- **Evidence source:** F2 (0/42 abstention), G (8/42, 34/42 spurious, `stable: false`), H1 (45.2% abstention with EM 0.0 + 10.7% false abstention), H1-R (null-score margins noise), A0 P1/P2 (64.3% at 49.9% FA; 62.4% FA on P2), ledger claim audit lines 268–271, ledger Direction C, ADR DECIDED status.
- **Verification result:** All cited numbers verified. The classification conflated two claims: **H-B1** (answerability is an important distinct problem) — every cited artifact speaks to this → **SUPPORTED**; **H-B2** (a separately implemented module is *required*) — **zero direct tests exist**; A0 abstains within the existing architecture; the ledger does not assert necessity and its live alternative (Direction C) is an *in-model* training redesign.
- **Correction:** Split into **H-B1 = SUPPORTED** and **H-B2 = UNVERIFIED** (QA matrix §3); E2 restated as the direct H-B2 test; GATE §6 notes the ADR decision is a design decision on indirect evidence.
- **Scientific impact:** Prevents "supported problem → supported solution" slippage; E2's possible outcomes now explicitly *move* H-B2 rather than confirming a foregone conclusion. The ADR's DECIDED status is preserved as a design decision (historical artifacts untouched).
- **Changes E0 selection?** **NO** — E0 isolates the H-B1 axis and explicitly does not resolve H-B2.

### R5 — E6 training-total arithmetic error

- **Previous claim:** "Total training examples move 506 → 614 → 700 as count moves 20 → 114."
- **Evidence source:** arithmetic on the fixed 486 answerable (verified in training-split artifacts: 486 + n).
- **Verification result:** Wrong. Correct totals: 20→506, 30→516, 50→536, 75→561, 114→600 (ratios 3.95 / 5.81 / 9.33 / 13.37 / 19.00%).
- **Correction:** Fixed in `EXPERIMENT_CANDIDATE_MATRIX.md` (E6) and `NEXT_EXPERIMENT_DECISION.md` §4.2; the linked-variable statement now reads: count, class ratio n/(486+n), and total 486+n are **one free parameter seen three ways**.
- **Scientific impact:** Strengthens (does not weaken) the confound conclusion; E6's disposition unchanged — retained with documented confound, not selected.
- **Changes E0 selection?** **NO.**

### R6 — A0 `false_abstention` dual values (49.9 vs 92.2)

- **Previous claim:** decision documents cited A0 P1 false abstention 49.9% without acknowledging a second artifact reporting 92.2%.
- **Evidence source:** `experiments/results/A0/evaluation_results.json` + `all_results.json` + `research_ledger.json` (49.9) vs `experiments/phase4f_4_results.json` + 4F.4 report text (92.2); metric code `run_experiment.py` (abstained answerable ÷ answerable), `evaluate.py` ((answerable − correct) ÷ answerable), `phase4f_5/evaluation/evaluation_protocol.json` (protocol definition).
- **Verification result:** **Not a data contradiction — a definition collision.** Protocol value: 437/876 = 49.9%. The 92.2 value = (876 − 68)/876 = answerable *error rate* mislabeled `false_abstention` by a second script (A1 analog: 0.0 protocol vs 99.3 in the 4F.4 report). P2's 62.4 = 138/221, protocol (confirmed via failure taxonomy ABSTAIN 138).
- **Correction:** Decision documents use **protocol values only**, with the definitional divergence recorded (QA matrix §2.3, control matrix rule 2).
- **Scientific impact:** None on conclusions (both values exceed ADR Gate 2's < 20% criterion); removes a future mixing hazard.
- **Changes E0 selection?** **NO.**

### R7 — `spurious_rate` denominator inconsistency discovered

- **Previous claim:** spurious rates compared across systems as like-for-like (e.g., F2 23.1% vs H1 54.8%).
- **Evidence source:** artifact fields + counts: F2 42/182 = 23.1 (of-all), A0 15/918 = 1.6 (of-all), A1/A2 42/918 = 4.6 (of-all), H1 23/42 = 54.8 (of-unanswerable), G 34/42 = 80.95 (of-unanswerable).
- **Verification result:** The raw fields use **two different denominators** across artifacts.
- **Correction:** Harmonized per-unanswerable column added (A0·P1 35.7%, A1 100%, A2 100%, F2·P3 100%, G 81.0%, H1 54.8%) — derived arithmetic from verified counts; raw fields never compared across artifacts (control matrix rule 3).
- **Scientific impact:** Cross-artifact spurious comparisons are now denominator-safe; no hypothesis affected.
- **Changes E0 selection?** **NO.**

### R8 — "Per-category P3 extraction success rates are not recorded in the reconciled ledger"

- **Previous claim:** per-category P3 numbers treated as unavailable/unknown.
- **Evidence source:** `f2_benchmark.json`, `h1_metric_recalculation.json`, `benchmark_result.json`.
- **Verification result:** True of the ledger's *summary*, false of the *evidence base* — full per-category P3 values exist in the source files (F2: DIRECT_SPAN 12.5/47.4, NUMERIC 5.0/39.8, all other answerable categories 0.0; H1: all categories 0.0 EM; G: identical EM to F2).
- **Correction:** The full per-category grid is now tabulated (QA matrix §2.2) and used as E1/E3 baselines; the "unknown" was moved to what is genuinely unknown — **stage attribution** (E0's subject).
- **Scientific impact:** Removes an overstated unknown; sharpens E0's novelty claim from "record per-category numbers" to "attribute failure stages."
- **Changes E0 selection?** **NO** — if anything, cleaner: per-category bookkeeping was never what E0 adds; the presence hierarchy is.

### R9 — G stability population ambiguous

- **Previous claim:** "G's ±0.1 → 25-point shift" presented without its population (readable as benchmark).
- **Evidence source:** `stability_analysis.json`, `validation_calibration.json` (85 answerable + 8 unanswerable), `benchmark_result.json`.
- **Verification result:** Stability was measured on **P3-validation (85+8)**: `max_abstention_shift 25.0`, `stable: false`. The benchmark G result (EM 2.86 / F1 16.92 / 19.05% / 27.86% / 80.95%) is separately verified. G's per-category EM equals F2's (same weights — threshold changed abstention, not extraction).
- **Correction:** Population tagged everywhere the shift is cited (GATE criterion 3, control matrix C2b, NEXT §4.3).
- **Scientific impact:** Prevents evaluation-population mixing; no classification changed.
- **Changes E0 selection?** **NO.**

### R10 — Production-model checksum scope

- **Previous claim:** control matrix cited only `cb9f1dde...f69deb`, while the research ledger records `df592aa8...` for the production model — apparent mismatch.
- **Evidence source:** `research_ledger.json` (`frozen_artifact_integrity`), RESEARCH_LEDGER.md (Hash/Path/Status table), direct `sha256sum backend/models/documind-qa/model.safetensors` (recomputed this phase).
- **Verification result:** **Scope difference, not a contradiction:** the ledger hash covers the **directory** (`Path: backend/models/documind-qa` — manifest scope), the `cb9f1dde...` value is the sha256 of **`model.safetensors` alone**, recomputed unchanged this phase. Model directory untouched (file mtimes 2026-09-02).
- **Correction:** Both hashes cited with explicit scope labels (control matrix §2 C0 and §5).
- **Scientific impact:** None; the integrity statement is now unambiguous.
- **Changes E0 selection?** **NO.**

### R11 — DATE precision ("96%" vs artifact)

- **Previous claim:** "EM 96% on DATE."
- **Evidence source:** `A0/evaluation_results.json`: DATE n=25, EM 96.0, F1 98.3.
- **Verification result:** Verified; normalized to the artifact's exact value 96.0 (no 96.4 appears anywhere in source artifacts).
- **Correction:** Exact value used in all documents.
- **Scientific impact:** None.
- **Changes E0 selection?** **NO.**

---

## Part 2 — Claims verified without change

| Claim | Artifact | Result |
|---|---|---|
| P3 = 182/140/42, sha256 `1166bf4f...50a41d0` | `qa_benchmark_v1.jsonl` (recomputed: 182 lines, 42 `is_impossible`) | VERIFIED, UNCHANGED |
| F2: EM 2.9 / F1 19.7 / 0 abstention / 42 spurious | `f2_benchmark.json` | VERIFIED |
| G: EM 2.86 / F1 16.92 / 19.05 / 27.86 / 80.95, threshold 1.5705 | `benchmark_result.json` | VERIFIED |
| H1: EM 0.0 / F1 11.0 / 45.2 / 10.7 / 54.8 | `h1_metric_recalculation.json`, `research_ledger.json` | VERIFIED |
| H1-R null-score: mean margin −0.000344, 3/42 positive, overlap < 0.25 SD; holdout inflated, benchmark reliable | `h1_null_score_analysis.json`, H1 reconciliation | VERIFIED |
| A0/A1/A2 overall per population (all eight figures) | evaluation_results / a*_test.json | VERIFIED |
| Ledger claim audit: "20 negatives insufficient" PARTIALLY_SUPPORTED; "H20 too different" HYPOTHESIS; "Hybrid QA is required" UNVERIFIED ("pure speculation"); "F2 ≈ A1/A2" SUPPORTED | RESEARCH_LEDGER.md lines 268–271 | VERIFIED VERBATIM |
| Ledger Directions A–E assessments; Direction C = ledger's own highest-information pick (class-balanced 50%); Direction D/E "not the highest-information next step" | RESEARCH_LEDGER.md §17 | VERIFIED |
| A0 P1 failure counts (ABSTAIN 437 / EXTRACT 371 / SPURIOUS 15 / +27 unanswerable-abstained / +68 correct = 918) | `A0/evaluation_results.json` taxonomy | VERIFIED, internally consistent |
| ADR Gate thresholds (Gate 1–4) and DECIDED/HYPOTHESIS/DEFERRED statuses | `ARCHITECTURE_DECISION_RECORD.md` | VERIFIED |
| Flat chunk model §5.4 (structure absent by construction) | `CURRENT_ARCHITECTURE.md` | VERIFIED (design fact, labeled as such) |

---

## Part 3 — Unresolved / UNVERIFIED claims carried forward

1. **Stored retrieval traces for P3** and **benchmark-level per-example raw predictions** — availability UNVERIFIED; E0.5 records them as feasibility dependencies (validation-split raw predictions do exist: `raw_predictions_validation.json`).
2. **A3 (DeBERTa)** — reported collapsed (NaN loss) in 4F.4 but **unreconciled in the ledger**; cited in neither direction as settled.
3. **ADR Gate 1 (retrieval recall) and Gate 3 (structure detection)** — unmeasured.
4. Whether class-balanced (50%) in-model training meets Gate 2 — untested (ledger Direction C); it remains the live H-B2 alternative to E2.
5. **Causal sufficiency of any localized bucket** — E0 localizes; no local artifact can prove a fix would work (attribution ≠ causation).
6. Arithmetic-vs-lookup split within P3 NUMERIC — unannotated; E0 must split it.

---

## Part 4 — Does any correction change E0 selection?

**No. Every item above answers "Changes E0 selection? = NO."**

- R2/R3/R8 **strengthen** E0's rationale: the zeros are real but unattributed, and per-category bookkeeping already exists — what is missing is exactly the presence/stage decomposition E0 provides.
- R6/R7/R10 are definitional/integrity fixes: they make the controls safe to compare without moving any partition.
- R1/R4/R5/R9 narrow wording or split claims without changing which bucket any failure sits in.

**Therefore: `HIGHEST_INFORMATION_CANDIDATE` remains E0 — a measurement study (zero changed variables), which discriminates H-A vs H-C vs retrieval/context on the answerable axis and isolates H-B1 on the answerability axis; which cannot resolve H-B2, H-D, H-E, or capacity-vs-data; whose result determines whether E1, E2, or E3 is interpretable first; and which proves no architecture.**

---

*Phase 4F.6-BR artifact. Correction record only. No historical artifact modified. No dataset/benchmark/production model changed. No training. No network/GitHub access. No commit. No push.*

---

**Addendum (Phase 4F.6-C-R):** this report's verification scope was the P1/P2 evidence plus the then-known P3 systems (F2/G/H1). The P3 A0/A1/A2 baseline results (`phase4f_5d/analysis/`) were discovered afterward; absence statements made in sibling documents during BR are superseded, and C0/C1b/H-A/H-B now carry those results under `DESCRIPTIVE_ONLY / COMPARABILITY_LIMITED` where provenance requires it. See `PHASE4F6C_RECONCILIATION.md`.
