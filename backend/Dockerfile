# DocuMind backend runtime image.
#
# Build context: ./backend  (see compose.yaml and backend/.dockerignore).
# The image contains NO secrets and NO model weights:
#   * configuration is supplied at runtime via environment variables (compose);
#   * the locally-provisioned models (documind-qa, whisper, media-verification)
#     are mounted read-only at /app/models by compose — they are gitignored
#     operator assets and must never be baked into a layer.
# The only model pre-fetched at build time is the small sentence-transformers
# embedding model, stored OUTSIDE /app/models so the read-only mount does not
# hide it. This keeps runtime offline-capable for embeddings.
#
# Build arg PRELOAD_EMBEDDING_MODEL=0 skips that download for a network-free
# build (embeddings then fall back to the documented runtime resolution).

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_DISABLE_TELEMETRY=1

# libgomp1 provides the OpenMP runtime used by the torch / onnxruntime wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Dependencies -----------------------------------------------------------
# gTTS is installed with --no-deps on purpose: its published metadata declares
# click<8.2, which conflicts with huggingface_hub's click>=8.4.2, so a normal
# resolve fails. Its Python runtime API does not use click. This mirrors the
# documented provisioning step in requirements.txt.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && grep -v '^gTTS' requirements.txt > /tmp/requirements-docker.txt \
    && python -m pip install -r /tmp/requirements-docker.txt \
    && python -m pip install --no-deps gTTS==2.5.4 \
    && rm -f /tmp/requirements-docker.txt

# ---- Embedding model (self-contained, runnable offline) ---------------------
ARG PRELOAD_EMBEDDING_MODEL=1
RUN mkdir -p /opt/documind-models \
    && if [ "$PRELOAD_EMBEDDING_MODEL" = "1" ]; then \
        python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2').save('/opt/documind-models/all-MiniLM-L6-v2')"; \
    else \
        echo "PRELOAD_EMBEDDING_MODEL=0: skipping embedding-model preload"; \
    fi

# ---- Application code -------------------------------------------------------
COPY . .

# ---- Non-root runtime user --------------------------------------------------
# /app/uploads is created here so the named volume inherits its ownership on
# first use; otherwise the non-root user could not write to the upload volume.
RUN mkdir -p /app/uploads \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /opt/documind-models \
    && chmod 0755 /app/docker-entrypoint.sh

USER appuser

EXPOSE 8000

# Entrypoint validates the provisioned models, applies Alembic migrations, then
# starts uvicorn with a single worker (model singletons are per-process).
ENTRYPOINT ["/app/docker-entrypoint.sh"]
