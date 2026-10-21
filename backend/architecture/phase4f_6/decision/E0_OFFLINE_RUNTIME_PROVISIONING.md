# E0 OFFLINE RUNTIME PROVISIONING — Phase 4F.6-G

> **⚠ CORRECTION (2026-09-27) — see [`E0_ERRATUM_2026-09-27.md`](./E0_ERRATUM_2026-09-27.md).**
> Three statements below are inaccurate and must not be relied on:
> - "**no alembic environment in repo**" → an Alembic environment **does** exist
>   (`backend/alembic.ini` + `backend/migrations/`). Correction **C4**.
> - production target "`postgresql+asyncpg://localhost:5432/documind` from `backend/.env`"
>   → the real `backend/.env` targets a managed remote PostgreSQL service; localhost is only
>   the `config.py` / `alembic.ini` default. Correction **C1**.
> - "PostgreSQL is not local (no remote/cloud/Supabase)" → both halves are wrong: a local
>   PostgreSQL 16.6 distribution is present on this machine, and the configured target is a
>   remote managed service. Correction **C6**.
> The body below is preserved unaltered as the historical record of Phase 4F.6-G.

**Date:** 2026-09-23 · **Nature:** environment-provisioning/readiness documentation **only** — no software installed, no downloads, no network, no SQL executed, no production contact, no E0 execution. This document prepares the runtime required to measure things honestly; per Task 15 it makes **no claim** about retrieval quality, retrieval bottleneck, model quality, representation quality, answerability quality, or any hypothesis H-A…H-E (§13).

**Companion artifacts:** `e0_diagnostics/offline_runtime_checklist.json` (machine-readable), `decision/E0_RETRIEVAL_RUN_MANIFEST.json` → `phase_4f_6g_provisioning`.

---

## 1. Current blocker

Phase 4F.6-F established `D. NO_POSTGRES`; Phase 4F.6-G Task 1 established `C. NO_MEDIA`. Combined: **`E0_RETRIEVAL_RUNTIME_BLOCKED`** — the existing DocuMind retrieval implementation cannot execute because there is no local PostgreSQL server and no server-side pgvector, and now also **no operator-provided offline installation media anywhere on this machine**. This blocker is not bypassed: no substitute engine (SQLite/FAISS/in-memory) is permitted, and the Python `pgvector==0.5.0` client is a type adapter, not the server extension.

## 2. Media search evidence (Task 1 → classification **`C. NO_MEDIA`**)

| Location searched (local only) | Patterns | Hits |
|---|---|---|
| `~/Downloads`, `~/Desktop`, `~/Documents` (maxdepth 3, venv excluded) | `*postgres*`, `*pgsql*`, `*pgvector*`, `vector.control`, `vector--*.sql`, `vector.dll` | **0** |
| `/c/Downloads`, `/d/Downloads`, `/d/setup`, `/c/setup` (existence) | — | directories absent |
| Package caches: `~/scoop/cache`, `chocolatey cache/lib`, `WinGet Packages/Links` | `postgres`/`pgsql`/`pgvector` | **cache directories absent** |
| Other local drives `/d`, `/e`, `/f` | — | absent |

Nothing was downloaded; nothing was installed.

### Exact missing media (Task 1 STOP record)
```
MISSING: PostgreSQL server installation media + matching pgvector server extension media
```
Concretely, the operator must provide **one** of:
- **M1** — PostgreSQL Windows x64 installer (`.exe`, e.g. EDB win32-x64) **or** portable/archives zip, for a server major within the matrix in §4; **and**
- **M2** — the matching **server-side pgvector** build for that exact major + AMD64 ABI: extension files `vector.control`, `vector--*.sql`, `vector.dll` (plus import lib if required by the server build), delivered as an offline package — **or** M2′ pgvector *source archive* plus a pre-authorized local build toolchain (MSVC Build Tools already present locally); building must not pull from the network.
- Not sufficient: the Python client package (already present), Docker images (no Docker), cloud/database-as-a-service (forbidden), or any network `CREATE EXTENSION ... ` download path.

## 3. Required version matrix (Task 2 — derived from local code, not chosen)

| Component | Requirement | Local evidence |
|---|---|---|
| Server architecture | **Windows x64 (AMD64)** | `PROCESSOR_ARCHITECTURE=AMD64`, `uname -m=x86_64` |
| PostgreSQL server major | within **asyncpg 0.30.0's supported range: 9.5–17** (practically 13–17 for a modern offline installer); record exact `version()` at setup | installed asyncpg 0.30.0 package description: "supported for PostgreSQL versions 9.5 to 17" |
| pgvector **server extension** | build matching the chosen major + AMD64 ABI; must provide `vector` type, `vector(384)` dimension constraint, cosine operator `<=>`, `ORDER BY` distance ordering | retrieval contract: `retrieval_schema_requirements.json` |
| Python pgvector **client** | `pgvector==0.5.0` — already installed; **not** the server extension | `backend/requirements.txt:16` |
| Driver | `asyncpg==0.30.0` (only driver — `psycopg2-binary` **not installed**) | `backend/requirements.txt:6` |
| ORM | `sqlalchemy[asyncio]==2.0.36` | `backend/requirements.txt:5` |
| Migrations | `alembic==1.14.1` installed but **no alembic environment in repo** → schema creation must use the existing pattern `Base.metadata.create_all` (tests/conftest) | repo search |
| Python runtime | 3.11.0 (venv) | `backend/venv` |

No arbitrary version may be pinned beyond these locally evidenced constraints; whatever major the operator provides must satisfy the validation checks in §6 (items 3, 5, 6, 7, 8, 9, 10).

## 4. Diagnostic isolation contract (Task 3)

| Item | Value |
|---|---|
| Diagnostic database | `documind_e0_diagnostic` (only) |
| Production database | `documind` — target `postgresql+asyncpg://localhost:5432/documind` from `backend/.env` — **never connect, never modify** |
| Connection string | separate DSN; diagnostic DSN must **not** appear in `backend/.env`, and `.env` must not be modified (hash/mtime checked before and after any future session) |
| Role | dedicated diagnostic role (e.g. `e0_diag`) **where feasible**; if the environment only offers one role, record that fact and the justification before any SQL |
| Schema | diagnostic DB default schema only; no production schema writes |
| Forbidden | production document ingestion, production retrieval queries, production row reads/writes (except the unavoidable `users` FK row if the existing model requires one — must be a dedicated diagnostic row, recorded in the ingestion report) |
| Application config | production `.env` untouched; the diagnostic DSN is passed to the diagnostic session only (explicit parameter/env var outside the repository), never written into repo files |

**Isolation proof — checkable BEFORE any SQL is executed:**
1. Parse the intended DSN → host is localhost, database name `== documind_e0_diagnostic`, `!= documind`.
2. Diff intended DSN against `DATABASE_URL` in `backend/.env` → must differ in database (and role, if a dedicated role exists).
3. Record `.env` sha256+mtime before; re-record after the session → identical.
4. Record every DSN used during the session in `E0_RETRIEVAL_RUN_MANIFEST.json`.
5. If any check fails → Task 16 failure rule ("diagnostic DB is not isolated"/"production DB accidentally targeted") → immediate stop.

## 5. Offline install validation checklist (Task 4 — **do not execute without local media**)

| # | Check | Status |
|---|---|---|
| 1 | PostgreSQL server binary exists (`<root>/bin/postgres.exe`, `pg_config --version`) | `NOT_CHECKED` |
| 2 | Server starts locally (`pg_ctl -D <datadir> start`; `pg_isready`) | `NOT_CHECKED` |
| 3 | Server version compatible (major within asyncpg 0.30.0 range 9.5–17; record `SELECT version()`) | `NOT_CHECKED` |
| 4 | pgvector server extension files exist (`vector.control`, `vector--*.sql`, `vector.dll` under the server's `share/extension` + `lib`) | `NOT_CHECKED` |
| 5 | `CREATE EXTENSION vector;` succeeds **in the diagnostic DB** (from already-local files only) | `NOT_CHECKED` |
| 6 | vector type available: `SELECT '[1,2,3]'::vector;` | `NOT_CHECKED` |
| 7 | cosine operator available: `SELECT '[1,0]'::vector <=> '[0,1]'::vector;` → finite float (cosine distance) | `NOT_CHECKED` |
| 8 | `vector(384)` accepted: `CREATE TEMP TABLE _t(v vector(384)); DROP TABLE _t;` | `NOT_CHECKED` |
| 9 | asyncpg connects: `asyncpg.connect(dsn)` → `SELECT 1` (asyncpg 0.30.0) | `NOT_CHECKED` |
| 10 | SQLAlchemy stack connects: `create_async_engine('postgresql+asyncpg://…')` → `SELECT 1` (SQLAlchemy 2.0.36) | `NOT_CHECKED` |

## 6. Exact operator setup order (Task 5 — never modifies `.env`)

1. Obtain authorized **offline** PostgreSQL installer/media (M1). 2. Install PostgreSQL locally (or unpack portable). 3. Start the local service. 4. Verify server version (`SELECT version()`; major in §4 range). 5. Add/enable the matching **pgvector server extension from locally supplied media** (M2) — `CREATE EXTENSION vector` from local files only. 6. Create isolated database `documind_e0_diagnostic`. 7. Create the diagnostic role (where feasible). 8. Verify the connection target against §4's pre-SQL isolation proof. 9. Verify pgvector (§5 items 5–8). 10. Create the diagnostic schema using the already-approved pattern (`Base.metadata.create_all` against the diagnostic engine; models: `backend/auth/models.py`, `backend/documents/models.py`). 11. Verify schema (§5 + column/type inventory vs `retrieval_schema_requirements.json`). 12. Resume Phase 4F.6-F Tasks 6–18 (offline embedding verification → ingest 6/93 → validation → smoke test → parity → readiness re-gate).

## 7. Diagnostic connection contract (Task 6 — placeholders only, no secrets)

```yaml
host:     <DIAG_HOST>          # must be localhost
port:     <DIAG_PORT>          # e.g. 5432 (same instance, different database) or an isolated instance port
database: documind_e0_diagnostic
user:     <DIAG_ROLE>          # dedicated role where feasible, else recorded justification
password: source = <OPERATOR_SUPPLIED_ENV_VAR>   # provided in-session; NEVER stored in a repo file,
                                                 # NEVER in backend/.env, NEVER printed to artifacts
sslmode:  <local policy: disable|require>         # loopback default: disable
sqlalchemy_url: postgresql+asyncpg://<DIAG_ROLE>:<PASSWORD_IN_MEMORY>@<DIAG_HOST>:<DIAG_PORT>/documind_e0_diagnostic
asyncpg_dsn:    postgresql://<DIAG_ROLE>@<DIAG_HOST>:<DIAG_PORT>/documind_e0_diagnostic
```
No real credentials inserted; no secrets file created; `.env` not modified.

## 8. Schema requirements preservation (Task 7 — verified, not redesigned)

`e0_diagnostics/retrieval_schema_requirements.json` remains authoritative and unchanged this phase. Preserved: tables `users` / `documents` / `document_chunks`; vector column `embedding vector(384)`; cosine `<=>` with `1 - distance` similarity; metadata filters (`user_id` ownership, `embedding_status='ready'`, `embedding IS NOT NULL`); identifiers as defined by the existing models; `ORDER BY embedding <=> … LIMIT top_k`. Retrieval SQL itself (`chat/rag.py::retrieve_chunks`, identical at `embeddings/routes.py`) is referenced, never edited. Provenance sidecar `e0_chunk_provenance` remains as *defined* in 4F.6-E (offsets don't exist in the production schema) — creation only when the diagnostic DB exists.

## 9. Corpus readiness (Task 8 — **VERIFIED this phase**)

Fingerprint recipe (now recorded so future checks reproduce): files sorted by name; `sha256` over interleaved `filename_bytes || file_bytes`.

| Check | Result |
|---|---|
| Source corpus fingerprint `3ec81cc5868f29a047409358943127509b4700cf2ddae1b877030059e4687ab1` | **match** (6 JSON files) |
| Chunk corpus fingerprint `e6965cdad6684c65b739a316e01cff9e020e96a1588ec4aa37b19cfe98b135ea` | **match** (6 JSONL files) |
| Source documents | **6/6**; per-document `document_sha256` mismatches **0** |
| Chunk rows | **93/93** |
| document_id mapping + ordering | present (`document_id`, `sequence` on every chunk) |
| structural metadata | present (`structure` block, offsets `source_start`/`source_end`, `chunker_version`, `source_document_hash`) |
| provenance sidecar design | defined (4F.6-E §6 mapping); creation deferred to runtime |

**Not ingested** — per scope, corpus stays on disk only.

## 10. Resume test (Task 9 — exact order once media exists)

A. server detection → B. version verification → C. pgvector verification → D. isolation proof → E. schema verification → F. offline embedding verification → G. ingest 6 documents / 93 chunks → H. count & hash validation (6/6, 93/93, 0 mismatches) → I. 3–5 question retrieval smoke test → J. one unanswerable smoke test → K. runtime retrieval parity verification → **only then** reconsider the E0 execution gate (4F.6-F Task 15, twelve conditions). This phase does not start any of A–K.

## 11. Failure conditions (Task 10 — runtime stays blocked if any holds)

- PostgreSQL is not local (no remote/cloud/Supabase) · pgvector **server** extension missing · diagnostic DB cannot be isolated · production `documind` is the only available target · runtime requires a network download · existing retrieval code must be modified · corpus hashes change unexpectedly · vector dimension ≠ 384 · cosine operator unavailable · retrieval scores cannot be produced genuinely.
- Never substitute another retrieval engine (no SQLite, no FAISS, no in-memory cosine search, no fabricated traces).

## 12. Scientific boundary (Task 15)

This document asserts nothing about retrieval quality, retrieval bottleneck, model quality, representation quality, answerability quality, or H-A/H-B/H-C/H-D/H-E — in either direction. It exists solely to make the later measurements possible and honest. Prepared instructions are **not** evidence of readiness (Task 14).

## 13. Validation (Task 13) — all PASS

- Benchmark `qa_benchmark_v1.jsonl`: 182 lines / 42 `is_impossible`, sha256 `1166bf4ff38265c2…` — **unchanged**
- Dataset `training_data_v3_1.jsonl` sha256 `a517530354fc9bca…` — **unchanged** · production model `model.safetensors` sha256 `cb9f1dde94fca0e1…` — **unchanged**
- Source fingerprint **match**, chunk fingerprint **match** (recipe recorded §9) · production code untouched · **no production DB access, 0 SQL executed** · **no software installed, no downloads, no network, no GitHub** · no training · no E0 execution · **no retrieval traces created** (`retrieval_traces.jsonl` and `retrieval_traces_smoke.jsonl` both absent; manifest `retrieval_trace_status = "NOT_EXECUTED"`) · **no secrets created** (§7 placeholders only) · no commit · no push

## 14. Final status (Task 14)

Media search returned `C. NO_MEDIA`; therefore:

# `FINAL STATUS: E0_OFFLINE_RUNTIME_BLOCKED`

```
MISSING: PostgreSQL server installation media + matching pgvector server extension media
```

E0 remains blocked (4F.6-F gate conditions 1–2 still FAIL). The next actionable event is the operator completing setup order §6 (steps 1–5) from **locally supplied** media; then Phase 4F.6-F resumes at Task 1 detection → Tasks 6–18. Prepared instructions alone do not make E0 ready.

```
GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
SOFTWARE INSTALLED: NO
DOWNLOADS: NO
SQL EXECUTED: NO
PRODUCTION DATABASE ACCESSED: NO
PRODUCTION CODE MODIFIED: NO
BENCHMARK MODIFIED: NO
DATASET MODIFIED: NO
MODEL MODIFIED: NO
TRAINING RUN: NO
E0 EXECUTED: NO
RETRIEVAL TRACES CREATED: NONE
SECRETS CREATED: NO
COMMIT: NO
PUSH: NO
```
