# STEP 1.4 — PostgreSQL Verification Readiness Assessment (2026-10-09)

## 1. Executive summary

**Decision: NO-GO for PostgreSQL verification now.** Verification must not be run against any database until the blockers in §10 are resolved.

Main reasons, all from source inspection:

1. **Target isolation is not enforced before connection.** Several evaluation runners import the global `storage.database` engine at module import time, before any isolation guard runs. The application database URL is resolved from `.env`/settings with no runner-level assertion of the actual engine target.
2. **The integration fixture is destructive by design.** The integration fixture drops and recreates its target database unconditionally. Its only protection is an identity check on the URL. Destructive integration tests delete every row in their target.
3. **Migrations are coupled to the application.** The Alembic environment silently falls back to a placeholder URL when settings fail to load. `main.py` runs `alembic upgrade head` in its startup lifespan against whatever `DATABASE_URL` resolves to.
4. **Artifact and upload containment is not enforced.** `RunOutput` uses the caller's directory exactly as given. It refuses overwrites of existing files but has no containment check against a dedicated root. `UPLOAD_DIR` defaults to a relative path (`./uploads` in `.env`), so its location depends on the process working directory.
5. **The remaining Phase 3D raw-SQL cleanup block is still exact-email scoped rather than run-owned.** Its remediation is not complete.

PostgreSQL behaviour of the cleanup code is **NOT VERIFIED**. Every existing cleanup test is source inspection, mock, or SQLite. The only PostgreSQL run of the upload runner predates its current cleanup change.

## 2. Scope and non-execution declaration

- **Scope:** readiness of evaluation-runner cleanup remediations (Steps 0 through 1.3) for later isolated PostgreSQL verification.
- **Non-execution declaration:** this assessment did **not** connect to any database. It did **not** execute any runner, migration, integration test, end-to-end test, cleanup function, or destructive SQL. It did **not** read the value of any secret. The only `.env` observation was that a `DATABASE_URL` key is present. Its value was not read or recorded.
- **Modified files:** only the single new file at this path. No tracked file was edited.
- **Method:** read-only file reads and read-only `grep`/`sed`/`ls`/`git` commands.

## 3. Repository evidence reviewed

Evidence labels: `VERIFIED FROM SOURCE` = read in the current working tree during this task. `REPORTED BY PRIOR RUN` = taken from a prior remediation report and not re-checked against runtime behaviour.

| Area | Path(s) | Status |
|---|---|---|
| Safety register | `backend/architecture/EVALUATION_SAFETY_MASTER_REGISTER.md` | `REPORTED BY PRIOR RUN` (exists; not re-audited here) |
| Step 0 / 0.5 audit | `backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md`, `STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` | `REPORTED BY PRIOR RUN` (read in part) |
| Remediation reports | `STEP0_7_…`, `STEP0_8_…`, `STEP1_1_…` (Phase 3F) | `REPORTED BY PRIOR RUN` |
| Isolation guard | `backend/evaluation/isolation.py` | `VERIFIED FROM SOURCE` |
| Artifact writer | `backend/evaluation/artifacts.py` (`RunOutput`) | `VERIFIED FROM SOURCE` |
| DB engine | `backend/storage/database.py` | `VERIFIED FROM SOURCE` |
| Settings | `backend/config.py` | `VERIFIED FROM SOURCE` |
| Upload storage | `backend/storage/file_store.py` | `VERIFIED FROM SOURCE` |
| Migrations | `backend/migrations/env.py` | `VERIFIED FROM SOURCE` |
| Test fixtures | `backend/tests/fixtures/integration_db.py`, `e2e_config.py`, `backend/tests/conftest.py`, `backend/pytest.ini` | `VERIFIED FROM SOURCE` |
| Runners | `run_phase3d_upload_integration.py`, `run_phase4b_evaluation.py`, `run_phase3f_evaluation.py`, `run_phase3e_validation.py`, `run_phase3e_integration.py`, `run_phase3d_evaluation.py` (in `backend/evaluation/experiments/`) | `VERIFIED FROM SOURCE` (targeted reads only) |
| Unit tests | `test_phase3d_cleanup_scope.py`, `test_phase3d_evaluation_cleanup_scope.py`, `test_phase3e_integration_cleanup_scope.py`, `test_phase4b_evaluation_cleanup_scope.py`, `test_legacy_runner_isolation.py`, `test_evaluation_isolation.py` | `VERIFIED FROM SOURCE` (existence/targeted reads); behaviour `NOT VERIFIED` |
| Git baseline | HEAD and `git status` | `VERIFIED FROM SOURCE` (see §12) |

Earlier reads of several files were lost during context compaction. Findings that depend on them are marked `REPORTED BY PRIOR RUN` where they were not re-confirmed in this task.

## 4. Current database isolation architecture

### 4.1 How the target URL enters the system

- **Settings:** `backend/config.py` supplies `database_url` from environment/`.env`. `get_settings()` is cached.
- **Global engine:** `backend/storage/database.py` builds a module-level engine from the settings present **at import time** (`VERIFIED FROM SOURCE`). Any module that imports this engine or its session factory binds to whatever the settings resolved to at that moment.
- **Alembic:** `backend/migrations/env.py` (`VERIFIED FROM SOURCE`) reads `alembic.ini`'s `sqlalchemy.url` (a placeholder naming database `documind` on port 5432) and overwrites it with `get_settings().database_url` when settings load. If settings fail to load, the `except Exception: pass` path **silently keeps the placeholder**. A misconfigured environment can therefore migrate a default-named local database without any error.
- **Application startup:** `main.py`'s lifespan runs `alembic upgrade head` against the resolved `DATABASE_URL` (`REPORTED BY PRIOR RUN`, consistent with the Alembic `env.py` comment referencing `main.py`).
- **Import-time settings:** `backend/documents/routes.py` calls `get_settings()` at import time (`REPORTED BY PRIOR RUN`). Any runner that imports the app's routers before its guard therefore resolves settings before the guard.

### 4.2 Engine creation versus guard ordering

`REPORTED BY PRIOR RUN` (Step 0.5 audit, re-checked for the import chain in this task): **four runners import the global `storage.database` engine or session.** Three of them do so at module import time, before any guard function runs. The guard therefore cannot prevent an engine from being created against the application database; it can only prevent later use.

`NOT VERIFIED`: whether the guard is called before the first query in every code path.

### 4.3 Guard quality

`VERIFIED FROM SOURCE` (`backend/evaluation/isolation.py`): a central guard exists, and the evaluation runners reference it. Its checks are identity-based (URL/host/name pattern checks). `NOT VERIFIED` against a real PostgreSQL server:

- that it compares the **effective** engine URL, including `sslmode` translation and any URL-encoded components;
- that it rejects the application database by name **and** host **and** role;
- that it fails closed on an unparseable or missing URL.

**Important:** per the task constraints, a name containing `test`, `local`, `temporary`, or `evaluation` is **not** proof of isolation. The guard must not rely on name patterns alone.

### 4.4 Connection pools and cached settings

- The global engine and `get_settings()` cache mean a runner that modifies environment variables after import **will not** change the engine target. The reverse is also true: an engine created early keeps the early target. Both are silent failures.
- `NOT VERIFIED`: whether any runner re-creates the engine after setting its own URL.

## 5. Proposed isolated verification architecture

Four resources must be separate, and each must be validated before use.

| # | Resource | Owner | Required configuration | Validation (fail closed) |
|---|---|---|---|---|
| 1 | Normal application database | Application | Never referenced by any verification run. | Must **not** be the resolved target of the verification run (compare the effective URL, not a name pattern). |
| 2 | Disposable verification database | Verification run | Dedicated database on a dedicated cluster or dedicated instance name created for this run only. Role has no superuser rights, no `CREATEDB` for other databases, and no access to application roles. | Confirm host, port, database name, and role against an explicit allow-list supplied by the operator. Confirm the database is **empty** or was created by this run (marker table or recorded creation). Refuse if any application table is present. |
| 3 | Temporary upload root | Verification run | Fresh directory created by the run (for example via `tempfile.mkdtemp`) with a run-specific marker. The upload configuration (`UPLOAD_DIR`) is set **explicitly** to this path before any settings are read. | Resolve all upload paths and confirm each is a descendant of this root (after symlink resolution). Refuse if `UPLOAD_DIR` is relative or unset. |
| 4 | Temporary artifact/report root | Verification run | Fresh directory owned by the run. All `RunOutput` directories are passed explicitly. | Confirm each output directory is a descendant of this root. Confirm no target exists before writing (already enforced by `RunOutput.reserve`). |

Additional requirements:

- The verification harness must **assert the effective engine URL** after construction, against the allow-list, before running any migration or query.
- The harness must **refuse to start** if the application database URL is present under any alternate environment variable name. `NOT VERIFIED`: whether such a check exists.
- Migrations must run only against the disposable database, and the harness must not rely on `main.py` startup migrations.

## 6. Runner-by-runner readiness matrix

Status labels follow the requested vocabulary. Proposed verification status uses `READY`, `READY WITH CONDITIONS`, `BLOCKED`, or `UNKNOWN`.

| Runner | Phase | Isolation guard | Engine created before guard? | DB target path | Cleanup strategy | PostgreSQL behaviour needing verification | Upload isolation | Report isolation | Existing tests and limits | Proposed status |
|---|---|---|---|---|---|---|---|---|---|---|
| `run_phase3d_upload_integration.py` | 3D upload | Guard present | **Yes** for module-level imports (`REPORTED BY PRIOR RUN`) | Global engine via settings | Run-owned records **plus** remaining exact-email raw-SQL block | Raw SQL deletion; FK order; rollback on failure | Uses `save_upload`/`UPLOAD_DIR`; containment not enforced | `RunOutput`, no containment check | One PostgreSQL run predates current cleanup change; unit tests use SQLite/mocks | **BLOCKED** |
| `run_phase3d_evaluation.py` | 3D eval | Guard present | Not verified | Settings | Run-owned cleanup (Phase 3D scope test) | FK order; cascade; concurrency | Not verified | `RunOutput` | Source-inspection tests only | **BLOCKED** |
| `run_phase3e_integration.py` | 3E integration | Guard present | Not verified | Settings | Run-owned cleanup (3E scope test) | Cascade with `document_graph_edges`; ordering | Not verified | `RunOutput` | Source-inspection tests only | **BLOCKED** |
| `run_phase3e_validation.py` | 3E validation | Guard present | Not verified | Settings | Not verified | Not verified | Not verified | `RunOutput` | Not verified | **UNKNOWN** |
| `run_phase3f_evaluation.py` | 3F eval | Guard present | Not verified | Settings | Run-owned cleanup (Step 1.1 remediation) | Cleanup ordering; transaction boundaries | Not verified | `RunOutput` | Source-inspection tests only | **BLOCKED** |
| `run_phase4b_evaluation.py` | 4B eval | Guard present | Not verified | Settings | Run-owned cleanup (4B scope test) | Cleanup ordering; concurrency | Not verified | `RunOutput` | Source-inspection tests only | **BLOCKED** |
| `run_dual_path_ablation.py` | Ablation | Not verified | Not verified | Not verified | Not verified | Not verified | Not verified | `RunOutput` | Not verified | **UNKNOWN** |
| `run_table_evidence_measurement.py` | Measurement | Not verified | Not verified | Not verified | Not verified | Not verified | Not verified | `RunOutput` | Not verified | **UNKNOWN** |

Notes:

- **No runner is `READY`.** Passing unit tests do not establish PostgreSQL safety.
- The matrix covers only the runners inspected in this task. Remaining scripts (R19–R22 in the master register) and the archived `backend/phases/` tree were **not** reviewed in depth and are `UNKNOWN`.
- `NOT VERIFIED` appears where a cell could not be confirmed from the reads that survived context compaction. Those cells need re-inspection before any verification decision.

## 7. Cleanup safety analysis

### 7.1 Identity sourcing

- **Harness user IDs:** each cleanup must obtain IDs from records the same run created. `VERIFIED FROM SOURCE` for the unit-test expectations; `NOT VERIFIED` that every runner does this.
- **Exactness:** identities must be UUIDs generated by the run, not derived from email strings. The Phase 3D raw-SQL block still scopes by **exact email**. Exact-email matching is deterministic but can match a pre-existing or concurrent user with the same address. This is the most important open cleanup risk.
- **Concurrency:** two runs using the same test email, or the same database, can delete each other's records. Concurrency is `NOT VERIFIED` and cannot be established from source alone. Separate databases (§5) are the only reliable mitigation.

### 7.2 Scope and ordering

- Cleanup must delete only the current run's owned records.
- Deletion order must respect foreign keys. Cascade behaviour on PostgreSQL (`ON DELETE CASCADE`) must be verified against the real database. SQLite `PRAGMA foreign_keys=ON` in `conftest.py` is a compatibility measure and **does not prove PostgreSQL cascade behaviour**.
- `NOT VERIFIED`: whether a cleanup running after an unrelated user's records were created can delete them through cascade.

### 7.3 Lifecycle coverage

| Path | Required | Evidence |
|---|---|---|
| Success | Cleanup runs | `NOT VERIFIED` under PostgreSQL |
| Assertion failure | Cleanup runs | Source-only |
| Exception | Cleanup runs | Source-only |
| Timeout | Cleanup runs or run is killed with a cleanup-safe state | `NOT VERIFIED` |
| Interruption (Ctrl-C/SIGTERM) | Cleanup or a recoverable state | `NOT VERIFIED`; no runner was found to handle signals (`REPORTED BY PRIOR RUN`) |

### 7.4 Remaining Phase 3D raw-SQL block

The block is exact-email scoped and not run-owned. It **must be remediated** before PostgreSQL verification of the upload runner. It cannot safely remain outside verification scope, because the upload runner is the one with an existing PostgreSQL run that predates the current cleanup.

Cleanup-unit-test coverage is limited to source inspection and mocks. This analysis does not claim that the raw-SQL block is safe on PostgreSQL.

### 7.5 What requires PostgreSQL testing

Source inspection can establish:

- which identifiers are used;
- which deletion statements exist;
- the presence of a `finally` path or a guard call.

Only PostgreSQL testing can establish:

- foreign-key and cascade effects;
- transaction rollback behaviour;
- whether a delete matches unrelated rows;
- lock and concurrency behaviour.

## 8. Upload and artifact containment analysis

### 8.1 Upload root

- `backend/storage/file_store.py` (`VERIFIED FROM SOURCE`) writes uploads under the configured `UPLOAD_DIR`.
- `.env` sets `UPLOAD_DIR=./uploads` (`VERIFIED FROM SOURCE`). A relative path resolves against the **process working directory**. Running a runner from a different directory can write to a different location, including, if the cwd is the backend directory, the real `backend/uploads/` tree.
- `save_upload` call sites: `NOT VERIFIED` as a complete list. The Phase 3D upload runner calls it (`REPORTED BY PRIOR RUN`).
- **Containment:** no runner was found to enforce that upload paths are descendants of a dedicated temporary root (`NOT VERIFIED` as a complete statement).

### 8.2 Report and artifact output

- `RunOutput` (`VERIFIED FROM SOURCE`) uses the directory **exactly as given**. Relative paths are recorded as relative. It refuses overwrites via `reserve()`, which checks existence before writing.
- `RunOutput` has **no containment check**. It does not prevent a directory that points into `backend/uploads/` or an existing report tree. Overwrite protection covers only the named files, not directory-level misuse.
- Logs and provenance manifests: `NOT VERIFIED` whether each runner routes them through `RunOutput`.

### 8.3 Required configuration to prove containment

For each runner:

1. Require `UPLOAD_DIR` and every output directory to be **absolute** and inside the run's temporary root.
2. Resolve each path with symlinks followed (`Path.resolve()`) and confirm it is a descendant of the temporary root (`is_relative_to`).
3. Confirm no path is inside `backend/uploads/` or any existing `backend/evaluation/reports/` tree.
4. Refuse the run if any check fails.

This can be proven **without writing files**: resolve the configured paths and assert containment before the first write. The check must run before any settings or upload directory is consumed.

## 9. Failure and recovery verification matrix

None of these scenarios has been executed. Each row defines the expected safe outcome and the evidence needed.

| Scenario | Expected safe outcome | Evidence needed |
|---|---|---|
| Wrong database target | Run refuses before any query | Effective engine URL logged and compared to allow-list; zero queries recorded |
| Missing or ambiguous database URL | Run fails closed; no fallback to placeholder | Error raised; `alembic.ini` placeholder never used; `env.py` fallback path tested |
| Application database supplied accidentally | Run refuses | Guard rejects by host, port, name, and role |
| Unexpected host or database name | Run refuses | Allow-list mismatch error |
| Insufficient database privileges | Run fails before destructive step | Privilege probe output (no secret values) |
| Migration failure | Cleanup and rollback; no partial state left in a shared database | Migration log; disposable database dropped or marked unusable |
| Cleanup after assertion failure | Owned records removed; unrelated rows untouched | Row counts before/after for owned and unrelated identities |
| Cleanup after exception | Same as above | Same as above |
| Process interruption during run | Recoverable state; next run does not delete others' records | Marker table identifies the run; next run refuses non-empty database |
| Concurrent evaluation runs | Separate databases; no shared cleanup | Distinct database names; no shared identities |
| Upload directory escaping the isolated root | Run refuses | Containment check failure before writes |
| Report path pointing to a pre-existing application artifact | Run refuses (reserve collision or containment failure) | Collision error; artifact hash unchanged |
| Runner creating an engine before the guard | **Blocked by design**: guard must run before import | Import-order test (AST or subprocess with an empty environment) |
| Connections or cached settings resolving to an unexpected target | Run refuses | Effective URL check after `get_settings.cache_clear()` and engine rebuild |

## 10. Ranked blockers and prerequisites

Ranked by priority. P0 items block any PostgreSQL execution.

| Rank | Blocker / prerequisite | Type | Status |
|---|---|---|---|
| P0-1 | Move the isolation guard before any module-level import of `storage.database` in all runners; no engine created before the guard passes | Source change | `NOT VERIFIED` (4 runners affected) |
| P0-2 | Replace exact-email raw-SQL cleanup in the Phase 3D upload runner with run-owned, UUID-scoped deletion | Source change | `REQUIRES OPERATOR CONFIRMATION` for approach |
| P0-3 | Establish a disposable PostgreSQL target with an explicit allow-list (host, port, name, role), verified before use | Infrastructure | `REQUIRES OPERATOR CONFIRMATION` |
| P0-4 | Remove or guard the Alembic silent placeholder fallback so migrations fail closed | Source change | `VERIFIED FROM SOURCE` (fallback exists) |
| P0-5 | Enforce containment of `UPLOAD_DIR` and all output directories inside a run-owned temporary root | Source change | `NOT VERIFIED` (no containment check found) |
| P1-1 | Stop `main.py` startup from migrating during verification runs | Source change | `REPORTED BY PRIOR RUN` |
| P1-2 | Fix import-time `get_settings()` in `documents/routes.py` so settings are resolved after the guard | Source change | `REPORTED BY PRIOR RUN` |
| P1-3 | Add a fail-closed check that the destructive integration fixture cannot target a non-disposable database | Source change | `VERIFIED FROM SOURCE` (identity check only) |
| P1-4 | Confirm signal and `finally` cleanup behaviour | Source/runtime | `NOT VERIFIED` |
| P2-1 | Confirm no runner imports from `tests/` (production/test separation) | Source check | `NOT VERIFIED` |
| P2-2 | Complete the runner matrix for scripts not reviewed here | Source check | `NOT VERIFIED` |

## 11. Go/no-go recommendation

**NO-GO.** Do not run any PostgreSQL verification now.

Proceed only when:

1. P0-1 through P0-5 are resolved and each has source evidence.
2. The disposable database target is provisioned and its identity is confirmed by the operator. `REQUIRES OPERATOR CONFIRMATION`.
3. A written pre-run checklist is approved, covering allow-list values, role privileges, and the temporary roots.

Until then, the only permitted verification is read-only source inspection and SQLite-based unit tests. Those **do not** prove PostgreSQL cleanup safety.

## 12. Evidence limitations and items requiring human/operator confirmation

### 12.1 Limitations

- No PostgreSQL was contacted. No runner, migration, integration test, or end-to-end test was executed.
- No test results were produced in this task. Test counts and pass/fail claims come from prior reports and are labelled `REPORTED BY PRIOR RUN`.
- The Step 0.6 report does not exist in the repository. Its results come only from the Step 0 README.
- `run_phase3d_upload_integration.py` was not re-hashed in this task.
- Several files read earlier were dropped from working context. Findings that depended on them are marked accordingly.
- PostgreSQL cascade, transaction, lock, and concurrency behaviour is `NOT VERIFIED`.
- The safety register is treated as a source of prior findings, not as a re-audited authority.

### 12.2 Items requiring operator confirmation

- `REQUIRES OPERATOR CONFIRMATION`: the disposable database host, port, name, and role, and whether it is on a dedicated instance.
- `REQUIRES OPERATOR CONFIRMATION`: the approved cleanup approach for the Phase 3D raw-SQL block.
- `REQUIRES OPERATOR CONFIRMATION`: whether the application's `DATABASE_URL` value is intentionally the same host as any proposed verification target. This was **not** checked, to avoid reading secret values.
- `REQUIRES OPERATOR CONFIRMATION`: the temporary upload and report roots, and whether they may be created under the operating system temp directory.

## 13. Git preservation

- **Baseline HEAD:** `6baaa2a0773df66e5fb26814afbe67647fb43435`
- **Baseline status:** 1113 entries under `--untracked-files=all` (sorted-status digest `a55d84e189cdb6b8edf5a04f604ef96c`), recorded at `/tmp/step14_baseline_status.txt` outside the repository.
- **Intended change:** one new file, this report.
- **Tracked files modified by this task:** none.
- **Existing files deleted or overwritten by this task:** none.
- **Database, migration, runner, test, upload, benchmark, model-weight, or configuration changes:** none.
- **Final status and HEAD:** recorded in the final response of this task.
