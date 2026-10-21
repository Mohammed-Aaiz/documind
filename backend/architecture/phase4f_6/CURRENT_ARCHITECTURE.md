# DocuMind — Current Architecture

## Purpose

Factual reconstruction of the current DocuMind system as it exists on the local filesystem. No design aspirations. No future plans. Only what is implemented and observable.

---

## 1. High-Level Structure

```
DocuMind
├── Frontend (React/TypeScript)
│   └── src/
├── Backend (FastAPI/Python)
│   └── backend/
├── Production Model (BERT-based QA)
│   └── backend/models/documind-qa/
└── Research Artifacts
    └── backend/phase4f/
```

**Architecture type:** Monolithic client-server application with Python backend serving a React frontend. No microservices. No message queues. No background workers. All operations are synchronous HTTP request-response.

---

## 2. Frontend

**Location:** `src/`

### 2.1 Structure

```
src/
├── App.tsx                    # Root component with routing
├── pages/                     # Page-level components
│   ├── VerificationPage.tsx   # Media verification UI
│   └── ...
├── components/
│   └── common/
│       └── TopNavBar.tsx      # Navigation bar
├── context/
│   ├── WorkspaceContext.tsx   # Global workspace state
│   └── SettingsContext.tsx    # Application settings
├── lib/
│   └── api.ts                 # API client functions
└── types/
    └── index.ts               # TypeScript type definitions
```

### 2.2 Current Responsibilities

- **WorkspaceContext:** Manages global workspace state (selected workspace, documents, chat history). Acts as the primary state container for the application. Contains document management, chat management, and navigation state in a single context.
- **SettingsContext:** Manages application settings (API endpoints, feature flags).
- **api.ts:** HTTP client for backend API calls.
- **VerificationPage:** Media verification interface (currently non-functional backend).

### 2.3 Architectural Weakness

**WorkspaceContext is a monolithic state container.** It mixes workspace management, document management, chat state, and navigation into a single context. This creates:
- Unnecessary re-renders (changing chat state re-renders document lists)
- Difficult testing (cannot isolate document logic from chat logic)
- Growth barrier (adding reliability state would further bloat the context)

---

## 3. Backend API Layer

**Location:** `backend/main.py`

### 3.1 Current Responsibilities

- FastAPI application setup
- CORS configuration
- Router inclusion from domain modules
- Static file serving

### 3.2 Routers

| Router | Prefix | Source |
|--------|--------|--------|
| Documents | `/api/documents` | `backend/documents/routes.py` |
| Embeddings | `/api/embeddings` | `backend/embeddings/routes.py` |
| Chat | `/api/chat` | `backend/chat/routes.py` |
| Reliability | `/api/reliability` | `backend/reliability/routes.py` |
| Verification | `/api/verification` | `backend/verification/routes.py` |

### 3.3 Architectural Weakness

**No request validation layer.** Route handlers directly validate input. No middleware for request/response logging, rate limiting, or authentication. No health check endpoint. No API versioning.

---

## 4. Brain

**Location:** `backend/brain/`

### 4.1 Current Responsibilities

The Brain is the orchestration layer. It:
1. Receives user requests
2. Classifies intent
3. Plans execution steps
4. Dispatches to adapters
5. Collects results
6. Applies gates
7. Assembles responses

### 4.2 Modules

| Module | Responsibility | Current State |
|--------|---------------|---------------|
| `classifier.py` | Intent classification | Implemented, uses rule-based + LLM classification |
| `planner.py` | Execution planning | Implemented, generates step plans |
| `executor.py` | Step execution | Implemented, runs plans through adapters |
| `gate.py` | Quality gates | Implemented, applies validation rules |
| `response.py` | Response assembly | Implemented, formats final output |
| `adapters.py` | External service adapters | Implemented, wraps document/embedding/chat services |
| `types.py` | Type definitions | Implemented, defines request/response types |

### 4.3 Interfaces

- **Input:** `BrainRequest` (query, workspace_id, context)
- **Output:** `BrainResponse` (answer, sources, confidence, outcome)
- **Internal:** Steps flow through classifier → planner → executor → gate → response

### 4.4 Dependencies

- Document service (retrieval)
- Embedding service (vector search)
- Chat/QA service (answer generation)
- Verification service (media checks)

### 4.5 Architectural Weakness

**Brain owns too much orchestration logic.** The classifier, planner, and executor are tightly coupled. The planner generates steps that the executor understands, but there's no formal contract between them. Adding a new workflow type requires modifying planner, executor, and potentially classifier.

---

## 5. Document Ingestion Pipeline

**Location:** `backend/documents/`

### 5.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `routes.py` | Upload API, document CRUD |
| `models.py` | Document, DocumentChunk, DocumentMetadata models |
| `processing.py` | File parsing, text extraction |
| `chunking.py` | Text chunking (fixed-size with overlap) |
| `validation.py` | Input validation |

### 5.2 Processing Flow

```
Upload → Validate → Parse → Extract Text → Chunk → Store
```

### 5.3 Document Model

```python
class Document:
    id: str
    filename: str
    content_type: str
    file_size: int
    created_at: datetime

class DocumentChunk:
    id: str
    document_id: str
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict
```

### 5.4 Architectural Weakness

**Flat chunk model.** Documents are chunked into flat text segments. No representation of:
- Sections / headings
- Tables (rows, cells)
- Lists (items, ordering)
- Pages
- Element relationships

Chunks are the only document representation. The system cannot distinguish a table cell from a paragraph. This is the primary architectural limitation identified by Phase 4E/4F research.

---

## 6. Embeddings / Retrieval

**Location:** `backend/embeddings/`

### 6.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `routes.py` | Embedding API, similarity search |
| `model.py` | Embedding model loading and inference |

### 6.2 Retrieval Flow

```
Query → Embed → Vector Search → Top-K Chunks → Return
```

### 6.3 Current Capabilities

- Dense retrieval using sentence-transformers
- Cosine similarity search
- Top-K retrieval

### 6.4 Architectural Weakness

**Single retrieval strategy.** No lexical retrieval (BM25). No hybrid retrieval. No reranking. No query transformation. The retrieval pipeline is a single dense vector search with no fallback or fusion.

---

## 7. Chat / RAG / QA

**Location:** `backend/chat/`

### 7.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `routes.py` | Chat API, conversation management |
| `rag.py` | RAG pipeline orchestration |
| `qa_model.py` | Extractive QA model loading and inference |

### 7.2 RAG Flow

```
Question → Retrieve Context → Format Prompt → QA Model → Answer
```

### 7.3 QA Model

- **Base:** BERT-based extractive QA (production model)
- **Behavior:** Extracts answer spans from context
- **Answerability:** Determined by `insufficient_context` flag and confidence threshold
- **No-answer handling:** CLS token scoring for null answers

### 7.4 Architectural Weakness

**All questions forced through extractive QA.** The system cannot:
- Handle table-specific questions differently from text questions
- Perform numerical aggregation
- Handle multi-hop reasoning
- Generate grounded summaries
- Distinguish answerable from unanswerable questions reliably

The QA model is the single answer engine for all question types. This is the core limitation identified by Phase 4F research.

---

## 8. Verification

**Location:** `backend/verification/`

### 8.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `routes.py` | Verification API |
| `models.py` | Verification result models |

### 8.2 Current State

**Minimal implementation.** The verification module exists but has limited functionality. It can receive media inputs and return basic verification results, but no deep media analysis is implemented.

### 8.3 Architectural Weakness

**Verification is tightly coupled to the chat pipeline.** There's no separate media verification pipeline. No frame extraction. No audio analysis. No feature extraction. The module is a stub.

---

## 9. Reliability

**Location:** `backend/reliability/`

### 9.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `routes.py` | Reliability API |
| `models.py` | Reliability record models |

### 9.2 Current State

**Minimal implementation.** Records reliability metrics but has limited analysis capabilities.

---

## 10. Storage / Database

### 10.1 Current State

- **File storage:** Local filesystem (`backend/storage/file_store.py`)
- **Database:** SQLite (via SQLAlchemy)
- **Vector store:** In-memory or simple file-based

### 10.2 Architectural Weakness

**No structured document storage.** The database stores documents as blobs and chunks as text. No relational model for document elements. No versioning. No provenance tracking.

---

## 11. Evaluation

**Location:** `backend/evaluation/`

### 11.1 Current Responsibilities

| Module | Responsibility |
|--------|---------------|
| `harness/evaluator.py` | Evaluation runner |
| `harness/corpus.py` | Corpus management |
| `harness/extraction.py` | Answer extraction |

### 11.2 Current State

**Functional evaluation harness.** Can run extractive QA evaluation against benchmarks. Phase 4F used this extensively.

---

## 12. Configuration

**Location:** `backend/config.py`

### 12.1 Current Responsibilities

- Environment variable loading
- Model path configuration
- Feature flags
- API endpoint configuration

---

## 13. Key Architectural Weaknesses Summary

| Weakness | Impact | Evidence |
|----------|--------|----------|
| Flat chunk model | Cannot handle tables, lists, sections | Phase 4E categories fail |
| Single retrieval strategy | No fallback, no hybrid | Retrieval quality ceiling |
| Single answer engine | All questions forced through extractive QA | Phase 4F EM ceiling ~7% |
| Monolithic Brain | Tight coupling, hard to extend | Adding workflows requires multi-file changes |
| No evidence provenance | Cannot trace answers to source elements | Verification impossible |
| No answerability separation | Extractive QA owns all abstention | Phase 4F: 0% abstention without explicit training |
| No structured document representation | Documents are flat text chunks | Table/list questions fail |
| Monolithic frontend context | State mixing, re-render bloat | Growth barrier |

---

## 14. Tests

### 14.1 Test Coverage

The project has at least 2079 test files detected. Tests cover:
- Document processing
- Embedding generation
- RAG pipeline
- QA model inference
- Brain orchestration
- API endpoints

### 14.2 Test Architecture Weakness

Tests are primarily integration tests. Limited unit tests for individual modules. No contract tests between modules. No property-based tests.

---

## 15. Production Model

- **Location:** `backend/models/documind-qa/`
- **Type:** BERT-based extractive QA
- **Checksum:** `df592aa8d0ee1a235489bd3eead44d4cf0861221339226311960697c1c1512ac`
- **Status:** Frozen, production baseline
- **Note:** Binary may be gitignored and absent from repository. Verified unchanged via research ledger.
