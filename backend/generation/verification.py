"""Deterministic verification of a generated answer against its evidence.

This is **not** an entailment model.  It is a lexical support check that can be
reproduced exactly on any machine, and its limits are stated where they matter:

* It catches the failure modes that motivated it: a claim citing evidence that
  does not contain its content, an invented number, a citation number that does
  not exist, and uncited factual claims.
* It will not catch a paraphrase whose words overlap the evidence but whose
  meaning is wrong, and it will mark a correct paraphrase with low lexical
  overlap as unsupported.  ``verified`` therefore means "every claim is
  lexically supported by the evidence it cites", never "the answer is correct".
"""

from __future__ import annotations

import os
import re
from typing import NamedTuple, Sequence

from generation.planning import extract_citations, split_claims, strip_citations
from generation.sentence_boundaries import is_non_terminal_boundary
from generation.types import (
    CLAIM_CONTRADICTED,
    CLAIM_INSUFFICIENT,
    CLAIM_PARTIALLY_SUPPORTED,
    CLAIM_SUPPORTED,
    CLAIM_UNSUPPORTED,
    ClaimCheck,
    EvidenceBlock,
    VerificationReport,
)

#: Support thresholds.  Deliberately conservative: a claim must share most of
#: its content words with the evidence it cites to count as supported.
SUPPORT_RATIO = 0.60

#: Lower bar applied when every number in the claim also appears in the cited
#: evidence — numbers are the part of a claim least tolerant of paraphrase.
NUMERIC_SUPPORT_RATIO = 0.45

#: A claim with no content words cannot be verified.  One content word *is* a
#: claim: "2010", "45" and "Endpoints" are exactly the answers the benchmark
#: labels, and rejecting them withheld correct answers as "too short to verify"
#: (measured 2026-10-17 during candidate evaluation: 6 of 20 rows withheld for
#: this reason alone).
MIN_CLAIM_TOKENS = 1

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.%/-]*")

_STOPWORDS = frozenset(
    """a an and are as at be been being both but by can could did do does for from had has have
    how if in into is it its may might must no not of on or other our over same should so some
    such than that the their them then there these they this those through to under up use used
    using was we were what when where which while who why will with within would""".split()
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def content_tokens(text: str) -> list[str]:
    """Lower-cased content words of ``text`` (stopwords removed)."""
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS]


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def _stem(token: str) -> str:
    """Very small suffix stripper, used only for question/evidence overlap.

    Deliberately conservative: it exists so "recalibrated" and "calibration"
    compare equal, not to be a linguistic stemmer.
    """
    for suffix in ("ations", "ation", "ions", "ion", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def question_evidence_coverage(question: str, evidence_text: str) -> float:
    """Fraction of the question's content words present in the evidence.

    Kept for compatibility and diagnostics.  The production answerability
    decision uses :func:`answerability`, which is measured to be better on both
    axes (see its docstring); a raw coverage ratio rejects legitimate questions
    phrased with generic wording such as "what was the reported monetary
    value?".
    """
    terms = [
        token for token in content_tokens(question)
        if token not in _QUESTION_WORDS
    ]
    if not terms:
        return 1.0
    evidence_stems = {_stem(token) for token in content_tokens(evidence_text)}
    matched = sum(1 for term in terms if _stem(term) in evidence_stems)
    return matched / len(terms)


#: Question words that carry no topic of their own.  A question is not
#: unanswerable merely because it says "the document" or "reported value".
#: Selecting this list is a measurement, not a preference: the gate comparison
#: below was run over all 182 frozen P3 rows.
_GENERIC_QUESTION_TERMS = frozenset(
    """report reports reported document documents describe described describes
    say says said state states stated mention mentions mentioned about given
    according text passage figure figures value values information provide
    provides provided indicate indicates indicated specify specifies specified
    exact exactly kind type sort main primarily generally name named called
    compare contrast difference differences steps step procedure process explain
    explanation list enumerate happen happens happened example examples reason
    reasons importance role work works why""".split()
)
# The second group names the *shape of the answer* (compare, list the steps,
# explain why), not its subject: a question is not unanswerable because the
# document does not literally contain the word "compare".  Adding it was
# measured on the frozen P3 benchmark: EM and F1 are unchanged (0.100 / 0.194)
# and the unanswerable spurious-answer rate is unchanged (0.024), while three of
# the five mark-depth fixture questions stopped being falsely refused.

#: Questions that ask for a quantity; when the evidence contains a number they
#: are answerable even if the question's wording does not literally repeat the
#: evidence's vocabulary ("how much is the IPO proceeds?" vs "raised $185
#: million in the IPO").
_QUANTITY_QUESTION_RE = re.compile(
    r"how (?:much|many)\b|what (?:is|was|were) the (?:value|number|amount|percentage|total|size|count)\b"
    r"|what percentage\b|what proportion\b",
    re.IGNORECASE,
)

#: Terms that name the *document's structure* or the question's own framing
#: rather than its subject: "Describe the content of the ... section", "near the
#: boundary between ... and ...", "what the table shows".  Measured on the
#: frozen P3 benchmark (2026-10-18): 44 of the 49 answerable refusals contained
#: them, and every refused row had its gold answer inside the recorded context.
#: Excluding them lowers answerable refusals 49 -> 13 and leaves gate-permitted
#: unanswerable rows at 8 of 42.  Ordinals are deliberately *not* included: in
#: "When was the first version released?" the ordinal carries the question, and
#: treating it as framing let an unanswerable row through (3 of 42 spurious).
#: The effect on answer quality is measured by ``run_generation_benchmark``.
_STRUCTURAL_QUESTION_TERMS = frozenset(
    """section sections content covered covers discussed listed comes
    boundary between near looking table show detailed full context metric
    monetary amount count""".split()
)

#: At most this many distinctive question terms may be absent from the evidence
#: before generation is refused.
MAX_MISSING_QUESTION_TERMS = 1

#: Fiscal-year notation as a single token (``FY2024``), which the project
#: tokenizer produces because it does not split a letter/digit boundary.  The
#: evidence spells the same thing "fiscal year 2024", so the token was counted
#: as one absent term *and* left the year uncounted — two false misses on a
#: question the document answers (measured: ``num_1ae85d6b``, ``num_4c6d491a``).
#: Expanding the token to its year is a normalisation, not a threshold change.
_FISCAL_YEAR_RE = re.compile(r"^fy(\d{2,4})$")


def _normalise_question_term(term: str) -> tuple[str, ...]:
    """Question-term variants that count as the same term in the evidence."""
    fiscal = _FISCAL_YEAR_RE.match(term)
    if fiscal:
        return (fiscal.group(1),)
    return (term,)


class Answerability(NamedTuple):
    """Deterministic, measured answerability decision for one request."""

    allowed: bool
    missing: tuple[str, ...]
    coverage: float
    reason: str


def answerability(question: str, evidence_text: str) -> Answerability:
    """Decide whether the evidence can answer ``question`` at all.

    Two signals, measured on the frozen P3 benchmark (182 rows; 140 answerable /
    42 unanswerable) by replaying one generation pass and applying each policy
    offline:

    =====================  =========  ===========  ==================
    policy                 EM         F1           spurious answers
    =====================  =========  ===========  ==================
    coverage >= 0.5        0.036      0.092        0.000
    no gate                0.129      0.253        0.214
    **this policy**        0.100      0.194        0.024
    =====================  =========  ===========  ==================

    It refuses only when the evidence is missing more than one distinctive
    question term, and it treats a quantity question as answerable when the
    evidence contains a number.  It is still lexical: it can be wrong about a
    paraphrase, which is why the verifier independently withholds output that
    cannot be attributed to the evidence.
    """
    distinctive = [
        term
        for token in content_tokens(question)
        if token not in _QUESTION_WORDS
        and token not in _GENERIC_QUESTION_TERMS
        and token not in _STRUCTURAL_QUESTION_TERMS
        for term in _normalise_question_term(token)
    ]
    coverage = question_evidence_coverage(question, evidence_text)
    if not distinctive:
        return Answerability(True, (), coverage, "the question has no distinctive terms to check")

    evidence_stems = {_stem(token) for token in content_tokens(evidence_text)}
    missing = tuple(term for term in distinctive if _stem(term) not in evidence_stems)
    if len(missing) <= MAX_MISSING_QUESTION_TERMS:
        return Answerability(True, missing, coverage, "at most one distinctive question term is absent")

    if _QUANTITY_QUESTION_RE.search(question) and _NUMBER_RE.search(evidence_text):
        return Answerability(
            True,
            missing,
            coverage,
            "the question asks for a quantity and the evidence contains a number",
        )

    return Answerability(
        False,
        missing,
        coverage,
        "the evidence is missing more than one distinctive question term: "
        + ", ".join(missing),
    )


def support_ratio(claim: str, evidence_text: str) -> float:
    """Fraction of the claim's content words present in the evidence.

    A claim can legitimately consist only of words the content filter removes
    (``Other``, ``All``, ``Total``) — a table row or column named that way is a
    real gold answer.  Comparing such a claim against the content-word set gave
    ``0.0`` and withheld it (measured: ``tc_03298034``, gold ``Other``).  For
    that case only, raw tokens are compared on both sides.
    """
    text = strip_citations(claim)
    claim_tokens = content_tokens(text)
    if claim_tokens:
        evidence_tokens = set(content_tokens(evidence_text))
    else:
        claim_tokens = _TOKEN_RE.findall(text.lower())
        evidence_tokens = set(_TOKEN_RE.findall((evidence_text or "").lower()))
    if not claim_tokens:
        return 0.0
    if not evidence_tokens:
        return 0.0
    matched = sum(1 for token in claim_tokens if token in evidence_tokens)
    return matched / len(claim_tokens)


def numbers_supported(claim: str, evidence_text: str) -> bool:
    """Whether every number in the claim appears in the evidence."""
    claim_numbers = _numbers(strip_citations(claim))
    if not claim_numbers:
        return True
    return claim_numbers <= _numbers(evidence_text)


def attribute_claim(
    sentence: str, blocks: Sequence[EvidenceBlock]
) -> tuple[list[int], float, str]:
    """Attribute one claim to the evidence blocks that support it.

    Returns ``(supporting_indices, best_ratio, reason)``.  Attribution is
    **derived by this function**, not taken from the model: a model-supplied
    ``[n]`` is checked too (a wrong number is reported), but a missing one is
    not treated as an ungrounded answer.
    """
    claim_text = strip_citations(sentence)
    if not content_tokens(claim_text) and len(
        _TOKEN_RE.findall(claim_text.lower())
    ) < MIN_CLAIM_TOKENS:
        return [], 0.0, "claim too short to verify"

    stated = extract_citations(sentence)
    by_index = {block.index: block for block in blocks}
    invalid = [index for index in stated if index not in by_index]
    if invalid:
        return [], 0.0, "model cited a non-existent evidence number: " + ", ".join(
            str(index) for index in invalid
        )

    # A number is the least tolerant part of a claim: if the claim states one,
    # the evidence it is attributed to must contain that exact value.  Lexical
    # overlap alone is never enough for a numeric claim ("every 45 days" shares
    # most of its words with "every 30 days" but asserts a different fact).
    claim_numbers = bool(_numbers(claim_text))
    threshold = NUMERIC_SUPPORT_RATIO if claim_numbers else SUPPORT_RATIO

    # Score every block: attribution must not depend on the model naming one.
    scored: list[tuple[float, bool, int]] = []
    for block in blocks:
        ratio = support_ratio(claim_text, block.content)
        numeric_ok = numbers_supported(claim_text, block.content)
        scored.append((ratio, numeric_ok, block.index))

    best_ratio, best_numeric, _ = max(scored, key=lambda item: (item[0], item[1]))

    if claim_numbers and not best_numeric:
        return [], best_ratio, "claim contains a value absent from the evidence"
    if best_ratio < threshold:
        return [], best_ratio, "claim text is not sufficiently present in the evidence"

    # A model citation, when present, must itself be among the supporting blocks.
    supporting = [
        index
        for ratio, numeric_ok, index in scored
        if ratio >= threshold and numeric_ok
    ]
    if stated and not set(stated) & set(supporting):
        return [], best_ratio, "claim cites evidence that does not contain it"

    return sorted(supporting), best_ratio, "attributed to evidence"


# ---------------------------------------------------------------------------
# Entity alignment for numeric claims
# ---------------------------------------------------------------------------
#
# The measured failure this targets: the extractive model answered
# "every 90 days" (the *sensor* array) for a question about the *lidar* array,
# because both numbers appear in the same retrieved passage.  Lexical support
# alone accepts that.  This check requires the sentence that contains the
# claimed value to be about the same entity as the sentence that mentions the
# question's distinctive term.

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

#: Question words that never identify the entity being asked about.
_QUESTION_WORDS = frozenset(
    """how often many much long frequently frequently frequency interval period what when where
    which why who whom whose does do did is are was were the a an of in on for to at by""".split()
)


def split_sentences(text: str) -> list[str]:
    """Sentence split that does not break a line-wrapped or abbreviated sentence.

    Extracted document text wraps mid-sentence ("...requires\ncalibration...").
    A newline followed by a lower-case word continues the sentence; a newline
    after sentence punctuation or before a capital starts a new one.

    Spaces after a period are decided by the shared abbreviation rule, so
    ``CEO: Dr. Sarah Chen`` and ``The U.S. team`` stay in one sentence while a real
    sentence boundary still splits.  A newline is always a boundary: evidence
    lines and table rows are structural, and a paragraph break is not an
    abbreviation.
    """
    joined = re.sub(r"\n+(?=[a-z0-9(])", " ", text)
    pieces: list[str] = []
    start = 0
    for boundary in _SENTENCE_SPLIT_RE.finditer(joined):
        if "\n" not in boundary.group() and is_non_terminal_boundary(
            joined[start : boundary.start()], joined[boundary.end() :]
        ):
            continue
        part = joined[start : boundary.start()].strip()
        if part:
            pieces.append(part)
        start = boundary.end()
    part = joined[start:].strip()
    if part:
        pieces.append(part)
    return pieces


def _subject_tokens(sentence: str) -> list[str]:
    """Content tokens before the first number — the sentence's subject/head."""
    tokens = content_tokens(sentence)
    numbers = {match.start() for match in _NUMBER_RE.finditer(sentence)}
    if numbers:
        first_number = min(numbers)
        prefix = sentence[:first_number]
        head = content_tokens(prefix)[:2]
        if head:
            return head
    return tokens[:2]


def _rare_question_term(question: str, evidence_text: str) -> str | None:
    """The question's most distinctive term, by document frequency in the evidence."""
    sentences = split_sentences(evidence_text)
    if len(sentences) < 2:
        return None
    terms = [
        token for token in content_tokens(question)
        if token not in _QUESTION_WORDS
    ]
    if not terms:
        return None
    frequencies = {
        term: sum(1 for s in sentences if term in content_tokens(s))
        for term in terms
    }
    candidates = [term for term in terms if frequencies[term] > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda term: (frequencies[term], term))


def _raw_terms(text: str) -> set[str]:
    """Lower-cased tokens longer than two characters, question words removed."""
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 2 and token not in _QUESTION_WORDS
    }


def _parse_pipe_table(
    sentences: Sequence[str],
) -> tuple[list[str], list[list[str]]] | None:
    """Header and equal-width data rows of a simple pipe-delimited table.

    Extracted tables arrive as one header line followed by one line per row.
    A line with fewer than three cells, or a row whose width differs from the
    header, is not treated as a table: the caller falls back to the prose rule.
    """
    header: list[str] | None = None
    rows: list[list[str]] = []
    for sentence in sentences:
        if "|" not in sentence:
            continue
        cells = [cell.strip() for cell in sentence.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if header is None:
            header = cells
        elif len(cells) == len(header):
            rows.append(cells)
    if header is None or not rows:
        return None
    return header, rows


def _table_entity_alignment(
    question: str, claim_numbers: set[str], sentences: Sequence[str]
) -> str | None:
    """Column-aware entity check for pipe tables, or ``None`` when not a table.

    The prose rule anchors on the sentence containing the question's rarest
    term.  For a table that sentence is the **header**, so a value in the
    matching data row looks like a different entity and is wrongly withheld
    (measured: ``1,000 req/min`` and ``+4.2%`` were exact gold answers).  Here
    the header names the asked column, cell 0 names the row, and a claim is
    accepted only when all of its numbers in that row sit in the asked column.
    Cell 0 is never used to infer the asked column: it is the row label/table
    title (``Tier``, ``Division``), and questions such as "the payment schedule
    of Q2 2025" name the table, not a column.
    """
    table = _parse_pipe_table(sentences)
    if table is None:
        return None
    header, rows = table
    question_terms = _raw_terms(question)
    overlaps = [
        (len(question_terms & _raw_terms(cell)), index)
        for index, cell in enumerate(header)
        if index > 0 and question_terms & _raw_terms(cell)
    ]
    if not overlaps:
        return None
    # Prefer the header with the most shared terms; on a tie, the leftmost.
    asked_column = max(overlaps, key=lambda item: (item[0], -item[1]))[1]

    rows_with_value = [
        row for row in rows if any(_numbers(cell) & claim_numbers for cell in row)
    ]
    if not rows_with_value:
        return "unable"
    for row in rows_with_value:
        if not (_raw_terms(row[0]) & question_terms):
            continue
        value_columns = {
            index for index, cell in enumerate(row) if _numbers(cell) & claim_numbers
        }
        if value_columns and value_columns <= {asked_column}:
            return "matched"
        return "mismatch"
    return "mismatch"


def _list_entity_alignment(
    question: str, claim_text: str, evidence_text: str
) -> str | None:
    """Membership check for heading+item evidence, or ``None`` when not a list.

    The prose rule anchors on the sentence containing the question's rarest term.
    For a heading + one-item-per-line block that sentence is the **heading**, so
    an item is judged to belong to a different entity and withheld — measured on
    the ordinal list questions (``COO: Elena Vasquez (since June 2021)`` was
    rejected because "Current Leadership" does not repeat inside the item).

    The test is against the list's **items**, not against sentences: the evidence
    sentence splitter fragments exactly the lines a list resolver returns
    (``R.T. (2025).`` becomes two sentences, ``OAuth 2.0 ...`` is merged with the
    next item).  A claim that occurs inside an item of a list whose heading names
    the question's focus belongs to that heading by construction.

    The import is deferred because ``generation.lists`` imports ``tables``, which
    imports this module.
    """
    from generation.lists import parse_lists

    lists = parse_lists(evidence_text)
    if not lists:
        return None
    claim = " ".join(strip_citations(claim_text).lower().split())
    if not claim:
        return None
    focus = _rare_question_term(question, evidence_text)
    if focus is None:
        # No distinctive term means no heading can be tied to the question; the
        # prose rule stays in charge rather than accepting any nearby list.
        return None
    for sequence in lists:
        # ``_raw_terms``, not ``content_tokens``: the resolver compares headings
        # without dropping stopwords, and a heading must be resolvable and
        # verifiable by the same test.
        heading_stems = {_stem(token) for token in _raw_terms(sequence.heading)}
        if _stem(focus) not in heading_stems:
            continue
        if any(claim in " ".join(item.lower().split()) for item in sequence.items):
            return "matched"
    return None


def numeric_entity_alignment(question: str, claim: str, evidence_text: str) -> str:
    """Whether a numeric claim's sentence is about the question's entity.

    Returns ``matched``, ``mismatch``, ``not_applicable`` (no number in the
    claim, or too little structure to judge) or ``unable`` (the value sentence
    could not be located).  It never guesses.
    """
    claim_numbers = _numbers(strip_citations(claim))
    if not claim_numbers:
        return "not_applicable"
    sentences = split_sentences(evidence_text)
    if len(sentences) < 2:
        return "not_applicable"

    table_decision = _table_entity_alignment(question, claim_numbers, sentences)
    if table_decision is not None:
        return table_decision

    list_decision = _list_entity_alignment(question, claim, evidence_text)
    if list_decision is not None:
        return list_decision

    focus = _rare_question_term(question, evidence_text)
    if focus is None:
        return "not_applicable"

    anchor = next(
        (s for s in sentences if focus in content_tokens(s)),
        None,
    )
    if anchor is None:
        return "unable"
    anchor_subject = set(_subject_tokens(anchor))
    if not anchor_subject:
        return "not_applicable"

    value_sentences = [s for s in sentences if _numbers(s) & claim_numbers]
    if not value_sentences:
        return "unable"

    if any(anchor_subject <= set(content_tokens(s)) for s in value_sentences):
        return "matched"

    # The anchor sentence is chosen by the question's rarest term, which can be
    # a passing mention of the entity ("the sensor array ...") rather than the
    # sentence that answers the question.  A value sentence is therefore also
    # accepted when it mentions that rarest term itself: the question's focus is
    # the entity, whereas a term shared by every sentence ("calibration") says
    # nothing about which entity the value belongs to.
    focus_stem = _stem(focus)
    if any(focus_stem in {_stem(t) for t in content_tokens(s)} for s in value_sentences):
        return "matched"
    return "mismatch"


def check_claim(
    sentence: str,
    blocks: Sequence[EvidenceBlock],
    question: str | None = None,
) -> ClaimCheck:
    """Judge one sentence against the evidence blocks."""
    indices, ratio, reason = attribute_claim(sentence, blocks)
    if not indices:
        return ClaimCheck(
            sentence=sentence,
            citation_indices=[],
            supported=False,
            support_ratio=round(ratio, 4),
            reason=reason,
            state=CLAIM_UNSUPPORTED,
        )

    by_index = {block.index: block for block in blocks}
    supporting = [by_index[index] for index in indices]
    best = max(
        supporting,
        key=lambda block: support_ratio(strip_citations(sentence), block.content),
    )
    entity_check = "not_applicable"
    if question and question.strip():
        entity_check = numeric_entity_alignment(question, sentence, best.content)

    if entity_check == "mismatch":
        return ClaimCheck(
            sentence=sentence,
            citation_indices=indices,
            supported=False,
            support_ratio=round(ratio, 4),
            reason="value appears in the evidence but belongs to a different entity",
            state=CLAIM_UNSUPPORTED,
            entity_check="mismatch",
        )

    return ClaimCheck(
        sentence=sentence,
        citation_indices=indices,
        supported=True,
        support_ratio=round(ratio, 4),
        reason=reason,
        state=CLAIM_SUPPORTED,
        entity_check=entity_check,
    )


VERIFIER_MODE_ENV = "DOCUMIND_VERIFIER"
"""``lexical`` (default) or ``relations``.

The relation-aware verifier lives in ``generation.verification_relations`` and is
opt-in: the default behaviour of the API is unchanged unless an operator sets this
variable.  Evaluation of both modes is recorded in
``evaluation/reports/claim_verification_2026-10-17`` and
``.../generation_benchmark_2026-10-17_fmt10_relations_verifier``.
"""


def verifier_mode() -> str:
    """Which verifier is configured (unknown values fall back to ``lexical``)."""
    value = os.environ.get(VERIFIER_MODE_ENV, "lexical").strip().lower()
    return value if value in ("lexical", "relations") else "lexical"


def verify_with_mode(
    answer: str,
    blocks: Sequence[EvidenceBlock],
    question: str | None = None,
) -> VerificationReport:
    """Verify with the configured verifier (the single entry point for callers).

    ``lexical`` is the production verifier.  ``relations`` aggregates the
    claim-level verdicts of the relation-aware verifier into the same
    :class:`VerificationReport` contract, so routes, persistence and the frontend
    keep working unchanged.
    """
    if verifier_mode() == "relations":
        from generation.verification_relations import verify_answer_claims

        return _report_from_verdicts(verify_answer_claims(answer, blocks, question))
    return verify_answer(answer, blocks, question=question)


def _report_from_verdicts(verdicts) -> VerificationReport:
    """Aggregate relation verdicts into the existing report contract."""
    from generation.planning import extract_citations

    checks: list[ClaimCheck] = []
    contradicted: list[str] = []
    for verdict in verdicts:
        stated = extract_citations(verdict.claim)
        state = {
            "SUPPORTED": CLAIM_SUPPORTED,
            "CONTRADICTED": CLAIM_CONTRADICTED,
            "INSUFFICIENT_EVIDENCE": CLAIM_INSUFFICIENT,
        }.get(verdict.label, CLAIM_UNSUPPORTED)
        if state == CLAIM_CONTRADICTED:
            contradicted.append(verdict.claim)
        checks.append(
            ClaimCheck(
                sentence=verdict.claim,
                citation_indices=list(stated),
                supported=state == CLAIM_SUPPORTED,
                support_ratio=verdict.best_support_score,
                reason=verdict.explanation,
                state=state,
            )
        )

    supported = [check for check in checks if check.supported]
    unsupported = [check.sentence for check in checks if not check.supported]
    if not checks:
        return VerificationReport(verified=False, status=CLAIM_INSUFFICIENT)
    if len(supported) == len(checks):
        status = CLAIM_SUPPORTED
    elif supported:
        status = CLAIM_PARTIALLY_SUPPORTED
    elif all(check.state == CLAIM_INSUFFICIENT for check in checks):
        status = CLAIM_INSUFFICIENT
    else:
        status = CLAIM_UNSUPPORTED

    return VerificationReport(
        claims=checks,
        citation_accuracy=round(len(supported) / len(checks), 4),
        supported_claims=len(supported),
        unsupported_claims=unsupported[:10],
        uncited_claims=sum(1 for check in checks if not check.citation_indices),
        verified=len(supported) == len(checks),
        status=status,
        contradicted_claims=contradicted[:10],
    )


def verify_answer(
    answer: str,
    blocks: Sequence[EvidenceBlock],
    question: str | None = None,
) -> VerificationReport:
    """Verify every claim in ``answer`` against ``blocks``.

    Empty evidence, an empty answer, or an answer that is only the abstention
    marker all yield an explicit state rather than a vacuous pass.
    """
    if not blocks:
        return VerificationReport(verified=False, status=CLAIM_INSUFFICIENT)

    sentences = split_claims(answer)
    if not sentences:
        return VerificationReport(verified=False, status=CLAIM_INSUFFICIENT)

    checks = [check_claim(sentence, blocks, question=question) for sentence in sentences]
    supported = [check for check in checks if check.supported]
    unsupported = [check.sentence for check in checks if not check.supported]
    uncited = sum(1 for check in checks if not check.citation_indices)

    # Every claim is attributed by this module, so accuracy is the fraction of
    # claims the evidence actually supports.  It is not a probability.
    citation_accuracy = len(supported) / len(checks) if checks else 0.0
    verified = bool(checks) and not unsupported
    if verified:
        status = CLAIM_SUPPORTED
    elif supported:
        status = CLAIM_PARTIALLY_SUPPORTED
    else:
        status = CLAIM_UNSUPPORTED

    return VerificationReport(
        claims=checks,
        citation_accuracy=round(citation_accuracy, 4),
        supported_claims=len(supported),
        unsupported_claims=unsupported[:10],
        uncited_claims=uncited,
        verified=verified,
        status=status,
        wrong_entity_claims=[
            check.sentence for check in checks if check.entity_check == "mismatch"
        ][:10],
    )
