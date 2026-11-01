"""Recoverable provider failures must retain safe, useful protocol information."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from conversation import routes
from generation.types import GenerationUnavailableError


def limited(delay=None):
    error = GenerationUnavailableError("private upstream body/API credential")
    error.status_code = 429
    error.retry_after_seconds = delay
    return error


@pytest.mark.parametrize("delay,expected", [(1.2, "2"), (-10, "0"), (900, "300"),
    (None, None), ("nan", None), (float("inf"), None), ("untrusted", None)])
def test_rate_limit_is_sanitized_and_retry_delay_is_bounded(delay, expected):
    response = routes._http_error(limited(delay))
    assert response.status_code == 429
    assert (response.headers or {}).get("Retry-After") == expected
    assert "rate limited" in response.detail
    assert "private upstream" not in response.detail


def test_other_provider_failure_still_has_generic_unavailable_contract():
    response = routes._http_error(GenerationUnavailableError("private server details"))
    assert response.status_code == 503
    assert "private" not in response.detail and response.headers is None


@pytest.mark.asyncio
async def test_rest_failure_rolls_back_and_retains_429(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(routes, "answer_with_memory", AsyncMock(side_effect=limited(3.1)))
    with pytest.raises(routes.HTTPException) as caught:
        await routes.ask_in_conversation(str(uuid4()), routes.AskConversationRequest(question="Explain current"),
                                         SimpleNamespace(id=uuid4()), db)
    assert caught.value.status_code == 429 and caught.value.headers == {"Retry-After": "4"}
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_sse_emits_recoverable_error_without_leaking_upstream_text(monkeypatch):
    async def failed(*args, **kwargs):
        yield {"event": "token", "data": {"text": "Provisional"}}
        raise limited(2.5)
    monkeypatch.setattr(routes, "require_session", AsyncMock())
    monkeypatch.setattr(routes, "stream_with_memory", failed)
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    response = await routes.stream_in_conversation(str(uuid4()),
        routes.AskConversationRequest(question="Explain current"),
        SimpleNamespace(is_disconnected=AsyncMock(return_value=False)), SimpleNamespace(id=uuid4()), db)
    events = [item async for item in response.body_iterator]
    error = json.loads(events[-1].split("data: ", 1)[1])
    assert error["code"] == "429" and error["retryAfterSeconds"] == 3
    assert "rate limited" in error["message"] and "private" not in "".join(events)
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_rate_limit_returns_to_listening_without_claiming_missing_engine():
    from voice_webrtc import VoiceWebRTCSession
    events = []
    async def status(state):
        events.append(("status", state))
    async def error(code, message):
        events.append((code, message))
    instance = SimpleNamespace(_turn_generation=0, send_status=status, send_error=error,
                               _transcribe=AsyncMock(side_effect=limited()))
    await VoiceWebRTCSession._run_turn(instance, b"\x00\x00" * 160)
    assert events[-1] == ("status", "listening")
    assert any(code == "rate_limited" for code, _ in events)
    assert not any(code == "engine_unavailable" for code, _ in events)
