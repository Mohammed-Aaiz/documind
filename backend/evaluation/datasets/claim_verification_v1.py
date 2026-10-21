"""Claim-verification evaluation set, v1 (2026-10-17).

Purpose: measure whether a verifier decides **claim support** correctly, separately
from answer accuracy.  The frozen 182-question QA benchmark stays untouched and is
never edited by this dataset.

Every example is a single claim plus the evidence blocks a retrieval step could have
supplied.  Labels are claim-level:

* ``SUPPORTED`` — the evidence asserts the claim (paraphrase allowed).
* ``CONTRADICTED`` — the evidence asserts something incompatible with the claim
  (different value for the same entity, reversed negation, reversed comparison).
* ``INSUFFICIENT_EVIDENCE`` — the evidence neither asserts nor contradicts it.

Contradiction is deliberately **not** merged with missing evidence: the product
needs to tell a user "the document says otherwise" apart from "the document does not
say".

Provenance and limitations (read before quoting any number):

* The examples are **synthetic**, written for this evaluation.  They are modelled on
  the kind of sentences the production corpus contains (maintenance manuals, API
  docs, finance tables) but they are not sampled from real user documents, so results
  are **not** a measurement of real-world verifier accuracy.
* The categories follow the failure taxonomy in the verifier mission (A–M).
* Some examples require arithmetic or world knowledge (e.g. "two hours" vs "twelve
  minutes", "once a month" vs "every 30 days").  Those are marked ``hard`` in the
  rationale and reported separately — a verifier is not required to solve them, but
  they must not be silently counted as easy wins.
* The ``dev`` split may be used to choose a threshold; ``test`` is held out and is
  reported once.  Do not tune on ``test``.

Annotation rules:

1. Judge the claim against the supplied evidence only.  Outside knowledge never
   makes a claim SUPPORTED.
2. A different number, unit, date, entity or negation for the same subject is
   CONTRADICTED, not merely unsupported.
3. A claim the evidence does not address at all is INSUFFICIENT_EVIDENCE.
4. Paraphrase is allowed: wording differences alone do not change the label.
5. If the evidence contains conflicting statements and the claim repeats one of them,
   the claim is CONTRADICTED by the other passage (``evidence_conflict`` is recorded).
"""

from __future__ import annotations

from dataclasses import dataclass, field

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

#: Failure-taxonomy codes (see the mission's Agent 1 list).
CATEGORIES = {
    "A": "correct paraphrase rejected (low lexical overlap)",
    "B": "unsupported claim accepted because of word overlap",
    "C": "correct numeric answer",
    "D": "incorrect numeric value / unit",
    "E": "correct entity",
    "F": "wrong entity",
    "G": "negation reversed",
    "H": "unsupported causal relationship",
    "I": "comparison",
    "J": "support requires more than one passage",
    "K": "citation points at a passage that does not support the claim",
    "M": "insufficient or contradictory evidence",
}


@dataclass(frozen=True)
class ClaimExample:
    example_id: str
    category: str
    split: str  # "dev" | "test"
    label: str
    evidence: tuple[str, ...]
    claim: str
    rationale: str
    hard: bool = False
    stated_citations: tuple[int, ...] = ()
    evidence_conflict: bool = False
    citation_correct: bool = True


def _e(example_id, category, split, label, evidence, claim, rationale, **kwargs) -> ClaimExample:
    if isinstance(evidence, str):
        evidence = (evidence,)
    return ClaimExample(
        example_id=example_id,
        category=category,
        split=split,
        label=label,
        evidence=tuple(evidence),
        claim=claim,
        rationale=rationale,
        **kwargs,
    )


EXAMPLES: tuple[ClaimExample, ...] = (
    # --- A: supported paraphrases with little word overlap -------------------
    _e("A01", "A", "dev", SUPPORTED,
       "Calibration is the process of comparing an instrument's reading against a reference standard and correcting the difference.",
       "Calibration compares instrument readings to a reference and corrects the deviation.",
       "Same process, different wording; 'deviation' is the difference being corrected."),
    _e("A02", "A", "dev", SUPPORTED,
       "A failed calibration check blocks the robot from dispatch until it is resolved.",
       "The robot cannot be dispatched while a calibration failure is unresolved.",
       "Paraphrase with a negated formulation."),
    _e("A03", "A", "test", SUPPORTED,
       "Manual calibration needs a technician and takes about two hours.",
       "A technician spends roughly two hours on manual calibration.",
       "Same fact, reordered."),
    _e("A04", "A", "test", SUPPORTED,
       "Lidar calibration uses the manufacturer reference target.",
       "The reference target supplied by the manufacturer is used for lidar calibration.",
       "Nominalisation, same content."),
    _e("A05", "A", "dev", SUPPORTED,
       "The robot is parked on a level pad and the reference target is mounted.",
       "Calibration begins by parking the robot on a level pad and mounting the reference target.",
       "Steps restated in sequence; 'begins' adds no unsupported fact."),
    _e("A06", "A", "test", SUPPORTED,
       "The lidar array requires calibration every 30 days.",
       "Lidar needs recalibrating once a month.",
       "'once a month' is 30 days; requires calendar knowledge.", hard=True),

    # --- B: false-by-overlap -------------------------------------------------
    _e("B01", "B", "dev", CONTRADICTED,
       "The sensor array is recalibrated every 90 days.",
       "The sensor array is recalibrated every 30 days.",
       "Same sentence, different value; overlap is high but the claim is false."),
    _e("B02", "B", "dev", CONTRADICTED,
       "The lidar array requires calibration every 30 days. The sensor array is recalibrated every 90 days.",
       "The sensor array requires calibration every 30 days.",
       "Correct number attached to the wrong array."),
    _e("B03", "B", "test", CONTRADICTED,
       "Repeated failures on the same axis indicate a worn bearing.",
       "Repeated failures on the same axis cause a worn bearing.",
       "Evidence states an indicator, the claim asserts causation; word overlap is near-total."),
    _e("B04", "B", "test", CONTRADICTED,
       "Calibration records are stored in the maintenance log for five years.",
       "Calibration records are kept for the warranty period of five years.",
       "'stored in the log' becomes 'kept for the warranty period' — an added term."),
    _e("B05", "B", "dev", CONTRADICTED,
       "The power rail operates at 12 volts.",
       "The power rail operates at 24 volts.",
       "Single-token difference, opposite fact."),

    # --- C: correct numeric --------------------------------------------------
    _e("C01", "C", "dev", SUPPORTED,
       "Maximum of 200 items per request.",
       "The maximum is 200 items per request.",
       "Exact numeric match."),
    _e("C02", "C", "dev", SUPPORTED,
       "Net income attributable to shareholders was $142.6 million.",
       "Net income was $142.6 million.",
       "Decimal value preserved."),
    _e("C03", "C", "test", SUPPORTED,
       "The company raised $185 million in the IPO.",
       "The IPO raised $185 million.",
       "Same value, reordered."),
    _e("C04", "C", "test", SUPPORTED,
       "Pagination uses a default page size of 50 items.",
       "The default page size is 50.",
       "Numeric match without the unit word."),
    _e("C05", "C", "dev", SUPPORTED,
       "Calibration records are retained for five years.",
       "Records are kept for 5 years.",
       "Number word vs digit; deterministic normalisation expected."),

    # --- D: incorrect numeric / unit ----------------------------------------
    _e("D01", "D", "dev", CONTRADICTED,
       "The lidar array requires calibration every 30 days.",
       "The lidar array requires calibration every 90 days.",
       "Different interval for the same entity."),
    _e("D02", "D", "dev", CONTRADICTED,
       "The lidar array requires calibration every 30 days.",
       "The lidar array requires calibration every 30 weeks.",
       "Same number, different unit."),
    _e("D03", "D", "test", CONTRADICTED,
       "Calibration records are retained for five years.",
       "Calibration records are retained for five months.",
       "Unit changed while the number stays."),
    _e("D04", "D", "test", CONTRADICTED,
       "Net income was $142.6 million.",
       "Net income was $142.6 billion.",
       "Magnitude changed."),
    _e("D05", "D", "dev", CONTRADICTED,
       "The power rail operates at 12 volts.",
       "The power rail operates at 12 amps.",
       "Unit changed; the number alone is not support."),

    # --- E: correct entity ---------------------------------------------------
    _e("E01", "E", "dev", SUPPORTED,
       "CTO: James Whitfield, CFO: Robert Tanaka, COO: Elena Vasquez.",
       "Robert Tanaka is the CFO.",
       "Correct role/entity pair."),
    _e("E02", "E", "dev", SUPPORTED,
       "The lidar array requires calibration every 30 days.",
       "The lidar array is calibrated every 30 days.",
       "Entity and value correct."),
    _e("E03", "E", "test", SUPPORTED,
       "The docking station performs automated calibration.",
       "Automated calibration is performed by the docking station.",
       "Passive/active restatement of the same relation."),

    # --- F: wrong entity -----------------------------------------------------
    _e("F01", "F", "dev", CONTRADICTED,
       "CTO: James Whitfield, CFO: Robert Tanaka, COO: Elena Vasquez.",
       "Elena Vasquez is the CFO.",
       "Role belongs to another person in the same list."),
    _e("F02", "F", "dev", CONTRADICTED,
       "Manual calibration takes about two hours. Automated calibration finishes in twelve minutes.",
       "Automated calibration takes about two hours.",
       "Value belongs to the other method."),
    _e("F03", "F", "test", INSUFFICIENT,
       "The lidar array requires calibration every 30 days.",
       "The sensor array requires calibration every 30 days.",
       "Evidence never describes the sensor array's interval; this is absence, not contradiction."),
    _e("F04", "F", "test", CONTRADICTED,
       "The sensor array is recalibrated every 90 days. The lidar array requires calibration every 30 days.",
       "The lidar array requires calibration every 90 days.",
       "Interval of the sensor array attached to the lidar."),

    # --- G: negation reversed ------------------------------------------------
    _e("G01", "G", "dev", CONTRADICTED,
       "Calibration cannot correct a physically damaged lidar unit.",
       "Calibration can correct a physically damaged lidar unit.",
       "Negation dropped; polarity reversed."),
    _e("G02", "G", "dev", CONTRADICTED,
       "A failed calibration check blocks the robot from dispatch.",
       "A failed calibration check does not block the robot from dispatch.",
       "Negation added."),
    _e("G03", "G", "test", CONTRADICTED,
       "The system does not store raw audio.",
       "The system stores raw audio.",
       "Negation dropped."),
    _e("G04", "G", "test", CONTRADICTED,
       "Lidar calibration does not require a reference target.",
       "Lidar calibration requires the reference target.",
       "Negation dropped."),

    # --- H: unsupported causal relationship ---------------------------------
    _e("H01", "H", "dev", INSUFFICIENT,
       "Repeated failures on the same axis indicate a worn bearing.",
       "A worn bearing causes repeated failures on the same axis.",
       "Evidence reports an indicator, not a cause."),
    _e("H02", "H", "dev", INSUFFICIENT,
       "Intervals are shortened after a collision or a firmware update.",
       "Firmware updates cause collisions, so the interval is shortened.",
       "Causal chain invented; evidence only orders two events."),
    _e("H03", "H", "test", INSUFFICIENT,
       "The robot is parked on a level pad.",
       "Parking on a level pad prevents calibration drift.",
       "Purpose and causal effect are not in the evidence."),
    _e("H04", "H", "test", INSUFFICIENT,
       "Calibration records are retained for five years.",
       "The five-year retention policy exists to satisfy auditors.",
       "Motive invented."),

    # --- I: comparisons ------------------------------------------------------
    _e("I01", "I", "dev", CONTRADICTED,
       "Manual calibration is more accurate on damaged hardware, while automated calibration is cheaper for a large fleet.",
       "Manual calibration is cheaper than automated calibration.",
       "Evidence says the opposite about cost."),
    _e("I02", "I", "dev", CONTRADICTED,
       "Manual calibration takes about two hours. Automated calibration finishes in twelve minutes.",
       "Automated and manual calibration take about the same time.",
       "Evidence states a large difference."),
    _e("I03", "I", "test", SUPPORTED,
       "Manual calibration takes about two hours. Automated calibration finishes in twelve minutes.",
       "Automated calibration is faster than manual calibration.",
       "Derived comparison; requires unit conversion.", hard=True),
    _e("I04", "I", "test", INSUFFICIENT,
       "Manual calibration is more accurate on damaged hardware.",
       "Manual calibration is always more accurate than automated calibration.",
       "'on damaged hardware' does not support an unconditional comparison."),

    # --- J: support from more than one passage ------------------------------
    _e("J01", "J", "dev", SUPPORTED,
       ("The lidar array requires calibration every 30 days.",
        "Calibration records are retained for five years."),
       "The lidar array is calibrated every 30 days and the records are kept for five years.",
       "Two clauses, each supported by a different passage."),
    _e("J02", "J", "dev", SUPPORTED,
       ("Manual calibration needs a technician.",
        "Manual calibration takes about two hours."),
       "Manual calibration needs a technician and takes about two hours.",
       "Composed from two passages."),
    _e("J03", "J", "test", SUPPORTED,
       ("The lidar array requires calibration every 30 days.",
        "Calibration cannot correct a physically damaged lidar unit."),
       "Lidar is calibrated every 30 days, but calibration cannot repair physical damage.",
       "Two claims, two passages."),
    _e("J04", "J", "test", INSUFFICIENT,
       ("The lidar array requires calibration every 30 days.",
        "Calibration records are retained for five years."),
       "Lidar calibration is required every 30 days because the records are kept for five years.",
       "Conjunction is supported; the causal link is not."),

    # --- K: citation that does not support the claim ------------------------
    _e("K01", "K", "dev", SUPPORTED,
       ("The lidar array requires calibration every 30 days.",
        "The power rail operates at 12 volts."),
       "The lidar array requires calibration every 30 days.",
       "Claim is true (block 1) but the model cites block 2.",
       stated_citations=(2,), citation_correct=False),
    _e("K02", "K", "test", SUPPORTED,
       ("Net income was $142.6 million.",
        "The company raised $185 million in the IPO."),
       "Net income was $142.6 million.",
       "Claim is true (block 1) but the model cites block 2.",
       stated_citations=(2,), citation_correct=False),
    _e("K03", "K", "dev", INSUFFICIENT,
       ("The power rail operates at 12 volts.",),
       "The lidar array requires calibration every 30 days.",
       "Citation to a block that does not discuss the claim; claim itself is unsupported here.",
       stated_citations=(1,), citation_correct=False),

    # --- M: insufficient or contradictory evidence --------------------------
    _e("M01", "M", "dev", INSUFFICIENT,
       "The board of directors consists of 9 members.",
       "The board met on 12 March.",
       "Evidence describes the board's size, not a meeting."),
    _e("M02", "M", "dev", INSUFFICIENT,
       "The system uses sentence transformer models.",
       "The system uses TensorFlow.",
       "A framework is never named."),
    _e("M03", "M", "test", INSUFFICIENT,
       "Documents are processed into chunks of 384 tokens with 64-token overlap.",
       "The retention policy is 30 days.",
       "Retention is not discussed."),
    _e("M04", "M", "test", CONTRADICTED,
       ("The lidar calibration interval is 30 days.",
        "The lidar calibration interval is 45 days."),
       "The lidar calibration interval is 30 days.",
       "One passage repeats the claim, another contradicts it; the conflict is recorded rather than averaged away.",
       evidence_conflict=True),
    _e("M05", "M", "dev", INSUFFICIENT,
       ("Documents are processed into chunks of 384 tokens.",),
       "The chunk overlap is 64 tokens.",
       "The document mentions chunk size but not overlap."),
)


def by_split(split: str) -> tuple[ClaimExample, ...]:
    return tuple(example for example in EXAMPLES if example.split == split)


def statistics() -> dict:
    """Counts used in reports (no hidden filtering)."""
    labels = {}
    categories = {}
    for example in EXAMPLES:
        labels[example.label] = labels.get(example.label, 0) + 1
        categories[example.category] = categories.get(example.category, 0) + 1
    return {
        "total": len(EXAMPLES),
        "dev": len(by_split("dev")),
        "test": len(by_split("test")),
        "labels": labels,
        "categories": categories,
        "hard_examples": sum(1 for example in EXAMPLES if example.hard),
        "citation_error_examples": sum(1 for example in EXAMPLES if not example.citation_correct),
        "evidence_conflict_examples": sum(1 for example in EXAMPLES if example.evidence_conflict),
    }
