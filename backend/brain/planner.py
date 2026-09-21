"""
Deterministic planner for the DocuMind Brain.

Maps Intent → Plan.  Each intent produces a fixed, finite sequence of
execution steps.  No loops, no autonomous replanning, no LLM-generated
plans, no dynamic tool discovery.
"""

from brain.types import (
    Intent,
    Capability,
    Plan,
    PlanStep,
    ParsedRequest,
)


def build_plan(parsed: ParsedRequest) -> Plan:
    """Construct a deterministic execution plan for the given intent.

    The plan is a fixed sequence of steps.  Given the same intent,
    the same plan is always produced.
    """
    _PLANS = {
        Intent.DOCUMENT_QUESTION: Plan(
            steps=(
                PlanStep(
                    capability=Capability.DOCUMENT_RETRIEVAL,
                    input_keys=("user_id", "parsed_request.cleaned_text", "top_k"),
                    output_key="retrieval_sources",
                ),
                PlanStep(
                    capability=Capability.CONTEXT_BUILDING,
                    # The question is needed to size the context against the QA
                    # model's real input window (Phase 3D).
                    input_keys=("retrieval_sources", "parsed_request.cleaned_text"),
                    output_key="context",
                ),
                PlanStep(
                    capability=Capability.QA_ANSWER,
                    input_keys=("parsed_request.cleaned_text", "context"),
                    output_key="qa_result",
                ),
            ),
            required_capabilities=(
                Capability.DOCUMENT_RETRIEVAL,
                Capability.CONTEXT_BUILDING,
                Capability.QA_ANSWER,
            ),
        ),
        Intent.DOCUMENT_SEARCH: Plan(
            steps=(
                PlanStep(
                    capability=Capability.DOCUMENT_RETRIEVAL,
                    input_keys=("user_id", "parsed_request.cleaned_text", "top_k"),
                    output_key="retrieval_sources",
                ),
            ),
            required_capabilities=(
                Capability.DOCUMENT_RETRIEVAL,
            ),
        ),
        Intent.DOCUMENT_SUMMARY: Plan(
            steps=(
                PlanStep(
                    capability=Capability.SUMMARY_GENERATION,
                    input_keys=("user_id", "parsed_request.cleaned_text"),
                    output_key="summary_result",
                ),
            ),
            required_capabilities=(
                Capability.SUMMARY_GENERATION,
            ),
        ),
        Intent.MEDIA_VERIFICATION: Plan(
            steps=(
                PlanStep(
                    capability=Capability.MEDIA_VERIFICATION,
                    input_keys=("raw_question",),
                    output_key="verification_result",
                ),
            ),
            required_capabilities=(
                Capability.MEDIA_VERIFICATION,
            ),
        ),
        Intent.UNSUPPORTED_REQUEST: Plan(
            steps=(),
            required_capabilities=(),
        ),
    }

    return _PLANS[parsed.intent]
