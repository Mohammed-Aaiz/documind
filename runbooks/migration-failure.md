# Incident: Alembic migration failure or schema drift

## Purpose
Recover when migrations fail or the database schema does not match the models,
causing SQL errors on specific endpoints (e.g. missing `reliability_logs`).

## Impact
Endpoints touching missing/changed tables return 500 while others work.
The repo has a linear migration chain (`000_create_base_tables` →
`005_add_document_graph`; head `005`), so a failure classically presents as
endpoints touching the affected revision failing while others still work.

## Symptoms
- 500s with `relation "reliability_logs" does not exist` (or similar
  `UndefinedTable`/`ProgrammingError`) on `/api/reliability/last-query` or on
  `/api/chat/ask` (which upserts reliability data on every query).
- Alembic command fails with a traceback mentioning a revision or SQL error.
- Schema drift: `alembic` reports pending changes vs models in
  `backend/*/models.py`.

## Severity
P2

## Immediate Actions
1. Do not re-run migrations repeatedly — identify the failure first.
2. Take no action on the database before confirming which revision state it
   is in.
3. Keep the API running; a partial schema failure is not a full outage.

## Diagnosis
1. **Check current revision.** From `backend/`, inspect the alembic version
   table in the database targeted by `sqlalchemy.url` (from
   `backend/alembic.ini` / env). Compare with the migration files in
   `backend/migrations/versions/` (`000` … `005`, head `005`).
2. **Alembic runs async?** Yes — `backend/migrations/env.py` uses
   `async_engine_from_config` with asyncpg; it requires a reachable
   PostgreSQL (SQLite will not work for migrations because of
   PostgreSQL-specific types like `JSONB`/`UUID` and `ON CONFLICT` usage).
3. **Partial application?** Each revision applies in one transaction (e.g. `001`
   creates `reliability_logs` + its index). A failure mid-way typically rolls
   back cleanly; verify whether the table exists before assuming drift.
4. **Drift vs models?** The declarative models in `auth/models.py`,
   `documents/models.py`, `chat/models.py`, `verification/models.py`,
   `reliability/models.py`, `user/models.py` are the source of truth. The full
   schema is now covered by migrations: `000_create_base_tables.py` (revision
   root, `down_revision = None`; creates the base tables and runs
   `CREATE EXTENSION IF NOT EXISTS vector`), followed by `001`–`004`. Alembic is
   the only sanctioned schema-creation path, and the application applies
   migrations to `head` at startup (`backend/main.py`, `_ensure_database_schema`).
   `Base.metadata.create_all` is not used for application schema — the test suite
   creates tables via the SQLite conftest only.

## Recovery
1. If the revision state is behind and the failure is understood, run the
   migration normally: from `backend/`, use Alembic to upgrade to head
   (conceptual command — `alembic upgrade head`). This is a schema change:
   **REQUIRES HUMAN APPROVAL** before execution in production.
2. If a migration is failing due to data (e.g. constraint conflicts), stop and
   involve the database owner; do not hand-edit rows to force the migration.
3. After a successful migration, restart the API only if it had cached failed
   prepared statements/errors — generally not required.

## Validation
- The `reliability_logs` table exists with the columns from `001`
  (`user_id` unique FK, metrics, `sources_json` JSONB).
- `GET /api/reliability/last-query` returns 200 (empty payload is fine).
- A `/api/chat/ask` query succeeds end-to-end (it performs the upsert).

## Rollback
Verified rollback exists at the schema level only:
`backend/migrations/versions/001_add_reliability_logs.py` defines
`downgrade()` that drops the `ix_reliability_logs_user_id` index and the
`reliability_logs` table. **REQUIRES HUMAN APPROVAL** — dropping the table
discards stored reliability snapshots. No deployment rollback exists (no
deployment tooling in the repo).

## Escalation
- Any migration that partially applied and cannot be cleanly re-run → database
  owner. **REQUIRES HUMAN APPROVAL** for manual `alembic_version` stamping or
  hand-written SQL fixes.

## Do Not
- Do not manually stamp alembic versions to "unstick" a migration without
  understanding the exact schema state.
- Do not run migrations against SQLite or a non-PostgreSQL target.
- Do not edit migration files after they have been applied anywhere.
- Do not delete the alembic version table to force re-runs.

## Root Cause Follow-Up
- The chain (`000`–`005`) now covers the modeled tables. Still confirm each
  environment is stamped at the same head and that the pgvector extension
  exists — `000_create_base_tables` runs `CREATE EXTENSION IF NOT EXISTS vector`.
- Consider generating migrations from model diffs rather than hand-writing,
  to avoid future drift.
