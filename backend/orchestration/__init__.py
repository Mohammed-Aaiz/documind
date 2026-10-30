"""LangGraph orchestration for the stateful, evidence-grounded conversation.

Modules
-------

``state``
    The typed state that flows between nodes.
``followup``
    Deterministic follow-up resolution against the stored history.
``rerank``
    DistilBERT-as-cross-encoder reranking of retrieved passages.
``graph``
    The ``langgraph`` state machine (load history → resolve → retrieve →
    rerank → generate → remember).
``service``
    The API-facing boundary (validation, store selection, typed result).
"""

from orchestration.service import (
    PIPELINE_VERSION,
    ConversationAnswer,
    answer_with_memory,
    clear_conversation,
    conversation_history,
    conversation_status,
)

__all__ = [
    "ConversationAnswer",
    "PIPELINE_VERSION",
    "answer_with_memory",
    "clear_conversation",
    "conversation_history",
    "conversation_status",
]
