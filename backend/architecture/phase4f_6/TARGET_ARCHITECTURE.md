# DocuMind — Target Architecture

## Purpose

Proposed architecture for DocuMind that addresses the limitations identified by Phase 4E/4F research. This is a design document, not an implementation plan. Every design decision is grounded in observed evidence from the research ledger.

---

## 1. Architectural Principles

### 1.1 Document Intelligence First

Documents have a canonical structured representation. Chunks are retrieval units derived from document structure, not the only representation. The system distinguishes text, sections, tables, rows, cells, lists, pages, metadata, and chunks.

### 1.2 Retrieval as a Subsystem

Retrieval is a multi-strategy subsystem with fusion and reranking. No single retrieval strategy dominates.

### 1.3 Question-Driven Routing

Different question types require different computational workflows. The system routes questions to specialized answer engines rather than forcing everything through extractive QA.

### 1.4 Evidence Provenance

Every answer traces to source evidence. Every evidence item traces to a document element. Every document element traces to a document version. No answer exists without provenance.

### 1.5 Answerability Separation

Answerability is a separate concern from answer extraction. The system explicitly determines whether evidence is sufficient before attempting to answer.

### 1.6 Verification as a Gate

No answer reaches the user without passing through verification. Verification checks grounding, evidence sufficiency, and citation accuracy.

---

## 2. Target Backend Architecture

```
backend/
├── api/                    # API layer (FastAPI routers)
│   ├── documents.py
│   ├── chat.py
│   ├── embeddings.py
│   ├── verification.py
│   └── reliability.py
├── brain/                  # Orchestration (simplified)
│   ├── classifier.py       # Intent classification
│   ├── planner.py          # Workflow planning
│   ├── executor.py         # Workflow execution
│   ├── gate.py             # Quality gates
│   └── response.py         # Response assembly
├── documents/              # Document intelligence
│   ├── ingestion.py        # File parsing, text extraction
│   ├── structure.py        # Structure extraction (sections, tables, lists)
│   ├── chunking.py         # Smart chunking from structure
│   ├── models.py           # Document, Element, Chunk models
│   └── versioning.py       # Document versioning
├── retrieval/              # Retrieval subsystem
│   ├── dense.py            # Dense vector retrieval
│   ├── lexical.py          # BM25/lexical retrieval
│   ├── fusion.py           # Hybrid fusion
│   ├── reranker.py         # Cross-encoder reranking
│   └── query.py            # Query transformation
├── qa/                     # Answer engine
│   ├── engine.py           # Answer engine router
│   ├── extractive.py       # Extractive QA (current)
│   ├── table.py            # Table QA (planned)
│   ├── numeric.py          # Numeric reasoning (planned)
│   ├── list.py             # List reasoning (planned)
│   ├── multi_chunk.py      # Multi-chunk synthesis (planned)
│   └── grounded.py         # Grounded generation (planned)
├── answerability/          # Answerability determination
│   ├── evidence_sufficiency.py  # Evidence sufficiency check
│   ├── classifier.py       # Answerability classifier
│   └── decision.py         # Final answer/abstain decision
├── verification/           # Verification pipeline
│   ├── grounding.py        # Grounding check
│   ├── evidence.py         # Evidence check
│   ├── citation.py         # Citation/provenance check
│   └── pipeline.py         # Verification pipeline
├── reliability/            # Reliability tracking
│   ├── models.py
│   └── routes.py
├── media/                  # Media verification (separate pipeline)
│   ├── validation.py       # Media input validation
│   ├── extraction.py       # Frame/audio extraction
│   ├── features.py         # Feature extraction
│   ├── detection.py        # Detection models
│   └── pipeline.py         # Media verification pipeline
├── models/                 # Model registry
│   └── registry.py         # Model registry
├── storage/                # Persistence
│   ├── database.py         # SQLAlchemy models
│   ├── file_store.py       # File storage
│   └── vector_store.py     # Vector storage
├── evaluation/             # Evaluation harness
│   └── harness/
├── config.py               # Configuration
└── main.py                 # Application entry
```

---

## 3. Frontend Target Architecture

```
src/
├── App.tsx
├── pages/
│   ├── VerificationPage.tsx
│   └── ...
├── features/
│   ├── workspace/          # Workspace management
│   │   ├── WorkspaceContext.tsx
│   │   └── components/
│   ├── documents/          # Document management
│   │   ├── DocumentContext.tsx
│   │   └── components/
│   ├── chat/               # Chat/QA
│   │   ├── ChatContext.tsx
│   │   └── components/
│   ├── reliability/        # Reliability tracking
│   │   ├── ReliabilityContext.tsx
│   │   └── components/
│   ├── verification/       # Media verification
│   │   ├── VerificationContext.tsx
│   │   └── components/
│   └── settings/           # Settings
│       ├── SettingsContext.tsx
│       └── components/
├── components/
│   └── common/
│       └── TopNavBar.tsx
├── lib/
│   └── api.ts
└── types/
    └── index.ts
```

**Key change:** Split monolithic `WorkspaceContext` into feature-specific contexts. Each context owns its state and logic. Re-renders are scoped to the feature that changed.

---

## 4. Document Intelligence

### 4.1 Structured Document Model

```python
class Document:
    id: str
    filename: str
    content_type: str
    versions: List[DocumentVersion]

class DocumentVersion:
    id: str
    document_id: str
    created_at: datetime
    elements: List[DocumentElement]
    chunks: List[Chunk]
    metadata: dict

class DocumentElement:
    id: str
    version_id: str
    type: ElementType  # SECTION, TABLE, LIST, TEXT, PAGE
    content: str
    position: int
    parent_id: Optional[str]  # For nested elements
    children: List[str]  # Child element IDs

class Table(DocumentElement):
    rows: List[TableRow]
    columns: List[str]

class TableRow:
    cells: List[TableCell]
    position: int

class TableCell:
    content: str
    row_span: int
    col_span: int
    is_header: bool

class List(DocumentElement):
    items: List[ListItem]
    ordered: bool

class ListItem:
    content: str
    position: int
    children: List[str]  # Nested list items

class Chunk:
    id: str
    version_id: str
    content: str
    element_ids: List[str]  # Source elements
    start_char: int
    end_char: int
    metadata: dict
```

### 4.2 Structure Extraction Pipeline

```
Raw Document
  ↓
Text Extraction
  ↓
Section Detection (headings, hierarchy)
  ↓
Table Detection (HTML tables, Markdown tables, grid patterns)
  ↓
List Detection (bullets, numbers, nesting)
  ↓
Page Detection (if PDF)
  ↓
Element Hierarchy Assembly
  ↓
Smart Chunking (respecting element boundaries)
```

### 4.3 Smart Chunking Rules

- Never split a table across chunks
- Never split a list item across chunks
- Respect section boundaries when possible
- Preserve element provenance in chunk metadata
- Target chunk size: 256-512 tokens
- Overlap: 50-100 tokens between adjacent chunks

---

## 5. Retrieval Subsystem

### 5.1 Architecture

```
Query
  ↓
Query Transformation
  ↓
Dense Retrieval (top-K)
  +
Lexical Retrieval (top-K)
  ↓
Candidate Fusion (RRF or weighted)
  ↓
Cross-Encoder Reranking (top-N)
  ↓
Evidence Candidates
```

### 5.2 Query Transformation

```python
class QueryTransformer:
    """Transform user query into retrieval-optimized form."""
    
    def transform(self, query: str, question_type: QuestionType) -> RetrievalQuery:
        """
        For table questions: extract entity references
        For numeric questions: identify quantity terms
        For section questions: boost heading matches
        For multi-hop: decompose into sub-queries
        """
        ...
```

### 5.3 Hybrid Fusion

```python
class HybridFusion:
    """Fuse dense and lexical retrieval results."""
    
    def fuse(
        self,
        dense_results: List[Candidate],
        lexical_results: List[Candidate],
        alpha: float = 0.7,  # Dense weight
    ) -> List[Candidate]:
        """Reciprocal Rank Fusion or weighted combination."""
        ...
```

### 5.4 Reranking

```python
class Reranker:
    """Cross-encoder reranking for evidence precision."""
    
    def rerank(
        self,
        query: str,
        candidates: List[Candidate],
        top_n: int = 10,
    ) -> List[Evidence]:
        """Return reranked evidence candidates with scores."""
        ...
```

---

## 6. Question Understanding

### 6.1 Question Taxonomy

| Question Type | Description | Example |
|---------------|-------------|---------|
| DIRECT_SPAN | Answer is a contiguous text span | "What is the document title?" |
| SECTION_SPECIFIC | Answer requires specific section | "What does the methodology section say?" |
| NUMERIC | Answer involves numbers/math | "What is the total revenue?" |
| TABLE_CELL | Answer is a specific table cell | "What is Q3 revenue?" |
| TABLE_ROW | Answer is a table row | "Show all Q3 figures" |
| TABLE_COMPARISON | Answer compares table values | "Which quarter had highest revenue?" |
| LIST_ITEM | Answer is a list element | "What are the ingredients?" |
| LIST_ORDER | Answer requires list ordering | "What is step 3?" |
| MULTI_CHUNK | Answer spans multiple chunks | "Summarize the full document" |
| MULTI_HOP | Answer requires reasoning across sources | "How does A relate to B?" |
| COMPARISON | Answer compares two entities | "How does X differ from Y?" |
| AGGREGATION | Answer requires combining data | "What is the average?" |
| LONG_CONTEXT | Answer requires full document understanding | "What is the main argument?" |
| SUMMARY | Answer is a synthesis | "Summarize this document" |
| UNANSWERABLE | Evidence insufficient | "What is the CEO's birthday?" |

### 6.2 Classifier

```python
class QuestionClassifier:
    """Classify question type and determine workflow."""
    
    def classify(self, question: str, context: List[Evidence]) -> QuestionType:
        """
        Classification rules:
        1. Parse question structure (who/what/when/where/how/why)
        2. Check for table references
        3. Check for numerical operators
        4. Check for comparison keywords
        5. Check for aggregation keywords
        6. Check evidence sufficiency
        """
        ...
```

---

## 7. Answer Engine

### 7.1 Router

```python
class AnswerEngine:
    """Route questions to specialized answer modules."""
    
    def __init__(self):
        self.modules = {
            QuestionType.DIRECT_SPAN: ExtractiveQA(),
            QuestionType.SECTION_SPECIFIC: ExtractiveQA(),
            QuestionType.TABLE_CELL: TableQA(),
            QuestionType.TABLE_ROW: TableQA(),
            QuestionType.NUMERIC: NumericQA(),
            QuestionType.LIST_ITEM: ListQA(),
            QuestionType.MULTI_CHUNK: MultiChunkQA(),
            QuestionType.SUMMARY: GroundedGenerator(),
        }
    
    def answer(
        self,
        question: str,
        question_type: QuestionType,
        evidence: List[Evidence],
    ) -> AnswerCandidate:
        """Route to appropriate module and return candidate answer."""
        module = self.modules.get(question_type, self.default_module)
        return module.answer(question, evidence)
```

### 7.2 Module Status

| Module | Status | Evidence |
|--------|--------|----------|
| ExtractiveQA | IMPLEMENTED | Current production QA |
| TableQA | PLANNED | No implementation |
| NumericQA | PLANNED | No implementation |
| ListQA | PLANNED | No implementation |
| MultiChunkQA | PLANNED | No implementation |
| GroundedGenerator | PLANNED | No implementation |

---

## 8. Answerability

### 8.1 Architecture

```
Evidence Candidates
  ↓
Evidence Sufficiency Check
  ↓
Answerability Determination
  ↓
Answer / Abstain Decision
```

### 8.2 Evidence Sufficiency

```python
class EvidenceSufficiency:
    """Determine if evidence is sufficient to answer the question."""
    
    def check(
        self,
        question: str,
        question_type: QuestionType,
        evidence: List[Evidence],
    ) -> SufficiencyResult:
        """
        Checks:
        1. Evidence count > 0
        2. Evidence relevance scores above threshold
        3. Evidence covers question entities
        4. Evidence is from relevant sections
        5. For table questions: table structure matches
        6. For numeric questions: numbers present
        """
        ...
```

### 8.3 Separation from Extractive QA

**Critical design decision:** Answerability is NOT owned by the extractive QA model. The Phase 4F research conclusively showed that:
- DistilBERT cannot learn answerability with H20 negatives (EM collapsed to 0%)
- The CLS/null-score mechanism provides no useful signal (mean margin: -0.000344)
- Answerability must be a separate concern

The answerability layer sits above the answer engine and can:
- Reject evidence before answer extraction
- Override the answer engine's output
- Provide abstention with explanation

---

## 9. Verification Pipeline

### 9.1 Architecture

```
Candidate Answer
  ↓
Grounding Check
  ↓
Evidence Check
  ↓
Citation/Provenance Check
  ↓
Verified / Partial / Abstain
```

### 9.2 Grounding Check

```python
class GroundingCheck:
    """Verify answer is grounded in evidence."""
    
    def check(
        self,
        answer: str,
        evidence: List[Evidence],
        question: str,
    ) -> GroundingResult:
        """
        Checks:
        1. Answer tokens appear in evidence
        2. Answer is not hallucinated
        3. Answer is supported by evidence
        """
        ...
```

### 9.3 Citation Check

```python
class CitationCheck:
    """Verify answer citations are accurate."""
    
    def check(
        self,
        answer: str,
        citations: List[Citation],
        evidence: List[Evidence],
    ) -> CitationResult:
        """
        Checks:
        1. Every citation maps to a real document element
        2. Cited content matches actual content
        3. Citation context is accurate
        """
        ...
```

### 9.4 Verification Gate

**No answer reaches the user without passing verification.** This is a hard gate, not a soft filter. The verification pipeline produces one of:
- **VERIFIED:** Answer is grounded, evidence is sufficient, citations are accurate
- **PARTIAL:** Answer is partially grounded, some citations may be inaccurate
- **ABSTAIN:** Answer cannot be verified, system should abstain

---

## 10. Evidence Contract

### 10.1 Canonical Evidence Object

```python
class Evidence:
    id: str
    content: str
    source: EvidenceSource
    retrieval: RetrievalInfo
    verification: VerificationStatus
    provenance: Provenance

class EvidenceSource:
    document_id: str
    document_version_id: str
    element_id: str
    element_type: ElementType
    page: Optional[int]
    section: Optional[str]
    chunk_id: Optional[str]

class RetrievalInfo:
    strategy: str  # dense, lexical, hybrid
    score: float
    rank: int
    query: str

class Provenance:
    created_at: datetime
    created_by: str  # module that produced this evidence
    chain: List[ProvenanceStep]  # full provenance chain
```

### 10.2 Provenance Chain

Every answer must trace:

```
Answer
  ↓
Evidence (with retrieval info)
  ↓
Document Element (with position)
  ↓
Document Version (with hash)
  ↓
Original Document (with upload info)
```

---

## 11. Model Registry

### 11.1 Registry Design

```python
class ModelRegistry:
    """Central registry for all models used in DocuMind."""
    
    models: Dict[str, ModelEntry]

class ModelEntry:
    name: str
    version: str
    model_type: ModelType  # EMBEDDING, RERANKER, QA, ANSWERABILITY, TABLE, GENERATOR, VERIFICATION
    path: str
    checksum: str
    input_contract: dict
    output_contract: dict
    resource_requirements: dict
    evaluation_status: str
    availability: bool
```

### 11.2 Supported Model Types

| Type | Current | Planned |
|------|---------|---------|
| EMBEDDING | sentence-transformers | - |
| RERANKER | - | cross-encoder |
| QA | BERT extractive | - |
| ANSWERABILITY | - | separate model |
| TABLE | - | table QA model |
| GENERATOR | - | grounded generator |
| VERIFICATION | - | media verification |

---

## 12. Media Verification Pipeline

### 12.1 Separate Pipeline

Media verification is a **separate capability** from document QA. It does not share the document ingestion, retrieval, or answer pipelines.

```
Media Input
  ↓
Media Validation
  ↓
Frame/Audio Extraction
  ↓
Feature Extraction
  ↓
Detection Models
  ↓
Verification
  ↓
Evidence
  ↓
Result
```

### 12.2 Status

**NOT IMPLEMENTED.** The current `backend/verification/` is a stub. This pipeline requires:
- Frame extraction (video)
- Audio extraction
- Feature extraction
- Detection models (deepfake, manipulation)
- Verification logic

This remains unavailable until genuinely implemented.

---

## 13. Target Repository Structure

### 13.1 Principles

- Modular monolith (no microservices)
- Clear module boundaries
- Single responsibility per module
- Formal contracts between modules
- No circular dependencies

### 13.2 Why Each Directory Exists

| Directory | Purpose | Public Interface |
|-----------|---------|-----------------|
| `api/` | HTTP layer | Router definitions |
| `brain/` | Orchestration | BrainRequest → BrainResponse |
| `documents/` | Document intelligence | Document → StructuredDocument |
| `retrieval/` | Retrieval subsystem | Query → EvidenceCandidates |
| `qa/` | Answer engine | Evidence → AnswerCandidate |
| `answerability/` | Answerability | Evidence → SufficiencyResult |
| `verification/` | Verification | AnswerCandidate → VerifiedAnswer |
| `media/` | Media verification | MediaInput → MediaResult |
| `models/` | Model registry | ModelEntry → Model |
| `storage/` | Persistence | CRUD operations |
| `evaluation/` | Evaluation harness | Benchmark → Results |

---

## 14. Architecture Evolution Plan

### Stage 1: Architecture Contracts
- Define formal interfaces between modules
- Create protocol classes (ABC) for each module boundary
- **Prerequisite:** None
- **Affected modules:** All
- **Risk:** Low (interface-only changes)
- **Production behavior change:** No

### Stage 2: Question Understanding + Workflow Routing
- Implement question classifier
- Define workflow routing matrix
- **Prerequisite:** Stage 1
- **Affected modules:** brain, qa
- **Risk:** Low (new module, no existing behavior change)
- **Production behavior change:** No (routes to existing QA by default)

### Stage 3: Structured Document Representation
- Implement structure extraction
- Add table/list/section detection
- **Prerequisite:** Stage 1
- **Affected modules:** documents
- **Risk:** Medium (changes document model)
- **Production behavior change:** No (backward compatible)

### Stage 4: Retrieval Deepening
- Add lexical retrieval (BM25)
- Implement hybrid fusion
- Add reranking
- **Prerequisite:** Stage 1
- **Affected modules:** retrieval
- **Risk:** Medium (changes retrieval pipeline)
- **Production behavior change:** No (additive)

### Stage 5: Answer Engine Abstraction
- Create answer engine router
- Migrate current extractive QA to module
- **Prerequisite:** Stage 2
- **Affected modules:** qa
- **Risk:** Medium (refactors QA layer)
- **Production behavior change:** No (same behavior, different structure)

### Stage 6: Answerability
- Implement evidence sufficiency
- Implement answerability classifier
- **Prerequisite:** Stage 5
- **Affected modules:** answerability, qa
- **Risk:** High (adds new decision layer)
- **Production behavior change:** Yes (abstention behavior changes)

### Stage 7: Verification
- Implement grounding check
- Implement citation check
- Add verification gate
- **Prerequisite:** Stage 5
- **Affected modules:** verification
- **Risk:** High (adds gate to answer pipeline)
- **Production behavior change:** Yes (answers may be filtered)

### Stage 8: Specialized Table/Numeric/List Workflows
- Implement table QA module
- Implement numeric QA module
- Implement list QA module
- **Prerequisite:** Stage 3, Stage 5
- **Affected modules:** qa
- **Risk:** High (new answer engines)
- **Production behavior change:** Yes (new capabilities)

### Stage 9: Grounded Synthesis
- Implement grounded generator
- Implement multi-chunk synthesis
- **Prerequisite:** Stage 5, Stage 7
- **Affected modules:** qa
- **Risk:** High (new answer paradigm)
- **Production behavior change:** Yes (new capabilities)

### Stage 10: Production Validation
- End-to-end testing
- Performance validation
- Security audit
- **Prerequisite:** All previous stages
- **Risk:** Low (validation only)
- **Production behavior change:** No

---

## 15. Hard Constraints

- No microservices (modular monolith)
- No autonomous agents (bounded Brain)
- No SQL in Brain
- No model internals in Brain
- No document parsing in Brain
- No vector database internals in Brain
- Every answer has provenance
- Every answer passes verification
- Answerability is separate from answer extraction
- Media verification is a separate pipeline
