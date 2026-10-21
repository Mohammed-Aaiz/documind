# STEP 1.5 — Evaluation Safety P0 Remediation Plan (2026-10-09)

## 1. Executive summary

**Scope.** Planning only. No code, test, configuration, migration, runner, or database was changed or run. No database was contacted.

**Decision.** Implementation may begin in the order in §9. **PostgreSQL verification remains NO-GO** until items P0-A to P0-E in §9 are complete and have source-level evidence.

**Principal findings (source-verified in this task):**

1. **Three structure runners have no isolation guard and can reach the application database.** `run_structure_rrf_calibration.py` (line 69), `run_structure_element_measurement.py` (line 88), and `run_structure_confirmation.py` (line 75) import `async_session` and `engine` from `storage.database` at module top. None of the three calls `assert_safe_evaluation_target`. Each `main()` runs `async_session()` and deletes a `User` matched by an exact email. These runners therefore act on whatever database the application settings resolve to.
2. **Correction to Step 1.4 §4.2.** Step 1.4 described "three runners" importing the engine before a guard runs. The accurate statement is narrower. The three module-top imports belong to the three unguarded structure runners, so no guard exists to run first. The six guarded runners do their `storage.database` and model imports after their guard, inside `main()` or inside helper functions that `main()` calls later.
3. **`run_table_evidence_measurement.py` falls back to the application URL.** Its resolver (`_resolve_database_url`, line 249) uses `DOCUMIND_PHASE4_DATABASE_URL`, else `get_settings().database_url`. Its only check is loopback host. A default local application database therefore passes. It then ingests a demo document and deletes a `User` by `EVAL_EMAIL` (line 439).
4. **Alembic silently falls back to a placeholder.** `migrations/env.py` wraps URL resolution in `except Exception: pass`. `main.py` runs `command.upgrade(cfg, "head")` at startup.
5. **Upload and report containment is absent.** `settings.upload_dir` defaults to `./uploads`, which is relative to the process CWD. Five runners call `save_upload` with no redirect. `RunOutput` refuses overwrites of named files but performs no containment check. Structure and table runners write fixed report paths.
6. **Cleanup ownership is mixed.** Five legacy runners use run-owned ORM cleanup (`cleanup_harness_rows`). The upload runner keeps an inline raw-SQL block that deletes by exact email. It runs in the `try` body, not in a `finally`. Its email uses a per-run `uuid4` suffix, so it is narrower than the register implies. The Phase 3F and 4B harness emails are deterministic (`harness_user_email`), so identity can collide across runs.
7. **Argument-supplied credentials.** `--database-url` appears in all guarded runners (F-7, open).

## 2. Source evidence reviewed

Evidence labels: `VERIFIED FROM SOURCE` = read or grepped in the current working tree during this task. `REPORTED BY PRIOR RUN` = taken from a register or step report and not re-derived here. `NOT VERIFIED` = not established by any evidence in this task.

| Evidence | Path | Label |
|---|---|---|
| Safety register | `backend/architecture/EVALUATION_SAFETY_MASTER_REGISTER.md` | `VERIFIED FROM SOURCE` (read; findings cross-checked below) |
| Step 1.4 assessment | `backend/architecture/STEP1_4_POSTGRESQL_VERIFICATION_READINESS_ASSESSMENT_2026-10-09.md` | `VERIFIED FROM SOURCE` (own output; one correction in §1 item 2) |
| Guard | `backend/evaluation/isolation.py` | `VERIFIED FROM SOURCE` (full read) |
| Global engine | `backend/storage/database.py` | `VERIFIED FROM SOURCE` (full read) |
| Settings | `backend/config.py` | `VERIFIED FROM SOURCE` (full read) |
| Alembic env | `backend/migrations/env.py` | `VERIFIED FROM SOURCE` (full read earlier in this session) |
| Startup migration | `backend/main.py` L36–60 | `VERIFIED FROM SOURCE` |
| Upload runner | `backend/evaluation/experiments/run_phase3d_upload_integration.py` L117–160, L184–260, L490–520 | `VERIFIED FROM SOURCE` |
| Structure runners | `run_structure_rrf_calibration.py`, `run_structure_confirmation.py`, `run_structure_element_measurement.py` (imports, `main`, deletes, writes) | `VERIFIED FROM SOURCE` (targeted greps and reads) |
| Table runner | `run_table_evidence_measurement.py` L243–268, L1046–1057 | `VERIFIED FROM SOURCE` |
| Guarded runners | `run_dual_path_ablation.py` L603–677; `run_phase3d_evaluation.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` (guard, env, engine line numbers) | `VERIFIED FROM SOURCE` (grep line numbers; read windows for two runners) |
| Harness cleanup and deterministic emails | `cleanup_harness_rows` and `harness_user_email` in the five legacy runners | `VERIFIED FROM SOURCE` (grep) |
| Archived phase tree | `backend/phases/**`, `backend/architecture/**` (excluding vendored `phase4f_gpu`) | `VERIFIED FROM SOURCE` (grep; four files spot-checked) |
| Scripts | `backend/scripts/*.py` (grep for engine, delete, unlink, alembic) | `VERIFIED FROM SOURCE` (grep); full read `NOT VERIFIED` for R19–R22 |
| Prior remediation reports (Steps 0–1.3) | `STEP0_*`, `STEP1_0`–`1_3` | `REPORTED BY PRIOR RUN` (not re-read in full here) |
| SQLite test results and counts | Step reports | `REPORTED BY PRIOR RUN`; not PostgreSQL evidence |
| `.env` | — | Only the presence of a `DATABASE_URL` key is known. Value **not read** (secret). |

## 3. Complete runner inventory

Classification uses the four required labels. Risk columns: DB = database reach, UP = upload root, RPT = report/artifact writes, CLN = cleanup, GRD = guard.

### 3.1 Evaluation experiment runners (`backend/evaluation/experiments/`)

| # | Script | Classification | DB | UP | RPT | CLN | GRD | Notes |
|---|---|---|---|---|---|---|---|---|
| E1 | `run_phase3d_upload_integration.py` | **IN SCOPE — BLOCKED** | Guard at L192 → env at L204 → models/app import after | Real app `UPLOAD_DIR` (F-4) | `RunOutput` for checks/manifest; no containment | ORM `cleanup_harness_rows` (L117) **plus** inline raw SQL by email (L490–520), not in `finally` | Yes (in `main`) | P0-E, P1-D |
| E2 | `run_phase3d_evaluation.py` | **IN SCOPE — REMEDIATION REQUIRED** | Guard L624 → env L637 | `save_upload` L142 (F-4) | Fixed report names L778–779 (F-9 extended) | ORM run-owned (L547–598, L784) | Yes | Report path P0-B |
| E3 | `run_phase3e_integration.py` | **IN SCOPE — BLOCKED** | Guard L158 → env L171 → `main` imports; models imported lazily inside `cleanup_harness_rows` (L112–113) | Uses app upload path via API | `RunOutput` | ORM run-owned (L81–133); line 483–485 inline `delete` scoped to stale id | Yes | Source-only, never on PG |
| E4 | `run_phase3e_validation.py` | **IN SCOPE — BLOCKED** | Guard L159 → env L172 → local engine L191 | Uses API (`upload_dir` not redirected) | Fixed `os.unlink` on sentinels | ORM run-owned (L81–133); step-5 inline delete (L554–559) source-only | Yes | Step 1.0 |
| E5 | `run_phase3f_evaluation.py` | **IN SCOPE — BLOCKED** | Guard L800 → env L813 → local engine L827 | `save_upload` L246/L270 (F-4) | Fixed report `phase3f_evaluation_report.json` (F-9) | ORM run-owned (L717–770); **deterministic** `harness_user_email` (L690) | Yes | P0-E identity |
| E6 | `run_phase4b_evaluation.py` | **IN SCOPE — BLOCKED** | Guard L780 → env L793 → local engine L807 | `save_upload` L221/L245 (F-4) | Fixed report (L965–966, F-9) | ORM run-owned (L697–750); **deterministic** `harness_user_email` (L670) | Yes | P0-E identity |
| E7 | `run_dual_path_ablation.py` | **IN SCOPE — REMEDIATION REQUIRED** | Guard L614 → env L623 → `storage.database` import L656 (after guard). Source-verified order is correct. | `save_upload` (F-4) | `RunOutput(args.out)` reserve (correct); no containment | Scoped user delete (L676, L793); `_delete_user_data` (L840) by owned doc ids | Yes | Cached-settings hazard §4.4 |
| E8 | `run_structure_rrf_calibration.py` | **IN SCOPE — BLOCKED (P0)** | **Module-top `storage.database` import L69; no guard; `async_session()` L980** | — | Fixed writes L1115–1148 (F-2) | Delete user by exact email L986 / L1057 | **None** | P0-A |
| E9 | `run_structure_element_measurement.py` | **IN SCOPE — BLOCKED (P0)** | **Module-top `storage.database` import L88; no guard; `async_session()` L1653** | `save_upload` (count 1; F-4) | Fixed writes L1799–1854 (F-2) | Delete by exact email L1659 / L1714 | **None** | P0-A; imports `run_dual_path_ablation` as a module (L90) |
| E10 | `run_structure_confirmation.py` | **IN SCOPE — BLOCKED (P0)** | **Module-top `storage.database` import L75; no guard; `async_session()` L728** | — | Fixed writes L906–930 (F-2) | Delete by exact email L734 / L773 | **None** | P0-A; imports E8 and E9 as modules |
| E11 | `run_table_evidence_measurement.py` | **IN SCOPE — BLOCKED (P0)** | Resolver falls back to **application URL** (L249); loopback-only check (L254) — **no central guard** | — (demo ingest, upload path not checked) | `_write_deterministic` fixed paths (F-2) | Delete user by `EVAL_EMAIL` L439 | **Loopback only** | P0-B |
| E12 | `run_phase4c_diagnostics.py` | **IN SCOPE — REMEDIATION REQUIRED** | None (no DB) | — | CWD-relative read L278 and write L584 (F-9) | — | n/a | Path anchoring only (P2.3) |
| E13 | `synthesize_structure_discriminating.py` | **IN SCOPE — EVIDENCE INCOMPLETE** | None | — | `write_text` L459–461 to default paths | — | n/a | Default output paths not read in this task |

Imported-only modules (not runners but on the import path of the structure runners): `run_dual_path_ablation.py` (used by E9, E10 via `base`), `chat.rag` (imported at module top by E8, E10), and `evaluation/runner.py` with the legacy `write_report(out_dir=None)` branch (F-2). Import-chain side effects of `chat.rag` at module top are `NOT VERIFIED`.

### 3.2 Scripts and archived trees

| # | Path | Classification | Risk | Justification |
|---|---|---|---|---|
| S1 | `backend/scripts/setup_db.py` | **IN SCOPE — REMEDIATION REQUIRED** | Runs `alembic upgrade head` in a subprocess with the application URL via `env.py` (L39–42) | Migration path under §6. Not an evaluation runner, but reaches the same environment. |
| S2 | `backend/scripts/cleanup_smoke.py` (R17) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Deletes application rows and upload directories by design (L123–136), against `async_session` | Operator script. Must never be invoked by a verification run. Add an explicit warning to §10 explicit exclusions. |
| S3 | `backend/scripts/cleanup_orphan_uploads.py` (R18) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Unlinks files under the application upload root (L213) | Operator script. Requires explicit operator authorisation (register F-4). |
| S4 | `backend/scripts/create_test_user.py` (R19) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Writes users to `async_session` (L33) | Writes to the application DB by design. Not in evaluation scope. |
| S5 | `backend/scripts/db_check.py` (R20) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Imports `engine` (L13); read-only check per register | Read-only, but it connects to the application engine. Exclude from verification runs. |
| S6 | `backend/scripts/start_server.py` (R22) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Server start; `rmtree` of `__pycache__` only (L62) | Not a database or artifact writer. |
| S7 | `backend/phases/phase4d/oracle_eval.py` | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Uses in-memory SQLite (L347) | Not PostgreSQL; archived research. |
| S8 | `backend/phases/phase4f/dataset/expand_and_audit.py` | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Read-only `iterdir` of `phases/phase4f/uploads` (L2036–2038) | Reads filenames only. |
| S9 | `backend/architecture/phase4f_6/e0_diagnostics/tools/*.py` (two spot-checked) | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Matches are numerical (`np.delete`) and version strings only | No DB or upload access found. |
| S10 | Remaining `backend/phases/**` `.py` (excluding `phase4f_gpu`) | **IN SCOPE — EVIDENCE INCOMPLETE** | Grep showed no `storage.database`, engine, `DELETE`, or `save_upload` matches in other files | Full read not performed. |
| S11 | `backend/phases/phase4f_gpu/**` | **OUT OF SCOPE — JUSTIFICATION REQUIRED** | Forbidden path per AGENTS.md §3 (no agent may write). Vendored environment. | Not inspected. |

### 3.3 Unresolved runners from the prior `UNKNOWN` set

- `run_dual_path_ablation.py`: now investigated; see E7.
- `run_table_evidence_measurement.py`: now investigated; see E11.
- `synthesize_structure_discriminating.py`: now partially investigated; see E13 (`EVIDENCE INCOMPLETE`).
- `scripts/db_check.py`, `scripts/create_test_user.py`, `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, `scripts/start_server.py` (R17–R22): now investigated at grep level; see S2–S6.

## 4. Import-order and guard analysis

### 4.1 Per-runner analysis

For each runner: entry point, import order, engine path, guard point, configuration loadability before the guard, the smallest correction, and regression tests.

**E1 `run_phase3d_upload_integration.py`**
- Entry: `main(argv)`. Module top imports only `evaluation.artifacts`, `evaluation.datasets.phase3d_corpus`, `evaluation.isolation`.
- Engine: `create_async_engine(evaluation_dsn)` at L240, after the guard. Models and `main.app` are imported inside `try` after the guard (L221–235).
- Guard: L192. `os.environ["DATABASE_URL"] = evaluation_dsn` at L204.
- Settings before guard: `application_database_url()` reads `.env` for `DATABASE_URL` and calls `get_settings()` **only** when that key is absent (`isolation.py` L123). With the key present, settings are not built before the guard.
- Smallest correction: none needed for ordering. Add a test asserting `get_settings` is not called before the guard in the `.env`-absent path, and make the `from main import app` path fail if `DATABASE_URL` differs from the validated DSN.

**E2, E3, E4, E5, E6, E7 (guarded runners)**
- Same pattern: `evaluation.isolation` only at module top; guard in `main` (E2 L624, E3 L158, E4 L159, E5 L800, E6 L780, E7 L614); env set immediately after; models and `storage.database` imported after. E3's `cleanup_harness_rows` imports models lazily (L112–113) and runs only after the guard.
- Order is correct in source. **Not verified** at runtime.

**E8, E9, E10 (unguarded structure runners)**
- **Module-level** `from storage.database import async_session, engine` (L69, L88, L75). This builds the global engine from `settings.database_url` at import time (`storage/database.py` L24–33). No guard is ever called.
- `main()` runs `async_session()` against that engine. The target is whatever the application resolves to.
- **Smallest correction (proposed, not implemented):** remove the module-top `storage.database` import from all three, add `assert_safe_evaluation_target` at the start of `main`, and build a local engine from the validated DSN, as the guarded runners do. Also withdraw the unscoped `out_dir=None` path (see §8).
- Note: E9 imports E7 (`run_dual_path_ablation`) as a module, and E10 imports E8 and E9 as modules. Importing E7 is safe, because it imports `storage.database` only inside `main`. The chain is still unsafe through E8 and E9 until their own module-top imports are removed (item 1 of §9).

**E11 `run_table_evidence_measurement.py`**
- Engine: `_resolve_database_url()` returns the application URL when `DOCUMIND_PHASE4_DATABASE_URL` is unset (L249). The guard is `_assert_local` (L254). `create_async_engine(url, …)` at L1054 follows it.
- A default local application database passes the loopback check. The order is safe; the **target is not validated**.
- Smallest correction: call `assert_safe_evaluation_target` and route the URL through `evaluation_database_url`, with no fallback to the application DSN.

### 4.2 Cross-cutting import hazards

- **H1 Module-level `storage.database` import.** Any module that imports `documents.models`, `chat.models`, `auth.models`, `user.models`, `reliability.models`, `graph.models` or `verification.models` triggers `storage.database` at import (verified: each model file imports `Base` from it). A runner must not import any model module before its guard.
- **H2 `documents/routes.py` calls `get_settings()` at import time** (`REPORTED BY PRIOR RUN`; not re-read here). `from main import app` therefore resolves settings at that point. In guarded runners this happens after the env is set.
- **H3 `lru_cache` on `get_settings`.** A `get_settings()` call before `os.environ["DATABASE_URL"]` is set would cache the application URL for the remainder of the process. Known call sites before the guard: `application_database_url()` fallback only (`isolation.py` L123). Not otherwise observed.
- **H4 `main.py` lifespan migration.** `_run_migrations` runs under the ASGI lifespan. `httpx.ASGITransport` does not run lifespan by default (`NOT VERIFIED` for each runner). If any runner starts uvicorn, startup would migrate whatever `DATABASE_URL` resolves to.
- **H5 Env-file versus env-var precedence.** `application_database_url()` reads `.env` directly, while `Settings` (pydantic-settings) gives environment variables precedence over `.env`. The guard compares against the `.env` value; the engine may use the environment value. This mismatch is the central reason the guard must validate the **effective** engine URL (§5.5).

### 4.3 Required regression tests (guard ordering)

| ID | Test | Method (no DB) |
|---|---|---|
| G-1 | No guarded runner imports `storage.database` or any model module before its guard call | AST scan of each runner's module-level imports; assert no name from `storage.database` or `*.models` above the guard line (static, not runtime) |
| G-2 | `assert_safe_evaluation_target` raises before `create_async_engine` is invoked, for each runner's `main` | Monkeypatch `sqlalchemy.ext.asyncio.create_async_engine` with a sentinel that fails the test; call `main` with unsafe args; assert sentinel never called |
| G-3 | Unsafe targets are refused before any connection: application identity, missing host, missing database, SQLite DSN, empty override | Unit tests on `isolation.py` (existing `test_evaluation_isolation.py` covers part; add the empty-override and SQLite cases if absent) |
| G-4 | Structure runners E8–E10 refuse the application DSN before any engine | After P0-A, same as G-2 with a monkeypatched `storage.database` absent |
| G-5 | `run_table_evidence_measurement` refuses the application DSN and refuses fallback | Unit test with `DOCUMIND_PHASE4_DATABASE_URL` unset and application URL local — assert refusal |
| G-6 | `DATABASE_URL` environment value after guard equals validated DSN | Monkeypatch env; call guarded `main` up to engine creation; assert `engine.url` identity equals validated identity |

## 5. Database target validation design

Design only. Nothing here is implemented.

### 5.1 Supply
- **Accepted sources, in order:** `DOCUMIND_INTEGRATION_DATABASE_URL` (environment) or a file-based secret. The `--database-url` argument is **accepted only with a refusal for any value containing a password**, to address F-7. Either form must be the only source; an explicit empty value is refused.
- The application DSN is read from `backend/.env` first, as today, and never from a runner-set environment variable.

### 5.2 Missing or ambiguous configuration
- Missing target: refuse with a credential-free message. **No fallback** to the application DSN. This removes the current `evaluation_database_url` fallback to `application_url` (`isolation.py` L185–186) for the runners that still use it.
- Multiple sources set and different: refuse.
- Application DSN cannot be read: refuse (already fail-closed in `assert_safe_evaluation_target`).

### 5.3 Rejection of application and production targets
- Compare the full identity `(host, port, database)` after normalising host case and default port. Reject equality.
- Reject a target whose host, port **and** database are all equal to the application identity, and warn if only the host or only the port matches.
- Do **not** treat names containing `test`, `temporary`, `evaluation` or `local` as evidence of isolation.

### 5.4 Identity attributes to validate
- Host (normalised, lower-case).
- Port (explicit, not defaulted silently).
- Database name (exact, not a prefix).
- Role name (`REQUIRES OPERATOR CONFIRMATION` for the allow-list; the role must be a non-superuser with no `CREATEDB`).
- Operator allow-list: a list of approved `(host, port, database)` tuples supplied outside the repository. A target not on the list is refused even when it differs from the application.

### 5.5 Effective-target check
- After the guard passes, and before any query, read the effective URL of **every** engine the run will use, and assert its identity equals the validated identity.
- For a global `storage.database` engine (should not exist after P0-A), assert identity against the validated identity and refuse on mismatch.
- Do not rely on `os.environ` alone (H5).

### 5.6 Credentials
- Never print the DSN. Use `display_dsn` (already credential-free) for logs and manifests.
- Never place a password in `argv`. Warn and refuse `--database-url` with an embedded password (F-7 remediation).
- Do not record the DSN in `RunOutput` manifests. Record `(host, port, database)` only.

### 5.7 Migrations constrained to the validated database
- Migrations for a verification run must target the validated disposable database only. Use a dedicated environment variable (proposed `DOCUMIND_MIGRATION_TARGET`) that is validated by the same guard and is **never** derived from the application settings.
- Disable application-startup migration (`main.py` lifespan) for evaluation runs by an explicit switch, or ensure no evaluation runner starts the lifespan (H4).

### 5.8 Operator confirmation
- `REQUIRES OPERATOR CONFIRMATION`: the disposable target's `(host, port, database)` and role; the allow-list; the isolation mechanism (dedicated instance or cluster); creation and destruction authority for the disposable database.

## 6. Alembic and startup migration analysis

### 6.1 How Alembic resolves its URL (`VERIFIED FROM SOURCE`)
1. `alembic.ini` provides a placeholder `sqlalchemy.url`.
2. `env.py` attempts `_DATABASE_URL = get_settings().database_url` through `_asyncpg_engine_args`, and overwrites the placeholder if that succeeds.
3. On any exception, it keeps the placeholder silently (`except Exception: pass`).

### 6.2 Silent placeholder fallback
- **Confirmed.** The placeholder names database `documind` on port 5432. If settings fail to load, Alembic silently targets a database with that identity. This is a fail-open path.

### 6.3 Startup migration reach
- `main.py` `_ensure_database_schema` runs `command.upgrade(cfg, "head")` under the lifespan (L51–53). It uses the same `env.py` and therefore the same resolution.
- `NOT VERIFIED`: whether a verification runner starts the lifespan.

### 6.4 Importing the application triggers initialisation
- Importing `storage.database` builds an async engine (no connection). Importing `config` does not connect. `documents/routes.py` calls `get_settings()` at import (`REPORTED BY PRIOR RUN`).
- Importing `main` does not run migrations (migrations run only in lifespan).

### 6.5 Binding the migration target to the validated database
- `env.py` must **refuse** when:
  - settings fail to load (replace the `pass` with a raise);
  - the URL is the placeholder;
  - `DOCUMIND_MIGRATION_TARGET` is set and its identity differs from the one validated for the run.
- Keep `sqlalchemy.url` unchanged in `alembic.ini` (not a secret; documented placeholder). Do not modify it in the implementation step unless required.

### 6.6 Tests that verify target selection without connecting to PostgreSQL
| ID | Test | Method |
|---|---|---|
| M-1 | `env.py` raises when settings fail to load | Monkeypatch `config.get_settings` to raise; call the URL-resolution function (refactor into a testable function) in isolation; assert raise, not placeholder |
| M-2 | `env.py` refuses the placeholder URL | Assert the resolved URL is not the `alembic.ini` placeholder |
| M-3 | Target identity mismatch refuses | Set `DOCUMIND_MIGRATION_TARGET` and a different application URL; assert refusal before engine creation (monkeypatch `async_engine_from_config` to fail) |
| M-4 | Startup migration cannot run for evaluation runs | Assert the switch disables `_run_migrations`; monkeypatch `command.upgrade` to fail |
| M-5 | Offline SQL generation (`alembic upgrade --sql`) reads only the validated URL | Permitted in a later verification step; **does not connect** (offline mode renders SQL). Requires operator approval because it is a migration command. |

## 7. Cleanup ownership design

### 7.1 Current state (`VERIFIED FROM SOURCE`)

| Runner | Identity source | Deterministic? | Cleanup mechanism | Scope | Runs on failure? |
|---|---|---|---|---|---|
| E1 upload | `uuid4` email suffix (L371, L459) | No (random per run) | ORM `cleanup_harness_rows` (L117) **and** inline raw SQL by email (L490–520) | Owned (ORM); raw SQL by exact email | Raw SQL inside `try` body only — **not on exception** |
| E2 3D eval | Arm-based email `harness_user_email` (L518) | Yes | ORM run-owned (L547–598) | Owned ids | `finally` at outer level (not re-read) |
| E3 3E integration | Identity source not re-read in this task | Not re-read | ORM run-owned (L81–133) | Owned ids | Not re-read |
| E4 3E validation | Fixed (not re-read) | Not re-read | ORM run-owned (L81–133); step-5 inline delete (L554–559) | Owned; inline delete scoped to doc ids | Not re-read |
| E5 3F eval | `harness_user_email(label)` (L690) | **Yes** | ORM run-owned (L717–770) | Owned ids | Not re-read |
| E6 4B eval | `harness_user_email(label)` (L670) | **Yes** | ORM run-owned (L697–750) | Owned ids | Not re-read |
| E7 dual-path | Fixed `EVAL_EMAIL` (L676) | Yes | ORM scoped user delete (L793) and `_delete_user_data` (L840) | Owned by user id | Not re-read |
| E8–E10 structure | Fixed `EVAL_EMAIL` | Yes | `delete(User).where(User.id == existing.id)` after exact-email lookup | Matches **any** user with that email, including application users | None |
| E11 table | Fixed `EVAL_EMAIL` | Yes | `delete(User).where(User.email == EVAL_EMAIL)` (L439) | Email-scoped | None |

### 7.2 Findings
- **C-1 (critical): E8–E11 delete application users by email.** If the application database contains a user with `EVAL_EMAIL` (`ablation_eval@test.local` or similar), the run deletes that user and their cascade. Email is not an owned identity.
- **C-2: deterministic identity collision (register §5.1).** E5 and E6 build the same email for the same label across runs. Two concurrent runs share identities and can delete each other's rows.
- **C-3: raw-SQL block in E1 is not on the exception path.** An exception before line 490 skips it. The ORM cleanup in `finally` (if present) remains.
- **C-4: no per-run nonce.** Only E1 includes a `uuid4` suffix. The others use fixed identities.

### 7.3 Proposed cleanup ownership model
1. **Run identity.** Generate `run_nonce = uuid4().hex` once per run. Derive every harness email as `<label>_<run_nonce>@test.local`. Persist the nonce in the run manifest.
2. **Owned set.** Record the created `User.id` values in memory at creation time. Cleanup deletes only ids in that set.
3. **Empty set.** If the owned set is empty, cleanup is a no-op. Never fall back to an email or prefix predicate.
4. **Deletion order (foreign-key-safe).** `ReliabilityLog` → `ChatMessage` → `ChatSession` → `DocumentChunk`(owned documents) → `Document` → `DocumentStructureEdge` / `DocumentStructureElement` / `DocumentGraphEdge` (owned documents, if present) → `User`. Verify against the models on PostgreSQL in the later step.
5. **Success and failure.** Cleanup runs in a `finally` that wraps the whole run after the owned set is established. Assertion failures record and continue. An exception re-raises after cleanup.
6. **Interruption.** `finally` does not run on SIGKILL. Recovery: the run writes a manifest with the nonce before creating users. A later run can list manifests and delete owned sets only if the manifest is present and the nonce matches. `REQUIRES OPERATOR CONFIRMATION` before adding any such recovery tool.
7. **Concurrent runs.** Unique nonce per run gives disjoint identities. Separate databases (§5) remove the remaining shared-database risk.
8. **Deletion outside owned records.** Enforce with a predicate that every `DELETE` includes `id IN (owned_ids)` or `user_id IN (owned_ids)`. Add a static test that rejects raw `DELETE`/`text(` in runners, except read-only diagnostics.

### 7.4 Is per-run uniqueness needed?
**Yes for E5 and E6, and for E8–E11.** E1 already has per-run randomness. Fixed identities cannot be proven exclusive to one run, so they must become run-unique. This changes harness email values, which changes the deterministic-id seed used by the structure runners (`uuid5` stand-in). `REQUIRES OPERATOR CONFIRMATION` whether that identity change is acceptable for the frozen benchmark and reproducibility claims (see §11).

### 7.5 Remaining Phase 3D raw-SQL block
- **Recommendation:** replace with ORM `cleanup_harness_rows`, scoped to owned ids, and move it into `finally`. It cannot safely remain outside verification scope, because E1 is the only runner with a PostgreSQL run that predates its cleanup change.

## 8. Upload and artifact containment design

### 8.1 Call sites and writers

| Runner | Upload writes | Report/artifact writes | Redirect present? |
|---|---|---|---|
| E1 | API via app `save_upload` (`storage/file_store.py`) | `RunOutput` (`checks.json`, manifest) | No |
| E2 | `save_upload` L142 | Fixed report names | No |
| E5 | `save_upload` L246/L270 | Fixed report name L1033–1034 | No |
| E6 | `save_upload` L221/L245 | Fixed report L965–966 | No |
| E7 | `save_upload` (in `ingest_corpus`) | `RunOutput(args.out)` | No |
| E9 | `save_upload` (count 1) | Fixed writes L1799–1854 | No |
| E8, E10 | None found | Fixed writes L1115–1148 / L906–930 | n/a |
| E11 | Demo ingest; path not inspected | `_write_deterministic` fixed paths | No |
| E12 | None | CWD-relative L278 / L584 | n/a |
| E13 | None | Default output paths (`write_text` L459–461) | n/a |

`settings.upload_dir` default is `./uploads` (`config.py`), resolved against the process CWD. `backend/uploads/` contained 1112 entries at the register baseline (`REPORTED BY PRIOR RUN`).

### 8.2 Required mechanism
1. **Dedicated temporary roots.** Each run creates `tempfile.mkdtemp(prefix="documind_eval_")` for uploads and another for artifacts. Both are created by the run and recorded in the manifest. Neither may be the application root.
2. **Explicit configuration before settings are read.** Set `UPLOAD_DIR` in the environment **before** `get_settings()` is first called, and call `get_settings.cache_clear()` after setting it. Assert `get_settings().upload_dir` equals the temp root (H3).
3. **Path resolution and containment.** For each configured directory, `Path(x).resolve()` must be absolute and `is_relative_to(temp_root)`. Symlinks are followed by `resolve()`. Refuse if the resolved path is inside `backend/uploads/` or any `backend/evaluation/reports/` tree.
4. **Refusal to overwrite.** Keep `RunOutput.reserve()` and extend it to refuse any target existing **outside** the temp root (refuse, do not write).
5. **Cleanup of run-owned temporary artifacts only.** Remove only files the run created (recorded in `RunOutput.written`), inside the temp root, in a `finally`. Never remove the application root. Never `rmtree` a path that was not created by the run.
6. **Failure and interruption.** Uploads from a killed run remain in the temp root and are removed by the operator (temp-root sweep limited to the `documind_eval_` prefix). `REQUIRES OPERATOR CONFIRMATION` for the sweep.
7. **Path traversal and symlink escape.** Reject `..` after normalisation; reject symlinks whose resolved target leaves the root; validate upload filenames through the existing `storage/file_store.py` rules (`VERIFIED FROM SOURCE`: not re-read in full here).

### 8.3 Proof without writing files
- Resolve each configured path (`Path.resolve()`), assert containment, and refuse before the first write. A unit test uses `tmp_path` and symlinks inside it, with no application path involved.

### 8.4 Fixed report paths (F-2) and CWD-relative paths (F-9)
- E8, E9, E10, E11, and `evaluation/runner.py` `write_report(out_dir=None)`: route through `RunOutput` with an explicit directory; `out_dir=None` raises.
- E2, E5, E6: replace fixed names with `RunOutput` output.
- E12: anchor reads and writes to `Path(__file__)`.

## 9. Dependency-ordered implementation plan

Priorities: P0 = blocks verification; P1 = required before verification; P2 = hygiene. Work items are ordered so target validation and import safety come first.

| Order | Priority | Work item | Finding | Expected files | Architectural decision | Minimal scope | Regression tests | Static checks | Completion evidence | Depends on | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | P0-A | **Remove module-top `storage.database` imports and add the central guard to the three structure runners** (E8, E9, E10) | C-1; F-2; G-4 | `run_structure_rrf_calibration.py`, `run_structure_element_measurement.py`, `run_structure_confirmation.py` | Local engine factory from the validated DSN (pattern of E5/E6) | Guard call first in `main`; local engine; no `async_session` from `storage.database` | G-1, G-2, G-4 | AST import check; `ruff`/`py_compile` | Tests pass; no `storage.database` import in these files | None | No change to metrics, corpus, weights, or report content |
| 2 | P0-B | **Route `run_table_evidence_measurement.py` through the central guard and remove the application fallback** (E11) | F-6; C-1 | `run_table_evidence_measurement.py` | Use `evaluation_database_url` with no application fallback | Replace `_resolve_database_url` fallback and loopback-only check with the guard; keep loopback as an extra check | G-5 | Static check that the module calls `assert_safe_evaluation_target` | G-5 passes; refusal path tested | P0-A pattern | No change to measurement logic |
| 3 | P0-C | **Fail-closed Alembic URL resolution and explicit migration target** | Section 6 §6.2 | `backend/migrations/env.py` | Refuse on settings failure; `DOCUMIND_MIGRATION_TARGET` validated by the guard | Replace `pass` with raise; refactor resolver into a testable function | M-1, M-2, M-3 | `alembic heads` (reads migration scripts; **NOT VERIFIED** that it never connects, so run only after confirming this) | M-1 to M-3 pass | Items 1–2 (guard reuse) | No migration files change; no DB reset |
| 4 | P0-D | **Disable startup migration for evaluation runs** | H4 / §6.3 | `backend/main.py` | Explicit switch (`DOCUMIND_SKIP_STARTUP_MIGRATION`) read before lifespan | Switch only; default unchanged | M-4 | Static check of lifespan | M-4 passes; default behaviour unchanged | Item 3 | Application migration behaviour for normal runs unchanged |
| 5 | P0-E | **Run-owned identities and ORM-only cleanup in `finally`** | C-2, C-3, C-4, §7 | `run_phase3d_upload_integration.py` (raw SQL → ORM; move to `finally`), `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` (nonce in `harness_user_email`), structure runners (nonce) | Per-run nonce; owned-id set; no email-predicate deletes | Replace raw SQL; add nonce; owned-id delete order | Owned-id unit tests; empty-set no-op; FK order; cleanup-after-exception (SQLite, labelled as such) | Static test that rejects raw `DELETE`/`text(` in runners | Unit tests pass; static test passes | Items 1–2; operator decision on identity change | Frozen benchmark values not changed; no PostgreSQL claim |
| 6 | P0-F | **Effective-target check** | §5.5, H3, H5 | `evaluation/isolation.py` (new helper), guarded runners | Check engine identity against validated identity before first query | Helper plus one call per runner | G-6 | Static check that every `create_async_engine` is preceded by the guard | G-6 passes | Items 1–2 | No new DB access in the guard |
| 7 | P1-A | **Upload root redirection and containment** | F-4, §8 | `storage/file_store.py` (read only unless needed), E1, E2, E5, E6, E7, E9 | `UPLOAD_DIR` set before settings are read; `cache_clear` | Redirect in each runner plus containment helper | Containment unit tests with `tmp_path` and symlinks; post-run count check (fixture) | Static check for `upload_dir` assignment before `get_settings` | Containment tests pass | Item 6 | No sweep of existing `backend/uploads/` |
| 8 | P1-B | **RunOutput containment and fixed-path removal** | F-2, F-9, §8.4 | `evaluation/artifacts.py`, `evaluation/runner.py`, E2, E5, E6, E8–E12 | Refuse outputs outside the temp root; `out_dir=None` raises | Route through `RunOutput`; anchor paths | Second run refused; `out_dir=None` raises | Static check for fixed `write_text` paths in runners | Refusal tests pass | Item 7 | No change to report content |
| 9 | P1-C | **Argv credential handling** | F-7 | Guarded runners' `parse_args` | Refuse embedded passwords; prefer env | Refuse or warn | Argv password refused (unit) | Static check | Unit tests pass | Item 2 | No change to env-var behaviour |
| 10 | P1-D | **Remove the application-DSN fallback in `evaluation_database_url`** | §5.2 | `evaluation/isolation.py` | Require explicit target | Remove fallback for runners using it | Unit test: no target → refusal | None | Tests pass | None | Application DSN still read for comparison |
| 11 | P2 | Tests for the uninstrumented runners (F-8); CWD anchoring (F-9); scripts warnings | F-8, F-9 | `tests/unit/evaluation/*`, `run_phase4c_diagnostics.py` | Spec-driven suite | Add cases | Spec-driven tests | Lint | Suite passes | Items 1–10 | No scripts run |
| 12 | Gate | **Pre-PostgreSQL verification review** | §11 | Architecture record only | Operator sign-off | — | — | — | Operator confirmation recorded | Items 1–11 | Not an implementation step |

Later (after the gate, not planned here): operator provisions an isolated PostgreSQL target; the upload runner's cleanup is verified once on that target; a clean-room run is recorded.

## 10. Regression and acceptance test matrix

| ID | Area | Test | Level | Runs without PostgreSQL? | Accepts when |
|---|---|---|---|---|---|
| G-1 | Import order | AST: no `storage.database`/model import before guard | Static | Yes | Zero violations across the guarded set and E8–E10 |
| G-2 | Guard before engine | Sentinel `create_async_engine` never called on refusal | Unit | Yes | Sentinel uncalled |
| G-3 | Guard rules | Application, missing host/database, SQLite, empty override refused | Unit | Yes | All refused with credential-free messages |
| G-4 | Structure runners | Refuse application DSN before any engine | Unit | Yes | Refused; no engine built |
| G-5 | Table runner | No fallback to application URL | Unit | Yes | Refusal |
| G-6 | Effective target | Engine identity equals validated identity | Unit | Yes (engine construction only, no connect) | Equality |
| M-1 | Alembic | Settings failure raises | Unit | Yes | Raise |
| M-2 | Alembic | Placeholder refused | Unit | Yes | Refusal |
| M-3 | Alembic | Target mismatch refused before engine | Unit | Yes | Refusal |
| M-4 | Startup | Migration switch disables upgrade | Unit | Yes | `command.upgrade` not called |
| M-5 | Offline SQL | Reads only validated URL | Operator-approved | Yes (offline) | Operator approval |
| C-1 | Cleanup | Owned-id delete only | Unit (SQLite, labelled) | Yes | No predicate outside owned set |
| C-2 | Cleanup | Nonce yields disjoint identities | Unit | Yes | Distinct emails |
| C-3 | Cleanup | Empty owned set is a no-op | Unit | Yes | No DELETE executed |
| C-4 | Cleanup | Cleanup in `finally` after exception | Unit (SQLite) | Yes, labelled as SQLite | Owned rows removed |
| C-5 | Cleanup | Static: no raw `DELETE`/`text(` in runners except read-only | Static | Yes | Zero violations |
| U-1 | Upload | Containment rejects escape and symlink | Unit (`tmp_path`) | Yes | Refusal |
| U-2 | Upload | Settings reflect redirected `UPLOAD_DIR` after `cache_clear` | Unit | Yes | Equality |
| U-3 | Artifact | `RunOutput` refuses an existing target outside root | Unit | Yes | Refusal |
| U-4 | Artifact | `out_dir=None` raises | Unit | Yes | Raise |
| X-1 | Post-run | Count of `backend/uploads/` unchanged | Operator fixture | No (filesystem only) | Unchanged |
| P-1 | PostgreSQL | Cleanup FK order and cascade | Later | **No** — requires isolated PG | Not claimed in this step |

**Not satisfiable without PostgreSQL:** FK cascade behaviour, transaction rollback, lock and concurrency behaviour, and whether a delete matches unrelated rows. These remain `NOT VERIFIED`.

## 11. Open architectural decisions

1. **Identity change.** Whether run-unique harness emails may replace fixed emails in E5, E6 and the structure runners, given the deterministic-id seed and frozen-benchmark reproducibility claims. `REQUIRES OPERATOR CONFIRMATION`.
2. **Structure runners' application users.** Whether the three structure runners may remain at all, or be archived. Their deletes reach application data. `REQUIRES OPERATOR CONFIRMATION`.
3. **Table runner default.** Whether `run_table_evidence_measurement.py` should refuse the application database even on loopback. Recommended: yes. `REQUIRES OPERATOR CONFIRMATION`.
4. **Migration switch name and default.** `DOCUMIND_MIGRATION_TARGET` and `DOCUMIND_SKIP_STARTUP_MIGRATION` are proposals.
5. **Operator allow-list.** Storage location and format (outside the repository).
6. **Temp-root sweep.** Whether a sweep of `documind_eval_*` directories is acceptable after an interrupted run.
7. **Interruption recovery.** Whether a manifest-driven recovery tool should exist. Recommended: no until the owned-id model is proven on PostgreSQL.
8. **Scripts S2–S6.** Whether to add a warning or a guard to operator scripts. Recommended: a documented warning only; no behaviour change in this plan.

## 12. Go/no-go recommendation

- **Implementation: GO, in the order given in §9, items 1–6 first.** Each item is bounded, and each has a test that runs without PostgreSQL.
- **PostgreSQL verification: NO-GO.** Verification requires items 1–8 and the operator decisions in §11. The upload runner's current cleanup must not be run against any database until item 5 is complete.
- **Do not run** any runner, migration, or destructive test during items 1–11 to validate them. Use unit tests and static checks only.

## 13. Preservation evidence and limitations

### 13.1 Preservation
- **Starting HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435` (recorded at the start of this task).
- **Baseline status:** recorded with `git status --porcelain=v1 --untracked-files=all` into `/tmp/step15_baseline_status.txt` (outside the repository), 1114 lines. Includes the Step 1.4 report as `??`.
- **Tracked files modified by this task:** none.
- **Existing files deleted or overwritten by this task:** none.
- **Intended addition:** this file only.
- **Final status and HEAD:** recorded in the final response of this task.
- No secret value, `.env` content, or DSN password was read or recorded. The only `.env` observation is the presence of a `DATABASE_URL` key (`REPORTED BY PRIOR RUN`).

### 13.2 Limitations
- No database was contacted. No runner, migration, integration test, or end-to-end test was executed. No cleanup function was run.
- Behaviour is **not verified** at runtime. Guard ordering, import order and cleanup scope are source-level findings only.
- Several earlier file reads were lost during context compaction. Claims depending on them are labelled `REPORTED BY PRIOR RUN` or `NOT VERIFIED`.
- `documents/routes.py` import-time `get_settings()` and `chat/rag.py` module-top imports are `REPORTED BY PRIOR RUN` or `NOT VERIFIED`.
- `main.py` lifespan triggering by any runner is `NOT VERIFIED`.
- Scripts R19–R22 and the archived `phases/` tree were checked by grep only; S10 is `EVIDENCE INCOMPLETE`.
- `synthesize_structure_discriminating.py` default output paths were not read (`EVIDENCE INCOMPLETE`).
- The two-file test count for the upload runner and the 70-case legacy isolation suite are `REPORTED BY PRIOR RUN`.
- Correction to Step 1.4 §4.2 is recorded in §1 item 2.
