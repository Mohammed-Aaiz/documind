"""Cold speech-model loading and decoding must both leave the event loop free."""
import io
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.datastructures import UploadFile

import voice


@pytest.mark.asyncio
async def test_cold_loader_and_decoder_run_on_workers_and_temp_audio_is_removed(monkeypatch):
    loop_thread = threading.get_ident()
    audio = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
    model, used_paths = object(), []
    def cold_load():
        assert threading.get_ident() != loop_thread, "Cold model loading blocked the event loop"
        return model
    def decode(actual_model, path):
        assert threading.get_ident() != loop_thread, "Decoding blocked the event loop"
        assert actual_model is model and Path(path).read_bytes() == audio
        used_paths.append(Path(path))
        return "Synthetic test transcript", "en", 1.2345
    monkeypatch.setattr(voice, "_load_model", cold_load)
    monkeypatch.setattr(voice, "_transcribe_path", decode)
    result = await voice.transcribe(SimpleNamespace(id="test-owner"),
                                    UploadFile(filename="sample.wav", file=io.BytesIO(audio)))
    assert result.text == "Synthetic test transcript" and result.language == "en"
    assert used_paths and all(not path.exists() for path in used_paths)


@pytest.mark.asyncio
async def test_unavailable_cold_loader_has_sanitized_service_error(monkeypatch):
    def unavailable():
        raise RuntimeError("private model path")
    monkeypatch.setattr(voice, "_load_model", unavailable)
    audio = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
    with pytest.raises(voice.HTTPException) as caught:
        await voice.transcribe(SimpleNamespace(id="test-owner"),
                               UploadFile(filename="sample.wav", file=io.BytesIO(audio)))
    assert caught.value.status_code == 503 and "private" not in caught.value.detail
