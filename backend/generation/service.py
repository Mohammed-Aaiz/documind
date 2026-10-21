"""Service layer for the additive generative answer path.

Responsibilities:

* turn retrieved ``SourceChunk`` records into numbered, citable evidence blocks
  (provenance preserved: document, page, section/heading path, chunk id);
* call the local engine;
* verify the output against the evidence that was actually supplied;
* decide what the API may honestly report (abstention, unsupported claims).

Retrieval is **not** implemented here: the caller passes the chunks produced by
``chat.rag`` so the generative path reuses the exact production retrieval
pipeline rather than a look-alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from generation.engine import generate, get_generator_status, is_generator_available
from generation.lists import resolve_list_answer
from generation.planning import ELABORATION_POINTS, compose_answer, plan_support_points
from generation.tables import resolve_table_answer
from generation.types import (
    AnswerFormat,
    EvidenceBlock,
    GenerationResult,
    GenerationUnavailableError,
)
from generation.types import CLAIM_INSUFFICIENT
from generation.verification import answerability, verify_with_mode

#: Evidence blocks offered to the generator.  Bounded because Flan-T5's encoder
#: window is 512 tokens; ``engine.fit_prompt`` then drops the lowest-ranked
#: blocks that do not fit.
MAX_EVIDENCE_BLOCKS = 8

#: Excerpt cap per block before prompt fitting.  A very long chunk would
#: otherwise consume the whole window and starve every other source.
MAX_BLOCK_CHARS = 1200

#: Reported engine name for an answer read from a table cell/row.  It is not a
#: model: the text comes from the evidence and the verifier checks it, so the
#: API must not imply that a language model produced it.
DETERMINISTIC_TABLE_ENGINE = "deterministic-table"

#: Same for an answer read from an ordered list (heading + one item per line).
DETERMINISTIC_LIST_ENGINE = "deterministic-list"


def _structured_answer(
    resolved,
    blocks: Sequence[EvidenceBlock],
    answer_format: AnswerFormat | str | int | None,
    engine: str,
    question: str,
    where: str,
) -> "GenerativeAnswer | None":
    """Verify a deterministically resolved answer and wrap it for the API.

    The returned text is evidence text, and it is still judged by the unchanged
    verifier: an answer that cannot be attributed to the block it came from is
    not used, so this path cannot invent content.  ``where`` describes the
    resolved position for the warning that is returned to the user.
    """
    report = verify_with_mode(resolved.text, blocks, question=question)
    if not report.verified:
        return None
    return GenerativeAnswer(
        answer=resolved.text,
        abstained=False,
        insufficient_context=False,
        verification=report.summary(),
        warnings=[
            f"The answer was read directly from {where} in evidence "
            f"[{resolved.citation}] and checked against it; it was not reworded "
            "by a language model."
        ],
        marks=AnswerFormat.coerce(answer_format).marks,
        model=engine,
        latency_ms=0,
        blocks=list(blocks),
    )


def _list_answer(
    question: str,
    blocks: Sequence[EvidenceBlock],
    answer_format: AnswerFormat | str | int | None,
) -> "GenerativeAnswer | None":
    """Answer an ordered-list question from the list itself, or ``None``.

    Measured on the frozen P3 benchmark (2026-10-21): the generative engine
    answered 2 of 20 list questions correctly.  It returned the wrong item, a
    truncated item (``Elena Vasquez`` for ``COO: Elena Vasquez (since June
    2021)``), or two concatenated items.  A position within an evidence list is
    not a generation problem.
    """
    resolved = resolve_list_answer(question, blocks)
    if resolved is None:
        return None
    where = f"item {resolved.position} of the list '{resolved.heading}'"
    return _structured_answer(
        resolved,
        blocks,
        answer_format,
        DETERMINISTIC_LIST_ENGINE,
        question,
        where,
    )


def _table_answer(
    question: str,
    blocks: Sequence[EvidenceBlock],
    answer_format: AnswerFormat | str | int | None,
) -> "GenerativeAnswer | None":
    """Answer a table lookup from the table itself, or ``None``.

    Measured on the frozen P3 benchmark (2026-10-21): the generative engine
    answered **0 of 40** table questions correctly — it returned the header, a
    value from the wrong column, or a neighbouring cell.  A row/column lookup
    the evidence already states structurally is not a generation problem, so it
    is resolved deterministically and then verified like any other answer (the
    returned text is evidence text, and an answer the verifier cannot attribute
    is not used).

    The direct answer is returned without mark-aware elaboration: for a table
    lookup the cell *is* the complete answer, and appending further evidence
    sentences both padded the answer and broke exactness (measured: 10-mark
    answers appended the table header to a correct cell).
    """
    resolved = resolve_table_answer(question, blocks)
    if resolved is None:
        return None

    where = f"row '{resolved.row_label}'"
    if resolved.column:
        where += f", column '{resolved.column}' of the table"
    return _structured_answer(
        resolved,
        blocks,
        answer_format,
        DETERMINISTIC_TABLE_ENGINE,
        question,
        where,
    )


@dataclass
class GenerativeAnswer:
    """Verified generative answer plus the provenance the API returns."""

    answer: str
    abstained: bool
    insufficient_context: bool
    verification: dict
    warnings: list[str]
    marks: int
    model: str
    latency_ms: int
    blocks: list[EvidenceBlock] = field(default_factory=list)


def build_evidence_blocks(chunks: Sequence[object]) -> list[EvidenceBlock]:
    """Number the retrieved evidence, preserving provenance and order.

    ``chunks`` are ``chat.rag.SourceChunk`` records (or anything exposing the
    same attributes).  Duplicates are dropped by ``chunk_id`` so one passage is
    never cited twice.  ``score`` is carried through unchanged and is never
    reinterpreted as correctness.
    """
    blocks: list[EvidenceBlock] = []
    seen: set[str] = set()

    for chunk in chunks:
        chunk_id = str(getattr(chunk, "chunk_id", "") or "")
        if chunk_id and chunk_id in seen:
            continue
        content = str(getattr(chunk, "content", "") or "").strip()
        if not content:
            continue
        if chunk_id:
            seen.add(chunk_id)

        blocks.append(
            EvidenceBlock(
                index=len(blocks) + 1,
                content=content[:MAX_BLOCK_CHARS],
                truncated=len(content) > MAX_BLOCK_CHARS,
                document_id=str(getattr(chunk, "document_id", "") or ""),
                document_name=str(getattr(chunk, "document_name", "") or ""),
                page=getattr(chunk, "page", None),
                heading_path=getattr(chunk, "heading_path", None),
                section=getattr(chunk, "section", None),
                score=float(getattr(chunk, "score", 0.0) or 0.0),
                chunk_id=chunk_id,
            )
        )
        if len(blocks) >= MAX_EVIDENCE_BLOCKS:
            break

    return blocks


def answer_generatively(
    question: str,
    chunks: Sequence[object],
    answer_format: AnswerFormat | str | int | None = None,
) -> GenerativeAnswer:
    """Generate and verify a grounded answer for ``question``.

    Raises :class:`GenerationUnavailableError` when the model is unavailable so
    the API can return 503.  Insufficient evidence is a normal, honest outcome
    (empty answer + ``abstained=True``).
    """
    blocks = build_evidence_blocks(chunks)
    if not blocks:
        report = verify_with_mode("", [])
        return GenerativeAnswer(
            answer="",
            abstained=True,
            insufficient_context=True,
            verification=report.summary(),
            warnings=["No document evidence was retrieved for this question."],
            marks=AnswerFormat.coerce(answer_format).marks,
            model="",
            latency_ms=0,
            blocks=[],
        )

    # Answerability gate: refuse only when the evidence is missing more than one
    # distinctive question term (measured policy — see
    # ``generation.verification.answerability``).  Without any gate the generator
    # answered all 42 unanswerable P3 rows; the previous coverage>=0.5 rule
    # rejected 72 of the 140 answerable rows and lost measurable EM/F1.
    combined_evidence = "\n".join(block.content for block in blocks)
    decision = answerability(question, combined_evidence)
    if not decision.allowed:
        report = verify_with_mode("", blocks, question=question)
        return GenerativeAnswer(
            answer="",
            abstained=True,
            insufficient_context=True,
            verification={**report.summary(), "status": CLAIM_INSUFFICIENT},
            warnings=[
                "The retrieved evidence does not cover the question's key terms "
                f"(coverage {decision.coverage:.2f}); no answer was generated."
            ],
            marks=AnswerFormat.coerce(answer_format).marks,
            model="",
            latency_ms=0,
            blocks=blocks,
        )

    table_result = _table_answer(question, blocks, answer_format)
    if table_result is not None:
        return table_result

    list_result = _list_answer(question, blocks, answer_format)
    if list_result is not None:
        return list_result

    result: GenerationResult = generate(question, blocks, answer_format=answer_format)

    warnings: list[str] = []

    # Grounding policy: an answer with no claim attributable to the retrieved
    # evidence is not an answer.  It is withheld (and reported), never returned
    # as if the documents supported it.  This is what prevents a fluent but
    # ungrounded generation from masquerading as document knowledge.
    withheld = False
    if result.answer and result.verification.supported_claims == 0:
        warnings.append(
            "The generated text could not be attributed to any retrieved evidence, so it was withheld."
        )
        result.answer = ""
        result.abstained = True
        result.verification.status = CLAIM_INSUFFICIENT
        withheld = True

    # Mark-aware depth: 5 marks stays a single direct answer; 10 and 15 add
    # further evidence sentences that are relevant to the question, each with
    # its own citation.  The depth therefore comes from covering more of the
    # supplied evidence, never from asking the model to write more (measured:
    # a longer depth cue made Flan-T5-base copy the context instead).
    points = []
    depth_shortfall = False
    if result.answer and not result.abstained:
        points = plan_support_points(question, blocks, result.marks, answer=result.answer)
        requested = ELABORATION_POINTS.get(AnswerFormat.coerce(result.marks), 0)
        depth_shortfall = requested > 0 and len(points) < requested
        composed = compose_answer(result.answer, points, result.marks)
        if composed != result.answer:
            result.answer = composed
            # The added points are evidence sentences, but verification still
            # runs over the *whole* returned answer so the reported status
            # describes what the user actually receives.
            result.verification = verify_with_mode(composed, blocks, question=question)

    if result.abstained:
        if not withheld:
            warnings.append(
                "The model reported that the retrieved evidence does not answer this question."
            )
    elif not result.verification.verified:
        if result.verification.wrong_entity_claims:
            warnings.append(
                "A numeric value in the answer belongs to a different entity than the question asks about."
            )
        if result.verification.unsupported_claims:
            warnings.append(
                f"{len(result.verification.unsupported_claims)} claim(s) are not supported by the cited evidence."
            )
        if result.verification.uncited_claims:
            warnings.append(
                f"{result.verification.uncited_claims} claim(s) carry no citation."
            )
    if depth_shortfall and result.answer:
        warnings.append(
            f"The evidence supports only {len(points)} additional point(s), so the answer is "
            f"shorter than a {result.marks}-mark answer normally allows; nothing was invented "
            "to fill the gap."
        )
    if len(blocks) >= MAX_EVIDENCE_BLOCKS:
        warnings.append(
            f"Only the top {MAX_EVIDENCE_BLOCKS} evidence blocks were supplied to the generator."
        )

    return GenerativeAnswer(
        answer=result.answer,
        abstained=result.abstained,
        insufficient_context=result.abstained or not result.answer.strip(),
        verification=result.verification.summary(),
        warnings=warnings,
        marks=result.marks,
        model=result.model,
        latency_ms=result.latency_ms,
        blocks=blocks,
    )


# ---------------------------------------------------------------------------
# Shared request path (used by /api/generation/answer and /api/chat/ask)
# ---------------------------------------------------------------------------
#
# Keeping retrieval and persistence here means both API surfaces produce the
# same evidence, the same verification and the same reliability record.  There
# is exactly one implementation of the generative request path.


async def retrieve_evidence(db, user_id: str, question: str, top_k: int = 5):
    """Retrieve evidence through the production pipeline (semantic + structure)."""
    from chat.rag import (
        dual_path_enabled,
        order_evidence_bands,
        retrieve_chunks,
        retrieve_dual_path,
        retrieve_table_row_evidence,
        table_evidence_enabled,
    )

    semantic = await retrieve_chunks(db, user_id, question, top_k=top_k)
    if dual_path_enabled():
        chunks = await retrieve_dual_path(
            db, user_id, question, top_k=top_k, semantic_chunks=semantic
        )
    else:
        chunks = semantic

    if table_evidence_enabled():
        rows = await retrieve_table_row_evidence(
            db, user_id, question=question, chunks=chunks
        )
        chunks = order_evidence_bands(chunks, rows)
    return chunks


async def run_generation(
    db,
    user_id: str,
    question: str,
    top_k: int = 5,
    answer_format: AnswerFormat | str | int | None = None,
) -> tuple[list, GenerativeAnswer]:
    """Retrieve evidence, generate, verify and return both the chunks and result."""
    chunks = await retrieve_evidence(db, user_id, question, top_k=top_k)
    result = answer_generatively(question, chunks, answer_format=answer_format)
    return chunks, result


def reliability_sources(chunks: Sequence[object], blocks: Sequence[EvidenceBlock]) -> list[dict]:
    """Sources exactly as supplied to the generator, with provenance."""
    supplied = {block.chunk_id for block in blocks if block.chunk_id}
    out: list[dict] = []
    for chunk in chunks:
        chunk_id = str(getattr(chunk, "chunk_id", ""))
        if supplied and chunk_id not in supplied:
            continue
        out.append(
            {
                "id": chunk_id,
                "documentId": str(getattr(chunk, "document_id", "")),
                "documentName": str(getattr(chunk, "document_name", "")),
                "content": str(getattr(chunk, "content", "")),
                "relevanceScore": float(getattr(chunk, "score", 0.0) or 0.0),
                "page": getattr(chunk, "page", None),
                "status": "VERIFIED",
                "retrievalPath": getattr(chunk, "retrieval_path", None),
                "fusionScore": getattr(chunk, "fusion_score", None),
                "structuralHops": getattr(chunk, "structural_hops", None),
                "evidenceKind": getattr(chunk, "evidence_kind", None),
                "section": getattr(chunk, "section", None),
                "elementType": getattr(chunk, "element_type", None),
                "tableElementId": getattr(chunk, "table_element_id", None),
                "rowIndex": getattr(chunk, "row_index", None),
                "headerRepeated": getattr(chunk, "header_repeated", None),
            }
        )
    return out


async def persist_generation(
    db,
    user_id: str,
    question: str,
    chunks: Sequence[object],
    result: GenerativeAnswer,
    answer_format: AnswerFormat,
) -> list[dict]:
    """Persist the last-query reliability record for a generative answer."""
    from reliability.routes import store_query_reliability

    sources = reliability_sources(chunks, result.blocks)
    best = max((s["relevanceScore"] for s in sources), default=0.0)
    average = (
        sum(s["relevanceScore"] for s in sources) / len(sources) if sources else 0.0
    )
    await store_query_reliability(
        user_id,
        {
            "question": question,
            "answer": result.answer,
            "qaConfidence": 0.0,  # no extractive span was produced
            "retrievalScore": best,
            "avgRetrievalScore": round(average, 4),
            "sourceCount": len(result.blocks),
            "uniqueDocuments": len({b.document_id for b in result.blocks if b.document_id}),
            "factualGrounded": bool(result.verification.get("verified")),
            "insufficientContext": result.insufficient_context,
            "sources": sources,
            "generation": {
                "engine": "generative",
                "model": result.model,
                "answerFormat": answer_format.value,
                "marks": result.marks,
                "latencyMs": result.latency_ms,
                "abstained": result.abstained,
                "verification": result.verification,
                "warnings": result.warnings,
            },
        },
        db=db,
    )
    return sources


__all__ = [
    "GenerativeAnswer",
    "answer_generatively",
    "build_evidence_blocks",
    "is_generator_available",
    "get_generator_status",
    "persist_generation",
    "reliability_sources",
    "retrieve_evidence",
    "run_generation",
    "GenerationUnavailableError",
]
