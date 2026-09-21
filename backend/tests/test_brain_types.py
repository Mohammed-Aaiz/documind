"""Tests for Brain type contracts.

Verifies that every type, enum, and dataclass in brain/types.py:
  • Exists with expected values
  • Can be constructed
  • Has correct field types
  • Integrates with the existing Outcome enum
  • Contains no service or infrastructure imports

These tests verify CONTRACTS, not behavior.
"""

import pytest
from outcomes import Outcome


# ---------------------------------------------------------------------------
# Import the Brain types — this also verifies no import-time errors
# ---------------------------------------------------------------------------

from brain.types import (
    Intent,
    Capability,
    PlanStep,
    Plan,
    QaResult,
    SourceRef,
    EvidenceBundle,
    TimingInfo,
    ErrorRecord,
    ParsedRequest,
    BrainResponse,
    ExecutionContext,
)


# ---------------------------------------------------------------------------
# 1. Intent enum
# ---------------------------------------------------------------------------

class TestIntent:
    def test_all_intents_exist(self):
        assert Intent.DOCUMENT_QUESTION.value == "DOCUMENT_QUESTION"
        assert Intent.DOCUMENT_SUMMARY.value == "DOCUMENT_SUMMARY"
        assert Intent.DOCUMENT_SEARCH.value == "DOCUMENT_SEARCH"
        assert Intent.MEDIA_VERIFICATION.value == "MEDIA_VERIFICATION"
        assert Intent.UNSUPPORTED_REQUEST.value == "UNSUPPORTED_REQUEST"

    def test_intent_is_string(self):
        assert isinstance(Intent.DOCUMENT_QUESTION, str)

    def test_intent_count(self):
        assert len(Intent) == 5


# ---------------------------------------------------------------------------
# 2. Capability enum
# ---------------------------------------------------------------------------

class TestCapability:
    def test_all_capabilities_exist(self):
        assert Capability.DOCUMENT_RETRIEVAL.value == "DOCUMENT_RETRIEVAL"
        assert Capability.QA_ANSWER.value == "QA_ANSWER"
        assert Capability.CONTEXT_BUILDING.value == "CONTEXT_BUILDING"
        assert Capability.EMBEDDING_GENERATION.value == "EMBEDDING_GENERATION"
        assert Capability.RELIABILITY_STORAGE.value == "RELIABILITY_STORAGE"
        assert Capability.MEDIA_VERIFICATION.value == "MEDIA_VERIFICATION"
        assert Capability.SUMMARY_GENERATION.value == "SUMMARY_GENERATION"

    def test_capability_is_string(self):
        assert isinstance(Capability.DOCUMENT_RETRIEVAL, str)

    def test_capability_count(self):
        assert len(Capability) == 7


# ---------------------------------------------------------------------------
# 3. PlanStep construction
# ---------------------------------------------------------------------------

class TestPlanStep:
    def test_construction(self):
        step = PlanStep(
            capability=Capability.DOCUMENT_RETRIEVAL,
            input_keys=("user_id", "cleaned_text"),
            output_key="retrieval_result",
        )
        assert step.capability == Capability.DOCUMENT_RETRIEVAL
        assert step.input_keys == ("user_id", "cleaned_text")
        assert step.output_key == "retrieval_result"

    def test_is_frozen(self):
        step = PlanStep(
            capability=Capability.QA_ANSWER,
            input_keys=("question",),
            output_key="qa_result",
        )
        with pytest.raises(AttributeError):
            step.capability = Capability.DOCUMENT_RETRIEVAL  # type: ignore[misc]

    def test_empty_input_keys(self):
        step = PlanStep(
            capability=Capability.CONTEXT_BUILDING,
            input_keys=(),
            output_key="context",
        )
        assert step.input_keys == ()


# ---------------------------------------------------------------------------
# 4. Plan construction
# ---------------------------------------------------------------------------

class TestPlan:
    def test_construction(self):
        step1 = PlanStep(
            capability=Capability.DOCUMENT_RETRIEVAL,
            input_keys=("user_id", "cleaned_text"),
            output_key="sources",
        )
        step2 = PlanStep(
            capability=Capability.QA_ANSWER,
            input_keys=("cleaned_text", "context"),
            output_key="qa_result",
        )
        plan = Plan(
            steps=(step1, step2),
            required_capabilities=(Capability.DOCUMENT_RETRIEVAL, Capability.QA_ANSWER),
        )
        assert len(plan.steps) == 2
        assert len(plan.required_capabilities) == 2

    def test_is_frozen(self):
        plan = Plan(steps=(), required_capabilities=())
        with pytest.raises(AttributeError):
            plan.steps = ()  # type: ignore[misc]

    def test_empty_plan(self):
        plan = Plan(steps=(), required_capabilities=())
        assert len(plan.steps) == 0


# ---------------------------------------------------------------------------
# 5. QaResult construction
# ---------------------------------------------------------------------------

class TestQaResult:
    def test_construction(self):
        r = QaResult(answer="1859", score=0.82, start=10, end=14)
        assert r.answer == "1859"
        assert r.score == 0.82
        assert r.start == 10
        assert r.end == 14

    def test_is_frozen(self):
        r = QaResult(answer="test", score=0.5, start=0, end=4)
        with pytest.raises(AttributeError):
            r.answer = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6. SourceRef construction
# ---------------------------------------------------------------------------

class TestSourceRef:
    def test_construction(self):
        s = SourceRef(
            chunk_id="abc-123",
            content="Test content about evolution",
            score=0.75,
            document_id="doc-456",
            document_name="darwin.pdf",
            page=3,
        )
        assert s.chunk_id == "abc-123"
        assert s.page == 3

    def test_none_page(self):
        s = SourceRef(
            chunk_id="abc",
            content="text",
            score=0.5,
            document_id="doc",
            document_name="file.txt",
            page=None,
        )
        assert s.page is None

    def test_is_frozen(self):
        s = SourceRef(
            chunk_id="x", content="y", score=0.1,
            document_id="d", document_name="n", page=None,
        )
        with pytest.raises(AttributeError):
            s.score = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 7. EvidenceBundle construction
# ---------------------------------------------------------------------------

class TestEvidenceBundle:
    def test_default_construction(self):
        eb = EvidenceBundle()
        assert eb.sources == []
        assert eb.retrieval_scores == []
        assert eb.qa_result is None
        assert eb.factual_grounded is False
        assert eb.grounding_signals == {}

    def test_full_construction(self):
        src = SourceRef(
            chunk_id="c1", content="text", score=0.7,
            document_id="d1", document_name="doc.pdf", page=1,
        )
        qa = QaResult(answer="answer", score=0.8, start=0, end=6)
        eb = EvidenceBundle(
            sources=[src],
            retrieval_scores=[0.7],
            qa_result=qa,
            factual_grounded=True,
            grounding_signals={"answer_found_in_context": True},
        )
        assert len(eb.sources) == 1
        assert eb.qa_result is not None
        assert eb.factual_grounded is True

    def test_is_mutable(self):
        """EvidenceBundle must be mutable — evidence accumulates over steps."""
        eb = EvidenceBundle()
        src = SourceRef(
            chunk_id="c1", content="text", score=0.5,
            document_id="d1", document_name="doc.pdf", page=None,
        )
        eb.sources.append(src)
        assert len(eb.sources) == 1


# ---------------------------------------------------------------------------
# 8. TimingInfo construction
# ---------------------------------------------------------------------------

class TestTimingInfo:
    def test_default_construction(self):
        t = TimingInfo()
        assert t.started_at is not None
        assert t.retrieval_ms == 0
        assert t.qa_ms == 0
        assert t.total_ms == 0

    def test_is_mutable(self):
        t = TimingInfo()
        t.retrieval_ms = 150
        t.qa_ms = 300
        t.total_ms = 450
        assert t.total_ms == 450


# ---------------------------------------------------------------------------
# 9. ErrorRecord construction
# ---------------------------------------------------------------------------

class TestErrorRecord:
    def test_construction(self):
        e = ErrorRecord(
            category="service_failure",
            message="Database connection lost",
            service="retrieval",
        )
        assert e.category == "service_failure"
        assert e.service == "retrieval"
        assert e.timestamp is not None

    def test_is_frozen(self):
        e = ErrorRecord(category="test", message="msg", service="svc")
        with pytest.raises(AttributeError):
            e.message = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 10. ParsedRequest construction
# ---------------------------------------------------------------------------

class TestParsedRequest:
    def test_construction(self):
        pr = ParsedRequest(
            cleaned_text="When did Darwin publish?",
            intent=Intent.DOCUMENT_QUESTION,
            intent_confidence=0.92,
        )
        assert pr.intent == Intent.DOCUMENT_QUESTION
        assert pr.intent_confidence == 0.92

    def test_is_frozen(self):
        pr = ParsedRequest(
            cleaned_text="x", intent=Intent.DOCUMENT_QUESTION, intent_confidence=0.5,
        )
        with pytest.raises(AttributeError):
            pr.intent = Intent.DOCUMENT_SUMMARY  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 11. BrainResponse construction
# ---------------------------------------------------------------------------

class TestBrainResponse:
    def test_default_construction(self):
        br = BrainResponse()
        assert br.answer == ""
        assert br.confidence == 0.0
        assert br.sources == []
        assert br.insufficient_context is True
        assert br.outcome == Outcome.INSUFFICIENT_EVIDENCE
        assert br.reliability == {}

    def test_full_construction(self):
        src = SourceRef(
            chunk_id="c1", content="text", score=0.7,
            document_id="d1", document_name="doc.pdf", page=1,
        )
        br = BrainResponse(
            answer="1859",
            confidence=0.82,
            sources=[src],
            insufficient_context=False,
            question="When?",
            outcome=Outcome.SUCCESS,
            reliability={"qaConfidence": 0.82, "sourceCount": 1},
        )
        assert br.outcome == Outcome.SUCCESS
        assert len(br.sources) == 1

    def test_outcome_integration(self):
        """BrainResponse.outcome must be the existing Outcome enum."""
        for o in Outcome:
            br = BrainResponse(outcome=o)
            assert br.outcome == o
            assert isinstance(br.outcome.value, str)


# ---------------------------------------------------------------------------
# 12. ExecutionContext construction
# ---------------------------------------------------------------------------

class TestExecutionContext:
    def test_default_construction(self):
        ctx = ExecutionContext()
        assert ctx.request_id  # auto-generated UUID
        assert ctx.user_id == ""
        assert ctx.session_id is None
        assert ctx.raw_question == ""
        assert ctx.parsed_request is None
        assert ctx.plan is None
        assert ctx.evidence is not None
        assert ctx.outcome == Outcome.INSUFFICIENT_EVIDENCE
        assert ctx.pipeline_version == "rag-v1"
        assert ctx.model_metadata == {}
        assert ctx.timing is not None
        assert ctx.errors == []
        assert ctx.response is None

    def test_full_construction(self):
        pr = ParsedRequest(
            cleaned_text="What is evolution?",
            intent=Intent.DOCUMENT_QUESTION,
            intent_confidence=0.9,
        )
        step = PlanStep(
            capability=Capability.DOCUMENT_RETRIEVAL,
            input_keys=("user_id", "cleaned_text"),
            output_key="sources",
        )
        plan = Plan(steps=(step,), required_capabilities=(Capability.DOCUMENT_RETRIEVAL,))
        err = ErrorRecord(category="test", message="msg", service="svc")
        ctx = ExecutionContext(
            request_id="req-123",
            user_id="user-456",
            session_id="sess-789",
            raw_question="What is evolution?",
            parsed_request=pr,
            plan=plan,
            outcome=Outcome.PARTIAL,
            pipeline_version="rag-v2",
            model_metadata={"qa_model": "./models/documind-qa"},
            errors=[err],
        )
        assert ctx.request_id == "req-123"
        assert ctx.user_id == "user-456"
        assert ctx.plan is not None
        assert len(ctx.plan.steps) == 1
        assert ctx.outcome == Outcome.PARTIAL
        assert len(ctx.errors) == 1

    def test_is_mutable(self):
        """ExecutionContext must be mutable — it accumulates state."""
        ctx = ExecutionContext()
        ctx.user_id = "user-1"
        ctx.outcome = Outcome.SUCCESS
        ctx.errors.append(
            ErrorRecord(category="test", message="msg", service="svc")
        )
        assert ctx.user_id == "user-1"
        assert ctx.outcome == Outcome.SUCCESS
        assert len(ctx.errors) == 1


# ---------------------------------------------------------------------------
# 13. No prohibited imports in brain/types.py
# ---------------------------------------------------------------------------

class TestNoProhibitedImports:
    """Verify that brain/types.py does not import infrastructure or services."""

    PROHIBITED = [
        "sqlalchemy",
        "fastapi",
        "asyncpg",
        "pgvector",
        "torch",
        "transformers",
        "sentence_transformers",
        "fitz",
        "docx",
        "chat.rag",
        "chat.qa_model",
        "embeddings.model",
        "documents.processing",
        "reliability.routes",
        "verification.routes",
        "storage.database",
        "auth.dependencies",
    ]

    def test_no_prohibited_imports(self):
        import pathlib
        types_path = pathlib.Path(__file__).resolve().parent.parent / "brain" / "types.py"
        content = types_path.read_text(encoding="utf-8")

        # Only check import lines (not comments or docstrings)
        import_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("from ") or line.strip().startswith("import ")
        ]

        violations = []
        for line in import_lines:
            for prohibited in self.PROHIBITED:
                if prohibited in line:
                    violations.append(f"{prohibited} in: {line}")

        assert not violations, (
            f"brain/types.py contains prohibited imports: {violations}. "
            f"Brain types must be independent of infrastructure and services."
        )
