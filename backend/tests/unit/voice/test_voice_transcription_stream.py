"""Regression tests for local Whisper progress and WebRTC voice-turn order.

Whisper remains a single post-utterance decode. These tests pin that partial
snapshots are cumulative segments from the same decode, the final transcript
is authoritative, and a cancelled turn cannot publish stale snapshots.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import voice
import voice_webrtc
from generation.types import AnswerFormat


class _FakeModel:
    def __init__(self, segments, *, language="en", duration=1.25):
        self.segments = iter(segments)
        self.info = SimpleNamespace(language=language, duration=duration)
        self.options = None

    def transcribe(self, _path, **options):
        self.options = options
        return self.segments, self.info


def test_whisper_partial_snapshots_come_from_the_final_segment_join():
    model = _FakeModel(
        [
            SimpleNamespace(text="What is"),
            SimpleNamespace(text=" the interval?"),
        ]
    )
    snapshots = []

    result = voice._transcribe_path_with_partials(
        model, "unused.wav", lambda text, index, language: snapshots.append(
            (text, index, language)
        )
    )

    assert result == ("What is the interval?", "en", 1.25)
    assert snapshots == [
        ("What is", 1, "en"),
        ("What is the interval?", 2, "en"),
    ]
    assert model.options == {"beam_size": 5, "vad_filter": True}


def test_partial_callback_failure_does_not_discard_final_transcript():
    model = _FakeModel([SimpleNamespace(text="grounded words")])

    def fail_progress(_text, _index, _language):
        raise RuntimeError("control channel closed")

    assert voice._transcribe_path_with_partials(
        model, "unused.wav", fail_progress
    ) == ("grounded words", "en", 1.25)


pytestmark_webrtc = pytest.mark.skipif(
    not voice_webrtc.AIORTC_AVAILABLE, reason="aiortc is not installed"
)


class _FakeDb:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def commit(self):
        return None


@pytestmark_webrtc
@pytest.mark.asyncio
async def test_webrtc_sends_partial_then_authoritative_transcript_then_answer_delta(
    monkeypatch,
):
    session = voice_webrtc.VoiceWebRTCSession(
        user_id="voice-user",
        session_id=str(uuid.uuid4()),
        answer_format=AnswerFormat.TEN,
    )
    events = []

    async def capture(payload):
        events.append(payload)

    session.send = capture
    answer = SimpleNamespace(answer="Grounded answer [1].", first_token_ms=12)

    async def transcribe(_pcm, *, turn_generation):
        await session._send_partial_transcript(
            turn_generation, "What is the answer?", 1, "en"
        )
        return "What is the answer?", "en", 1.25

    async def answer_stream(_db, **_kwargs):
        yield {"event": "delta", "data": {"text": "Grounded answer "}}
        yield {"event": "delta", "data": {"text": "[1]."}}
        yield {"event": "final", "data": answer}

    class _Wire:
        @staticmethod
        def model_dump():
            return {"sources": [], "answer": answer.answer}

    monkeypatch.setattr(session, "_transcribe", transcribe)
    monkeypatch.setattr(voice_webrtc, "async_session", _FakeDb)
    monkeypatch.setattr(voice_webrtc, "stream_with_memory", answer_stream)
    monkeypatch.setattr(voice_webrtc, "serialize_answer", lambda _answer: _Wire())

    async def no_audio(_text):
        return None

    async def playback_done():
        return None

    monkeypatch.setattr(session, "_stream_speech", no_audio)
    monkeypatch.setattr(session, "_wait_for_playback", playback_done)
    try:
        await session._run_turn(b"\x00\x00" * 160)
    finally:
        await session.close()

    kinds = [event.get("type") for event in events]
    partial_index = kinds.index("transcript_partial")
    final_index = kinds.index("transcript")
    thinking_index = next(
        index
        for index, event in enumerate(events)
        if event.get("type") == "status" and event.get("state") == "thinking"
    )
    delta_indices = [index for index, kind in enumerate(kinds) if kind == "answer_delta"]

    assert partial_index < final_index < thinking_index < delta_indices[0] < delta_indices[1]
    assert events[partial_index]["provisional"] is True
    assert events[partial_index]["text"] == "What is the answer?"
    assert events[final_index]["text"] == "What is the answer?"
    assert [events[index]["text"] for index in delta_indices] == [
        "Grounded answer ",
        "[1].",
    ]


@pytestmark_webrtc
@pytest.mark.asyncio
async def test_cancelled_turn_does_not_publish_stale_whisper_partials(monkeypatch):
    session = voice_webrtc.VoiceWebRTCSession(
        user_id="voice-user",
        session_id=str(uuid.uuid4()),
        answer_format=AnswerFormat.TEN,
    )
    events = []

    async def capture(payload):
        events.append(payload)

    session.send = capture
    monkeypatch.setattr(voice, "_load_model", lambda: object())

    def decode(_model, _path, on_partial):
        on_partial("Before interruption", 1, "en")
        session._turn_generation += 1  # a barge-in invalidates this generation
        on_partial("Stale continuation", 2, "en")
        return "Before interruption Stale continuation", "en", 2.0

    monkeypatch.setattr(voice, "_transcribe_path_with_partials", decode)
    try:
        result = await session._transcribe(
            b"\x00\x00" * 160, turn_generation=session._turn_generation
        )
    finally:
        await session.close()

    assert result[0] == "Before interruption Stale continuation"
    partials = [event for event in events if event.get("type") == "transcript_partial"]
    assert [event["text"] for event in partials] == ["Before interruption"]
