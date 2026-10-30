"""LangGraph state machine for a stateful GraphRAG conversation turn.

Graph shape::

    START → load_history → resolve_query → retrieve ─┬→ rerank → generate ─┐
                                                     └→ abstain ───────────┤
                                                                           └→ remember → END

Why each node exists
--------------------

``load_history``
    Reads the user's conversation from the store (Redis, or the in-process
    fallback when Redis is unreachable).  This is the only place history is
    read, so the graph and the REST history endpoint cannot disagree.

``resolve_query``
    Turns "and the second one?" into a retrievable query using the previous
    user turn (deterministically — see ``followup.py``).

``retrieve``
    Runs the project's production retrieval pipeline unchanged
    (``generation.service.retrieve_evidence``: pgvector + the dual structural
    path + the gated table band).  No parallel retrieval implementation exists.

``rerank``
    Orders the retrieved passages with the project QA model used as a
    cross-encoder relevance judge (``rerank.py``).  Ordering only — evidence is
    never dropped and no similarity score is rewritten.

``generate``
    Produces the grounded answer through ``generation.service.answer_generatively``
    so the answerability gate, verification and mark-aware depth policy stay a
    single implementation.  The engine is the instruct model when one is
    configured and loadable, otherwise the project's provisioned generator; the
    answer reports which model actually produced it.

``abstain``
    No evidence retrieved → an honest empty answer, without a model call.

``remember``
    Appends the user turn and the produced answer to the conversation store and
    persists the reliability record, then returns the updated history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph
from starlette.concurrency import run_in_threadpool

from generation.causal import (
    ConversationModelUnavailable,
    conversation_model_status,
    generate_conversation_answer,
    is_conversation_model_available,
)
from generation.service import (
    answer_generatively,
    persist_generation,
    retrieve_evidence,
)
from generation.types import AnswerFormat, GenerationUnavailableError
from orchestration.followup import resolve_followup
from orchestration.rerank import rerank_chunks
from orchestration.state import ConversationState
from session.store import ConversationMessage, ConversationStore

logger = logging.getLogger(__name__)

NODE_LOAD_HISTORY = "load_history"
NODE_RESOLVE_QUERY = "resolve_query"
NODE_RETRIEVE = "retrieve"
#: Node names must not collide with state keys (LangGraph forbids it), so the
#: rerank node is named ``rerank_evidence`` while its state field is ``rerank``.
NODE_RERANK = "rerank_evidence"
NODE_GENERATE = "generate"
NODE_ABSTAIN = "abstain"
NODE_REMEMBER = "remember"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _answer_fields(result) -> dict:
    """Flatten a ``GenerativeAnswer`` into state fields."""
    return {
        "result": result,
        "answer": result.answer,
        "model": result.model,
        "marks": result.marks,
        "verification": result.verification,
        "warnings": list(result.warnings),
        "insufficient_context": result.insufficient_context,
        "abstained": result.abstained,
        "latency_ms": result.latency_ms,
    }


def engine_for_model(model: str, *, instruct_model: str | None) -> str:
    """Name the engine that actually produced an answer.

    Never guessed from configuration: the label follows the ``model`` reported
    by the answer service, so a fallback cannot be described as the model that
    was requested.
    """
    from generation.service import DETERMINISTIC_LIST_ENGINE, DETERMINISTIC_TABLE_ENGINE

    if model == DETERMINISTIC_TABLE_ENGINE:
        return "deterministic-table"
    if model == DETERMINISTIC_LIST_ENGINE:
        return "deterministic-list"
    if instruct_model and model == instruct_model:
        return "instruct"
    return "generative"


def build_conversation_graph(*, db: Any, store: ConversationStore):
    """Compile the graph for one request's dependencies.

    ``db`` and ``store`` are per-request infrastructure handles, so the graph is
    compiled per request instead of being cached in a module global (a cached
    graph would pin one database session for every conversation in the
    process).  Compilation is in-memory and cheap.
    """
    from config import get_settings

    settings = get_settings()
    history_limit = max(1, int(settings.conversation_history_limit))
    ttl = max(1, int(settings.conversation_ttl_seconds))

    async def load_history(state: ConversationState) -> dict:
        messages = await store.history(
            state["user_id"], state["session_id"], limit=history_limit
        )
        return {"history": [m.as_dict() for m in messages], "errors": []}

    async def resolve_query(state: ConversationState) -> dict:
        query, resolved = resolve_followup(
            state["question"], state.get("history") or []
        )
        return {"retrieval_query": query, "followup_resolved": resolved}

    async def retrieve(state: ConversationState) -> dict:
        query = state.get("retrieval_query") or state["question"]
        chunks = await retrieve_evidence(
            db,
            state["user_id"],
            query,
            top_k=int(state.get("top_k") or 5),
            # The mark level decides whether the 1-hop hierarchy expansion runs;
            # passing it here keeps the conversation path on the same retrieval
            # implementation as /api/generation/answer.
            answer_format=state.get("answer_format"),
        )
        return {"chunks": list(chunks)}

    async def rerank(state: ConversationState) -> dict:
        ordered, meta = await run_in_threadpool(
            rerank_chunks, state["question"], state.get("chunks") or []
        )
        errors = list(state.get("errors") or [])
        if meta.get("error"):
            errors.append(str(meta["error"]))
        return {"chunks": list(ordered), "rerank": meta, "errors": errors}

    async def generate(state: ConversationState) -> dict:
        fmt = AnswerFormat.coerce(state.get("answer_format"))
        question = state["question"]
        chunks = list(state.get("chunks") or [])
        history = list(state.get("history") or [])
        warnings: list[str] = []

        instruct_model = conversation_model_status().get("model")
        generator = None
        instruct_ready = await run_in_threadpool(is_conversation_model_available)
        if instruct_ready:

            def _causal(question_text, blocks, *, answer_format=None, history=()):
                try:
                    return generate_conversation_answer(
                        question_text,
                        blocks,
                        answer_format=answer_format,
                        history=history,
                    )
                except ConversationModelUnavailable as exc:  # pragma: no cover
                    raise GenerationUnavailableError(str(exc)) from exc

            generator = _causal
        elif instruct_model:
            # Configured but not usable: say so instead of silently presenting
            # the fallback as the requested model.
            detail = conversation_model_status().get("error")
            warnings.append(
                f"The configured conversation model '{instruct_model}' is unavailable "
                f"({detail}); the project's provisioned generator produced this answer."
            )

        result = await run_in_threadpool(
            lambda: answer_generatively(
                question,
                chunks,
                answer_format=fmt,
                generator=generator,
                history=history,
            )
        )

        fields = _answer_fields(result)
        fields["engine"] = engine_for_model(
            result.model, instruct_model=instruct_model if instruct_ready else None
        )
        fields["warnings"] = [*warnings, *result.warnings]
        return fields

    async def abstain(state: ConversationState) -> dict:
        fmt = AnswerFormat.coerce(state.get("answer_format"))
        result = await run_in_threadpool(
            lambda: answer_generatively(state["question"], [], answer_format=fmt)
        )
        fields = _answer_fields(result)
        fields["engine"] = "generative"
        fields["rerank"] = {
            "applied": False,
            "signal": "none",
            "scored": 0,
            "candidates": 0,
            "scores": [],
            "error": "no evidence retrieved",
        }
        return fields

    async def remember(state: ConversationState) -> dict:
        user_id = state["user_id"]
        session_id = state["session_id"]
        created_at = _now()
        answer = state.get("answer") or ""

        history = await store.append(
            user_id,
            session_id,
            ConversationMessage(role="user", content=state["question"], created_at=created_at),
            ttl_seconds=ttl,
            limit=history_limit,
        )
        if answer.strip():
            history = await store.append(
                user_id,
                session_id,
                ConversationMessage(
                    role="assistant", content=answer, created_at=_now()
                ),
                ttl_seconds=ttl,
                limit=history_limit,
            )

        result = state.get("result")
        if result is not None:
            await persist_generation(
                db,
                user_id,
                state["question"],
                list(state.get("chunks") or []),
                result,
                AnswerFormat.coerce(state.get("answer_format")),
            )

        return {"history": [m.as_dict() for m in history]}

    graph = StateGraph(ConversationState)
    graph.add_node(NODE_LOAD_HISTORY, load_history)
    graph.add_node(NODE_RESOLVE_QUERY, resolve_query)
    graph.add_node(NODE_RETRIEVE, retrieve)
    graph.add_node(NODE_RERANK, rerank)
    graph.add_node(NODE_GENERATE, generate)
    graph.add_node(NODE_ABSTAIN, abstain)
    graph.add_node(NODE_REMEMBER, remember)

    graph.add_edge(START, NODE_LOAD_HISTORY)
    graph.add_edge(NODE_LOAD_HISTORY, NODE_RESOLVE_QUERY)
    graph.add_edge(NODE_RESOLVE_QUERY, NODE_RETRIEVE)
    graph.add_conditional_edges(
        NODE_RETRIEVE,
        lambda state: NODE_ABSTAIN if not state.get("chunks") else NODE_RERANK,
        {NODE_RERANK: NODE_RERANK, NODE_ABSTAIN: NODE_ABSTAIN},
    )
    graph.add_edge(NODE_RERANK, NODE_GENERATE)
    graph.add_edge(NODE_GENERATE, NODE_REMEMBER)
    graph.add_edge(NODE_ABSTAIN, NODE_REMEMBER)
    graph.add_edge(NODE_REMEMBER, END)

    return graph.compile()


__all__ = [
    "NODE_ABSTAIN",
    "NODE_GENERATE",
    "NODE_LOAD_HISTORY",
    "NODE_REMEMBER",
    "NODE_RERANK",
    "NODE_RESOLVE_QUERY",
    "NODE_RETRIEVE",
    "build_conversation_graph",
    "engine_for_model",
]
