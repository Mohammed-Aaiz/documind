"""Relation-aware claim verifier (deterministic; no generative model).

**Off by default.**  ``generation.verification`` remains the verifier the API uses
unless ``DOCUMIND_VERIFIER=relations`` is set.  This module is the candidate measured
on the claim dataset and, under that setting, on the frozen QA benchmark.

An embedding-similarity fallback is retained for paraphrase only: it fires when the
head term is already present, the claim states no value, and the cosine similarity
clears 0.80.  Two guards came out of the claim evaluation: a value-bearing claim
("kept for the warranty period of five years", cosine 0.87 against "stored in the
maintenance log for five years") is never accepted by similarity, and a universal
claim ("always more accurate") needs universal evidence.  An earlier free-standing
similarity rule (threshold 0.70-0.90, no gate) changed no verdict at all on the
dataset, so similarity here is a trigger, never a verdict.

Design principle: **similarity is never proof of support.**

Per (claim, sentence):

1. Contradiction first, because accepting a denied claim is the dangerous error:
   * a value conflict for the claim's own subject (different number, or same number
     with a different unit) when the sentence covers ≥75 % of the claim's salient
     terms;
   * a reversed relation in a ``ROLE: name`` list (``Elena Vasquez is the CFO``);
   * an "X and Y take the same …" claim against a sentence that states two
     different values;
   * a negation asymmetry where, ignoring negation, the two sentences are nearly
     identical (≥75 % overlap) — not merely similar wording;
   * a comparative pointing at a different subject (``manual is cheaper`` vs
     ``automated is cheaper``), considering every comparison in both sentences.
2. Support:
   * numbers and units agree and the sentence covers the claim's subject; or
   * lexical overlap ≥60 % (the classic rule); or
   * for a claim with no value, cosine similarity ≥0.80 with the head term present;
   in all cases the claim's own head term must occur in the sentence.
3. Otherwise neutral.

Claims joined by "and"/"but" are split and verified clause by clause, so a claim
whose parts are supported by different passages is not rejected for that reason.
A capitalised term in the claim that appears nowhere in the evidence (``TensorFlow``)
downgrades a would-be SUPPORTED verdict to INSUFFICIENT_EVIDENCE: resemblance does
not establish an unmentioned entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from generation.types import EvidenceBlock
from generation.verification import (
    _STOPWORDS,
    _numbers,
    _stem,
    content_tokens,
    split_sentences,
    strip_citations,
)

LABEL_SUPPORTED = "SUPPORTED"
LABEL_CONTRADICTED = "CONTRADICTED"
LABEL_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

#: Classic lexical support rule (unchanged from production).
LEXICAL_SUPPORT_RATIO = 0.60


#: Share of the claim's salient terms a sentence must contain to be treated as
#: talking about the same subject.
SUBJECT_RATIO = 0.60

#: Stricter share required before a numeric disagreement is called a contradiction.
CONTRADICTION_SUBJECT_RATIO = 0.75

#: Overlap (with negation words removed) required to call a negation asymmetry a
#: contradiction rather than a paraphrase.
NEGATION_CONTRAST_RATIO = 0.75

_QUANTIFIERS = frozenset({"every", "each", "per", "all", "any", "some"})

_NEGATIONS = frozenset(
    "not no never cannot can't doesn't don't isn't aren't wasn't weren't without nor none".split()
)

_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40",
    "fifty": "50", "sixty": "60", "ninety": "90", "hundred": "100",
}

_UNITS = (
    "days", "weeks", "months", "years", "hours", "minutes", "seconds",
    "volts", "amps", "watts", "million", "billion", "thousand", "percent", "%",
)

_COMPARATIVES = ("cheaper", "faster", "slower", "more accurate", "less accurate", "more expensive")

#: Intensifiers are not subject modifiers: in "manual calibration is always more
#: accurate", the subject is (manual, calibration), not (always, calibration).
_INTENSIFIERS = frozenset(
    "always never often sometimes usually typically generally only especially "
    "necessarily still even also all both roughly about approximately nearly "
    "almost quite very just".split()
)

#: Absolute universal quantifiers.  A universal claim ("always") is not supported by
#: a passage that states the same relation only for a narrower case.  Plain negation
#: ("cannot") is deliberately not listed: it is an ordinary negated fact, not a
#: universal claim, and treating it as one rejected the "cannot be dispatched" →
#: "blocks dispatch" paraphrase.
_ABSOLUTE_UNIVERSAL = ("always", "invariably", "in every case", "in all cases")

#: Causal connectives: a causal claim is not supported by evidence that only
#: reports an association.
_CAUSAL = (
    "cause", "causes", "caused", "causing", "leads to", "lead to", "results in",
    "result in", "prevents", "prevent", "because", "due to", "as a result",
)

#: Word characters exclude the trailing period: an earlier version captured
#: "calibration." and "million." as tokens, which silently lowered every overlap
#: ratio (found on the held-out split, 2026-10-17).
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9%/_-]*")
_ROLE_PAIR_RE = re.compile(r"([A-Z]{2,6})\s*:\s*([A-Z][\w]+(?:\s+[A-Z][\w]+)*)")
_CLAIM_ROLE_RE = re.compile(
    r"\b([A-Z][\w]+(?:\s+[A-Z][\w]+)*)\s+is\s+(?:the\s+)?([A-Z]{2,6})\b"
)
_SAME_RE = re.compile(r"\bsame\b", re.IGNORECASE)


def _normalise(text: str) -> str:
    lowered = " ".join(text.lower().split())
    for word, digits in _NUMBER_WORDS.items():
        lowered = re.sub(rf"\b{word}\b", digits, lowered)
    return lowered


def _units_of(text: str) -> set[str]:
    lowered = _normalise(text)
    return {unit for unit in _UNITS if re.search(rf"(?<![a-z]){re.escape(unit)}(?![a-z])", lowered)}


def _negated(text: str) -> bool:
    return bool(set(_WORD_RE.findall(_normalise(text))) & _NEGATIONS)


def _tokens(text: str) -> list[str]:
    """Content tokens using this module's tokenizer (no trailing period)."""
    return [
        token
        for token in _WORD_RE.findall(_normalise(text))
        if token not in _STOPWORDS
    ]


def _content(text: str) -> set[str]:
    return {_stem(token) for token in _tokens(text)}


def _overlap(claim: str, sentence: str) -> float:
    claim_tokens = _tokens(strip_citations(claim))
    if not claim_tokens:
        return 0.0
    sentence_tokens = _content(sentence)
    return sum(1 for token in claim_tokens if _stem(token) in sentence_tokens) / len(claim_tokens)


def _salient(claim: str) -> list[str]:
    """Content terms of the claim, excluding numbers, units and quantifiers.

    Quantifiers are excluded because they are not entities: in "every 30 days" the
    only word left is "every", which made the claim look like it had a subject and
    let an unrelated 90-day passage contradict it.
    """
    units = _units_of(claim)
    out = []
    for token in _tokens(strip_citations(claim)):
        if token.isdigit() or token in units or token in _QUANTIFIERS:
            continue
        out.append(token)
    return out


def _salient_ratio(claim: str, sentence: str) -> float:
    salient = _salient(claim)
    if not salient:
        return 0.0
    tokens = _content(sentence)
    return sum(1 for term in salient if _stem(term) in tokens) / len(salient)


def _head_present(claim: str, sentence: str) -> bool:
    """The claim's own head term must occur in the sentence.

    Without this, "the sensor array requires calibration every 30 days" is accepted
    by a sentence about the *lidar* array: the remaining words overlap and the value
    matches.  The head term is the first salient word of the claim.
    """
    salient = _salient(claim)
    if not salient:
        return True
    return _stem(salient[0]) in _content(sentence)


def _number_match(claim: str, sentence: str) -> bool:
    claim_numbers = _numbers(_normalise(claim))
    if not claim_numbers:
        return True
    return claim_numbers <= _numbers(_normalise(sentence))


def _unit_match(claim: str, sentence: str) -> bool:
    claim_units = _units_of(claim)
    if not claim_units:
        return True
    return claim_units <= _units_of(sentence)


def _has_causal_marker(text: str) -> bool:
    """Whether ``text`` itself states a causal relation (word-boundary match)."""
    lowered = _normalise(text)
    return any(
        re.search(rf"(?<![a-z]){re.escape(marker)}(?![a-z])", lowered)
        for marker in _CAUSAL
    )


def _is_universal(text: str) -> bool:
    lowered = _normalise(text)
    return any(
        re.search(rf"(?<![a-z]){re.escape(marker)}(?![a-z])", lowered)
        for marker in _ABSOLUTE_UNIVERSAL
    )


def _comparative_pairs(text: str) -> list[tuple[set[str], str]]:
    """Every ``(subject, comparative)`` pair in ``text``, in reading order.

    Only content words count: "manual calibration is cheaper" and "automated
    calibration is cheaper" differ in their subject (manual vs automated), not in
    the copula.  A sentence may state several comparisons ("manual is more accurate
    … while automated is cheaper"), so all of them are returned; taking only the
    first made a reversed comparison depend on which clause came first.
    """
    lowered = _normalise(text)
    found: list[tuple[int, set[str], str]] = []
    for comparative in _COMPARATIVES:
        start = lowered.find(comparative)
        while start != -1:
            words = [
                w for w in _tokens(lowered[:start]) if w not in _NEGATIONS and w not in _INTENSIFIERS
            ]
            if words:
                found.append((start, set(words[-2:]), comparative))
            start = lowered.find(comparative, start + len(comparative))
    found.sort(key=lambda item: item[0])
    return [(subject, comparative) for _, subject, comparative in found]


def _distinct_subject(claim_subject: set[str], sentence_subject: set[str]) -> bool:
    """The sentence compares a *different* subject than the claim does.

    "automated calibration is cheaper" contradicts "manual calibration is cheaper":
    the subjects share the head (calibration) but each carries a distinguishing
    modifier the other lacks.  A strict subset is not a conflict — "calibration is
    cheaper" is supported by "automated calibration is cheaper".
    """
    if not claim_subject or not sentence_subject:
        return False
    if not (claim_subject & sentence_subject):
        return True
    return bool(claim_subject - sentence_subject) and bool(sentence_subject - claim_subject)


def _comparative_subject(text: str) -> tuple[set[str], str] | None:
    """Subject and comparative of the first comparative clause in ``text``."""
    pairs = _comparative_pairs(text)
    return pairs[0] if pairs else None


def _role_conflict(claim: str, sentence: str) -> bool:
    """``X is the ROLE`` contradicts a ``ROLE: Y`` list where Y is not X."""
    match = _CLAIM_ROLE_RE.search(claim)
    if not match:
        return False
    person = " ".join(match.group(1).lower().split())
    role = match.group(2)
    pairs = [(r, " ".join(n.lower().split())) for r, n in _ROLE_PAIR_RE.findall(sentence)]
    for pair_role, pair_name in pairs:
        if pair_role != role:
            continue
        return pair_name not in person and person not in pair_name
    return False


def _unknown_capitalised(claim: str, evidence_text: str) -> bool:
    """A capitalised, non-initial term of the claim absent from all evidence."""
    words = re.findall(r"[A-Za-z][\w-]*", claim)
    evidence_lower = evidence_text.lower()
    for index, word in enumerate(words):
        if index == 0:
            continue  # sentence-initial capitalisation is not a proper noun
        if not word[0].isupper():
            continue
        if word.lower() in {"i"}:
            continue
        if word.lower() not in evidence_lower:
            return True
    return False


#: Similarity needed for the paraphrase fallback.  Measured on the claim dataset:
#: 0.80 accepts the "cannot be dispatched" → "blocks dispatch" paraphrase while
#: adding no false acceptance on either split (see the ablation in
#: ``evaluation/reports/claim_verification_2026-10-17``).
SEMANTIC_SUPPORT_THRESHOLD = 0.80


class _Similarity:
    """Lazy cosine similarity over the project's cached local embedder."""

    def __init__(self) -> None:
        self._model = None
        self._cache: dict[str, object] = {}

    def encode(self, text: str):
        if self._model is None:
            from embeddings.model import get_model

            self._model = get_model()
        if text not in self._cache:
            self._cache[text] = self._model.encode([text], normalize_embeddings=True)[0]
        return self._cache[text]

    def __call__(self, claim: str, sentence: str) -> float:
        import numpy as np

        return float(np.dot(self.encode(claim), self.encode(sentence)))


_SIMILARITY = _Similarity()


def semantic_similarity(claim: str, sentence: str) -> float:
    """Cosine similarity from the project's cached MiniLM embedder.

    Used only as a **fallback trigger** for phrase-level paraphrase; the support
    decision still requires the claim's head term and its numbers/units to be
    present in the sentence.
    """
    return _SIMILARITY(claim, sentence)


@dataclass
class ClaimVerdict:
    claim: str
    label: str
    supporting_blocks: list[int] = field(default_factory=list)
    contradicting_blocks: list[int] = field(default_factory=list)
    citation_ok: bool = True
    explanation: str = ""
    best_support_score: float = 0.0

    @property
    def supported(self) -> bool:
        return self.label == LABEL_SUPPORTED


def _sentence_relation(claim: str, sentence: str, question: str | None = None) -> str:
    """``"supports"``, ``"contradicts"`` or ``"neutral"`` for one pair."""
    overlap = _overlap(claim, sentence)
    salient_ratio = _salient_ratio(claim, sentence)
    same_subject = salient_ratio >= SUBJECT_RATIO
    claim_numbers = _numbers(_normalise(claim))
    numbers_ok = _number_match(claim, sentence)
    units_ok = _unit_match(claim, sentence)

    # --- contradictions ------------------------------------------------------
    if claim_numbers and salient_ratio >= CONTRADICTION_SUBJECT_RATIO:
        if not numbers_ok or not units_ok:
            return "contradicts"
    if _role_conflict(claim, sentence):
        return "contradicts"
    if _SAME_RE.search(claim) and len(_numbers(_normalise(sentence))) >= 2:
        return "contradicts"
    if _negated(claim) != _negated(sentence) and not claim_numbers and not _is_table_render(sentence):
        claim_plain = " ".join(w for w in _WORD_RE.findall(_normalise(claim)) if w not in _NEGATIONS)
        sentence_plain = " ".join(
            w for w in _WORD_RE.findall(_normalise(sentence)) if w not in _NEGATIONS
        )
        if _overlap(claim_plain, sentence_plain) >= NEGATION_CONTRAST_RATIO:
            return "contradicts"

    for clause_subject, clause_comparative in _comparative_pairs(claim):
        for evidence_subject, evidence_comparative in _comparative_pairs(sentence):
            if clause_comparative != evidence_comparative:
                continue
            if _distinct_subject(clause_subject, evidence_subject):
                return "contradicts"

    # --- causal claims need causal evidence ----------------------------------
    # Co-occurrence is not causation: a passage that reports an association (or only
    # that both events happened) cannot support "X causes Y", however many words the
    # two share.  The evidence must itself state the causal relation.
    if _has_causal_marker(claim) and not _has_causal_marker(sentence):
        return "neutral"

    # --- an absolute claim needs absolute evidence ----------------------------
    if _is_universal(claim) and not _is_universal(sentence):
        return "neutral"

    # --- question-to-attribute binding ---------------------------------------
    # A value can appear in the passage and still be the wrong attribute for the
    # question (a per-share fragment offered as the reported total).  This check is
    # conservative: it only fires on the readable prose structures below and only
    # for value-only claims; anything else keeps the previous behaviour.  It emits a
    # contradiction only because these structures *state a competing value for the
    # asked attribute* — a value merely sitting under another column is not a
    # contradiction (see ``_table_attribute_binding``).
    if _prose_attribute_binding(claim, sentence, question) == "contradicts":
        return "contradicts"

    # --- support -------------------------------------------------------------
    head_ok = _head_present(claim, sentence)
    # Similarity is a paraphrase trigger only.  It is not consulted for a claim that
    # states a value: "records are kept for the warranty period of five years" is
    # cosine 0.87 against "records are stored in the maintenance log for five
    # years", yet the claim's attachment (warranty period) appears nowhere.  Values
    # need their own branch, never a similarity bridge.
    if head_ok and not claim_numbers and overlap >= 0.25:
        if semantic_similarity(claim, sentence) >= SEMANTIC_SUPPORT_THRESHOLD:
            return "supports"
    if claim_numbers and numbers_ok and units_ok:
        if salient_ratio >= SUBJECT_RATIO and head_ok:
            return "supports"
        # Single-value answers: "every 30 days" has no content term to anchor it, so
        # the classic subject test can never pass.  Require the question's entity.
        if not _salient(claim) and _claimed_entity_ok(claim, sentence, question):
            return "supports"
    # Word overlap alone must not outvote a value: "every 90 days" shares two of its
    # three tokens with "every 30 days" and would otherwise be accepted.
    if overlap >= LEXICAL_SUPPORT_RATIO and head_ok and numbers_ok and units_ok:
        return "supports"
    return "neutral"


def _is_table_render(text: str) -> bool:
    """A pipe-delimited table render rather than a prose sentence.

    Table cells are values, so a cell such as ``No`` (auth not required) is not the
    negation of a prose claim.  Reading it as one turned ``/auth/token, Obtain
    access token.`` into a false contradiction against the very row that supports it.
    """
    return sum(1 for line in text.splitlines() if "|" in line) >= 1 and text.count("|") >= 2


_QUESTION_GENERIC = frozenset(
    "what which who whom whose when where why how according document table say says "
    "reported value amount much many does do did is was were are be been being the a an "
    "of for to in on at by with from about as that this these those it its".split()
)

_MONETARY_QUESTIONS = frozenset(
    {"monetary", "revenue", "income", "amount", "total", "sales", "profit", "price", "fee"}
)

_PERCENTAGE_QUESTIONS = frozenset({"percentage", "percent", "rate"})

_CHANGE_QUESTIONS = frozenset(
    {"increase", "decrease", "change", "growth", "grew", "rise", "fall", "decline"}
)

#: Question wording that asks for a value rather than a label.  When present, the
#: asked column must be a value column: "how much is the payment schedule of Q2
#: 2025?" shares more words with the row-key header (``Payment Schedule``) than with
#: ``Amount (USD)``, but the amount is what the question asks for.
_VALUE_CUES = frozenset(
    {
        "much", "many", "amount", "value", "values", "total", "cost", "price",
        "number", "count", "percent", "percentage", "rate", "min", "max", "mean",
        "median", "score", "revenue",
    }
)

_VALUE_COLUMN_TERMS = frozenset(
    {
        "amount", "value", "total", "cost", "price", "revenue", "income", "salary",
        "min", "max", "mean", "median", "percent", "percentage", "rate", "count",
        "number", "unit", "usd", "score", "qty", "quantity", "growth",
    }
)


def _table_rows(evidence_text: str) -> tuple[list[str], list[list[str]]] | None:
    """The first pipe-delimited header and its data rows, or ``None``.

    Only the benchmark's table rendering is parsed; this is not a general table
    reader and it deliberately refuses ragged rows.
    """
    lines = [line.strip() for line in evidence_text.splitlines() if line.strip() and "|" in line]
    if len(lines) < 2:
        return None
    header = [cell.strip() for cell in lines[0].split("|")]
    rows = [
        [cell.strip() for cell in line.split("|")]
        for line in lines[1:]
    ]
    rows = [row for row in rows if len(row) == len(header)]
    if not header or not rows:
        return None
    return header, rows


def _looks_like_unit(token: str) -> bool:
    """A short unit/symbol token (``m/s``, ``km``, ``hPa``, ``5m``).

    ``_UNITS`` is a curated word list; tables also use compact symbols.  This is
    deliberately narrow so ordinary content words are never treated as values.
    """
    return (
        token in {"km", "hpa", "usd", "req", "min", "kg", "cm", "mm", "mb", "gb", "ms", "m"}
        or "/" in token
        or "%" in token
        or bool(re.fullmatch(r"\d*[a-z]{1,3}", token))
    )


def _value_only(claim: str) -> bool:
    """A claim that carries a value but no entity of its own.

    Extends ``_salient`` to compact table units (``m/s``, ``hPa``, ``$412.5M``),
    while still refusing entity-bearing phrases such as ``200 employees`` or
    ``$178.0M + 650 Revenue exceeds $150M``.
    """
    units = _units_of(claim)
    content = [
        token
        for token in _tokens(strip_citations(claim))
        if not token.isdigit() and token not in units and token not in _QUANTIFIERS
    ]
    return all(_looks_like_unit(token) for token in content)


def _claim_in_cell(claim: str, cell: str) -> bool:
    """Whether the claim's value (or bare token) occurs in a table cell."""
    numbers = _numbers(_normalise(claim))
    if numbers:
        return numbers <= _numbers(_normalise(cell))
    text = _normalise(strip_citations(claim)).strip(" .")
    return bool(text) and text in _normalise(cell)


def _asked_column(
    header: list[str], question_terms: set[str], value_question: bool
) -> int | None:
    """The header column the question asks for, or ``None`` when undecidable.

    Column choice is overlap between header terms and the question.  A value
    question ("how much is the payment schedule of Q2 2025?") also matches the
    row-key header (``Payment Schedule``), so a single value-typed column wins in
    that case; ties and zero matches return ``None`` and no binding decision is made.
    """
    if value_question:
        value_columns = [
            index
            for index, cell in enumerate(header)
            if _content(cell) & _VALUE_COLUMN_TERMS
        ]
        if len(value_columns) == 1:
            return value_columns[0]
    scores = [len(_content(cell) & question_terms) for cell in header]
    best = max(scores)
    if best == 0 or scores.count(best) > 1:
        return None
    return scores.index(best)


def _table_attribute_binding(
    claim: str, evidence_text: str, question: str | None
) -> str | None:
    """Bind a value-only claim to the table column the question asks for.

    Returns:

    * ``"contradicts"`` when the asked column states a *different numeric value* for
      the asked attribute (``0.0`` offered as the mean of a column that states
      ``4.2``);
    * ``"misbound"`` when the claim's value sits in another column without the asked
      attribute stating a competing value (a unit offered as the asked variable); the
      caller reports insufficient evidence, not a contradiction;
    * ``None`` when the table cannot decide (no table, no column match, ambiguous
      row, value absent) — the ordinary support rules then apply.
    """
    if not question or not _value_only(claim):
        return None
    table = _table_rows(evidence_text)
    if not table:
        return None
    header, rows = table
    question_terms = _content(question) - _QUESTION_GENERIC
    if not question_terms:
        return None
    value_question = bool(_content(question) & _VALUE_CUES)
    column = _asked_column(header, question_terms, value_question)
    if column is None:
        return None

    row_scores = [len(_content(" ".join(row)) & question_terms) for row in rows]
    best_row_score = max(row_scores)
    if best_row_score:
        relevant = [row for row, score in zip(rows, row_scores) if score == best_row_score]
    elif len(rows) == 1:
        relevant = rows
    else:
        return None

    claim_numbers = _numbers(_normalise(claim))
    verdicts: list[str] = []
    for row in relevant:
        if column >= len(row):
            continue
        if _claim_in_cell(claim, row[column]):
            verdicts.append("aligned")
        elif any(
            index != column and _claim_in_cell(claim, cell)
            for index, cell in enumerate(row)
        ):
            asked_numbers = _numbers(_normalise(row[column]))
            if claim_numbers and asked_numbers and not (asked_numbers & claim_numbers):
                verdicts.append("contradicts")
            else:
                verdicts.append("misbound")
    if "aligned" in verdicts:
        return None
    if "contradicts" in verdicts:
        return "contradicts"
    if "misbound" in verdicts:
        return "misbound"
    return None


def _prose_attribute_binding(
    claim: str, sentence: str, question: str | None
) -> str | None:
    """Bind a value-only claim to the attribute the question asks for (prose).

    Only two readable structures are handled, both of which appeared in the
    actual-answer evaluation:

    * a derivative amount after ``or`` (``... $142.6 million, or $3``): the value
      after ``or`` is a per-share/derivative fragment, not the reported total;
    * a percentage-change sentence: ``1 percent from 20.3 percent`` asks for the
      base value, and ``4 percent ... 4.2 percent increase`` asks for the value
      attached to the change.

    Anything else returns ``None`` and the previous support rules apply.
    """
    if not question or not _value_only(claim):
        return None
    claim_numbers = {
        float(number.replace(",", ""))
        for number in _numbers(_normalise(claim))
        if number.replace(",", "").replace(".", "", 1).isdigit()
    }
    if not claim_numbers:
        return None
    question_terms = _content(question)

    if (question_terms & _MONETARY_QUESTIONS) and not (
        question_terms & {"share", "eps", "per"}
    ):
        amounts = [
            (match.start(), float(match.group(1).replace(",", "")))
            for match in re.finditer(r"\$\s*([\d,]+(?:\.\d+)?)", sentence)
        ]
        or_positions = [match.start() for match in re.finditer(r"\bor\b", sentence.lower())]
        for position in or_positions:
            before = [value for start, value in amounts if start < position]
            after = [(start, value) for start, value in amounts if start > position]
            if after and before and max(before) > after[0][1] and claim_numbers == {after[0][1]}:
                return "contradicts"

    if (question_terms & _PERCENTAGE_QUESTIONS) and not (
        question_terms & _CHANGE_QUESTIONS
    ):
        percentages = [
            (match.start(), float(match.group(1)))
            for match in re.finditer(r"([\d.]+)\s*(?:percent|%)", sentence)
        ]
        available = {value for _, value in percentages}
        if len(percentages) >= 2 and claim_numbers <= available:
            change = re.search(
                r"([\d.]+)\s*(?:percent|%)\s+from\s+([\d.]+)\s*(?:percent|%)",
                sentence,
            )
            if change:
                first, base = float(change.group(1)), float(change.group(2))
                if claim_numbers == {first} and first != base:
                    return "contradicts"
            cue = re.search(
                r"\b(increase|growth|grew|decrease|decline|rise|fall)\b", sentence
            )
            if cue:
                before_cue = [value for position, value in percentages if position < cue.start()]
                if before_cue:
                    metric = before_cue[-1]
                    if claim_numbers != {metric} and claim_numbers <= available:
                        return "contradicts"
    return None


def _claimed_entity_ok(claim: str, sentence: str, question: str | None) -> bool:
    """A value-only claim ("every 30 days", "200 users") needs its entity present.

    The claim carries no content term of its own, so matching the number alone would
    accept a bare table cell ("1") on any question.  The entity is taken from the
    question: at least half of its content terms must occur in the sentence.  Without
    a question a bare number is not attributable; a number with a unit is.
    """
    if not question or not question.strip():
        return bool(_units_of(claim))
    question_terms = _content(question)
    if not question_terms:
        return bool(_units_of(claim))
    shared = question_terms & _content(sentence)
    return len(shared) / len(question_terms) >= 0.50


def _split_clauses(claim: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s+(?:and|but)\s+", claim) if part.strip()]
    if len(parts) < 2:
        return []
    return [part for part in parts if len(content_tokens(part)) >= 2]


def verify_claim(
    claim: str,
    blocks: Sequence[EvidenceBlock],
    stated_citations: Sequence[int] = (),
    question: str | None = None,
) -> ClaimVerdict:
    """Verify one claim (recursively for clauses joined by "and"/"but")."""
    text = strip_citations(claim).strip()
    if not text or not blocks:
        return ClaimVerdict(
            claim=claim,
            label=LABEL_INSUFFICIENT,
            explanation="no claim text or no evidence",
            citation_ok=not stated_citations,
        )

    supporting: list[int] = []
    contradicting: list[int] = []
    misbound_note = ""
    best_score = 0.0
    contradiction_sentence = ""
    evidence_text = "\n".join(block.content for block in blocks)

    for block in blocks:
        binding = _table_attribute_binding(text, block.content, question)
        if binding == "contradicts":
            if block.index not in contradicting:
                contradicting.append(block.index)
            if not contradiction_sentence:
                contradiction_sentence = "the asked column states a different value"
            continue
        if binding == "misbound":
            if not misbound_note:
                misbound_note = (
                    "the value appears under a different attribute than the question asks"
                )
            continue
        for sentence in split_sentences(block.content):
            if not sentence.strip():
                continue
            relation = _sentence_relation(text, sentence, question=question)
            best_score = max(best_score, _overlap(text, sentence))
            if relation == "supports":
                if block.index not in supporting:
                    supporting.append(block.index)
            elif relation == "contradicts":
                if block.index not in contradicting:
                    contradicting.append(block.index)
                if not contradiction_sentence:
                    contradiction_sentence = sentence

    # A claim supported only in parts by separate passages: verify each clause.
    if not supporting and not contradicting:
        clauses = _split_clauses(text)
        if clauses:
            verdicts = [verify_claim(clause, blocks, question=question) for clause in clauses]
            labels = {verdict.label for verdict in verdicts}
            if labels == {LABEL_SUPPORTED}:
                merged = sorted({index for v in verdicts for index in v.supporting_blocks})
                return ClaimVerdict(
                    claim=claim,
                    label=LABEL_SUPPORTED,
                    supporting_blocks=merged,
                    citation_ok=not stated_citations or any(
                        index in merged for index in stated_citations
                    ),
                    explanation="each clause is supported by the evidence",
                    best_support_score=max(v.best_support_score for v in verdicts),
                )
            if LABEL_CONTRADICTED in labels:
                return ClaimVerdict(
                    claim=claim,
                    label=LABEL_CONTRADICTED,
                    supporting_blocks=sorted({i for v in verdicts for i in v.supporting_blocks}),
                    contradicting_blocks=sorted({i for v in verdicts for i in v.contradicting_blocks}),
                    citation_ok=True,
                    explanation="a clause of the claim is contradicted",
                )

    citation_ok = True
    if stated_citations:
        citation_ok = any(index in supporting for index in stated_citations)

    if contradicting and not supporting:
        label = LABEL_CONTRADICTED
        explanation = "evidence contradicts the claim: " + contradiction_sentence[:160]
    elif contradicting and supporting:
        label = LABEL_CONTRADICTED
        explanation = "evidence is conflicting; a contradicting passage exists"
    elif supporting:
        if _unknown_capitalised(claim, evidence_text):
            label = LABEL_INSUFFICIENT
            explanation = "the claim names a term that appears nowhere in the evidence"
        else:
            label = LABEL_SUPPORTED
            explanation = "claim is supported by the evidence"
    elif misbound_note:
        label = LABEL_INSUFFICIENT
        explanation = misbound_note
    else:
        label = LABEL_INSUFFICIENT
        explanation = "no passage asserts or contradicts the claim"

    return ClaimVerdict(
        claim=claim,
        label=label,
        supporting_blocks=sorted(supporting),
        contradicting_blocks=sorted(contradicting),
        citation_ok=citation_ok,
        explanation=explanation,
        best_support_score=round(best_score, 4),
    )


def verify_answer_claims(
    answer: str,
    blocks: Sequence[EvidenceBlock],
    question: str | None = None,
) -> list[ClaimVerdict]:
    """Split an answer into claims and verify each one.

    ``question`` is used only to attribute a value-only answer ("every 30 days") to a
    sentence that mentions the question's entity; it does not decide whether a
    supported claim actually answers the question.
    """
    from generation.planning import extract_citations, split_claims

    return [
        verify_claim(sentence, blocks, extract_citations(sentence), question=question)
        for sentence in split_claims(answer)
    ]
