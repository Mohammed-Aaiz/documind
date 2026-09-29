"""QA answer reconstruction — regression tests.

The production defect: the predicted token span was turned back into text with
``tokenizer.decode()``, which re-joins WordPiece tokens with inserted spaces and
therefore corrupts numbers, dates, currency and percentages::

    142.6 million  ->  "142. 6 million"
    $4,900         ->  "$ 4, 900"
    2011-2020      ->  "2011 - 2020"

The fix recovers the answer by slicing the ORIGINAL context using the
tokenizer's ``return_offsets_mapping=True`` output.

These tests use the REAL tokenizer (so the production tokenization and offset
mapping are exercised) together with a deterministic stub for the model weights,
which lets each case pin an exact answer span without depending on what the
trained model happens to predict.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

import chat.qa_model as qa


def _load_qa_tokenizer():
    """Load only the QA tokenizer (the tests never need the 265MB weights)."""
    from pathlib import Path
    from transformers import AutoTokenizer

    path = Path(qa._MODEL_NAME)
    if not path.exists():
        return None
    try:
        return AutoTokenizer.from_pretrained(str(path))
    except Exception:
        return None


_TOKENIZER = _load_qa_tokenizer()

pytestmark = pytest.mark.skipif(
    _TOKENIZER is None, reason="QA tokenizer unavailable"
)


# ---------------------------------------------------------------------------
# Deterministic model stub
# ---------------------------------------------------------------------------

class _StubQaModel:
    """Returns fixed logits so one (start, end) token pair wins deterministically."""

    def __init__(self, start_logits: torch.Tensor, end_logits: torch.Tensor) -> None:
        self._start_logits = start_logits
        self._end_logits = end_logits

    def eval(self):  # pragma: no cover - trivial
        return self

    def __call__(self, input_ids=None, attention_mask=None, token_type_ids=None, **kwargs):
        return SimpleNamespace(
            start_logits=self._start_logits,
            end_logits=self._end_logits,
        )


def _logits(seq_len: int, start_idx: int, end_idx: int,
            start_logit: float = 12.0, end_logit: float = 12.0):
    start = torch.full((1, seq_len), -100.0)
    end = torch.full((1, seq_len), -100.0)
    start[0, start_idx] = start_logit
    end[0, end_idx] = end_logit
    return start, end


@pytest.fixture
def install_stub(monkeypatch):
    """Install a tokenizer + stub model in place of the real QA weights."""

    def _install(start_logits: torch.Tensor, end_logits: torch.Tensor) -> None:
        monkeypatch.setattr(qa, "_tokenizer", _TOKENIZER)
        monkeypatch.setattr(qa, "_model", _StubQaModel(start_logits, end_logits))
        monkeypatch.setattr(qa, "_model_loaded", True)
        monkeypatch.setattr(qa, "_model_load_error", None)
        monkeypatch.setattr(
            qa,
            "_inference_config",
            {"max_input_length": 384, "max_answer_length": 100, "n_best": 20},
        )

    return _install


def _tokenize(question: str, context: str):
    """Tokenize exactly as production does, including the offset mapping."""
    return _TOKENIZER(
        question,
        context,
        return_offsets_mapping=True,
        max_length=384,
        truncation=True,
        padding=True,
    )


def _find_span(context: str, offsets, sequence_ids, target: str):
    """Token span (inclusive start/end) whose offsets cover ``target`` exactly."""
    for a in range(len(offsets)):
        if sequence_ids[a] != 1:
            continue
        for b in range(a, len(offsets)):
            if sequence_ids[b] != 1:
                continue
            if context[offsets[a][0]:offsets[b][1]] == target:
                return a, b
    return None


def _answer_for(install_stub, question: str, context: str, target: str,
                start_logit: float = 12.0, end_logit: float = 12.0):
    """Force the model to pick ``target``'s span, then run production QA."""
    enc = _tokenize(question, context)
    offsets = enc["offset_mapping"]
    sequence_ids = list(enc.sequence_ids(0))
    span = _find_span(context, offsets, sequence_ids, target)
    assert span is not None, f"{target!r} is not a single token span in {context!r}"
    start_logits, end_logits = _logits(
        len(enc["input_ids"]), span[0], span[1], start_logit, end_logit
    )
    install_stub(start_logits, end_logits)
    return qa.answer_question(question, context)


# ===========================================================================
# 1-6. Numeric / date / currency / percentage / Unicode answers
# ===========================================================================

class TestSourceTextReconstruction:
    @pytest.mark.parametrize(
        "question,context,target",
        [
            # 1. decimal
            ("What was the revenue?", "The revenue was 142.6 million dollars.",
             "142.6 million"),
            # 2. thousands separator
            ("How many people were employed?", "The company employed 89,000 people.",
             "89,000"),
            # 3. currency
            ("What was the budget?", "The budget was $4,900.", "$4,900"),
            # 4. date range
            ("When was the Transformation Era?",
             "The Transformation Era lasted from 2011-2020.", "2011-2020"),
            # 5. percentage
            ("What improvement was achieved?",
             "The treatment achieved 22.1% improvement.", "22.1%"),
            # 6. Unicode
            ("What was the threshold?", "The threshold was \u2265 95%.", "\u2265 95%"),
        ],
    )
    def test_answer_is_exact_source_text(self, install_stub, question, context, target):
        result = _answer_for(install_stub, question, context, target)
        assert result["answer"] == target

    @pytest.mark.parametrize(
        "context,target",
        [
            ("The revenue was 142.6 million dollars.", "142.6 million"),
            ("The company employed 89,000 people.", "89,000"),
            ("The budget was $4,900.", "$4,900"),
            ("The Transformation Era lasted from 2011-2020.", "2011-2020"),
            ("The treatment achieved 22.1% improvement.", "22.1%"),
            ("The threshold was \u2265 95%.", "\u2265 95%"),
        ],
    )
    def test_decoding_would_have_corrupted_the_answer(self, context, target):
        """Guard: documents the defect the fix addresses (uses the tokenizer only)."""
        enc = _tokenize("What is the value?", context)
        offsets = enc["offset_mapping"]
        sequence_ids = list(enc.sequence_ids(0))
        span = _find_span(context, offsets, sequence_ids, target)
        assert span is not None
        a, b = span
        decoded = _TOKENIZER.decode(
            enc["input_ids"][a:b + 1], skip_special_tokens=True
        ).strip()
        assert decoded != target  # the old path mangled this value

    def test_unicode_symbol_is_preserved(self, install_stub):
        result = _answer_for(
            install_stub, "What was the threshold?", "The threshold was \u2265 95%.", "\u2265 95%"
        )
        assert result["answer"] == "\u2265 95%"


# ===========================================================================
# 7. Ordinary textual answers still work
# ===========================================================================

class TestOrdinaryAnswers:
    def test_plain_text_answer(self, install_stub):
        result = _answer_for(
            install_stub, "What is the capital of France?",
            "The capital of France is Paris.", "Paris",
        )
        assert result["answer"] == "Paris"

    def test_answer_keeps_source_casing(self, install_stub):
        """The source text is authoritative, so original casing survives."""
        result = _answer_for(
            install_stub, "What is the capital of France?",
            "The capital of France is Paris.", "Paris",
        )
        assert result["answer"] == "Paris"

    def test_multi_word_text_answer(self, install_stub):
        result = _answer_for(
            install_stub, "Who led the programme?",
            "The programme was led by Dr Ada Kestrel.", "Dr Ada Kestrel",
        )
        assert result["answer"] == "Dr Ada Kestrel"


# ===========================================================================
# 8. Boundary correctness
# ===========================================================================

class TestBoundaries:
    def test_span_does_not_bleed_into_neighbours(self, install_stub):
        context = "The budget was $4,900 total."
        result = _answer_for(install_stub, "What was the budget?", context, "$4,900")
        assert result["answer"] == "$4,900"
        assert "was" not in result["answer"]
        assert "total" not in result["answer"]

    def test_decimal_value_is_not_extended(self, install_stub):
        """The exact production failure, at its smallest: 142.6 must stay 142.6."""
        context = "Total revenue was 142.6 million dollars in 2010."
        result = _answer_for(install_stub, "What was the revenue?", context, "142.6")
        assert result["answer"] == "142.6"

    def test_no_surrounding_whitespace(self, install_stub):
        context = "The company employed 89,000 people."
        result = _answer_for(
            install_stub, "How many people were employed?", context, "89,000"
        )
        assert result["answer"] == result["answer"].strip()
        assert result["answer"] == "89,000"

    def test_answer_is_a_substring_of_the_context(self, install_stub):
        context = "The Transformation Era lasted from 2011-2020."
        result = _answer_for(
            install_stub, "When was the Transformation Era?", context, "2011-2020"
        )
        assert result["answer"] in context


# ===========================================================================
# Preserved behaviour (nothing outside reconstruction changed)
# ===========================================================================

class TestPreservedBehaviour:
    def test_response_structure_unchanged(self, install_stub):
        result = _answer_for(
            install_stub, "What was the revenue?",
            "The revenue was 142.6 million dollars.", "142.6 million",
        )
        assert set(result) == {"answer", "score", "start", "end"}
        assert isinstance(result["answer"], str)
        assert isinstance(result["score"], float)
        assert isinstance(result["start"], int)
        assert isinstance(result["end"], int)

    def test_confidence_is_the_softmax_product_of_the_chosen_span(self, install_stub):
        """The confidence formula is unchanged: softmax(start) * softmax(end)."""
        question = "What was the revenue?"
        context = "The revenue was 142.6 million dollars."
        enc = _tokenize(question, context)
        span = _find_span(context, enc["offset_mapping"], list(enc.sequence_ids(0)),
                          "142.6 million")
        assert span is not None
        start_logits, end_logits = _logits(len(enc["input_ids"]), span[0], span[1],
                                           start_logit=8.0, end_logit=6.0)
        install_stub(start_logits, end_logits)

        result = qa.answer_question(question, context)

        expected = float(
            torch.softmax(start_logits, dim=1)[0][span[0]]
            * torch.softmax(end_logits, dim=1)[0][span[1]]
        )
        assert result["score"] == pytest.approx(round(expected, 4), abs=1e-6)
        assert 0.0 <= result["score"] <= 1.0

    def test_confidence_is_scored_on_the_same_span_that_is_returned(self, install_stub):
        question = "What was the budget?"
        context = "The budget was $4,900."
        result = _answer_for(install_stub, question, context, "$4,900")
        assert result["answer"] == "$4,900"
        assert result["score"] == pytest.approx(1.0, abs=1e-6)

    def test_empty_context_short_circuits_without_a_model(self):
        assert qa.answer_question("What was the revenue?", "   ") == {
            "answer": "",
            "score": 0.0,
            "start": 0,
            "end": 0,
        }


# ===========================================================================
# Safety: offsets from the question must never be sliced out of the context
# ===========================================================================

class TestOffsetSafety:
    def test_question_token_span_falls_back_to_decoding(self, monkeypatch):
        """Question tokens carry offsets into the QUESTION, not the context.

        If such a span is selected, slicing the context would return arbitrary
        characters, so the reconstruction must refuse and decode instead.
        """
        question = "What was the revenue?"
        context = "The revenue was 142.6 million dollars."

        monkeypatch.setattr(qa, "_tokenizer", _TOKENIZER)
        monkeypatch.setattr(qa, "_model_loaded", True)
        monkeypatch.setattr(qa, "_model_load_error", None)
        monkeypatch.setattr(
            qa, "_inference_config",
            {"max_input_length": 384, "max_answer_length": 100, "n_best": 20},
        )

        enc = _tokenize(question, context)
        seq_len = len(enc["input_ids"])
        # token 1 is the question's first content token
        start_logits, end_logits = _logits(seq_len, 1, 1)
        monkeypatch.setattr(qa, "_model", _StubQaModel(start_logits, end_logits))
        offsets = enc["offset_mapping"]
        decoded_question_token = _TOKENIZER.convert_ids_to_tokens(
            enc["input_ids"][1]
        )

        result = qa.answer_question(question, context)

        assert result["answer"] == decoded_question_token
        # and definitely not a bogus slice of the context
        assert result["answer"] != context[offsets[1][0]:offsets[1][1]]
        # no character span can be reported for an unmappable span
        assert (result["start"], result["end"]) == (0, 0)

    def test_char_span_helper_rejects_unmappable_spans(self):
        from answer_span import answer_char_span

        assert answer_char_span(None, None, 0, 0) is None
        # question-only span (sequence id 0)
        assert answer_char_span([(0, 4)], [0], 0, 0) is None
        # special token / empty offset
        assert answer_char_span([(0, 0)], [None], 0, 0) is None
        # inverted / out-of-range span
        assert answer_char_span([(0, 4), (5, 8)], [1, 1], 1, 0) is None
        assert answer_char_span([(0, 4)], [1], 0, 5) is None
        # valid context span -> (start, end) with an exclusive end
        span = answer_char_span([(0, 3), (4, 11)], [1, 1], 0, 1)
        assert span == (0, 11)


# ===========================================================================
# start/end are character offsets into the context (end exclusive)
# ===========================================================================

class TestCharacterOffsets:
    @pytest.mark.parametrize(
        "question,context,target",
        [
            ("What was the revenue?", "The revenue was 142.6 million dollars.",
             "142.6 million"),
            ("How many people were employed?", "The company employed 89,000 people.",
             "89,000"),
            ("What was the budget?", "The budget was $4,900.", "$4,900"),
            ("When was the Transformation Era?",
             "The Transformation Era lasted from 2011-2020.", "2011-2020"),
            ("What improvement was achieved?",
             "The treatment achieved 22.1% improvement.", "22.1%"),
            ("What was the threshold?", "The threshold was \u2265 95%.", "\u2265 95%"),
        ],
    )
    def test_context_slice_equals_answer(self, install_stub, question, context, target):
        result = _answer_for(install_stub, question, context, target)
        assert result["answer"] == target
        assert context[result["start"]:result["end"]] == target

    def test_offsets_equal_the_predicted_token_offsets(self, install_stub):
        question = "What was the revenue?"
        context = "The revenue was 142.6 million dollars."
        enc = _tokenize(question, context)
        span = _find_span(context, enc["offset_mapping"],
                          list(enc.sequence_ids(0)), "142.6 million")
        assert span is not None
        offsets = enc["offset_mapping"]

        result = _answer_for(install_stub, question, context, "142.6 million")

        assert (result["start"], result["end"]) == (
            offsets[span[0]][0], offsets[span[1]][1]
        )

    def test_end_is_exclusive(self, install_stub):
        context = "The budget was $4,900."
        result = _answer_for(install_stub, "What was the budget?", context, "$4,900")
        assert result["end"] - result["start"] == len("$4,900")
        assert 0 <= result["start"] <= result["end"] <= len(context)

    def test_empty_context_reports_zero_offsets(self):
        assert qa.answer_question("What was the revenue?", "   ")["start"] == 0
