"""Additive, local generative answering for DocuMind.

The extractive DistilBERT QA model in ``chat/qa_model.py`` remains the default
engine and the permanent comparison baseline.  This package adds a grounded
generative path (local Flan-T5-base, CPU, offline) with deterministic answer
planning and evidence-based verification.

See ``DOCUMIND_PROJECT_CONTEXT.md`` §0.4 Phase 2–3 for the approved direction and
the conditions that continue to apply.
"""

from generation.engine import (
    get_generator_status,
    is_generator_available,
    GENERATOR_ENABLED_ENV,
    GENERATOR_MODEL_ENV,
)
from generation.service import answer_generatively, build_evidence_blocks
from generation.types import (
    AnswerFormat,
    EvidenceBlock,
    GenerationResult,
    GenerationUnavailableError,
)

__all__ = [
    "AnswerFormat",
    "EvidenceBlock",
    "GenerationResult",
    "GenerationUnavailableError",
    "GENERATOR_ENABLED_ENV",
    "GENERATOR_MODEL_ENV",
    "answer_generatively",
    "build_evidence_blocks",
    "get_generator_status",
    "is_generator_available",
]
