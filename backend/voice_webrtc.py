"""Duplex voice conversation over WebRTC (``aiortc``), offline.

Transport
---------

``POST /api/voice/webrtc/offer`` with a JSON body::

    {"sdp": "<offer sdp>", "type": "offer",
     "sessionId": "<conversation id>", "answerFormat": "5" | "10" | "15"}

The server answers with its SDP (``type: "answer"``) and keeps the peer
connection for the life of the call.  ICE uses host candidates only: there is
no STUN/TURN server in the configuration, because the project must run on a
local machine with no external egress.

Media
-----

* **out** — :class:`PiperAudioStreamTrack`, a ``MediaStreamTrack`` that turns
  Piper's PCM chunks into 16 kHz mono ``AudioFrame`` objects on a continuous
  20 ms clock, padding with silence when the queue runs dry so playback never
  drifts or stutters.  * **in** — the browser's microphone track, resampled to 16 kHz mono and fed to
    the local Silero VAD (:mod:`voice_vad`).  The VAD, not the browser, decides
    when a turn ended and when the user talked over the answer.

Signaling requires the browser to include a ``control`` data channel in its
offer: an SDP answer cannot add an SCTP media section, so the channel has to be
negotiated by the offerer.  The server attaches to it and refuses an offer that
lacks it rather than running a call whose events could never reach the client.

Barge-in
--------

When speech is detected while a turn is generating or speaking, the in-flight
turn task is **cancelled** (that is the LangGraph call), the queued TTS audio is
discarded, the client is told over the data channel, and the session returns to
listening.  The same utterance is then transcribed as the next question.

What is real
------------

* STT is the provisioned local Whisper model (``voice._transcribe_path``).
* The answer is ``orchestration.service.answer_with_memory`` — the same
  LangGraph turn, retrieval, verification and conversation history as text.
* TTS is the configured engine (provisioned Piper by default).  For the local
  engine the synthesis generator is consumed incrementally, so audio starts
  before the whole answer has been synthesised.

Failure honesty: a missing model produces an ``error`` event with a code and a
reason; nothing is faked, and no audio is invented.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
import wave
from fractions import Fraction

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

import voice
import voice_vad
from auth.dependencies import CurrentUser
from config import get_settings
from generation.types import AnswerFormat, GenerationUnavailableError
from orchestration.service import (
    ConversationSessionNotFound, SessionBusyError, require_session, stream_with_memory,
)
from conversation.routes import Workspace, ConversationTask, serialize_answer
from session.store import InvalidConversationIdError, conversation_key
from storage.database import async_session, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

try:  # pragma: no cover - exercised only when the optional dependency is absent
    from aiortc import (
        MediaStreamTrack,
        RTCPeerConnection,
        RTCConfiguration,
        RTCSessionDescription,
    )
    from aiortc.mediastreams import MediaStreamError

    AIORTC_AVAILABLE = True
    AIORTC_ERROR: str | None = None
except Exception as exc:  # pragma: no cover
    MediaStreamTrack = object  # type: ignore[assignment,misc]
    RTCPeerConnection = None  # type: ignore[assignment]
    RTCConfiguration = None  # type: ignore[assignment]
    RTCSessionDescription = None  # type: ignore[assignment]

    class MediaStreamError(Exception):  # type: ignore[no-redef]
        """Placeholder so imports do not fail without aiortc."""

    AIORTC_AVAILABLE = False
    AIORTC_ERROR = f"aiortc is not installed: {exc}"


#: The WebRTC audio contract.  Both directions are 16 kHz mono int16, which is
#: what Silero VAD and Whisper consume and what Piper produces (resampled).
SAMPLE_RATE = 16_000
FRAME_SAMPLES = 320  # 20 ms
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE

#: 16-bit mono audio written for the transcription helper.
_STT_SUFFIX = ".wav"


def _looks_like_sdp(sdp: str) -> bool:
    """Cheap structural check, so garbage is refused before a peer is built.

    aiortc parses an arbitrary string into an SDP session with no media
    sections; that would otherwise surface as a channel-negotiation error
    rather than "this is not an offer".
    """
    text = sdp.replace("\r\n", "\n").strip()
    return text.startswith("v=0") and "\nm=" in text


def _frame_pcm(frame) -> bytes:
    """Actual s16 mono bytes of a decoded/resampled frame.

    PyAV allocates a full-size plane buffer for flushed frames while reporting
    only the valid ``samples``; reading the whole plane silently duplicates
    audio (measured: a 0.5 s 22.05 kHz chunk became 1.004 s of queued audio).
    Slicing by ``samples`` keeps the duration honest.
    """
    return bytes(frame.planes[0])[: frame.samples * 2]


def _resample_pcm16(pcm16: bytes, sample_rate: int) -> bytes:
    """Resample mono int16 PCM to 16 kHz with PyAV.

    PyAV is already a dependency (faster-whisper decodes through it); using it
    here means float and stereo inputs are handled by a real resampler rather
    than a hand-written linear interpolation.
    """
    import av

    if sample_rate == SAMPLE_RATE:
        return bytes(pcm16)
    samples = len(pcm16) // 2
    if samples <= 0:
        return b""
    frame = av.AudioFrame(format="s16", layout="mono", samples=samples)
    frame.planes[0].update(bytes(pcm16))
    frame.sample_rate = sample_rate
    frame.pts = 0
    frame.time_base = Fraction(1, sample_rate)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    out: list[bytes] = []
    for converted in resampler.resample(frame):
        out.append(_frame_pcm(converted))
    for converted in resampler.resample(None):
        out.append(_frame_pcm(converted))
    return b"".join(out)


def pcm16_to_wav(pcm16: bytes) -> bytes:
    """Wrap 16 kHz mono int16 PCM in a WAV container (for the STT helper)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm16)
    return buffer.getvalue()


def _decode_audio_bytes_to_pcm(audio: bytes) -> bytes:
    """Decode a WAV/MP3 blob to 16 kHz mono int16 PCM (non-local TTS engines)."""
    import av

    container = av.open(io.BytesIO(audio))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    out: list[bytes] = []
    try:
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                out.append(_frame_pcm(converted))
        for converted in resampler.resample(None):
            out.append(_frame_pcm(converted))
    finally:
        container.close()
    return b"".join(out)


class PiperAudioStreamTrack(MediaStreamTrack):  # type: ignore[misc,valid-type]
    """PCM → ``AudioFrame`` track with a continuous 20 ms clock.

    The track is the only place the output clock exists.  ``recv`` is paced by a
    monotonic deadline (not by the arrival of data), and an underrun yields a
    silent frame instead of a short or repeated one: that is what keeps PTS
    monotonic and stops a browser from hearing a stutter or drifting audio.
    """

    kind = "audio"

    def __init__(self) -> None:
        super().__init__()
        self._buffer = bytearray()
        self._pts = 0
        self._deadline: float | None = None
        self._enqueued_frames = 0
        self._silence_frames = 0

    # -- producer side -----------------------------------------------------

    def enqueue_pcm(self, pcm16: bytes, sample_rate: int) -> None:
        """Queue mono int16 PCM at ``sample_rate``; it is resampled to 16 kHz."""
        converted = _resample_pcm16(pcm16, sample_rate)
        if converted:
            self._buffer.extend(converted)
            self._enqueued_frames += len(converted) // FRAME_BYTES

    @property
    def speaking(self) -> bool:
        """Whether speech audio is queued or currently being played out."""
        return bool(self._buffer)

    @property
    def queued_ms(self) -> int:
        """Buffered audio in milliseconds (diagnostics, never a claim)."""
        return int(len(self._buffer) / 2 / SAMPLE_RATE * 1000)

    def clear(self) -> None:
        """Drop everything queued (barge-in).  PTS is *not* reset: the stream
        clock must keep running or the receiver sees a timestamp jump."""
        self._buffer.clear()

    # -- consumer side -----------------------------------------------------

    def _take_frame(self) -> bytes:
        if len(self._buffer) >= FRAME_BYTES:
            payload = bytes(self._buffer[:FRAME_BYTES])
            del self._buffer[:FRAME_BYTES]
            return payload
        if self._buffer:
            # A partial tail: pad *this* frame and keep the clock intact.
            payload = bytes(self._buffer)
            self._buffer.clear()
            return payload + b"\x00" * (FRAME_BYTES - len(payload))
        self._silence_frames += 1
        return b"\x00" * FRAME_BYTES

    async def recv(self):  # pragma: no cover - exercised through aiortc
        if self.readyState != "live":
            raise MediaStreamError("track is not live")

        import av

        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._deadline is None:
            # The first frame is produced immediately; the clock is then one
            # frame ahead, so every following frame waits its own interval.
            self._deadline = now + FRAME_SECONDS
        else:
            delay = self._deadline - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._deadline += FRAME_SECONDS
            # A suspended event loop must not make the track burst-send the
            # backlog: re-anchor instead of pretending no time passed.
            if self._deadline < loop.time() - 0.5:
                self._deadline = loop.time()

        frame = av.AudioFrame(format="s16", layout="mono", samples=FRAME_SAMPLES)
        frame.planes[0].update(self._take_frame())
        frame.sample_rate = SAMPLE_RATE
        frame.pts = self._pts
        frame.time_base = Fraction(1, SAMPLE_RATE)
        self._pts += FRAME_SAMPLES
        return frame

    def stop(self) -> None:
        self._buffer.clear()
        super().stop()


class WebRTCOfferRequest(BaseModel):
    """SDP offer plus the conversation it belongs to."""

    sdp: str = Field(..., min_length=1, max_length=65536)
    type: str = Field(default="offer")
    sessionId: str = Field(..., min_length=1)
    answerFormat: str = Field(default="10")
    workspace: Workspace = "student"
    task: ConversationTask = "answer"


class WebRTCOfferResponse(BaseModel):
    sdp: str
    type: str
    sessionId: str
    workspace: Workspace = "student"
    vad: dict
    stt: str
    tts: str    #: Live sessions.  A peer connection must stay referenced for its lifetime or
#: it would be garbage-collected mid-call.
_sessions: dict[str, "VoiceWebRTCSession"] = {}

#: Label of the data channel the browser creates for the turn protocol.
CONTROL_CHANNEL_LABEL = "control"


class NegotiationError(ValueError):
    """The offer is well-formed SDP but cannot carry the voice protocol."""


class VoiceWebRTCSession:
    """One WebRTC call: media wiring, VAD state machine and turn task."""

    def __init__(
        self,
        *,
        user_id: str,
        session_id: str,
        answer_format: AnswerFormat,
        workspace: str = "student",
        task: str = "answer",
    ) -> None:
        if not AIORTC_AVAILABLE:  # pragma: no cover
            raise RuntimeError(AIORTC_ERROR or "aiortc unavailable")
        self.id = uuid.uuid4().hex
        self.user_id = user_id
        self.session_id = session_id
        self.answer_format = answer_format
        self.workspace = workspace
        self.task = task
        self._turn_started_at: float | None = None
        self._first_audio_ms: int | None = None
        # No STUN/TURN: host candidates only.  This is what keeps the call on
        # the local machine with no external egress, so it is stated explicitly
        # rather than left to the library default.
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.track = PiperAudioStreamTrack()
        #: Attached when the browser's "control" channel arrives (see
        #: :meth:`_on_data_channel`); an answer cannot create it.
        self.channel = None
        self._ready_announced = False
        self.state = "listening"
        self._turn_task: asyncio.Task | None = None
        # A cancelled turn's native Whisper worker may finish its current
        # decode, but it must not publish partials into a later turn.
        self._turn_generation = 0
        self._reader_task: asyncio.Task | None = None
        self._vad: voice_vad.SileroVad | None = None
        self._vad_error: str | None = None
        self._utterance = bytearray()
        #: Last two silent windows, prepended when speech starts so the first
        #: syllable is not clipped by the detection latency.
        self._preroll: list[bytes] = []
        self._last_speech: float | None = None
        self._speech_windows = 0
        self._barged_this_utterance = False
        self._resampler = None
        self._closed = False
        self._threshold = float(get_settings().vad_threshold)
        self._silence_seconds = max(0.1, get_settings().vad_silence_ms / 1000)
        self._min_speech_windows = max(
            1, int((get_settings().vad_min_speech_ms / 1000) / FRAME_SECONDS)
        )
        self._max_utterance_bytes = int(
            SAMPLE_RATE * 2 * max(1, get_settings().webrtc_max_utterance_seconds)
        )

        self.pc.addTrack(self.track)
        self.pc.on("datachannel", self._on_data_channel)
        self.pc.on("track", self._on_track)
        self.pc.on("connectionstatechange", self._on_connection_state)

    # -- signaling ---------------------------------------------------------

    async def handle_offer(self, sdp: str, kind: str) -> str:
        """Apply the browser offer and return the answer SDP.

        ``setLocalDescription`` gathers ICE before returning, so the answer
        already carries this endpoint's host candidates — there is no trickle
        channel and none is needed for a local call.
        """
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=kind))
        if self.pc.sctp is None:
            raise NegotiationError(
                "The SDP offer must include the 'control' data channel"
            )
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        return self.pc.localDescription.sdp

    # -- control channel ---------------------------------------------------

    async def send(self, payload: dict) -> None:
        channel = self.channel
        if self._closed or channel is None or channel.readyState != "open":
            return
        try:
            channel.send(json.dumps(payload))
        except Exception:  # pragma: no cover - channel closed mid-send
            logger.debug("Control channel send failed", exc_info=True)

    async def send_status(self, state: str) -> None:
        self.state = state
        await self.send({"type": "status", "state": state})

    async def send_error(self, code: str, message: str) -> None:
        await self.send({"type": "error", "code": code, "message": message})

    def _on_data_channel(self, channel) -> None:
        """Attach the browser's control channel (the only channel accepted)."""
        if channel.label != CONTROL_CHANNEL_LABEL:
            logger.info("Closing unexpected data channel %r", channel.label)
            try:
                channel.close()
            except Exception:  # pragma: no cover - already closed
                pass
            return
        self.channel = channel
        channel.on("message", self._on_channel_message)
        channel.on("open", self._on_channel_open)
        if channel.readyState == "open":
            self._on_channel_open()

    def _on_channel_open(self) -> None:
        if self._ready_announced or self._closed:
            return
        self._ready_announced = True
        asyncio.create_task(self._announce_ready())

    def _on_channel_message(self, message: object) -> None:
        if not isinstance(message, str) or len(message) > 2048:
            return
        try:
            payload = json.loads(message) if isinstance(message, str) else {}
        except (TypeError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        kind = payload.get("type")
        if kind == "barge_in":
            asyncio.create_task(self.barge_in("client"))
        elif kind == "end":
            asyncio.create_task(self.close())
        elif kind == "answer_format":
            try:
                self.answer_format = AnswerFormat.coerce(payload.get("answerFormat"))
            except ValueError:
                pass

    async def _announce_ready(self) -> None:
        status = await asyncio.to_thread(voice_vad.vad_status)
        await self.send(
            {
                "type": "ready",
                "sessionId": self.session_id,
                "workspace": self.workspace,
                "stt": "whisper-local",
                "tts": voice.tts_engine_name(),
                "vad": status,
            }
        )

    # -- media -------------------------------------------------------------

    async def _on_track(self, track) -> None:
        if track.kind != "audio":
            return
        self._reader_task = asyncio.create_task(self._read_microphone(track))

    async def _read_microphone(self, track) -> None:
        """Resample microphone frames and drive the VAD state machine."""
        import av

        self._resampler = av.AudioResampler(
            format="s16", layout="mono", rate=SAMPLE_RATE
        )
        while not self._closed:
            try:
                frame = await track.recv()
            except Exception:
                break
            for converted in self._resampler.resample(frame):
                await self._on_pcm(_frame_pcm(converted))

    async def _on_pcm(self, pcm16: bytes) -> None:
        if self._vad is None:
            try:
                self._vad = await asyncio.to_thread(voice_vad.SileroVad, threshold=self._threshold)
            except voice_vad.VadUnavailable as exc:
                self._vad_error = str(exc)
                await self.send_error("vad_unavailable", str(exc))
                return

        loop = asyncio.get_running_loop()
        # Inference runs off the event loop: a 20 ms audio frame must not be
        # delayed by the model call that judges it.
        windows = await asyncio.to_thread(self._vad.feed, pcm16)
        for window, probability in windows:
            if probability >= self._threshold:
                await self._on_speech(window, loop.time())
            else:
                await self._on_silence(window, loop.time())

    async def _on_speech(self, window: bytes, now: float) -> None:
        self._last_speech = now
        if self._speech_windows == 0:
            self._utterance.clear()
            for pending in self._preroll:
                self._utterance.extend(pending)
            self._preroll.clear()
            self._barged_this_utterance = False
        self._speech_windows += 1
        self._utterance.extend(window)

        # Barge-in: sustained speech while the answer is generated or spoken.
        if (
            self._speech_windows >= self._min_speech_windows
            and not self._barged_this_utterance
            and self._turn_task is not None
            and not self._turn_task.done()
        ):
            self._barged_this_utterance = True
            await self.barge_in("vad")

        # Keep the utterance bounded (memory).
        if len(self._utterance) > self._max_utterance_bytes:
            del self._utterance[: len(self._utterance) - self._max_utterance_bytes]

    async def _on_silence(self, window: bytes, now: float) -> None:
        if self._speech_windows == 0:
            self._preroll.append(window)
            del self._preroll[:-2]
            return
        # Keep the trailing silence: Whisper decodes better with a short tail,
        # and it is also what ends the turn.
        self._utterance.extend(window)
        if self._last_speech is not None and (
            now - self._last_speech >= self._silence_seconds
        ):
            await self._finish_utterance()

    async def _finish_utterance(self) -> None:
        speech_windows = self._speech_windows
        audio = bytes(self._utterance)
        self._utterance.clear()
        self._preroll.clear()
        self._speech_windows = 0
        self._last_speech = None
        if speech_windows < self._min_speech_windows or not audio:
            return
        if self._turn_task is not None and not self._turn_task.done():
            # A turn is already running and the user did not barge in: do not
            # queue a second one silently.
            return
        self._turn_task = asyncio.create_task(self._run_turn(audio))

    # -- turn --------------------------------------------------------------

    async def barge_in(self, source: str) -> bool:
        """Cancel the in-flight turn, drop queued audio, return to listening."""
        task = self._turn_task
        running = task is not None and not task.done()
        self.track.clear()
        if running and task is not None:
            self._turn_generation += 1
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: B014
                pass
        self._turn_task = None
        if running:
            await self.send({"type": "interrupted", "reason": source})
            await self.send_status("listening")
        return running

    async def _run_turn(self, pcm16: bytes) -> None:
        turn_generation = self._turn_generation
        self._turn_started_at = time.perf_counter()
        self._first_audio_ms = None
        try:
            await self.send_status("transcribing")
            text, language, duration = await self._transcribe(
                pcm16, turn_generation=turn_generation
            )
            transcription_ms = int((time.perf_counter() - self._turn_started_at) * 1000)
            await self.send(
                {
                    "type": "transcript",
                    "text": text,
                    "language": language,
                    "duration": round(duration, 3),
                }
            )
            if not text.strip():
                await self.send_error(
                    "empty_transcript", "No speech was recognised in the audio."
                )
                await self.send_status("listening")
                return

            await self.send_status("thinking")
            answer = None
            async with async_session() as db:
                stream = stream_with_memory(
                    db,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    question=text,
                    answer_format=self.answer_format,
                    workspace=self.workspace,
                    task=self.task,
                )
                try:
                    async for event in stream:
                        if event["event"] == "delta":
                            await self.send({"type": "answer_delta", "text": event["data"]["text"], "provisional": True})
                        elif event["event"] == "final":
                            answer = event["data"]
                    await db.commit()
                finally:
                    await stream.aclose()

            if answer is None:
                raise GenerationUnavailableError("The answer provider did not finish the response")
            wire = serialize_answer(answer).model_dump()
            # Voice clients historically used `id`; retain that additive alias.
            for source in wire["sources"]:
                source["id"] = source["chunkId"]
            await self.send({"type": "answer", **wire})

            spoken = answer.answer.strip()
            if not spoken:
                await self.send_status("listening")
                return

            await self.send_status("speaking")
            await self._stream_speech(spoken)
            await self.send({
                "type": "timing", "transcriptionMs": transcription_ms,
                "firstTokenMs": getattr(answer, "first_token_ms", None),
                "firstAudioMs": self._first_audio_ms,
                "totalMs": int((time.perf_counter() - self._turn_started_at) * 1000),
                "scope": "server-turn-end-to-audio-enqueued",
            })
            # Synthesis returns as soon as the audio is *queued*; the turn is
            # only over once the track has actually played it out.  Without
            # this wait the session would claim to be listening while ~seconds
            # of speech are still on the wire, and a barge-in would arrive too
            # late to cancel anything.
            await self._wait_for_playback()
            await self.send_status("listening")

        except asyncio.CancelledError:
            # Barge-in.  The caller already reported it; do not swallow beyond
            # this point, so the task really ends as cancelled.
            raise
        except InvalidConversationIdError as exc:
            await self.send_error("invalid_session", "Invalid conversation session.")
            await self.send_status("listening")
        except ConversationSessionNotFound:
            await self.send_error("session_not_found", "Conversation not found in this workspace.")
            await self.close()
        except SessionBusyError:
            await self.send_error("session_busy", "A response is already running in this conversation.")
            await self.send_status("listening")
        except GenerationUnavailableError as exc:
            if getattr(exc, "status_code", None) == 429:
                await self.send_error("rate_limited", "The answer service is temporarily rate limited. Please wait a moment and try again.")
            else:
                await self.send_error("engine_unavailable", "The configured answer or speech recognition engine is unavailable.")
            await self.send_status("listening")
        except voice.TTSEngineUnavailable:
            logger.exception("WebRTC voice synthesis unavailable")
            await self.send_error("tts_unavailable", "Speech synthesis is unavailable.")
            await self.send_status("listening")
        except Exception:  # pragma: no cover - unexpected infrastructure failure
            logger.exception("WebRTC voice turn failed")
            await self.send_error("turn_failed", "The voice turn failed.")
            await self.send_status("listening")

    async def _send_partial_transcript(
        self, turn_generation: int, text: str, segment_index: int, language: str
    ) -> None:
        """Send one current-turn Whisper snapshot over the WebRTC data channel."""
        if self._closed or turn_generation != self._turn_generation:
            return
        await self.send(
            {
                "type": "transcript_partial",
                "text": text[:8192],
                "language": language,
                "segmentIndex": segment_index,
                "provisional": True,
            }
        )

    async def _transcribe(
        self, pcm16: bytes, *, turn_generation: int | None = None
    ) -> tuple[str, str, float]:
        """Transcribe PCM with local Whisper and stream its decoded segments.

        The callback runs on Whisper's worker thread. It schedules a bounded
        data-channel send on the event loop and waits only briefly; it never
        blocks the WebRTC audio reader or Silero VAD path.
        """
        if turn_generation is None:
            turn_generation = self._turn_generation
        loop = asyncio.get_running_loop()

        def publish_partial(text: str, segment_index: int, language: str) -> None:
            if self._closed or turn_generation != self._turn_generation:
                return
            future = asyncio.run_coroutine_threadsafe(
                self._send_partial_transcript(
                    turn_generation, text, segment_index, language
                ),
                loop,
            )
            try:
                future.result(timeout=0.75)
            except TimeoutError:
                # Progress is best-effort; the final transcript must continue.
                future.cancel()

        def transcribe_worker() -> tuple[str, str, float]:
            """Own temp-file cleanup even if the awaiting turn is cancelled."""
            try:
                model = voice._load_model()
            except RuntimeError as exc:
                raise GenerationUnavailableError(
                    "Speech-to-text model is unavailable"
                ) from exc

            # Cancellation cannot interrupt native CTranslate2 inference. If
            # the turn was cancelled while the model loaded, skip starting the
            # decode; the generation check also suppresses any stale callback.
            if self._closed or turn_generation != self._turn_generation:
                return "", "", 0.0

            handle, path = tempfile.mkstemp(
                prefix="voice_webrtc_", suffix=_STT_SUFFIX
            )
            try:
                with os.fdopen(handle, "wb") as file:
                    file.write(pcm16_to_wav(pcm16))
                return voice._transcribe_path_with_partials(
                    model, path, publish_partial
                )
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    logger.warning("Failed to remove temporary WebRTC audio file")

        # Unlike the event-loop audio reader, this worker is cancellable at the
        # await boundary. Native inference may finish in the background, but
        # barge-in returns promptly and no stale partial can be sent.
        return await loop.run_in_executor(None, transcribe_worker)

    async def _stream_speech(self, text: str) -> None:
        """Synthesise and enqueue audio, incrementally for the local voice.

        Piper's ``synthesize`` yields one ``AudioChunk`` per sentence.  The
        generator runs in a worker thread and each chunk is handed back to the
        event loop immediately, so playback starts before the full answer has
        been synthesised (and a barge-in drops whatever is still queued).
        """
        if voice.tts_engine_name() == "piper-local":
            await self._stream_local_piper(text)
            return
        audio = await run_in_threadpool(
            voice._synthesize_speech_bytes, text, voice.tts_language(), False
        )
        self._enqueue_audio(_decode_audio_bytes_to_pcm(audio), SAMPLE_RATE)

    def _enqueue_audio(self, pcm: bytes, rate: int) -> None:
        self.track.enqueue_pcm(pcm, rate)
        if pcm and self._first_audio_ms is None and self._turn_started_at is not None:
            self._first_audio_ms = int((time.perf_counter() - self._turn_started_at) * 1000)

    async def _wait_for_playback(self) -> None:
        """Wait until the queued speech has been sent to the peer.

        Bounded: a peer that never consumes audio must not wedge the turn, so
        the wait ends at the queued duration plus a small margin and the turn
        completes honestly rather than hanging forever.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.track.queued_ms / 1000 + 2.0
        while self.track.speaking and loop.time() < deadline:
            await asyncio.sleep(0.05)

    async def _stream_local_piper(self, text: str) -> None:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        cancelled = threading.Event()

        def _produce() -> None:
            try:
                piper_voice = voice._load_local_voice()
                config = voice._tts_synthesis_config(False)
                # Bound each synthesis call and check cancellation between
                # sentences/chunks. A cancelled worker must not keep generating
                # the rest of a long academic answer in the background.
                sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
                for sentence in sentences:
                    for offset in range(0, len(sentence), 320):
                        if cancelled.is_set():
                            return
                        segment = sentence[offset:offset + 320].strip()
                        if not segment:
                            continue
                        for chunk in piper_voice.synthesize(segment, syn_config=config):
                            if cancelled.is_set():
                                return
                            loop.call_soon_threadsafe(queue.put_nowait, (
                                "chunk", int(chunk.sample_rate), chunk.audio_int16_bytes,
                            ))
                if not cancelled.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", 0, b""))
            except Exception as exc:  # pragma: no cover - depends on the voice file
                if not cancelled.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", 0, "Local speech synthesis failed"))

        worker = asyncio.create_task(run_in_threadpool(_produce))
        try:
            while True:
                kind, rate, payload = await queue.get()
                if kind == "chunk":
                    self._enqueue_audio(payload, rate)
                elif kind == "done":
                    break
                else:
                    raise voice.TTSEngineUnavailable(payload)
        finally:
            cancelled.set()
            # The thread cannot be interrupted, but the task must not outlive
            # this coroutine (barge-in cancels it).
            if not worker.done():
                worker.cancel()

    # -- lifecycle ---------------------------------------------------------

    def _on_connection_state(self) -> None:
        state = self.pc.connectionState
        if state in ("failed", "closed"):
            asyncio.create_task(self.close())
        elif state == "disconnected":
            # aiortc can recover from a transient disconnect; only log it.
            logger.info("WebRTC peer disconnected (session %s)", self.id)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._turn_generation += 1
        self.track.stop()
        if self._reader_task is not None:
            self._reader_task.cancel()
        if self._turn_task is not None and self._turn_task is not asyncio.current_task() and not self._turn_task.done():
            self._turn_task.cancel()
        try:
            await self.pc.close()
        except Exception:  # pragma: no cover - already closed
            pass
        _sessions.pop(self.id, None)


def _json_safe_sources(chunks) -> list[dict]:
    """Source metadata for the client, with no ORM objects."""
    out = []
    for chunk in chunks:
        out.append(
            {
                "id": str(getattr(chunk, "chunk_id", "") or ""),
                "documentId": str(getattr(chunk, "document_id", "") or ""),
                "documentName": str(getattr(chunk, "document_name", "") or ""),
                "content": str(getattr(chunk, "content", "") or "")[:2000],
                "score": round(max(0.0, float(getattr(chunk, "score", 0.0) or 0.0)), 4),
                "page": getattr(chunk, "page", None),
                "section": getattr(chunk, "section", None),
                "evidenceKind": getattr(chunk, "evidence_kind", None),
                "retrievalPath": getattr(chunk, "retrieval_path", None),
            }
        )
    return out


async def close_all_sessions() -> None:
    """Close every live call (application shutdown).

    A peer connection owns background tasks; leaving them running past the
    lifespan would keep the process alive and leak sockets.
    """
    for session in list(_sessions.values()):
        try:
            await session.close()
        except Exception:  # pragma: no cover - shutdown must not raise
            logger.debug("Failed to close a WebRTC session", exc_info=True)


async def create_session(
    *,
    user_id: str,
    session_id: str,
    answer_format: AnswerFormat,
    workspace: str = "student",
    task: str = "answer",
) -> VoiceWebRTCSession:
    """Create and register one call.  Kept separate so tests can drive it."""
    session = VoiceWebRTCSession(
        user_id=user_id, session_id=session_id, answer_format=answer_format,
        workspace=workspace, task=task,
    )
    _sessions[session.id] = session
    return session


@router.post("/webrtc/offer", response_model=WebRTCOfferResponse)
async def webrtc_offer(
    body: WebRTCOfferRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WebRTCOfferResponse:
    """SDP offer/answer exchange for the duplex voice call."""
    if not AIORTC_AVAILABLE:  # pragma: no cover - dependency absent
        raise HTTPException(
            status_code=503,
            detail={
                "error": "WebRTC transport is unavailable",
                "message": "The server voice transport is not installed",
            },
        )

    session_id = body.sessionId.strip()
    try:
        conversation_key(str(current_user.id), session_id)
    except InvalidConversationIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.type != "offer":
        raise HTTPException(status_code=400, detail="Only SDP offers are accepted")

    if not _looks_like_sdp(body.sdp):
        raise HTTPException(status_code=400, detail="Invalid SDP offer")

    try:
        answer_format = AnswerFormat.coerce(body.answerFormat)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await require_session(db, str(current_user.id), session_id, body.workspace)
    except ConversationSessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Conversation not found in this workspace") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation session") from exc

    session = await create_session(
        user_id=str(current_user.id),
        session_id=session_id,
        answer_format=answer_format,
        workspace=body.workspace,
        task=body.task,
    )
    try:
        answer_sdp = await session.handle_offer(body.sdp, body.type)
    except NegotiationError as exc:
        await session.close()
        logger.info("WebRTC offer rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await session.close()
        logger.warning("WebRTC offer rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid SDP offer") from exc

    return WebRTCOfferResponse(
        sdp=answer_sdp,
        type="answer",
        sessionId=session_id,
        workspace=body.workspace,
        vad=await asyncio.to_thread(voice_vad.vad_status),
        stt="whisper-local",
        tts=voice.tts_engine_name(),
    )


__all__ = [
    "AIORTC_AVAILABLE",
    "CONTROL_CHANNEL_LABEL",
    "FRAME_BYTES",
    "FRAME_SAMPLES",
    "NegotiationError",
    "PiperAudioStreamTrack",
    "SAMPLE_RATE",
    "VoiceWebRTCSession",
    "close_all_sessions",
    "create_session",
    "pcm16_to_wav",
    "router",
    "webrtc_offer",
]
