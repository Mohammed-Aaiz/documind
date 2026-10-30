# BACKEND_AGENT

> **2026-10-27 scoped update:** previously unassigned `backend/conversation/**`,
> `backend/session/**`, `backend/voice.py`, `backend/voice_vad.py` and
> `backend/voice_webrtc.py` belong to this role. Provider configuration is authorized
> by `backend/architecture/DOCUMIND_WORKSPACE_REBUILD_2026-10-27.md`; provider and
> orchestration implementation remains AI_AGENT-owned. Older installed/not-installed
> descriptions below require inspection; they are not current environment evidence.

## Role

FastAPI HTTP surface, request/response logic, application services,
storage and backend behavior.

## Owns

-   `backend/main.py`
-   `backend/config.py`
-   `backend/storage/file_store.py`
-   `backend/auth/**`
-   `backend/settings/**`
-   `backend/verification/**`
-   `backend/reliability/**`
-   `backend/documents/**`
-   except each feature's `models.py`, owned by DATABASE_AGENT
-   `backend/requirements.txt` (Python dependency declarations)

`backend/user/` holds **only** `models.py` + `__init__.py` (ORM, DATABASE_AGENT); the
four `/api/user/*` routes were **removed** because they duplicated `GET /api/auth/me`
and `GET/PATCH /api/settings` and returned `404`. Do not reintroduce them.

## Must Not Touch

`backend/chat/**`, `backend/embeddings/**`, `backend/brain/**`,
`backend/graph/**`, `backend/tokenization.py`, `backend/outcomes.py`,
migrations, tests, frontend.

## Rules

Authenticated identity determines ownership. Never trust client-supplied
IDs. Preserve router contracts. Return honest unavailable/error states.
Validate inputs. Preserve async behavior.

Dependencies: **only BACKEND_AGENT may modify `backend/requirements.txt`.**
Declare new Python dependencies there — there is no second requirements file.
Do not upgrade or remove unrelated pinned dependencies. Do not change a
dependency that exists solely for another agent's code without requesting that
agent first (embeddings/retrieval/QA runtime deps belong to AI_AGENT; ORM and
migration tooling belongs to DATABASE_AGENT). Installing packages is a separate,
operator-approved provisioning step: it writes into `backend/venv/**`, which is
forbidden for agents.

## Planned dependency --- Voice Speech-to-Text (NOT INSTALLED)

Scope: real, local Whisper STT behind `POST /api/voice/transcribe`. No external
transcription API, no substituted speech model, no fabricated transcript.

Status: **NOT INSTALLED** — but **wheel availability is CONFIRMED** for this
environment (verified read-only against PyPI metadata; nothing was installed).
Nothing described below exists in the environment or in
`backend/requirements.txt` today.

Selected implementation: **`faster-whisper`**

Why (inspected evidence, not assumption):

-   The host is Windows and the system `ffmpeg` binary is **not** available
    (`ffmpeg` is not on PATH). `openai-whisper` requires that system binary,
    which cannot be provided through Python dependency management — this is
    the original blocker.
-   `faster-whisper` decodes audio through PyAV, whose wheels bundle the
    FFmpeg libraries, so no system binary is required.
-   The app venv already carries the Hugging Face stack it relies on
    (`huggingface_hub` 1.29.0, `tokenizers` 0.23.1, `numpy` 2.4.6, `tqdm` 4.70.0).
-   It runs on CTranslate2 rather than PyTorch, so it does not conflict with the
    pinned `torch` 2.13.0 used by `chat/qa_model.py`, and it is lighter at
    inference — consistent with the project's performance constraint of avoiding
    unnecessary heavyweight ML loading.

Confirmed dependency versions (verified compatible with CPython 3.11.0 /
Windows AMD64; every one publishes a `cp311` or `win_amd64` wheel —
**none installed today**):

-   `faster-whisper==1.2.1`   (pure-Python wheel)
-   `ctranslate2==4.8.2`      (`cp311-cp311-win_amd64` wheel)
-   `av==18.1.0`              (`cp311-abi3-win_amd64` wheel)
-   `onnxruntime==1.30.0`     (`cp311-cp311-win_amd64` wheel; a hard dependency
    of faster-whisper 1.2.1, not only of the VAD filter)

`av` **must stay below 19**: `av>=19.0.0` declares `Requires-Python >=3.12`, so
it has no CPython 3.11 wheel and would fail to resolve in this venv. Pin
`av==18.1.0` (or at most `av<19`). This is the one version trap in the set.

**System FFmpeg is NOT required.** `faster-whisper` decodes audio through PyAV,
whose wheels bundle the FFmpeg libraries. Verified: `ffmpeg` is not on PATH, and
this approach does not need it — which is exactly why `av`/PyAV was chosen over
`openai-whisper`.

A Whisper CTranslate2 model artifact must still be provisioned **once** and
stored locally, so transcription runs offline and no model is fetched at request
time. Choose the model size explicitly; do not silently default at runtime.

Pulled in transitively (wheels verified available): `pyyaml`, `protobuf`,
`flatbuffers`, `packaging`. Already satisfied by the venv: `huggingface_hub`
1.29.0, `tokenizers` 0.23.1, `numpy` 2.4.6, `tqdm` 4.70.0.

`openai-whisper` was **not** selected: it reuses the installed `torch` but
requires the system `ffmpeg` binary (absent), the exact blocker this decision
exists to remove.

## Verify

``` bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/api/health
python -m pytest -q tests
```
