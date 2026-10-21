"""Reference annotations for claims in DocuMind's actual benchmark answers, v1.

Purpose: close the gap left by ``claim_verification_v1`` (synthetic claims) by
annotating the claims the production generator actually emitted for the frozen
182-question benchmark, and judging both verifiers on those claims.

Scope and provenance
--------------------
* Every claim here was emitted by the production generative path
  (``generation.service.answer_generatively``) on an *answerable* row of
  ``phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl``.  The claim set is
  the union of the claims in the two recorded 10-mark runs:
  ``generation_benchmark_2026-10-17_fmt10`` (lexical, the production default) and
  ``generation_benchmark_2026-10-17_fmt10_relations_r5`` (the opt-in candidate).
  A claim present in only one run is marked as such in ``produced_by``.
* The evidence for a claim is the benchmark row's own ``context`` — the same
  single evidence block the generator and both verifiers saw.  Retrieval is not
  part of this measurement.
* 104 claims over 86 questions.  29 of them are **not claims**: table headers or
  rows rendered as prose, headings, or bare role/unit tokens.  They are retained
  and labelled ``NOT_A_CLAIM`` instead of being silently dropped, because their
  presence in answers is itself a generation-quality finding.  They are excluded
  from claim-level support metrics and reported separately.
* Annotations were produced by a single annotator (the coding agent) following
  the protocol below, then re-checked against the evidence.  There is no
  independent second human annotator, so these labels are a **reference set, not
  adjudicated ground truth**.  ``uncertainty`` marks the cases where a second
  annotator could reasonably disagree.

Annotation protocol (frozen before the verifiers were compared)
---------------------------------------------------------------
1. Judge the claim against the supplied row context only; outside knowledge never
   makes a claim SUPPORTED.
2. A value-only answer (e.g. ``$2.1 billion``) is read as
   ``<question attribute> = <value>``; the question supplies the attribute.  This
   is the same convention the generation benchmark and the synthetic claim set use.
3. ``SUPPORTED``: the context asserts the claim, allowing paraphrase and
   elliptical extraction.
4. ``CONTRADICTED``: the context asserts a different specific value for the same
   entity/attribute (different number, unit, role, polarity or comparison order).
   A value that merely appears under a different column is contradicted only when
   the context also states a different value for the asked attribute (`mean 4.2`
   makes `0.0` as the mean a contradiction); a missing fact is never contradicted.
5. ``INSUFFICIENT_EVIDENCE``: the context neither asserts nor contradicts the
   claim.  A value that appears only under a *different* attribute falls here when
   the context does not state a competing value for the asked attribute (the unit
   `m/s` offered as the asked variable).
6. ``PARTIALLY_SUPPORTED``: a compound claim whose elements are individually
   checkable and at least one is wrong.  It counts as *not fully supported* for
   support metrics and is also reported separately.
7. ``NOT_A_CLAIM``: no proposition (header, render, heading, bare token).  Excluded
   from support/contradiction metrics; acceptance of these by a verifier is
   reported as a separate quality signal, not as a truth error.
8. ``answers_question`` records whether the claim supplies the answer the gold
   span encodes.  It is orthogonal to truth: a supported claim can still fail to
   answer the question (e.g. the 2005 headcount instead of the 2010 one).
9. Ambiguity is recorded in ``uncertainty`` (``none``/``low``/``moderate``) with a
   rationale; it is never hidden by forcing a label.

Frozen-artifact rule: this file is versioned.  Do not edit labels in place to make
a verifier look better; create ``answer_claims_v2`` instead.

Extraction: this set was annotated against the pre-fix splitter, so its module
exposes ``split_claims`` from :mod:`evaluation.datasets.legacy_split` (a frozen
copy) rather than the production splitter.  That keeps the v1 report reproducible
after the abbreviation fix; current behavior is measured on ``answer_claims_v2``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from evaluation.datasets.legacy_split import split_claims  # frozen v1 extraction

DATASET_VERSION = "answer_claims_v1"
EXTRACTION = "evaluation.datasets.legacy_split.split_claims (pre-fix, frozen)"

DATASET_PATH = Path(__file__).with_name("answer_claims_v1.jsonl")

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
PARTIAL = "PARTIALLY_SUPPORTED"
NOT_A_CLAIM = "NOT_A_CLAIM"

LABELS = (SUPPORTED, CONTRADICTED, INSUFFICIENT, PARTIAL, NOT_A_CLAIM)
PROPOSITIONAL_LABELS = (SUPPORTED, CONTRADICTED, INSUFFICIENT, PARTIAL)

CATEGORIES = {
    "value_only": "bare value/entity answered under the question's attribute",
    "value_list": "several row values without their column labels",
    "sentence": "a grammatical sentence",
    "compound": "several assertions joined in one sentence",
    "table_render": "table header/row echoed into the answer (non-claim)",
    "fragment": "bare column label, unit, role token, or short elliptical value",
    "heading": "section heading (non-claim)",
}

UNCERTAINTY_LEVELS = ("none", "low", "moderate")


@dataclass(frozen=True)
class AnswerClaim:
    claim_id: str
    example_id: str
    question_kind: str
    claim: str
    label: str
    category: str
    answers_question: bool | None
    uncertainty: str
    produced_by: tuple[str, ...]
    annotator: str
    annotation_version: str
    rationale: str

    @property
    def is_propositional(self) -> bool:
        return self.label != NOT_A_CLAIM

    @property
    def fully_supported(self) -> bool:
        return self.label == SUPPORTED


def load(path: Path | None = None) -> list[AnswerClaim]:
    """Read the frozen JSONL.  Raises on malformed or inconsistent records."""
    source = path or DATASET_PATH
    claims: list[AnswerClaim] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            try:
                claim = AnswerClaim(
                    claim_id=raw["claim_id"],
                    example_id=raw["example_id"],
                    question_kind=raw["question_kind"],
                    claim=raw["claim"],
                    label=raw["label"],
                    category=raw["category"],
                    answers_question=raw["answers_question"],
                    uncertainty=raw["uncertainty"],
                    produced_by=tuple(raw["produced_by"]),
                    annotator=raw["annotator"],
                    annotation_version=raw["annotation_version"],
                    rationale=raw["rationale"],
                )
            except KeyError as exc:  # pragma: no cover - corrupt frozen data
                raise ValueError(f"{source}:{line_number} missing field {exc}") from exc
            _validate(claim, f"{source}:{line_number}")
            claims.append(claim)
    return claims


def _validate(claim: AnswerClaim, where: str) -> None:
    if claim.label not in LABELS:
        raise ValueError(f"{where}: unknown label {claim.label!r}")
    if claim.category not in CATEGORIES:
        raise ValueError(f"{where}: unknown category {claim.category!r}")
    if claim.uncertainty not in UNCERTAINTY_LEVELS:
        raise ValueError(f"{where}: unknown uncertainty {claim.uncertainty!r}")
    if claim.label == NOT_A_CLAIM and claim.answers_question is not None:
        raise ValueError(f"{where}: a non-claim cannot answer the question")
    if claim.label != NOT_A_CLAIM and claim.answers_question is None:
        raise ValueError(f"{where}: a claim must record whether it answers the question")


def statistics(claims: list[AnswerClaim] | None = None) -> dict:
    """Counts used in reports; no hidden filtering."""
    items = claims if claims is not None else load()
    labels: dict[str, int] = {}
    categories: dict[str, int] = {}
    uncertainty: dict[str, int] = {}
    for claim in items:
        labels[claim.label] = labels.get(claim.label, 0) + 1
        categories[claim.category] = categories.get(claim.category, 0) + 1
        uncertainty[claim.uncertainty] = uncertainty.get(claim.uncertainty, 0) + 1
    produced = {"lexical_only": 0, "relations_only": 0, "both": 0}
    for claim in items:
        modes = set(claim.produced_by)
        if modes == {"lexical", "relations"}:
            produced["both"] += 1
        elif modes == {"lexical"}:
            produced["lexical_only"] += 1
        elif modes == {"relations"}:
            produced["relations_only"] += 1
    propositional = [claim for claim in items if claim.is_propositional]
    return {
        "total": len(items),
        "examples": len({claim.example_id for claim in items}),
        "propositional": len(propositional),
        "non_claims": len(items) - len(propositional),
        "labels": labels,
        "categories": categories,
        "uncertainty": uncertainty,
        "produced_by": produced,
        "ambiguous_examples": sum(1 for claim in items if claim.uncertainty != "none"),
    }
