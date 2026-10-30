"""Stateful conversation memory (Phase C).

The store keeps one user's chat history as a structured message array
``[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]``
so the text chat and the streaming voice path read and write the *same*
conversation.  Redis is the backend; when Redis is unreachable the store says
so (``backend="memory"``) instead of silently pretending otherwise.

See :mod:`session.store` for the isolation and failure rules.
"""

from session.store import (
    ConversationMessage,
    ConversationStore,
    InMemoryConversationStore,
    RedisConversationStore,
    get_conversation_store,
    reset_conversation_store,
    store_status,
)

__all__ = [
    "ConversationMessage",
    "ConversationStore",
    "InMemoryConversationStore",
    "RedisConversationStore",
    "get_conversation_store",
    "reset_conversation_store",
    "store_status",
]
