"""Tests for the Brain orchestration skeleton.

Tests the classifier, planner, executor, evidence gate, response
assembler, and Brain.process() integration using test doubles.

No existing application code is mocked — test doubles are used only
to isolate Brain orchestration from service implementations.
"""

import pytest
import pytest_asyncio

from brain.classifier import classify
from brain.executor import CapabilityRegistry, Executor
from brain.gate import evaluate
from brain.planner import build_plan
from brain.response import assemble
from brain.types import (
    BrainResponse,
    Capability,
    ExecutionContext,
    ErrorRecord,
    Intent,
    Plan,
    PlanStep,
    ParsedRequest,
    QaResult,
    SourceRef,
)
from brain import Brain
from outcomes import Outcome


# =========================================================================
# CLASSIFIER TESTS
# =========================================================================

class TestClassifier:
    def test_document_question_with_question_word(self):
        pr = classify("When was Darwin born?")
        assert pr.intent == Intent.DOCUMENT_QUESTION
        assert pr.intent_confidence >= 0.75

    def test_document_question_with_phrase(self):
        pr = classify("According to the document, what is natural selection?")
        assert pr.intent == Intent.DOCUMENT_QUESTION

    def test_document_question_with_question_mark(self):
        pr = classify("evolution of species")
        # No question mark, no question word → low confidence DOCUMENT_QUESTION
        assert pr.intent == Intent.DOCUMENT_QUESTION
        assert pr.intent_confidence <= 0.6

    def test_document_summary(self):
        pr = classify("Summarize this document")
        assert pr.intent == Intent.DOCUMENT_SUMMARY
        assert pr.intent_confidence >= 0.8

    def test_document_summary_tldr(self):
        pr = classify("Give me a TL;DR of the report")
        assert pr.intent == Intent.DOCUMENT_SUMMARY

    def test_document_search(self):
        pr = classify("Find mentions of evolution in the files")
        assert pr.intent == Intent.DOCUMENT_SEARCH
        assert pr.intent_confidence >= 0.7

    def test_document_search_find(self):
        pr = classify("search for natural selection")
        assert pr.intent == Intent.DOCUMENT_SEARCH

    def test_media_verification(self):
        pr = classify("Check whether this image is fake")
        assert pr.intent == Intent.MEDIA_VERIFICATION
        assert pr.intent_confidence >= 0.8

    def test_media_verification_deepfake(self):
        pr = classify("Is this a deepfake video?")
        assert pr.intent == Intent.MEDIA_VERIFICATION

    def test_media_verification_authenticity(self):
        pr = classify("Verify the authenticity of this photo")
        assert pr.intent == Intent.MEDIA_VERIFICATION

    def test_unsupported_empty(self):
        pr = classify("")
        assert pr.intent == Intent.UNSUPPORTED_REQUEST
        assert pr.intent_confidence == 1.0

    def test_cleaned_text(self):
        pr = classify("  When   was   Darwin   born?  ")
        assert pr.cleaned_text == "when was darwin born?"

    def test_returns_parsed_request(self):
        pr = classify("test")
        assert isinstance(pr, ParsedRequest)
        assert isinstance(pr.intent, Intent)


# =========================================================================
# PLANNER TESTS
# =========================================================================

class TestPlanner:
    def test_document_question_plan(self):
        pr = classify("What is natural selection?")
        plan = build_plan(pr)
        assert len(plan.steps) == 3
        caps = [s.capability for s in plan.steps]
        assert Capability.DOCUMENT_RETRIEVAL in caps
        assert Capability.CONTEXT_BUILDING in caps
        assert Capability.QA_ANSWER in caps

    def test_document_search_plan(self):
        pr = classify("Find mentions of evolution")
        plan = build_plan(pr)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability == Capability.DOCUMENT_RETRIEVAL

    def test_document_summary_plan(self):
        pr = classify("Summarize this document")
        plan = build_plan(pr)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability == Capability.SUMMARY_GENERATION

    def test_media_verification_plan(self):
        pr = classify("Check this image for deepfake")
        plan = build_plan(pr)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability == Capability.MEDIA_VERIFICATION

    def test_unsupported_plan_empty(self):
        pr = classify("")
        plan = build_plan(pr)
        assert len(plan.steps) == 0
        assert len(plan.required_capabilities) == 0

    def test_plan_is_frozen(self):
        pr = classify("What is AI?")
        plan = build_plan(pr)
        assert isinstance(plan, Plan)

    def test_plan_is_deterministic(self):
        """Same intent always produces the same plan."""
        pr1 = classify("What is evolution?")
        pr2 = classify("Who was Darwin?")
        plan1 = build_plan(pr1)
        plan2 = build_plan(pr2)
        assert len(plan1.steps) == len(plan2.steps)
        for s1, s2 in zip(plan1.steps, plan2.steps):
            assert s1.capability == s2.capability
            assert s1.input_keys == s2.input_keys
            assert s1.output_key == s2.output_key


# =========================================================================
# EXECUTOR TESTS
# =========================================================================

class TestExecutor:
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Steps execute in order, outputs stored in context."""
        registry = CapabilityRegistry()

        results = []

        async def step1_adapter(user_id: str = "", cleaned_text: str = ""):
            results.append("step1")
            return [SourceRef(
                chunk_id="c1", content="text", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )]

        async def step2_adapter(retrieval_sources=None):
            results.append("step2")
            return "built context"

        registry.register(Capability.DOCUMENT_RETRIEVAL, step1_adapter)
        registry.register(Capability.CONTEXT_BUILDING, step2_adapter)

        executor = Executor(registry)
        ctx = ExecutionContext(user_id="u1", raw_question="test")
        plan = Plan(
            steps=(
                PlanStep(
                    capability=Capability.DOCUMENT_RETRIEVAL,
                    input_keys=("user_id", "cleaned_text"),
                    output_key="retrieval_sources",
                ),
                PlanStep(
                    capability=Capability.CONTEXT_BUILDING,
                    input_keys=("retrieval_sources",),
                    output_key="context",
                ),
            ),
            required_capabilities=(
                Capability.DOCUMENT_RETRIEVAL,
                Capability.CONTEXT_BUILDING,
            ),
        )

        ctx = await executor.run(ctx, plan)
        assert results == ["step1", "step2"]
        assert getattr(ctx, "retrieval_sources", None) is not None
        assert getattr(ctx, "context", None) == "built context"

    @pytest.mark.asyncio
    async def test_unavailable_capability_records_error(self):
        """Unregistered capability produces error, no fake output."""
        registry = CapabilityRegistry()
        executor = Executor(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="test")
        plan = Plan(
            steps=(
                PlanStep(
                    capability=Capability.DOCUMENT_RETRIEVAL,
                    input_keys=("user_id",),
                    output_key="result",
                ),
            ),
            required_capabilities=(Capability.DOCUMENT_RETRIEVAL,),
        )

        ctx = await executor.run(ctx, plan)
        assert len(ctx.errors) == 1
        assert ctx.errors[0].category == "capability_unavailable"
        assert getattr(ctx, "result", None) is None  # no fake output

    @pytest.mark.asyncio
    async def test_service_failure_records_error(self):
        """Exception in adapter produces error, no crash."""
        registry = CapabilityRegistry()

        async def failing_adapter(**kwargs):
            raise RuntimeError("Database connection lost")

        registry.register(Capability.DOCUMENT_RETRIEVAL, failing_adapter)

        executor = Executor(registry)
        ctx = ExecutionContext(user_id="u1", raw_question="test")
        plan = Plan(
            steps=(
                PlanStep(
                    capability=Capability.DOCUMENT_RETRIEVAL,
                    input_keys=("user_id",),
                    output_key="result",
                ),
            ),
            required_capabilities=(Capability.DOCUMENT_RETRIEVAL,),
        )

        ctx = await executor.run(ctx, plan)
        assert len(ctx.errors) == 1
        assert ctx.errors[0].category == "service_failure"
        assert "RuntimeError" in ctx.errors[0].message
        assert getattr(ctx, "result", None) is None  # no fake output

    @pytest.mark.asyncio
    async def test_no_fake_outputs(self):
        """When capability fails, context has no fabricated data."""
        registry = CapabilityRegistry()
        executor = Executor(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="test")
        plan = Plan(
            steps=(
                PlanStep(
                    capability=Capability.QA_ANSWER,
                    input_keys=("cleaned_text",),
                    output_key="qa_result",
                ),
            ),
            required_capabilities=(Capability.QA_ANSWER,),
        )

        ctx = await executor.run(ctx, plan)
        assert getattr(ctx, "qa_result", None) is None  # no fabricated result


# =========================================================================
# EVIDENCE GATE TESTS
# =========================================================================

class TestEvidenceGate:
    def test_no_evidence(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = []
        assert evaluate(ctx) == Outcome.INSUFFICIENT_EVIDENCE

    def test_retrieval_only_success(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="text", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.qa_result = None
        assert evaluate(ctx) == Outcome.SUCCESS

    def test_grounded_answer_strong_signals(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="1859", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.retrieval_scores = [0.7]
        ctx.evidence.qa_result = QaResult(answer="1859", score=0.82, start=0, end=4)
        ctx.evidence.factual_grounded = True
        assert evaluate(ctx) == Outcome.SUCCESS

    def test_grounded_answer_weak_signals(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="text", score=0.4,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.retrieval_scores = [0.4]
        ctx.evidence.qa_result = QaResult(answer="something", score=0.15, start=0, end=9)
        ctx.evidence.factual_grounded = True
        assert evaluate(ctx) == Outcome.PARTIAL

    def test_ungrounded_answer(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="text", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.retrieval_scores = [0.7]
        ctx.evidence.qa_result = QaResult(answer="guess", score=0.5, start=0, end=5)
        ctx.evidence.factual_grounded = False
        assert evaluate(ctx) == Outcome.PARTIAL

    def test_empty_answer(self):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="text", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.qa_result = QaResult(answer="", score=0.0, start=0, end=0)
        assert evaluate(ctx) == Outcome.INSUFFICIENT_EVIDENCE

    # ------------------------------------------------------------------
    # Phase 3D correction — unsupported questions must not be reported as
    # partially-supported answers.  The QA model returns a zero-probability
    # span when it finds nothing answerable; that is an abstention.
    # ------------------------------------------------------------------

    @staticmethod
    def _ctx(score: float, best: float, grounded: bool, answer: str = "guess"):
        ctx = ExecutionContext()
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="text", score=best,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.retrieval_scores = [best]
        ctx.evidence.qa_result = QaResult(answer=answer, score=score, start=0, end=5)
        ctx.evidence.factual_grounded = grounded
        return ctx

    def test_zero_confidence_answer_abstains(self):
        # The model assigned no probability to any span — no answer to give,
        # whether or not the span happens to appear in the context.
        assert evaluate(self._ctx(score=0.0, best=0.40, grounded=False)) == (
            Outcome.INSUFFICIENT_EVIDENCE
        )
        assert evaluate(self._ctx(score=0.0, best=0.65, grounded=True)) == (
            Outcome.INSUFFICIENT_EVIDENCE
        )

    def test_low_but_non_zero_confidence_answer_is_not_abstained(self):
        # Regression guard against over-abstention: measured correct answers
        # exist at scores as low as 0.0001, so only an exact zero abstains.
        assert evaluate(self._ctx(score=0.0001, best=0.24, grounded=True)) == (
            Outcome.PARTIAL
        )
        assert evaluate(self._ctx(score=0.15, best=0.40, grounded=False)) == (
            Outcome.PARTIAL
        )

    def test_ungrounded_answer_weak_confidence_but_strong_retrieval_is_partial(self):
        # Strong retrieval keeps the answer partially supported.
        assert evaluate(self._ctx(score=0.15, best=0.55, grounded=False)) == (
            Outcome.PARTIAL
        )

    def test_ungrounded_answer_strong_confidence_weak_retrieval_is_partial(self):
        assert evaluate(self._ctx(score=0.60, best=0.30, grounded=False)) == (
            Outcome.PARTIAL
        )

    def test_grounded_answer_weak_signals_remains_partial(self):
        # Weak support must stay visible as PARTIAL, never be flattened into
        # abstention, when the span really is in the supplied context.
        assert evaluate(self._ctx(score=0.15, best=0.40, grounded=True)) == (
            Outcome.PARTIAL
        )

    def test_model_unavailable_error_is_unavailable(self):
        ctx = ExecutionContext()
        ctx.errors.append(
            ErrorRecord(
                category="model_unavailable",
                message="QA model missing",
                service="QA_ANSWER",
            )
        )
        assert evaluate(ctx) == Outcome.UNAVAILABLE

    def test_no_sources_abstains_regardless_of_qa_result(self):
        # Mirrors the strict evidence invariant: if nothing was supplied to QA,
        # a QA result must not be able to make the answer look supported.
        ctx = self._ctx(score=0.95, best=0.95, grounded=True)
        ctx.evidence.sources = []
        ctx.evidence.retrieval_scores = []
        assert evaluate(ctx) == Outcome.INSUFFICIENT_EVIDENCE

    def test_capability_unavailable_error(self):
        ctx = ExecutionContext()
        ctx.errors.append(
            ErrorRecord(
                category="capability_unavailable",
                message="Not implemented",
                service="brain",
            )
        )
        assert evaluate(ctx) == Outcome.UNAVAILABLE

    def test_service_failure_error(self):
        ctx = ExecutionContext()
        ctx.errors.append(
            ErrorRecord(
                category="service_failure",
                message="DB error",
                service="retrieval",
            )
        )
        assert evaluate(ctx) == Outcome.FAILED

    def test_no_plan_unsupported(self):
        ctx = ExecutionContext()
        ctx.plan = Plan(steps=(), required_capabilities=())
        # Gate only sees errors and evidence — unsupported requests are
        # handled by Brain before reaching the gate.
        assert evaluate(ctx) == Outcome.INSUFFICIENT_EVIDENCE


# =========================================================================
# RESPONSE ASSEMBLY TESTS
# =========================================================================

class TestResponseAssembly:
    def test_successful_response(self):
        ctx = ExecutionContext(raw_question="When?")
        ctx.outcome = Outcome.SUCCESS
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="1859", score=0.7,
                document_id="d1", document_name="doc.pdf", page=1,
            )
        ]
        ctx.evidence.qa_result = QaResult(answer="1859", score=0.82, start=0, end=4)
        ctx.evidence.retrieval_scores = [0.7]
        ctx.evidence.factual_grounded = True

        resp = assemble(ctx)
        assert isinstance(resp, BrainResponse)
        assert resp.answer == "1859"
        assert resp.confidence == 0.82
        assert resp.outcome == Outcome.SUCCESS
        assert resp.insufficient_context is False
        assert len(resp.sources) == 1
        assert resp.reliability["sourceCount"] == 1

    def test_insufficient_evidence_response(self):
        ctx = ExecutionContext(raw_question="What?")
        ctx.outcome = Outcome.INSUFFICIENT_EVIDENCE

        resp = assemble(ctx)
        assert resp.answer == ""
        assert resp.insufficient_context is True
        assert resp.outcome == Outcome.INSUFFICIENT_EVIDENCE

    def test_unavailable_response(self):
        ctx = ExecutionContext(raw_question="Summarize")
        ctx.outcome = Outcome.UNAVAILABLE

        resp = assemble(ctx)
        assert resp.answer == ""
        assert resp.insufficient_context is True
        assert resp.outcome == Outcome.UNAVAILABLE

    def test_reliability_source_status(self):
        ctx = ExecutionContext()
        ctx.outcome = Outcome.SUCCESS
        ctx.evidence.sources = [
            SourceRef(
                chunk_id="c1", content="a", score=0.6,
                document_id="d1", document_name="doc.pdf", page=1,
            ),
            SourceRef(
                chunk_id="c2", content="b", score=0.35,
                document_id="d1", document_name="doc.pdf", page=2,
            ),
            SourceRef(
                chunk_id="c3", content="c", score=0.2,
                document_id="d2", document_name="other.pdf", page=1,
            ),
        ]
        ctx.evidence.qa_result = QaResult(answer="x", score=0.5, start=0, end=1)
        ctx.evidence.retrieval_scores = [0.6, 0.35, 0.2]
        ctx.evidence.factual_grounded = True

        resp = assemble(ctx)
        source_statuses = [s["status"] for s in resp.reliability["sources"]]
        assert source_statuses == ["VERIFIED", "MARGINAL", "UNRESOLVED"]
        assert resp.reliability["uniqueDocuments"] == 2


# =========================================================================
# BRAIN INTEGRATION TESTS
# =========================================================================

class TestBrainIntegration:
    def _make_registry_with_test_doubles(self) -> CapabilityRegistry:
        """Create a registry with test double adapters."""
        registry = CapabilityRegistry()

        async def retrieval_adapter(user_id: str = "", cleaned_text: str = "", top_k: int = 5):
            return [
                SourceRef(
                    chunk_id="c1",
                    content="Charles Darwin published On the Origin of Species in 1859.",
                    score=0.72,
                    document_id="d1",
                    document_name="darwin.pdf",
                    page=1,
                )
            ]

        async def context_adapter(retrieval_sources=None, cleaned_text=""):
            if retrieval_sources:
                return "\n\n".join(s.content for s in retrieval_sources)
            return ""

        async def qa_adapter(cleaned_text: str = "", context: str = ""):
            return QaResult(answer="1859", score=0.82, start=56, end=60)

        registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval_adapter)
        registry.register(Capability.CONTEXT_BUILDING, context_adapter)
        registry.register(Capability.QA_ANSWER, qa_adapter)

        return registry

    @pytest.mark.asyncio
    async def test_successful_document_question(self):
        registry = self._make_registry_with_test_doubles()
        brain = Brain(registry)

        ctx = ExecutionContext(
            user_id="u1",
            raw_question="When did Darwin publish On the Origin of Species?",
        )
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.SUCCESS
        assert ctx.response is not None
        assert ctx.response.answer == "1859"
        assert ctx.response.outcome == Outcome.SUCCESS
        assert ctx.response.insufficient_context is False
        assert len(ctx.response.sources) >= 1
        assert ctx.response.confidence > 0

    @pytest.mark.asyncio
    async def test_insufficient_evidence(self):
        """No sources retrieved → INSUFFICIENT_EVIDENCE."""
        registry = CapabilityRegistry()

        async def empty_retrieval(**kwargs):
            return []

        async def context_adapter(retrieval_sources=None, cleaned_text=""):
            return ""

        async def qa_adapter(cleaned_text: str = "", context: str = ""):
            return QaResult(answer="", score=0.0, start=0, end=0)

        registry.register(Capability.DOCUMENT_RETRIEVAL, empty_retrieval)
        registry.register(Capability.CONTEXT_BUILDING, context_adapter)
        registry.register(Capability.QA_ANSWER, qa_adapter)

        brain = Brain(registry)
        ctx = ExecutionContext(user_id="u1", raw_question="What is quantum physics?")
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.INSUFFICIENT_EVIDENCE
        assert ctx.response.answer == ""

    @pytest.mark.asyncio
    async def test_unavailable_capability(self):
        """Media verification not registered → UNAVAILABLE."""
        registry = CapabilityRegistry()
        brain = Brain(registry)

        ctx = ExecutionContext(
            user_id="u1",
            raw_question="Check whether this image is a deepfake",
        )
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.UNAVAILABLE
        assert ctx.response is not None
        assert ctx.response.answer == ""
        assert len(ctx.errors) > 0
        assert ctx.errors[0].category == "capability_unavailable"

    @pytest.mark.asyncio
    async def test_unsupported_request(self):
        """Empty/unsupported → FAILED (handled by Brain, not gate)."""
        registry = CapabilityRegistry()
        brain = Brain(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="")
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.FAILED
        assert ctx.response is not None
        assert len(ctx.errors) > 0
        assert ctx.errors[0].category == "invalid_request"

    @pytest.mark.asyncio
    async def test_service_failure(self):
        """Adapter exception → FAILED."""
        registry = CapabilityRegistry()

        async def failing_retrieval(**kwargs):
            raise ConnectionError("Database unreachable")

        async def noop(**kwargs):
            return None

        # Register all capabilities needed for DOCUMENT_QUESTION,
        # but DOCUMENT_RETRIEVAL will fail.
        registry.register(Capability.DOCUMENT_RETRIEVAL, failing_retrieval)
        registry.register(Capability.CONTEXT_BUILDING, noop)
        registry.register(Capability.QA_ANSWER, noop)

        brain = Brain(registry)
        ctx = ExecutionContext(user_id="u1", raw_question="What is AI?")
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.FAILED
        assert any(e.category == "service_failure" for e in ctx.errors)

    @pytest.mark.asyncio
    async def test_intent_classified(self):
        registry = self._make_registry_with_test_doubles()
        brain = Brain(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="When was Darwin born?")
        ctx = await brain.process(ctx)

        assert ctx.parsed_request is not None
        assert ctx.parsed_request.intent == Intent.DOCUMENT_QUESTION

    @pytest.mark.asyncio
    async def test_plan_built(self):
        registry = self._make_registry_with_test_doubles()
        brain = Brain(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="What is evolution?")
        ctx = await brain.process(ctx)

        assert ctx.plan is not None
        assert len(ctx.plan.steps) == 3  # retrieval → context → qa

    @pytest.mark.asyncio
    async def test_timing_recorded(self):
        registry = self._make_registry_with_test_doubles()
        brain = Brain(registry)

        ctx = ExecutionContext(user_id="u1", raw_question="When?")
        ctx = await brain.process(ctx)

        assert ctx.timing.total_ms >= 0
        assert ctx.timing.retrieval_ms >= 0
        assert ctx.timing.qa_ms >= 0

    @pytest.mark.asyncio
    async def test_search_intent_only_retrieval(self):
        """DOCUMENT_SEARCH only runs retrieval, no QA."""
        registry = CapabilityRegistry()

        async def retrieval_adapter(**kwargs):
            return [
                SourceRef(
                    chunk_id="c1", content="evolution text", score=0.6,
                    document_id="d1", document_name="doc.pdf", page=1,
                )
            ]

        registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval_adapter)

        brain = Brain(registry)
        ctx = ExecutionContext(user_id="u1", raw_question="Find mentions of evolution")
        ctx = await brain.process(ctx)

        assert ctx.outcome == Outcome.SUCCESS
        assert ctx.response.sources[0].content == "evolution text"
        # No QA was run
        assert ctx.evidence.qa_result is None


# =========================================================================
# DEPENDENCY / IMPORT TEST
# =========================================================================

class TestBrainDependencyIsolation:
    """Verify brain/ does not import infrastructure or services."""

    PROHIBITED = [
        "sqlalchemy", "fastapi", "asyncpg", "pgvector",
        "torch", "transformers", "sentence_transformers",
        "fitz", "docx",
        "chat.rag", "chat.qa_model", "embeddings.model",
        "documents.processing", "reliability.routes",
        "verification.routes", "storage.database", "auth.dependencies",
    ]

    def test_no_prohibited_imports_in_brain_core(self):
        """Core Brain modules (not adapters) must not import infrastructure."""
        import pathlib
        brain_dir = pathlib.Path(__file__).resolve().parent.parent / "brain"

        # adapters.py is the service bridge — it MAY import services.
        # Only test the core Brain modules.
        core_files = ["__init__.py", "types.py", "classifier.py",
                      "planner.py", "executor.py", "gate.py", "response.py"]

        violations = []
        for name in core_files:
            py_file = brain_dir / name
            if not py_file.exists():
                continue
            content = py_file.read_text(encoding="utf-8")
            import_lines = [
                line.strip()
                for line in content.splitlines()
                if line.strip().startswith("from ") or line.strip().startswith("import ")
            ]
            for line in import_lines:
                for prohibited in self.PROHIBITED:
                    if prohibited in line:
                        violations.append(f"{name}: {prohibited} in: {line}")

        assert not violations, (
            f"Brain core modules contain prohibited imports: {violations}"
        )
