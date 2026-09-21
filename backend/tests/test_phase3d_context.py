"""Phase 3D — QA context window and evidence-reporting tests.

The companion change to chunking: the context supplied to the QA model must be
measured in tokens against the model's real window, and the sources reported as
evidence must be exactly the ones the model was given.
"""

from __future__ import annotations

import pytest

from chat.rag import (
    MIN_CONTEXT_TOKENS,
    ContextPack,
    build_context,
    build_qa_context,
    truncate_to_tokens,
)
from chat.qa_model import (
    count_input_tokens,
    count_text_tokens,
    get_max_input_length,
    is_tokenizer_available,
)

pytestmark = pytest.mark.skipif(
    not is_tokenizer_available(), reason="QA tokenizer unavailable"
)


def chunk(cid: str, content: str, score: float = 0.5):
    from chat.rag import SourceChunk

    return SourceChunk(
        chunk_id=cid,
        content=content,
        score=score,
        document_id="d1",
        document_name="doc.txt",
        page=1,
    )


SENTENCE = "The Kestrel programme concluded in 1984 after twelve flights. "


def long_text(tokens_wanted: int) -> str:
    """Approximate text of a given token size, built from whole sentences."""
    text = ""
    while count_text_tokens(text) is None or count_text_tokens(text) < tokens_wanted:
        text += SENTENCE
    return text.strip()


# ===========================================================================
# Window arithmetic
# ===========================================================================

class TestWindow:
    def test_max_input_length_matches_the_model_config(self):
        assert get_max_input_length() == 384

    def test_context_is_a_str_subclass(self):
        pack = build_qa_context([chunk("c1", "Short context.")], "What?")
        assert isinstance(pack, str)
        assert pack.strip() == "Short context."

    def test_never_exceeds_the_model_window(self):
        question = "When did the Kestrel programme conclude?"
        chunks = [chunk(f"c{i}", long_text(120)) for i in range(6)]
        pack = build_qa_context(chunks, question)
        total = count_input_tokens(question, str(pack))
        assert total <= get_max_input_length(), total
        assert pack.used_tokens <= pack.budget_tokens

    def test_long_question_reduces_the_budget(self):
        chunks = [chunk("c1", long_text(120))]
        short = build_qa_context(chunks, "Why?")
        long_q = build_qa_context(chunks, " ".join(["Why"] * 200))
        assert long_q.budget_tokens < short.budget_tokens

    def test_empty_chunk_list_yields_empty_context(self):
        pack = build_qa_context([], "Who?")
        assert pack == ""
        assert pack.included_ids == ()
        assert pack.omitted_ids == ()


# ===========================================================================
# Selection behaviour
# ===========================================================================

class TestSelection:
    def test_top_chunk_is_always_included(self):
        huge = chunk("c1", long_text(4000))
        pack = build_qa_context([huge], "What happened?")
        assert pack.included_ids == ("c1",)
        assert pack.truncated_ids == ("c1",)
        assert count_input_tokens("What happened?", str(pack)) <= get_max_input_length()

    def test_large_early_chunk_does_not_starve_later_evidence(self):
        """The legacy builder ``break``s on overflow; this one must not."""
        big = chunk("big", long_text(3000), score=0.9)
        small = chunk("small", "The Kestrel programme concluded in 1984.", score=0.8)
        pack = build_qa_context([big, small], "When did Kestrel conclude?")

        # ``big`` is the top chunk and is truncated; ``small`` still gets in
        # because the loop continues rather than stopping.
        assert "big" in pack.included_ids
        assert "small" in pack.included_ids or "small" in pack.omitted_ids

    def test_later_chunks_are_included_when_they_fit(self):
        first = chunk("a", "Short opening context.", 0.9)
        second = chunk("b", "The answer is 1984.", 0.8)
        pack = build_qa_context([first, second], "When?")
        assert pack.included_ids == ("a", "b")
        assert "1984" in str(pack)

    def test_non_fitting_later_chunk_is_skipped_not_truncated(self):
        first = chunk("a", long_text(200), 0.9)
        oversized = chunk("b", long_text(3000), 0.8)
        tail = chunk("c", "Tail evidence 1984.", 0.7)
        pack = build_qa_context([first, oversized, tail], "When?")

        assert pack.included_ids == ("a", "c")
        assert "b" in pack.omitted_ids
        assert pack.truncated_ids == ()

    def test_omissions_are_recorded_never_silent(self):
        chunks = [chunk(f"c{i}", long_text(200)) for i in range(5)]
        pack = build_qa_context(chunks, "Question?")
        counted = len(pack.included_ids) + len(pack.omitted_ids)
        assert counted == len(chunks)
        assert set(pack.included_ids).isdisjoint(pack.omitted_ids)

    def test_blank_chunks_are_recorded_as_omitted(self):
        pack = build_qa_context([chunk("a", "   "), chunk("b", "Real text.")], "Q?")
        assert "a" in pack.omitted_ids
        assert "b" in pack.included_ids


# ===========================================================================
# Truncation
# ===========================================================================

class TestTruncation:
    def test_truncation_prefers_sentence_boundaries(self):
        text = "First sentence here. " * 40
        trimmed = truncate_to_tokens(text, 50)
        assert trimmed.endswith(".")
        assert count_text_tokens(trimmed) <= 50

    def test_truncation_falls_back_to_characters_without_boundaries(self):
        # Words but no sentence terminators anywhere: the sentence-aligned path
        # finds nothing, so the character binary search must take over.
        text = "alpha " * 500
        assert count_text_tokens(text) > 60
        trimmed = truncate_to_tokens(text, 60)
        assert 0 < len(trimmed) < len(text)
        assert count_text_tokens(trimmed) <= 60

    def test_oversized_single_word_collapses_as_the_model_sees_it(self):
        # WordPiece turns a >100-character word into a single [UNK] token, so
        # count and model agree; the accounting must not disagree with the
        # model it is budgeting for.
        word = "X" * 5000
        assert count_text_tokens(word) == 1
        assert truncate_to_tokens(word, 60) == word

    def test_zero_budget_returns_empty(self):
        assert truncate_to_tokens("Any text at all.", 0) == ""


# ===========================================================================
# Legacy comparison
# ===========================================================================

class TestLegacyContrast:
    def test_legacy_builder_overflows_the_model_window(self):
        """Documents why the companion change is required.

        The legacy builder happily returns ~4000 characters, far more than the
        QA model's token window, so most of it is silently discarded.
        """
        chunks = [chunk(f"c{i}", long_text(200)) for i in range(5)]
        legacy = build_context(chunks)
        assert count_text_tokens(legacy) > get_max_input_length()

    def test_token_aware_builder_uses_most_of_the_window(self):
        chunks = [chunk("a", long_text(150)), chunk("b", long_text(150))]
        pack = build_qa_context(chunks, "Why?")
        utilisation = pack.used_tokens / max(1, pack.budget_tokens)
        assert utilisation > 0.8, utilisation


# ===========================================================================
# Brain evidence reporting
# ===========================================================================

class TestEvidenceReporting:
    async def test_reported_sources_match_the_supplied_context(self):
        from brain import Brain
        from brain.executor import CapabilityRegistry
        from brain.types import Capability, ExecutionContext, QaResult, SourceRef

        supplied = ["kept1", "kept2"]
        registry = CapabilityRegistry()

        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return [
                SourceRef(chunk_id=cid, content=f"content of {cid}", score=score,
                          document_id="d1", document_name="doc.txt", page=1)
                for cid, score in (("kept1", 0.8), ("kept2", 0.7), ("dropped", 0.6))
            ]

        async def context(retrieval_sources=None, cleaned_text=""):
            return ContextPack(
                "content of kept1\n\ncontent of kept2",
                included_ids=tuple(supplied),
                omitted_ids=("dropped",),
                truncated_ids=(),
                budget_tokens=100,
                used_tokens=50,
                exact=True,
            )

        async def qa(cleaned_text="", context=""):
            return QaResult(answer="content", score=0.9, start=0, end=7)

        registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval)
        registry.register(Capability.CONTEXT_BUILDING, context)
        registry.register(Capability.QA_ANSWER, qa)

        ctx = ExecutionContext(user_id="u1", raw_question="What is kept?")
        ctx = await Brain(registry).process(ctx)

        evidence = ctx.evidence
        assert [s.chunk_id for s in evidence.sources] == supplied
        assert evidence.grounding_signals["omitted_source_ids"] == ["dropped"]
        assert evidence.grounding_signals["retrieved_source_count"] == 3
        assert evidence.grounding_signals["context_used_tokens"] == 50
        assert evidence.retrieval_scores == [0.8, 0.7]
        assert ctx.response.reliability["sourceCount"] == 2
        assert ctx.response.reliability["omittedSourceCount"] == 1
        assert ctx.response.reliability["retrievedSourceCount"] == 3

    async def test_plain_string_context_preserves_previous_behaviour(self):
        from brain.executor import CapabilityRegistry
        from brain.types import Capability, ExecutionContext, QaResult, SourceRef
        from brain import Brain

        registry = CapabilityRegistry()

        async def retrieval(user_id="", cleaned_text="", top_k=5):
            return [
                SourceRef(chunk_id="c1", content="text", score=0.8,
                          document_id="d1", document_name="d.txt", page=1)
            ]

        async def context(retrieval_sources=None, cleaned_text=""):
            return "text"

        async def qa(cleaned_text="", context=""):
            return QaResult(answer="text", score=0.9, start=0, end=4)

        registry.register(Capability.DOCUMENT_RETRIEVAL, retrieval)
        registry.register(Capability.CONTEXT_BUILDING, context)
        registry.register(Capability.QA_ANSWER, qa)

        ctx = ExecutionContext(user_id="u1", raw_question="What?")
        ctx = await Brain(registry).process(ctx)
        assert [s.chunk_id for s in ctx.evidence.sources] == ["c1"]
        assert ctx.response.reliability["sourceCount"] == 1
        assert ctx.response.reliability["omittedSourceCount"] == 0
