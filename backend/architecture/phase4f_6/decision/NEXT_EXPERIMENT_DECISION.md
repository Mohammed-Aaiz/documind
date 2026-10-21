# DocuMind — Next Experiment Decision (Phase 4F.6-B)

## 1. Decision Statement

**HIGHEST_INFORMATION_CANDIDATE: E0 — Failure-Attribution Audit on the Frozen Benchmark (retrieval recall, gold-span presence, element-type attribution, conditional extraction success).**

This is a factual decision analysis about which planned experiment most effectively **discriminates between the competing hypotheses** H-A, H-B, H-C, H-D, and H-E. It is not a statement about the best experiment, the winning architecture, or a superior model. No hypothesis is ranked here.

**SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY — GITHUB ACCESSED: NO — NETWORK ACCESSED: NO — TRAINING RUN: NO**

---

## 2. Why E0 Discriminates Between the Current Hypotheses

The evidence base has one structural hole: **every observed benchmark failure is currently unattributed between four different causes** — retrieval failure, context construction failure, representation failure, and answer extraction failure. This is documented, not assumed:

- The architecture audit's own "supporting experiments" section lists retrieval recall measurement and structure-extraction evaluation as needed evidence — neither has been run.
- The QUESTION_WORKFLOW_MATRIX attributes category failures (e.g., TABLE_CELL EM 0.0% on P3 under F2, G, and H1 — and never above 3.6% in any of the nine measured evaluations) while simultaneously noting that no attribution measurement exists.
- The research ledger's claim audit does not classify any category failure as extraction-bound; it classifies the model-capacity question as untested.

Because of this hole, **the two leading intervention candidates cannot currently interpret their own results**:

| If E0 is not run first... | ...then this outcome is ambiguous |
|---|---|
| E1 (stronger extractive model) scores no gain | "Model insufficient" vs "gold evidence never reached the model" — indistinguishable |
| E1 gains on DIRECT_SPAN only | "Tables are representation-bound" vs "tables were never retrieved" — indistinguishable |
| E3 (structured handlers) scores no gain | "Structured workflows insufficient" vs "structure extraction failed" vs "retrieval missed the table" — indistinguishable |
| E2 (answerability gate) fails | "Gate features weak" vs "retrieved evidence for unanswerable is indistinguishable from answerable" — indistinguishable |

E0 resolves these ambiguities with **zero changed variables**: same dataset, same benchmark, same checkpoints, same thresholds, same evaluation logic. It partitions the P3 error budget into buckets that map one-to-one onto the hypotheses:

- **Extraction-bound residual on span categories** → makes H-A testable with a defined target (E1 becomes interpretable).
- **Representation-bound residual (gold source is a table/list, structure absent)** → makes H-C testable (E3 becomes the informative intervention) and predicts E1 low-yield.
- **Retrieval/context-bound residual** → neither H-A nor H-C is the current binding constraint; upstream retrieval work (ADR Gate 1) precedes both.
- **Answerable extraction succeeds while unanswerable spurious answers persist** → isolates the H-B1 problem axis cleanly so E2 (the direct H-B2 test) is interpretable.

No other candidate partitions more than one or two hypotheses, and every other candidate changes at least one variable, so a null result from any of them is confounded. E0 is also the smallest candidate: measurement-only, CPU-only, hours of runtime, no training, no production code change, no dataset change.

**What E0 is:** a measurement study, not a model experiment — zero changed variables (same dataset, benchmark, checkpoints, thresholds, evaluation logic), so **it cannot prove any architecture correct**; it only localizes failures so that later experiments become interpretable.

**What E0 cannot prove:** it cannot confirm any intervention's benefit; it **cannot resolve H-B2** (whether a separately implemented answerability module is required — E0 only isolates the H-B1 problem axis on the answerable/unanswerable split); it cannot validate a router (H-E); it says nothing about H-D; and it cannot separate model-capacity from data effects (those require training runs). It also localizes without proving causality — a representation-bound bucket does not prove a structured handler would succeed.

**Why no training is needed first:** E0 runs entirely on existing artifacts at zero variable cost, and its partition determines which of E1/E2/E3 is interpretable at all — running a training experiment before attribution makes even its null result ambiguous. E1/E2/E3/E4 remain governed by the controls in `EXPERIMENT_CONTROL_MATRIX.md`.

---

## 3. Candidate Assessment Summary (no ranking, factual)

| Candidate | Hypotheses it separates | Variables changed | Interpretability of a null result without E0 | Training required |
|---|---|---|---|---|
| E0 | H-A vs H-C vs retrieval/context (and conditions H-B/H-E interpretation) | None | n/a (measurement) | No |
| E1 | H-A only (weakly; H-C unaffected) | 1 (model) | Low — null is ambiguous | Yes |
| E2 | H-B only | 1 (gate) | Medium — depends on retrieval indistinguishability | No (deterministic variant) |
| E3 | H-C only (and only after Gate 3) | 1 (answer path for structured categories) | Low — ambiguous vs structure-extraction failure | No |
| E4 | H-D only | 1 (answering method) | Low — plus evaluation-design prerequisite | No |
| E5 (incremental) | H-E only, one route at a time | 1 per step | Low until its routes exist (E3 first) | Depends |
| E6 | nominally H-B, but confounded (§4) | count **and** ratio **and** total size | Low — and endpoints already exist | Yes |

---

## 4. Special Requirement — Evaluation of the 20 → 30 → 50 → 75 → 114 Negative-Count Sweep

The existing proposal is **not accepted automatically**. Findings:

### 4.1 What the sweep would distinguish
- Within a single model family (DistilBERT), a single negative type (H20), and fixed hyperparameters, it could map a **dose-response boundary between "no abstention" and "answerable collapse"**. That is a real, if narrow, contribution to H-B.

### 4.2 What it cannot distinguish
| Question the sweep is supposed to inform | Can the sweep resolve it? | Why |
|---|---|---|
| Data quantity problem | **No** | Count and class ratio are perfectly confounded: with answerable fixed at 486, ratio = n/(486+n). Total training size also co-varies (506 → 516 → 536 → 561 → 600 across the five points). Quantity, ratio, and optimization exposure are one free parameter, not three. |
| Model capacity problem | **No** | One model family only. Capacity was never varied (A2 vs A1 is a separate, P2-only comparison). |
| Answerability architecture problem | **No** | The CLS/null-score mechanism — the architectural element under suspicion — is held fixed at every count. H1-R showed that mechanism's signal is noise (mean margin −0.000344) at 114; counts 20–75 measure the same mechanism. |
| Distribution mismatch (are H20 negatives too different?) | **No** | The negative pool is held constant by design. |
| Extractive architecture mismatch (tables, arithmetic, synthesis) | **No** | Untouched by the sweep; table categories will remain wherever retrieval and representation leave them. |

### 4.3 Explicit statement of intertwining
**The sweep changes several intertwined factors (negative count, class ratio, total training-set size) without resolving the core architecture question (who owns answerability, and why do structured categories fail).** Both endpoints already exist as reconciled evidence — 20 = F2 (0% abstention) and 114 = H1 (collapse: 45.2% abstention, 54.8% spurious of the 42 unanswerable, EM 0.0). The five-point sweep would add intermediate boundary points of the same confounded variable, at the highest training cost of any candidate, while producing a result whose null case ("all counts fail") is ambiguous between "count was never the variable" and "the mechanism cannot learn this."

**Disposition: retained as candidate E6 with the confound documented; NOT selected as the highest-information candidate; any future run must pre-register the threshold, report threshold stability (G's ±0.1 → 25-point shift, `stable: false`, measured on P3-validation 85 answerable + 8 unanswerable — not on the benchmark), and be interpreted only within DistilBERT/H20 scope. What E6 cannot answer, stated exactly: whether model capacity is the cause; whether the H20 negative distribution is the cause; whether extractive QA is the architectural mismatch; whether separate answerability ownership is better.** The research ledger's separate class-balanced (50%) direction shares the count/ratio confound by construction and inherits the same disposition.

---

## 5. Special Requirement — Is the Evidence Sufficient to Justify a Hybrid Architecture?

**Answer: NO — not on current evidence.** The reason is not that tables and lists are difficult. The reason is what the evidence does and does not establish:

### 5.1 Which capabilities demonstrably require specialized computation
| Capability | Evidence | Status |
|---|---|---|
| Arithmetic aggregation (NUMERIC with operations) | Span extraction cannot compute by construction; QUESTION_WORKFLOW_MATRIX documents this | Requires specialized computation — by construction, UNVERIFIED against benchmark |
| Cross-chunk / long-context synthesis | Single-context span extraction cannot synthesize by construction | Requires specialized computation — by construction, UNVERIFIED against benchmark |
| Table cell/row with structure | Flat chunk model carries no cell identity (CURRENT_ARCHITECTURE §5.4); EM 0.0% on P3 (F2, G, H1); TABLE_ROW EM 0.0% in all 9 measured evaluations, TABLE_CELL never above 3.6% in any of 9 | Requires structure representation first; whether the handler or an improved extractive model would suffice is UNVERIFIED (attribution pending E0) |
| List ordering | Ordering not represented in chunks | Requires positional representation; UNVERIFIED |

### 5.2 Which capabilities still belong to extractive QA
- DIRECT_SPAN and SECTION_SPECIFIC are native to span extraction: F2 reaches F1 19.7% on P3 and A0 reaches EM 7.8% on P1, with strong DATE/ENTITY performance in P1. Nothing in the evidence suggests these need a different engine — but per-category attribution (E0) must confirm it.
- Extractive QA remains the **default route** for any capability not yet proven to need specialization.

### 5.3 Can routing be independently tested?
Yes, in principle and incrementally: a router whose default route is the existing engine must be **behaviorally identical** to the baseline, which is a directly testable seam (output equivalence on P3). Router accuracy can be measured against P3 category labels — with the acknowledged limitation that **category ≠ workflow type**, so the labels are a proxy, an evaluation limitation, not a validated routing ground truth.

### 5.4 Can a hybrid architecture be introduced incrementally?
Yes, structurally: MODULE_SEAMS defines the answer-engine seam, and TARGET_ARCHITECTURE §7.2 marks only ExtractiveQA as IMPLEMENTED. Each route can be added behind the seam with its own evidence and tests, defaulting to extractive. This is an architectural property, not evidence that routing pays off.

### 5.5 What experiment would actually validate the router?
The validation sequence, in dependency order:
1. **E0** — establishes which categories are genuinely answer-engine-bound (otherwise a router routes the wrong problems).
2. **Behavioral-equivalence step** — router installed with all routes defaulting to existing extractive QA; P3 outputs must be identical to C1. This validates the seam, not the hypothesis.
3. **One route at a time** (E3's table/list/numeric route first, since it is the only specialized engine with a defined design) — per-category P3 delta with all other categories held constant.
4. Only when at least one route shows a per-category delta does H-E accumulate SUPPORTED evidence; until then the research ledger's classification stands: **"Hybrid QA is required" = UNVERIFIED — no hybrid architecture has been tested.**

**Conclusion: a hybrid architecture is not justified or rejected by current evidence; it is untested. The premature-hybridization risk is real because zero specialized engines exist to route to.**

---

## 6. Evidence-Driven Decision Tree

```text
                        Current Evidence (P3, frozen)
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
     Run E0: attribute the                    Unanswerable side
     answerable error budget                  already isolated (OBSERVED:
              │                               F2 0% abstain, H1 collapse,
              │                               CLS noise, G unstable)
              │                                       │
    ┌─────────┼──────────────┐                        │
    │         │              │                        │
 Retrieval/  Gold present,  Gold source is            │
 context     extraction     table/list,               │
 bound       fails on       structure absent          │
    │        span cats           │                    │
    │         │                  │                    │
    ▼         ▼                  ▼                    ▼
 Gate 1:    H-A is testable  H-C is testable      H-B is testable
 retrieval  → E1 (model       → Gate 3 structure   → E2 (independent
 recall      change only,      accuracy, then E3     answerability gate,
 work        P3 vs C1)         (structured           engine unchanged)
 (Stage 4)                     handlers, span        │
                               path unchanged)       │
                                    │                │
                                    ▼                ▼
                              Per-category delta   Abstention on 42
                              off 0% with span     unanswerable with
                              cats regression-     bounded false
                              checked              abstention, stable
                                    │              threshold
                                    ▼                │
                              H-E becomes            │
                              testable:              │
                              E5 router default-     │
                              equivalence,           │
                              then one route         │
                              at a time              │
                                    │                │
                                    └───────┬────────┘
                                            │
                              Verification before answer
                              acceptance (provenance +
                              grounding + citation gate)
                                            │
                                            ▼
                                   Final answer / abstention

  H-D (grounded generation) branches ONLY from the context-bound
  and synthesis categories, after E0 shows they are genuinely
  context-bound rather than retrieval-bound — evaluation design
  first, P3 subset tagged separately from diagnostic subset.
```

Every leaf maps to an existing ADR decision gate: Gate 1 (retrieval), Gate 2 (answerability), Gate 3 (structure), Gate 4 (production readiness) — see `ARCHITECTURE_MIGRATION_GATE.md`.

---

## 7. Frozen Benchmark Protection

- The benchmark remains **182 examples / 140 answerable / 42 unanswerable**, hash `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`.
- Every candidate experiment above uses this benchmark unchanged.
- Any expanded diagnostic dataset (needed only for E4's synthesis subset and E0's element-type annotation layer) is labeled separately and never merged into the 182/140/42 totals.
- Element-type annotations created for E0 attach to example IDs; they do not edit `qa_benchmark_v1.jsonl`.

---

## 8. What Remains Unresolved

1. Whether answerable failures on P3 are retrieval-bound, representation-bound, or extraction-bound (E0 not yet run).
2. Whether any negative count, class ratio, or loss design lets the extractive model learn answerability (E6 confounded; class-balanced direction untested).
3. Whether a deterministic sufficiency gate meets ADR Gate 2 criteria (E2 not yet run).
4. Whether structure extraction meets Gate 3 on P3 source documents (unmeasured).
5. Whether a stronger extractive model moves P3 EM above the F2 corrected baseline (E1 not run; A3 unreconciled).
6. Whether grounded generation produces grounded answers at all locally (H-D entirely untested).
7. Whether routing earns its complexity (H-E untested; zero specialized engines exist).
8. Whether A0's abstention behavior can be reproduced **per-example** on P3 — A0·P3 **aggregates now exist** (EM 2.1 / F1 12.0, abstention 27/42 = 64.3%, false abstention 78/140 = 55.7%, spurious 15; `phase4f_5d/analysis/`, incorporated in 4F.6-C-R), but per-example C0·P3 outputs were not stored and the run's harness/checkpoint/tokenizer/params provenance is unrecorded (missing-provenance list: `PHASE4F6C_RECONCILIATION.md`); behavioral-equivalence testing (gate criterion 8) still requires a declared run capturing per-example outputs with hashes re-verified.

---

*Phase 4F.6-B decision artifact. Planning only. This document does not authorize implementation, training, or benchmark change.*
