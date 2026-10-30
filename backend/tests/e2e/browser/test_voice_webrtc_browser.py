"""Real-browser verification of the WebRTC voice call (fake microphone device).

What this proves that the other layers cannot
---------------------------------------------

``tests/integration/voice/test_voice_webrtc_offer.py`` negotiates with an
``aiortc`` client, and ``src/lib/voiceStream.test.ts`` drives a jsdom fake.
Between them they cover the server and the client logic, but neither runs a
browser: the capture path (``navigator.mediaDevices.getUserMedia`` →
``RTCRtpSender.replaceTrack`` → Opus → server) and the playback element are
assumed, not exercised.  That is exactly where this harness works.

Chromium's own fake audio device supplies the signal:
``--use-file-for-fake-audio-capture=<wav>`` makes a real WAV the microphone, so
the audio the browser sends is a normal WebRTC track produced by the browser
itself — no injected JS, no synthesised frames in Python, no stubbed
``getUserMedia``.

The WAV is synthesised at run time with the provisioned Piper voice, read back
by the server's local Whisper, answered from ``darwin_proper.pdf`` and spoken
through ``PiperAudioStreamTrack``.  The assertions therefore span the whole
loop: browser capture → WebRTC → Silero VAD turn end → STT → LangGraph turn →
TTS → WebRTC playback → phase back to listening.  The conversation is opened
empty, so the transcript cannot satisfy either assertion on its own.

Deliberate limitations
----------------------

* Chromium replays the capture file on a loop, so the signal cannot be timed to
  land inside the assistant's answer.  Acoustic barge-in is covered on the
  server side by ``tests/unit/voice/test_voice_webrtc_session.py`` and
  ``tests/integration/voice/test_voice_webrtc_offer.py``; here the assertion is
  that the control walks ``listening → transcribing → thinking → speaking →
  listening`` with no error notice.
* The fake device is not a physical microphone: hardware echo cancellation and
  real room acoustics remain unverified.

Latency
-------

Every control-channel frame is timestamped with the page's own
``performance.now()``, so the numbers a run prints are measured where the user
experiences them — microphone attach, the server's turn-end window, STT, the
conversation turn, TTS start and playback — instead of being inferred from
Python-side polling.  The report is deliberately not asserted against a bound:
a shared machine's timings are not a contract, and a threshold would fail a run
for being slow rather than for being wrong.

Skipped — never failed — when the live server, Playwright, Chrome or the local
model artifacts are absent, like every other harness in this directory.
"""

from __future__ import annotations

import io
import time
import wave
from pathlib import Path

import pytest

from tests.fixtures import e2e_config
from tests.fixtures.live_server import optional_import, require_live_server

#: Spoken into the fake microphone by the provisioned Piper voice.
QUESTION = "When did Charles Darwin publish On the Origin of Species?"

#: Phrase Whisper must recover from the fake microphone.  The conversation is
#: opened *empty* (no text turn), so anything matching this can only have come
#: from the fake microphone.
TRANSCRIPT_NEEDLE = "Origin of Species"

#: The grounded answer to ``QUESTION`` in ``darwin_proper.pdf``.
ANSWER_NEEDLE = "1859"

#: Silence appended after the spoken question.  Chromium loops the capture file,
#: and a repetition that lands while the turn is still being transcribed is a
#: real barge-in (measured: it cancelled the turn outright at 30 s).  The runway
#: has to outlast a whole turn — local Whisper is ~4 s warm but was measured at
#: ~22 s while the server was busy — so it is deliberately generous.
SILENCE_SECONDS = 120.0

#: The control's ``title`` is the current phase label (VoiceStreamButton.tsx),
#: which makes the phase readable without depending on layout text.
VOICE_BUTTON = 'button[aria-label="Voice conversation"]'

PHASE_IDLE = "Tap to speak"
PHASE_LISTENING = "Listening — pause to send"
PHASE_TRANSCRIBING = "Transcribing…"
PHASE_THINKING = "Thinking…"
PHASE_SPEAKING = "Speaking — speak or tap to interrupt"
PHASE_ERROR = "Voice unavailable"

#: Records every control-channel frame with the browser's own monotonic clock.
#: The hook only observes — each frame is forwarded to the client unchanged —
#: so it cannot alter what the turn does, only what the harness can time.
VOICE_EVENTS_HOOK = """
window.__voiceEvents = [];
(() => {
  const descriptor = Object.getOwnPropertyDescriptor(
    RTCDataChannel.prototype, 'onmessage');
  Object.defineProperty(RTCDataChannel.prototype, 'onmessage', {
    configurable: true,
    get() { return descriptor.get.call(this); },
    set(handler) {
      descriptor.set.call(this, (event) => {
        try {
          const payload = JSON.parse(String(event.data));
          window.__voiceEvents.push({
            t: Math.round(performance.now()),
            type: String(payload.type || ''),
            state: String(payload.state || ''),
          });
        } catch (error) {
          // A non-JSON frame is not part of the measured protocol and the
          // client reports it; dropping it here changes nothing downstream.
        }
        return handler(event);
      });
    },
  });
})();
"""


def _voice_events(page) -> list[dict]:
    """Every control-channel frame the page received, with its own timestamps."""
    return page.evaluate("() => (window.__voiceEvents || []).slice()")


def _turn_marks(events: list[dict]) -> dict[str, int]:
    """Page-clock timestamp of each protocol mark of the first turn.

    ``status`` frames are keyed by their state: the server also reports
    ``listening`` when the microphone attaches, so a bare ``listening`` mark
    would find the start of the turn instead of its end.
    """

    def key(entry: dict) -> str:
        return f"{entry['type']}:{entry['state']}" if entry.get("state") else entry["type"]

    def first(mark: str, start: int = 0) -> int:
        for index in range(start, len(events)):
            if key(events[index]) == mark:
                return index
        return -1

    order = [
        ("transcribing", "status:transcribing"),
        ("transcript", "transcript"),
        ("answer", "answer"),
        ("speaking", "status:speaking"),
        ("listening", "status:listening"),
    ]
    marks: dict[str, int] = {}
    cursor = 0
    for name, mark in order:
        index = first(mark, cursor)
        assert index >= 0, (
            f"the turn never reported {mark!r}; frames seen: "
            f"{[key(entry) for entry in events]}"
        )
        marks[name] = int(events[index]["t"])
        cursor = index + 1
    return marks


def _latency_report(marks: dict[str, int], clicked_at: float) -> dict[str, float]:
    """The turn's spans, in milliseconds, all on the page's clock."""
    return {
        "capture + VAD window (click -> transcribing)": marks["transcribing"] - clicked_at,
        "STT (transcribing -> transcript)": marks["transcript"] - marks["transcribing"],
        "conversation turn (transcript -> answer)": marks["answer"] - marks["transcript"],
        "TTS start (answer -> speaking)": marks["speaking"] - marks["answer"],
        "playback (speaking -> listening)": marks["listening"] - marks["speaking"],
        "turn total (transcribing -> listening)": marks["listening"] - marks["transcribing"],
        "end to end (click -> listening)": marks["listening"] - clicked_at,
    }


def _phase(page) -> str:
    """The phase label the control currently shows.

    A short timeout keeps a control that has left the DOM (the page returned to
    the homepage) a clear failure instead of a 30 s Playwright hang.
    """
    try:
        return page.locator(VOICE_BUTTON).get_attribute("title", timeout=5_000) or ""
    except Exception:
        return "(control absent)"


def _message_area_text(page) -> str:
    """Text of the scrollable transcript area (never the always-mounted drawer)."""
    return page.evaluate(
        """() => {
            const els = document.querySelectorAll(
                '[class*="overflow-y-auto"][class*="px-4"][class*="py-4"]');
            return els.length ? els[els.length - 1].innerText : '';
        }"""
    )


def _state(page) -> str:
    """One-line description of the page, for failure messages."""
    try:
        body = " | ".join(page.inner_text("body")[:300].splitlines())
    except Exception as exc:  # pragma: no cover - only on a broken page
        body = f"(unreadable: {exc})"
    return f"phase={_phase(page)!r} notice={_notice_text(page)!r} body={body!r}"


def _notice_text(page) -> str:
    """Any warning/error the voice control is showing, or an empty string."""
    return page.evaluate(
        """() => {
            const button = document.querySelector(
                'button[aria-label="Voice conversation"]');
            if (!button) return '';
            const box = button.closest('div.flex.flex-col');
            if (!box) return '';
            return Array.from(box.querySelectorAll('span[role="status"]'))
                .map((el) => el.innerText.trim())
                .filter(Boolean)
                .join(' | ');
        }"""
    )


def _poll(
    page,
    predicate,
    observed: set[str],
    *,
    timeout: float,
    interval: float = 0.15,
    label: str = "",
) -> bool:
    """Poll ``predicate`` until true, recording every phase label seen.

    ``observed`` is how the test proves the control *passed through* a phase it
    is no longer in: a single snapshot after the turn would only ever see
    ``listening``.
    """
    deadline = time.monotonic() + timeout
    last_report = 0.0
    while True:
        current = _phase(page)
        if current:
            observed.add(current)
        if predicate():
            return True
        now = time.monotonic()
        if label and now - last_report >= 15.0:
            last_report = now
            print(
                f"[poll:{label}] phase={current!r} remaining={deadline - now:.0f}s",
                flush=True,
            )
        if now >= deadline:
            return False
        time.sleep(interval)


def _require_local_artifacts() -> None:
    """Skip unless the server's own models are provisioned locally.

    The harness synthesises its capture file with the same Piper voice the
    server speaks with, so a missing artifact is an environment gap, not a test
    failure.
    """
    import voice
    import voice_vad

    voice_file = voice.local_tts_model_path()
    if not voice_file.is_file():
        pytest.skip(
            f"provisioned Piper voice not found at {voice_file} "
            "(python -m piper.download_voices en_US-ljspeech-medium --data-dir models/tts)"
        )
    vad_file = voice_vad.model_path()
    if not vad_file.is_file():
        pytest.skip(f"provisioned Silero VAD model not found at {vad_file}")
    whisper_dir = Path(voice._MODEL_NAME)
    if not whisper_dir.is_dir():
        pytest.skip(f"provisioned Whisper model not found at {whisper_dir}")


def _build_capture_wav(directory: Path) -> Path:
    """Synthesise ``QUESTION`` and pad it to ``SILENCE_SECONDS`` of silence.

    The result is what Chromium feeds to the page as the microphone: real
    speech, at Piper's own rate, in the one container the fake device accepts.
    """
    import voice

    speech = voice._synthesize_local_speech_bytes(QUESTION, False)
    with wave.open(io.BytesIO(speech), "rb") as source:
        params = source.getparams()
        spoken_frames = source.readframes(source.getnframes())

    frame_bytes = params.sampwidth * params.nchannels
    silence = b"\x00" * int(params.framerate * SILENCE_SECONDS) * frame_bytes

    path = directory / "voice-question.wav"
    with wave.open(str(path), "wb") as target:
        target.setnchannels(params.nchannels)
        target.setsampwidth(params.sampwidth)
        target.setframerate(params.framerate)
        target.writeframes(spoken_frames + silence)
    return path


def _login(page, base: str) -> None:
    page.goto(base, wait_until="networkidle")
    email = page.locator('input[type="email"]')
    email.wait_for(state="visible", timeout=15_000)
    email.fill(e2e_config.DEMO_USER_EMAIL)
    page.locator('input[type="password"]').fill(e2e_config.DEMO_USER_PASSWORD)
    page.locator('button[type="submit"]').click()
    page.locator('input[placeholder*="Oracle"]').wait_for(state="visible", timeout=20_000)


def _upload_corpus_and_open_conversation(page) -> None:
    """Ingest the fixture PDF, then open an *empty* conversation.

    Both halves matter.  The document gives the voice turn evidence to answer
    from; the empty conversation gives the voice client the ``sessionId`` its
    call hangs off.  It is opened through the homepage's "New conversation"
    control rather than by sending a text question, so the microphone's turn is
    the first thing in the transcript and every word the assertions look for
    can only have come from the fake microphone.
    """
    page.locator('input[type="file"]').set_input_files(str(e2e_config.DARWIN_PDF))
    page.locator(f"text={e2e_config.DARWIN_PDF.name}").first.wait_for(
        state="visible", timeout=20_000
    )

    # Upload processing is synchronous server-side, so the row's chunk count is
    # the honest "retrieval can see this document" signal; do not assume it.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if "chunks" in page.inner_text("body"):
            break
        time.sleep(1.0)
    else:
        raise AssertionError("the uploaded document never reported chunks")

    page.locator('button[title="New conversation"]').click()
    page.locator('input[placeholder="Ask the Oracle..."]').wait_for(
        state="visible", timeout=20_000
    )


def _run_voice_call(page) -> None:
    """Start the call, speak through the fake microphone, verify the turn."""
    observed: set[str] = set()

    button = page.locator(VOICE_BUTTON)
    button.wait_for(state="visible", timeout=20_000)

    # The client negotiates on mount (VoiceStreamButton's effect), so the idle
    # label after a conversation exists means the SDP answer was accepted and
    # the peer connection is up — before any microphone is attached.
    assert _poll(
        page, lambda: button.is_enabled(), observed, timeout=60_000
    ), "the voice control never became enabled after the conversation was created"
    assert _poll(
        page, lambda: _phase(page) == PHASE_IDLE, observed, timeout=60_000
    ), f"the call never reached idle after negotiation; phase={_phase(page)!r}"
    assert "Voice unavailable" not in _notice_text(page), (
        f"negotiation failed: {_notice_text(page)!r}"
    )

    # The label goes idle as soon as the SDP answer is applied, which is before
    # ICE/DTLS finished.  Attaching the microphone into a half-open connection
    # was measured to deliver no media at all (the server logged the offer and
    # then nothing), so let the peer connection settle first.
    time.sleep(2.5)

    # Measured from the same click the turn is started with, so the reported
    # "end to end" span includes the question the user actually has to speak.
    clicked_at = page.evaluate("() => performance.now()")
    button.click()

    assert _poll(
        page,
        lambda: _phase(page) == PHASE_LISTENING,
        observed,
        timeout=60_000,
        label="listening",
    ), f"the microphone track was never attached; phase={_phase(page)!r}"
    assert button.get_attribute("aria-pressed", timeout=5_000) == "true"

    # 1. The browser's fake microphone → WebRTC → server VAD → Whisper.
    assert _poll(
        page,
        lambda: TRANSCRIPT_NEEDLE in _message_area_text(page),
        observed,
        timeout=120_000,
        label="transcript",
    ), (
        "the spoken question never reached the transcript; "
        f"phases seen: {sorted(observed)}; {_state(page)}"
    )
    assert PHASE_TRANSCRIBING in observed or PHASE_THINKING in observed, (
        f"the control never reported progress; phases seen: {sorted(observed)}"
    )

    # 2. The LangGraph turn answers from the ingested document.
    assert _poll(
        page,
        lambda: ANSWER_NEEDLE in _message_area_text(page),
        observed,
        timeout=120_000,
        label="answer",
    ), (
        "the voice turn produced no grounded answer; "
        f"phases seen: {sorted(observed)}; {_state(page)}"
    )

    # 3. Piper audio played back through the track: the server awaits playback
    #    before reporting `listening`, so seeing both means the turn finished
    #    rather than merely started.
    assert _poll(
        page,
        lambda: PHASE_SPEAKING in observed and _phase(page) == PHASE_LISTENING,
        observed,
        timeout=120_000,
        label="speaking",
    ), (
        "the answer was never spoken back over the track; "
        f"phases seen: {sorted(observed)}; {_state(page)}"
    )

    marks = _turn_marks(_voice_events(page))
    print("[latency] measured on the page's own clock:", flush=True)
    for label, millis in _latency_report(marks, clicked_at).items():
        print(f"[latency] {label:<44} {millis / 1000:6.2f} s", flush=True)

    # Honest capability reporting from the `ready` message.
    assert "Server voice detection unavailable" not in _notice_text(page), (
        "the server reported its VAD as unavailable; the call cannot decide "
        "turn end, so this run cannot verify the transport"
    )

    # 4. Stop the call through the control (client `barge_in` + mic release).
    button.click()
    assert _poll(
        page,
        lambda: _phase(page) == PHASE_IDLE,
        observed,
        timeout=30_000,
        label="stop",
    ), f"stopping the call did not return to idle; phase={_phase(page)!r}"

    # `speaking` is the phase that proves audio flowed; `error` would mean the
    # call broke at some point in the sequence.
    assert PHASE_SPEAKING in observed, f"phases seen: {sorted(observed)}"
    assert PHASE_ERROR not in observed, f"phases seen: {sorted(observed)}"


@pytest.mark.e2e
def test_webrtc_voice_turn_with_fake_microphone(tmp_path):
    """A full duplex turn in a real browser with Chromium's fake microphone.

    Skipped unless the dev server answers at the recorded base URL, Playwright
    and Chrome are installed, and the local TTS/VAD/STT artifacts exist.
    """
    base = e2e_config.base_url()
    require_live_server(base)
    optional_import("playwright", reason="Playwright is not in requirements.txt")
    _require_local_artifacts()

    from playwright.sync_api import sync_playwright

    capture_wav = _build_capture_wav(tmp_path)
    print(f"\n[setup] fake microphone capture: {capture_wav} ({capture_wav.stat().st_size} bytes)")

    token = e2e_config.login(
        e2e_config.DEMO_USER_EMAIL, e2e_config.DEMO_USER_PASSWORD, base
    )
    stale = e2e_config.purge_documents(base, token=token, name=e2e_config.DARWIN_PDF.name)
    print(f"[setup] removed {stale} stale document(s) before upload")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=True,
                args=[
                    # Auto-accept the permission prompt and expose a device.
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    # …and make that device play our synthesized question.
                    f"--use-file-for-fake-audio-capture={capture_wav.as_posix()}",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    permissions=["microphone"],
                )
                # Installed before any page script runs, so the very first
                # negotiated data channel is observed too.
                context.add_init_script(VOICE_EVENTS_HOOK)
                page = context.new_page()
                _login(page, base)
                _upload_corpus_and_open_conversation(page)
                _run_voice_call(page)
            finally:
                browser.close()
    finally:
        removed = e2e_config.purge_documents(
            base, token=token, name=e2e_config.DARWIN_PDF.name
        )
        print(f"[teardown] removed {removed} document(s) after the run")
