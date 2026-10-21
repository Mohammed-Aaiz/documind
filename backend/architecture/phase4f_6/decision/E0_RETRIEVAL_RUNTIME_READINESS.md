# E0 RETRIEVAL RUNTIME READINESS — Phase 4F.6-E (Tasks 12–15)

> **⚠ CORRECTION (2026-09-27) — see [`E0_ERRATUM_2026-09-27.md`](./E0_ERRATUM_2026-09-27.md).**
> Two statements below are inaccurate and must not be relied on:
> - "`backend/.env`'s `DATABASE_URL` (`postgresql+asyncpg://…@localhost:5432/documind`
>   = production target)" → the real `backend/.env` targets a managed remote PostgreSQL
>   service. Correction **C2**.
> - "no migrations (repo has no alembic…)" → an Alembic environment **does**
>   exist (`backend/alembic.ini` + `backend/migrations/`). Correction **C5**.
> The body below is preserved unaltered as the historical record of Phase 4F.6-E.

**Date:** 2026-09-23 · **Nature:** environment/readiness work only — **no E0 execution, no smoke test executed, zero retrieval traces**. Evidence: `e0_diagnostics/diagnostics/embedding_offline_verification.json`, `e0_diagnostics/retrieval_schema_requirements.json`, `decision/E0_RETRIEVAL_RUN_MANIFEST.json`.

---

## 1. Runtime availability — Task 1 inventory → classification `D. NO_LOCAL_POSTGRES`

| Probe (local state only) | Result |
|---|---|
| Windows services (`sc query … state= all`) | no postgres service registered |
| Registry `HKLM\SYSTEM\CurrentControlSet\Services` | no postgres key |
| PATH executables (`command -v` + `where.exe`: psql/pg_ctl/postgres/initdb/pg_config) | none |
| Install locations (Program Files(x86), C:\postgres, C:\pgsql, C:\tools, scoop, chocolatey, D:\) | none exist |
| Data directories (PG 14–17 defaults, %APPDATA%/%LOCALAPPDATA%/postgresql) | none exist |
| Listening sockets 5430–5439 (netstat) | none at all |
| Docker | absent |
| Offline installers/archives (Downloads) | none |
| venv packages matching pg/postgres/vector | `pgvector==0.5.0` **client library only** (Python `Vector` type — cannot substitute for the server extension) |

**Classification: `D. NO_LOCAL_POSTGRES`.** Authorization questions (classes B/C) never arise. Tasks 2, 3, 7 (creation), 8, 9, 10, 11-execution are **gated off** → recorded as `NOT_APPLICABLE` below, with preparation content completed where it does not require a server.

## 2. Isolation plan (Task 7 definition — prepared, NOT created)

- **Database identifier (planned):** `documind_e0_diagnostic` (or an equivalently named dedicated schema in a dedicated instance).
- **Connection target:** a diagnostic DSN that is **not** `backend/.env`'s `DATABASE_URL` (`postgresql+asyncpg://…@localhost:5432/documind` = production target — never used, never altered).
- **Isolation proof requirements (must all hold at creation time):** (a) database name ≠ `documind`; (b) application config files unchanged — the diagnostic DSN is passed only to an explicit diagnostic run command, never written to `backend/.env`; (c) no rows written to any database referenced by production config; (d) role/ownership scoped to the diagnostic database; (e) verification query showing `current_database() = 'documind_e0_diagnostic'` recorded in the runtime manifest before ingestion.
- **Status:** `DEFINED_NOT_CREATED` — Task 7 is gated on an authorized non-production runtime already existing; none exists (§1).

## 3. Versions (Task 12 fields)

- **PostgreSQL version:** N/A — no server exists (classification D).
- **pgvector version:** server extension **N/A/ABSENT**; client library `pgvector==0.5.0` (venv) recorded. No installation attempted (network forbidden).

## 4. Embedding model — Task 6, re-verified offline this phase → **PASS**

| Field | Value |
|---|---|
| model identifier | `sentence-transformers/all-MiniLM-L6-v2` |
| implementation | `backend/embeddings/model.py` (`embed_query`/`embed_texts`, `_DIMENSIONS=384`) |
| cache location | `C:\Users\moham\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2` (snapshot `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`) |
| dimension | **384** (matches `Vector(384)`) |
| checksums | all snapshot files sha256-recorded (`model.safetensors` `53aa5117…d9db`, `tokenizer.json` `be50c362…2037`, full set in `diagnostics/embedding_offline_verification.json`) |
| offline load | **success** under `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`; `network_needed: false` |
| determinism | identical outputs across repeated encodes (`deterministic_across_runs: true`), probe norm 1.0 |

No download attempted; had the model required network, this phase would BLOCK on Task 6 — not needed.

## 5. Retrieval implementation & contract — Task 5 (verified by inspection; NOT rewritten)

- **Function:** `chat/rag.py::retrieve_chunks(db, user_id, query, top_k=5)`; second call site `embeddings/routes.py::semantic_search` (endpoint `topK` default 5).
- **SQL:** byte-identical at both sites (grep-verified): `1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity … WHERE d.user_id=:user_id AND d.embedding_status='ready' AND dc.embedding IS NOT NULL ORDER BY dc.embedding <=> CAST(:embedding AS vector) LIMIT :top_k`.
- **Embedding model:** all-MiniLM-L6-v2 · **dimension:** 384 · **operator:** pgvector cosine `<=>` · **similarity:** `1 − distance` · **top_k:** 5 · **ordering:** cosine-distance ascending, `LIMIT top_k` · **filters:** user ownership + `embedding_status='ready'` + `embedding IS NOT NULL` · **returned fields:** chunk_id, content, document_id, document_name, page, similarity (+ heading_path, section, element_type, token_count, chunker_version on the rag path).
- **Thresholds (downstream, recorded for completeness):** `rag_answer` `relevance_threshold=0.15`; insufficient-context gate `qa_score<0.30 AND best_retrieval<0.50`. The embeddings `/search` endpoint applies no threshold (pure top-k).
- **Second algorithm introduced:** none. **Rewrites:** none. Full schema contract: `e0_diagnostics/retrieval_schema_requirements.json` (Task 4 output: tables/columns, vector(384), cosine, metadata, identifiers, indexes — ANN index not declared anywhere and not required by the SQL at 93 chunks).

## 6. Diagnostic ingestion preparation — Task 8 (mapping prepared; execution N/A)

Planned field mapping honoring every preservation requirement, using **only existing columns**:

| Isolated artifact (4F.6-D) | Existing column | Preserved |
|---|---|---|
| `document_id` (e.g. `company_history_eta`) | `documents.name` (verbatim) + `documents.id` = deterministic UUIDv5 (recorded in sidecar) | document IDs ✓ |
| `document_sha256` (64 hex) | `documents.content_hash` (varchar 64 — exact fit) | source hashes ✓ |
| `chunker_version: chunk-v1-legacy-chars-1000-200` | `documents.chunker_version` + `document_chunks.chunker_version` | chunker version ✓ |
| chunk sequence | `document_chunks.chunk_index` | order ✓ |
| isolated `doc_id::cNNN` | `document_chunks.embedding_id` (varchar 255, verbatim) + `id` = deterministic UUIDv5 (sidecar) | chunk IDs ✓ |
| chunk text | `document_chunks.content` (byte-identical to isolated corpus) | text ✓ |
| structure ids (section/table/row/cell/list/item) + `heading_path/section/element_type/token_count/page` | same-named columns; full span index → sidecar `structure json` | structural metadata ✓ |
| `source_start/source_end` per chunk | **no columns exist in the schema** → preserved in the diagnostic-only sidecar `e0_chunk_provenance` + the isolated corpus files (never dropped, never schema-altered) | source offsets ✓ (via sidecar; documented schema gap) |
| embeddings | `embed_texts()` (existing implementation) → `document_chunks.embedding` | existing embedding path ✓ |
| status fields | `documents.embedding_status='ready'`, `status='ready'`, `chunk_count` | retrieval filters satisfiable ✓ |

Scope guards: **only** the 6 reconstructed documents and 93 chunk records are ever candidates for ingestion — no benchmark example is stored as a document; frozen benchmark/dataset untouched; ingestion executable only after §10 conditions exist.

**Ingestion counts (actual, from database):** documents **0/6**, chunks **0/93** — `NOT_APPLICABLE` (no server exists; no placeholders written anywhere).

## 7. Smoke test — Task 10: **NOT_RUN**

- Questions executed: **0** (planned set: 3–5 P3 answerable questions, existing retrieval path, recorded query/top_k/doc ids/chunk ids/ranks/scores).
- `retrieval_traces.jsonl`: still **not created**; manifest `retrieval_trace_status = "NOT_EXECUTED"`; zero rows anywhere; nothing fabricated.
- No smoke conclusions of any kind exist to evaluate (Task 16 is vacuously satisfied: no test ran, so no claim about retrieval quality/bottleneck/hypotheses can or does appear).

## 8. Parity — Task 11: static contract parity **VERIFIED BY INSPECTION**, runtime parity **NOT VERIFIED → not E0-ready**

| Item | Static result |
|---|---|
| same retrieval function | ✓ `retrieve_chunks` identified as the single rag path; `/search` endpoint uses the identical SQL string |
| same SQL | ✓ byte-identical strings at both call sites (grep count 2/2 each) |
| same embedding model | ✓ all-MiniLM-L6-v2, offline-verified §4 |
| same vector dimension | ✓ 384 = `Vector(384)` |
| same top_k | ✓ 5 (signature default + endpoint default) |
| same threshold | ✓ 0.15 / gate (0.30, 0.50) recorded; no second threshold exists |
| same ranking rule | ✓ `ORDER BY embedding <=> … LIMIT` unchanged |
| only intended change = isolated database/corpus | ✓ planned (DSN + rows only; config files untouched) |

Runtime parity **requires execution against a live diagnostic database** → cannot be verified this phase. Per Task 11: not calling it E0-ready.

## 9. Exact runtime blocker (Task 15) + what must exist before resuming

**Blocker:** no PostgreSQL+pgvector *server* runtime exists on this machine (classification D) and none may be obtained with network access — so there is nothing for the existing retrieval implementation to execute against. Explicitly **not** done, per Task 15: no internet install, no SQLite, no FAISS, no in-memory cosine substitute, no fabricated traces, E0 kept blocked.

**Precise local operator setup requirements (future authorized environment):**
1. **Offline-obtained PostgreSQL 16/17 Windows x64 installation media**, provided by the operator from an authorized source (the agent must not download), installed locally as a service.
2. **pgvector extension files matching that PostgreSQL version** from the same offline media (SQL/control/DLL set); verification: `CREATE EXTENSION vector;` succeeds and `SELECT * FROM pg_extension WHERE extname='vector'` returns a version — record it (≥0.5 line compatible with client 0.5.0).
3. **Dedicated non-production database** `documind_e0_diagnostic` (or dedicated instance) + role scoped to it; isolation proof per §2 recorded **before** any row is written. Production DSN in `backend/.env` remains untouched.
4. **Schema creation via the existing in-repo pattern** `Base.metadata.create_all` (as `backend/tests/conftest.py:115`, with all models imported) — no migrations (repo has no alembic; production creation method is *not verified in-repo* per `runbooks/migration-failure.md`).
5. **Then, in order:** ingest 6 documents + 93 chunks via the existing embed path (§6) → Task 9 validation with actual DB counts (6/93/93-unique/384-dim/hashes) → Task 10 smoke (3–5 questions) → Task 11 runtime parity → re-evaluate §14 gate → only then schedule the full 182-example E0 trace phase.

## 10. E0 gate — Task 14 (all ten conditions)

| # | Condition | Result |
|---|---|---|
| 1 | Authorized non-production PostgreSQL exists | **FAIL** (classification D) |
| 2 | pgvector exists (server) | **FAIL** (client-only; no server to extend) |
| 3 | Database isolated from production | **UNVERIFIABLE** (nothing exists; isolation plan §2 prepared) |
| 4 | Existing retrieval implementation executes unchanged | **FAIL** (no execution possible) |
| 5 | Local embedding model loads offline | **PASS** (§4) |
| 6 | 6 documents + 93 chunks ingested correctly | **FAIL** (0/6, 0/93 — N/A) |
| 7 | Diagnostic retrieval returns genuine scores/ranks | **FAIL** (no query ever issued) |
| 8 | Smoke test passes | **FAIL** (NOT_RUN, 0 questions) |
| 9 | Retrieval parity verified | **FAIL** (static-only; runtime unverifiable) |
| 10 | No frozen artifact or production state changed | **PASS** (§17 validation) |

**Any failure ⇒ do not execute E0.** Seven conditions fail → **E0 NOT executed this phase.**

## 11. Remaining blockers (consolidated)

1. **B-R1 (decisive):** local PostgreSQL 16/17 + matching pgvector server extension, offline/operator-provided (§10.1–10.2).
2. **B-R2:** authorized creation of the isolated `documind_e0_diagnostic` database with recorded isolation proof (§2, §10.3).
3. **B-R3 (then):** ingestion → Task 9 DB-count validation → Task 10 smoke → Task 11 runtime parity → gate re-check. Only after all: the full E0 182-example run, which remains a **separate later phase**.

## 12. Files

**Created:** `decision/E0_RETRIEVAL_RUNTIME_READINESS.md` (this file) · `e0_diagnostics/retrieval_schema_requirements.json` · `e0_diagnostics/diagnostics/embedding_offline_verification.json`.
**Updated:** `decision/E0_RETRIEVAL_RUN_MANIFEST.json` (Task 13: `retrieval_trace_status: "NOT_EXECUTED"` + `phase_4f_6e_runtime_update` block; no trace rows added).
**Not created:** any retrieval trace, any database, any table, any row.

---

# `FINAL STATUS: E0_RETRIEVAL_RUNTIME_BLOCKED`

**Exact runtime dependency preventing progress:** a local **PostgreSQL (16/17) server with the pgvector extension** — neither exists on this machine (no binaries, no service, no data dir, no sockets, no offline install media; only the pgvector 0.5.0 Python client is present). Per Task 15: no network install, no substitute engines, no fabricated traces; E0 remains blocked.

```
GITHUB ACCESSED: NO
NETWORK ACCESSED: NO
TRAINING RUN: NO
E0 EXECUTED: NO
SMOKE TEST RUN: 0 QUESTIONS
RETRIEVAL TRACES: NONE — retrieval_trace_status = NOT_EXECUTED
PRODUCTION DATABASE MODIFIED: NO (never connected)
PRODUCTION CODE MODIFIED: NO
BENCHMARK MODIFIED: NO
DATASET MODIFIED: NO
MODEL WEIGHTS MODIFIED: NO
SOURCE/CHUNK CORPUS MODIFIED: NO (fingerprints recorded §manifest)
HISTORICAL ARTIFACT MODIFIED: NO
SQL EXECUTED ANYWHERE: NO (0 DDL, 0 DML)
COMMIT: NO
PUSH: NO
```
