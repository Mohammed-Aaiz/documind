"""Conversation memory: a Redis-backed, user-scoped message store.

Design rules
------------

* **Owner-scoped by construction.**  Every key embeds the authenticated user
  id (``documind:conversation:{user_id}:{session_id}``).  A caller cannot read
  or clear another user's conversation because the user id comes from the JWT
  on the server side, never from the request body.

* **Honest failure.**  Redis is an infrastructure dependency, not something the
  application may fake.  :func:`get_conversation_store` pings Redis once; if
  that fails the store falls back to a process-local store **and reports**
  ``backend="memory"`` with the connection error, so an API response can state
  where the conversation actually lives.  Nothing claims Redis when it is not
  there.

* **Bounded.**  History is capped (``conversation_history_limit`` messages,
  ``MAX_MESSAGE_CHARS`` characters per message) and expires after
  ``conversation_ttl_seconds``.  A conversation cannot grow without bound, and
  a stale session does not resurrect as "memory".

* **Append-only storage discipline.**  The Redis backend uses ``RPUSH`` +
  ``LTRIM`` + ``EXPIRE``, which are atomic per command, so two requests writing
  to one conversation cannot lose each other's messages the way a
  read-modify-write would.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)

#: Conversation roles the store accepts.  ``assistant`` replaces the older
#: ``oracle`` sender label of the SQL chat tables for the *conversation* layer;
#: the model layer keeps its own vocabulary.
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
VALID_ROLES: tuple[str, ...] = (ROLE_USER, ROLE_ASSISTANT)

#: Hard cap per message.  An answer longer than this is truncated *by the
#: caller* (the generation path already bounds its output); the store refuses
#: to persist more than this so one request cannot exhaust the key budget.
MAX_MESSAGE_CHARS = 8000

#: Key-safe identifier: UUIDs and the app's own session ids are alphanumeric
#: with hyphens/underscores.  Anything else is rejected rather than embedded in
#: a Redis key (this is also what prevents key injection such as ``a:b``).
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

KEY_PREFIX = "documind:conversation"

DEFAULT_TTL_SECONDS = 86_400
DEFAULT_HISTORY_LIMIT = 12


class InvalidConversationIdError(ValueError):
    """Raised when a user id or session id is not key-safe."""


@dataclass(frozen=True)
class ConversationMessage:
    """One turn of a conversation.

    ``role`` is ``"user"`` or ``"assistant"``.  ``content`` is the text that was
    actually produced or received — it is never summarised or rewritten here.
    """

    role: str
    content: str
    created_at: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content, "createdAt": self.created_at}

    @classmethod
    def from_dict(cls, data: Any) -> "ConversationMessage | None":
        """Parse one stored record, dropping anything malformed.

        Corrupt entries are skipped rather than raising: a single bad record
        must not make a conversation unreadable.
        """
        if not isinstance(data, dict):
            return None
        role = str(data.get("role", "")).strip().lower()
        content = data.get("content")
        if role not in VALID_ROLES or not isinstance(content, str):
            return None
        return cls(role=role, content=content, created_at=str(data.get("createdAt", "") or ""))


def _validate_id(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not _ID_RE.match(text):
        raise InvalidConversationIdError(
            f"{label} must be 1-64 characters of letters, digits, hyphen or underscore."
        )
    return text


def conversation_key(user_id: str, session_id: str) -> str:
    """Redis key for one user's conversation (owner-scoped)."""
    return f"{KEY_PREFIX}:{_validate_id(user_id, 'user id')}:{_validate_id(session_id, 'session id')}"


def _clamp_history(messages: Iterable[ConversationMessage], limit: int) -> list[ConversationMessage]:
    items = list(messages)
    if limit <= 0:
        return []
    return items[-limit:]


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class ConversationStore:
    """Async message store contract shared by the Redis and memory backends."""

    backend: str = "unknown"

    async def append(
        self,
        user_id: str,
        session_id: str,
        message: ConversationMessage,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        raise NotImplementedError

    async def history(
        self,
        user_id: str,
        session_id: str,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        raise NotImplementedError

    async def clear(self, user_id: str, session_id: str) -> None:
        raise NotImplementedError

    async def status(self) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisConversationStore(ConversationStore):
    """Redis list per (user, session), with TTL and trimming."""

    backend = "redis"

    def __init__(self, client: Any, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._client = client
        self._ttl = max(1, int(ttl_seconds))

    async def append(
        self,
        user_id: str,
        session_id: str,
        message: ConversationMessage,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        key = conversation_key(user_id, session_id)
        payload = json.dumps(
            {
                "role": message.role,
                "content": message.content[:MAX_MESSAGE_CHARS],
                "createdAt": message.created_at,
            },
            ensure_ascii=False,
        )
        ttl = max(1, int(ttl_seconds or self._ttl))

        # Three atomic commands, no read-modify-write: concurrent appends cannot
        # overwrite each other.
        await self._client.rpush(key, payload)
        if limit > 0:
            await self._client.ltrim(key, -limit, -1)
        await self._client.expire(key, ttl)
        return await self.history(user_id, session_id, limit=limit)

    async def history(
        self,
        user_id: str,
        session_id: str,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        key = conversation_key(user_id, session_id)
        raw = await self._client.lrange(key, 0, -1)
        messages: list[ConversationMessage] = []
        for entry in raw or []:
            if isinstance(entry, bytes):
                entry = entry.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(entry)
            except (TypeError, ValueError):
                logger.warning("Dropping unparseable conversation record in %s", key)
                continue
            message = ConversationMessage.from_dict(parsed)
            if message is not None:
                messages.append(message)
        return _clamp_history(messages, limit)

    async def clear(self, user_id: str, session_id: str) -> None:
        await self._client.delete(conversation_key(user_id, session_id))

    async def status(self) -> dict:
        return {
            "backend": self.backend,
            "ttlSeconds": self._ttl,
            "available": True,
            "error": None,
        }


# ---------------------------------------------------------------------------
# In-process fallback backend
# ---------------------------------------------------------------------------


class InMemoryConversationStore(ConversationStore):
    """Process-local fallback used only when Redis is unreachable.

    It is intentionally *not* durable and not shared between workers; the API
    reports ``backend="memory"`` so a client knows the conversation is
    process-scoped rather than claiming Redis persistence.
    """

    backend = "memory"

    def __init__(self, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, error: str | None = None) -> None:
        self._ttl = max(1, int(ttl_seconds))
        self._error = error
        self._entries: dict[str, list[ConversationMessage]] = {}
        self._expires_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _live(self, key: str) -> bool:
        deadline = self._expires_at.get(key)
        if deadline is None:
            return True
        if time.monotonic() >= deadline:
            self._entries.pop(key, None)
            self._expires_at.pop(key, None)
            return False
        return True

    async def append(
        self,
        user_id: str,
        session_id: str,
        message: ConversationMessage,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        key = conversation_key(user_id, session_id)
        ttl = max(1, int(ttl_seconds or self._ttl))
        async with self._lock:
            messages = self._entries.get(key, []) if self._live(key) else []
            messages.append(
                ConversationMessage(
                    role=message.role,
                    content=message.content[:MAX_MESSAGE_CHARS],
                    created_at=message.created_at,
                )
            )
            self._entries[key] = _clamp_history(messages, limit)
            self._expires_at[key] = time.monotonic() + ttl
            return list(self._entries[key])

    async def history(
        self,
        user_id: str,
        session_id: str,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[ConversationMessage]:
        key = conversation_key(user_id, session_id)
        async with self._lock:
            if not self._live(key):
                return []
            return _clamp_history(self._entries.get(key, []), limit)

    async def clear(self, user_id: str, session_id: str) -> None:
        key = conversation_key(user_id, session_id)
        async with self._lock:
            self._entries.pop(key, None)
            self._expires_at.pop(key, None)

    async def status(self) -> dict:
        return {
            "backend": self.backend,
            "ttlSeconds": self._ttl,
            "available": True,
            "error": self._error,
        }


# ---------------------------------------------------------------------------
# Process-level selection
# ---------------------------------------------------------------------------

_store: ConversationStore | None = None
_store_lock = asyncio.Lock()


def reset_conversation_store() -> None:
    """Drop the cached store (used by tests and by configuration changes)."""
    global _store
    _store = None


async def get_conversation_store() -> ConversationStore:
    """Return the process-wide store, preferring Redis.

    Redis is probed once (``PING``) so a missing server is detected at first
    use rather than on every request.  On failure the in-memory fallback is
    returned together with the connection error, which the API surfaces as
    ``backend="memory"`` — the conversation is still stateful, it is just not
    shared or durable, and the response says exactly that.
    """
    global _store
    if _store is not None:
        return _store

    async with _store_lock:
        if _store is not None:
            return _store

        from config import get_settings

        settings = get_settings()
        ttl = settings.conversation_ttl_seconds

        try:
            import redis.asyncio as redis_async

            client = redis_async.Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await client.ping()
            _store = RedisConversationStore(client, ttl_seconds=ttl)
            logger.info("Conversation memory backend: redis (%s)", settings.redis_url)
        except Exception as exc:  # pragma: no cover - depends on local Redis
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Conversation memory backend unavailable (%s); using in-process "
                "memory for this worker",
                reason,
            )
            _store = InMemoryConversationStore(ttl_seconds=ttl, error=reason)

        return _store


async def store_status() -> dict:
    """Report which backend actually holds conversation state.

    A health endpoint may call this: it performs no model load and no
    additional Redis round-trip beyond the initial probe.
    """
    try:
        return await (await get_conversation_store()).status()
    except Exception as exc:  # pragma: no cover - defensive
        return {"backend": "unavailable", "available": False, "error": str(exc)}


__all__ = [
    "ConversationMessage",
    "ConversationStore",
    "InMemoryConversationStore",
    "InvalidConversationIdError",
    "MAX_MESSAGE_CHARS",
    "RedisConversationStore",
    "ROLE_ASSISTANT",
    "ROLE_USER",
    "conversation_key",
    "get_conversation_store",
    "reset_conversation_store",
    "store_status",
]
