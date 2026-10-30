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

import logging
import re
import time
from dataclasses import dataclass, field, replace
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
    VerificationReport,
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

logger = logging.getLogger(__name__)

#: How many seeds the 15-mark graph expansion starts from (the highest-ranked
#: retrieved chunks) and how many 1-hop neighbours it may add.  Both are small
#: because the prompt's own block cap is ``MAX_EVIDENCE_BLOCKS``: adding more
#: would only push retrieved evidence out of the model's window.
GRAPH_EXPANSION_SEED_COUNT = 3
GRAPH_EXPANSION_MAX_ADDED = 4


class RetrievedEvidence(list):
    """List-compatible evidence with an honest optional KG retrieval status."""

    def __init__(self, values=(), *, knowledge_graph_status: str = "not_searched",
                 routing: dict | None = None, spatial_status: str = "not_searched"):
        super().__init__(values)
        self.knowledge_graph_status = knowledge_graph_status
        self.routing = routing or {}
        self.spatial_status = spatial_status

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
    *,
    generator=None,
    history: Sequence[object] = (),
) -> GenerativeAnswer:
    """Generate and verify a grounded answer for ``question``.

    ``generator`` optionally replaces the model call with another engine that
    has the same contract — ``(question, blocks, answer_format=..., history=...)
    -> GenerationResult`` — which is how the conversation graph routes to an
    instruct model while keeping *this* module's answerability gate, verification,
    depth planning and warning policy as the single implementation.  When it is
    ``None`` the project's provisioned engine (``generate``) runs unchanged.

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

    result: GenerationResult
    if generator is None:
        result = generate(question, blocks, answer_format=answer_format)
    else:
        result = generator(
            question, blocks, answer_format=answer_format, history=history
        )

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


async def _expand_long_form_evidence(db, user_id: str, chunks: Sequence[object]) -> list:
    """Append 1-hop graph neighbours to the retrieved evidence for a long answer.

    The neighbours are *retrieved context*, not new retrieval: each one is an
    actual chunk of one of the caller's own documents, reached by the persisted
    structure graph, and it keeps its provenance (``structural_hops``,
    ``structural_relation``, heading path).  ``score`` stays ``0.0`` because no
    similarity was computed for it, exactly like the dual-path structural
    stream.

    A failure here must not deny the user the retrieved evidence they already
    have: the exception is logged and the original chunks are returned.  The
    answer therefore never claims expansion it did not get.
    """
    from chat.rag import RETRIEVAL_STRUCTURAL, SourceChunk
    from graph.service import expand_evidence_via_graph

    if len(chunks) >= MAX_EVIDENCE_BLOCKS:
        return list(chunks)

    seed_ids = [
        str(getattr(chunk, "chunk_id", ""))
        for chunk in chunks
        if getattr(chunk, "evidence_kind", "chunk") == "chunk"
        and getattr(chunk, "chunk_id", None)
    ][:GRAPH_EXPANSION_SEED_COUNT]
    if not seed_ids:
        return list(chunks)

    try:
        neighbours = await expand_evidence_via_graph(
            db, user_id, seed_ids, max_neighbours=GRAPH_EXPANSION_MAX_ADDED
        )
    except Exception:  # pragma: no cover - depends on a live database
        logger.warning(
            "Graph expansion failed for a 15-mark answer; using the retrieved evidence only",
            exc_info=True,
        )
        return list(chunks)

    seen = {str(getattr(chunk, "chunk_id", "")) for chunk in chunks}
    expanded = list(chunks)
    for neighbour in neighbours:
        if len(expanded) >= MAX_EVIDENCE_BLOCKS:
            break
        if neighbour.chunk_id in seen:
            continue
        seen.add(neighbour.chunk_id)
        expanded.append(
            SourceChunk(
                chunk_id=neighbour.chunk_id,
                content=neighbour.content,
                score=0.0,  # structural evidence has no similarity
                document_id=neighbour.document_id,
                document_name=neighbour.document_name,
                page=neighbour.page,
                heading_path=neighbour.heading_path,
                section=neighbour.section,
                retrieval_path=RETRIEVAL_STRUCTURAL,
                structural_hops=neighbour.hops,
                structural_relation=neighbour.relation,
                structural_score=neighbour.weight / (1 + neighbour.hops),
            )
        )
    return expanded


async def retrieve_evidence(
    db,
    user_id: str,
    question: str,
    top_k: int = 5,
    answer_format: AnswerFormat | str | int | None = None,
    *, query_routing: bool = False,
):
    """Retrieve dense, structural, table and entity-relation evidence.

    ``answer_format`` only changes *how much* of the retrieved structure is
    offered: a 15-mark answer additionally receives the 1-hop graph neighbours
    of its top seeds (parent heading + adjacent chunks), so its depth can come
    from the document's own hierarchy.  Shorter formats retrieve exactly what
    they retrieved before.
    """
    from chat.rag import (
        dual_path_enabled,
        order_evidence_bands,
        retrieve_chunks,
        retrieve_dual_path,
        retrieve_table_row_evidence,
        table_evidence_enabled,
    )

    async def dense_search():
        candidate_depth = min(32, max(20, top_k * 3)) if query_routing else top_k
        if query_routing:
            from chat.rag import retrieve_hybrid_chunks
            semantic = await retrieve_hybrid_chunks(db, user_id, question, top_k=top_k,
                                                    candidate_limit=candidate_depth)
        else:
            semantic = await retrieve_chunks(db, user_id, question, top_k=top_k)
        results = await retrieve_dual_path(db, user_id, question, top_k=candidate_depth, semantic_chunks=semantic) if dual_path_enabled() else semantic
        if table_evidence_enabled():
            rows = await retrieve_table_row_evidence(db, user_id, question=question, chunks=results)
            results = order_evidence_bands(results, rows)
        if AnswerFormat.coerce(answer_format).marks == AnswerFormat.FIFTEEN.marks:
            results = await _expand_long_form_evidence(db, user_id, results)
        return results

    routing = {"path": "both", "source": "disabled", "reason": "Legacy callers search both indexes.", "latencyMs": 0}
    graph_state = None
    if query_routing:
        from graph.service import knowledge_graph_status
        try:
            async with db.begin_nested():
                graph_state = await knowledge_graph_status(db, user_id)
        except Exception:
            logger.warning("Graph availability check failed", exc_info=True)
            graph_state = "unavailable"
        if graph_state == "available":
            from generation.query_router import route_query
            decision = await route_query(question)
            routing = {"path": decision.path, "source": decision.source, "reason": decision.reason,
                       "latencyMs": decision.latency_ms, "provider": decision.provider, "hosted": decision.hosted}
        else:
            # There is no benefit in paying for a neural router when the graph
            # index has not been built. Dense retrieval remains immediately useful.
            routing = {"path": "semantic", "source": "index-availability",
                       "reason": "Entity graph is not available; use dense and document structure evidence.", "latencyMs": 0}

    async def finish(values, graph_status):
        if query_routing and values:
            from generation.reranking import rerank_candidates
            values, reranking = await rerank_candidates(question, values, top_k=top_k)
            routing["reranker"] = reranking
            from generation.topic_context import expand_topic_context
            try:
                values, topic_coverage = await expand_topic_context(db, user_id, values)
            except Exception:
                logger.warning("Topic context unavailable; preserving retrieved evidence", exc_info=True)
                topic_coverage = {"status": "unavailable"}
            routing["topicContext"] = topic_coverage
        spatial_status = "not_searched"
        if query_routing:
            from generation.spatial_retrieval import is_spatial_query
            if is_spatial_query(question):
                from config import get_settings
                from embeddings.visual import visual_model_status
                visual_settings = get_settings()
                availability = visual_model_status(visual_settings)
                routing["visualIndex"] = availability["status"]
                if availability["available"]:
                    from embeddings.visual_index import retrieve_visual_patches
                    try:
                        import uuid
                        async with db.begin_nested():
                            patches = await retrieve_visual_patches(
                                db, question, uuid.UUID(str(user_id)),
                                top_k=min(4, top_k), settings=visual_settings)
                        routing["visualIndex"] = "retrieved" if patches else "no_indexed_match"
                        # Separate rank streams: CLIP image similarity and
                        # MiniLM text similarity are not comparable raw scores.
                        ranked = [(1 / (60 + rank), 0, item)
                                  for rank, item in enumerate(values, 1)]
                        ranked += [(1 / (60 + rank), 1, item)
                                   for rank, item in enumerate(patches, 1)]
                        ranked.sort(key=lambda item: (-item[0], item[1]))
                        values = [replace(item, fusion_score=score)
                                  for score, _, item in ranked][:MAX_EVIDENCE_BLOCKS]
                    except Exception:
                        logger.warning("Visual patch search unavailable; retaining text evidence", exc_info=True)
                        routing["visualIndex"] = "unavailable"
        if query_routing and values:
            from generation.spatial_retrieval import enrich_spatial_sources
            try:
                async with db.begin_nested():
                    values, spatial_status = await enrich_spatial_sources(db, user_id, question, values)
            except Exception:
                logger.warning("Spatial context unavailable; preserving retrieved text", exc_info=True)
                spatial_status = "unavailable"
        return RetrievedEvidence(values, knowledge_graph_status=graph_status,
                                 routing=routing, spatial_status=spatial_status)

    chunks = [] if routing["path"] == "graph" else await dense_search()
    if routing["path"] == "semantic":
        status = "not_requested" if graph_state == "available" else graph_state or "empty"
        return await finish(chunks, status)

    graph_status = "empty"
    graph_chunks = []
    try:
        from chat.rag import RETRIEVAL_HYBRID, RETRIEVAL_KNOWLEDGE_GRAPH, SourceChunk
        from graph.service import knowledge_graph_status, retrieve_knowledge_graph_candidates

        # Keep this optional path inside a savepoint. If the additive KG
        # schema is absent or temporarily unavailable, its SQL error must not
        # poison the transaction that persists the ordinary answer/chat.
        async def query_graph():
            return (
                await retrieve_knowledge_graph_candidates(
                    db, user_id, question, max_hops=3,
                    max_candidates=min(4, max(1, top_k)),
                ),
                await knowledge_graph_status(db, user_id),
            )

        begin_nested = getattr(db, "begin_nested", None)
        if callable(begin_nested):
            async with begin_nested():
                graph_candidates, graph_state = await query_graph()
        else:  # small unit-test adapters may expose only execute()
            graph_candidates, graph_state = await query_graph()
        graph_chunks = [
            SourceChunk(
                chunk_id=item.chunk_id,
                content=item.content,
                score=0.0,
                document_id=item.document_id,
                document_name=item.document_name,
                page=item.page,
                heading_path=item.heading_path,
                section=item.section,
                retrieval_path=RETRIEVAL_KNOWLEDGE_GRAPH,
                knowledge_graph_path=item.graph_path,
                knowledge_graph_hops=item.hops,
                knowledge_graph_predicate=item.predicate,
                knowledge_graph_quote=item.evidence_quote,
            )
            for item in graph_candidates
        ]
        if graph_chunks:
            graph_status = "retrieved"
        elif graph_state == "available":
            graph_status = "available_no_match"
        elif graph_state == "pending":
            graph_status = "pending"
        elif graph_state == "unavailable":
            graph_status = "unavailable"
        else:
            graph_status = "empty"
    except Exception:
        # Dense/structure evidence remains usable. The caller surfaces this
        # state so an unavailable KG is never presented as a successful walk.
        logger.warning("Entity-relation graph retrieval failed; using existing evidence paths", exc_info=True)
        graph_status = "unavailable"

    if not graph_chunks:
        if routing["path"] == "graph":
            # A routing prediction is not an answerability decision. A missing
            # entity match always gets a dense rescue pass instead of a refusal.
            chunks = await dense_search()
            routing["denseRescue"] = True
        return await finish(chunks, graph_status)

    by_id = {str(getattr(chunk, "chunk_id", "")): index for index, chunk in enumerate(chunks)}
    additions = []
    for candidate in graph_chunks:
        existing_index = by_id.get(candidate.chunk_id)
        if existing_index is not None:
            existing = chunks[existing_index]
            # Keep its prior retrieval path and raw score; attach the KG trail
            # without counting the same source chunk twice.
            chunks[existing_index] = replace(
                existing,
                retrieval_path=RETRIEVAL_HYBRID,
                knowledge_graph_path=candidate.knowledge_graph_path,
                knowledge_graph_hops=candidate.knowledge_graph_hops,
                knowledge_graph_predicate=candidate.knowledge_graph_predicate,
                knowledge_graph_quote=candidate.knowledge_graph_quote,
            )
            continue
        by_id[candidate.chunk_id] = -1
        additions.append(candidate)

    # Fuse ranks rather than pretending graph distance is cosine similarity.
    # A chunk found by both paths receives both contributions; its original
    # dense score and its exact entity-relation trail remain independently visible.
    primary_rank = {chunk.chunk_id: index + 1 for index, chunk in enumerate(chunks)}
    graph_rank = {chunk.chunk_id: index + 1 for index, chunk in enumerate(graph_chunks)}
    merged = []
    for chunk in [*chunks, *additions]:
        base = primary_rank.get(chunk.chunk_id)
        graph = graph_rank.get(chunk.chunk_id)
        score = (0.5 / (60 + base) if base else 0.0) + (0.5 / (60 + graph) if graph else 0.0)
        merged.append(replace(chunk, fusion_score=score))
    merged.sort(key=lambda chunk: (-float(chunk.fusion_score or 0),
                                  min(primary_rank.get(chunk.chunk_id, 1000), graph_rank.get(chunk.chunk_id, 1000)),
                                  chunk.chunk_id))
    return await finish(merged, graph_status)


def verified_supported_claims(
    answer: str, blocks: Sequence[EvidenceBlock], question: str,
) -> tuple[str, VerificationReport, bool]:
    """Keep complete supported claims, then verify the resulting answer again.

    A stray uncited closing sentence must not discard an otherwise grounded
    answer. The caller reports any omissions; thresholds and source IDs remain
    unchanged. Never reconstruct or paraphrase a claim during this step.
    """
    report = verify_with_mode(answer, blocks, question=question)
    if report.verified or not report.supported_claims:
        return answer, report, False
    sentences = []
    for claim in report.claims:
        if not claim.supported or not claim.citation_indices:
            continue
        # ClaimCheck contains the citation-stripped sentence. Restore the
        # verified source indices so the final answer remains inspectable.
        sentence = claim.sentence.rstrip()
        punctuation = sentence[-1:] if sentence[-1:] in (".", "!", "?") else ""
        body = sentence[:-1] if punctuation else sentence
        citations = " ".join(f"[{index}]" for index in claim.citation_indices)
        sentences.append(f"{body} {citations}{punctuation}")
    retained = "\n\n".join(sentences)
    checked = verify_with_mode(retained, blocks, question=question)
    if not checked.verified:
        return answer, report, False
    return retained, checked, True


async def answer_from_evidence(
    question: str,
    chunks: Sequence[object],
    answer_format: AnswerFormat | str | int | None = None,
    *,
    settings=None,
) -> tuple[list, GenerativeAnswer]:
    """Use Groq for the stateless API, preserving the exact supplied excerpts.

    Historical ``answer_generatively`` remains available to frozen evaluation
    callers. Product routes use this async provider path instead and never load
    its former local model. Both paths retain the existing evidence verifier.
    """
    from config import get_settings
    from generation.provider_prompt import prepare_prompt, select_evidence
    from generation.providers import complete_answer

    started = time.perf_counter()
    settings = settings if settings is not None else get_settings()
    fmt = AnswerFormat.coerce(answer_format)
    ordered, _ = select_evidence(question, chunks)
    if not ordered:
        return [], GenerativeAnswer(
            answer="", abstained=True, insufficient_context=True,
            verification=verify_with_mode("", []).summary(),
            warnings=["No document evidence was retrieved for this question."],
            marks=fmt.marks, model="", latency_ms=0, blocks=[],
        )
    prepared = prepare_prompt(question, ordered, [], workspace="student", task="answer",
                              answer_format=fmt, context_tokens=int(getattr(settings, "groq_context_tokens", 8192)))
    warnings = list(prepared.warnings)
    answer, model = "", ""
    abstained = not prepared.blocks
    if prepared.blocks:
        completion = await complete_answer(prepared.messages, max_tokens=prepared.max_tokens,
                                           settings=settings)
        answer, model = completion.text.strip(), completion.model
        citations = {int(value) for value in re.findall(r"\[(\d+)\]", answer)}
        valid_citations = bool(citations) and citations <= {block.index for block in prepared.blocks}
        abstained = not answer or "INSUFFICIENT_EVIDENCE" in answer.upper() or not valid_citations
        if abstained:
            warnings.append("The generated draft lacked supported evidence or valid source references and was withheld.")
        if completion.finish_reason in ("length", "max_tokens"):
            warnings.append("The provider reached its output limit; this answer may be incomplete.")
        warnings.append("Groq generated the draft using the supplied document evidence.")
    else:
        warnings.append("No usable evidence fits the configured context window.")
    report = verify_with_mode(answer, prepared.blocks, question=question)
    if answer and not abstained and not report.verified:
        answer, report, omitted = verified_supported_claims(answer, prepared.blocks, question)
        if omitted:
            warnings.append("Claims that could not be supported by the supplied evidence were omitted; the remaining answer was checked again.")
    if answer and not abstained and not report.verified:
        abstained = True
        warnings.append("The generated draft contained claims the evidence verifier could not support and was withheld.")
    return prepared.sources, GenerativeAnswer(
        answer="" if abstained else answer, abstained=abstained,
        insufficient_context=abstained, verification=report.summary(),
        warnings=warnings, marks=fmt.marks, model=model,
        latency_ms=int((time.perf_counter() - started) * 1000), blocks=prepared.blocks,
    )


async def run_generation(
    db,
    user_id: str,
    question: str,
    top_k: int = 5,
    answer_format: AnswerFormat | str | int | None = None,
) -> tuple[list, GenerativeAnswer]:
    """Retrieve through the shared RAG pipeline and answer with Groq."""
    started = time.perf_counter()
    chunks = await retrieve_evidence(
        db, user_id, question, top_k=top_k, answer_format=answer_format, query_routing=True
    )
    sources, result = await answer_from_evidence(question, chunks, answer_format=answer_format)
    result.latency_ms = int((time.perf_counter() - started) * 1000)
    return sources, result


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
    "answer_from_evidence",
    "build_evidence_blocks",
    "is_generator_available",
    "get_generator_status",
    "persist_generation",
    "reliability_sources",
    "retrieve_evidence",
    "run_generation",
    "GenerationUnavailableError",
]
