"""Typed contracts for the additive generative answer path.

These types are deliberately independent of FastAPI, SQLAlchemy and the
service layer, mirroring the rule already used by ``brain/types.py``: contracts
live on their own so the planner, the verifier and the engine can be tested
without a database, a model download or an HTTP client.

Nothing here is a capability claim.  The generative path is *additive*: the
extractive DistilBERT path (``chat/qa_model.py``) remains the default engine and
the permanent comparison baseline until an evaluation justifies otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AnswerFormat(str, Enum):
    """Requested academic answer extent.

    The mark value selects *answer-planning directives*, never a word count:
    a 15-mark definition and a 15-mark derivation must not be forced into the
    same shape (``DOCUMIND_PROJECT_CONTEXT.md`` §0.4 Phase 3).
    """

    FIVE = "5"
    TEN = "10"
    FIFTEEN = "15"

    @property
    def marks(self) -> int:
        return int(self.value)

    @classmethod
    def coerce(cls, value: "AnswerFormat | str | int | None") -> "AnswerFormat":
        """Accept ``5``, ``"5"``, ``"10"``, ``"15"`` (default 10).

        Defaulting to 10 is a product default, not a measurement: it is the
        middle extent and is stated in the response as ``answerFormat``.
        """
        if isinstance(value, cls):
            return value
        if value is None or str(value).strip() == "":
            return cls.TEN
        text = str(value).strip()
        for member in cls:
            if text == member.value:
                return member
        raise ValueError(
            f"Unsupported answer format {text!r}; expected one of "
            f"{', '.join(m.value for m in cls)}."
        )


@dataclass(frozen=True)
class EvidenceBlock:
    """One citable evidence unit handed to the generator.

    ``index`` is the 1-based citation number printed in the prompt and expected
    in the generated answer (``[1]``).  Provenance fields are optional because
    legacy chunks legitimately carry ``None`` for them.
    """

    index: int
    content: str
    document_id: str = ""
    document_name: str = ""
    page: int | None = None
    heading_path: tuple[str, ...] | None = None
    section: str | None = None
    score: float = 0.0
    chunk_id: str = ""
    knowledge_graph_path: str | None = None
    knowledge_graph_hops: int | None = None
    knowledge_graph_predicate: str | None = None
    knowledge_graph_quote: str | None = None
    spatial_regions: list[dict] | None = None
    #: True when ``content`` is an excerpt of a longer chunk.  Structural
    #: resolution must not claim a *position* from a truncated list: the tail is
    #: missing silently, so "the eighth item" could resolve to the fifth
    #: surviving one.
    truncated: bool = False

    def label(self) -> str:
        """Human-readable provenance label used inside the prompt."""
        parts: list[str] = [self.document_name or "document"]
        if self.page is not None:
            parts.append(f"page {self.page}")
        if self.section:
            parts.append(f"section: {self.section}")
        elif self.heading_path:
            parts.append("section: " + " > ".join(self.heading_path))
        if self.knowledge_graph_path:
            parts.append(f"entity path: {self.knowledge_graph_path}")
        return ", ".join(parts)


@dataclass(frozen=True)
class SupportPoint:
    """One evidence-grounded supporting point added for a longer answer.

    ``text`` is a sentence taken from the cited evidence block: elaboration
    never invents content, so a 10/15-mark answer is longer because it covers
    more of the evidence, not because the model was asked to say more.
    """

    text: str
    citation: int


@dataclass(frozen=True)
class AnswerPlan:
    """Deterministic planning output for one question/format pair.

    ``instructions`` are prompt directives derived from the requested marks and
    the question's own command words.  They are not templates and carry no
    claim about expected length in words.
    """

    marks: int
    directives: tuple[str, ...]
    max_new_tokens: int
    question_type: str

    def as_prompt_lines(self) -> list[str]:
        return [f"- {item}" for item in self.directives]


CLAIM_SUPPORTED = "SUPPORTED"
CLAIM_PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
CLAIM_UNSUPPORTED = "UNSUPPORTED"
CLAIM_CONTRADICTED = "CONTRADICTED"
CLAIM_UNABLE = "UNABLE_TO_VERIFY"
CLAIM_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


@dataclass
class ClaimCheck:
    """Verification outcome for one sentence of generated prose.

    ``supported`` is kept for backward compatibility and is true only for
    ``state == CLAIM_SUPPORTED``.  ``entity_check`` records whether the numeric
    value was found in the sentence of the same entity the question asks about
    (``matched`` / ``mismatch`` / ``not_applicable`` / ``unable``).
    """

    sentence: str
    citation_indices: list[int]
    supported: bool
    support_ratio: float
    reason: str
    state: str = CLAIM_UNSUPPORTED
    entity_check: str = "not_applicable"


@dataclass
class VerificationReport:
    """Deterministic, evidence-based verification of a generated answer.

    ``citation_accuracy`` is the fraction of *cited* claims whose cited
    evidence actually supports them.  ``unsupported_claims`` lists claims the
    evidence does not support (or that cite a non-existent block).  Neither is
    a calibrated probability of correctness.
    """

    claims: list[ClaimCheck] = field(default_factory=list)
    citation_accuracy: float = 0.0
    supported_claims: int = 0
    unsupported_claims: list[str] = field(default_factory=list)
    uncited_claims: int = 0
    verified: bool = False
    #: Answer-level state: SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED |
    #: INSUFFICIENT_EVIDENCE.  ``verified`` is true only for SUPPORTED.
    status: str = "UNSUPPORTED"
    #: Claim sentences whose numeric value belongs to a different entity.
    wrong_entity_claims: list[str] = field(default_factory=list)
    #: Claims the evidence contradicts (relation-aware verifier).  Kept separate
    #: from ``unsupported_claims`` because "the document says otherwise" is a
    #: different fact from "the document does not say".
    contradicted_claims: list[str] = field(default_factory=list)

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    def summary(self) -> dict:
        return {
            "claimCount": self.claim_count,
            "supportedClaims": self.supported_claims,
            "unsupportedClaims": list(self.unsupported_claims),
            "uncitedClaims": self.uncited_claims,
            "citationAccuracy": round(self.citation_accuracy, 4),
            "verified": self.verified,
            "status": self.status,
            "wrongEntityClaims": list(self.wrong_entity_claims),
            "contradictedClaims": list(self.contradicted_claims),
        }


@dataclass
class GenerationResult:
    """What the generative service returns to its caller.

    ``answer`` is empty when the engine abstained or failed; ``abstained`` and
    ``error`` explain why.  ``prompt`` is retained for debugging and evaluation
    reproducibility, and is never returned over the API.
    """

    answer: str
    abstained: bool
    verification: VerificationReport
    model: str
    marks: int
    latency_ms: int
    prompt: str = ""
    error: str | None = None


class GenerationUnavailableError(RuntimeError):
    """The generative model could not be loaded.

    Raised so the API layer can return an explicit 503 instead of an empty
    answer, exactly as the extractive path does for an unavailable QA model.
    """
