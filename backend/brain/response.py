"""
Response assembler for the DocuMind Brain.

Converts the final ExecutionContext (with evidence, outcome, and errors)
into a BrainResponse.  The API layer will later map BrainResponse to
its Pydantic AskResponse schema.

The assembler does NOT import FastAPI or Pydantic.
"""

from brain.types import (
    BrainResponse,
    ExecutionContext,
    EvidenceBundle,
    QaResult,
    SourceRef,
)
from outcomes import Outcome


def assemble(ctx: ExecutionContext) -> BrainResponse:
    """Build a BrainResponse from the completed ExecutionContext.

    Uses the outcome and evidence to produce an honest response.
    No fabricated data.
    """
    evidence = ctx.evidence
    outcome = ctx.outcome

    # Build sources from evidence
    sources = list(evidence.sources)

    # Extract QA details
    qa = evidence.qa_result
    answer = qa.answer if qa else ""
    confidence = qa.score if qa else 0.0

    # Determine insufficient_context flag
    insufficient = outcome in (
        Outcome.INSUFFICIENT_EVIDENCE,
        Outcome.UNAVAILABLE,
        Outcome.FAILED,
    )

    # Phase 3D correction: when the Brain abstains, it must not present the
    # model's low-confidence guess as the answer.  The extractive QA model has
    # no no-answer head, so it always emits *some* span; surfacing that span
    # alongside an abstention would be an evidence-backed claim the system just
    # decided it cannot make.  The raw QA score is still reported honestly
    # through the reliability evidence below, so nothing is hidden.
    if insufficient:
        answer = ""
        confidence = 0.0

    # Build reliability dict (maps to ReliabilityEvidence schema)
    reliability = _build_reliability(evidence, insufficient)

    return BrainResponse(
        answer=answer,
        confidence=confidence,
        sources=sources,
        insufficient_context=insufficient,
        question=ctx.raw_question,
        outcome=outcome,
        reliability=reliability,
    )


def _build_reliability(
    evidence: EvidenceBundle, insufficient: bool
) -> dict:
    """Build the reliability evidence dictionary.

    Maps to the ReliabilityEvidence Pydantic schema in chat/routes.py.
    """
    scores = evidence.retrieval_scores
    best = max(scores) if scores else 0.0
    avg = sum(scores) / len(scores) if scores else 0.0

    # Count unique documents from sources
    doc_ids = {s.document_id for s in evidence.sources}

    # Source status classification (same thresholds as existing code)
    source_refs = []
    for src in evidence.sources:
        if src.score >= 0.5:
            status = "VERIFIED"
        elif src.score >= 0.3:
            status = "MARGINAL"
        else:
            status = "UNRESOLVED"

        source_refs.append({
            "id": src.chunk_id,
            "documentId": src.document_id,
            "documentName": src.document_name,
            "content": src.content[:200],
            "relevanceScore": round(max(0.0, src.score), 4),
            "page": src.page,
            "status": status,
        })

    # Phase 3D transparency: chunks retrieved but not supplied to the QA model
    # are counted rather than silently dropped from the report.
    signals = evidence.grounding_signals or {}
    omitted = signals.get("omitted_source_ids") or []
    retrieved_count = signals.get("retrieved_source_count")
    if retrieved_count is None:
        retrieved_count = len(evidence.sources)

    return {
        "qaConfidence": evidence.qa_result.score if evidence.qa_result else 0.0,
        "retrievalScore": round(best, 4),
        "avgRetrievalScore": round(avg, 4),
        "sourceCount": len(evidence.sources),
        "uniqueDocuments": len(doc_ids),
        "factualGrounded": evidence.factual_grounded,
        "insufficientContext": insufficient,
        "sources": source_refs,
        # --- Phase 3D additions (all default-safe for existing clients) ---
        "retrievedSourceCount": int(retrieved_count),
        "omittedSourceCount": len(omitted),
        "contextBudgetTokens": int(signals.get("context_budget_tokens", 0) or 0),
        "contextUsedTokens": int(signals.get("context_used_tokens", 0) or 0),
    }
