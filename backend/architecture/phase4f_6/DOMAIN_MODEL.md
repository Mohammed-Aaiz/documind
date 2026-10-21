# DocuMind — Domain Model

## Purpose

Define the core domain concepts for DocuMind. These are conceptual entities, not database schemas. Each concept has a clear purpose, owner, relationships, mutability classification, and provenance requirements.

---

## 1. Document Domain

### 1.1 Document

**Purpose:** Represents an uploaded file and its metadata.

**Owner:** Document ingestion service

**Relationships:**
- Has many `DocumentVersion`s (one per upload/processing)
- Belongs to a `Workspace`
- Has many `DocumentChunk`s (via latest version)

**Mutable vs Immutable:**
- `id`: immutable (assigned at creation)
- `filename`: mutable (can be renamed)
- `content_type`: immutable
- `file_size`: immutable
- `created_at`: immutable
- `workspace_id`: mutable (can be moved)

**Provenance requirements:**
- Record upload timestamp
- Record original filename
- Record content type
- Record file size
- Record checksum of original file

---

### 1.2 DocumentVersion

**Purpose:** Represents a specific processing version of a document. When a document is re-processed (e.g., with improved structure extraction), a new version is created. Previous versions are preserved.

**Owner:** Document processing service

**Relationships:**
- Belongs to a `Document`
- Has many `DocumentElement`s
- Has many `Chunk`s

**Mutable vs Immutable:**
- `id`: immutable
- `document_id`: immutable
- `created_at`: immutable
- `elements`: immutable (once created, never modified)
- `chunks`: immutable (once created, never modified)
- `metadata`: immutable

**Provenance requirements:**
- Record processing pipeline version
- Record processing parameters
- Record element extraction confidence scores
- Record chunk generation parameters

---

### 1.3 DocumentElement

**Purpose:** Represents a structured element within a document. This is the canonical representation of document structure.

**Owner:** Document structure extraction service

**Relationships:**
- Belongs to a `DocumentVersion`
- Has parent `DocumentElement` (for nesting)
- Has child `DocumentElement`s
- Has many `Chunk`s that reference it

**Mutable vs Immutable:**
- All fields immutable once created

**Subtypes:**

| Subtype | Description | Additional Fields |
|---------|-------------|-------------------|
| `Section` | A section with heading and content | heading, level, content |
| `Table` | A structured table | rows, columns, caption |
| `TableRow` | A table row | cells, position, is_header |
| `TableCell` | A table cell | content, row_span, col_span, is_header |
| `List` | An ordered or unordered list | items, ordered |
| `ListItem` | A list item | content, position, children |
| `TextBlock` | A plain text block | content |
| `Page` | A page boundary | page_number |

**Provenance requirements:**
- Record extraction method (parser, model)
- Record confidence score
- Record position in original document
- Record bounding box (if available)

---

### 1.4 Chunk

**Purpose:** A retrieval unit derived from document structure. Chunks are what get embedded and searched. They reference source elements for provenance.

**Owner:** Chunking service

**Relationships:**
- Belongs to a `DocumentVersion`
- References many `DocumentElement`s
- Referenced by many `RetrievalCandidate`s

**Mutable vs Immutable:**
- All fields immutable once created

**Mutable fields:**
- `embedding`: mutable (can be recomputed with different model)

**Provenance requirements:**
- Record chunking strategy used
- Record target chunk size
- Record overlap parameters
- Record which elements were combined
- Record character offsets in original text

---

## 2. Retrieval Domain

### 2.1 Query

**Purpose:** Represents a user's information need, potentially transformed for retrieval.

**Owner:** Query transformation service

**Relationships:**
- Created from user `Question`
- Produces many `RetrievalCandidate`s

**Mutable vs Immutable:**
- `original_text`: immutable
- `transformed_text`: immutable (once transformed)
- `question_type`: immutable (once classified)

**Provenance requirements:**
- Record original query text
- Record transformation applied
- Record question type classification
- Record classification confidence

---

### 2.2 RetrievalCandidate

**Purpose:** A chunk retrieved in response to a query, with retrieval metadata.

**Owner:** Retrieval service

**Relationships:**
- References a `Chunk`
- References a `Query`
- May become `Evidence` after verification

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record retrieval strategy (dense, lexical, hybrid)
- Record retrieval score
- Record rank
- Record reranking score (if applicable)
- Record which retrieval pipeline produced it

---

### 2.3 RetrievalRun

**Purpose:** Records a complete retrieval operation for auditing and debugging.

**Owner:** Retrieval subsystem

**Relationships:**
- Produced by a `Query`
- Contains many `RetrievalCandidate`s

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record timestamp
- Record retrieval strategy configuration
- Record top-K parameter
- Record fusion parameters (if hybrid)
- Record reranker used (if any)
- Record total candidates retrieved
- Record total candidates returned

---

## 3. Evidence Domain

### 3.1 Evidence

**Purpose:** A verified piece of information that supports an answer. Evidence is a RetrievalCandidate that has passed initial verification.

**Owner:** Evidence verification service

**Relationships:**
- Derived from `RetrievalCandidate`
- References `DocumentElement` (via chunk)
- Supports `AnswerCandidate`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Full retrieval provenance (inherited from RetrievalCandidate)
- Full document provenance (inherited from Chunk → Element → Document)
- Verification status
- Verification timestamp

---

### 3.2 Provenance

**Purpose:** The complete traceability chain from answer to original document.

**Owner:** Provenance tracking service

**Relationships:**
- Attached to every `Evidence`
- Attached to every `AnswerCandidate`

**Provenance chain:**
```
AnswerCandidate
  ↓
Evidence (retrieval info)
  ↓
Chunk (character offsets)
  ↓
DocumentElement (position)
  ↓
DocumentVersion (processing info)
  ↓
Document (upload info)
```

**Mutable vs Immutable:**
- All fields immutable once created

---

## 4. Answer Domain

### 4.1 Question

**Purpose:** Represents a user's question, classified and ready for processing.

**Owner:** Question classification service

**Relationships:**
- Created from user input
- Produces `Query` for retrieval
- Produces `QuestionType` classification
- Produces `AnswerCandidate`

**Mutable vs Immutable:**
- `text`: immutable
- `question_type`: immutable (once classified)
- `workspace_id`: immutable

**Provenance requirements:**
- Record original question text
- Record classification result
- Record classification confidence
- Record timestamp

---

### 4.2 QuestionType

**Purpose:** The classified type of a question, determining which workflow to use.

**Owner:** Question classifier

**Relationships:**
- Attached to `Question`
- Determines `AnswerStrategy`

**Mutable vs Immutable:**
- Immutable once classified

**Values:** See Question Workflow Matrix

---

### 4.3 AnswerCandidate

**Purpose:** A candidate answer produced by an answer engine, before verification.

**Owner:** Answer engine

**Relationships:**
- Produced by `Question`
- Supported by many `Evidence`
- Passes through `VerificationPipeline`
- Becomes `VerifiedAnswer` or `Abstention`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record which answer engine produced it
- Record answer engine version
- Record evidence used
- Record confidence score
- Record answer span (if extractive)
- Record answer text (if generative)

---

### 4.4 VerifiedAnswer

**Purpose:** An answer that has passed verification. This is what reaches the user.

**Owner:** Verification pipeline

**Relationships:**
- Derived from `AnswerCandidate`
- Contains `Evidence` with full provenance
- Contains `Citation`s

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Full answer provenance (inherited from AnswerCandidate)
- Verification results
- Grounding check results
- Citation check results
- Final verification status

---

### 4.5 Abstention

**Purpose:** A decision to not provide an answer, with explanation.

**Owner:** Answerability service or verification pipeline

**Relationships:**
- Produced by `Question`
- Has `AbstentionReason`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record abstention reason
- Record which module decided to abstain
- Record evidence considered (if any)
- Record timestamp

---

### 4.6 Citation

**Purpose:** A reference from an answer to a specific point in a source document.

**Owner:** Citation extraction service

**Relationships:**
- Attached to `VerifiedAnswer`
- References `DocumentElement`
- References `Chunk`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record cited text
- Record source element
- Record source chunk
- Record character offsets
- Record page number (if applicable)

---

## 5. Answerability Domain

### 5.1 SufficiencyResult

**Purpose:** The result of evidence sufficiency analysis.

**Owner:** Evidence sufficiency service

**Relationships:**
- Produced by `Evidence` analysis
- Determines `Answerability` decision

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record sufficiency criteria checked
- Record which criteria passed/failed
- Record confidence score
- Record timestamp

---

### 5.2 Answerability

**Purpose:** The decision of whether the system can answer a question.

**Owner:** Answerability service

**Relationships:**
- Determined by `SufficiencyResult`
- Determines whether `AnswerCandidate` is produced or `Abstention` is returned

**Mutable vs Immutable:**
- All fields immutable once created

**Values:**
- ANSWERABLE: Evidence is sufficient, proceed to answer
- UNANSWERABLE: Evidence is insufficient, abstain

---

## 6. Verification Domain

### 6.1 VerificationRun

**Purpose:** Records a complete verification operation.

**Owner:** Verification pipeline

**Relationships:**
- Processes `AnswerCandidate`
- Produces `VerifiedAnswer` or `Abstention`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record verification pipeline version
- Record each check performed
- Record each check result
- Record final verification status
- Record timestamp

---

### 6.2 VerificationStatus

**Purpose:** The result of verification.

**Owner:** Verification pipeline

**Mutable vs Immutable:**
- Immutable once determined

**Values:**
- VERIFIED: Answer is grounded, evidence is sufficient, citations are accurate
- PARTIAL: Answer is partially grounded, some citations may be inaccurate
- ABSTAIN: Answer cannot be verified

---

## 7. Reliability Domain

### 7.1 ReliabilityRecord

**Purpose:** Records the reliability of a system operation for monitoring and improvement.

**Owner:** Reliability tracking service

**Relationships:**
- Attached to `VerifiedAnswer` or `Abstention`
- Contains `Outcome`

**Mutable vs Immutable:**
- All fields immutable once created

**Provenance requirements:**
- Record operation type
- Record outcome
- Record latency
- Record resource usage
- Record error information (if any)
- Record timestamp

---

### 7.2 Outcome

**Purpose:** Classify the result of an application operation.

**Owner:** Reliability service

**Mutable vs Immutable:**
- Immutable once determined

**Values:**
- SUCCESS: Full results returned
- PARTIAL: Partial results returned
- INSUFFICIENT_EVIDENCE: Not enough information
- UNAVAILABLE: Capability not available
- FAILED: Unexpected error

**Current implementation:** Defined in `backend/outcomes.py`. This is the only domain concept that currently exists as code.

---

## 8. Model Domain

### 8.1 ModelEntry

**Purpose:** A registered model in the model registry.

**Owner:** Model registry

**Relationships:**
- Used by answer engines
- Used by retrieval services
- Used by verification services

**Mutable vs Immutable:**
- `name`: immutable
- `version`: immutable
- `path`: immutable
- `checksum`: immutable
- `availability`: mutable (can change)
- `evaluation_status`: mutable (can change)

**Provenance requirements:**
- Record model source
- Record training data
- Record evaluation results
- Record checksum
- Record resource requirements

---

## 9. Relationship Diagram

```
Document
  └── DocumentVersion
        ├── DocumentElement (Section, Table, List, TextBlock, Page)
        │     ├── TableRow → TableCell
        │     └── ListItem → ListItem (nested)
        └── Chunk → DocumentElement (references)
              └── RetrievalCandidate → Query
                    └── Evidence → AnswerCandidate
                          └── VerifiedAnswer → Citation → DocumentElement
                          └── Abstention → AbstentionReason
              
Question
  ├── QuestionType
  ├── Query
  └── AnswerCandidate / Abstention

ModelEntry
  ├── used by AnswerEngine
  ├── used by RetrievalService
  └── used by VerificationService

ReliabilityRecord → Outcome
```

---

## 10. Immutability Summary

| Concept | Mutable Fields | Immutable Fields |
|---------|---------------|-----------------|
| Document | filename, workspace_id | id, content_type, file_size, created_at |
| DocumentVersion | (none) | all |
| DocumentElement | (none) | all |
| Chunk | embedding | all other fields |
| Query | (none) | all |
| RetrievalCandidate | (none) | all |
| Evidence | (none) | all |
| Question | (none) | all |
| AnswerCandidate | (none) | all |
| VerifiedAnswer | (none) | all |
| Abstention | (none) | all |
| ModelEntry | availability, evaluation_status | name, version, path, checksum |
| ReliabilityRecord | (none) | all |

---

## 11. Provenance Summary

| Concept | Minimum Provenance Required |
|---------|---------------------------|
| Document | upload timestamp, original filename, checksum |
| DocumentVersion | processing pipeline version, parameters |
| DocumentElement | extraction method, confidence, position |
| Chunk | chunking strategy, parameters, element references |
| RetrievalCandidate | strategy, score, rank, query |
| Evidence | full retrieval + document provenance |
| AnswerCandidate | answer engine, version, evidence, confidence |
| VerifiedAnswer | full answer + verification provenance |
| Abstention | reason, module, evidence considered |
| Citation | cited text, source element, offsets |
