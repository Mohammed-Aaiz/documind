# PGVECTOR-LIFECYCLE-AUTH-02 — PostgreSQL/pgvector Lifecycle Authorization Design

## 1. Document identity, version, status, authorship

| Field | Value |
|---|---|
| Task ID | `PGVECTOR-LIFECYCLE-AUTH-02` |
| Document | **NEW design**, authored from scratch on 2026-10-16 |
| Version | `0.1.0-draft` |
| Status | `NEW DESIGN DRAFTED — INDEPENDENT REVIEW PENDING` |
| Authorship | Authored by the agent operating under the owner's instruction for this task |
| Relationship to `PGVECTOR-LIFECYCLE-AUTH-01` | **None asserted.** The `-01` design text could not be recovered (see §5.0). This document is **not** a recovery, continuation, faithful reconstruction, or restatement of it. Where a control here resembles an earlier recommendation, that is convergent reasoning, not provenance |
| Implementation status | **Not implemented.** No source file was modified. This document is the only artifact created by this task |
| Independent review | **Not performed and not claimed.** See §16 |

**Claim-status vocabulary used throughout.** `VERIFIED` = read from current source at the cited line range. `DESIGN DECISION` = chosen here, not yet implemented. `ASSUMPTION` = believed true, not verified. `UNRESOLVED` = requires an owner or reviewer decision. `PROPOSED CONTROL` = a control this document specifies.

## 2. Executive summary

DocuMind reprocesses documents by deleting a document's previous chunks (which cascades to its pgvector embeddings and graph edges) inside one request transaction and rebuilding them, rolling back on failure so the last indexed version survives (`documents/routes.py:740-859`). Everything that drains, rebuilds, verifies or cleans such data is a **lifecycle operation** — create, migrate, write, inspect, clean, dispose — and the project has no enforceable authority for any of it. Today every destructive lifecycle primitive **refuses unconditionally** (`evaluation/isolation.py:378-441`), which is safe but blocks work, and the destructive-success tests are explicitly skipped for that reason (`tests/fixtures/disposable_db.py:22-37`).

This design supplies the missing authority as one coherent mechanism: a single **canonical target identity** that no caller can assemble from parts, an **Ed25519-signed registration** that names the target and the permitted operations, a **`RegisteredTargetRun`** object that is the only accepted entry argument (a DSN never is), **connection-time validation** on every physical connection including pool checkouts and reconnects, **least-privilege roles** with a justified privilege list, a **run-scoped manifest** that makes cleanup provable and idempotent, an explicit **state machine** with fail-closed terminals, and **redaction and secret-delivery** rules that keep credentials out of argv, logs, exception text and subprocess output.

Two properties are deliberately **not** claimed: that any of this is verified against a live PostgreSQL server (nothing in this task touched a database), and that concurrency safety is enforced across hosts (it is not — see §9-I and §14).

## 3. Scope and non-goals

### 3.1 In scope
1. Creating, migrating, populating, inspecting, cleaning and disposing a **disposable PostgreSQL + pgvector target** used to verify document-preservation behaviour during reprocessing.
2. Preventing the **application database** and any unregistered database from being modified by test, evaluation, harness or migration code.
3. The **preservation invariant** of reprocessing: a failed attempt must leave the last successfully indexed version intact and searchable.
4. Authorization, identity binding, least privilege, secret handling, redaction and audit for the above.

### 3.2 Explicit non-goals
- Implementing any control (this is a design).
- Gate 27 (per-document atomic run claims, active-run identity, collision-resistant run IDs, concurrency-safe cleanup) — **separate, unresolved, not approved**.
- The QA/embedding model's quality, retrieval relevance, or ranking behaviour.
- Production data migration of any kind.
- Cross-host mutual exclusion (declared out of scope, with the consequence stated in §9-I/§14).
- Provisioning by this design: the cluster, roles and the private signing key are operator acts (§15).

## 4. Verified repository baseline

Read-only, 2026-10-16:

| Item | Observed value |
|---|---|
| Branch / HEAD | `main` / `6baaa2a0773df66e5fb26814afbe67647fb43435` (matches the previously reported HEAD; unchanged) |
| Staged | 0 |
| Unstaged modified | 331 |
| Untracked (non-ignored) | 865 |
| Ignored entries | 77 |
| Total status entries | 386 |
| Files changed by this task | **1 new file** (this document). No existing file was created, edited, renamed or deleted |

Content hashes of the evidence files (sha256, first 12 hex chars), re-confirmed during this task and unchanged from the earlier verification in this session:

```
evaluation/isolation.py               d41aded078ca
tests/fixtures/integration_db.py      9ac725e26328
tests/fixtures/e2e_config.py          d04f0215197a
main.py                               0668ebde2a27
migrations/env.py                     b37a3aba9962
config.py                             cc3df7f07f63
storage/database.py                   e31e020d4c9b
scripts/setup_db.py                   87e74ad01dd4
tests/conftest.py                     51ef64c83970
```

No `.env` file, credential, token or private key was read; no database was contacted; no migration, service, subprocess or destructive command was executed.

## 5. Evidence-based current-state findings

### 5.0 The `-01` design text
`VERIFIED`: no repository artifact contains `PGVECTOR-LIFECYCLE-AUTH` (tracked or untracked), nor the identifiers `RegisteredTargetRun` or `Ed25519`; the git object store holds no copy (174 unreachable blobs, the reflog-only commit `d671907`, all searched — 0 matches). The original wording is unavailable. **RV-1–RV-8 are therefore treated as historical labels with unknown definitions** (§10).

### 5.1 F-1 — credential/target identity can be assembled from two sources
`VERIFIED` (source). `tests/fixtures/integration_db.py:302-337`: `psql_value(dsn, sql)` takes `host`, `port`, `user`, `password` from `e2e_config.postgres()` (`:311`, `:313`) but the **database name** from the passed `dsn` (`:323` `"-d", database_identity(dsn)[2]`). `e2e_config.database_url()` resolves `DOCUMIND_E2E_DATABASE_URL` → `backend/.env` `DATABASE_URL` → ambient `DATABASE_URL` (`e2e_config.py:135-150`), while callers pass `application_database_url()`, which prefers `backend/.env` (`integration_db.py:124-131` → `isolation.py:125-140`). The two resolvers can therefore disagree, and the statement executes on the resolver's server as the resolver's role. Guards that do exist validate `database_identity(dsn)` = `(host, port, database)` (`isolation.py:146-155`) — a tuple that is **not** the connection actually used; the role is never validated and the password is never bound to the `dsn`. Reachability is currently bounded: `_drop_database` (`:350-368`) and `_create_database` (`:371-386`) call primitives that raise unconditionally first (`isolation.py:378-415`, `:418-441`), so those two paths cannot reach psql — the defect is **latent, not live**. `inspect_schema` (`:447-470`) and `e2e_config.psql` (`e2e_config.py:207-245`) have no local guard. This finding is also already registered in the project's own ledger (`STEP1_6M:84` F-M2; `STEP1_6P:88` P04).

### 5.2 F-1b — SQL/psql invocation safety
`VERIFIED`. Unescaped interpolation into SQL: `f"SELECT count(*) FROM pg_database WHERE datname = '{name}'"` (`:342`), `f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'` (`:361`), `f'CREATE DATABASE "{name}"'` (`:386`). Missing startup-file isolation and error trapping: the psql argv at `:316-327` carries no `-X` and no `-v ON_ERROR_STOP=1`. Subprocess exit handling is present (`returncode` checked at `:332`, `:419`, `:437`) but a partial multi-statement run cannot be detected.

### 5.3 F-2 — subprocess output is truncated, not redacted
`VERIFIED`. Five sites embed raw child output into raised exceptions: `integration_db.py:335` (`stderr[:400]`), `:424` (`stderr[:400]`), `:444` (`stdout[-600:]` + `stderr[-600:]`), `e2e_config.py:240` (`stderr[:400]`), `e2e_config.py:318` (`stderr[:400]`). Truncation bounds length, not content. Two of those paths place a **password-bearing DSN** in the child's environment (`integration_db.py:402-403`; `e2e_config.py:302-303`), and `main.py:67` logs `logger.error("Database migration failed: %s", exc, exc_info=True)`, so a DSN echoed by any child or driver error reaches the log. `NOT REPRODUCED`: a password appearing in psql's own stderr (the password travels via `PGPASSWORD`, `:313`, `e2e_config.py:218-221`). `INCONCLUSIVE`: whether a child traceback actually echoes the DSN — unrunnable here without a database.

### 5.4 F-2b — password on the command line
`VERIFIED`. `e2e_config.py:306` passes `["--password", password]` to `scripts/create_test_user.py`, which accepts only `--password` with a default test password (`scripts/create_test_user.py:64`). This contradicts the same module's stated policy at `e2e_config.py:39-41` and `:216-217` ("never argv… never a process listing").

### 5.5 F-3 — plain-string, cached settings with an import-time engine
`VERIFIED`. `config.py:43` `database_url: str` and `:46` `jwt_secret_key: str` are plain strings (no `SecretStr` anywhere in the repo); `get_settings()` is `@lru_cache`d (`:182-183`) and reads `.env` (`:37`); `storage/database.py:41` captures the URL and `:43` builds the engine **at import**, with `pool_pre_ping=True`. Nothing in the repository currently logs or prints settings (grep: 0 call sites), and SQLAlchemy 2.0.36 masks the password in both `repr` and `str` of a URL (observed in-memory: `postgresql+asyncpg://documind:***@…`), whereas pydantic prints field values in `repr` and in `ValidationError` text (observed on a synthetic model). `UNRESOLVED`: mid-run rotation/revocation is not supported — the URL is cached and captured at import, so a rotated credential is not picked up and a `pool_pre_ping` reconnect reuses the original URL.

### 5.6 Startup and migration paths
`VERIFIED`. `main.py:44-53` runs `command.upgrade(cfg, "head")` from the FastAPI `lifespan` (`:76-84`, dispatched via `run_in_executor` at `:65`) against whatever `settings.database_url` resolves to — **application startup migrates a database unconditionally**. The Alembic CLI path resolves the URL from cached settings but swallows every failure (`migrations/env.py:44-57`, bare `except Exception: pass`), falling back to the hard-coded loopback placeholder `alembic.ini:3`. The operator script passes no `env=` to its subprocess (`scripts/setup_db.py:38-43`), so it inherits the ambient environment and prints child stdout/stderr verbatim (`:44-55`). Tests never trigger the lifespan: the client uses `ASGITransport(app=app)` with no lifespan manager (`tests/conftest.py:212-217`), and the unit-test engine is **SQLite in-memory** (`tests/conftest.py:50`, `:144-151`) with dialect-scoped type compiles for `postgresql.UUID`/`JSONB` (`:62-69`) — so a green unit suite proves nothing about PostgreSQL behaviour.

### 5.7 What must be preserved
`VERIFIED`. The reprocess endpoint deletes old chunks and structure rows provisionally inside the request transaction, runs the pipeline, commits only on success, and rolls back otherwise (`documents/routes.py:826-859`), so the previous version — chunks, `Vector(384)` embeddings (`documents/models.py:74`), structure elements, graph edges — is restored on failure. `documents/models.py`: `stored_path` (`:35`), `content_hash` (`:36`), `chunk_count` (`:40`), `embedding_status` (`:44`), `processing_started_at` (`:53`); FKs cascade on delete (`document_chunks.document_id`, `:69-71`). Ownership is reached through `document_id → documents.user_id`. Staleness is `_STALE_PROCESSING_SECONDS = 600` (`documents/routes.py:80`, `:419-426`). Existing cleanup precedent: archive-not-delete with a scan/apply split (`scripts/cleanup_orphan_uploads.py:74-157`, `main` `:455`) and descriptor-relative deletion with symlink/reparse-point refusal (`scripts/cleanup_path.py:74-250`).

## 6. Threat model and trust boundaries

**Actors / processes:** application runtime (server, lifespan migrations); operator (shell, `scripts/setup_db.py`, signing key holder); test harness (pytest, `tests/fixtures/*`); evaluation runners (`evaluation/experiments/*`); cleanup workers; the PostgreSQL server and its roles; subprocess children (`psql`, `alembic`, `create_test_user.py`).

**Trust boundaries:** (B1) process ↔ cluster over the network; (B2) developer workstation ↔ registration store and signing key; (B3) application process ↔ test/evaluation process inside the same checkout; (B4) parent ↔ child process (argv, environment, inherited file descriptors); (B5) repository contents ↔ operator intent.

| # | Threat | Controls | Status |
|---|---|---|---|
| T1 | A test or evaluation run modifies the **application database** | C-C*, C-E*, C-F* | DESIGN DECISION |
| T2 | A run reaches an **unintended but valid** database (staging clone, second checkout) | C-C1–C-C5, C-D* | DESIGN DECISION |
| T3 | Credentials leak via argv, environment, logs, exceptions, subprocess output | C-J3–C-J6, C-K3 | DESIGN DECISION |
| T4 | A forged or replayed registration authorizes a target | C-D3–C-D8 | DESIGN DECISION |
| T5 | Privilege escalation: the lifecycle role exceeds its allowlist | C-G1–C-G6 | DESIGN DECISION |
| T6 | Cleanup deletes data the run did not create | C-H1–C-H7 | DESIGN DECISION |
| T7 | Configuration drift between authorization and use (TOCTOU) | C-C5, C-E2, C-E4 | DESIGN DECISION |
| T8 | Concurrent runs race (duplicate creation, cleanup of a live run) | C-I2–C-I5 | **PARTIAL** — single-cluster only |
| T9 | Application startup migrates a test-only database | C-F1–C-F4 | DESIGN DECISION |

**Cryptography cannot solve:** operator compromise (whoever holds the private key can sign anything), a compromised workstation or OS credential store, cluster superuser, and the fact that a *valid signature proves who authorized a target, never that the target is safe or empty*.

## 7. Architecture and data flow

```
operator ──(private key, offline)──► signs Registration (canonical JSON + Ed25519)
                                        │  stored: registration store, repo-owned public key
                                        ▼
caller ──► RegisteredTargetRun(TIR, operations, run_id, registration, expiry)
              │  built only by the authorizing factory; a DSN is never accepted
              ▼
        pre-flight gates (registration verify → identity → privileges → run state)
              ▼
        engine (NullPool for lifecycle) ──► connect event hook on EVERY connection
              │                                  validate current_database/current_user/
              │                                  server addr+port/backend pid/role attrs/SSL
              ▼                                  mismatch ⇒ disconnect + raise
        operation ──► manifest (written BEFORE first write) ──► work ──► verify
              ▼
        cleanup (manifest-scoped, idempotent) ──► dispose ──► audit record
```

## 8. Lifecycle state machine

States: `UNREGISTERED → REGISTERED → VALIDATED → EXECUTING → {COMMITTED, FAILED}` with `CLEANING → CLEANED`; terminals `EXPIRED`, `REVOKED`, `REPLAY_DETECTED`, `IDENTITY_MISMATCH`, `QUARANTINED`.

| Transition | Precondition | Failure mode |
|---|---|---|
| `REGISTERED → VALIDATED` | signature verifies against the pinned public key; not expired/revoked; not replayed; TIR complete | any failure ⇒ refuse before I/O; `EXPIRED`/`REVOKED`/`REPLAY_DETECTED` |
| `VALIDATED → EXECUTING` | connection hook passed; role attributes match; run record written and manifest persisted | `IDENTITY_MISMATCH`; engine disposed, no write |
| `EXECUTING → COMMITTED` | operation completed and verification passed | — |
| `EXECUTING → FAILED` | any exception | transaction rolled back; data preserved; evidence recorded |
| `COMMITTED/FAILED → CLEANING` | manifest present and parseable; ownership provable | unprovable ownership ⇒ `QUARANTINED`, **preserve** |
| `CLEANING → CLEANED` | every manifest resource deleted or proven absent; re-scan reports zero survivors | partial ⇒ remain `CLEANING`, retryable |

Invariant: **no state other than `EXECUTING`/`CLEANING` may write**, and `REVOKED`/`EXPIRED` may always move a run out of `EXECUTING` at the next check point (§9-E4), never into a write.

## 9. Detailed controls A–K

Each control: **threat → control → enforcement point (EP) → failure mode → verification → residual risk**.

### A. Scope, objectives, non-goals
**C-A1** (DESIGN DECISION) Lifecycle operations are: `CREATE_TARGET`, `MIGRATE_TARGET`, `SEED`, `INSPECT`, `CLEAN`, `DISPOSE`. Each is a distinct capability in the registration; a registration for `INSPECT` never authorizes `CLEAN`. Preserved during reprocessing: previous chunks, `Vector(384)` embeddings, structure elements, graph edges, `content_hash`, `stored_path`, and the document's searchable status. Prohibited: any operation against the application database; any unregistered target; any broad table/schema/database-wide deletion.

### B. Threat model and trust boundaries
**C-B1** §6 is normative. **C-B2** The trusted computing base is: the OS, the Python runtime and its dependencies, the PostgreSQL server, the pinned public key, and the operator. Everything else — callers, DSNs, environment variables, Python objects, manifests, child processes — is **untrusted input**.

### C. Authoritative target identity
**C-C1** (DESIGN DECISION) One canonical **Target Identity Record (TIR)**, created once by a single resolver and immutable thereafter:

| Field | Source | Verifiability |
|---|---|---|
| `scheme` | configuration | asserted |
| `host` + `resolved_ip` | configuration + DNS at pre-flight | partially verifiable (DNS can change) |
| `port` | configuration | asserted |
| `database` | configuration | asserted |
| `role` (`username`) | configuration | asserted |
| `cluster_id` | `SELECT system_identifier FROM pg_control_system()` (or a recorded cluster UUID table) | **independently verifiable on the connection** |
| `tls_mode` | configuration + `current_setting('ssl')` / `pg_stat_ssl` | verifiable |
| `role_attrs` | `pg_roles.rolsuper/rolcreatedb/rolcreaterole/rolbypassrls` | verifiable |

**C-C2** No component may combine fields from two sources: the resolver is pure and returns a TIR or raises. The previous defect is precisely a violation of this rule (`integration_db.py:311` + `:323`).
**C-C3** A caller-supplied DSN is **never** identity proof; it is a *claim*, admitted only as input to the resolver and then discarded in favour of the TIR.
**C-C4** Connection-override query parameters (`host`, `hostaddr`, `port`, `dbname`, `service`) are refused outright — the existing precedent (`isolation.py:87`) is retained and extended to the resolver.
**C-C5** TOCTOU: the TIR is re-derived from the *live connection* at every enforcement point; nothing cached from pre-flight is trusted at write time.
*Failure mode:* incomplete TIR, unresolvable host, or an override parameter ⇒ refuse before any socket or subprocess. *Residual risk:* `port`/`host` cannot by themselves prove cluster identity — only `cluster_id` can, and only if the role may read it.

### D. Registration and cryptographic authorization
**C-D1** Only the **operator** may register a target; registration is an offline act performed with a private key that never enters the repository, the application process, or CI.
**C-D2** Payload (canonical JSON, RFC 8785, `schema_version: 1`): `{schema_version, registration_id (UUIDv7), target: TIR, operations: [...], run_id_scope, issued_at, not_before, expires_at, nonce, operator_id}`.
**C-D3** Signature: **Ed25519** over the canonical bytes. The public key is pinned in the repository/configuration; the private key is held by the operator only. (`cryptography 50.0.1` is already available via `requirements.txt:9` — **no new dependency is required**, and none may be added without owner approval.)
**C-D4** Verification is fail-closed: missing, malformed, non-canonical, unknown-key, expired, not-yet-valid, wrong-operation, wrong-target or revoked ⇒ refuse before I/O.
**C-D5** Replay resistance: `registration_id` is single-use per run; the consumed id is recorded in the run store; reuse ⇒ `REPLAY_DETECTED`.
**C-D6** Revocation: an operator-held revocation list (monotonic, hashed) is consulted at every pre-flight and at every re-check point; a revoked registration cannot authorize a new write and forces `CLEANING`.
**C-D7** Key rotation: `key_id` is part of the payload; multiple public keys may be pinned with disjoint validity windows; a signature is accepted only under the key valid at `issued_at`.
**C-D8** Binding: the registration binds **target identity + permitted operations + run id scope**. The `RegisteredTargetRun` also carries the *digest* of the registration it was created from, so a caller cannot present a registration for one target while operating on another.
**C-D9** Storage integrity: registrations live outside the repository, owned by the operator, readable only by the operator and the run process; symlink/reparse-point refusal and path containment follow the existing precedent (`scripts/cleanup_path.py:74-200`).
*Residual risk:* the private key is a single point of trust; a stolen key forges valid registrations. Signing proves **authorization**, never target safety.

### E. Connection-time enforcement
**C-E1** (DESIGN DECISION) A SQLAlchemy `connect` event listener validates **every** connection, including new pool checkouts and reconnects: `current_database()`, `current_user`, `inet_server_addr()`, `inet_server_port()`, backend pid, `pg_roles` flags, and `cluster_id`. Mismatch ⇒ the connection is closed and the operation raises.
**C-E2** Pool policy: **`NullPool` for lifecycle/harness connections** (no reuse across validation boundaries — precedent exists at `migrations/env.py:85`). For application-facing pooled connections, per-connection validation is **mandatory and unavoidable** if pooling is retained; the design states plainly that transaction/connection pooling without per-checkout validation is **not supported**.
**C-E3** Revalidation triggers: before the first write; after any reconnect; before cleanup; on expiry/revocation; and at each batch boundary for long operations.
**C-E4** (DESIGN DECISION) URL comparison is explicitly **not** identity. The existing literal comparison (`isolation.py:504-522`, which opens no connection) remains useful as a cheap pre-flight but is demoted to *pre-flight only*; the authoritative check is C-E1 against the live session.
**C-E5** Fail-closed: if validation cannot run (permission denied reading `pg_roles`, unknown `cluster_id`, missing TLS state) the operation is refused, not downgraded.
*Failure mode:* validation error ⇒ dispose engine, raise, no write. *Residual risk:* a hostile server can lie; the assumption is a trusted server and TLS.

### F. Migration and application-startup isolation
**C-F1** (DESIGN DECISION) Application startup **must not migrate by default**. Startup migrations become conditional on an explicit `APPLICATION_MIGRATIONS=authorized` setting, and the default for tests, CI and evaluation is refusal. `main.py:44-53,76-84` is the enforcement point.
**C-F2** The Alembic settings-override fallback (`migrations/env.py:44-57`) must become a **hard refusal**: an unavailable or malformed settings source is an error, never a silent fallback to `alembic.ini:3`'s loopback placeholder.
**C-F3** `scripts/setup_db.py` must pass an explicit `env=` allowlist (never inherit the ambient environment) and must not print raw child stderr (`setup_db.py:38-55`).
**C-F4** Process separation: a process that holds application configuration may perform only application operations; a process that holds lifecycle authorization may target only the registered test target. A process holding **both** must choose explicitly before any I/O, and the choice is recorded in the audit record.
**C-F5** Test execution must never start the application lifespan (today's `ASGITransport` behaviour is incidental and must become an asserted invariant).
*Failure mode:* both configurations present and no explicit choice ⇒ refuse.

### G. Least privilege
**C-G1** (DESIGN DECISION) Three roles, no shared credentials:

| Role | Permitted | Forbidden |
|---|---|---|
| `documind_app` | DML/`SELECT` on the application schema; no DDL | DDL, `CREATE`, ownership of tables, access to the lifecycle schema |
| `documind_lifecycle` | `CREATE`/`DROP` on **tables and indexes inside a dedicated `lifecycle` schema** for the registered target; DML on that schema; `SELECT` on catalogs needed by §9-E | DML on any other schema; `SUPERUSER`; `CREATEROLE`; `BYPASSRLS`; ownership of `public`; `TRUNCATE` outside the lifecycle schema |
| `documind_inspector` | `SELECT` on catalogs and on the registered target's data for verification | all writes; all DDL |

**C-G2** Justified elevation: database creation/drop requires **`CREATEDB`**, which is cluster-wide and cannot be scoped to one database name. Options, in order of preference: (a) provision and drop the disposable database **out of band by an operator or a one-shot admin role** that holds `CREATEDB` only for that window; (b) a dedicated cluster/instance used only for disposables; (c) if `CREATEDB` is granted to `documind_lifecycle`, it must be paired with a naming policy, a `CONNECTION LIMIT`, and an explicit statement of the residual risk (the role can create any database on that cluster).
**C-G3** Object-level allowlist to be asserted at validation: schema ownership and `CREATE` on the schema; `TEMP`; `TRUNCATE`/`TRIGGER`/`REFERENCES`; column-level and default ACLs; sequence privileges; `SECURITY DEFINER` functions; `search_path` shadowing; RLS — each checked for *unexpected* grants, refusing on any unknown privilege.
**C-G4** `search_path` is set explicitly (never left to the server default or to a role default) at connection setup.
**C-G5** No `SECURITY DEFINER` function may be owned by a superuser in the lifecycle path.
**C-G6** Every privilege claim above is marked **NOT VERIFIED AGAINST A LIVE SERVER**.

### H. Run-scoped cleanup and preservation
**C-H1** (DESIGN DECISION) A **run manifest** is persisted **before the first write**, containing: `run_id`, TIR digest, registration digest, and the identity of every resource the run will create.
**C-H2** Ownership is provable and explicit: each run operates as a **run-scoped principal** (a dedicated test user created by the run), so every owned row is reachable through `user_id` → `documents.user_id`; cleanup is `id`-scoped **and** owner-scoped, never table-, schema- or database-wide.
**C-H3** Deletion is by explicit id list from the manifest, with the pre-existing preservation invariant (`documents/routes.py:826-859`) unchanged: a failed reprocess still leaves the previous version intact.
**C-H4** Idempotent and retry-safe: re-running cleanup against a partly-cleaned manifest is a no-op for absent ids and must never widen scope on error.
**C-H5** Partial setup / interrupted cleanup: the manifest is append-as-you-go for created resources; a crash leaves a manifest that is *smaller* than reality only if a write succeeded without being recorded — therefore the manifest is written **before** each creation, not after (`intent-then-act`), so a stale manifest over-approximates and can be safely re-scanned.
**C-H6** Stale manifests: two-phase cleanup — (1) delete manifest ids; (2) re-scan for zero survivors among run-owned resources; a non-empty re-scan keeps the run in `CLEANING` and records evidence.
**C-H7** Unprovable ownership ⇒ `QUARANTINED`: **abort and preserve**, never guess. Broad deletes are prohibited, and destructive-success tests remain skipped (`tests/fixtures/disposable_db.py:22-37`) until this control is implemented *and* independently verified.
**C-H8** Filesystem cleanup follows existing precedent: descriptor-relative deletion with symlink/reparse-point refusal (`scripts/cleanup_path.py:36-56`, `:74-250`), and archive-not-delete for orphans (`scripts/cleanup_orphan_uploads.py:74-157`).

### I. Concurrency and lifecycle state machine
**C-I1** §8 is normative. **C-I2** `run_id` is collision-resistant (UUIDv7: time-ordered + random) so ids are unique across processes without coordination.
**C-I3** Duplicate/replayed execution: the consumed `registration_id` and the run record make a second identical run refuse (`REPLAY_DETECTED`).
**C-I4** (DESIGN DECISION) Single-cluster mutual exclusion is enforceable with a PostgreSQL **advisory lock** keyed on a deterministic hash of `(TIR database, lifecycle resource, run scope)`, taken before the first write and released at cleanup. This is the only cross-process mechanism in the design that is *enforced* rather than *policy*.
**C-I5** **Honest limitation:** a host-local lock file or manifest-presence check is **not** cross-process or cross-host safety. Across hosts and across clusters, concurrency remains **policy plus detection**: overlap is detectable from the audit record and the advisory lock (per cluster), but is not prevented. Gate 27's stronger atomic-run-claim requirement is **not** satisfied by this design and remains unapproved.
**C-I6** Cleanup vs. a live run: an advisory lock is held for the whole run, so cleanup cannot acquire the lock of a running scope; a stale-run reclaim requires proving the previous holder is gone (backend pid absent) plus a grace period.

### J. Configuration and secrets
**C-J1** One authoritative target configuration, resolved by C-C2. Conflicting sources (e.g. `DOCUMIND_E2E_DATABASE_URL` disagreeing with `backend/.env`) ⇒ **refuse**, never "prefer one silently" — this is deliberate and differs from today's precedence chain (`e2e_config.py:135-150`).
**C-J2** Secrets are typed as `SecretStr` (`config.py:43,46`) and unmasked only at the point of use.
**C-J3** **No secret in argv, ever.** `create_test_user.py` gains an env/stdin delivery path and loses its default password (`scripts/create_test_user.py:64`); `e2e_config.py:306` stops passing `--password`. Disposable local test credentials are labelled as such and are distinct from application credentials; neither may be reused.
**C-J4** Subprocess environments are **allowlisted**, not inherited: pass only the variables the child needs (`integration_db.py:311`, `:402`; `e2e_config.py:215`, `:302` are the enforcement points).
**C-J5** Centralized, tested **redaction** applied to every child stdout/stderr and to every exception before logging or raising, replacing truncation at the five identified sites. Redaction strips `scheme://user:password@` userinfo, any configured secret value, and known env-var values.
**C-J6** Error text stays diagnostically useful: redaction replaces only secret material, keeping host/port/database/role (already credential-free by construction: `isolation.py:146-155`, `:173-181`) plus exit codes and the operation name.
**C-J7** Engine lifecycle: one construction point; explicit `dispose()`; rotation requires a new process or an explicit re-resolve (no silent reuse of a cached URL). Settings caching (`config.py:182-183`) is retained for non-secret values.
**C-J8** Conflicting/absent configuration must fail closed at startup — today `main.py:67` logs and re-raises; that behaviour is kept but the logged text must pass through C-J5 first.

### K. Verification, observability and recovery
**C-K1** Audit events (structured, append-only): `run_id`, `registration_id`, `key_id`, TIR **digest** (not the DSN), operation, state transitions, validation outcomes, cleanup deltas, exit status. No credentials, no full DSNs.
**C-K2** Evidence before/after: chunk count, `content_hash`, structure element count, embedding count, revision, `pgvector` version — the existing `verify_schema` shape (`integration_db.py:475-500`) is the model.
**C-K3** Incident diagnostics must never require printing a secret: a redaction-safe "identity card" (`host:port/database` + role + `cluster_id` digest) is the maximum disclosure.
**C-K4** Recovery from partial execution: rollback for in-transaction work; manifest-driven, idempotent cleanup for cross-transaction work; `QUARANTINED` for anything unprovable, with an operator record.
**C-K5** A run is only `CLEANED` when a re-scan proves zero run-owned survivors; otherwise the operator sees `CLEANING`/`QUARANTINED` explicitly.

## 10. Historical Review Mapping (RV-1–RV-8)

**The original definitions of RV-1 through RV-8 were not recovered** (§5.0). Nothing below is historical fact. The "Proposed concern" column is a **proposal derived from verified current-source evidence**, offered so a reviewer can confirm or replace it. **No label is claimed resolved.**

| Label | Original definition | Verified evidence available | Proposed concern (PROPOSAL, not history) | Proposed design control | Verification method | Owner confirmation |
|---|---|---|---|---|---|---|
| RV-1 | unavailable; requires owner confirmation | `main.py:44-53,76-84`; `migrations/env.py:44-57`; `setup_db.py:38-55` | Application startup / migration path targets a database it should not | C-F1–C-F5, C-C* | Source-order tests; DB-free refusal tests | required |
| RV-2 | unavailable | `isolation.py:378-441` (unconditional refusal today) | Authorization must not be forgeable or bypassable; a Python object is not a boundary | C-D2–C-D8, C-A1 | Forged/absent/replayed registration tests | required |
| RV-3 | unavailable | `integration_db.py:311` + `:323`; `isolation.py:146-155` | Credential and target identity can be assembled from different sources | C-C1–C-C5, C-E1–C-E5 | Conflicting-resolver refusal test; connection-hook tests | required |
| RV-4 | unavailable | no provisioning artifact exists in the repo | Least privilege and credential storage | C-G1–C-G6, C-D9, C-J2–C-J4 | Live-server privilege audit | required |
| RV-5 | unavailable | `cryptography 50.0.1` present (`requirements.txt:9`) | Registration authenticity and key trust | C-D1–C-D7 | Signature/canonicalization/rotation/revocation tests | required |
| RV-6 | unavailable | `documents/routes.py:826-859`; `documents/models.py:69-71`; `disposable_db.py:22-37` | Run-scoped cleanup must not touch unowned data | C-H1–C-H8 | Manifest tampering and unowned-resource tests | required |
| RV-7 | unavailable | `isolation.py:504-522`; `config.py:43,182-183`; `storage/database.py:41-43` | Identity, expiry, revocation; URL ≠ authenticated role; cached credentials | C-C1, C-E1–C-E5, C-D4–C-D7, C-J7 | Reconnect/rotation/revocation tests | required |
| RV-8 | unavailable | reflog/ledger evidence; Gate 27 unapproved | Concurrency guarantees | C-I2–C-I6 | Advisory-lock and overlap-detection tests | required |

**RV-1–RV-8 status: NOT RESOLVED.** An independent reviewer holding confirmed requirements must assess this design against each label.

## 11. Threat-to-control traceability matrix

| Threat | Control | Enforcement point | Failure mode | Verification | Residual risk |
|---|---|---|---|---|---|
| T1 app DB modified | C-C2, C-F1–C-F4, C-A1 | resolver; lifespan; Alembic CLI | refuse | source-order + refusal tests | misconfigured application role |
| T2 unintended target | C-C1, C-C3, C-D8, C-E1 | resolver; pre-flight; connect hook | refuse before I/O | conflicting-source + cluster-id tests | hostile server; DNS change |
| T3 secret leak | C-J3–C-J6, C-K1 | argv builders; redaction; logging | redact then report | leak tests (argv/env/log/exception) | OS-level inspection by same user |
| T4 forged registration | C-D3–C-D7 | pre-flight verification | refuse | signature/replay/rotation tests | private-key theft |
| T5 privilege creep | C-G1–C-G6 | role grants; validation | refuse | live privilege audit | cluster-wide `CREATEDB` if granted |
| T6 unowned deletion | C-H1–C-H7 | manifest; id+owner-scoped delete | `QUARANTINED`, preserve | manifest-tamper/unowned tests | cascade reachability (live check) |
| T7 TOCTOU | C-C5, C-E3 | every connection/batch | disconnect + raise | reconnect tests | server-side change mid-transaction |
| T8 concurrent runs | C-I4, C-I6 | advisory lock | block or detect | lock/overlap tests | **cross-host only detection** |
| T9 startup migration | C-F1, C-F2 | lifespan; Alembic env | refuse | startup refusal test | operator override misuse |

## 12. Security test matrix

Legend: **P** = what it proves; **N** = what it does **not** prove. None of these tests was executed in this task.

| # | Class | Test | P | N |
|---|---|---|---|---|
| 1 | Static/source (no DB) | Guard-before-effect ordering: authorization precedes any engine/`subprocess.run` in each entry point | ordering in source text | runtime dispatch |
| 2 | Static | No `--password` in any argv builder; no DSN string interpolation into SQL | absence in source | dynamic construction |
| 3 | Unit (no DB) | Canonicalization + Ed25519 verify for valid/invalid/expired/revoked/replayed registrations | crypto and state logic | server behaviour |
| 4 | Unit | Redaction strips userinfo/secret values from representative psql/alembic stderr | the redactor, on fixtures | real psql output shapes |
| 5 | Unit | Conflicting config sources (`DOCUMIND_E2E_DATABASE_URL` ≠ `.env`) ⇒ refuse | resolver policy | — |
| 6 | Unit | TIR construction rejects override params and incomplete identity | resolver policy | — |
| 7 | Mocked connection | `connect` hook rejects wrong database / role / port / cluster_id; passes on match | hook logic incl. **new connections** | real server metadata |
| 8 | Mocked | Pool reconnect / stale-connection path revalidates | revalidation trigger | real pool behaviour |
| 9 | Mocked | Startup migration refusal when `APPLICATION_MIGRATIONS` unset; Alembic settings failure is fatal | startup policy | — |
| 10 | Mocked | Cleanup refuses on unprovable ownership; no scope widening on error | manifest/ownership logic | real FK cascades |
| 11 | Mocked | Manifest tampering (extra ids) cannot widen deletion | ownership + id scoping | — |
| 12 | Integration (disposable, authorized) | Provision → migrate → seed → verify → cleanup → dispose on a registered target | end-to-end lifecycle | application DB safety |
| 13 | Integration | `pgvector` present; `vector(384)` round-trip; revision matches | real pgvector behaviour | model quality |
| 14 | Adversarial | Same-name database on a different host/port refused (no string aliasing) | identity strictness | — |
| 15 | Adversarial | Registered target reachable but role holds extra grants ⇒ refuse | privilege allowlist | complete privilege universe |
| 16 | Adversarial | Second run with a consumed registration ⇒ `REPLAY_DETECTED` | replay control | — |
| 17 | Adversarial | Advisory-lock contention ⇒ second run blocked/detected | single-cluster locking | cross-host |
| 18 | Destructive (**separately authorized**) | Cleanup deletes only run-owned rows; pre-existing documents/vectors survive | run-scoped cleanup | non-cascade relationships |
| 19 | Destructive (**separately authorized**) | Interrupted cleanup retried is idempotent and does not touch another run | idempotence | crash injection fidelity |
| 20 | Blocked until a human authorizes env + credentials | Live privilege audit, `cluster_id` verification, TLS state, revocation mid-run | real-server facts | — |

## 13. Assumptions and owner decisions

**Assumptions:** a dedicated disposable cluster or instance is acceptable; `pgvector` is installed there; TLS is available; the operator can hold an offline Ed25519 private key; the host is POSIX (see U4); PostgreSQL 13+ for `WITH (FORCE)` and advisory locks (project targets 16).

**Owner decisions (UNRESOLVED):**

| # | Decision | Why it cannot be decided here |
|---|---|---|
| U1 | Where the disposable target lives: dedicated cluster/instance vs. a shared cluster where the lifecycle role holds `CREATEDB` | Trades cluster-wide privilege against infrastructure cost |
| U2 | Whether mid-run credential rotation/revocation must be supported (changes engine/settings lifecycle) | Behaviour-affecting production-adjacent change |
| U3 | Where registrations and the revocation list are stored, and by whom | Secret-management policy the repo has no approved provider for |
| U4 | Supported host platform for ownership/permission checks | Host is `win32`; `os.geteuid` absent; no `chmod`/`S_IMODE` helper exists, so POSIX ownership assertions are unimplementable there |
| U5 | Whether destructive-success tests may be un-skipped once this design is implemented and independently verified | Currently `pytest.mark.skip` (`tests/fixtures/disposable_db.py:22-37`) |
| U6 | Confirmation of the historical RV-1–RV-8 definitions | Original text unrecoverable |

## 14. Open risks and limitations

1. **No live verification.** Every privilege, identity, cascade, pool and revocation claim is unverified against PostgreSQL.
2. **Concurrency is not fully enforced.** Single-cluster advisory locking is enforced; cross-host overlap is policy plus detection (C-I5). Gate 27 remains unresolved and unapproved.
3. **`CREATEDB` is cluster-scoped.** If granted to the lifecycle role, that role can create any database on the cluster (C-G2 residual).
4. **Signing proves authorization, not safety.** A valid registration can authorize an empty, safe-looking database that is not the intended one if the operator signs the wrong target.
5. **`cluster_id` readability** depends on role privileges; if unreadable, validation degrades to host/port/role with an explicit, documented weaker guarantee.
6. **Unit tests run on SQLite** (`tests/conftest.py:50`) with dialect-scoped shims, so a green suite is not evidence of PostgreSQL compliance.
7. **The manifest over-approximates by design** (intent-then-act); correctness depends on the re-scan, which is itself unverified until implemented.
8. **Redaction is a new control** replacing truncation; its completeness against real psql/Alembic output is unverified.

## 15. Implementation prerequisites and prohibited actions

**Prerequisites (owner/operator, outside this task):** U1–U4 decided; cluster and roles provisioned; `pgvector` installed; Ed25519 keypair generated **by the operator**; public key pinned; registration store created with correct ownership; a named owner per file (`backend/config.py` → BACKEND_AGENT per `agents/backend-agent.md:11`; `backend/tests/**` → TEST_AGENT; `backend/scripts/**` → DATABASE_AGENT; `backend/evaluation/**` → EVALUATION_AGENT; `backend/architecture/**` remains Coordinator-owned).

**Prohibited:** implementing any control; modifying application code, migrations, tests, settings or agent contracts; provisioning PostgreSQL/pgvector/roles/databases; connecting to any database; running migrations, destructive SQL or cleanup; reading or printing secrets; committing, pushing, staging, resetting, stashing or discarding; modifying or approving Gate 27; un-skipping destructive tests.

## 16. Independent-review handoff checklist

- [ ] Reviewer **did not author** this design and does not inherit the author's conversation.
- [ ] Reviewer holds this document (version `0.1.0-draft`) **and confirmed requirements**, including the historical RV-1–RV-8 definitions (U6).
- [ ] Reviewer has read-only repository access and verifies the cited line ranges in §17 (hashes in §4).
- [ ] Reviewer challenges each control's enforcement point, failure mode and residual risk; source-proven facts are separated from runtime assumptions.
- [ ] Reviewer answers the ten cross-examination questions independently (strongest argument against approval; most dangerous bypass; guarantees asserted but not enforced; what is closable without a database; what needs a live server; unintended-database protection; role/physical-connection binding; enforceable concurrency; what would change the verdict; smallest defensible next step).
- [ ] Reviewer does **not** accept the author's own analysis as verification, and RV-1–RV-8 are **not** marked resolved by self-assessment.

**Status: `INDEPENDENT REVIEW PENDING`. No reviewer has been engaged, and none is claimed.**

## 17. Evidence appendix (exact paths and line ranges)

| Path | Lines | Claim supported |
|---|---|---|
| `backend/main.py` | 44-53, 56-69 (log at 67), 76-84, 88-91 | startup runs migrations; error logging with `exc_info`; lifespan + uploads mkdir + engine dispose |
| `backend/migrations/env.py` | 44-57, 82-88 | settings override with bare `except: pass`; `poolclass=pool.NullPool`; `asyncio.run` |
| `backend/alembic.ini` | 3 | hard-coded loopback placeholder URL |
| `backend/scripts/setup_db.py` | 30-43, 44-55 | subprocess without `env=`; verbatim stdout/stderr printing |
| `backend/tests/fixtures/integration_db.py` | 302-337, 311, 313, 323, 332-336, 342, 350-368, 371-386, 402-403, 419-424, 438-444, 447-470, 475-500, 557-596 | the F-1 mixing; psql argv; guards; error text; schema verification; provisioning fixture |
| `backend/tests/fixtures/e2e_config.py` | 39-41, 135-150, 152-163, 166-178, 207-245, 216-221, 240, 302-303, 306, 318 | resolver precedence; `PGPASSWORD` transport; argv password; stderr sites |
| `backend/tests/fixtures/disposable_db.py` | 22-37 | destructive-success tests skipped pending authority |
| `backend/evaluation/isolation.py` | 82, 87, 92-101, 125-140, 146-155, 173-181, 249-314, 378-415, 418-441, 443-470, 470-522 | identity model; override refusal; fail-closed guards; credential-free rendering; unconditional refusals; URL-only engine comparison |
| `backend/config.py` | 36-40, 43, 46, 182-183 | plain-string settings; `.env`; `lru_cache` |
| `backend/storage/database.py` | 11, 41, 43, 49, 56-63 | URL transform; import-time engine; session factory; `get_db` |
| `backend/documents/routes.py` | 79-80, 419-426, 504-514, 740-859 | staleness rule; scoped reprocess; preservation invariant |
| `backend/documents/models.py` | 17, 24, 35-53, 63-95, 134+ | `Vector(384)`; document/chunk columns; cascade FKs; ownership path |
| `backend/tests/conftest.py` | 50, 62-69, 98-151, 190-217 (ASGITransport at 214) | SQLite in-memory engine; dialect shims; `get_db` override; `ASGITransport` without lifespan |
| `backend/scripts/cleanup_orphan_uploads.py` | 74-157, 455 | scan/apply split; archive-not-delete |
| `backend/scripts/cleanup_path.py` | 36-56, 74-250 | symlink/reparse refusal; descriptor-relative deletion; `S_ISREG` checks |
| `backend/requirements.txt` | 9 | `cryptography` availability for Ed25519 without a new dependency |
| `backend/architecture/STEP1_6M_READ_ONLY_POSTGRESQL_READINESS_REVIEW_2026-10-12.md` | 84 | pre-existing registered finding F-M2 (target divergence) |
| `backend/architecture/STEP1_6P_COMPLETE_CALLABLE_INVENTORY_AND_BYPASS_AUDIT_2026-10-12.md` | 88 | pre-existing registered finding P04 (`psql_value`) |

**End of `PGVECTOR-LIFECYCLE-AUTH-02` design, version `0.1.0-draft`.**
