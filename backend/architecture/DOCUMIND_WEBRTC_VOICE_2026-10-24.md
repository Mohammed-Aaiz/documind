# DocuMind — Duplex voice over WebRTC, with server-side Silero VAD (2026-10-24)

**Status:** IMPLEMENTED — MEASURED LOCALLY. Replaces the `WS /api/voice/stream`
transport; does not add a schema, a model provider, or an external service.
**Companions:** `DOCUMIND_LOCAL_TTS_EVALUATION_2026-10-23.md` (TTS engine),
`DOCUMIND_STATEFUL_CONVERSATION_2026-10-22.md` (the LangGraph turn this
transport speaks), `DOCUMIND_PROJECT_CONTEXT.md` §0.9 and §55.

---

## 1. The question

The voice surface existed and worked: `WS /api/voice/stream` accepted raw PCM
frames, ran server-side Silero VAD for turn end, called the LangGraph turn and
pushed MP3 in 16 KiB chunks back. It was sufficient for one talker and one
turn, and it was wrong in three ways that matter for a *conversation*:

1. **The browser decided when the turn ended and when to barge in.** Client
   VAD (`src/lib/voiceActivity.ts`) ran on the same microphone signal that the
   server VAD was judging, from a different signal path, at a different
   threshold. When the two disagreed the session either cut the user off
   mid-sentence or waited for a silence that never came.
2. **The transport was not audio.** WebSocket JSON + base64/binary PCM meant
   the client re-implemented buffering, jitter handling and playback pacing,
   and the server could not use the jitter buffer or the timestamps a real
   media stack gives you.
3. **Barge-in cancelled queued bytes, not a call.** Cancelling the websocket
   task did not stop the audio the browser had already buffered, so the
   assistant kept talking for a second or more after being interrupted.

The task was therefore not "add WebRTC"; it was **move the two turn-taking
decisions to the side that can actually make them**, and give the audio a
transport that paces itself.

## 2. Decision

**One transport: WebRTC via `aiortc`, with the server owning turn-taking.**

- `aiortc==1.14.0` carries SDP/ICE and the RTP audio path; it pins `av<17`,
  which is why `av` is `16.1.0` (faster-whisper needs `av>=11`; 16.1.0 is the
  only version both accept).
- **No STUN/TURN.** `RTCPeerConnection(RTCConfiguration(iceServers=[]))` on the
  server and `{ iceServers: [] }` in the browser. A local call connects over
  host candidates and never leaves the machine; a remote deployment would need
  TURN and is explicitly out of scope while local evaluation must stay offline.
- **The WebSocket endpoint was removed, not kept alongside.** Two transports
  would mean two barge-in implementations and two sets of bugs; the client VAD
  module was deleted with it so there is exactly one authority on turn-taking.
- **Silero v5 ONNX on the existing `onnxruntime` CPU provider** — no torch, no
  torchaudio, no CUDA, **0 VRAM**, so the 3000 MiB budget in
  `generation/causal.py` is untouched. The model is provisioned locally at
  `backend/models/vad/silero_vad.onnx` like the QA/Whisper/Piper weights.

## 3. Transport contract

`POST /api/voice/webrtc/offer` (JWT required) takes
`{"sdp": ..., "type": "offer", "sessionId": ..., "answerFormat": "5"|"10"|"15"}`
and returns `{"sdp": ..., "type": "answer", "sessionId": ...}`.

Two non-obvious constraints, both enforced rather than assumed:

- **The browser must create the `control` data channel in its offer.** An SDP
  answer cannot add an SCTP media section, so a server-created channel would
  never be negotiated. An offer without it is refused with an explicit `400`
  instead of running a call whose events can never reach the client.
- **A body that is not an SDP is refused before a peer is built.** aiortc
  parses any string into a session with zero media sections; the structural
  check (`v=0` plus an `m=` line) turns that into "this is not an offer".

Data channel protocol (`control`):

| Direction | Message | Meaning |
|---|---|---|
| server → client | `ready` | `sessionId`, `stt:"whisper-local"`, `tts` engine name, `vad` status |
| server → client | `status` | `transcribing` / `thinking` / `speaking` / `listening` |
| server → client | `transcript` | recognised text, language, duration |
| server → client | `answer` | the full turn result: text, engine, marks, verification, sources, history, memory backend |
| server → client | `interrupted` | `reason: "vad"` (server-detected) or `"client"` (tap-to-stop) |
| server → client | `error` | stable `code` + human `message`; never a fabricated success |
| client → server | `barge_in` | the user tapped stop |
| client → server | `answer_format` | switch 5/10/15-mark answering mid-call |

Media: both directions are **16 kHz mono int16**, 20 ms frames (320 samples,
640 bytes). The outgoing direction is a `PiperAudioStreamTrack`; the incoming
direction is the browser microphone, resampled with a real PyAV resampler
(float/stereo inputs included) and fed to the VAD.

## 4. The track, and why the pacing is written the way it is

`PiperAudioStreamTrack` buffers PCM into an `asyncio.Queue` and yields
`av.AudioFrame` at 16 kHz on a **continuous 20 ms monotonic clock**:

- a short tail becomes a **padded final frame** rather than a truncated one;
- an underrun yields **silence** authored from the same clock, so PTS never
  jumps and the receiver's jitter buffer never sees a discontinuity.

Two bugs were found by measurement, not by reading:

- **Flushed PyAV frames report full-size planes.** Reading
  `bytes(frame.planes[0])` duplicates audio: a 0.5 s 22.05 kHz chunk became
  1.004 s queued. `_frame_pcm` slices to `frame.samples * 2`.
- **`speaking` may not mean "queued".** Piper synthesis returns once the audio
  is enqueued; the turn now also awaits playback (`_wait_for_playback`) before
  reporting `listening`. Without it the session claimed to listen while seconds
  of speech were still on the wire, so a barge-in arrived after the turn had
  already "finished" and cancelled nothing.

## 5. VAD and barge-in

`backend/voice_vad.py` wraps the Silero v5 ONNX model with the **per-stream
recurrent state** the export requires, 512-sample windows prefixed with the
previous 64 samples as context. Feeding 512 samples alone returns ≈0.001–0.008
even for loud speech — measured on the Silero test corpus; with the context it
returns 1.0. This is why the class owns state instead of exposing a stateless
helper, and why a per-frame call with fresh state would silently "never detect
speech" rather than fail.

State machine per stream:

- **turn end** — ≥ `VAD_MIN_SPEECH_MS` of speech (200 ms) followed by
  `VAD_SILENCE_MS` (700 ms) below threshold; two silent windows of pre-roll are
  kept so the first phoneme is not clipped;
- **barge-in** — sustained speech (≥ `VAD_MIN_SPEECH_WINDOWS`) while a turn
  task is alive. It cancels the task (which *is* the LangGraph call), clears
  the queued audio, emits `interrupted` with `reason:"vad"`, returns to
  `listening`, and the same utterance becomes the next question. Once per
  utterance, so a long interruption cannot cancel the turn it just started;
- **bounds** — `WEBRTC_MAX_UTTERANCE_SECONDS` (60 s) caps the utterance buffer.

Inference runs in a worker thread (`asyncio.to_thread`), so a 20 ms audio frame
is never delayed by the model call that judges it.

Failure is explicit: a missing/invalid model raises `VadUnavailable`, the
session sends `error{code:"vad_unavailable"}` and reports
`vad:{available:false,error}` in `ready`; the UI shows "Server voice detection
unavailable". Nothing falls back to pretending a turn ended.

## 6. Measured on this machine (2026-10-24)

Environment: Python 3.11, Windows, `aiortc 1.14.0`, `av 16.1.0`,
`onnxruntime 1.30.0`, CPU only. Models provisioned locally: Whisper `small`,
Piper `en_US-ljspeech-medium`, Silero v5. Verification client: a real `aiortc`
peer (not a browser), real backend process, no mocks on the media path.

| Measurement | Result |
|---|---|
| ICE to `connected`, host candidates only | connected; no STUN/TURN configured, no external socket observed |
| SDP offer/answer round trip | `200`, `type:"answer"`, `v=0` + audio media section present |
| Question spoken by Piper → local Whisper | transcribed **verbatim** |
| Answer audio through the track | **44 speech frames**, peak **20829 / 32767**, **≈0.86 s** |
| Barge-in during playback | `interrupted{reason:"vad"}` received, audio cleared, back to `listening` |
| Speech start → `interrupted`, TTS thread idle | **≈0.5 s** |
| Same, in one run while Piper was synthesising | **≈3.3 s** — see §7 |
| Unit + integration voice tests | **36 passed** (`tests/unit/voice`, `test_voice_webrtc_offer.py`) |
| Voice + conversation suite | **86 passed** in 72.3 s |
| Frontend | **49 passed**, `npm run build` clean |

Earlier in the same task, before the docs were updated, the whole unit suite
ran at 1814 passed / 23 skipped; that number is quoted from that run and was not
re-measured after the final documentation edits, which touch no code.

## 7. Limitations — do not overstate

- **No physical microphone, no real browser.** The E2E evidence is an `aiortc`
  client; browser capture and playback are covered by jsdom fakes only. Browser
  echo cancellation / noise suppression behaviour is therefore unverified.
- **Barge-in latency is not benchmarked.** Cancellation is verified. The 3.3 s
  sample shows what happens when the GIL is held by Piper synthesis: the event
  loop starves and the VAD thread's result cannot be acted on until it returns.
  Measured once; not characterised.
- **Host-candidate ICE cannot cross NAT.** Fine locally, insufficient remotely.
- **Turn end is still silence-based** (700 ms). A slow talker will be cut;
  there is no semantic end-of-turn model.
- **The gap between STT and TTS is not streamed.** Whisper runs on the whole
  utterance and the answer is generated before speech starts, so a turn's
  first audio arrives after generation, not during it.
- **Not measured against the frozen extractive benchmark**, which this change
  does not touch.

## 8. Security notes

- The offer endpoint requires a JWT; the conversation id is validated and
  scoped to the authenticated user before a turn runs (`session.conversation_key`),
  never trusted from the body.
- Only a `control`-labelled data channel is accepted; other channels are closed.
- Channel payloads are parsed defensively — malformed JSON is dropped, an
  unknown `answer_format` keeps the previous value.
- ICE servers are empty by construction, so a call cannot be relayed to a third
  party. There is no new file upload path and no new `eval`/shell surface.
- Audio is treated as untrusted input: bounded buffers, bounded utterance
  length, bounded VAD window.

## 9. Files

| File | Role |
|---|---|
| `backend/voice_webrtc.py` | offer endpoint, `PiperAudioStreamTrack`, `VoiceWebRTCSession`, barge-in |
| `backend/voice_vad.py` | Silero v5 ONNX wrapper with per-stream state, `vad_status()` |
| `backend/config.py` | `VAD_MODEL_PATH`, `VAD_THRESHOLD`, `VAD_SILENCE_MS`, `VAD_MIN_SPEECH_MS`, `WEBRTC_MAX_UTTERANCE_SECONDS` |
| `backend/voice.py` | streaming synthesis hook used by the track (synthesize route unchanged) |
| `backend/main.py` | router registration, `close_all_sessions()` on shutdown |
| `src/lib/voiceStream.ts` | `RTCPeerConnection` client, `replaceTrack` microphone, `<audio>` playback |
| `src/lib/api.ts` | `offerVoiceWebRTC` |
| `src/components/common/VoiceStreamButton.tsx` | phase UI, level meter, VAD-unavailable notice |
| `src/pages/WorkspacePage.tsx` | wiring, mute-during-own-playback |

Deleted: `src/lib/voiceActivity.ts` (client VAD) and the `WS /api/voice/stream`
endpoint in `backend/conversation/stream.py`.

**Next agent:** browser E2E (Playwright) with a fake audio device would close the
largest remaining gap — the physical-capture path — and a barge-in latency
benchmark under sustained synthesis would quantify §7's second limitation.

## 10. Browser E2E — implemented 2026-10-25

`backend/tests/e2e/browser/test_voice_webrtc_browser.py` closes the
physical-capture gap named above. It launches Chrome with Chromium's own fake
audio device (`--use-fake-device-for-media-stream`,
`--use-file-for-fake-audio-capture=<wav>`), where the WAV is synthesised at run
time with the provisioned Piper voice, then logs in, ingests
`darwin_proper.pdf`, opens an *empty* conversation and clicks the voice control
— so nothing matching the assertions can have come from a text turn.

Measured once on the local dev stack: `1 passed in 152.25s` — transcript
"When did Charles Darwin publish on the Origin of Species?" (Whisper, from the
fake microphone), answer "1859. The Origin of Species [4]" (`engine:
generative`, `model: google/flan-t5-base`), phases
`listening → transcribing → thinking → speaking → listening`, then a tap back to
`idle`. Skips — never fails — without the live server, Playwright, Chrome or the
local Whisper/Piper/Silero artifacts.

The harness found one real defect, now fixed: the voice `answer` frame keys its
sources `id` (`_json_safe_sources` above) while the transcript renders
`chunkId`, so the first spoken answer threw in `WorkspacePage`
(`src.chunkId.slice(0, 8)`) and unmounted the whole workspace.
`normalizeVoiceSources()` in `src/lib/voiceStream.ts` renames the key at the
frame boundary; `src/lib/voiceStream.test.ts` covers it.

Still unverified: hardware echo cancellation and room acoustics (the fake device
has neither), and barge-in latency under sustained synthesis.

## 11. Turn latency — measured in the browser, 2026-10-25

`test_voice_webrtc_browser.py` timestamps every control-channel frame with the
page's own `performance.now()` (`VOICE_EVENTS_HOOK`), so these spans are
measured where the user experiences them — not inferred from Python-side
polling. Three consecutive runs, same machine, headless Chrome via Playwright,
local Whisper / Piper / Silero on CPU, `google/flan-t5-base` for the turn:

| Span (client clock) | run 1 | run 2 | run 3 | median |
|---|---|---|---|---|
| capture + VAD turn end (click → `transcribing`) | 8.97 s | 4.36 s | 4.40 s | 4.40 s |
| STT (`transcribing` → `transcript`) | 61.12 s | 62.21 s | 57.71 s | 61.12 s |
| conversation turn (`transcript` → `answer`) | 37.96 s | 18.75 s | 16.57 s | 18.75 s |
| TTS start (`answer` → `speaking`) | 1.45 s | 0.02 s | 0.01 s | 0.02 s |
| playback (`speaking` → `listening`) | 6.43 s | 6.80 s | 6.66 s | 6.66 s |
| turn total (`transcribing` → `listening`) | 106.96 s | 87.78 s | 80.95 s | 87.78 s |
| end to end (click → `listening`) | 115.93 s | 92.13 s | 85.35 s | 92.13 s |

All three runs passed (pytest wall time 155 s / 121 s / 114 s).

Reading the numbers:

- **The VAD turn end is prompt.** Click-to-`transcribing` (4.4–9.0 s) is the
  spoken question plus the server's silence window; nothing waits on the
  network, because the call is host-candidate-only on loopback.
- **STT dominates.** 57–62 s for the same ~4 s question. That is this machine's
  state, not the engine's character: every run shared the desktop with
  CPU-heavy applications (an antivirus host process, an office suite, a
  browser, and the coding agent itself). The harness prints these spans and
  deliberately asserts no bound on them, so a slow box fails nothing — treat
  this table as a record of one loaded desktop, never as a benchmark.
- **The turn itself** (retrieval + generation + verification) took 17–38 s, and
  **playback** 6.4–6.8 s — Piper's own speaking time for the answer, awaited by
  the server before it reports `listening` again.
- End to end a spoken turn is therefore **85–116 s on this box, STT-bound**.
  The remaining honest gap is the same as §7's: a quiet machine and a barge-in
  latency measurement under sustained synthesis are still unmeasured.
