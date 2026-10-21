# DocuMind — Architecture Decision Record

## Purpose

Document architecture alternatives, evidence from Phase 4F research, unresolved decisions, and decision gates. Every decision is grounded in observed evidence. No decisions are made prematurely.

---

## 1. Decision Framework

### 1.1 Decision States

| State | Meaning |
|-------|---------|
| DECIDED | Decision made, implementation approved |
| DEFERRED | Decision postponed, awaiting evidence |
| BLOCKED | Decision blocked on prerequisite |
| HYPOTHESIS | Proposed but not yet validated |

### 1.2 Evidence Classification

| Classification | Meaning |
|---------------|---------|
| OBSERVED | Directly measured in experiments |
| SUPPORTED | Strong evidence from multiple sources |
| PARTIALLY_SUPPORTED | Some evidence, but incomplete |
| HYPOTHESIS | Proposed but not validated |
| UNRESOLVED | Unknown, requires investigation |
| UNVERIFIED | Claimed but not verified |

---

## 2. DECIDED: Modular Monolith

**Decision:** DocuMind remains a modular monolith. No microservices.

**Evidence:**
- Current system is a monolith with clear module boundaries
- No scaling requirements that justify microservices complexity
- Team size does not warrant distributed system overhead
- Local deployment simplicity is valuable

**Alternatives considered:**
- Microservices: Rejected (overengineering for current scale)
- Serverless: Rejected (cold start latency, complexity)

**Status:** DECIDED

---

## 3. DECIDED: Answerability Separation

**Decision:** Answerability is a separate concern from answer extraction. The extractive QA model does NOT own answerability.

**Evidence (OBSERVED):**
- H1 experiment: DistilBERT EM collapsed to 0% when trained with 114 H20 negatives
- H1 null-score analysis: mean margin = -0.000344 (indistinguishable from noise)
- H1-R audit: CLS/null-score mechanism provides no useful signal
- F2 experiment: 20 unanswerable negatives produced 0% abstention on benchmark

**Alternatives considered:**
- Embed answerability in QA model: REJECTED (Phase 4F evidence)
- Separate answerability model: ACCEPTED
- Rule-based answerability: ACCEPTED (initial implementation)

**Status:** DECIDED

---

## 4. DECIDED: Evidence Provenance

**Decision:** Every answer traces to source evidence. Every evidence item traces to a document element. No answer exists without provenance.

**Evidence:**
- Phase 4F research identified inability to trace answers as a key limitation
- Current system has no provenance tracking
- Verification requires provenance

**Alternatives considered:**
- Optional provenance: REJECTED (defeats the purpose)
- Provenance only for verified answers: REJECTED (need provenance for debugging)

**Status:** DECIDED

---

## 5. DECIDED: Verification Gate

**Decision:** No answer reaches the user without passing through verification.

**Evidence:**
- Phase 4F: QA model produces unsupported answers
- Current system: No verification of answers
- Production risk: Unverified answers could be harmful

**Alternatives considered:**
- Optional verification: REJECTED (security risk)
- Post-answer verification only: ACCEPTED (initial implementation)

**Status:** DECIDED

---

## 6. DEFERRED: Model Base for Next Experiment

**Decision:** Which model base to use for the next QA experiment.

**Evidence:**
- DistilBERT: EM 0-7% across experiments
- BERT-base: EM 0-3% across experiments
- Production BERT: EM 3-8% (different training data)

**Alternatives considered:**
- DistilBERT with fewer negatives: HYPOTHESIS (not tested)
- BERT-base with fewer negatives: HYPOTHESIS (not tested)
- Larger model (RoBERTa, DeBERTa): HYPOTHESIS (not tested)
- Keep production BERT: HYPOTHESIS (not tested)

**Blocking question:** What is the optimal negative count? (20, 30, 50, 114?)

**Status:** DEFERRED

---

## 7. DEFERRED: Retrieval Strategy

**Decision:** Which retrieval strategy to implement first.

**Evidence:**
- Current: Dense retrieval only (sentence-transformers)
- No lexical retrieval (BM25) exists
- No hybrid fusion exists
- No reranking exists

**Alternatives considered:**
- Dense only: CURRENT (limited)
- Dense + BM25: HYPOTHESIS (likely better)
- Dense + BM25 + Reranking: HYPOTHESIS (likely best)
- Dense + BM25 + Reranking + Query Transformation: HYPOTHESIS (comprehensive)

**Blocking question:** Does retrieval quality limit answer quality? (Need to measure retrieval recall)

**Status:** DEFERRED

---

## 8. DEFERRED: Answer Engine Architecture

**Decision:** How to structure the answer engine.

**Evidence:**
- Current: Single extractive QA model for all question types
- Phase 4F: Extractive QA EM ceiling ~7%
- Table/list/numeric questions: 0% EM across all experiments

**Alternatives considered:**
- Single extractive QA: CURRENT (limited)
- Router + specialized modules: HYPOTHESIS (likely better)
- Router + specialized modules + grounded generator: HYPOTHESIS (comprehensive)
- End-to-end generative: HYPOTHESIS (unknown)

**Blocking question:** Does specialized routing improve answer quality?

**Status:** DEFERRED

---

## 9. DEFERRED: Grounded Generation

**Decision:** Whether to implement grounded generative QA.

**Evidence:**
- No generative QA exists in the current system
- Phase 4F did not test generative approaches
- Grounded generation could handle SUMMARY, LONG_CONTEXT, MULTI_HOP questions

**Alternatives considered:**
- No generation: CURRENT (limited)
- Extractive only: HYPOTHESIS (limited)
- Extractive + grounded generation: HYPOTHESIS (comprehensive)
- End-to-end generative: HYPOTHESIS (unknown)

**Blocking question:** Can extractive QA handle enough question types to be useful?

**Status:** DEFERRED

---

## 10. HYPOTHESIS: Structured Document Representation

**Hypothesis:** Adding structured document representation (sections, tables, lists) will improve answer quality for TABLE_CELL, TABLE_ROW, LIST_ITEM, SECTION_SPECIFIC questions.

**Evidence:**
- Phase 4E/4F: These categories have 0% EM
- Current system: Flat chunks cannot represent structure
- No direct test of structured representation

**Experiment needed:**
- Independent variable: Document representation (flat vs structured)
- Dependent variable: EM for TABLE_CELL, TABLE_ROW, LIST_ITEM, SECTION_SPECIFIC
- Control: Same QA model, same training data
- Dataset: P3 benchmark (182 examples)
- Success: EM > 0% for structured categories
- Failure: EM remains 0% despite structure

**Status:** HYPOTHESIS

---

## 11. HYPOTHESIS: Hybrid Retrieval

**Hypothesis:** Adding BM25 lexical retrieval alongside dense retrieval will improve retrieval recall.

**Evidence:**
- No lexical retrieval exists
- Dense retrieval may miss keyword-specific queries
- Hybrid retrieval is standard practice in RAG systems

**Experiment needed:**
- Independent variable: Retrieval strategy (dense vs dense+BM25)
- Dependent variable: Retrieval recall@K
- Control: Same query set, same document collection
- Dataset: P3 benchmark queries
- Success: Recall@10 improves by >5%
- Failure: No improvement or degradation

**Status:** HYPOTHESIS

---

## 12. HYPOTHESIS: Reranking

**Hypothesis:** Cross-encoder reranking will improve evidence precision.

**Evidence:**
- No reranking exists
- Dense retrieval may return irrelevant candidates
- Reranking is standard practice in retrieval pipelines

**Experiment needed:**
- Independent variable: Reranking (none vs cross-encoder)
- Dependent variable: Precision@K, MRR
- Control: Same retrieval results
- Dataset: P3 benchmark
- Success: Precision@5 improves by >10%
- Failure: No improvement or latency too high

**Status:** HYPOTHESIS

---

## 13. HYPOTHESIS: Negative Count Optimization

**Hypothesis:** Reducing H20 negative count from 114 to 20-50 will prevent model collapse while maintaining answerability learning.

**Evidence:**
- F2 (20 negatives): EM 2.9%, no abstention learned
- H1 (114 negatives): EM 0.0%, model collapsed
- Optimal count unknown between 20 and 114

**Experiment needed:**
- Independent variable: Negative count (20, 30, 50, 75, 114)
- Dependent variable: EM, F1, abstention rate, spurious rate
- Control: Same model base, same hyperparameters
- Dataset: P3 benchmark
- Success: EM > 2.9% with abstention > 0%
- Failure: All counts produce collapse or no abstention

**Status:** HYPOTHESIS

---

## 14. UNRESOLVED: Table QA Approach

**Unresolved:** How to handle table questions.

**Unknowns:**
- Can extractive QA handle table cells if table structure is preserved?
- Do table-specific models exist and are they practical?
- Can LLMs handle table reasoning with table context?

**Experiment needed:**
- Test extractive QA with structured table representation
- Test table-specific models if available
- Test LLM-based table reasoning

**Status:** UNRESOLVED

---

## 15. UNRESOLVED: Multi-hop Reasoning

**Unresolved:** How to handle questions requiring reasoning across multiple sources.

**Unknowns:**
- Can evidence fusion produce multi-hop answers?
- Do multi-hop reasoning models exist?
- Is multi-hop reasoning necessary for the target use case?

**Experiment needed:**
- Identify multi-hop questions in the benchmark
- Test evidence fusion approaches
- Test multi-hop models if available

**Status:** UNRESOLVED

---

## 16. UNRESOLVED: Grounded Generation vs Extractive

**Unresolved:** Whether to use grounded generation or extractive QA for synthesis questions.

**Unknowns:**
- Can extractive QA handle SUMMARY, LONG_CONTEXT questions?
- Does grounded generation improve answer quality?
- What is the latency cost of generation?

**Experiment needed:**
- Test extractive QA on SUMMARY/LONG_CONTEXT questions
- Test grounded generation on same questions
- Compare quality and latency

**Status:** UNRESOLVED

---

## 17. Decision Gates

### 17.1 Gate 1: Retrieval Quality

**Gate:** Before implementing specialized answer engines, verify that retrieval quality is sufficient.

**Criteria:**
- Retrieval recall@10 > 70% for answerable questions
- Retrieval recall@10 > 50% for unanswerable questions

**If gate fails:** Focus on retrieval improvement before answer engine work.

**If gate passes:** Proceed to answer engine work.

---

### 17.2 Gate 2: Answerability Separation

**Gate:** Before implementing verification, verify that answerability separation works.

**Criteria:**
- Answerability classifier accuracy > 80%
- Abstention rate for unanswerable questions > 50%
- False abstention rate for answerable questions < 20%

**If gate fails:** Improve answerability before verification work.

**If gate passes:** Proceed to verification work.

---

### 17.3 Gate 3: Structured Document Representation

**Gate:** Before implementing table/list answer engines, verify that structure extraction works.

**Criteria:**
- Table detection recall > 90%
- List detection recall > 90%
- Section detection recall > 95%

**If gate fails:** Improve structure extraction before specialized answer engines.

**If gate passes:** Proceed to table/list answer engines.

---

### 17.4 Gate 4: Production Readiness

**Gate:** Before deploying to production, verify end-to-end quality.

**Criteria:**
- Overall EM > 10% on P3 benchmark
- Unanswerable abstention > 60%
- False abstention < 15%
- Verification pass rate > 90%
- Latency < 2 seconds per query

**If gate fails:** Improve quality before production deployment.

**If gate passes:** Deploy to production.

---

## 18. Decision Timeline

| Decision | State | Expected Date | Blocking |
|----------|-------|---------------|----------|
| Modular monolith | DECIDED | Complete | No |
| Answerability separation | DECIDED | Complete | No |
| Evidence provenance | DECIDED | Complete | No |
| Verification gate | DECIDED | Complete | No |
| Model base | DEFERRED | After Gate 1 | Yes |
| Retrieval strategy | DEFERRED | After Gate 1 | Yes |
| Answer engine architecture | DEFERRED | After Gate 2 | Yes |
| Grounded generation | DEFERRED | After Gate 3 | Yes |
| Table QA approach | UNRESOLVED | After Gate 3 | Yes |
| Multi-hop reasoning | UNRESOLVED | After Gate 3 | Yes |

---

## 19. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Retrieval quality insufficient | Medium | High | Gate 1, fallback to dense-only |
| Answerability separation fails | Low | High | Gate 2, fallback to threshold |
| Table structure extraction fails | Medium | Medium | Gate 3, fallback to flat chunks |
| Model collapse with negatives | High | High | Negative count optimization |
| Verification too strict | Medium | Medium | Tunable verification thresholds |
| Latency too high | Medium | Medium | Caching, async processing |
| Production deployment breaks | Low | High | Gate 4, staged rollout |

---

## 20. Evidence Traceability

Every architecture decision traces to evidence:

| Decision | Evidence Source | Classification |
|----------|----------------|----------------|
| Answerability separation | H1 null-score analysis | OBSERVED |
| Evidence provenance | Phase 4F research ledger | SUPPORTED |
| Verification gate | Phase 4F answer quality | SUPPORTED |
| Modular monolith | Current system assessment | OBSERVED |
| Table structure extraction | Phase 4E/4F category failures | OBSERVED |
| Hybrid retrieval | Standard RAG practice | HYPOTHESIS |
| Reranking | Standard RAG practice | HYPOTHESIS |
| Negative count optimization | F2 vs H1 comparison | PARTIALLY_SUPPORTED |
| Grounded generation | SUMMARY/LONG_CONTEXT gaps | HYPOTHESIS |
| Multi-hop reasoning | MULTI_HOP category gaps | HYPOTHESIS |
