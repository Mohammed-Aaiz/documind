"""Phase 3D reconciliation tests — the corrections made after the re-review.

These cover the three verified gaps and the two guards the contract requires:

  A. retrieval preserves the Phase 3D structure metadata
  B. reported evidence is never wider than what the QA model was supplied
  C. a missing QA model is UNAVAILABLE (not a generic FAILED)
  D. the Brain remains the only orchestration path for /api/chat/ask

Everything here is deterministic and tokenizer-free, so the invariants are
checked even when the QA model or tokenizer cannot be loaded.  Real
PostgreSQL/pgvector behaviour is validated separately by
``test_phase3d_upload_integration.py``.

Tests are async so pytest-asyncio owns the event loop; no test in this suite
may tear it down for the modules that run after it.
"""

from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from brain import Brain
from brain.executor import CapabilityRegistry
from brain.gate import QA_CONFIDENCE_STRONG, RETRIEVAL_STRONG
from brain.types import (
    Capability,
    ExecutionContext,
    ModelUnavailableError,
    QaResult,
    SourceRef,
)
from chat.rag import ContextPack, SourceChunk, coerce_heading_path
from outcomes import Outcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def source(cid: str, score: float = 0.7, **meta) -> SourceRef:
    return SourceRef(
        chunk_id=cid,
        content=f"content of {cid}",
        score=score,
        document_id="d1",
        document_name="doc.txt",
        page=1,
        **meta,
    )


def registry(retrieval, context, qa) -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(Capability.DOCUMENT_RETRIEVAL, retrieval)
    reg.register(Capability.CONTEXT_BUILDING, context)
    reg.register(Capability.QA_ANSWER, qa)
    return reg


class _FakeRow(dict):
    """Minimal asyncpg-style row with attribute access."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - test helper
            raise AttributeError(item) from exc


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """Captures the SQL and returns fixed rows, so no pgvector is needed."""

    def __init__(self, rows):
        self.rows = rows
        self.sql = ""

    async def execute(self, statement, params=None):
        self.sql = str(statement)
        return _FakeResult(self.rows)


async def _retrieve(session, query="query", user_id="user-1", top_k=5):
    from chat.rag import retrieve_chunks

    with patch("chat.rag.embed_query", return_value=[0.0] * 384):
        return await retrieve_chunks(session, user_id, query, top_k=top_k)


# ===========================================================================
# A. Retrieval metadata
# ===========================================================================

class TestRetrievalMetadata:
    @pytest.mark.asyncio
    async def test_select_includes_all_phase3d_columns(self):
        """The retrieval SQL must actually read the metadata columns."""
        session = _FakeSession([])
        await _retrieve(session)

        for column in (
            "heading_path",
            "section",
            "element_type",
            "token_count",
            "chunker_version",
        ):
            assert column in session.sql, f"retrieval does not select {column}"

        # Scoping must remain on the owning user.
        assert "d.user_id = :user_id" in session.sql

    @pytest.mark.asyncio
    async def test_metadata_is_mapped_onto_the_source_chunk(self):
        session = _FakeSession([
            _FakeRow(
                chunk_id=uuid.uuid4(),
                content="The Vermilion coating cures in 6 hours.",
                document_id=uuid.uuid4(),
                document_name="manual.docx",
                page=None,
                similarity=0.71,
                heading_path='["Reference Manual", "Epsilon"]',
                section="Epsilon",
                element_type="paragraph",
                token_count=42,
                chunker_version="chunk-v2-structure-tokens",
            )
        ])

        chunks = await _retrieve(session)

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.heading_path == ("Reference Manual", "Epsilon")
        assert chunk.section == "Epsilon"
        assert chunk.element_type == "paragraph"
        assert chunk.token_count == 42
        assert chunk.chunker_version == "chunk-v2-structure-tokens"

    @pytest.mark.asyncio
    async def test_legacy_chunks_yield_none_metadata(self):
        session = _FakeSession([
            _FakeRow(
                chunk_id=uuid.uuid4(),
                content="legacy chunk",
                document_id=uuid.uuid4(),
                document_name="old.txt",
                page=2,
                similarity=0.4,
                heading_path=None,
                section=None,
                element_type=None,
                token_count=99,
                chunker_version="chunk-v1-legacy-chars-1000-200",
            )
        ])

        chunk = (await _retrieve(session))[0]

        assert chunk.heading_path is None
        assert chunk.section is None
        assert chunk.element_type is None
        assert chunk.token_count == 99
        assert chunk.chunker_version == "chunk-v1-legacy-chars-1000-200"

    def test_heading_path_accepts_either_list_or_json_string(self):
        assert coerce_heading_path(["A", "B"]) == ("A", "B")
        assert coerce_heading_path('["A", "B"]') == ("A", "B")
        assert coerce_heading_path(None) is None
        assert coerce_heading_path([]) is None
        assert coerce_heading_path("not json") is None

    @pytest.mark.asyncio
    async def test_metadata_reaches_the_brain_evidence_bundle(self):
        """Adapter must copy metadata from SourceChunk to SourceRef."""
        from brain.adapters import retrieval_adapter

        service_chunk = SourceChunk(
            chunk_id="c1",
            content="body",
            score=0.9,
            document_id="d1",
            document_name="doc.docx",
            page=None,
            heading_path=("Handbook", "Tools"),
            section="Tools",
            element_type="list",
            token_count=17,
            chunker_version="chunk-v2-structure-tokens",
        )

        with patch(
            "brain.adapters.retrieve_chunks", new=AsyncMock(return_value=[service_chunk])
        ):
            refs = await retrieval_adapter(
                db=None, user_id="u1", cleaned_text="q", top_k=5
            )

        assert refs[0].heading_path == ("Handbook", "Tools")
        assert refs[0].section == "Tools"
        assert refs[0].element_type == "list"
        assert refs[0].token_count == 17
        assert refs[0].chunker_version == "chunk-v2-structure-tokens"


# ===========================================================================
# B. Evidence invariant — reported ⊆ supplied
# ===========================================================================

class TestEvidenceInvariant:
    @staticmethod
    async def _run(included, retrieved, answer="guess", score=0.9):
        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return list(retrieved)

        async def context(retrieval_sources=None, cleaned_text=""):
            text = "\n\n".join(s.content for s in retrieved if s.chunk_id in included)
            return ContextPack(
                text,
                included_ids=tuple(included),
                omitted_ids=tuple(
                    s.chunk_id for s in retrieved if s.chunk_id not in included
                ),
                budget_tokens=100,
                used_tokens=10,
                exact=True,
            )

        async def qa(cleaned_text="", context=""):
            return QaResult(answer=answer, score=score, start=0, end=5)

        ctx = ExecutionContext(user_id="u1", raw_question="What?")
        return await Brain(registry(retrieval, context, qa)).process(ctx)

    @pytest.mark.asyncio
    async def test_all_chunks_omitted_reports_zero_evidence(self):
        retrieved = [source("c1"), source("c2"), source("c3")]
        ctx = await self._run(included=(), retrieved=retrieved)

        assert ctx.evidence.sources == []
        assert ctx.evidence.retrieval_scores == []
        assert ctx.response.reliability["sourceCount"] == 0
        assert ctx.response.reliability["retrievedSourceCount"] == 3
        assert ctx.response.reliability["omittedSourceCount"] == 3
        assert ctx.outcome == Outcome.INSUFFICIENT_EVIDENCE
        assert ctx.response.answer == ""
        assert ctx.response.insufficient_context is True

    @pytest.mark.asyncio
    async def test_partial_inclusion_drops_only_omitted_chunks(self):
        retrieved = [source("c1"), source("c2"), source("c3")]
        ctx = await self._run(included=("c1", "c3"), retrieved=retrieved)

        reported = [s.chunk_id for s in ctx.evidence.sources]
        assert reported == ["c1", "c3"]
        assert ctx.evidence.grounding_signals["omitted_source_ids"] == ["c2"]
        assert ctx.response.reliability["sourceCount"] == 2
        assert ctx.response.reliability["omittedSourceCount"] == 1

    @pytest.mark.asyncio
    async def test_reported_evidence_never_exceeds_supplied(self):
        """Invariant across every inclusion pattern."""
        retrieved = [source(f"c{i}") for i in range(5)]
        for included in [
            (),
            ("c0",),
            ("c1", "c2"),
            ("c0", "c1", "c2", "c3", "c4"),
        ]:
            ctx = await self._run(included=included, retrieved=retrieved)
            reported = {s.chunk_id for s in ctx.evidence.sources}
            assert reported <= set(included), (included, reported)

    @pytest.mark.asyncio
    async def test_plain_string_context_keeps_previous_behaviour(self):
        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return [source("c1"), source("c2")]

        async def context(retrieval_sources=None, cleaned_text=""):
            return "content of c1"

        async def qa(cleaned_text="", context=""):
            return QaResult(answer="content", score=0.9, start=0, end=7)

        ctx = ExecutionContext(user_id="u1", raw_question="What?")
        ctx = await Brain(registry(retrieval, context, qa)).process(ctx)

        assert [s.chunk_id for s in ctx.evidence.sources] == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_abstention_hides_the_qa_span_but_keeps_the_raw_score(self):
        """An unsupported guess must not be presented as an answer."""
        retrieved = [source("c1", score=0.20)]
        ctx = await self._run(
            included=("c1",), retrieved=retrieved, answer="tungsten", score=0.0
        )

        assert ctx.outcome == Outcome.INSUFFICIENT_EVIDENCE
        assert ctx.response.answer == ""
        assert ctx.response.confidence == 0.0
        # Honest reporting: the raw score is still carried in the evidence.
        assert ctx.response.reliability["qaConfidence"] == 0.0
        assert ctx.response.reliability["sourceCount"] == 1

    @pytest.mark.asyncio
    async def test_grounded_weak_answer_still_reports_the_span(self):
        retrieved = [source("c1", score=0.80)]
        ctx = await self._run(
            included=("c1",),
            retrieved=retrieved,
            answer="content of c1",
            score=0.20,
        )

        assert ctx.outcome == Outcome.PARTIAL
        assert ctx.response.answer == "content of c1"
        assert ctx.response.confidence == 0.20


# ===========================================================================
# C. Model availability
# ===========================================================================

class TestGateCorrections:
    def test_thresholds_are_the_documented_values(self):
        from brain.gate import QA_CONFIDENCE_NONE

        assert QA_CONFIDENCE_STRONG == 0.30
        assert RETRIEVAL_STRONG == 0.50
        assert QA_CONFIDENCE_NONE == 0.0

    @pytest.mark.asyncio
    async def test_missing_qa_model_yields_unavailable(self):
        """The QA adapter must raise the Brain-owned unavailability signal."""
        from brain.adapters import qa_adapter

        with patch("brain.adapters.is_model_available", return_value=False):
            with pytest.raises(ModelUnavailableError):
                await qa_adapter(cleaned_text="q", context="some context")

    @pytest.mark.asyncio
    async def test_executor_classifies_missing_model_as_model_unavailable(self):
        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return [source("c1")]

        from brain.adapters import context_adapter, qa_adapter

        ctx = ExecutionContext(user_id="u1", raw_question="When did it happen?")
        with patch("brain.adapters.is_model_available", return_value=False):
            ctx = await Brain(
                registry(retrieval, context_adapter, qa_adapter)
            ).process(ctx)

        categories = [e.category for e in ctx.errors]
        assert "model_unavailable" in categories, categories
        assert ctx.outcome == Outcome.UNAVAILABLE
        assert ctx.response.answer == ""

    @pytest.mark.asyncio
    async def test_retrieval_only_intent_still_succeeds(self):
        """Search intents have no QA step and must remain SUCCESS."""

        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return [source("c1")]

        async def unused(**kwargs):  # pragma: no cover - must not be called
            raise AssertionError("QA must not run for search intents")

        ctx = ExecutionContext(user_id="u1", raw_question="Find mentions of Kestrel")
        ctx = await Brain(registry(retrieval, unused, unused)).process(ctx)

        assert ctx.outcome == Outcome.SUCCESS
        assert ctx.evidence.qa_result is None


# ===========================================================================
# D. Brain remains the only orchestration path
# ===========================================================================

class TestBrainIsThePath:
    def test_ask_handler_delegates_to_brain(self):
        """POST /api/chat/ask must go through Brain.process()."""
        from chat import routes

        ask_source = inspect.getsource(routes.ask)
        assert "Brain(" in ask_source
        assert "brain.process(ctx)" in ask_source
        assert "rag_answer" not in ask_source

    def test_ask_route_module_does_not_use_the_legacy_path(self):
        from chat import routes

        module_text = inspect.getsource(routes)
        assert "rag_answer" not in module_text
        assert "build_context(" not in module_text

    def test_adapters_wire_the_phase3d_context_builder(self):
        from brain import adapters

        module_text = inspect.getsource(adapters)
        assert "build_qa_context" in module_text
        assert "import build_context" not in module_text
        assert "build_context(" not in module_text
