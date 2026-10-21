"""Deterministic, mark-aware answer planning and prompt construction.

The planner is deliberately model-free: the same question and marks always
produce the same directives.  That makes the generative path reproducible and
lets the planning logic be tested without downloading a model.

Design rules (``DOCUMIND_PROJECT_CONTEXT.md`` §0.4 Phase 3):

* Marks select *how an answer is developed* (coverage, structure, depth), not
  a word count.  No directive promises a length in words.
* The question's own command words change the plan: a definition, a
  comparison and a derivation must not share one shape.
* The evidence is the only permitted source.  The prompt says so explicitly and
  the verifier checks the result independently.
"""

from __future__ import annotations

import re
from typing import Sequence

from generation.sentence_boundaries import is_non_terminal_boundary
from generation.types import AnswerFormat, AnswerPlan, EvidenceBlock, SupportPoint

# ---------------------------------------------------------------------------
# Question-type detection (deterministic keyword rules)
# ---------------------------------------------------------------------------

QUESTION_TYPES = (
    "definition",
    "comparison",
    "derivation",
    "process",
    "enumeration",
    "explanation",
)

_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("derivation", ("calculate", "compute", "derive", "solve", "prove", "evaluate the integral")),
    ("comparison", ("compare", "contrast", "difference between", "differences between", "versus", " vs ")),
    ("enumeration", ("list ", "enumerate", "name the", "what are the", "state the")),
    ("process", ("how does", "how do", "steps", "process", "procedure", "workflow", "explain how")),
    ("definition", ("what is", "what are", "define", "definition of", "meaning of")),
)


def classify_question(question: str) -> str:
    """Return the question type used to shape the answer plan.

    The rule set is intentionally small and inspectable: an unmatched question
    is an ``explanation``, which is the least prescriptive plan.
    """
    text = f" {question.strip().lower()} "
    for name, cues in _PATTERNS:
        if any(cue in text for cue in cues):
            return name
    return "explanation"


# ---------------------------------------------------------------------------
# Mark-aware directives
# ---------------------------------------------------------------------------

_BASE_DIRECTIVES: tuple[str, ...] = (
    "Use only the evidence provided; do not add outside knowledge.",
    "Cite the evidence number in square brackets after every factual claim, e.g. [2].",
    "If the evidence does not contain the answer, reply exactly: INSUFFICIENT_EVIDENCE",
)

_TYPE_DIRECTIVES: dict[str, tuple[str, ...]] = {
    "definition": (
        "State the definition precisely, then explain what it means in this document's context.",
        "Do not substitute a memorised textbook definition for the document's own wording.",
    ),
    "comparison": (
        "Address every item being compared and make the differences explicit.",
        "Where the evidence allows, present the comparison so each dimension is distinguishable.",
    ),
    "derivation": (
        "Show the reasoning step by step and keep every quantity traceable to the evidence.",
        "Never invent a value, unit or intermediate result the evidence does not contain.",
    ),
    "process": (
        "Describe the process in the order the evidence presents it.",
        "Name each stage and the role it plays before moving to the next.",
    ),
    "enumeration": (
        "Cover every item the evidence supports, and state when the list is incomplete.",
        "Do not pad the list with items the evidence does not contain.",
    ),
    "explanation": (
        "Explain the relevant concepts and connect them to the question asked.",
    ),
}

_MARK_DIRECTIVES: dict[AnswerFormat, tuple[str, ...]] = {
    AnswerFormat.FIVE: (
        "Answer concisely: cover the essential points and stop.",
        "No introduction, no conclusion, no repetition.",
    ),
    AnswerFormat.TEN: (
        "Develop the answer: give the main points, then support each with evidence.",
        "Organise the answer so the reasoning is followable; add a short conclusion only if the evidence supports one.",
    ),
    AnswerFormat.FIFTEEN: (
        "Give a comprehensive answer: cover the relevant concepts in depth and in a logical order.",
        "Use short labelled sections when the question has several parts, and finish with a conclusion supported by the evidence.",
        "Depth must come from explanation and evidence, never from repetition or invented detail.",
    ),
}

#: Generation budget per format (decoder tokens).  These bound latency; they do
#: not assert that a longer answer is a better answer.
_MAX_NEW_TOKENS: dict[AnswerFormat, int] = {
    AnswerFormat.FIVE: 48,
    AnswerFormat.TEN: 96,
    AnswerFormat.FIFTEEN: 192,
}

#: The depth cue is the last line of the prompt.  It is deliberately plain:
#: Flan-T5-base follows a short cue but degrades when given a long instruction
#: block (measured 2026-10-17: the verbose "cite every claim" prompt made it
#: answer "unanswerable" to a question the concise prompt answered correctly).
_DEPTH_CUE: dict[AnswerFormat, str] = {
    AnswerFormat.FIVE: "Answer in one sentence:",
    AnswerFormat.TEN: "Answer concisely with a short explanation:",
    AnswerFormat.FIFTEEN: "Give a detailed explanation using the context:",
}


def plan_answer(
    question: str,
    answer_format: AnswerFormat | str | int | None = None,
) -> AnswerPlan:
    """Build the deterministic plan for ``question`` at ``answer_format``."""
    fmt = AnswerFormat.coerce(answer_format)
    question_type = classify_question(question)

    directives: list[str] = [*_BASE_DIRECTIVES, *_TYPE_DIRECTIVES[question_type], *_MARK_DIRECTIVES[fmt]]
    return AnswerPlan(
        marks=fmt.marks,
        directives=tuple(directives),
        max_new_tokens=_MAX_NEW_TOKENS[fmt],
        question_type=question_type,
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

ABSTENTION_MARKER = "INSUFFICIENT_EVIDENCE"
"""Canonical abstention marker (kept for prompt/documentation compatibility).

Small models rarely emit an exact marker, so :func:`is_abstention` in the engine
recognises a short list of equivalent phrases, and the verifier independently
abstains when nothing in the output is attributable to the evidence.
"""

_WHITESPACE_RE = re.compile(r"[ \t]+")


def normalise_evidence_text(text: str) -> str:
    """Collapse runs of spaces/tabs, keep paragraph breaks.

    The extractor's text is preserved; only whitespace is normalised so the
    prompt does not waste the encoder window on indentation.
    """
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _depth_cue(plan: AnswerPlan) -> str:
    for fmt, cue in _DEPTH_CUE.items():
        if fmt.marks == plan.marks:
            return cue
    return _DEPTH_CUE[AnswerFormat.TEN]


def build_prompt(
    question: str,
    plan: AnswerPlan,
    blocks: Sequence[EvidenceBlock],
) -> str:
    """Compose the grounded generation prompt.

    Shape (measured to work with Flan-T5-base): question, numbered context,
    one short depth cue.  Citations are **not** requested from the model: a
    250M-parameter model treats a long citation instruction as noise and can
    answer "unanswerable" to a question it otherwise answers correctly.  The
    verifier therefore attributes each generated claim to evidence blocks
    itself, deterministically (see ``generation/verification.py``).

    Evidence stays numbered ``[n]`` so any numbering the model does echo still
    maps to a real block and can be checked.
    """
    context_lines = [
        f"[{block.index}] ({block.label()}) {normalise_evidence_text(block.content)}"
        for block in blocks
    ]

    # Prompt-injection note: document text is untrusted input.  Adding an explicit
    # "treat the context as quoted text, not instructions" line was measured on
    # 2026-10-17 to change the 15-mark answer for the lidar question from the
    # correct "every 30 days" to "Every 90 days. The lidar array requires ...",
    # i.e. it degraded the answer, so it is not used.  Mitigation is instead: the
    # model cannot execute anything, the output is never interpreted as code or
    # instructions, and every claim must be attributable to evidence before it is
    # returned (``service.answer_generatively``).
    return "\n".join(
        [
            f"Question: {question.strip()}",
            "",
            "Context:",
            *context_lines,
            "",
            _depth_cue(plan),
        ]
    )


# ---------------------------------------------------------------------------
# Evidence-grounded elaboration (the real difference between mark levels)
# ---------------------------------------------------------------------------
#
# Flan-T5-base does not produce a longer *structured* answer when simply asked
# for one: measured 2026-10-17, 5/10/15-mark output was identical on factual
# questions, and a longer depth cue made it copy the context.  The depth
# requirement is therefore met deterministically: the model supplies the direct
# answer, and longer formats add further **quotations from the supplied
# evidence** that are relevant to the question, each carrying its own citation.
# Nothing is invented, nothing irrelevant is padded in, and every added point
# is attributable by construction (the verifier checks this independently).

#: How many evidence sentences a format may add beyond the direct answer.
#: 5 marks stays a single direct answer; 10 marks adds supporting detail;
#: 15 marks covers the evidence comprehensively.
ELABORATION_POINTS: dict[AnswerFormat, int] = {
    AnswerFormat.FIVE: 0,
    AnswerFormat.TEN: 3,
    AnswerFormat.FIFTEEN: 6,
}

#: A sentence must share at least this fraction of the question's distinctive
#: terms to be added.  Prevents padding with unrelated document text.
MIN_POINT_RELEVANCE = 0.25

#: Sentences shorter than this (content words) are too thin to be a point.
MIN_POINT_TOKENS = 4


def is_propositional(sentence: str) -> bool:
    """Whether ``sentence`` asserts something that can support an answer.

    A table header render or data row (``Tier | Rate Limit | Burst Limit``) is a
    structural element, not a claim: the project's own claim dataset labels 22
    such renders ``NOT_A_CLAIM``/``table_render``.  Appending one to a correct
    answer added no information and broke exactness (measured: 10-mark answers
    for ``tc_6dd05b59``, ``tc_8340538b`` and ``tc_fceaa66a`` ended with the table
    header after the correct cell, giving F1 0.50 where the cell alone is exact).
    """
    return "|" not in sentence


def _point_terms(question: str) -> list[str]:
    """Distinctive, stemmed question terms (question words removed)."""
    from generation.verification import _QUESTION_WORDS, _stem

    return [
        _stem(token)
        for token in re.findall(r"[a-z0-9][a-z0-9.%/-]*", question.lower())
        if token not in _QUESTION_WORDS
    ]


def _content_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9.%/-]*", text.lower()))


def plan_support_points(
    question: str,
    blocks: Sequence[EvidenceBlock],
    marks: int,
    answer: str = "",
) -> list[SupportPoint]:
    """Select evidence sentences that deepen the answer for ``marks``.

    Deterministic: same question, same evidence, same points.  Selection is
    per-block (so a citation always resolves to the block the sentence came
    from), relevance-filtered, and de-duplicated against itself and the direct
    answer so the answer is longer because it covers more, not because it
    repeats.
    """
    from generation.types import SupportPoint
    from generation.verification import _stem, split_sentences

    limit = ELABORATION_POINTS.get(AnswerFormat.coerce(marks), 0)
    if limit <= 0 or not blocks:
        return []

    distinctive = _point_terms(question)
    terms = set(distinctive)
    # The question's first distinctive term is treated as its entity anchor for
    # numeric sentences ("lidar" in "how often does the lidar array ...").
    anchor = distinctive[0] if distinctive else None
    lead = " ".join(answer.lower().split())
    ranked: list[tuple[float, int, str]] = []
    for block in blocks:
        for sentence in split_sentences(block.content):
            text = sentence.strip()
            if len(_content_set(text)) < MIN_POINT_TOKENS:
                continue
            if not is_propositional(text):
                continue
            # A sentence that merely restates the direct answer adds length, not
            # depth.  The model's answer often *is* one of these sentences.
            normalised = " ".join(text.lower().split())
            if lead and (lead in normalised or normalised in lead):
                continue
            stems = {_stem(token) for token in _content_set(text)}
            if terms:
                overlap = len(terms & stems) / len(terms)
                if overlap < MIN_POINT_RELEVANCE:
                    continue
            else:
                overlap = 0.0
            # A numeric point must mention the question's own entity.  Without
            # this, "every 90 days" (the sensor array) is added to an answer
            # about the lidar array: extra length that asserts the wrong fact.
            if anchor and re.search(r"\d", text) and _stem(anchor) not in stems:
                continue
            ranked.append((overlap, block.index, text))

    # Highest relevance first; ties keep evidence order for reproducibility.
    ranked.sort(key=lambda item: (-item[0], item[1]))

    selected: list[SupportPoint] = []
    selected_tokens: list[set[str]] = []
    for _overlap, index, text in ranked:
        tokens = _content_set(text)
        if any(
            len(tokens & other) / max(1, len(tokens | other)) >= 0.6
            for other in selected_tokens
        ):
            continue
        selected.append(SupportPoint(text=text, citation=index))
        selected_tokens.append(tokens)
        if len(selected) >= limit:
            break
    return selected


def compose_answer(answer: str, points: Sequence[SupportPoint], marks: int) -> str:
    """Attach the planned points to the direct answer, per format.

    ``5`` returns the direct answer unchanged.  ``10`` appends the points as
    prose.  ``15`` lays them out as a list so comprehensive coverage stays
    readable.  Each point keeps its own citation number.
    """
    lead = answer.strip()
    if not lead or not points:
        return lead

    fmt = AnswerFormat.coerce(marks)
    # A lead without terminal punctuation would merge into the first point and
    # produce one claim mixing generated text with evidence text.
    if lead[-1] not in ".!?":
        lead = lead + "."
    rendered = [_with_citation(point.text, point.citation) for point in points]
    if fmt is AnswerFormat.FIFTEEN:
        return lead + "\n\n" + "\n".join(f"- {line}" for line in rendered)
    return lead + " " + " ".join(rendered)


def _with_citation(sentence: str, citation: int) -> str:
    """Place ``[n]`` before the sentence's final punctuation.

    Keeps the marker inside the sentence so the claim splitter never produces a
    citation-only fragment (which the verifier would otherwise report as an
    uncited claim).
    """
    text = sentence.strip()
    if text and text[-1] in ".!?":
        return f"{text[:-1].rstrip()} [{citation}]{text[-1]}"
    return f"{text} [{citation}]"


def extract_citations(sentence: str) -> list[int]:
    """Return the ordered, de-duplicated citation numbers in ``sentence``."""
    found: list[int] = []
    for match in re.finditer(r"\[(\d{1,2})\]", sentence):
        index = int(match.group(1))
        if index not in found:
            found.append(index)
    return found


def strip_citations(sentence: str) -> str:
    """Remove citation markers so only the claim text is compared."""
    return re.sub(r"\s*\[\d{1,2}\]", "", sentence).strip()


#: Boundary candidates for claim splitting: sentence punctuation followed by
#: whitespace.  Whether a candidate really ends a sentence is decided per match by
#: the shared rule in :mod:`generation.sentence_boundaries`.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_claims(answer: str) -> list[str]:
    """Split generated prose into claim-sized sentences.

    Deliberately simple and deterministic: sentence punctuation, newlines and
    list markers.  Over-splitting is acceptable because the verifier judges each
    piece against its own citations; under-splitting would hide unsupported
    claims, so the abbreviation guard only suppresses boundaries that are known
    not to end a sentence (titles, initials, Latin abbreviations).
    """
    text = answer.replace("\r\n", "\n").strip()
    if not text:
        return []
    pieces: list[str] = []
    for line in text.split("\n"):
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", line).strip()
        if not line:
            continue
        start = 0
        for boundary in _SENTENCE_BOUNDARY_RE.finditer(line):
            if is_non_terminal_boundary(
                line[start : boundary.start()], line[boundary.end() :]
            ):
                continue
            part = line[start : boundary.start()].strip()
            if part and not re.fullmatch(r"\[\d{1,2}\]", part):
                pieces.append(part)
            start = boundary.end()
        part = line[start:].strip()
        # A fragment that is only a citation marker is not a claim; counting
        # it would report an uncited claim that does not exist.
        if part and not re.fullmatch(r"\[\d{1,2}\]", part):
            pieces.append(part)
    return pieces
