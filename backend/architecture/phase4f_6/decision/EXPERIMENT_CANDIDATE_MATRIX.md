# DocuMind — Experiment Candidate Matrix (Phase 4F.6-B, reconciled in 4F.6-BR)

> **Reconciliation status:** candidates re-derived from verified evidence on 2026-09-23. Corrections vs the initial draft: E0 replaced by a five-level evidence-presence hierarchy (exact-string matching alone was insufficient), E6 training-total arithmetic fixed (506 → 516 → 536 → 561 → 600), E2 outcomes rewritten against H-B1/H-B2, per-category P3 premise corrected. See `PHASE4F6B_RECONCILIATION.md`.
> **Updated in 4F.6-C-R:** P3 A0/A1/A2 aggregate results incorporated (E0 fixed-controls note, E1 baselines, E0 feasibility dependency (b) resolved for the F2/G pipeline) — see `PHASE4F6C_RECONCILIATION.md`.
>
> **SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO — PLANNING ONLY: NO EXPERIMENT IS EXECUTED HERE**

Candidates are derived from the evidence in `QA_HYPOTHESIS_MATRIX.md`. Controls per `EXPERIMENT_CONTROL_MATRIX.md`. Population tags are mandatory on every figure.

---

## E0 — Evidence-Presence & Failure-Attribution Audit on the Frozen Benchmark

| Field | Value |
|---|---|
| **Nature** | **Measurement study, not a model experiment** — no weights, thresholds, datasets, or evaluation logic change |
| **Hypothesis tested** | Conditions **H-A vs H-C vs retrieval/context** as the location of the answerable P3 error budget; isolates the **H-B1** axis. Does **not** test H-B2, H-D, or H-E |
| **Intervention** | None. Produces per-example attribution labels (Levels 1–5 below) as an **external diagnostic artifact** keyed by example_id |
| **Fixed controls** | Dataset, benchmark (182/140/42, hash), checkpoints (F2 primary; A0/A1/A2 on P1/P2 and **P3 aggregates** as historical context only — P3 per-example outputs for A0/A1/A2 do not exist), thresholds, evaluation logic, production model, retrieval index state |
| **Changed variables** | **Zero** |
| **Population** | P3 for attribution; P1/P2 only to interpret historical numbers (never pooled); DIAGNOSTIC for any new annotation |
| **Metrics** | Per-level presence rates (L1–L5) by category × answerability; error-budget partition (retrieval / context construction / representation / extraction); conditional extraction success (L4→L5); scoring-normalization near-miss share; unanswerable spurious-vs-abstain from existing predictions |
| **Expected runtime/resources** | CPU, hours. **No training, no GPU** — subject to the feasibility dependencies in E0.5 |
| **What it cannot prove** | Any intervention's benefit; H-B2 (module necessity); H-D; H-E; capacity-vs-data questions (need training); that representation change would *cause* improvement (localization ≠ causation); anything about DATE/ENTITY (absent from P3) or TABLE_COMPARISON/LIST_ORDER/SUMMARY/MULTI_HOP (no population contains them) |
| **Follow-up** | E1/E2/E3 selection is determined by the partition (E0.3) |

### E0.1 Evidence-presence hierarchy (replaces naive exact string matching)

Matching runs under a shared normalization: Unicode NFKC, casefold, whitespace collapse, punctuation strip, digit/format normalization (currency, thousands separators, decimals, `percent`↔`%`), plus the category-specific rules stated per level.

**Level 1 — Gold source/document identity matches retrieved source.**
- *Proves:* retrieval routed to the correct document.
- *Does not prove:* the answering part of the document was retrieved, or that any answer text is present.
- *False-negative risks:* document alias/version IDs, ID normalization mismatches.
- *False-positive risks:* right document, wrong region (document retrieved but answering chunks not in top-k) — L2/L3 then fail, which is the intended cascade.

**Level 2 — Gold source element/chunk is identifiable in the retrieved set** (section heading, table id, list id, or ingest-time chunk offset).
- *Proves:* the structural locus of the answer is retrievable and locatable.
- *Does not prove:* the locus contains the answer text (right table, wrong row is decided at L3).
- *False-negative risks:* missing/incorrect annotation; ingest-time sectionizer/table-detector failure (itself recorded — a detectable representation signal); element split across chunk boundaries.
- *False-positive risks:* duplicate tables/headings matching the wrong instance.
- *Requirement:* element locators are **supplemental annotation held as an external diagnostic artifact** (`DIAGNOSTIC`), keyed by example_id — the benchmark file is never edited.

**Level 3 — Gold answer span is present in the retrieved source text** (normalized containment in the retrieved chunk text as stored in the corpus).
- *Category rules:* numerics match under format normalization (`$1,247`≡`1247`, `91.4 percent`≡`91.4%`); tables match by **row-tuple co-presence** (anchor cell + value cell + header when present), not bare substring; lists match ignoring bullet/index tokens (order verified separately at representation level); whitespace/punctuation-insensitive; case-insensitive.
- *Proves:* retrieval + corpus construction delivered answer-bearing text to the model's input.
- *Does not prove:* the model's forward pass actually saw it (L4) or could select it (L5).
- *False-negative risks:* paraphrased gold (gold not verbatim — flagged explicitly), wrong span offsets, table serialized without the row anchor, list item split across chunks, numeric formats outside the normalizer (logged for manual review counts).
- *False-positive risks:* coincidental occurrence of short/numeric/generic answers elsewhere — mitigated by **anchor co-presence requirement (tables) and match-occurrence counting** (multiple matches → flagged ambiguous, reported as a separate rate).

**Level 4 — Gold answer string appears in the actual model input** (post-context-construction, post-truncation token window of the recorded run).
- *Proves:* extraction was possible in principle for that forward pass.
- *Does not prove:* selection was fair (position, distractors, competing matches).
- *False-negative risks:* tokenizer digit-splitting (`91. 4`) breaking string comparison — containment is evaluated on pre-tokenization text; offset-mapping bugs.
- *False-positive risks:* same coincidental-substring risks as L3, same mitigations.

**Level 5 — Model extracts the gold answer when evidence is known present** (given L4, does the recorded prediction match gold: EM, F1 > 0, and a third "scoring-normalizable match" rate under E0's normalizer).
- *Proves:* the model's extraction capability conditional on evidence presence — the only clean measurement of extraction quality.
- *Does not prove:* behavior where L4 is false; generalization to a different model or checkpoint; that any change would help.
- *False-negative risks:* scoring strictness — quantified by the scoring-normalizable rate (**measured only; evaluation logic is not changed by E0** — any scoring change would be a separate, declared decision).
- *False-positive risks:* exact matches by coincidence (negligible for long answers; covered by the ambiguity flag for 1-token numerics).

### E0.2 Error decomposition (two orthogonal axes — never mixed)

**Axis 1 — failure stage (computed over the 140 answerable P3 examples only):**

```text
corpus chunk for gold doc contains answer?   ── no ──► CONTEXT CONSTRUCTION FAILURE (ingest/chunking)
        │ yes
retrieved top-k contains answer-bearing chunk? ── no ──► RETRIEVAL FAILURE
        │ yes
element/structure context present (L2 & anchor co-presence)? ── no ──► REPRESENTATION FAILURE
        │ yes
present in model input post-truncation (L4)? ── no ──► CONTEXT-ASSEMBLY/TRUNCATION FAILURE
        │ yes
prediction correct (L5)?  ── no ──► EXTRACTION FAILURE
                               └── yes ──► SUCCESS
```

**Axis 2 — answerability (computed over all 182, independently of Axis 1):**
`ANSWERABLE` (answered-correct / answered-wrong / falsely-abstained — protocol definitions) vs `UNANSWERABLE` (abstained / spurious). Levels 1–5 are undefined for unanswerable examples (gold is empty) — they are never forced into stage buckets.

**E0 can identify (subject to E0.5):** per-category shares of retrieval failure, context-construction failure (corpus and assembly/truncation), representation failure (structure proxies), and extraction failure on answerable P3; the scoring-normalization near-miss share; the unanswerable spurious-vs-abstain split (from existing predictions).

**E0 cannot identify:** whether any fix helps (no intervention is run); H-B2 module necessity; H-D generation adequacy; H-E router benefit; capacity-vs-data causality; causal sufficiency of representation (a representation-bound bucket localizes, it does not prove a handler would succeed); behavior of DATE/ENTITY or classes with no population; anything beyond stored runs if retrieval traces/raw predictions do not exist (E0.5).

### E0.3 How each partition maps to the hypotheses

| Partition outcome | Interpretation | Next candidate |
|---|---|---|
| Extraction-bound residual large (L4 ✓, L5 ✗) on span categories | H-A has a defined, measurable target | **E1** becomes interpretable |
| Representation-bound dominant (L2/anchor fails; gold is table/list) | H-C gains its attribution; model swaps already failed to move EM | **E3** first; E1 predicted low-yield for these categories |
| Retrieval/context-bound dominant | Neither H-A nor H-C is the binding constraint; ADR Gate 1 precedes both | Gate 1 work (declared retrieval experiment) |
| Answerable extraction succeeds while unanswerable remains spurious | H-B1 axis isolated cleanly | **E2** becomes interpretable |
| Scoring-normalizable share large | Part of the zero-EM surface is normalization, not capability — recorded as a reclassification rate; changing scoring is a separate declared decision, **not** part of E0 | Re-scope E1/E3 targets after the declared decision |

No other candidate partitions more than one or two hypotheses; every other candidate changes at least one variable, confounding its own null result.

### E0.4 Benchmark protection

- The benchmark file `qa_benchmark_v1.jsonl` is **read-only for E0**: 182/140/42, hash `1166bf4f...50a41d0` before and after.
- Element locators and any expanded examples live in a separate `DIAGNOSTIC` artifact keyed by example_id; they are never merged into benchmark totals.

### E0.5 Feasibility dependencies (UNVERIFIED until E0 design time)

1. **Stored retrieval traces for P3** (top-k lists per example): availability **UNVERIFIED** in current artifacts. If absent, E0 Phase A includes a retrieval-instrumentation run — still no training, no benchmark edit, no evaluation-logic change — recorded as a control entry before use.
2. **Per-example benchmark raw predictions**: **RESOLVED for the F2/G pipeline** — `raw_predictions_benchmark.json` exists with all 182 examples (predicted answer, token indices, logits, null scores, confidence). For A0/A1/A2 on P3 only aggregates exist (`phase4f_5d/analysis/`) — per-example L5 coverage for those models would require a **declared** inference pass with the unchanged checkpoint (recorded as an optional dependency; declared, hashes re-verified, no weight change).

---

## E1 — Stronger extractive model under identical conditions

| Field | Value |
|---|---|
| Hypothesis tested | H-A |
| Intervention | Exactly one change: the model (architecture/initialization or training recipe — **one** of these, chosen pre-registration) |
| Fixed controls | Dataset (486+20-style recipe unchanged or the single declared recipe change), benchmark, evaluation logic, thresholds, architecture around the model |
| Changed variables | 1 (model) |
| Population / benchmark | P3 (182, frozen); control **C1** (F2: EM 2.9 / F1 19.7) |
| Metrics | EM, F1, protocol false abstention, unanswerable abstention, spurious (stated denominator) — all tagged P3; per-category delta vs C1 (P3 per-category baselines now exist for six systems: F2 — DIRECT_SPAN 12.5, NUMERIC 5.0, all other categories 0.0; A0/A1/A2 from `phase4f_5d/analysis/` — DIRECT_SPAN 4.2/16.7/16.7, all table/list categories 0.0 across all six; A0/A1/A2 are **aggregates only**, `DESCRIPTIVE_ONLY`) |
| Expected resources | One training run + one evaluation run (H1-pipeline scale); GPU-hours comparable to H1 |
| Possible outcomes & interpretation | *EM/F1 gain concentrated on span categories → H-A gains SUPPORTED evidence for that scope; table/list categories unchanged would reinforce the representation-bound reading. Null on P3 → H-A loses its remaining scope (after E0 says extraction-bound share was non-trivial, a null then indicts the specific recipe, not extraction generally). Category gains without E0 attribution remain ambiguous — hence E0 first.* |
| Cannot prove | Whether retrieval/representation was the binding constraint (E0's job); anything about H-B2/H-D/H-E; that capacity (vs recipe/data) caused any delta unless exactly one of those was varied |
| Follow-up | E3 if gains miss structured categories; E2 in parallel if the unanswerable axis was E0's finding |

## E2 — Independent answerability gate; answer engine unchanged

| Field | Value |
|---|---|
| Hypothesis tested | **H-B2** (directly) on the foundation of **H-B1** (already SUPPORTED) |
| Intervention | Exactly one change: a new abstention-decision layer in front of the unchanged engine (deterministic evidence-sufficiency variant first — no training) |
| Fixed controls | Model, weights, corpus, retrieval, benchmark, evaluation logic |
| Changed variables | 1 (gate) |
| Population / benchmark | P3 (182, frozen) |
| Metrics | Unanswerable abstention (ADR Gate 2: > 50%), protocol false abstention (< 20%), spurious (stated denominator), EM/F1 on answerable must not regress vs C1; **threshold pre-registered + stability report** (G's ±0.1 → 25-point shift measured on P3-validation 85+8 must not recur) |
| Expected resources | Implementation + offline evaluation; no training; CPU; hours–day |
| Possible outcomes & interpretation | *Meets Gate 2 with stable threshold → first direct SUPPORTED evidence for H-B2; the ADR's DECIDED status earns experimental backing. Abstention rises but false abstention explodes (G-like) → the sufficiency features are as weak as the CLS signal; H-B1 stays SUPPORTED, H-B2 stays UNVERIFIED and the trained in-model variant (ledger Direction C) becomes the competing test. No abstention change → retrieved evidence for unanswerable is indistinguishable at the feature level → points at retrieval/distribution, not ownership.* |
| Cannot prove | That a *trained* answerability model would behave the same (different intervention); anything about tables/lists/routing/generation; the cause of H1's collapse |
| Follow-up | Class-balanced in-model training (ledger Direction C) as the direct H-B2 alternative if the gate underperforms |

## E3 — Structured table/list/numeric handlers with extractive QA retained for simple spans

| Field | Value |
|---|---|
| Hypothesis tested | H-C |
| Intervention | Exactly one change: structured answer path for the declared structured categories; span path untouched |
| Fixed controls | Retrieval, model, corpus, benchmark, evaluation logic, span-path behavior |
| Changed variables | 1 (answer path for structured categories) |
| Population / benchmark | P3 (182, frozen); per-category deltas with all other categories regression-checked vs C1 |
| Metrics | Per-category EM/F1 on TABLE_CELL / TABLE_ROW / LIST_ITEM / NUMERIC (C1 baselines: all 0.0 except NUMERIC 5.0), overall EM/F1, no-regression on span categories |
| Prerequisites | ADR Gate 3 (table/list/section detection recall) **unmeasured** — must be measured first; E0 must show these categories are representation-bound rather than retrieval-bound |
| Expected resources | Deterministic implementation + evaluation; no training; CPU; days |
| Possible outcomes & interpretation | *Per-category gains off 0.0 with no span regression → H-C gains SUPPORTED evidence. Null → ambiguous unless E0 showed evidence presence: with E0's L1–L4 confirmed, a null indicts the handler design; without E0, "retrieval never delivered the table" survives.* |
| Cannot prove | H-A, H-B, H-D, H-E; that structure was the cause without E0's attribution; Gate 3-adequate detection quality (separate measurement) |
| Follow-up | E5's behavioral-equivalence step if a route proves out |

## E4 — Grounded generative answering on a controlled subset

| Field | Value |
|---|---|
| Hypothesis tested | H-D |
| Intervention | Exactly one change: answering method (grounded generation) on a pre-declared controlled subset |
| Fixed controls | Retrieval, corpus, benchmark (full 182 unchanged; subset results reported **in addition to**, never replacing, full-benchmark results) |
| Changed variables | 1 (answering method) + unavoidable evaluation-design work, declared in advance as a prerequisite — this is why E4 is not next |
| Population / benchmark | P3 + a separately labeled DIAGNOSTIC synthesis subset (never merged into 182/140/42) |
| Metrics | EM/F1 where defined; grounding fidelity; provenance completeness; abstention behavior (protocol) |
| Expected resources | New model + inference pipeline + evaluation design; GPU; the largest non-training cost of any candidate |
| Possible outcomes & interpretation | *Grounded, higher-scoring answers on synthesis categories → H-D gains SUPPORTED evidence for that scope. Ungrounded or worse → H-D loses its motivation. Either way the result is subset-scoped.* |
| Cannot prove | H-A/H-B/H-C; benchmark-wide superiority (subset design); production latency behavior |
| Follow-up | E0 + Gate 1 first regardless — the ledger already ranks D "not the highest-information next step" |

## E5 — Hybrid router + specialized engines (incremental form only)

| Field | Value |
|---|---|
| Hypothesis tested | H-E |
| Intervention | **As a single experiment it is excluded (multi-variable).** The admissible incremental form: (a) router installed with **all routes defaulting to existing extractive QA — P3 outputs must be identical to C1** (behavioral-equivalence step validating the seam, not the hypothesis); (b) **one route at a time** (E3's route first — the only specialized engine with a defined design), per-category delta with all else constant |
| Fixed controls | Everything except the single enabled route per step |
| Changed variables | 1 per step |
| Population / benchmark | P3 (182, frozen) |
| Metrics | Output equivalence vs C1 at step (a); per-category delta + whole-benchmark EM/F1 regression check at step (b); router accuracy vs P3 category labels — acknowledged as an **imperfect proxy** for workflow types (evaluation limitation) |
| Prerequisites | At least one specialized engine existing (E3 outcome); E0 attribution so the router routes the right problems |
| Expected resources | Implementation + equivalence tests + evaluation; no training for step (a); CPU |
| Possible outcomes & interpretation | *Equivalence fails → seam defect, H-E untested. Equivalence holds, route gains with no regression → H-E gains its first SUPPORTED evidence. Equivalence holds, no gain → H-E accrues NOT_SUPPORTED evidence for that route.* |
| Cannot prove | Global optimality of routing; interaction effects between routes (one-at-a-time design); H-D |
| Follow-up | Only after ≥1 route shows a per-category delta does the ledger's UNVERIFIED classification of "Hybrid QA is required" begin to move |

## E6 — Negative-count sweep (20 → 30 → 50 → 75 → 114) — retained, confound documented

| Field | Value |
|---|---|
| Hypothesis tested | Nominally H-B1-adjacent (data-count axis) — **it cannot reach H-B2 or H-A** |
| Intervention | Negative-count points {20, 30, 50, 75, 114} with everything else fixed (DistilBERT, H20 pool, LR, epochs) |
| Fixed controls | Model family, negative pool, hyperparameters, benchmark, evaluation logic |
| **Changed variables (mathematically linked — one free parameter)** | With answerable fixed at 486: **count n, class ratio n/(486+n), and total training size 486+n are the same variable seen three ways.** The proposal's five points: n = 20 → total 506, ratio 3.95%; n = 30 → 516, 5.81%; n = 50 → 536, 9.33%; n = 75 → 561, 13.37%; n = 114 → 600, 19.00% |
| Population / benchmark | P3 (182, frozen) |
| Metrics | EM, F1, unanswerable abstention, protocol false abstention, spurious (stated denominator); threshold pre-registered + stability reported (G's ±0.1 problem) |
| Expected resources | Five training runs + five evaluations — the **highest training cost of any candidate** |
| **What it explicitly cannot answer** | (1) whether **model capacity** is the cause — one model family only; (2) whether the **H20 negative distribution** is the cause — pool held constant by design; (3) whether **extractive QA is the architectural mismatch** — untouched by the sweep; (4) whether **separate answerability ownership** is better — the CLS/null-score mechanism (the element under suspicion) is identical at every count; H1-R showed that mechanism's signal is noise at 114, and counts 20–75 measure the same mechanism |
| Possible outcomes & interpretation | *A dose-response boundary between "no abstention" (20 = F2, observed) and "answerable collapse" (114 = H1, observed) — a real but narrow mapping within DistilBERT/H20 scope. "All counts fail" is ambiguous between "count was never the variable" and "the mechanism cannot learn this" — the null is uninterpretable without the H-B2 alternatives (E2, class-balanced Direction C).* |
| Cannot prove | Any of the four items above; anything about H-C/H-D/H-E; cross-family generalization |
| Disposition | **Retained as candidate with the confound documented; NOT selected as highest-information.** Both endpoints already exist as reconciled evidence, so the sweep would buy intermediate points of one confounded variable at the highest training cost. The ledger's separate class-balanced (50%) direction shares the ratio/total confound by construction and inherits the same disposition. Any future run pre-registers thresholds, reports stability, and is interpreted only within DistilBERT/H20 scope |

---

## Selection cross-reference

The highest-information determination — **`HIGHEST_INFORMATION_CANDIDATE: E0`** — and its reasoning (why a measurement study precedes every model experiment, which hypotheses it discriminates, which it cannot resolve) live in `NEXT_EXPERIMENT_DECISION.md`. This matrix records candidates and controls only; no hypothesis is ranked and no winner is declared.

---

*Phase 4F.6-B decision artifact, reconciled 4F.6-BR. Planning only. No training. No benchmark change. No production change. No commit. No push.*
