# Voice conversation progress updates — 2026-10-27

Status: **CONFIRMED implementation** of partial transcript and answer-caption events on the existing local WebRTC voice path. This does not claim true live-microphone token STT or a measured latency improvement.

## Existing voice layers retained

- One full-duplex WebRTC peer carries the microphone to the local backend and Piper assistant audio back to the browser. No STUN/TURN relay is configured.
- Browser microphone capture requests echo cancellation, noise suppression, and automatic gain control. The UI reports only the settings returned by the browser; browser DSP support is not inferred.
- Server-side Silero VAD owns turn boundaries and hands-free barge-in. Manual interruption remains available. Both paths cancel the active response and clear queued audio.
- Voice turns use the authenticated workspace conversation, the same retrieval/answer pipeline, and the configured local speech synthesizer.

## New progress protocol

- After VAD ends an utterance, the existing local faster-whisper decode is consumed through its segment iterator. Each yielded segment can send a cumulative `transcript_partial` snapshot over the WebRTC control channel. No second model call is run for partial text.
- The final `transcript` remains authoritative and is the only transcript submitted to retrieval and generation. Partial text is UI progress only.
- The assistant's provisional `answer_delta` text is shown as a live caption. Audio playback still waits for the final verified answer, then streams through the existing Piper audio track.
- Per-session turn generations suppress partials from a cancelled or closed call from reaching later turns. Temporary audio remains bounded and uses the existing server-side cleanup path.

## Boundaries and verification

The current faster-whisper API accepts a complete audio source; it does not accept a live microphone stream or expose token-by-token partial decoding during capture. Consequently, transcript snapshots arrive only as decode segments are emitted after the utterance ends. A short utterance may produce one segment near decode completion. The 2026-10-25 benchmark in `DOCUMIND_WEBRTC_VOICE_2026-10-24.md` measured 57–62 seconds of STT for a short question on a loaded CPU desktop; no post-change end-to-end latency comparison was run. Do not claim that this implementation reduced that interval.

Verification: `backend/tests/unit/voice` — **33 passed**, one existing pytest-asyncio deprecation warning; frontend voice unit/component suites — **25 passed**; `npm run typecheck` passed; backend `py_compile` and `git diff --check` passed. Tests verify protocol order, final transcript authority, cancellation, VAD/barge-in, captions, and reported browser processing settings. They do not verify physical microphones, room acoustics, hardware noise reduction, or current full turn latency.

No dependency, speech model, cloud STT service, or migration was added for this change.
