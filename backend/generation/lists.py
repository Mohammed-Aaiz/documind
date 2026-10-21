"""Deterministic resolution of ordered-list questions.

Second application of the rule proven for tables in Mission 6: when the evidence
already states the answer structurally, resolve it from the structure instead of
asking the 250M-parameter seq2seq model.

Measured on the frozen P3 benchmark (2026-10-21): of 20 ``LIST_ITEM`` questions —
"which citation is listed third", "name the fifth key financial highlights",
"which current leadership handles cfo: robert tanaka" — the generative path
answered **2** correctly. The model returned the wrong item, a truncated item
("Elena Vasquez" for "COO: Elena Vasquez (since June 2021)"), or two concatenated
items. Every one of those contexts is a heading line followed by one item per
line, and the gold answer is that item **verbatim**.

Two question forms are supported:

* **positional** — an explicit ordinal ("first", "third", "comes fourth",
  "listed eighth", "last") selects the item at that 1-based position;
* **by content** — no ordinal, but the question names one item ("handles cfo:
  robert tanaka", "operating margin: 22.1%"), which selects the single item
  containing those terms.

Conservatism, in order of importance:

* a list is a run of **consecutive non-empty lines**: a heading plus at least two
  item lines. Prose paragraphs are separated by blank lines and therefore never
  form a run;
* the heading must be named by the question (all of its terms occur in it), so a
  question about something else cannot be answered from a nearby list;
* a positional answer requires an explicit ordinal that the list is long enough
  to satisfy — a position beyond the list abstains rather than extrapolating;
* a content answer requires one uniquely best item and at least two shared terms;
* nothing is inferred from retrieval rank or from the order blocks were supplied
  in: the position always comes from the evidence's own line order;
* any unresolved or ambiguous case returns ``None`` and the caller falls back to
  generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from generation.tables import subject_terms
from generation.types import EvidenceBlock
from generation.verification import _stem

#: A list needs at least two items after its heading.  One "item" is a wrapped
#: prose line, not a list.
MIN_LIST_ITEMS = 2

#: A heading is a label, not a sentence: no terminal punctuation, few words.
MAX_HEADING_WORDS = 8
MAX_ITEM_CHARS = 200

_TERMINAL_PUNCTUATION = (".", ":", ";", "?", "!", ",")

_ORDINALS: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "last": -1,
    "final": -1,
}

#: "the third", "comes fourth", "listed eighth", and bare ordinals all match.
_ORDINAL_RE = re.compile(
    r"\b(" + "|".join(_ORDINALS) + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ListBlock:
    """A heading plus its ordered items, recovered from one evidence block."""

    heading: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class ListAnswer:
    """An ordered-list answer taken verbatim from the evidence.

    ``position`` is the 1-based position within ``items`` (``None`` for a
    content-matched item), so the caller can report *why* this item was chosen
    without re-deriving it.
    """

    text: str
    citation: int
    heading: str
    position: int | None
    matched_by: str  # "position" | "content"


def _is_heading(line: str) -> bool:
    """Whether ``line`` can be a list heading rather than a first item.

    A colon is disqualifying: ``Revenue: $847.3 million`` is a key/value item, not
    a heading, and treating it as one shifts every position by one.
    """
    return (
        bool(line)
        and not line.endswith(_TERMINAL_PUNCTUATION)
        and "|" not in line
        and ":" not in line
        and len(line.split()) <= MAX_HEADING_WORDS
    )


def parse_lists(text: str) -> list[ListBlock]:
    """Recover heading+items lists from ``text``; never raises, never guesses.

    Lines are used directly: the evidence keeps one item per line, and the
    sentence splitter deliberately joins a newline followed by a lower-case word,
    which would merge items and destroy their positions.
    """
    blocks: list[ListBlock] = []
    run: list[str] = []

    def flush() -> None:
        nonlocal run
        if len(run) >= MIN_LIST_ITEMS + 1:
            heading, items = run[0], tuple(run[1:])
            shortest_item = min(len(item.split()) for item in items)
            if (
                _is_heading(heading)
                and len(heading.split()) <= shortest_item
                and all(item and len(item) <= MAX_ITEM_CHARS for item in items)
                and not any("|" in item for item in items)
            ):
                blocks.append(ListBlock(heading=heading, items=items))
        run = []

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        run.append(line)
    flush()
    return blocks


def requested_position(question: str) -> int | None:
    """The 1-based ordinal a question asks for, or ``None``.

    ``last``/``final`` return ``-1``; the caller resolves it against the list
    length.  A question with two ordinals is ambiguous and returns ``None``.
    """
    matches = _ORDINAL_RE.findall(question)
    if len(matches) != 1:
        return None
    return _ORDINALS[matches[0].lower()]


def _heading_named_by(question: str, block: ListBlock) -> bool:
    """Whether the question names this list's heading.

    Compared on stems so a singular question ("the last key financial
    highlight") still names a plural heading ("Key Financial Highlights"); the
    heading's terms must all appear, so this stays a strict subset test.
    """
    heading_terms = {_stem(token) for token in subject_terms(block.heading)}
    if not heading_terms:
        return False
    return heading_terms <= {_stem(token) for token in subject_terms(question)}


def _resolve_by_position(block: ListBlock, position: int) -> tuple[str, int] | None:
    if position == -1:
        return block.items[-1], len(block.items)
    if 1 <= position <= len(block.items):
        return block.items[position - 1], position
    return None


def _resolve_by_content(question: str, block: ListBlock) -> tuple[str, int] | None:
    """The single item the question describes, by shared distinctive terms."""
    question_terms = set(subject_terms(question))
    scored: list[tuple[int, int]] = []
    for index, item in enumerate(block.items):
        overlap = len(question_terms & set(subject_terms(item)))
        if overlap:
            scored.append((overlap, index))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    if best < 2:
        return None
    winners = [index for score, index in scored if score == best]
    if len(winners) != 1:
        return None
    index = winners[0]
    return block.items[index], index + 1


def resolve_list_answer(
    question: str, blocks: Sequence[EvidenceBlock]
) -> ListAnswer | None:
    """Resolve an ordered-list question, or ``None`` when it cannot be resolved."""
    if not question or not blocks:
        return None

    if len(_ORDINAL_RE.findall(question)) > 1:
        # Two positions in one question ("the first and third item") cannot be
        # answered with one item, and must not silently degrade to a content
        # match.
        return None

    position = requested_position(question)

    for block in blocks:
        for sequence in parse_lists(block.content):
            if not _heading_named_by(question, sequence):
                continue

            if position is not None:
                if getattr(block, "truncated", False):
                    # The excerpt dropped the tail without a marker, so a
                    # position cannot be established — abstain rather than
                    # return whichever item survived the cut.
                    continue
                resolved = _resolve_by_position(sequence, position)
                if resolved is None:
                    # The list is shorter than the requested position: the
                    # evidence cannot answer this, so abstain rather than guess.
                    continue
                text, resolved_position = resolved
                return ListAnswer(
                    text=text,
                    citation=block.index,
                    heading=sequence.heading,
                    position=resolved_position,
                    matched_by="position",
                )

            resolved = _resolve_by_content(question, sequence)
            if resolved is None:
                continue
            text, resolved_position = resolved
            return ListAnswer(
                text=text,
                citation=block.index,
                heading=sequence.heading,
                position=resolved_position,
                matched_by="content",
            )
    return None


__all__ = [
    "ListAnswer",
    "ListBlock",
    "parse_lists",
    "requested_position",
    "resolve_list_answer",
]
