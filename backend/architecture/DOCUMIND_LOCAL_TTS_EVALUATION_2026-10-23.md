# Local TTS evaluation — replacing gTTS

**Date:** 2026-10-23
**Status:** `IMPLEMENTED — VERIFIED` (2026-10-23). The recommendation below was
adopted: `TTS_ENGINE=local` runs the provisioned Piper `en_US-ljspeech-medium`
voice on the CPU, and gTTS is opt-in only. Measurements, the exact change set and
the verification evidence are in §10; §§1–9 are the evaluation that led to it
(`PROPOSED` at the time it was written, kept as the decision record).

This record answers one question: *what would it take, and what would it cost, to
synthesize speech locally instead of calling Google Translate at request time?*
It is the evidence needed for a `§61`-style decision; it is not that decision.

---

## 1. What is being replaced, exactly

| Surface | Today | gTTS-specific |
|---|---|---|
| `POST /api/voice/synthesize` | 1–2000 chars → `audio/mpeg` bytes | `slow` flag, language validated against `gtts.lang.tts_langs()` |
| `WS /api/voice/stream` turn | answer text → `_synthesize()` → MP3 in 16 KiB frames, `audio_start.format = "audio/mpeg"` | same helper |
| Capability report | `{"stt": "whisper-local", "tts": "gtts"}` | literal `"gtts"` |
| Client | `apiSynthesizeSpeech()` returns `res.blob()`; `VoiceSpeakerButton` / `VoiceStreamClient` play it | format-agnostic already |
| Tests | `tests/integration/voice/test_voice_synthesize.py` (17 cases), `tests/integration/conversation/test_voice_stream.py`, `src/lib/voiceStream.test.ts` | mock `_synthesize_speech_bytes`; assert `audio/mpeg`, `"gtts"` |

Two constants and one helper are the whole runtime coupling. The client does not
care whether the bytes are MP3 or WAV — only the header the server sends and the
`audio_start.format` frame name it.

## 2. Why consider it

1. **Answer text leaves the machine.** The synthesized text is an answer built
   from the user's documents. gTTS sends it to `translate.google.com`. For a
   product whose entire premise is "your documents stay local", that is the
   sharpest inconsistency in the voice path — sharper than the audio itself.
2. **Offline.** `AGENTS.md` requires the project's models to be local
   (`local_files_only`, no external fallback). Whisper already is; TTS is not.
3. **Latency.** Measured here today, one short sentence (46 chars):
   **2.28 s, 28 032 bytes** — almost all of it network round-trip. A local
   15M–82M-parameter model on this CPU synthesizes the same text in well under a
   second (third-party RTF benchmarks; Windows SAPI measured 0.32 s — see §6).
4. **Failure mode.** Upstream outage ⇒ `503 Voice synthesis service is
   unavailable`. Locally the failure is "model artifact missing", which is the
   same honest, provisionable failure Whisper already has.

## 3. Host budget (measured, this machine)

The target is a single laptop: **RTX 3050 Laptop, 4 GB VRAM, 16 GB RAM**. Every
number below was read on this host on 2026-10-23, not taken from a spec sheet.

| Fact | Value |
|---|---|
| RAM | **15.7 GiB total, 5.6 GiB available, 64 % already in use** while this record was written |
| CPU | Intel, **12 threads** |
| GPU | RTX 3050 Laptop, **4096 MiB total, 3308 MiB free** with no model loaded (`torch 2.13.0+cu126`) |
| Disk | 33 GB free — a 63 MB voice is not a constraint |
| Python | 3.11.0 (Windows, AMD64) |
| Already installed | `onnxruntime 1.30.0` (**CPU provider only**), `torch`, `av 18.1.0`, `numpy`, `scipy` |
| Not installed | `piper*`, `TTS`, `kokoro`, `misaki`, `soundfile`, `pyttsx3`, `espeak*` (no binary on PATH) |
| Artifacts already on disk | `models/whisper` 464 MB, `models/documind-qa` 254 MB, `models/media-verification` 328 MB, `models/experiments` 762 MB |
| VRAM already spoken for | Qwen2.5-1.5B-Instruct 4-bit ≈ **1155 MiB allocator / 1276 MiB driver** peak with the conversation path warm |

### 3.1 What is actually left for TTS

- **VRAM:** 4096 − 1276 = **2820 MiB** free with the conversation model warm, so
  VRAM is not the immediate blocker — but every MiB spent here is KV-cache
  headroom lost. **A TTS engine that costs 0 MiB VRAM is a hard preference.**
- **Host RAM:** 5.6 GiB free *before* any DocuMind model is loaded. Order of
  magnitude once the stack is warm: Whisper `small` int8 ≈ 0.6–1.0 GiB, MiniLM
  embeddings ≈ 0.15 GiB, DistilBERT QA ≈ 0.3 GiB, local PostgreSQL ≈ 0.2 GiB,
  and the 1.5B model's load-time host copy ≈ 1.5 GiB. That leaves roughly
  **1.5–2.5 GiB** for TTS in the worst case — and less when other applications
  are running (the machine was already at 64 % before DocuMind started).
- **Usable envelope for a TTS engine on this host: ≤ ~0.4 GiB RSS and 0 MiB
  VRAM.** Piper `medium` fits with a wide margin. Kokoro-82M on CPU does **not**
  fit that envelope comfortably here.
- Loading stays lazy per engine, exactly as `chat/qa_model.py` and `voice.py`
  already do, so a session that never speaks never pays any of it.

## 4. Candidates

### A. Piper (VITS → ONNX Runtime, CPU) — *recommended*

- Runtime: `piper-tts` (current line is `piper1-gpl`; the older `rhasspy/piper`
  C++/MIT line is legacy). ONNX Runtime is **already installed** with the CPU
  provider — the same dependency class the embedding/QA paths already tolerate.
- Footprint (measured 2026-10-23, `en_US-ljspeech-medium`): **63,531,379 bytes**
  on disk, **138 MiB RSS** after load, **343 MiB peak** after synthesis,
  **0 MiB VRAM** — inside the §3.1 envelope, loaded once per process like
  `WhisperModel`.
- Speed (measured, same host): load **2.66 s**; 46-char sentence **149–203 ms**;
  ~300-char answer **816–918 ms** for 18.3 s of audio (RTF **0.044–0.068**). The
  third-party benchmark (~0.35 core-hour per audio-hour) is consistent with this.
- Languages: many, **one model file per voice/language** — this matters, because
  the current API accepts ~40 language codes.
- Licensing — two separate questions:
  - the **engine** `piper1-gpl` is **GPL-3.0** and *embeds espeak-ng* (also
    GPL-3.0). Server-side use does not trigger GPL's distribution obligations,
    but shipping a desktop/bundled build would. This is a product decision, not
    a technical one.
  - each **voice** carries its own licence. `en_US-lessac-*` is trained on the
    Blizzard 2013 corpus and **must not be used commercially**; pick a
    permissive voice (LibriTTS-derived or explicitly CC-BY/CC0) and record the
    choice. Verify the voice card at pin time.
- Quality: clearly synthetic, intelligible, "assistant-like". Fine for reading
  a grounded answer aloud; not pleasant for long prose.

### B. Kokoro-82M (StyleTTS2 lineage, 82M params) — *best quality, does not fit this host*

- Weights **Apache-2.0**, ≈ **330–350 MB**, 24 kHz, strong naturalness for its
  size — the best-sounding option in this footprint class.
- Runs on **torch**, already installed. On CPU it costs roughly **0.8–1.2 GiB
  RSS** and is slower than Piper; that is at or above the whole TTS envelope in
  §3.1 on a machine already at 64 % RAM. On GPU it would add ~0.4–0.8 GB VRAM
  next to the LLM, eating KV-cache headroom and breaking the "voice costs no
  VRAM" property Whisper established.
- G2P: English uses `misaki`; **espeak-ng (GPL-3.0) is required for non-English
  and for out-of-distribution fallback**, and on Windows it is a separate MSI
  install — a system-level dependency, unlike the project's self-contained
  model-directory pattern.
- Language coverage: 8 languages, versus gTTS's ~40.

### C. Windows SAPI (`pyttsx3` / `System.Speech`)

- Zero download, truly offline, no model artifact, negligible memory.
- **Measured here:** the same 46-character sentence synthesized in **317 ms**
  (148 614-byte WAV) through `System.Speech`, versus 2.28 s for gTTS. That is the
  throughput reference point a local neural engine has to beat, not a quality
  endorsement.
- **OS-locked** (the app would only speak on Windows), voice quality is poor,
  voice set depends on the machine, and tests could not be deterministic across
  CI. Acceptable as an operator-side fallback; not acceptable as the product's
  TTS engine.

### D. Larger neural systems (XTTS-v2, Chatterbox, F5-TTS, …)

- 1.8 GB+ weights, real-time-ish only on GPU, and several carry
  **non-commercial** licence terms. On a 4 GB card shared with a 1.5B LLM this
  is the wrong trade: high VRAM, high cold-start, no offline advantage over A/B.
  Rejected for this hardware tier.

### E. espeak-ng directly

GPL-3.0 and robotic. Rejected on quality.

## 5. Tradeoff summary

| | gTTS (today) | Piper | Kokoro-82M | SAPI |
|---|---|---|---|---|
| Offline | **No** | Yes | Yes | Yes |
| Answer text stays local | **No** | Yes | Yes | Yes |
| New dependency | — | `piper-tts` (GPL-3.0, espeak bundled) | `kokoro` + `misaki` (+ torch, present) | `pyttsx3` |
| Artifact size | 0 | 63–114 MB / voice | ~330 MB | 0 |
| VRAM | 0 | 0 | 0 (CPU) / +0.4–0.8 GB (GPU) | 0 |
| Host RAM (warm) | ~0 (per request) | ~0.15–0.35 GiB (est.) | ~0.8–1.2 GiB (est.) | ~0.05 GiB |
| Latency (short answer) | 2.28 s measured, network-bound | **0.15–0.20 s measured** | ~1 s CPU (claimed) | **0.32 s measured** |
| Naturalness | Good (cloud) | Fair | Very good | Poor |
| Languages | ~40 | many, per-voice files | 8 (espeak MSI off-English) | OS voices |
| Licences to clear | none (but ToS/privacy) | engine GPL-3.0 + per-voice | weights Apache-2.0 (+ espeak for non-en) | none |
| Portable to Linux/macOS | Yes | Yes | Yes | **No** |

## 6. What was *not* verified

- **Audio quality was not judged by listening.** The numbers prove the engine
  runs, is fast and is small; they say nothing about how it sounds.
- Kokoro was **not** installed or run; its latency and RSS remain estimates.
- The gTTS (2.28 s / 28 032 bytes) and Windows SAPI (317 ms / 148 614 bytes)
  numbers are measured on this host; SAPI is a throughput reference, not a
  candidate.
- Windows behaviour of the `piper-tts` wheel *is* now verified on this Python
  3.11 environment: it bundles its own espeak-ng data, no MSI or PATH binary is
  needed (the voice loaded and synthesized with no `espeak-ng` on PATH).
- The chosen voice's dataset licence was confirmed from its model card
  (LJSpeech — **public domain**); that is a dataset licence, not legal review.

## 7. Recommendation

**Decision (adopted 2026-10-23): Piper `medium` is the local TTS engine —
English first, CPU-only, public-domain voice — with gTTS retained only as an
explicitly-selected option.**

Why this is the one on *this* hardware (§3.1):

1. **0 MiB VRAM.** The 4 GB card keeps its ~2.8 GiB of headroom for the
   conversation model's KV cache; nothing here competes with it.
2. **~63 MB artifact, ~0.15–0.35 GiB RSS** — the only candidate comfortably
   inside the ≤ ~0.4 GiB / 0 MiB envelope on a 16 GB machine already at 64 % use.
3. **ONNX Runtime 1.30.0 CPU is already installed and pinned**, so this adds one
   Python package and no second inference stack.
4. **Sub-second synthesis** for an answer-sized sentence on 12 threads, against
   2.28 s measured for gTTS on the same box and 0.32 s for SAPI.
5. **The runtime coupling is one helper and two constants** (§1), so the change
   is small and testable without touching retrieval, generation or the client.

Conditions attached to that choice:

- **Kokoro-82M is not recommended for this machine.** It is the better-sounding
  model, but ~0.8–1.2 GiB RSS does not fit a budget already holding Whisper, the
  QA stack and a 1.5B LLM on 16 GB, and putting it on the GPU would eat the
  headroom criterion 1 protects. Reconsider only after a RAM upgrade or if the
  conversation LLM is dropped.
- **Windows SAPI is an operator-side emergency fallback, never the product
  engine** (Windows-only, poor voice, non-deterministic tests).
- **Explicit configuration, never a silent fallback.** A `TTS_ENGINE` setting
  (`local` | `gtts`) reported truthfully in the `ready` frame; a missing voice
  artifact must return `503`, not quietly reach the network — silent fallback
  would reintroduce exactly the leak this removes.
- **Do not change language semantics silently:** either ship voices for the
  languages offered, or keep rejecting unsupported codes with the existing 400
  rather than speaking the wrong language.
- **Licensing is a product decision, not a runtime one:** the engine is GPL-3.0
  and the voice must permit commercial use (`en_US-lessac-*` does not). If GPL
  is unacceptable, stop and revisit — do not swap in espeak-ng or SAPI to dodge
  it.

## 8. If approved, the change set is

- `voice.py`: replace `_synthesize_speech_bytes` with a lazily-loaded,
  thread-serialized **Piper `medium`** engine (ONNX Runtime CPU, 0 VRAM); keep
  the endpoint contract, add the engine's real media type. The voice directory
  is resolved from `config` and loaded once per process, mirroring
  `WHISPER_MODEL_NAME`, never from the request body.
- `conversation/stream.py`: `_synthesize` delegates to the same helper; the
  `audio_start.format` frame and `"tts"` capability string report the configured
  engine. `av 18.1.0` is already installed, so **MP3 encoding needs no new native
  dependency** if the client/`audio/mpeg` contract must be preserved; otherwise
  WAV is simpler and the client already accepts any blob.
- `config.py`: `tts_engine` (default `local`), `tts_voice`, `tts_model_path`
  (mirroring `WHISPER_MODEL_NAME`); the provisioned voice lands at
  `backend/models/tts/<voice>.onnx` and `backend/models/tts/` is git-ignored.
- Requirements: the engine + licence note; drop or demote `gTTS` only when the
  local path is measured.
- Tests: mock the new boundary; one **real** offline synthesis test (network
  blocked, non-empty audio asserted, header checked); the stream test's
  `audio/mpeg` / `"gtts"` assertions updated to the reported capability.
- Docs: `CONTEXT.md` endpoint table, `README.md`, and §55/§62 of
  `DOCUMIND_PROJECT_CONTEXT.md` currently say TTS is an external network
  service — that statement changes only when the engine does.

## 9. Verification that would be required before claiming it works

1. `pytest -q tests/integration/voice tests/integration/conversation` green with
   the real engine (not only the mocked boundary).
2. One measured run on this laptop: synthesis wall-time and peak RSS for a 5-,
   50- and 300-character answer, recorded in this file. Acceptance: **peak RSS
   ≤ 0.4 GiB** for the TTS process and **no VRAM growth** (§3.1) — if Piper
   exceeds either, the recommendation above is wrong and must be revised here,
   not quietly shipped.
3. A run with outbound network blocked, proving synthesis still succeeds and no
   socket is opened.
4. A `ready` frame captured from a live socket showing the engine actually in
   use.
5. Voice-stream barge-in still cancels mid-synthesis (the current test asserts
   the protocol, not the engine).

## 10. Implementation and verification (2026-10-23)

### 10.1 What changed

| File | Change |
|---|---|
| `backend/voice.py` | `TTS_ENGINE` dispatch (`local` \| `gtts`), lazy cached `PiperVoice` loader, serialized synthesis, `TTSEngineUnavailable`, engine-derived media type / filename / language policy, `slow` → `length_scale=1.3` |
| `backend/config.py` | `tts_engine` (`local`), `tts_voice` (`en_US-ljspeech-medium`), `tts_model_path` |
| `backend/conversation/stream.py` | `audio_start.format` and the `ready` frame's `tts` report the engine actually in use; `tts_unavailable` error frame instead of a generic `turn_failed` |
| `backend/requirements.txt` | `piper-tts==1.3.0`; gTTS marked opt-in |
| `.gitignore` | `backend/models/tts/` (provisioned artifact, not source) |
| `src/lib/voiceStream.ts` | playback blob uses the media type the server announces instead of hardcoded `audio/mpeg` |
| `backend/tests/integration/voice/test_voice_tts_local.py` | new: engine identity, WAV contract, language refusal, fail-closed 503 (no path leak), `slow` mapping, and one real network-blocked synthesis |
| `backend/tests/integration/voice/test_voice_synthesize.py` | pinned to `TTS_ENGINE=gtts` (it tests the gTTS mapping) |
| `backend/tests/integration/conversation/test_voice_stream.py` | asserts the reported engine/media type rather than literals |
| Docs | `README.md`, `CONTEXT.md`, `DOCUMIND_PROJECT_CONTEXT.md` (§34, §53.11, §55, §62) |

Provisioned artifact: `backend/models/tts/en_US-ljspeech-medium.onnx` (+
`.onnx.json`), downloaded with `python -m piper.download_voices
en_US-ljspeech-medium --data-dir models/tts`. Dataset: LJSpeech, **public
domain**; single speaker, 22.05 kHz.

### 10.2 Measured on this host

| Check | Result |
|---|---|
| Voice load | **2.66 s** (once per process) |
| 46-char sentence | **149–203 ms**, 3.0 s audio, RTF 0.049–0.068 |
| ~300-char answer | **816–918 ms**, 18.3 s audio, RTF 0.044–0.050 |
| Peak RSS | **343 MiB** (138 MiB after load) — acceptance was ≤ 0.4 GiB |
| VRAM | **0** — the 4 GB card keeps its conversation-model headroom |
| Offline | real synthesis passed with `socket.create_connection` blocked |

### 10.3 Test evidence

- `pytest -q tests/integration/voice tests/integration/conversation`: **63 passed,
  1 failed**. The failure is the pre-existing order-dependent
  `test_voice_stream.py::TestHandshake::test_session_is_acknowledged_with_real_backend_state`
  ("did not receive 'ready'; got ['ready']"); it passes alone and passed before
  this change in the same full-suite position.
- `tests/integration/voice/test_voice_tts_local.py`: **9 passed** (real synthesis
  included, not skipped).
- `pytest -q tests/unit`: **1731 passed, 23 skipped** (unchanged).
- `vitest run src/lib/voiceStream.test.ts src/pages/WorkspacePage.tts.test.tsx`:
  **16 passed**, including a new assertion that the playback blob uses the
  announced `audio/wav`.
- Not exercised: a live `uvicorn` + browser run (the local PostgreSQL cluster on
  port 55433 was not running during verification); quality was not judged by ear
  (§6).

### 10.4 Known limits of the implementation

- WAV over the socket is ~44.1 kB/s (a 20 s answer ≈ 880 kB) versus MP3's ~24 kB/s
  at 64 kbps. The client already consumes a blob, so this is bandwidth only; the
  MP3 path (`av` is installed) was not taken.
- `slow=True` changes phoneme duration, not prosody — an approximation, labelled
  as such.
- The engine is GPL-3.0 (see §7); the deployment decision stands.
- A voice is provisioned for English only. Other languages return `400` unless
  `TTS_ENGINE=gtts` is selected.
