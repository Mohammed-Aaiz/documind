# Incident: DocuMind QA model unavailable (chat/ask returns 503)

## Purpose
Recover when the trained QA model at `backend/models/documind-qa` is missing
or fails to load. `/api/chat/ask` refuses to answer rather than falling back
to an external model — that is intentional behavior (see
`DOCUMIND_PROJECT_CONTEXT.md` §17).

## Impact
`POST /api/chat/ask` returns **503** with
`"DocuMind QA model is not available"`. The AI workspace cannot answer
questions. Uploads, embeddings, login, and reliability history still work.

## Symptoms
- `/api/chat/ask` → 503 with a detail body containing the model path and error
  string (`backend/chat/routes.py`).
- `GET /api/health` shows `"qa_model": {"available": false, "error": "..."}`.
- First request after start fails: the model loads lazily, so an error only
  appears on first use (`backend/chat/qa_model.py`).
- Log line / error text contains:
  `DocuMind QA model not found at '<path>'` or
  `Failed to load DocuMind QA model from '<path>': ...`

## Severity
P1

## Immediate Actions
1. Check health endpoint output to capture the exact error string.
2. Confirm what `QA_MODEL_NAME` resolves to (default
   `./models/documind-qa`, relative to the `backend/` working directory).
3. Do not point `QA_MODEL_NAME` at any external model directory — see "Do Not".

## Diagnosis
1. **Directory exists?** The path from `QA_MODEL_NAME` must exist relative to
   the backend working directory. Default: `backend/models/documind-qa/`.
2. **Required artifacts present?** Per `backend/models/README.md`:
   `config.json`, `model.safetensors` (or `pytorch_model.bin`), `tokenizer.json`,
   `tokenizer_config.json`, plus special-token/vocab files. Note: the repo's
   `config.json`, `inference_config.json`, `tokenizer.json` and
   `tokenizer_config.json` are tracked in git, but **`model.safetensors` is
   gitignored** (`llm/model.safetensors` and
   `backend/models/documind-qa/model.safetensors` in `.gitignore`) — a fresh
   clone has no weights and the model will not load until weights are restored
   from the team's model storage.
3. **Load failure details?** The exception text is surfaced verbatim in the
   health endpoint and in the 503 detail — read it (missing file, corrupt
   weights, incompatible `transformers` version, OOM).
4. **transformers version?** `backend/requirements.txt` pins
   `sentence-transformers>=3.0.0`; `qa_model.py` notes the
   `question-answering` pipeline task was removed in transformers v5 — the code
   loads `AutoModelForQuestionAnswering`/`AutoTokenizer` directly. A stray
   transformers upgrade/downgrade can break loading.

## Recovery
1. If weights are missing: restore `model.safetensors` from the team's model
   artifact storage into the directory configured by `QA_MODEL_NAME`.
   This is a data/file restore, not a code change.
2. If the path is wrong: correct `QA_MODEL_NAME` in `backend/.env` (owner
   approval) and restart the backend.
3. If loading fails for version reasons, align installed transformers with the
   version the model was trained with (check `model_card.json` /
   `inference_config.json` in the model directory) — coordinate with the ML
   owner before changing dependency versions.
4. The module caches the failure in-process (`_model_loaded = True` on error):
   after restoring files, **restart the backend** to retry loading.

## Validation
- `GET /api/health` shows `"qa_model": {"available": true, "error": null}`.
- `POST /api/chat/ask` with a question about an embedded document returns an
  answer with `reliability` evidence (real scores, not fabricated).

## Rollback
No verified rollback mechanism found. The change is restoring/correcting model
files or env config; revert by undoing the specific file/env change made.

## Escalation
- If weights cannot be located anywhere, escalate to the ML owner who trained
  the model (`DOCUMIND_PROJECT_CONTEXT.md` §15–16). Do not substitute another
  model.

## Do Not
- Do not download or point at any external model (RoBERTa, generic DistilBERT,
  OpenAI, Gemini, Claude, Groq, Ollama, etc.). The project explicitly forbids
  external fallback — the system must fail honestly instead.
- Do not serve an empty/placeholder answer to hide the 503.

## Root Cause Follow-Up
- `model.safetensors` is intentionally untracked; consider documenting the
  canonical artifact location (e.g. in `backend/models/README.md`) so recovery
  does not depend on tribal knowledge.
