#!/bin/sh
# DocuMind backend container entrypoint.
#
#   1. Fail fast (with an explicit message) if a required, operator-provisioned
#      local model directory is missing — rather than starting a container that
#      would answer those endpoints dishonestly later.
#   2. Apply pending Alembic migrations through the project's existing workflow.
#      (main.py's lifespan also brings the schema to head; this makes the step
#      explicit and keeps a migration failure out of the uvicorn boot path.)
#   3. Exec uvicorn with a single worker: the QA / Whisper / media singletons
#      are per-process, so extra workers would each load the models.
set -eu

QA_DIR="${QA_MODEL_NAME:-/app/models/documind-qa}"
WHISPER_DIR="${WHISPER_MODEL_NAME:-/app/models/whisper/small}"
MEDIA_DIR="/app/models/media-verification"

missing=0
require_dir() {
    if [ ! -d "$1" ]; then
        echo "FATAL: required model directory not found: $1" >&2
        echo "  Provision the model on the host and mount it (see compose.yaml ->" >&2
        echo "  ./backend/models:/app/models:ro), or point the corresponding" >&2
        echo "  environment variable at a valid local directory." >&2
        missing=1
    fi
}

require_dir "$QA_DIR"
require_dir "$WHISPER_DIR"
require_dir "$MEDIA_DIR"

if [ "$missing" -ne 0 ]; then
    echo "Refusing to start: one or more provisioned models are unavailable." >&2
    exit 1
fi

# Embeddings: only a warning. The project resolves a local directory when one
# exists and otherwise falls back to the (offline) HuggingFace cache/Hub.
if [ -n "${EMBEDDING_MODEL:-}" ] && [ ! -d "${EMBEDDING_MODEL}" ]; then
    echo "WARNING: EMBEDDING_MODEL='${EMBEDDING_MODEL}' is not a local directory;" >&2
    echo "         it will be resolved as a model id instead." >&2
fi

echo "Applying database migrations (alembic upgrade head)..."
python -m alembic upgrade head

echo "Starting DocuMind API..."
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
