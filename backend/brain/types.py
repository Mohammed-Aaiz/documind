"""
Brain type contracts for DocuMind.

Defines the typed data structures that flow through the Brain workflow.
These are CONTRACTS only — no logic, no side effects, no service imports.

Design rules:
  • No SQLAlchemy, FastAPI, PostgreSQL, pgvector, transformers, or
    sentence-transformers imports.
  • No imports from chat/, embeddings/, documents/, reliability/, or
    verification/ service modules.
  • Reuses the existing Outcome enum from outcomes.py.
  • Brain-owned types are structurally compatible with service types
    but independently defined to avoid circular dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from outcomes import Outcome


# ---------------------------------------------------------------------------
# 0. Brain-owned execution exceptions
# ---------------------------------------------------------------------------

class ModelUnavailableError(RuntimeError):
    """A required model could not be loaded.

    Raised by an adapter (never by the Brain itself) so the executor can
    classify the failure as ``model_unavailable`` instead of a generic
    ``service_failure``.  The evidence gate maps that category to
    ``Outcome.UNAVAILABLE``, which the API layer surfaces as an explicit 503
    rather than a 200 with an empty answer.

    Declared here, in Brain-owned types, so the Brain never imports the
    service layer merely to recognise this condition.
    """


# ---------------------------------------------------------------------------
# 1. Intent
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    """What the user wants to accomplish.

    The Brain classifies every incoming request into exactly one intent.
    """

    DOCUMENT_QUESTION = "DOCUMENT_QUESTION"
    """User asks a factual question about their documents."""

    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    """User requests a summary of a document or set of documents."""

    DOCUMENT_SEARCH = "DOCUMENT_SEARCH"
    """User searches for specific content across documents."""

    MEDIA_VERIFICATION = "MEDIA_VERIFICATION"
    """User asks to analyze media for manipulation or synthetic content."""

    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"
    """Request cannot be handled by any available capability."""


# ---------------------------------------------------------------------------
# 2. Capability
# ---------------------------------------------------------------------------

class Capability(str, Enum):
    """Services the Brain may invoke.

    Each capability maps to a specific service module.  The Brain selects
    capabilities based on intent; services execute independently.
    """

    DOCUMENT_RETRIEVAL = "DOCUMENT_RETRIEVAL"
    """Retrieve relevant document chunks via pgvector similarity search.
    Owner: chat/rag.py → retrieve_chunks()"""

    QA_ANSWER = "QA_ANSWER"
    """Extract an answer from context using the custom QA model.
    Owner: chat/qa_model.py → answer_question()"""

    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    """Build a context string from retrieved chunks.
    Owner: chat/rag.py → build_context()"""

    EMBEDDING_GENERATION = "EMBEDDING_GENERATION"
    """Generate vector embeddings for text.
    Owner: embeddings/model.py → embed_query(), embed_texts()"""

    RELIABILITY_STORAGE = "RELIABILITY_STORAGE"
    """Persist reliability evidence for the Reliability Center.
    Owner: reliability/routes.py → store_query_reliability()"""

    MEDIA_VERIFICATION = "MEDIA_VERIFICATION"
    """Analyze media for manipulation or synthetic content.
    Owner: verification/routes.py (future)"""

    SUMMARY_GENERATION = "SUMMARY_GENERATION"
    """Generate a summary from retrieved document content.
    Owner: not yet implemented."""


# ---------------------------------------------------------------------------
# 3. PlanStep
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanStep:
    """One deterministic execution step in a Brain plan.

    A step names a capability, specifies where its inputs come from
    (keys in the ExecutionContext), and where its output goes.
    """

    capability: Capability
    """Which service capability to invoke."""

    input_keys: tuple[str, ...]
    """Keys in ExecutionContext whose values are passed as inputs."""

    output_key: str
    """Key in ExecutionContext where the result is stored."""


# ---------------------------------------------------------------------------
# 4. Plan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Plan:
    """A deterministic, finite execution plan.

    Plans are constructed from the intent and available capabilities.
    They are inspectable, debuggable, and produce the same sequence of
    steps for the same intent.  No autonomous loops.
    """

    steps: tuple[PlanStep, ...]
    """Ordered execution steps."""

    required_capabilities: tuple[Capability, ...]
    """All capabilities this plan depends on.  If any is unavailable,
    the plan cannot execute and the Brain returns UNAVAILABLE."""


# ---------------------------------------------------------------------------
# 5. QaResult — Brain-owned representation of QA model output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QaResult:
    """Brain's typed view of the QA model output.

    Structurally compatible with the dict returned by
    chat/qa_model.py → answer_question(), but independently defined
    to avoid importing the service layer.
    """

    answer: str
    """The extracted answer span."""

    score: float
    """Confidence score (0.0–1.0)."""

    start: int
    """Start character offset in context."""

    end: int
    """End character offset in context."""


# ---------------------------------------------------------------------------
# 6. SourceRef — Brain-owned representation of a retrieved source
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceRef:
    """Brain's typed view of a retrieved document chunk.

    Structurally compatible with chat/rag.py → SourceChunk, but
    independently defined to avoid importing the service layer.
    """

    chunk_id: str
    """Unique chunk identifier."""

    content: str
    """Text content of the chunk."""

    score: float
    """Similarity score from vector search."""

    document_id: str
    """Parent document identifier."""

    document_name: str
    """Display name of the source document."""

    page: int | None
    """Page number (1-based) if available, else None."""

    # --- Phase 3D structure metadata (None for legacy chunks) ---
    heading_path: tuple[str, ...] | None = None
    """Heading hierarchy of the chunk's section, or None."""

    section: str | None = None
    """Nearest ancestor heading text, or None."""

    element_type: str | None = None
    """Chunk element type (paragraph/heading/table/list/mixed/text), or None."""

    token_count: int | None = None
    """Token count recorded at ingestion, or None."""

    chunker_version: str | None = None
    """Chunker that produced this chunk, or None for legacy chunks."""


# ---------------------------------------------------------------------------
# 7. EvidenceBundle
# ---------------------------------------------------------------------------

@dataclass
class EvidenceBundle:
    """Evidence produced during Brain execution.

    Accumulated by the executor as each step completes.  The evidence
    gate uses this to classify the final outcome.
    """

    sources: list[SourceRef] = field(default_factory=list)
    """Retrieved document chunks that served as evidence."""

    retrieval_scores: list[float] = field(default_factory=list)
    """Raw similarity scores from vector search."""

    qa_result: QaResult | None = None
    """Result from the QA model, if invoked."""

    factual_grounded: bool = False
    """Whether the answer span appears in the retrieved context."""

    grounding_signals: dict[str, Any] = field(default_factory=dict)
    """Additional grounding metadata (extensible).

    Known keys:
      - "answer_found_in_context": bool
      - "omitted_source_ids": list[str]      — retrieved but not given to QA
      - "retrieved_source_count": int        — retrieved before the QA window
      - "context_budget_tokens": int
      - "context_used_tokens": int
      - "context_truncated_source_ids": list[str]
    """


# ---------------------------------------------------------------------------
# 8. TimingInfo
# ---------------------------------------------------------------------------

@dataclass
class TimingInfo:
    """Timing information for a Brain request.

    Updated as each execution step completes.
    """

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """When the Brain began processing this request."""

    retrieval_ms: int = 0
    """Milliseconds spent in document retrieval."""

    qa_ms: int = 0
    """Milliseconds spent in QA model inference."""

    total_ms: int = 0
    """Total milliseconds from start to response assembly."""


# ---------------------------------------------------------------------------
# 9. ErrorRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErrorRecord:
    """An error that occurred during Brain execution.

    Multiple errors may accumulate across steps.  The Brain maps the
    most significant error to the final Outcome.
    """

    category: str
    """Error classification.

    Known categories:
      - "no_evidence": no relevant chunks found
      - "weak_evidence": chunks found but below relevance threshold
      - "no_answer": QA model returned empty answer
      - "ungrounded_answer": answer not found in context
      - "model_unavailable": QA/embedding model not loaded
      - "capability_unavailable": feature not implemented
      - "invalid_request": malformed or empty input
      - "service_failure": error in a downstream service
      - "unexpected_error": uncaught exception
    """

    message: str
    """Human-readable error description.  Must not expose secrets
    or internal stack traces."""

    service: str
    """Which service produced the error (e.g., "qa_model", "retrieval",
    "embedding", "brain")."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """When the error occurred."""


# ---------------------------------------------------------------------------
# 10. ParsedRequest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedRequest:
    """Structured representation of the user's raw input.

    Produced by the Brain's request understanding step.
    """

    cleaned_text: str
    """Normalized input text (stripped, whitespace-collapsed)."""

    intent: Intent
    """Classified intent."""

    intent_confidence: float
    """Classification confidence (0.0–1.0)."""


# ---------------------------------------------------------------------------
# 11. BrainResponse — Brain-owned response representation
# ---------------------------------------------------------------------------

@dataclass
class BrainResponse:
    """The Brain's output, consumed by the API layer.

    Structurally compatible with the existing AskResponse Pydantic model
    in chat/routes.py, but defined independently to avoid importing FastAPI.
    The API layer maps this to the Pydantic response.
    """

    answer: str = ""
    """The answer text (empty if outcome is not SUCCESS/PARTIAL)."""

    confidence: float = 0.0
    """QA model confidence (0.0–1.0)."""

    sources: list[SourceRef] = field(default_factory=list)
    """Evidence sources."""

    insufficient_context: bool = True
    """Whether the system determined it lacks sufficient context."""

    question: str = ""
    """The original user question."""

    outcome: Outcome = Outcome.INSUFFICIENT_EVIDENCE
    """Final outcome classification."""

    reliability: dict[str, Any] = field(default_factory=dict)
    """Reliability evidence data (maps to ReliabilityEvidence schema).

    Known keys:
      - qaConfidence: float
      - retrievalScore: float
      - avgRetrievalScore: float
      - sourceCount: int
      - uniqueDocuments: int
      - factualGrounded: bool
      - insufficientContext: bool
    """


# ---------------------------------------------------------------------------
# 12. ExecutionContext
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Complete state passed through the Brain workflow.

    Created by the API layer for each request.  Accumulated by the
    Brain executor as steps complete.  The evidence gate and response
    assembler read from this context.
    """

    # --- Identity ---
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier for tracing."""

    user_id: str = ""
    """Authenticated user ID (from JWT)."""

    session_id: str | None = None
    """Chat session ID, if applicable."""

    # --- Input ---
    raw_question: str = ""
    """Original user input."""

    top_k: int = 5
    """Number of chunks to retrieve (from API request)."""

    parsed_request: ParsedRequest | None = None
    """Structured representation after parsing."""

    # --- Plan ---
    plan: Plan | None = None
    """Deterministic execution plan."""

    # --- Evidence ---
    evidence: EvidenceBundle = field(default_factory=EvidenceBundle)
    """Accumulated evidence from execution steps."""

    # --- Outcome ---
    outcome: Outcome = Outcome.INSUFFICIENT_EVIDENCE
    """Final outcome classification."""

    # --- Metadata ---
    pipeline_version: str = "rag-v1"
    """Pipeline version for traceability."""

    model_metadata: dict[str, str] = field(default_factory=dict)
    """Model information.

    Known keys:
      - "qa_model": str (model path)
      - "embedding_model": str (model name)
    """

    # --- Timing ---
    timing: TimingInfo = field(default_factory=TimingInfo)
    """Request timing information."""

    # --- Errors ---
    errors: list[ErrorRecord] = field(default_factory=list)
    """Errors accumulated during execution."""

    # --- Response ---
    response: BrainResponse | None = None
    """Final assembled response (set by response assembler)."""
