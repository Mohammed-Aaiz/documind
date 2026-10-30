"""Conversation store: isolation, bounds, expiry and honest fallback.

No Redis server is required.  The Redis backend is exercised through a small
fake that implements exactly the commands the store uses (``rpush``/``ltrim``/
``expire``/``lrange``/``delete``), so the store's own key and TTL discipline is
what is under test.
"""

from __future__ import annotations

import json

import pytest

from session import store as store_module
from session.store import (
    ConversationMessage,
    InMemoryConversationStore,
    InvalidConversationIdError,
    RedisConversationStore,
    conversation_key,
    get_conversation_store,
    reset_conversation_store,
)


class FakeRedis:
    """Minimal async Redis list implementation, enough for the store."""

    def __init__(self, *, fail_ping: bool = False) -> None:
        self.lists: dict[str, list[str]] = {}
        self.expiry: dict[str, int] = {}
        self.deleted: list[str] = []
        self.fail_ping = fail_ping
        self.commands: list[str] = []

    async def rpush(self, key: str, value: str) -> int:
        self.commands.append("rpush")
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def ltrim(self, key: str, start: int, end: int) -> None:
        self.commands.append("ltrim")
        items = self.lists.get(key, [])
        # Redis LTRIM uses inclusive, negative-capable indexes.
        n = len(items)
        lo = max(0, n + start if start < 0 else start)
        hi = n + end if end < 0 else end
        self.lists[key] = items[lo : hi + 1]

    async def expire(self, key: str, ttl: int) -> bool:
        self.commands.append("expire")
        self.expiry[key] = ttl
        return True

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        self.commands.append("lrange")
        return list(self.lists.get(key, []))

    async def delete(self, key: str) -> int:
        self.commands.append("delete")
        self.deleted.append(key)
        self.expiry.pop(key, None)
        return 1 if self.lists.pop(key, None) is not None else 0

    async def ping(self) -> bool:
        if self.fail_ping:
            raise ConnectionError("redis is not running")
        return True


class TestKeySafety:
    def test_key_embeds_the_owner(self):
        key = conversation_key("user-1", "session-1")
        assert key == "documind:conversation:user-1:session-1"

    @pytest.mark.parametrize("bad", ["", "a:b", "a b", "../etc", "x" * 65])
    def test_unsafe_identifiers_are_rejected(self, bad):
        with pytest.raises(InvalidConversationIdError):
            conversation_key(bad, "session-1")

    def test_uuid_shaped_ids_are_accepted(self):
        key = conversation_key("6f1a1d9c-8f2b-4b1e-9c3a-1234567890ab", "chat_01")
        assert key.endswith("chat_01")


class TestRedisStore:
    @pytest.mark.asyncio
    async def test_history_round_trips_roles_and_content(self):
        client = FakeRedis()
        store = RedisConversationStore(client)
        await store.append("u1", "s1", ConversationMessage("user", "How often?"))
        await store.append("u1", "s1", ConversationMessage("assistant", "Every 30 days."))

        messages = await store.history("u1", "s1")
        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[1].content == "Every 30 days."

    @pytest.mark.asyncio
    async def test_users_are_isolated_by_key(self):
        client = FakeRedis()
        store = RedisConversationStore(client)
        await store.append("u1", "s1", ConversationMessage("user", "owner one"))
        await store.append("u2", "s1", ConversationMessage("user", "owner two"))

        assert [m.content for m in await store.history("u1", "s1")] == ["owner one"]
        assert [m.content for m in await store.history("u2", "s1")] == ["owner two"]
        assert set(client.lists) == {
            "documind:conversation:u1:s1",
            "documind:conversation:u2:s1",
        }

    @pytest.mark.asyncio
    async def test_history_is_trimmed_and_ttl_is_set(self):
        client = FakeRedis()
        store = RedisConversationStore(client)
        for i in range(6):
            await store.append(
                "u1", "s1", ConversationMessage("user", f"q{i}"), limit=3, ttl_seconds=60
            )

        messages = await store.history("u1", "s1")
        assert [m.content for m in messages] == ["q3", "q4", "q5"]
        # The stored list itself is trimmed, not only the read.
        stored = client.lists["documind:conversation:u1:s1"]
        assert len(stored) == 3
        assert client.expiry["documind:conversation:u1:s1"] == 60
        assert json.loads(stored[-1])["role"] == "user"

    @pytest.mark.asyncio
    async def test_corrupt_records_are_skipped_not_fatal(self):
        client = FakeRedis()
        store = RedisConversationStore(client)
        key = conversation_key("u1", "s1")
        client.lists[key] = [
            "not json",
            json.dumps({"role": "wizard", "content": "ignored"}),
            json.dumps({"role": "user", "content": "kept"}),
        ]
        messages = await store.history("u1", "s1")
        assert [m.content for m in messages] == ["kept"]

    @pytest.mark.asyncio
    async def test_clear_deletes_only_the_owners_key(self):
        client = FakeRedis()
        store = RedisConversationStore(client)
        await store.append("u1", "s1", ConversationMessage("user", "a"))
        await store.append("u2", "s1", ConversationMessage("user", "b"))

        await store.clear("u1", "s1")
        assert client.deleted == ["documind:conversation:u1:s1"]
        assert await store.history("u1", "s1") == []
        assert len(await store.history("u2", "s1")) == 1


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_append_is_bounded_by_limit(self):
        store = InMemoryConversationStore()
        for i in range(5):
            await store.append("u1", "s1", ConversationMessage("user", f"q{i}"), limit=2)
        assert [m.content for m in await store.history("u1", "s1")] == ["q3", "q4"]

    @pytest.mark.asyncio
    async def test_expired_conversation_is_empty_and_dropped(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr(store_module.time, "monotonic", lambda: clock["now"])

        store = InMemoryConversationStore()
        await store.append("u1", "s1", ConversationMessage("user", "old"), ttl_seconds=10)
        clock["now"] += 11

        assert await store.history("u1", "s1") == []
        assert "documind:conversation:u1:s1" not in store._entries

    @pytest.mark.asyncio
    async def test_message_content_is_capped(self):
        store = InMemoryConversationStore()
        await store.append(
            "u1", "s1", ConversationMessage("user", "x" * (store_module.MAX_MESSAGE_CHARS + 50))
        )
        (message,) = await store.history("u1", "s1")
        assert len(message.content) == store_module.MAX_MESSAGE_CHARS


class TestStoreSelection:
    @pytest.mark.asyncio
    async def test_unreachable_redis_falls_back_and_says_so(self, monkeypatch):
        import redis.asyncio as redis_async

        monkeypatch.setattr(
            redis_async.Redis,
            "from_url",
            classmethod(lambda cls, *a, **k: FakeRedis(fail_ping=True)),
        )
        reset_conversation_store()

        store = await get_conversation_store()
        status = await store.status()
        assert isinstance(store, InMemoryConversationStore)
        assert status["backend"] == "memory"
        assert "redis is not running" in (status["error"] or "")

        # The fallback still remembers the conversation.
        await store.append("u1", "s1", ConversationMessage("user", "kept anyway"))
        assert [m.content for m in await store.history("u1", "s1")] == ["kept anyway"]

    @pytest.mark.asyncio
    async def test_reachable_redis_is_used_and_reported(self, monkeypatch):
        import redis.asyncio as redis_async

        client = FakeRedis()
        monkeypatch.setattr(
            redis_async.Redis, "from_url", classmethod(lambda cls, *a, **k: client)
        )
        reset_conversation_store()

        store = await get_conversation_store()
        assert isinstance(store, RedisConversationStore)
        assert (await store.status())["backend"] == "redis"


@pytest.fixture(autouse=True)
def _reset_store():
    reset_conversation_store()
    yield
    reset_conversation_store()
