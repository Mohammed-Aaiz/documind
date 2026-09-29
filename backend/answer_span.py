"""Answer-span reconstruction — the single shared implementation.

Why this module exists
----------------------
Both the production QA path and every Phase 4F evaluation runner used to turn a
predicted token span into answer text with::

    tokenizer.decode(input_ids[start:end + 1], skip_special_tokens=True).strip()

``decode()`` re-joins WordPiece tokens with inserted spaces, so any value the
tokenizer split came back corrupted::

    142.6 million  ->  "142. 6 million"
    $4,900         ->  "$ 4, 900"
    2011-2020      ->  "2011 - 2020"

Those artefacts suppressed EM/F1 for every numeric, date, currency and
percentage answer in every recorded Phase 4F result.  The tokenizer's
``return_offsets_mapping=True`` output points each token back into the original
string, so slicing the source context reproduces the document's literal
characters instead of a re-tokenized approximation.

Consumers
---------
* ``chat/qa_model.py`` — the live QA path (answer text, ``start`` and ``end``).
* ``phase4f/**`` — the Phase 4F evaluation runners.

This module is deliberately **dependency-free** (standard library only) and
lives at the ``backend/`` root so that both layers can import it without either
one depending on the other: production code must not reach into the research
tree, and the Phase 4F runners are launched from many different working
directories (including self-contained archived GPU packages) where importing
``chat.*`` would pull in the service layer and its environment configuration.
"""

from __future__ import annotations

import os

#: Environment variable selecting the span-selection protocol.
#: ``joint`` (default, protocol v2) or ``argmax_chain`` (protocol v1, the recorded
#: Phase 4F runners).  See :func:`select_answer_span`.
SPAN_SELECTION_ENV = "PHASE4F_SPAN_SELECTION"
PROTOCOL_JOINT = "joint"
PROTOCOL_ARGMAX_CHAIN = "argmax_chain"


def active_span_selection() -> str:
    """The span-selection protocol in force, from ``$PHASE4F_SPAN_SELECTION``."""
    return os.getenv(SPAN_SELECTION_ENV, PROTOCOL_JOINT).strip().lower()


def span_text(context, offsets, sequence_ids, span):
    """Answer text for a ``(start, end)`` span, or ``""`` when unmappable."""
    if span is None:
        return ""
    char_span = answer_char_span(offsets, sequence_ids, span[0], span[1])
    return context[char_span[0]:char_span[1]] if char_span else ""


def answer_char_span(
    offsets,
    sequence_ids,
    start_idx: int,
    end_idx: int,
):
    """Map an inclusive token span to ``(char_start, char_end)`` in the context.

    ``start_idx``/``end_idx`` are inclusive token positions; the returned
    ``char_end`` is exclusive, so ``context[char_start:char_end]`` is the answer.

    Returns ``None`` when the span cannot be mapped onto the *context* string:

    * ``offsets``/``sequence_ids`` are unavailable (slow tokenizer);
    * the span is out of range or inverted;
    * either token belongs to sequence 0 (the question) or to no sequence
      (``[CLS]``/``[SEP]``/padding) — offset mappings are relative to whichever
      sequence a token came from, so a question token's offsets point into the
      question, not the context;
    * the mapped character range is empty.
    """
    if offsets is None or sequence_ids is None:
        return None
    length = len(offsets)
    if start_idx < 0 or end_idx < start_idx or end_idx >= length:
        return None
    if sequence_ids[start_idx] != 1 or sequence_ids[end_idx] != 1:
        return None
    char_start = offsets[start_idx][0]
    char_end = offsets[end_idx][1]
    if char_end <= char_start:
        return None
    return char_start, char_end


def reconstruct_answer(context, offsets, sequence_ids, start_idx, end_idx,
                       tokenizer=None, input_ids=None):
    """Answer text taken from the ORIGINAL ``context``.

    Falls back to ``tokenizer.decode()`` when the span cannot be mapped onto the
    context (see :func:`answer_char_span`), which preserves the previous
    behaviour for those degenerate spans.
    """
    span = answer_char_span(offsets, sequence_ids, start_idx, end_idx)
    if span is not None:
        return context[span[0]:span[1]]
    if tokenizer is not None and input_ids is not None:
        return tokenizer.decode(
            input_ids[start_idx:end_idx + 1], skip_special_tokens=True
        ).strip()
    return ""


def select_joint_span(start_logits, end_logits, sequence_ids, max_answer_length,
                      offsets=None):
    """Pick the inclusive ``(start, end)`` token pair maximising ``start_logit + end_logit``.

    This is the standard SQuAD-style extractive span selection. The alternative
    used by the Phase 4F runners — ``argmax(start)`` and then ``argmax(end)``
    inside a window after that start — is not equivalent: the best end for the
    best start is not necessarily the best end overall, so the greedy chain can
    settle on a span the model itself scores lower.

    Only context-mappable spans are considered (both tokens from sequence 1,
    ``e - s + 1 <= max_answer_length``). Pass ``offsets`` (the tokenizer's
    ``offset_mapping``) to additionally require the span to map onto real
    context characters — without it the trailing ``[SEP]``, whose sequence id is
    1 but whose character range is empty, stays a candidate. Returns ``None``
    when no such span exists. ``start_logits``/``end_logits``/``sequence_ids``
    are plain sequences (e.g. ``tensor.tolist()``), which keeps this module
    dependency-free.
    """
    if sequence_ids is None or start_logits is None or end_logits is None:
        return None
    n = min(len(start_logits), len(end_logits), len(sequence_ids))
    best_score = None
    best = None
    for s in range(n):
        if sequence_ids[s] != 1:
            continue
        upper = min(s + max_answer_length, n)
        for e in range(s, upper):
            if sequence_ids[e] != 1:
                continue
            if offsets is not None and answer_char_span(
                offsets, sequence_ids, s, e
            ) is None:
                continue
            score = start_logits[s] + end_logits[e]
            if best_score is None or score > best_score:
                best_score = score
                best = (s, e)
    return best


def recorded_argmax_chain(start_logits, end_logits, window, max_items=None):
    """Protocol v1: ``argmax(start)`` then ``argmax(end)`` inside ``window``.

    This is the greedy chain the recorded Phase 4F runners used. It is kept so that
    v1 numbers stay reproducible from this same module (``PHASE4F_SPAN_SELECTION=
    argmax_chain``) instead of only from git history. Note that it does NOT mask
    ``[CLS]``, so the chosen start can be a question/special token — that is a
    faithful reproduction, not an endorsement.

    Ties resolve to the lowest index, matching ``numpy.argmax``/``torch.argmax``.
    """
    n = len(start_logits) if max_items is None else min(len(start_logits), max_items)
    if n <= 0:
        return None
    start_idx = 0
    for i in range(1, n):
        if start_logits[i] > start_logits[start_idx]:
            start_idx = i
    upper = min(start_idx + window, len(end_logits))
    end_idx = start_idx
    for i in range(start_idx + 1, upper):
        if end_logits[i] > end_logits[end_idx]:
            end_idx = i
    return start_idx, end_idx


def select_answer_span(context, offsets, sequence_ids, start_logits, end_logits,
                       max_answer_length, tokenizer=None, input_ids=None,
                       protocol=None):
    """The Phase 4F answer step: pick a span, then read it from the ORIGINAL context.

    ``protocol`` defaults to ``$PHASE4F_SPAN_SELECTION`` (or ``"joint"``):

    * ``"joint"`` — protocol v2. Maximises ``start_logit + end_logit`` over
      context-mappable spans (:func:`select_joint_span`). The span always maps onto
      real context characters, so the answer never falls back to decoded tokens.
    * ``"argmax_chain"`` — protocol v1, the rule the recorded Phase 4F runners used
      (:func:`recorded_argmax_chain`). Kept for before/after re-runs.

    ``start_logits``/``end_logits`` may be tensors or plain sequences. Returns
    ``(answer, start_idx, end_idx)``; a degenerate absence of any selectable span
    gives ``("", 0, 0)``.
    """
    if hasattr(start_logits, "tolist"):
        start_logits = start_logits.tolist()
    if hasattr(end_logits, "tolist"):
        end_logits = end_logits.tolist()

    mode = protocol or active_span_selection()
    if mode == PROTOCOL_ARGMAX_CHAIN:
        span = recorded_argmax_chain(start_logits, end_logits, max_answer_length)
    else:
        span = select_joint_span(start_logits, end_logits, sequence_ids,
                                 max_answer_length, offsets=offsets)
    if span is None:
        return "", 0, 0

    text = reconstruct_answer(context, offsets, sequence_ids, span[0], span[1],
                              tokenizer=tokenizer, input_ids=input_ids)
    return text, span[0], span[1]


def tokenize_with_offsets(tokenizer, question, context, **kwargs):
    """Tokenize a (question, context) pair, returning ``(encoding, offsets, seq_ids)``.

    ``kwargs`` are forwarded to the tokenizer (``max_length``, ``truncation``,
    ``padding``, ``return_tensors``...).  ``return_offsets_mapping`` is always
    forced on, and the mapping is removed from ``encoding`` afterwards so the
    result can still be passed to a model.
    """
    encoding = tokenizer(
        question, context, return_offsets_mapping=True, **kwargs
    )
    offsets = encoding["offset_mapping"]
    # return_tensors batches this to shape [1, seq, 2]
    if hasattr(offsets, "tolist"):
        offsets = offsets.tolist()
    if (offsets and isinstance(offsets[0], list)
            and offsets[0] and isinstance(offsets[0][0], list)):
        offsets = offsets[0]
    offsets = [tuple(o) for o in offsets]
    sequence_ids = list(encoding.sequence_ids(0))
    del encoding["offset_mapping"]
    return encoding, offsets, sequence_ids
