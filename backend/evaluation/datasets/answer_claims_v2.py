"""Reference annotations for claims in DocuMind's actual benchmark answers, v2.

Same schema, evidence and annotation protocol as ``answer_claims_v1``.  The
difference is the **claim extraction**: v2 re-extracts the claims from the same
two recorded 10-mark runs with the corrected production splitter
(``generation.planning.split_claims``, abbreviation fix of 2026-10-18).  v1 was
annotated against the old splitter and is preserved byte-for-byte, together with
its frozen extraction (``evaluation.datasets.legacy_split``), so its report stays
reproducible.

Population change (one answer, both recorded runs)
---------------------------------------------------
``li_ab55f3c4`` ("Which executive is the CEO?"), recorded answer ``Dr. Sarah
Chen``:

===========  ===========================================  =========================
v1           ``Dr.`` (NOT_A_CLAIM) + ``Sarah Chen`` (SUPPORTED)  2 claims
v2           ``Dr. Sarah Chen`` (SUPPORTED)                       1 claim
===========  ===========================================  =========================

The merged claim is re-annotated, not copied: the question supplies the CEO slot,
the evidence assigns it to Dr. Sarah Chen, so the merged text is SUPPORTED,
``value_only``, and answers the question.  All other 102 records are carried over
unchanged (labels, categories, uncertainty and rationales untouched).

Totals: 103 claims over 86 questions — 75 propositional (66 SUPPORTED, 5
CONTRADICTED, 2 INSUFFICIENT_EVIDENCE, 2 PARTIALLY_SUPPORTED) and 28 non-claims.

Frozen-artifact rule: this file is versioned.  Do not edit labels in place to make
a verifier look better; create ``answer_claims_v3`` instead.
"""

from __future__ import annotations

from pathlib import Path

from evaluation.datasets import answer_claims_v1 as _v1

#: The production extractor, not a frozen copy: v2 describes current behavior.
from generation.planning import split_claims  # noqa: F401  (re-exported)

DATASET_VERSION = "answer_claims_v2"
EXTRACTION = "generation.planning.split_claims (abbreviation fix 2026-10-18)"
SUPERSEDES = "answer_claims_v1"
DATASET_PATH = Path(__file__).with_name("answer_claims_v2.jsonl")

#: Explicit v1 → v2 record mapping.  ``removed`` records exist only in v1,
#: ``added`` only in v2; every other v1 ``claim_id`` is unchanged in v2.
CHANGES = {
    "example_id": "li_ab55f3c4",
    "reason": "splitter no longer treats 'Dr.' as a sentence end",
    "removed": [
        {
            "claim_id": "ac_0344c2a5d5",
            "claim": "Dr.",
            "label": _v1.NOT_A_CLAIM,
            "category": "fragment",
        },
        {
            "claim_id": "ac_17daf46833",
            "claim": "Sarah Chen",
            "label": _v1.SUPPORTED,
            "category": "value_only",
        },
    ],
    "added": [
        {
            "claim_id": "ac_c411173a36",
            "claim": "Dr. Sarah Chen",
            "label": _v1.SUPPORTED,
            "category": "value_only",
            "supersedes": ["ac_0344c2a5d5", "ac_17daf46833"],
        }
    ],
}

# Re-export the schema and constants so callers can treat datasets uniformly.
AnswerClaim = _v1.AnswerClaim
SUPPORTED = _v1.SUPPORTED
CONTRADICTED = _v1.CONTRADICTED
INSUFFICIENT = _v1.INSUFFICIENT
PARTIAL = _v1.PARTIAL
NOT_A_CLAIM = _v1.NOT_A_CLAIM
LABELS = _v1.LABELS
PROPOSITIONAL_LABELS = _v1.PROPOSITIONAL_LABELS
CATEGORIES = _v1.CATEGORIES
UNCERTAINTY_LEVELS = _v1.UNCERTAINTY_LEVELS


def load(path: Path | None = None) -> list[AnswerClaim]:
    """Read the frozen v2 JSONL using the v1 schema and validation."""
    return _v1.load(path or DATASET_PATH)


def statistics(claims: list[AnswerClaim] | None = None) -> dict:
    """Counts used in reports; no hidden filtering."""
    return _v1.statistics(claims if claims is not None else load())
