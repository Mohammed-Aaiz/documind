# DocuMind — Module Seams Analysis

## Purpose

Analyze current and target module seams using deep-module terminology. Apply the deletion test to each module: if this module disappeared, would its complexity disappear or reappear across many callers?

---

## 1. Deep-Module Definitions

| Term | Definition |
|------|-----------|
| **Module** | A unit of code with a clear responsibility |
| **Interface** | The public API of a module |
| **Implementation** | The internal details of a module |
| **Seam** | A boundary between modules where they interact |
| **Adapter** | A translation layer between modules with incompatible interfaces |
| **Depth** | The ratio of functionality provided to interface complexity |
| **Leverage** | How much functionality a module enables relative to its size |
| **Locality** | How much related functionality is co-located in a module |

---

## 2. Current Module Analysis

### 2.1 Brain

**Current interface:**
```
BrainRequest → BrainResponse
```

**Current implementation:**
- classifier.py: Intent classification
- planner.py: Execution planning
- executor.py: Step execution
- gate.py: Quality gates
- response.py: Response assembly
- adapters.py: External service adapters
- types.py: Type definitions

**Deletion test:** If Brain disappeared, its complexity would reappear across every route handler that currently delegates to Brain. The classification, planning, execution, gating, and response logic would be scattered across chat/routes.py, documents/routes.py, etc.

**Depth assessment:** MEDIUM. The Brain provides significant functionality (orchestration, classification, planning) through a single interface. However, the internal modules (classifier, planner, executor) are tightly coupled.

**Leverage:** HIGH. Brain is used by every request handler.

**Locality:** MEDIUM. Related orchestration logic is co-located, but the internal modules leak implementation details through tight coupling.

**Current seam issues:**
- Planner and executor have no formal contract
- Adapters know about specific service implementations
- Gate logic is embedded in executor

---

### 2.2 Documents

**Current interface:**
```
upload(file) → Document
get_document(id) → Document
list_documents() → List[Document]
delete_document(id) → None
```

**Current implementation:**
- routes.py: API handlers
- models.py: SQLAlchemy models
- processing.py: File parsing
- chunking.py: Text chunking
- validation.py: Input validation

**Deletion test:** If Documents disappeared, every feature that needs document data would have to implement its own file parsing, chunking, and storage logic.

**Depth assessment:** LOW-MEDIUM. The module provides document management through a simple interface, but the internal processing pipeline (parse → chunk → store) is not abstracted.

**Leverage:** HIGH. Documents are central to the entire system.

**Locality:** HIGH. All document-related logic is co-located.

**Current seam issues:**
- No structure extraction (tables, lists, sections)
- Chunking is flat (no element awareness)
- No versioning

---

### 2.3 Embeddings

**Current interface:**
```
embed(text) → Vector
search(query, top_k) → List[Chunk]
```

**Current implementation:**
- routes.py: API handlers
- model.py: Model loading and inference

**Deletion test:** If Embeddings disappeared, every feature that needs search would have to implement its own vector search logic.

**Depth assessment:** MEDIUM. The module provides embedding and search through a simple interface.

**Leverage:** MEDIUM. Used by retrieval, but not by all features.

**Locality:** HIGH. All embedding logic is co-located.

**Current seam issues:**
- No lexical retrieval (BM25)
- No hybrid fusion
- No reranking
- No query transformation

---

### 2.4 Chat

**Current interface:**
```
chat(question, context) → Answer
```

**Current implementation:**
- routes.py: API handlers
- rag.py: RAG pipeline orchestration
- qa_model.py: QA model loading and inference

**Deletion test:** If Chat disappeared, the entire QA capability would be lost. No other module provides answer generation.

**Depth assessment:** LOW. The Chat module is a thin wrapper around the QA model. Most logic is in the route handler.

**Leverage:** HIGH. Chat is the primary user-facing feature.

**Locality:** MEDIUM. RAG orchestration is in rag.py, but the QA model is tightly coupled.

**Current seam issues:**
- QA model is the only answer engine
- No answerability separation
- No verification
- RAG pipeline is monolithic

---

### 2.5 Verification

**Current interface:**
```
verify(media) → VerificationResult
```

**Current implementation:**
- routes.py: API handlers
- models.py: Result models

**Deletion test:** If Verification disappeared, no verification capability would exist. However, the current implementation is a stub.

**Depth assessment:** LOW. The module is a stub with minimal functionality.

**Leverage:** LOW. Currently not integrated into the QA pipeline.

**Locality:** HIGH. All verification logic is co-located.

**Current seam issues:**
- Stub implementation
- Not integrated with QA pipeline
- No media verification capability

---

### 2.6 Reliability

**Current interface:**
```
record(outcome) → None
get_records() → List[ReliabilityRecord]
```

**Current implementation:**
- routes.py: API handlers
- models.py: Record models

**Deletion test:** If Reliability disappeared, no reliability tracking would exist. However, the current implementation is minimal.

**Depth assessment:** LOW. The module is minimal.

**Leverage:** LOW-MEDIUM. Useful for monitoring but not critical for core functionality.

**Locality:** HIGH.

**Current seam issues:**
- Minimal implementation
- Not integrated with other modules

---

## 3. Current Seam Map

```
                    ┌─────────────┐
                    │   Frontend  │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────┴──────┐
                    │   API Layer │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │  Documents │ │ Brain │ │    Chat    │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              │            │            │
              │     ┌──────┼──────┐     │
              │     │      │      │     │
        ┌─────┴──┐ ┌┴─────┐ ┌────┴──┐ ┌┴──────┐
        │  Embed │ │Class │ │ Plan  │ │QA Model│
        └────────┘ └──────┘ └───────┘ └───────┘
```

**Seam issues:**
1. Brain → Chat: Tight coupling, no formal contract
2. Brain → Documents: Brain knows about document internals
3. Chat → QA Model: QA model is the only answer engine
4. No verification seam in the QA pipeline
5. No answerability seam

---

## 4. Target Module Analysis

### 4.1 Brain (Simplified)

**Target interface:**
```
BrainRequest → BrainResponse
```

**Target implementation:**
- classifier.py: Intent classification (unchanged)
- planner.py: Workflow selection (simplified)
- executor.py: Workflow execution (delegates to specialized services)
- gate.py: Quality gates (unchanged)
- response.py: Response assembly (unchanged)

**Depth assessment:** HIGH. Brain provides orchestration through a simple interface. Implementation details are hidden behind service boundaries.

**Leverage:** HIGH. Brain is used by every request handler.

**Locality:** HIGH. Orchestration logic is co-located.

**Target seam issues:** None. Brain delegates to services through formal contracts.

---

### 4.2 Documents (Enhanced)

**Target interface:**
```
upload(file) → Document
get_document(id) → Document
get_structure(version_id) → List[DocumentElement]
get_chunks(version_id) → List[Chunk]
```

**Target implementation:**
- ingestion.py: File parsing, text extraction
- structure.py: Structure extraction (sections, tables, lists)
- chunking.py: Smart chunking from structure
- models.py: Domain models
- versioning.py: Document versioning

**Depth assessment:** HIGH. Documents provide document intelligence through a clear interface. Structure extraction is hidden behind the interface.

**Leverage:** HIGH. Documents are central to the system.

**Locality:** HIGH. All document logic is co-located.

**Target seam issues:** None. Structure extraction is an internal implementation detail.

---

### 4.3 Retrieval (New)

**Target interface:**
```
retrieve(query, question_type) → List[Evidence]
```

**Target implementation:**
- dense.py: Dense vector retrieval
- lexical.py: BM25/lexical retrieval
- fusion.py: Hybrid fusion
- reranker.py: Cross-encoder reranking
- query.py: Query transformation

**Depth assessment:** HIGH. Retrieval provides a complete retrieval pipeline through a single interface. Internal strategies are hidden.

**Leverage:** HIGH. Retrieval is used by every answer engine.

**Locality:** HIGH. All retrieval logic is co-located.

**Target seam issues:** None. Internal strategies are hidden behind the interface.

---

### 4.4 Answer Engine (New)

**Target interface:**
```
answer(question, question_type, evidence) → AnswerCandidate
```

**Target implementation:**
- engine.py: Router
- extractive.py: Extractive QA
- table.py: Table QA
- numeric.py: Numeric QA
- list.py: List QA
- multi_chunk.py: Multi-chunk synthesis
- grounded.py: Grounded generation

**Depth assessment:** HIGH. Answer Engine provides specialized answer generation through a single interface. Internal modules are hidden.

**Leverage:** HIGH. Answer Engine is the core answering capability.

**Locality:** HIGH. All answer logic is co-located.

**Target seam issues:** None. Internal modules are hidden behind the interface.

---

### 4.5 Answerability (New)

**Target interface:**
```
check_sufficiency(question, question_type, evidence) → SufficiencyResult
determine_answerability(sufficiency_result) → Answerability
```

**Target implementation:**
- evidence_sufficiency.py: Evidence sufficiency check
- classifier.py: Answerability classifier
- decision.py: Final answer/abstain decision

**Depth assessment:** HIGH. Answerability provides answerability determination through a clear interface.

**Leverage:** HIGH. Answerability prevents unsupported answers.

**Locality:** HIGH.

**Target seam issues:** None.

---

### 4.6 Verification (New)

**Target interface:**
```
verify(answer_candidate, evidence) → VerifiedAnswer | Abstention
```

**Target implementation:**
- grounding.py: Grounding check
- evidence.py: Evidence check
- citation.py: Citation/provenance check
- pipeline.py: Verification pipeline

**Depth assessment:** HIGH. Verification provides answer verification through a clear interface.

**Leverage:** HIGH. Verification prevents unverified answers.

**Locality:** HIGH.

**Target seam issues:** None.

---

## 5. Target Seam Map

```
                    ┌─────────────┐
                    │   Frontend  │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────┴──────┐
                    │   API Layer │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │Documents  │ │ Brain │ │Reliability │
        └─────┬─────┘ └───┬───┘ └───────────┘
              │            │
              │     ┌──────┼──────────────┐
              │     │      │              │
              │ ┌───┴───┐ ┌┴────────┐ ┌───┴────────┐
              │ │Retrieval│ │Answerability│ │Verification│
              │ └───┬───┘ └──────────┘ └────────────┘
              │     │
              │ ┌───┴────────────────┐
              │ │   Answer Engine    │
              │ │  ┌─────┬─────┬───┐ │
              │ │  │Ext  │Table│Num│ │
              │ │  └─────┴─────┴───┘ │
              │ └────────────────────┘
```

**Seam improvements:**
1. Brain → Retrieval: Formal contract through `retrieve()` interface
2. Brain → Answerability: Formal contract through `check_sufficiency()` interface
3. Brain → Answer Engine: Formal contract through `answer()` interface
4. Brain → Verification: Formal contract through `verify()` interface
5. Answer Engine → specialized modules: Router hides internal modules
6. No tight coupling between modules

---

## 6. Adapter Patterns

### 6.1 Current Adapters

| Adapter | From | To | Issue |
|---------|------|----|-------|
| Brain.adapters | Brain | Services | Knows about specific service implementations |
| Chat.rag | Chat | QA Model | Tight coupling to single QA model |

### 6.2 Target Adapters

| Adapter | From | To | Purpose |
|---------|------|----|---------|
| RetrievalAdapter | Brain | Retrieval | Translates Brain requests to retrieval queries |
| AnswerAdapter | Brain | Answer Engine | Translates Brain requests to answer engine calls |
| VerificationAdapter | Brain | Verification | Translates answer candidates to verification requests |
| DocumentAdapter | Brain | Documents | Translates Brain requests to document queries |

### 6.3 Adapter Design

```python
class RetrievalAdapter:
    """Adapter between Brain and Retrieval subsystem."""
    
    def adapt(self, request: BrainRequest) -> RetrievalQuery:
        """Translate Brain request to retrieval query."""
        ...
    
    def unadapt(self, results: List[Evidence]) -> BrainEvidence:
        """Translate retrieval results to Brain format."""
        ...
```

---

## 7. Module Dependency Rules

### 7.1 Allowed Dependencies

```
Brain → Retrieval, Answerability, Answer Engine, Verification, Documents
Retrieval → Documents, Embeddings
Answer Engine → Retrieval (for evidence)
Answerability → Evidence (from Retrieval)
Verification → Evidence, AnswerCandidate
Documents → Storage
Embeddings → Storage
```

### 7.2 Forbidden Dependencies

```
Brain → QA Model (direct)
Answer Engine → Documents (direct)
Retrieval → Answer Engine
Verification → Answer Engine
Any module → Brain (no circular dependencies)
Any module → Storage (except Documents and Embeddings)
```

---

## 8. Testability Assessment

### 8.1 Current Testability

| Module | Unit Testable | Integration Testable | Notes |
|--------|--------------|---------------------|-------|
| Brain | Partial | Yes | Tightly coupled to services |
| Documents | Yes | Yes | Clean interface |
| Embeddings | Yes | Yes | Clean interface |
| Chat | No | Yes | Tight coupling to QA model |
| Verification | Yes | Yes | Simple stub |
| Reliability | Yes | Yes | Simple implementation |

### 8.2 Target Testability

| Module | Unit Testable | Integration Testable | Notes |
|--------|--------------|---------------------|-------|
| Brain | Yes | Yes | Delegates to services |
| Documents | Yes | Yes | Clean interface |
| Retrieval | Yes | Yes | Clean interface |
| Answer Engine | Yes | Yes | Router pattern |
| Answerability | Yes | Yes | Clean interface |
| Verification | Yes | Yes | Clean interface |

---

## 9. Migration Seams

### 9.1 Current → Target Migration Points

| Migration | Current Module | Target Module | Seam |
|-----------|---------------|---------------|------|
| Document structure | documents/processing.py | documents/structure.py | New module |
| Smart chunking | documents/chunking.py | documents/chunking.py (enhanced) | Interface change |
| Hybrid retrieval | embeddings/routes.py | retrieval/dense.py + lexical.py | Split module |
| Reranking | (none) | retrieval/reranker.py | New module |
| Query transformation | (none) | retrieval/query.py | New module |
| Answer engine | chat/qa_model.py | qa/engine.py + extractive.py | Refactor |
| Table QA | (none) | qa/table.py | New module |
| Answerability | chat/rag.py (partial) | answerability/ | Extract module |
| Verification | verification/ (stub) | verification/ (enhanced) | Rewrite |

### 9.2 Migration Strategy

**Phase 1: Add new modules alongside existing code**
- Create retrieval/ with dense.py (migrate from embeddings/)
- Create retrieval/ with lexical.py (new)
- Create qa/engine.py (new)
- Create answerability/ (new)
- Enhance verification/ (rewrite)

**Phase 2: Route new queries through new modules**
- Brain routes to retrieval/ instead of embeddings/
- Brain routes to answerability/ before answer engine
- Brain routes to verification/ after answer engine

**Phase 3: Remove old modules**
- Remove embeddings/routes.py (replaced by retrieval/)
- Remove chat/rag.py (replaced by answerability/ + answer engine)
- Remove chat/qa_model.py (replaced by qa/engine.py)

---

## 10. Complexity Distribution

### 10.1 Current Complexity Distribution

```
Brain: 40% (orchestration, classification, planning, execution)
Documents: 25% (parsing, chunking, storage)
Chat: 20% (RAG, QA)
Embeddings: 10% (model, search)
Other: 5% (verification, reliability)
```

### 10.2 Target Complexity Distribution

```
Brain: 15% (simplified orchestration)
Documents: 25% (enhanced with structure extraction)
Retrieval: 20% (hybrid, reranking, fusion)
Answer Engine: 20% (specialized modules)
Answerability: 10% (sufficiency, classification)
Verification: 10% (grounding, citation)
```

**Key insight:** Complexity is redistributed from the monolithic Brain to specialized modules. Each module has higher depth (more functionality per interface unit).
