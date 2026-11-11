"""Written diagrams survive while WebRTC speaks only their surrounding prose."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import voice_webrtc


@pytest.mark.parametrize(("answer", "expected"), [
    ("Wind turns the rotor.\n```text\nWind [1]\n |\nRotor [1]\n```\nThe shaft drives a generator.",
     "Wind turns the rotor.\nThe shaft drives a generator."),
    ("Before.\n```text\nFirst drawing\n```\nBetween.\n```text\nSecond drawing\n```\nAfter.",
     "Before.\nBetween.\nAfter."),
    ("Supported explanation.\n```text\nAn unfinished drawing\n+----+", "Supported explanation."),
    ("```text\nA drawing without prose\n```", "The diagram is available in the written answer."),
    ("```python\nprint('example')\n```\nA code explanation.",
     "```python\nprint('example')\n```\nA code explanation."),
    ("Plain supported explanation [1].", "Plain supported explanation [1]."),
    (" \n", ""),
])
def test_spoken_answer_omits_text_figures_without_eating_following_prose(answer, expected):
    assert voice_webrtc._spoken_answer_text(answer) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(("written", "spoken"), [
    ("Wind turns the rotor [1].\n```text\nWind [1]\n |\nRotor [1]\n```\nThe shaft drives a generator [2].",
     "Wind turns the rotor [1].\nThe shaft drives a generator [2]."),
    ("```text\nWind [1]\n |\nRotor [1]\n```", "The diagram is available in the written answer."),
    ("", None),
])
async def test_real_turn_sends_full_written_answer_but_never_speaks_the_drawing(monkeypatch, written, spoken):
    db = SimpleNamespace(commit=AsyncMock())

    @asynccontextmanager
    async def session():
        yield db

    answer = SimpleNamespace(answer=written, first_token_ms=None)

    async def stream(*args, **kwargs):
        yield {"event": "final", "data": answer}

    monkeypatch.setattr(voice_webrtc, "async_session", session)
    monkeypatch.setattr(voice_webrtc, "stream_with_memory", stream)
    monkeypatch.setattr(voice_webrtc, "serialize_answer", lambda result: SimpleNamespace(
        model_dump=lambda: {"answer": result.answer, "sources": []},
    ))
    instance = SimpleNamespace(
        _turn_generation=0, user_id="test-owner", session_id="test-session",
        answer_format="10", workspace="student", task="answer",
        _transcribe=AsyncMock(return_value=("Explain wind power with a diagram.", "en", 1.0)),
        send=AsyncMock(), send_status=AsyncMock(), send_error=AsyncMock(),
        _stream_speech=AsyncMock(), _wait_for_playback=AsyncMock(),
    )

    await voice_webrtc.VoiceWebRTCSession._run_turn(instance, b"\x00\x00" * 320)

    db.commit.assert_awaited_once()
    payloads = [call.args[0] for call in instance.send.await_args_list]
    assert next(payload for payload in payloads if payload["type"] == "answer")["answer"] == written
    instance.send_error.assert_not_awaited()
    if spoken is None:
        instance._stream_speech.assert_not_awaited()
        instance._wait_for_playback.assert_not_awaited()
    else:
        instance._stream_speech.assert_awaited_once_with(spoken)
        instance._wait_for_playback.assert_awaited_once()
    assert instance.send_status.await_args_list[-1].args == ("listening",)
