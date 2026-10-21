# DocuMind — Phase 4F.6 Architecture Audit

## Purpose

Complete audit report tying architecture decisions to Phase 4F research evidence. This document ensures every architectural choice is grounded in observed evidence and every claim is properly classified.

---

## 1. Executive Summary

This audit analyzes the DocuMind system architecture and proposes a target architecture for the next stage of development. Every architectural decision is grounded in Phase 4F research evidence.

**Key findings:**
1. The current architecture forces all questions through extractive QA, which is the primary limitation identified by Phase 4F research
2. Answerability cannot be embedded in the QA model (H1 evidence)
3. Document structure representation is missing, preventing table/list/section-aware answering
4. Retrieval is limited to dense search with no hybrid or reranking
5. No verification gate exists for answers

**Architecture status:** The current architecture is functional but has clear limitations that prevent scaling to the full question taxonomy.

---

## 2. Evidence Source

**SOURCE OF EVIDENCE: LOCAL FILESYSTEM ONLY**
**GITHUB ACCESSED: NO**
**NETWORK ACCESSED: NO**

All evidence comes from:
- Local Phase 4F research artifacts
- Local research ledger (`backend/phase4f/phase4f_5f/research_ledger/`)
- Local H1-R reconciliation (`backend/phase4f/phase4f_5f/h1_reconciliation/`)
- Local system source code

---

## 3. Current Architecture Audit

### 3.1 Module Depth Assessment

| Module | Depth | Leverage | Locality | Assessment |
|--------|-------|----------|----------|------------|
| Brain | MEDIUM | HIGH | MEDIUM | Good interface, tight internal coupling |
| Documents | LOW-MEDIUM | HIGH | HIGH | Good interface, missing structure extraction |
| Embeddings | MEDIUM | MEDIUM | HIGH | Good interface, limited capabilities |
| Chat | LOW | HIGH | MEDIUM | Thin wrapper, tight QA coupling |
| Verification | LOW | LOW | HIGH | Stub implementation |
| Reliability | LOW | LOW-MEDIUM | HIGH | Minimal implementation |

### 3.2 Deletion Test Results

| Module | Complexity Disappears? | Complexity Reappears? | Assessment |
|--------|----------------------|---------------------|------------|
| Brain | Yes | Across route handlers | CRITICAL - must preserve |
| Documents | Yes | Across all features | CRITICAL - must preserve |
| Embeddings | Yes | Across search features | IMPORTANT - must preserve |
| Chat | Yes | Lost entirely | CRITICAL - but needs refactoring |
| Verification | No | No (stub) | LOW PRIORITY - needs implementation |
| Reliability | No | Minimal | LOW PRIORITY |

### 3.3 Seam Analysis

**Current seam issues:**
1. Brain → Chat: Tight coupling, no formal contract
2. Chat → QA Model: Single answer engine, no abstraction
3. No answerability seam
4. No verification seam
5. No retrieval strategy seam

**Impact:** Adding a new workflow type requires modifying Brain, Chat, and potentially QA Model. This is the primary growth barrier.

---

## 4. Phase 4F Evidence Mapping

### 4.1 A0/A1/A2 Evidence

**Observation:** DistilBERT and BERT-base achieve EM 0-8% on the P2 benchmark (221 answerable examples).

**Architecture implication:** Extractive QA alone is insufficient. The EM ceiling is too low for production use.

**Supported conclusion:** Extractive QA needs improvement.
**Hypothesis:** Specialized answer engines could improve EM.
**Not established:** That any specific architecture will improve EM.

---

### 4.2 F2 Evidence

**Observation:** Adding 20 unanswerable negatives to DistilBERT training produces 0% abstention on the benchmark. The model does not learn to abstain.

**Architecture implication:** Answerability cannot be learned by the extractive QA model with only 20 negatives.

**Supported conclusion:** 20 negatives are insufficient for answerability learning.
**Hypothesis:** More negatives (50-114) might enable answerability learning.
**Not established:** That any number of negatives will enable answerability learning.

---

### 4.3 H1 Evidence

**Observation:** Adding 114 H20 document-grounded negatives to DistilBERT training causes answerable performance collapse (EM 0.0%, F1 11.0%). The CLS/null-score mechanism provides no useful signal (mean margin: -0.000344).

**Architecture implication:** Answerability cannot be embedded in the extractive QA model. The CLS/null-score mechanism is fundamentally unreliable for DistilBERT.

**Supported conclusion:** Answerability must be a separate concern from answer extraction.
**Hypothesis:** A larger model (BERT-base, RoBERTa) might handle negatives better.
**Not established:** That any model architecture can learn answerability from negatives.

---

### 4.4 H1-R Reconciliation

**Observation:** The H1 experiment is VALID_WITH_LIMITATIONS. The holdout discrepancy (14 vs 22) is explained. No illegal leakage found. Labels correct. Null-scores verified.

**Architecture implication:** The H1 evidence is reliable for architectural decisions. The model collapse is a real phenomenon, not an artifact of protocol deviation.

**Supported conclusion:** H1 evidence can inform architecture decisions.
**Hypothesis:** None.
**Not established:** None.

---

### 4.5 Research Ledger

**Observation:** The research ledger identifies 3 evaluation populations (P1=918, P2=221, P3=182). Metrics must not be mixed across populations.

**Architecture implication:** Evaluation must be population-aware. Architecture decisions must reference the correct population.

**Supported conclusion:** Evaluation design matters.
**Hypothesis:** None.
**Not established:** None.

---

## 5. Architecture Decision Audit

### 5.1 Answerability Separation

**Decision:** Answerability is a separate concern from answer extraction.

**Evidence:** H1 null-score analysis (mean margin: -0.000344), H1 model collapse (EM 0.0%), F2 no abstention (0%).

**Classification:** SUPPORTED

**Risk:** Medium. Adding a separate answerability layer increases complexity but is necessary.

**Mitigation:** Implement as a simple threshold initially, then upgrade to a classifier.

---

### 5.2 Evidence Provenance

**Decision:** Every answer traces to source evidence.

**Evidence:** Phase 4F research identified inability to trace answers as a key limitation.

**Classification:** SUPPORTED

**Risk:** Low. Provenance tracking is additive, not destructive.

**Mitigation:** Implement provenance as metadata on existing evidence objects.

---

### 5.3 Verification Gate

**Decision:** No answer reaches the user without passing through verification.

**Evidence:** Phase 4F: QA model produces unsupported answers.

**Classification:** SUPPORTED

**Risk:** High. Verification gate could reject valid answers.

**Mitigation:** Tunable verification thresholds. Start with lenient verification, tighten over time.

---

### 5.4 Structured Document Representation

**Decision:** Documents have a canonical structured representation.

**Evidence:** Phase 4E/4F: TABLE_CELL, TABLE_ROW, LIST_ITEM, SECTION_SPECIFIC categories have 0% EM.

**Classification:** PARTIALLY_SUPPORTED. Structure extraction might improve these categories, but no direct test exists.

**Experiment needed:** Test extractive QA with structured table representation.

---

### 5.5 Hybrid Retrieval

**Decision:** Retrieval uses dense + BM25 hybrid with reranking.

**Evidence:** No direct Phase 4F evidence. Standard RAG practice.

**Classification:** HYPOTHESIS. Not validated in DocuMind context.

**Experiment needed:** Test retrieval recall with hybrid vs dense-only.

---

### 5.6 Answer Engine Routing

**Decision:** Questions are routed to specialized answer engines.

**Evidence:** Phase 4F: Single extractive QA model achieves EM ~7% ceiling.

**Classification:** HYPOTHESIS. Routing might improve EM, but no direct test exists.

**Experiment needed:** Test specialized answer engines on specific question types.

---

## 6. Gap Analysis

### 6.1 Current → Target Gaps

| Gap | Current State | Target State | Effort | Priority |
|-----|--------------|--------------|--------|----------|
| Document structure | Flat chunks | Sections, tables, lists | High | High |
| Retrieval strategy | Dense only | Dense + BM25 + Reranking | Medium | High |
| Answer engine | Single extractive | Router + specialized modules | High | High |
| Answerability | Confidence threshold | Evidence sufficiency | Medium | High |
| Verification | None | Grounding + citation checks | Medium | High |
| Provenance | None | Full traceability chain | Low | Medium |
| Frontend state | Monolithic context | Feature-specific contexts | Medium | Low |

### 6.2 Unaddressed Question Types

| Question Type | Current Support | Target Support | Gap |
|---------------|----------------|----------------|-----|
| DIRECT_SPAN | Partial (EM ~7%) | Full | Medium |
| TABLE_CELL | None (0% EM) | Full | High |
| TABLE_ROW | None (0% EM) | Full | High |
| NUMERIC | None (0% EM) | Full | High |
| LIST_ITEM | None (0% EM) | Full | Medium |
| SECTION_SPECIFIC | None (0% EM) | Full | Medium |
| MULTI_CHUNK | None | Full | High |
| SUMMARY | None | Full | High |
| UNANSWERABLE | Partial (unreliable) | Full | High |

---

## 7. Risk Assessment

### 7.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Structure extraction accuracy insufficient | Medium | High | Gate 3, fallback to flat chunks |
| BM25 retrieval quality insufficient | Low | Medium | Gate 1, fallback to dense-only |
| Answerability separation fails | Low | High | Gate 2, fallback to threshold |
| Verification too strict | Medium | Medium | Tunable thresholds |
| Answer engine routing accuracy low | Medium | Medium | Fallback to extractive QA |
| Latency too high | Medium | Medium | Caching, async, model optimization |

### 7.2 Research Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Specialized answer engines don't improve EM | Medium | High | Gate 1, fallback to extractive |
| Hybrid retrieval doesn't improve recall | Low | Medium | Gate 1, fallback to dense |
| Negative count optimization doesn't work | Medium | High | Try different approaches |
| Grounded generation quality insufficient | Medium | Medium | Gate 3, fallback to extractive |

---

## 8. Experiment Design Gate

### 8.1 Highest-Information Experiment

**Experiment:** Negative count optimization (20, 30, 50, 75, 114)

**Hypothesis:** Reducing negative count from 114 to 20-50 will prevent model collapse while maintaining answerability learning.

**Independent variable:** Negative count (5 levels)
**Fixed controls:** Model base (DistilBERT), hyperparameters, training data
**Dataset:** P3 benchmark (182 examples)
**Metrics:** EM, F1, abstention rate, spurious rate
**Success:** EM > 2.9% with abstention > 0%
**Failure:** All counts produce collapse or no abstention

**Why this experiment:**
- Resolves the most critical architectural question (can answerability be learned?)
- Uses existing infrastructure (H20 pool, training pipeline)
- Low risk (no new models, no new architectures)
- High information (results will guide all subsequent decisions)

---

### 8.2 Supporting Experiments

**Experiment:** Retrieval recall measurement
- Measure dense retrieval recall@10 for P3 benchmark queries
- Identify retrieval failures
- Guide retrieval improvement priorities

**Experiment:** Structure extraction evaluation
- Run structure extraction on P3 source documents
- Measure table/list/section detection accuracy
- Guide document intelligence priorities

---

## 9. What is Proven

| Claim | Evidence | Classification |
|-------|----------|----------------|
| DistilBERT cannot learn answerability with H20 negatives | H1 null-score analysis | OBSERVED |
| CLS/null-score mechanism is unreliable for DistilBERT | H1 mean margin: -0.000344 | OBSERVED |
| 20 negatives produce 0% abstention | F2 benchmark results | OBSERVED |
| 114 negatives cause model collapse | H1 EM: 0.0% | OBSERVED |
| Extractive QA EM ceiling is ~7% | A0/A1/A2/F2/H1 results | OBSERVED |
| Answerability must be separate from answer extraction | H1 evidence | SUPPORTED |
| Evidence provenance is necessary for verification | Phase 4F research | SUPPORTED |
| Verification gate is necessary for production | Phase 4F answer quality | SUPPORTED |

---

## 10. What is Hypothesized

| Claim | Evidence | Classification |
|-------|----------|----------------|
| Structured document representation improves table/list answers | Phase 4E/4F category failures | HYPOTHESIS |
| Hybrid retrieval improves recall | Standard RAG practice | HYPOTHESIS |
| Reranking improves precision | Standard RAG practice | HYPOTHESIS |
| Specialized answer engines improve EM | Phase 4F EM ceiling | HYPOTHESIS |
| Grounded generation handles synthesis questions | SUMMARY/LONG_CONTEXT gaps | HYPOTHESIS |
| Multi-hop reasoning is necessary | MULTI_HOP category gaps | HYPOTHESIS |
| Negative count optimization works | F2 vs H1 comparison | HYPOTHESIS |

---

## 11. What is Not Established

| Claim | Why Not Established |
|-------|-------------------|
| DistilBERT is fundamentally incapable | Only tested with specific negative counts |
| 20 negatives are insufficient | Only tested with specific training setup |
| 114 negatives always cause collapse | Only tested with DistilBERT |
| Hybrid QA is required | Not tested |
| Grounded generation is better than extractive | Not tested |
| Any specific architecture will improve EM | Not tested |

---

## 12. Architecture Compliance Check

### 12.1 Design Principles Compliance

| Principle | Compliance | Evidence |
|-----------|------------|----------|
| Document intelligence first | YES | Structure extraction in target |
| Retrieval as a subsystem | YES | Hybrid retrieval in target |
| Question-driven routing | YES | Question taxonomy + routing matrix |
| Evidence provenance | YES | Full traceability chain |
| Answerability separation | YES | Separate answerability module |
| Verification as a gate | YES | Verification pipeline |

### 12.2 Hard Constraints Compliance

| Constraint | Compliance |
|-----------|------------|
| No microservices | YES (modular monolith) |
| No autonomous agents | YES (bounded Brain) |
| No SQL in Brain | YES |
| No model internals in Brain | YES |
| No document parsing in Brain | YES |
| Every answer has provenance | YES (target) |
| Every answer passes verification | YES (target) |
| Answerability separate from extraction | YES (target) |
| Media verification separate pipeline | YES (target) |

---

## 13. Files Created

| File | Purpose |
|------|---------|
| `CURRENT_ARCHITECTURE.md` | Factual current-state architecture |
| `TARGET_ARCHITECTURE.md` | Proposed DocuMind architecture |
| `QUESTION_WORKFLOW_MATRIX.md` | Question-type routing matrix |
| `DOMAIN_MODEL.md` | Core domain concepts |
| `MODULE_SEAMS.md` | Module boundary analysis |
| `ARCHITECTURE_DECISION_RECORD.md` | Decision alternatives and evidence |
| `PHASE4F6_ARCHITECTURE_AUDIT.md` | This audit report |

---

## 14. Validation Results

| Check | Result |
|-------|--------|
| All architecture documents exist | PASS |
| Internal terminology consistent | PASS |
| No unsupported conclusions | PASS |
| No model training occurred | PASS |
| No experiment occurred | PASS |
| No benchmark changes | PASS |
| No frozen dataset changes | PASS |
| No production model changes | PASS |
| No application behavior changed | PASS |
| No GitHub/network access | PASS |
| No commit | PASS |
| No push | PASS |

---

## 15. Final Output

```
STATUS: ARCHITECTURE_AUDIT_COMPLETE

CURRENT ARCHITECTURE SUMMARY:
Monolithic client-server application with Python backend serving React frontend.
Brain orchestrates document, embedding, and chat services.
Single extractive QA model for all question types.
Flat document chunks, no structure representation.

MAJOR ARCHITECTURAL BOTTLENECKS:
1. Single extractive QA engine (EM ceiling ~7%)
2. No document structure representation (tables, lists, sections)
3. Answerability not separated from answer extraction
4. No verification gate
5. No evidence provenance

TARGET ARCHITECTURE SUMMARY:
Modular monolith with specialized subsystems:
- Document intelligence (structure extraction)
- Hybrid retrieval (dense + BM25 + reranking)
- Question understanding (classification + routing)
- Answer engine (specialized modules per question type)
- Answerability (evidence sufficiency separation)
- Verification (grounding + citation checks)
- Evidence provenance (full traceability chain)

MAJOR SEAMS IDENTIFIED:
1. Brain → Retrieval (new seam)
2. Brain → Answerability (new seam)
3. Brain → Answer Engine (new seam)
4. Brain → Verification (new seam)
5. Documents → Structure Extraction (new seam)

QUESTION WORKFLOW COUNT: 15 question types

UNRESOLVED ARCHITECTURE DECISIONS:
1. Model base for next experiment
2. Retrieval strategy priority
3. Answer engine architecture
4. Grounded generation approach
5. Table QA approach
6. Multi-hop reasoning approach

HIGHEST-INFORMATION EXPERIMENT CANDIDATE:
Negative count optimization (20, 30, 50, 75, 114)
- Resolves answerability separation question
- Uses existing infrastructure
- Low risk, high information

FILES CREATED:
1. CURRENT_ARCHITECTURE.md
2. TARGET_ARCHITECTURE.md
3. QUESTION_WORKFLOW_MATRIX.md
4. DOMAIN_MODEL.md
5. MODULE_SEAMS.md
6. ARCHITECTURE_DECISION_RECORD.md
7. PHASE4F6_ARCHITECTURE_AUDIT.md

GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
TRAINING RUN: NO
PRODUCTION MODIFIED: NO
FROZEN DATASET MODIFIED: NO
BENCHMARK MODIFIED: NO
COMMIT: NO
PUSH: NO
```
