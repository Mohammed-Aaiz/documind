"""WebRTC session state machine: VAD barge-in and turn hand-off.

A real ``RTCPeerConnection`` is created (it negotiates nothing here), but no
network, no model and no database are touched: ``send``, the VAD and the turn
body are stubbed.  What is asserted is the *decision* — speech over the answer
cancels the in-flight turn and drops queued audio — not a mock's return value.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

import voice_webrtc
from generation.types import AnswerFormat

pytestmark = pytest.mark.skipif(
    not voice_webrtc.AIORTC_AVAILABLE, reason="aiortc is not installed"
)


class _FakeVad:
    """Returns a scripted probability for every window it is given."""

    def __init__(self, probability: float) -> None:
        self.probability = probability
        self.windows = 0

    def feed(self, pcm16: bytes):
        # The session hands whole 20 ms frames; report them one at a time.
        self.windows += len(pcm16) // voice_webrtc.FRAME_BYTES
        return [
            (pcm16[index : index + voice_webrtc.FRAME_BYTES], self.probability)
            for index in range(0, len(pcm16), voice_webrtc.FRAME_BYTES)
        ]


@pytest.fixture()
async def session():
    instance = voice_webrtc.VoiceWebRTCSession(
        user_id="user-1",
        session_id=str(uuid.uuid4()),
        answer_format=AnswerFormat.TEN,
    )
    events: list[dict] = []

    async def capture(payload: dict) -> None:
        events.append(payload)

    instance.send = capture  # type: ignore[method-assign]
    try:
        yield instance, events
    finally:
        await instance.close()


class TestBargeIn:
    async def test_cancelled_turn_is_reported_and_audio_is_dropped(self, session):
        instance, events = session
        instance.track.enqueue_pcm(b"\x01\x00" * 1600, voice_webrtc.SAMPLE_RATE)
        turn = asyncio.create_task(asyncio.sleep(30))
        instance._turn_task = turn

        running = await instance.barge_in("vad")

        assert running is True
        assert turn.cancelled()
        assert instance.track.speaking is False
        assert any(event["type"] == "interrupted" for event in events)
        assert any(
            event.get("type") == "status" and event.get("state") == "listening"
            for event in events
        )

    async def test_barge_in_with_no_turn_is_a_no_op(self, session):
        instance, events = session
        assert await instance.barge_in("client") is False
        assert events == []

    async def test_sustained_speech_while_speaking_cancels_the_turn(self, session):
        instance, events = session
        instance._vad = _FakeVad(0.95)
        instance._turn_task = asyncio.create_task(asyncio.sleep(30))

        windows = instance._min_speech_windows
        for _ in range(windows):
            await instance._on_pcm(b"\x00\x00" * voice_webrtc.FRAME_SAMPLES)

        assert instance._turn_task is None
        assert instance._barged_this_utterance is True
        assert any(event["type"] == "interrupted" for event in events)

    async def test_silence_never_barges_in(self, session):
        instance, events = session
        instance._vad = _FakeVad(0.01)
        turn = asyncio.create_task(asyncio.sleep(30))
        instance._turn_task = turn

        for _ in range(instance._min_speech_windows + 5):
            await instance._on_pcm(b"\x00\x00" * voice_webrtc.FRAME_SAMPLES)

        assert this_running(turn)
        assert not any(event["type"] == "interrupted" for event in events)
        turn.cancel()


def this_running(task: asyncio.Task) -> bool:
    return not task.done()


class TestTurnHandoff:
    async def test_silence_after_speech_starts_a_turn_with_the_utterance(
        self, session
    ):
        instance, _events = session
        started: list[bytes] = []

        async def fake_turn(pcm: bytes) -> None:
            started.append(pcm)

        instance._run_turn = fake_turn  # type: ignore[method-assign]
        instance._speech_windows = instance._min_speech_windows
        instance._utterance.extend(b"\x02\x00" * voice_webrtc.FRAME_SAMPLES)
        instance._last_speech = asyncio.get_running_loop().time() - (
            instance._silence_seconds + 0.05
        )

        await instance._finish_utterance()
        assert instance._turn_task is not None
        await instance._turn_task

        assert started and started[0].startswith(b"\x02\x00")
        assert instance._speech_windows == 0

    async def test_too_little_speech_is_not_sent_for_transcription(self, session):
        instance, _events = session
        started: list[bytes] = []

        async def fake_turn(pcm: bytes) -> None:  # pragma: no cover - must not run
            started.append(pcm)

        instance._run_turn = fake_turn  # type: ignore[method-assign]
        instance._speech_windows = 1
        instance._utterance.extend(b"\x02\x00" * 10)

        await instance._finish_utterance()

        assert started == []
        assert instance._turn_task is None

    async def test_a_second_turn_is_not_queued_over_a_running_one(self, session):
        instance, _events = session
        instance._turn_task = asyncio.create_task(asyncio.sleep(30))
        instance._speech_windows = instance._min_speech_windows
        instance._utterance.extend(b"\x02\x00" * 64)

        await instance._finish_utterance()

        assert instance._turn_task is not None
        assert not instance._turn_task.done()
        instance._turn_task.cancel()


class TestPlaybackWait:
    async def test_wait_ends_after_the_queued_audio_is_sent(self, session):
        instance, _events = session
        instance.track.enqueue_pcm(b"\x00\x00" * voice_webrtc.FRAME_SAMPLES, voice_webrtc.SAMPLE_RATE)
        assert instance.track.speaking is True

        consumer = asyncio.create_task(instance.track.recv())
        await instance._wait_for_playback()

        assert consumer.done()
        assert instance.track.speaking is False

    async def test_wait_returns_immediately_when_nothing_is_queued(self, session):
        instance, _events = session
        loop = asyncio.get_running_loop()
        started = loop.time()

        await instance._wait_for_playback()

        assert loop.time() - started < 0.2


class TestControlChannel:
    async def test_answer_format_can_be_changed_over_the_channel(self, session):
        instance, _events = session
        instance._on_channel_message('{"type": "answer_format", "answerFormat": "15"}')
        assert instance.answer_format is AnswerFormat.FIFTEEN

    async def test_an_invalid_format_is_ignored(self, session):
        instance, _events = session
        instance._on_channel_message('{"type": "answer_format", "answerFormat": "7"}')
        assert instance.answer_format is AnswerFormat.TEN
