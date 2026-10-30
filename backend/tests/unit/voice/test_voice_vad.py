"""Silero VAD wrapper: windowing, context state and honest availability.

The decision logic is tested with a stub session so the suite stays fast and
independent of the provisioned model; one live test exercises the real ONNX
file when it is present (skipped, never faked, when it is not).
"""

from __future__ import annotations

import struct

import pytest

import voice_vad


class _StubSession:
    """Records the model inputs and returns scripted probabilities."""

    def __init__(self, probability: float) -> None:
        self.probability = probability
        self.inputs: list[dict] = []

    def run(self, _outputs, feeds):
        self.inputs.append({key: value.copy() for key, value in feeds.items()})
        import numpy as np

        return (
            np.array([[self.probability]], dtype="float32"),
            feeds["state"],
        )


def _silence_windows(count: int) -> bytes:
    return b"\x00" * (voice_vad.WINDOW_BYTES * count)


@pytest.fixture()
def stub_vad(monkeypatch):
    session = _StubSession(0.9)
    monkeypatch.setattr(voice_vad, "_session", session)
    monkeypatch.setattr(voice_vad, "_session_loaded", True)
    monkeypatch.setattr(voice_vad, "_session_error", None)
    return session


class TestWindowing:
    def test_one_window_requires_exactly_512_samples(self, stub_vad):
        vad = voice_vad.SileroVad(threshold=0.5)
        with pytest.raises(ValueError):
            vad.probability(b"\x00" * (voice_vad.WINDOW_BYTES - 2))

    def test_feed_buffers_a_partial_window(self, stub_vad):
        vad = voice_vad.SileroVad(threshold=0.5)
        assert vad.feed(b"\x00" * (voice_vad.WINDOW_BYTES // 2)) == []
        windows = vad.feed(b"\x00" * (voice_vad.WINDOW_BYTES // 2))
        assert len(windows) == 1
        assert len(windows[0][0]) == voice_vad.WINDOW_BYTES

    def test_model_input_prepends_64_samples_of_context(self, stub_vad):
        # The v5 ONNX export needs 64 context samples before the 512 new ones;
        # feeding 512 alone returned ~0.001 for loud speech (measured).
        vad = voice_vad.SileroVad(threshold=0.5)
        vad.probability(b"\x00" * voice_vad.WINDOW_BYTES)
        first = stub_vad.inputs[0]["input"]
        assert first.shape == (1, voice_vad.WINDOW_SAMPLES + voice_vad.CONTEXT_SAMPLES)

        vad.probability(b"\x00" * voice_vad.WINDOW_BYTES)
        second = stub_vad.inputs[1]["input"]
        assert second.shape == (1, voice_vad.WINDOW_SAMPLES + voice_vad.CONTEXT_SAMPLES)

    def test_reset_clears_context_and_state(self, stub_vad):
        vad = voice_vad.SileroVad(threshold=0.5)
        vad.probability(b"\x00" * voice_vad.WINDOW_BYTES)
        vad.reset()
        assert not vad._context.any()
        assert not vad._state.any()


class TestDecision:
    def test_threshold_is_inclusive_and_configurable(self, monkeypatch):
        session = _StubSession(0.5)
        monkeypatch.setattr(voice_vad, "_session", session)
        monkeypatch.setattr(voice_vad, "_session_loaded", True)

        assert voice_vad.SileroVad(threshold=0.5).is_speech(b"\x00" * voice_vad.WINDOW_BYTES)
        assert not voice_vad.SileroVad(threshold=0.6).is_speech(
            b"\x00" * voice_vad.WINDOW_BYTES
        )


class TestAvailability:
    def test_a_missing_model_is_reported_not_guessed(self, monkeypatch, tmp_path):
        missing = tmp_path / "absent.onnx"
        monkeypatch.setattr(voice_vad, "model_path", lambda: missing)
        monkeypatch.setattr(voice_vad, "_session", None)
        monkeypatch.setattr(voice_vad, "_session_loaded", False)
        monkeypatch.setattr(voice_vad, "_session_error", None)

        status = voice_vad.vad_status()

        assert status["available"] is False
        assert "not found" in status["error"]
        with pytest.raises(voice_vad.VadUnavailable):
            voice_vad.SileroVad()

    def test_status_names_the_engine_it_would_use(self, stub_vad):
        status = voice_vad.vad_status()
        assert status["engine"] == "silero-onnx"
        assert status["available"] is True


class TestLiveModel:
    """Runs the real model when it is provisioned (skips otherwise)."""

    @pytest.fixture(autouse=True)
    def _require_model(self, monkeypatch):
        monkeypatch.setattr(voice_vad, "_session", None)
        monkeypatch.setattr(voice_vad, "_session_loaded", False)
        monkeypatch.setattr(voice_vad, "_session_error", None)
        if not voice_vad.model_path().is_file():
            pytest.skip("Silero VAD model is not provisioned")

    def test_silence_is_not_detected_as_speech(self):
        vad = voice_vad.SileroVad(threshold=0.5)
        windows = vad.feed(_silence_windows(50))
        assert windows, "the model produced no windows"
        assert all(probability < 0.5 for _window, probability in windows)

    def test_a_tone_is_reported_with_a_probability_in_range(self):
        # A pure tone is not speech, so the assertion is about the contract
        # (a real probability), not about detecting it.
        import math

        pcm = b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * i / 16000)))
            for i in range(voice_vad.WINDOW_SAMPLES * 10)
        )
        vad = voice_vad.SileroVad(threshold=0.5)
        windows = vad.feed(pcm)
        assert len(windows) == 10
        assert all(0.0 <= probability <= 1.0 for _window, probability in windows)
