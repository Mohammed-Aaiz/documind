"""Regression tests for the shared ``answer_span`` module.

The production QA path and every Phase 4F evaluation runner used
``tokenizer.decode()`` on the predicted token span, which re-inserts spaces at
subword boundaries and corrupts numeric, date, currency and percentage answers.
These tests pin the replacement behaviour.

``answer_span`` is the single shared implementation (production + research);
``TestSingleImplementation`` guards that there is exactly one copy of it.
"""

from __future__ import annotations

import pytest

from answer_span import (
    PROTOCOL_ARGMAX_CHAIN,
    PROTOCOL_JOINT,
    SPAN_SELECTION_ENV,
    answer_char_span,
    reconstruct_answer,
    recorded_argmax_chain,
    select_answer_span,
    select_joint_span,
    span_text,
    tokenize_with_offsets,
)


def _load_qa_tokenizer():
    from pathlib import Path

    import chat.qa_model as qa
    from transformers import AutoTokenizer

    path = Path(qa._MODEL_NAME)
    if not path.exists():
        return None
    try:
        return AutoTokenizer.from_pretrained(str(path))
    except Exception:
        return None


_TOKENIZER = _load_qa_tokenizer()

requires_tokenizer = pytest.mark.skipif(
    _TOKENIZER is None, reason="QA tokenizer unavailable"
)


# ===========================================================================
# answer_char_span — mapping rules
# ===========================================================================

class TestAnswerCharSpan:
    def test_valid_context_span(self):
        assert answer_char_span([(0, 3), (4, 11)], [1, 1], 0, 1) == (0, 11)

    def test_no_offsets_available(self):
        assert answer_char_span(None, None, 0, 0) is None
        assert answer_char_span([(0, 3)], None, 0, 0) is None

    def test_question_only_span_is_rejected(self):
        # sequence id 0 == question; its offsets point into the question
        assert answer_char_span([(0, 4)], [0], 0, 0) is None

    def test_special_token_span_is_rejected(self):
        assert answer_char_span([(0, 0)], [None], 0, 0) is None

    def test_inverted_and_out_of_range_spans(self):
        assert answer_char_span([(0, 4), (5, 8)], [1, 1], 1, 0) is None
        assert answer_char_span([(0, 4)], [1], 0, 5) is None
        assert answer_char_span([(0, 4)], [1], -1, 0) is None

    def test_empty_character_range_is_rejected(self):
        assert answer_char_span([(0, 0), (0, 0)], [1, 1], 0, 1) is None


# ===========================================================================
# reconstruct_answer — source text, never decoded tokens
# ===========================================================================

NUMERIC_CASES = [
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
]


def _span_for(question, context, target):
    enc, offsets, sequence_ids = tokenize_with_offsets(
        _TOKENIZER, question, context, max_length=384, truncation=True,
        padding="max_length", return_tensors="pt",
    )
    for a in range(len(offsets)):
        if sequence_ids[a] != 1:
            continue
        for b in range(a, len(offsets)):
            if sequence_ids[b] != 1:
                continue
            if context[offsets[a][0]:offsets[b][1]] == target:
                return offsets, sequence_ids, a, b
    return offsets, sequence_ids, None, None


@requires_tokenizer
class TestReconstructAnswer:
    @pytest.mark.parametrize("question,context,target", NUMERIC_CASES)
    def test_answer_is_exact_source_text(self, question, context, target):
        offsets, sequence_ids, a, b = _span_for(question, context, target)
        assert a is not None, f"{target!r} is not a single token span"
        assert reconstruct_answer(context, offsets, sequence_ids, a, b) == target

    @pytest.mark.parametrize("question,context,target", NUMERIC_CASES)
    def test_decoding_would_have_corrupted_the_answer(self, question, context, target):
        """Guard: the value the old decode-based path produced."""
        enc, offsets, sequence_ids = tokenize_with_offsets(
            _TOKENIZER, question, context, max_length=384, truncation=True,
            padding="max_length", return_tensors="pt",
        )
        _, _, a, b = _span_for(question, context, target)
        decoded = _TOKENIZER.decode(
            enc["input_ids"][0][a:b + 1], skip_special_tokens=True
        ).strip()
        assert decoded != target

    def test_falls_back_to_decoding_when_unmappable(self):
        context = "The revenue was 142.6 million dollars."
        tokenizer = _TOKENIZER
        enc, offsets, sequence_ids = tokenize_with_offsets(
            tokenizer, "What was the revenue?", context, max_length=384,
            truncation=True, padding="max_length", return_tensors="pt",
        )
        # token 1 is a question token -> no context span
        result = reconstruct_answer(
            context, offsets, sequence_ids, 1, 1,
            tokenizer=tokenizer, input_ids=enc["input_ids"][0],
        )
        assert result == tokenizer.convert_ids_to_tokens(
            int(enc["input_ids"][0][1])
        )

    def test_padding_positions_do_not_leak_into_the_answer(self):
        context = "The budget was $4,900."
        offsets, sequence_ids, a, b = _span_for("What was the budget?", context, "$4,900")
        assert a is not None
        # a trailing padded token has sequence id None and offsets (0, 0)
        enc, offsets, sequence_ids = tokenize_with_offsets(
            _TOKENIZER, "What was the budget?", context, max_length=384,
            truncation=True, padding="max_length", return_tensors="pt",
        )
        last = len(offsets) - 1
        assert answer_char_span(offsets, sequence_ids, a, last) is None


# ===========================================================================
# tokenize_with_offsets — encoding stays model-ready
# ===========================================================================

@requires_tokenizer
class TestTokenizeWithOffsets:
    def test_offset_mapping_is_removed_from_the_encoding(self):
        enc, offsets, sequence_ids = tokenize_with_offsets(
            _TOKENIZER, "What was the revenue?",
            "The revenue was 142.6 million dollars.", max_length=384,
            truncation=True, padding="max_length", return_tensors="pt",
        )
        assert "offset_mapping" not in enc
        # still a valid model input
        assert set(enc.keys()) <= {"input_ids", "attention_mask", "token_type_ids"}
        assert len(offsets) == len(sequence_ids) == enc["input_ids"].shape[1]

    def test_offsets_point_back_into_the_context(self):
        context = "The revenue was 142.6 million dollars."
        _, offsets, sequence_ids = tokenize_with_offsets(
            _TOKENIZER, "What was the revenue?", context, max_length=384,
            truncation=True, padding="max_length", return_tensors="pt",
        )
        for offset, seq in zip(offsets, sequence_ids):
            if seq == 1:
                assert context[offset[0]:offset[1]]


# ===========================================================================
# span_text — answer text for a span, or ""
# ===========================================================================

class TestSpanText:
    CONTEXT = "The revenue was 142.6 million dollars."
    OFFSETS = [(4, 11), (12, 15), (16, 29)]
    SEQ = [1, 1, 1]

    def test_returns_the_source_slice(self):
        assert span_text(self.CONTEXT, self.OFFSETS, self.SEQ, (0, 0)) == "revenue"
        assert span_text(self.CONTEXT, self.OFFSETS, self.SEQ, (0, 2)) == \
            "revenue was 142.6 million"

    def test_none_span_is_empty(self):
        assert span_text(self.CONTEXT, self.OFFSETS, self.SEQ, None) == ""

    def test_unmappable_spans_are_empty(self):
        # question token, special/padding token, and an empty character range
        assert span_text(self.CONTEXT, self.OFFSETS, [0, 1, 1], (0, 0)) == ""
        assert span_text(self.CONTEXT, [(0, 0)], [1], (0, 0)) == ""
        assert span_text(self.CONTEXT, None, None, (0, 0)) == ""
        assert span_text(self.CONTEXT, self.OFFSETS, self.SEQ, (0, 9)) == ""


# ===========================================================================
# select_joint_span — the joint-logit selection rule
# ===========================================================================

class TestSelectJointSpan:
    def test_joint_selection_is_not_the_argmax_chain(self):
        """The greedy chain can settle on a pair the model itself scores lower.

        Here ``argmax(start)`` is token 0, whose window (max length 2) only
        reaches token 1 -> score 10.  The joint optimum is token 4 paired with
        itself -> score 18.
        """
        start = [10.0, 0.0, 0.0, 0.0, 9.0]
        end = [0.0, 0.0, 2.0, 3.0, 9.0]
        assert select_joint_span(start, end, [1, 1, 1, 1, 1], 2) == (4, 4)

    def test_joint_selection_never_scores_lower_than_the_argmax_chain(self):
        start = [10.0, 0.0, 8.0, 0.0, 0.0]
        end = [0.0, 1.0, 1.0, 7.0, 0.0]
        seq = [1, 1, 1, 1, 1]
        max_len = 2
        s, e = select_joint_span(start, end, seq, max_len)
        chain_s = 0
        chain_e = chain_s + max(range(min(chain_s + max_len, 5) - chain_s),
                                key=lambda o: end[chain_s + o])
        assert start[s] + end[e] >= start[chain_s] + end[chain_e]

    def test_max_answer_length_bounds_the_span(self):
        start = [5.0, 0.0]
        end = [0.0, 9.0]
        assert select_joint_span(start, end, [1, 1], 2) == (0, 1)
        # length 1 -> the profitable end is out of reach from token 0, so the
        # (lower-scoring) start is no longer the chain's free choice
        assert select_joint_span(start, end, [1, 1], 1) == (1, 1)

    def test_only_context_tokens_are_candidates(self):
        start = [100.0, 5.0, 0.0]
        end = [100.0, 0.0, 4.0]
        # token 0 = question, token 2 = padding
        assert select_joint_span(start, end, [0, 1, None], 5) == (1, 1)
        assert select_joint_span(start, end, [0, 0, None], 5) is None

    def test_returns_none_without_inputs_or_valid_spans(self):
        assert select_joint_span(None, [1.0], [1], 5) is None
        assert select_joint_span([1.0], None, [1], 5) is None
        assert select_joint_span([1.0], [1.0], None, 5) is None
        assert select_joint_span([1.0], [1.0], [0], 5) is None
        assert select_joint_span([1.0], [1.0], [None], 5) is None

    def test_offsets_reject_spans_that_cannot_map_to_text(self):
        start = [1.0, 7.0, 100.0]
        end = [1.0, 7.0, 100.0]
        seq = [1, 1, 1]
        # token 2 is the trailing [SEP]: sequence id 1, empty character range
        offsets = [(0, 3), (4, 7), (0, 0)]
        assert select_joint_span(start, end, seq, 3) == (2, 2)
        assert select_joint_span(start, end, seq, 3, offsets=offsets) == (1, 1)

    def test_accepts_plain_sequences(self):
        """Dependency-free: lists, not tensors."""
        assert select_joint_span([1, 2], [3, 4], [1, 1], 2) == (1, 1)

    def test_first_maximum_wins_ties(self):
        assert select_joint_span([1.0, 1.0], [1.0, 1.0], [1, 1], 1) == (0, 0)


# ===========================================================================
# recorded_argmax_chain — the v1 protocol, kept reproducible
# ===========================================================================

class TestRecordedArgmaxChain:
    def test_greedy_chain(self):
        assert recorded_argmax_chain([1.0, 5.0, 0.0], [0.0, 1.0, 9.0], 3) == (1, 2)

    def test_window_bounds_the_end(self):
        start, end = [5.0, 0.0], [0.0, 9.0]
        assert recorded_argmax_chain(start, end, 2) == (0, 1)
        assert recorded_argmax_chain(start, end, 1) == (0, 0)

    def test_does_not_mask_cls(self):
        """Faithfulness to v1: the chain is allowed to pick token 0."""
        assert recorded_argmax_chain([9.0, 1.0], [1.0, 1.0], 2) == (0, 0)

    def test_ties_resolve_to_the_lowest_index(self):
        assert recorded_argmax_chain([1.0, 1.0], [1.0, 1.0], 2) == (0, 0)

    @pytest.mark.parametrize(
        "start,end",
        [([0.1, 3.0, 2.9, 0.0], [2.0, 0.5, 1.5, 1.4]),
         ([5.0, 0.0, 0.0], [0.0, 0.0, 7.0]),
         ([-1.0, -2.0, -3.0], [-3.0, -2.0, -1.0])],
    )
    def test_matches_numpy_argmax(self, start, end):
        import numpy as np

        s = int(np.argmax(start))
        e = s + int(np.argmax(end[s:s + 2]))
        assert recorded_argmax_chain(start, end, 2) == (s, e)

    def test_empty_input_has_no_span(self):
        assert recorded_argmax_chain([], [], 5) is None


# ===========================================================================
# select_answer_span — the runner answer step, both protocols
# ===========================================================================

class TestSelectAnswerSpan:
    CONTEXT = "The revenue was 142.6 million dollars."
    # token 0 = [CLS] (question), 1-4 = context, 5 = trailing [SEP]
    OFFSETS = [(0, 0), (4, 11), (12, 15), (16, 29), (30, 37), (0, 0)]
    SEQ = [0, 1, 1, 1, 1, 1]
    # the greedy chain's argmax start is [CLS]; joint selection cannot use it
    START = [9.0, 5.0, 0.0, 1.0, 0.0, 0.0]
    END = [0.0, 0.0, 0.0, 9.0, 0.0, 0.0]
    WINDOW = 4

    def test_joint_is_the_default(self):
        text, s, e = select_answer_span(
            self.CONTEXT, self.OFFSETS, self.SEQ, self.START, self.END, self.WINDOW)
        assert (s, e) == (1, 3)
        assert text == "revenue was 142.6 million"

    def test_v1_protocol_is_reproducible(self):
        text, s, e = select_answer_span(
            self.CONTEXT, self.OFFSETS, self.SEQ, self.START, self.END, self.WINDOW,
            protocol=PROTOCOL_ARGMAX_CHAIN)
        assert (s, e) == (0, 3)  # the greedy chain picks the [CLS] start
        assert text == ""       # ... which cannot be mapped onto the context

    def test_environment_variable_switches_the_protocol(self, monkeypatch):
        monkeypatch.setenv(SPAN_SELECTION_ENV, PROTOCOL_ARGMAX_CHAIN)
        assert select_answer_span(
            self.CONTEXT, self.OFFSETS, self.SEQ, self.START, self.END,
            self.WINDOW)[1:] == (0, 3)
        monkeypatch.setenv(SPAN_SELECTION_ENV, PROTOCOL_JOINT)
        assert select_answer_span(
            self.CONTEXT, self.OFFSETS, self.SEQ, self.START, self.END,
            self.WINDOW)[1:] == (1, 3)

    def test_accepts_tensors(self):
        import torch

        text, s, e = select_answer_span(
            self.CONTEXT, self.OFFSETS, self.SEQ,
            torch.tensor(self.START), torch.tensor(self.END), self.WINDOW)
        assert (s, e) == (1, 3)
        assert text == "revenue was 142.6 million"

    def test_no_selectable_span_gives_empty_and_zero(self):
        assert select_answer_span("x", [(0, 0)], [0], [5.0], [5.0], 4) == ("", 0, 0)
        assert select_answer_span("x", [(0, 0)], [None], [5.0], [5.0], 4) == ("", 0, 0)


# ===========================================================================
# Exactly one implementation, shared by production and research
# ===========================================================================

class TestSingleImplementation:
    def test_production_uses_the_shared_function(self):
        """chat/qa_model.py must not carry its own copy of the mapping rules."""
        import chat.qa_model as qa

        assert qa.answer_char_span is answer_char_span

    def test_no_second_implementation_exists(self):
        """The old duplicated module must stay deleted."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("phase4f.span_reconstruction")

    @pytest.mark.parametrize(
        "offsets,sequence_ids,start_idx,end_idx",
        [
            ([(0, 3), (4, 11)], [1, 1], 0, 1),
            ([(0, 0)], [None], 0, 0),
            ([(0, 4)], [0], 0, 0),
            ([(0, 4), (5, 8)], [1, 1], 1, 0),
            ([(0, 4)], [1], 0, 5),
            ([(0, 0), (0, 0)], [1, 1], 0, 1),
            (None, None, 0, 0),
        ],
    )
    def test_production_callers_get_the_shared_behaviour(
        self, offsets, sequence_ids, start_idx, end_idx
    ):
        from chat.qa_model import answer_char_span as production_entry

        assert production_entry(
            offsets, sequence_ids, start_idx, end_idx
        ) == answer_char_span(offsets, sequence_ids, start_idx, end_idx)
