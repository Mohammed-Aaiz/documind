# Incident: PostgreSQL unavailable / connection failures

## Purpose
Recover when the backend cannot reach PostgreSQL — the single datastore for
users, documents, chunks (with pgvector embeddings), chats, reliability logs,
and settings.

## Impact
Every authenticated endpoint fails (login, documents, chat, reliability,
sessions). Only `/api/health` still responds (it does not touch the DB).
All data endpoints 500. Users cannot log in or use the product at all.

## Symptoms
- Logins fail with 500 (`/api/auth/login`).
- Any authenticated API call returns 500; frontend surfaces
  "Request failed (500)" from `src/lib/api.ts`.
- `/api/health` returns 200 — confirming the API process is alive.
- Uvicorn logs show `asyncpg`/`sqlalchemy` `OperationalError` / connection
  errors (engine is created with `pool_pre_ping=True` in
  `backend/storage/database.py`).

## Severity
P0

## Immediate Actions
1. Verify the API itself is fine: `curl http://localhost:8000/api/health`.
2. Check whether PostgreSQL is running and accepting connections on the host
   from `DATABASE_URL` (see `backend/config.py`; default
   `postgresql+asyncpg://documind:documind@localhost:5432/documind`).
3. Do not restart the API repeatedly — each failed request burns retries
   against the DB; fix the database first.

## Diagnosis
1. **Database process up?** Connect to the PostgreSQL host and check the
   service status (use your platform's standard method — no DB tooling is
   committed in this repo).
2. **Reachable from the backend host?** From the host running the API,
   test connectivity to the host/port embedded in `DATABASE_URL`.
3. **Credentials valid?** If connections are refused with authentication
   errors, the credentials in `DATABASE_URL` no longer match the database.
4. **Database exists and has the schema?** The expected tables come from
   `backend/migrations/versions/001_add_reliability_logs.py` plus the models
   declared in `backend/auth/models.py`, `backend/documents/models.py`,
   `backend/chat/models.py`, `backend/verification/models.py`,
   `backend/reliability/models.py`, `backend/user/models.py`
   (users, documents, document_chunks, chat_sessions, chat_messages,
   verification_results, reliability_logs, source_refs, user_settings).
5. **pgvector present?** Retrieval SQL in `backend/chat/rag.py` and
   `backend/embeddings/routes.py` uses the `vector` type and `<=>` operator;
   a missing pgvector extension produces errors on embedding/retrieval
   endpoints while plain reads may still work.
6. **Errors localized to reliability endpoints?** `reliability/routes.py`
   uses PostgreSQL-specific `INSERT ... ON CONFLICT`; it fails on non-Postgres
   backends or when the `reliability_logs` table/unique constraint is missing.

## Recovery
1. Restart PostgreSQL using your platform's standard procedure
   (conceptual — platform not defined in the repo).
2. If credentials changed, update `DATABASE_URL` **only with the owner's
   approval**; then restart the API (`uvicorn main:app ...` from `backend/`).
3. If the schema is missing/incomplete, see [migration-failure.md](migration-failure.md).

## Validation
- `GET /api/health` → 200 (should already be true).
- Login succeeds and returns a JWT.
- `GET /api/documents` returns the user's documents (exercises DB read).
- A chat `/api/chat/ask` query returns sources (exercises pgvector path).

## Rollback
No verified rollback mechanism found for database infrastructure (no DB
tooling/infrastructure files in the repo). Schema-level rollback exists only
for Alembic migrations — see [migration-failure.md](migration-failure.md).

## Escalation
- If PostgreSQL data appears corrupted or lost, stop: **REQUIRES HUMAN
  APPROVAL** for any restore. No backup/restore tooling is present in the
  repository, so use your infrastructure owner's process.
- Escalate to whoever operates the PostgreSQL instance if the server itself
  is unstable.

## Do Not
- Do not delete or recreate the database to "reset" the state.
  **REQUIRES HUMAN APPROVAL** — data loss.
- Do not point the API at a different database (e.g. SQLite) in production;
  `asyncpg` + pgvector SQL (`<=>`) will not work and reliability upserts
  will fail.
- Do not change `DATABASE_URL` silently; existing data would be orphaned.

## Root Cause Follow-Up
- The repo contains no backup automation. After recovery, verify a backup of
  the database exists outside this repository's scope.
- If connection exhaustion caused the outage, note that the engine uses
  default pool sizes; tune deliberately (code change — out of runbook scope).
