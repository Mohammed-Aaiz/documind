"""The WebRTC audio track: clock, PTS, resampling and silence padding.

These tests drive ``recv()`` directly (no peer connection, no network).  They
assert the properties a stuttering/clock-drifting track would violate: constant
frame size, monotonic sample-accurate PTS, silence (never a short frame) on
underrun, and a duration that survives resampling.
"""

from __future__ import annotations

import asyncio
import math
import struct
from fractions import Fraction

import pytest

import voice_webrtc


def _pcm(duration_seconds: float, rate: int, *, amplitude: int = 12000) -> bytes:
    samples = int(rate * duration_seconds)
    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(samples)
    )


class TestTrackClock:
    async def test_frames_are_20ms_and_pts_is_sample_accurate(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            track.enqueue_pcm(_pcm(0.25, voice_webrtc.SAMPLE_RATE), voice_webrtc.SAMPLE_RATE)
            frames = [await track.recv() for _ in range(5)]
        finally:
            track.stop()

        assert [frame.samples for frame in frames] == [voice_webrtc.FRAME_SAMPLES] * 5
        assert [frame.pts for frame in frames] == [
            voice_webrtc.FRAME_SAMPLES * index for index in range(5)
        ]
        assert {frame.sample_rate for frame in frames} == {voice_webrtc.SAMPLE_RATE}
        assert {frame.time_base for frame in frames} == {
            Fraction(1, voice_webrtc.SAMPLE_RATE)
        }

    async def test_pts_keeps_running_through_silence(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            track.enqueue_pcm(_pcm(0.02, voice_webrtc.SAMPLE_RATE), voice_webrtc.SAMPLE_RATE)
            first = await track.recv()
            silent = await track.recv()
        finally:
            track.stop()

        assert first.pts == 0
        assert silent.pts == voice_webrtc.FRAME_SAMPLES
        assert bytes(silent.planes[0]) == b"\x00" * voice_webrtc.FRAME_BYTES

    async def test_a_partial_tail_is_padded_not_shortened(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            # 100 samples: half a frame.
            track.enqueue_pcm(b"\x01\x00" * 100, voice_webrtc.SAMPLE_RATE)
            frame = await track.recv()
        finally:
            track.stop()

        payload = bytes(frame.planes[0])
        assert frame.samples == voice_webrtc.FRAME_SAMPLES
        assert payload[:100] == b"\x01\x00" * 50
        assert payload[200:] == b"\x00" * (voice_webrtc.FRAME_BYTES - 200)

    async def test_pacing_waits_for_the_clock(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            started = asyncio.get_running_loop().time()
            await track.recv()
            await track.recv()
            await track.recv()
            elapsed = asyncio.get_running_loop().time() - started
        finally:
            track.stop()

        # Two frame intervals elapse between the first and third frame.
        assert elapsed >= 2 * voice_webrtc.FRAME_SECONDS * 0.8


class TestTrackBuffer:
    def test_resampling_preserves_duration(self):
        # 0.5 s at 22.05 kHz must remain 0.5 s at 16 kHz.  A naive concatenation
        # of flushed PyAV frames doubled it (measured 1.004 s).
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            track.enqueue_pcm(_pcm(0.5, 22050), 22050)
            assert 450 <= track.queued_ms <= 550
        finally:
            track.stop()

    def test_clear_drops_queued_audio_and_reports_not_speaking(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        try:
            track.enqueue_pcm(_pcm(0.2, 16000), 16000)
            assert track.speaking is True
            track.clear()
            assert track.speaking is False
            assert track.queued_ms == 0
        finally:
            track.stop()

    def test_stop_ends_the_track(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        track.stop()
        assert track.readyState != "live"


class TestWavWrapper:
    def test_pcm_is_wrapped_as_16k_mono_wav(self):
        import io
        import wave

        wav = voice_webrtc.pcm16_to_wav(b"\x00\x00" * 1600)
        with wave.open(io.BytesIO(wav)) as handle:
            assert handle.getframerate() == voice_webrtc.SAMPLE_RATE
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getnframes() == 1600


class TestTrackRequiresLiveState:
    async def test_recv_refuses_a_stopped_track(self):
        track = voice_webrtc.PiperAudioStreamTrack()
        track.stop()
        with pytest.raises(Exception):
            await track.recv()
