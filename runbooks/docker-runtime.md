# Docker / Production Runtime

How to run DocuMind as a reproducible local/production-style stack with Docker
Compose. Written from the actual implementation (`compose.yaml`,
`backend/Dockerfile`, `Dockerfile.frontend`, `docker/nginx.conf`) — the container
runtime runs the **same application code**; nothing about app behaviour changes.

## Services

| Service | Image / build | Listens | Published to host |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 (internal) | **No** — internal network only |
| `backend` | `backend/Dockerfile` | 8000 | `127.0.0.1:8000` (loopback) |
| `frontend` | `Dockerfile.frontend` (Vite → nginx) | 80 | `8080` |

The backend does **not** serve the SPA; nginx serves the built bundle and
reverse-proxies `/api/` to `backend:8000`, so the browser is same-origin.

## Required configuration

Compose reads a repo-root `.env` (gitignored) for `${...}` interpolation.
No secret is stored in `compose.yaml` or any Dockerfile.

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | yes | database password (fails fast if unset) |
| `JWT_SECRET_KEY` | yes | HS256 signing key, `openssl rand -hex 32` |
| `POSTGRES_USER` / `POSTGRES_DB` | no | default `documind` |
| `CORS_ORIGINS` | no | default `http://localhost:8080,http://127.0.0.1:8080` |
| `MAX_UPLOAD_SIZE_MB` | no | default `50` |
| `OMP_NUM_THREADS` | no | default `2` (torch/onnxruntime thread cap) |

## Model provisioning (important)

The backend requires locally-provisioned models. They are **mounted read-only**
from the host — never baked into an image layer (they are large and gitignored):

| Model | Host path | Container path | Model |
|---|---|---|---|
| QA | `backend/models/documind-qa` | `/app/models/documind-qa` | trained DistilBERT QA |
| Whisper | `backend/models/whisper/small` | `/app/models/whisper/small` | faster-whisper small |
| Media verification | `backend/models/media-verification` | `/app/models/media-verification` | Deep-Fake-Detector-v2 (ViT) |
| Embeddings | pre-fetched at build | `/opt/documind-models/all-MiniLM-L6-v2` | all-MiniLM-L6-v2 |

The container entrypoint (`backend/docker-entrypoint.sh`) **fails fast with an
explicit message** if any of the three mounted models is missing, rather than
starting a container that would answer those endpoints dishonestly.

If a host build has no network, build with
`docker compose build --build-arg PRELOAD_EMBEDDING_MODEL=0` and provide the
embedding model another way (e.g. place it in `backend/models/all-MiniLM-L6-v2`
and set `EMBEDDING_MODEL` accordingly).

## Bring-up

```bash
# 0. Provide the required variables (repo-root .env)
#    POSTGRES_PASSWORD=...   JWT_SECRET_KEY=$(openssl rand -hex 32)

docker compose config          # validate interpolation/config
docker compose build           # build backend + frontend images
docker compose up -d           # start db -> backend -> frontend
docker compose ps              # expect db/backend/frontend healthy
docker compose logs -f backend # watch migrations + startup
```

Migrations run through the existing Alembic workflow, twice-safely: the
entrypoint runs `alembic upgrade head`, and `main.py`'s lifespan brings the
schema to head at startup as well (idempotent). To run them explicitly:

```bash
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python -m alembic current
```

## Health / readiness

```bash
curl http://localhost:8000/api/health      # backend readiness (also via proxy: http://localhost:8080/api/health)
curl -I http://localhost:8080              # frontend
```

A backend `200` is not just "process alive": the healthcheck hits `/api/health`,
which is only reachable after the lifespan completed — meaning the database was
reachable and migrations applied. The `db` healthcheck uses `pg_isready`.

## Authenticated smoke test (existing infrastructure)

```bash
# create a user with the project's own script, then log in and call an
# authenticated endpoint
docker compose exec backend \
  python scripts/create_test_user.py --email smoke@test.com --password 'Pass123!' --name Smoke

TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.com","password":"Pass123!"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
```

## Restart / shutdown

```bash
docker compose restart backend
docker compose down            # keeps named volumes (db_data, uploads)
docker compose down -v         # DESTROYS the database and uploads (requires approval)
```

## Security posture

- No `.env` or secrets in any image or the Compose file; configuration is
  environment-supplied at runtime.
- PostgreSQL is internal to the `documind` network; no host port is published.
- The backend publishes only on `127.0.0.1`; the frontend is the public entrypoint.
- Containers run as a non-root user (`appuser`, uid 10001; nginx runs as its
  default unprivileged user) with `no-new-privileges:true`.
- Model files live under `/app/models` (read-only mount) and are never exposed
  through the frontend/static routes.
- CORS/authentication are unchanged; the UI is same-origin via the nginx proxy.

## Troubleshooting

| Symptom | Cause / action |
|---|---|
| Backend exits with `FATAL: required model directory not found` | Provision the model under `backend/models/...`; see the table above. |
| `Set POSTGRES_PASSWORD ...` / `Set JWT_SECRET_KEY ...` on `compose config` | Add the variable to the repo-root `.env`. |
| Backend unhealthy for a long time on first boot | Expected: the first `/api/health` triggers the lazy QA-model load; `start_period` is 300s. |
| Migration error in logs | See `runbooks/migration-failure.md`. |
| Database connection failures | See `runbooks/database-failure.md`. |
