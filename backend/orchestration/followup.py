"""Deterministic follow-up resolution against the conversation history.

Multi-turn memory has to do something real: a question like "and the second
one?" carries almost no retrievable content on its own.  This module decides —
without a model, and therefore reproducibly — whether a new question is a
follow-up, and if so builds the retrieval query from the previous user turn.

It only ever *widens* the retrieval query; the answer is still generated from
retrieved document evidence and verified against it, so conversation history
cannot become a source of facts that the documents do not contain.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

#: A question with this many words or fewer is treated as a continuation.
MAX_FOLLOWUP_WORDS = 6

#: Openers that make a short question a continuation by themselves.
FOLLOWUP_CUES: tuple[str, ...] = (
    "and ",
    "also ",
    "what about",
    "how about",
    "why",
    "how so",
    "then ",
    "else",
    "it ",
    "its ",
    "that ",
    "those ",
    "these ",
    "they ",
    "them ",
    "the same",
    "more on",
    "explain that",
    "elaborate",
    "go on",
    "continue",
)

#: Upper bound for the composed retrieval query, so a long previous turn cannot
#: dominate retrieval or the embedding window.
MAX_RETRIEVAL_QUERY_CHARS = 600


def _content(turn: object) -> str:
    if isinstance(turn, Mapping):
        return str(turn.get("content", "") or "")
    return str(getattr(turn, "content", "") or "")


def _role(turn: object) -> str:
    if isinstance(turn, Mapping):
        return str(turn.get("role", "") or "").strip().lower()
    return str(getattr(turn, "role", "") or "").strip().lower()


def last_user_question(history: Sequence[object]) -> str:
    """The most recent user turn, or ``""`` when there is none."""
    for turn in reversed(list(history)):
        if _role(turn) == "user":
            text = _content(turn).strip()
            if text:
                return text
    return ""


def is_followup(question: str) -> bool:
    """Whether ``question`` reads as a continuation of the previous turn."""
    text = question.strip().lower()
    if not text:
        return False
    if any(text.startswith(cue) for cue in FOLLOWUP_CUES):
        return True
    return len(text.split()) <= MAX_FOLLOWUP_WORDS


def resolve_followup(question: str, history: Iterable[object]) -> tuple[str, bool]:
    """Return ``(retrieval_query, resolved)`` for this turn.

    ``resolved`` is true only when a previous user question was actually
    prepended; it is reported to the client so the behaviour is visible rather
    than implicit.
    """
    clean = question.strip()
    previous = last_user_question(list(history))
    if not previous or not is_followup(clean):
        return clean, False

    if previous.lower() == clean.lower():
        return clean, False

    combined = f"{previous} {clean}".strip()
    if len(combined) > MAX_RETRIEVAL_QUERY_CHARS:
        combined = combined[:MAX_RETRIEVAL_QUERY_CHARS].rstrip()
    return combined, True


__all__ = [
    "FOLLOWUP_CUES",
    "MAX_FOLLOWUP_WORDS",
    "MAX_RETRIEVAL_QUERY_CHARS",
    "is_followup",
    "last_user_question",
    "resolve_followup",
]
