# DocuMind Backend Tests

This directory is the **only** place pytest discovers tests (`pytest.ini` sets
`testpaths = tests`). Nothing under `auth/`, `chat/`, `documents/`,
`embeddings/`, `brain/`, `graph/`, or any other production package is ever
collected, and no production module may import from here — the dependency
direction is `PRODUCTION ↑ TESTS`.

## Layout

```
tests/
├── conftest.py            # in-memory SQLite fixtures + ASGI client + user factory
├── fixtures/              # shared test-layer helpers (NOT production code)
│   ├── e2e_config.py         # single config source for the live-server harnesses
│   ├── darwin_proper.pdf     # committed document fixture (browser harness)
│   └── integration_http.py   # stdlib HTTP helper for live-server e2e harnesses
├── unit/
│   ├── auth/              # JWT/config policy
│   ├── brain/             # Brain types, orchestration, outcomes
│   ├── chat/              # answer span, RAG context, provenance, chat endpoint
│   ├── documents/         # chunking, processing lifecycle, extraction
│   ├── evaluation/        # metric library, runner honesty rules, corpus contracts
│   ├── embeddings/        # (reserved)
│   ├── graph/             # structural graph + fusion (see below)
│   ├── reliability/       # (reserved)
│   ├── security/          # SQL-safety
│   ├── storage/           # DATABASE_URL normalisation
│   └── verification/      # (reserved)
├── integration/
│   ├── auth/              # auth flow over the ASGI app
│   ├── documents/         # upload/file-integrity over the ASGI app
│   ├── graph/             # graph ingestion + graph-aware RAG over the app
│   ├── rag/               # real-DB pipeline validation
│   ├── security/          # CORS preflight + cross-user isolation
│   ├── settings/          # /api/settings
│   └── verification/      # verification endpoint honesty + frontend source scan
├── e2e/
│   └── browser/           # live-server harnesses (React proxy → FastAPI → Postgres)
└── README.md
```

`unit/storage/`, `unit/security/`, `integration/settings/` and
`integration/verification/` are **additive** categories: the contract's baseline
set does not cover `config.py` / `storage/database.py` / `/api/settings` /
`/api/verification`, and forcing those modules into an unrelated category would
have made the categorisation less clear, not more.

## Running

```bash
cd backend
./venv/Scripts/python.exe -m pytest -q                 # full suite
./venv/Scripts/python.exe -m pytest -q tests/unit
./venv/Scripts/python.exe -m pytest -q tests/integration
./venv/Scripts/python.exe -m pytest -q tests/e2e
./venv/Scripts/python.exe -m pytest -q tests/unit/graph
./venv/Scripts/python.exe -m pytest -q tests/integration/graph
```

**Never** run a test file directly (`python tests/unit/chat/test_chat_unit.py`).
Use the runner above.

## Test databases

Almost everything is SQLite-backed and needs no PostgreSQL. `conftest.py` builds
one in-memory engine (`sqlite+aiosqlite:///:memory:` with `StaticPool`), points
the ASGI app's `get_db` dependency at it, and turns on `PRAGMA foreign_keys=ON`
so `ON DELETE CASCADE` behaves as it does on the real database.

SQLite compatibility is **dialect-scoped** and never rewrites the production
models:

* `@compiles(postgresql.UUID, "sqlite")` declares UUID columns as `CHAR(32)`,
  matching the 32-character hex SQLAlchemy's UUID emulation stores, and
  `@compiles(postgresql.JSONB, "sqlite")` renders JSONB as SQLite's `JSON`.
* The SQLite test engine gets `dialect.colspecs[postgresql.UUID] = _SQLiteUUID`,
  which also accepts a canonical UUID *string* because PostgreSQL does —
  production routes pass `str(current_user.id)` straight into UUID comparisons,
  and a malformed id is still rejected exactly as PostgreSQL rejects it.
* Nothing assigns to `Column.type`, `Table` or `Base.metadata`. The production
  metadata stays genuine PostgreSQL metadata for the whole process, so the
  SQLite tests and the real-PostgreSQL validation can share one pytest process
  in either order.

`tests/unit/storage/test_sqlite_type_isolation.py` pins that contract. Do not
"fix" SQLite compatibility by patching model columns: that is exactly what made
the suite depend on collection order.

`tests/integration/rag/test_real_e2e_validation.py` is the exception to
"SQLite-backed": it needs a reachable PostgreSQL. It runs the real pipeline
(PostgreSQL + pgvector + alembic schema + embeddings + retrieval + Brain + QA
model) **in-process**, against a dedicated throwaway database
(`documind_integration`, created on the application's own server, migrated,
verified, and dropped afterwards). It is destructive, so `assert_isolated_target()`
refuses the application DSN before the first destructive statement, and all four
step assertions must hold. It skips only when no server is reachable at all;
every other failure raises.

## `tests/e2e/browser`

These harnesses drive a **live** server (React dev proxy on port 3000, or the
backend directly on 8000) against the real PostgreSQL database. They require the
test user `test@documind.io` to exist and are not part of the fast suite. Every
module is marked `e2e` and skips itself when its base URL is unreachable, so a
plain `pytest -q` run reports them as *skipped*, never as passed.

### Configuration — `fixtures/e2e_config.py`

Everything machine- and runtime-specific comes from that one module. No harness
hard-codes a host, a port, a binary path or a user's home directory, and **no
environment variable has to be exported by hand**:

| What | Where it comes from | Test-only override |
| --- | --- | --- |
| base URL | `http://localhost:3000` (Vite proxy) | `DOCUMIND_E2E_BASE_URL` |
| PostgreSQL host/port/db/user | parsed from the application's own `DATABASE_URL` — `backend/.env` outranks the ambient environment | `DOCUMIND_E2E_DATABASE_URL` |
| `psql` executable | first existing of the known install locations, then `PATH` | `DOCUMIND_E2E_PSQL` |

Because the connection parameters are parsed from the same `DATABASE_URL` the
backend uses, a harness can never drift onto a different database (or silently
onto port 5432) — `PGPORT` is neither read nor required. Direct row verification
deliberately **fails loudly** rather than skipping when `psql` cannot be found:
its whole point is direct database verification, and a silent skip would turn
"not verified" into "passed".

Generated uploads (`test_document.pdf`, `ml_test.pdf`, `documind_facts.pdf`, …)
are written into `e2e/browser/uploads/`, which the harness creates on demand and
which is git-ignored; committed documents live in `fixtures/`.

The RAG harness runs as its own user (`e2e.rag@test.local`, created on demand by
`create_test_user.py`) and purges that user's corpus before and after ingesting
its knowledge document, so retrieval is scoped to a corpus the harness owns
rather than to whatever other runs have accumulated. The browser harness
identifies its own conversation by the *active* marker in the drawer rather than
by preview text, which every past run renders identically.

## Research runners are NOT here

Measurement harnesses live in `backend/evaluation/experiments/` and are named
`run_*.py`. They are research, not tests: `pytest` cannot discover them, and
they must be launched explicitly (from `backend/`). See
`backend/evaluation/README.md`.
