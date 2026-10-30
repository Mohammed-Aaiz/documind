"""Typed state for the stateful GraphRAG conversation graph.

The state is the contract between graph nodes: it is a plain ``TypedDict`` of
serialisable values (no ORM sessions, no model handles), so the graph can be
traced, resumed or checkpointed later without rewriting the nodes.

Every field is optional (``total=False``) because LangGraph merges a node's
returned partial dict into the accumulated state: a node returns only what it
changes.
"""

from __future__ import annotations

from typing import Any, TypedDict


class ConversationState(TypedDict, total=False):
    """One turn of a stateful conversation.

    Retrieval and generation inputs
    -------------------------------
    ``user_id`` / ``session_id`` identify the conversation.  ``user_id`` is
    taken from the JWT by the route, never from the request body: it is what
    scopes both retrieval and conversation memory.
    """

    user_id: str
    session_id: str
    question: str
    answer_format: str
    top_k: int

    # --- Conversation memory ------------------------------------------------
    history: list[dict[str, str]]
    """Prior turns, oldest first, as returned by the store."""

    retrieval_query: str
    """Question actually used for retrieval.  Equals ``question`` unless a
    follow-up was resolved against the previous turn."""

    followup_resolved: bool

    # --- Retrieval ----------------------------------------------------------
    chunks: list[Any]
    """``chat.rag.SourceChunk`` records.  Kept as a list so LangGraph can merge
    it; the nodes treat the items as read-only."""

    rerank: dict
    """Rerank metadata: whether it ran, the signal, and any error."""

    # --- Answer -------------------------------------------------------------
    result: Any
    """The ``generation.service.GenerativeAnswer`` produced for this turn.  It
    is kept as an object because the reliability record needs the exact
    evidence blocks that were supplied; the graph runs without a checkpointer,
    so nothing here is ever serialised."""

    answer: str
    engine: str
    model: str
    marks: int
    verification: dict
    warnings: list[str]
    insufficient_context: bool
    abstained: bool
    latency_ms: int

    # --- Diagnostics --------------------------------------------------------
    errors: list[str]
    """Non-fatal problems (e.g. "rerank skipped").  Never used to hide a
    failure: an answer that could not be produced leaves ``answer`` empty and
    ``abstained`` true instead."""


__all__ = ["ConversationState"]
