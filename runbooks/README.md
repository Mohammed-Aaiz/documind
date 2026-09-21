# DocuMind Operational Runbooks

Recovery guides for real failure modes in this repository. Written from the actual
implementation (backend/, src/, config files) — not from plans or design docs.

## System snapshot (verified)

- **Backend:** Python / FastAPI (`backend/main.py`), run with
  `uvicorn main:app --host 0.0.0.0 --port 8000` from `backend/` (see
  `backend/start_server.py`).
- **Frontend:** React 18 + TypeScript + Vite (`npm run dev`, port 3000; proxy
  `/api` → `http://localhost:8000` in `vite.config.ts`; production build via
  `npm run build`).
- **Database:** PostgreSQL + pgvector via SQLAlchemy async (`asyncpg`),
  configured by `DATABASE_URL` in `backend/config.py`; engine in
  `backend/storage/database.py` (pool_pre_ping enabled).
- **Migrations:** Alembic (`backend/alembic.ini`, `backend/migrations/`,
  single revision `001_add_reliability_logs.py`).
- **Auth:** email/password (bcrypt) + JWT HS256 (`python-jose`). Secrets via
  `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` in `backend/config.py`.
- **QA model:** local trained DistilBERT model at
  `backend/models/documind-qa`, path from `QA_MODEL_NAME`
  (`backend/chat/qa_model.py`). **No external model fallback by design.**
- **Embeddings:** `sentence-transformers` model `all-MiniLM-L6-v2` (384-dim),
  loaded lazily (`backend/embeddings/model.py`). First use downloads from Hugging Face.
- **File storage:** local disk under `UPLOAD_DIR` (default `backend/uploads/`),
  UUID-named files (`backend/storage/file_store.py`).
- **Health check:** `GET /api/health` (includes QA-model availability).

## Not present in this project (do not assume elsewhere)

No Docker, Kubernetes, CI/CD pipelines, queues, cron jobs, external LLM APIs,
payments, email, object storage, feature flags, or cloud infrastructure exist
in the repository. Deployment/rollback mechanisms: **NOT VERIFIED** (none found).

## Environment variables (names only — values live in backend/.env, gitignored)

| Variable | Used by |
|---|---|
| `DATABASE_URL` | `backend/config.py` (PostgreSQL asyncpg URL) |
| `JWT_SECRET_KEY` | `backend/config.py` (HS256 signing key) |
| `JWT_ALGORITHM` | `backend/config.py` |
| `JWT_EXPIRE_MINUTES` | `backend/config.py` |
| `CORS_ORIGINS` | `backend/config.py` |
| `UPLOAD_DIR` | `backend/config.py` |
| `MAX_UPLOAD_SIZE_MB` | `backend/config.py` |
| `QA_MODEL_NAME` | `backend/chat/qa_model.py` (local model path) |
| `VITE_API_BASE_URL` | `src/lib/api.ts` (frontend API base) |

## Runbooks

| File | Incident | Severity |
|---|---|---|
| [api-down.md](api-down.md) | API unreachable / complete outage | P0 |
| [database-failure.md](database-failure.md) | PostgreSQL unavailable / connection failures | P0 |
| [auth-token-failure.md](auth-token-failure.md) | JWT verification / secret mismatch — mass 401s | P1 |
| [qa-model-unavailable.md](qa-model-unavailable.md) | QA model missing or fails to load | P1 |
| [embedding-failure.md](embedding-failure.md) | Embedding model or pgvector retrieval failure | P1 |
| [upload-storage-failure.md](upload-storage-failure.md) | Upload directory / file storage failure | P2 |
| [migration-failure.md](migration-failure.md) | Alembic migration failure or drift | P2 |

## Severity definitions

- **P0** — complete production outage (API down, database down).
- **P1** — major feature outage (auth broken, QA/RAG dead, embeddings dead).
- **P2** — limited operational issue with manageable impact.
- **P3** — low-risk maintenance (no runbooks created at this level).

## Conventions

- All commands run from the `backend/` directory unless noted.
- High-risk actions are marked **REQUIRES HUMAN APPROVAL**; documentation-only
  agents must not execute them.
- Never put real secret values in these files — variable names only.
