# STEP 1.6I — Unified Destructive-Target Authorization

Date: 2026-10-11
Verdict: **PARTIALLY COMPLETE.** Database-destructive paths in the integration fixture and in the nine destructive evaluation runners are gated by one shared contract. Two destructive operations are classified UNRESOLVED (section 5) and one architectural decision is outstanding. PostgreSQL verification remains **NO-GO**.

## 1. Agents: what actually executed

The runtime exposed no specialist-agent dispatch. No specialist agent was invoked and no specialist output exists. Every review in this step was performed by the single running agent (Buffy). The responsibilities below are therefore **unfulfilled as separate roles**. Each was performed in the Coordinator's voice, and the reviewer roles were not independently run.

| Role | Status |
| --- | --- |
| COORDINATOR | Performed here (scope, classification, decisions). Not independently reviewed |
| SECURITY_AGENT | **Not executed as a separate agent.** Threat analysis in section 4 was done by the Coordinator |
| DATABASE_AGENT | **Not executed as a separate agent.** Contract in section 3 was written by the Coordinator |
| BACKEND_AGENT | **Not executed as a separate agent.** Runner edits were made by the Coordinator |
| TEST_AGENT | **Not executed as a separate agent.** Tests were written by the Coordinator |
| VERIFIER | **Not executed.** No independent review of the diff exists |

## 2. Baseline and its limits

- Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`
- Initial `git status --short`: **384** entries.
- Limitation: the full status listing was not saved to a file at the start of this step, so only the count is recorded. The comparison at the end is by count and by the paths this step touched. It is not a file-by-file comparison.
- Git cannot show untracked files as diffs, so the edited untracked files were verified by reading back and by tests.

## 3. Authorization contract

Five questions, each answered by a different check. None implies another.

| # | Question | Mechanism | Where |
| --- | --- | --- | --- |
| 1 | URL validity (scheme, parsing, no connection-override parameters, no malformed port) | `assert_safe_evaluation_target` | `evaluation/isolation.py` |
| 2 | Application isolation (database name differs, case-insensitively) | `assert_safe_evaluation_target` | `evaluation/isolation.py` |
| 3 | Target identity (host, port, database; literal engine check) | `database_identity`, `assert_engine_matches_target` | `evaluation/isolation.py` |
| 4 | **Destructive permission** | `assert_disposal_authorized` on `DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE` | `evaluation/isolation.py` |
| 5 | **Proof of disposability** | **Not established by any check in this repository.** | — |

Rules, enforced by `assert_disposal_authorized`:
- Unset or blank authorization refuses.
- The variable must equal the target's database name exactly (surrounding whitespace is stripped).
- The application's database name is never authorized, even if named.
- The check runs *after* the validity guard and never replaces it.
- It is re-evaluated at every call. The decision is not cached.

What the authorization does **not** establish: that the operator is right, or that the database holds no other data. The operator declares a name. The gate guarantees only that the destroyed name is the one named.

The URL variable, a name containing `integration` or `test`, a valid PostgreSQL URL, and a target that differs from the application all remain insufficient on their own. The tests in section 7 check this directly.

### Ownership of the contract

The contract lives in `evaluation/isolation.py` (EVALUATION_AGENT). The fixture (`tests/fixtures/integration_db.py`, TEST_AGENT) now delegates to it. There is one definition of the variable name and one implementation of the rule.

### Intentional divergence (open decision)

The fixture also requires the target to be on the **application's host and port** (same server). Its drop and create run through the application server's maintenance connection. The central contract does not impose this, so evaluation runners accept a different host or port. This is the largest remaining difference between the two layers. See section 8.

## 4. Destructive-path inventory and classification

Classifications: **AUTHORIZED** (gated by the contract before the first side effect), **SAFELY BLOCKED** (refuses by default with no path to proceed), **UNRESOLVED** (no defensible boundary established; not gated).

| Path | Operation | Target source | Gate before first side effect | Redirect after validation? | Classification |
| --- | --- | --- | --- | --- | --- |
| `tests/fixtures/integration_db.py` `provisioned_integration_database()` → `_drop_database` / `_create_database` | DROP and CREATE DATABASE | `DOCUMIND_INTEGRATION_DATABASE_URL` or derived `documind_integration` | Yes: `assert_authorized_destructive_target()` (URL + contract + same-server) before any I/O; primitives re-check the name before SQL | Env re-read at each primitive; a changed authorization or name is refused | **AUTHORIZED** (operator-declared name; disposability unproven) |
| `test_real_e2e_validation.py` `isolated_database` fixture (pytest) | calls the provisioning path above | same | same | same | **AUTHORIZED** |
| `test_real_e2e_validation.py` `__main__` `--use-provisioned-database` | row deletes via `run_full_validation` | `DOCUMIND_INTEGRATION_DATABASE_URL` | `assert_authorized_destructive_target()` (added in 1.6H) | as above | **AUTHORIZED** |
| `run_phase3d_evaluation.py` | row deletes (owned users) | `--database-url` → env → app DSN | central validity guard, then `assert_disposal_authorized` (this step), before any DB use | env re-read per call | **AUTHORIZED** |
| `run_phase3d_upload_integration.py` | row deletes, including raw `text("DELETE …")` | same | same | same | **AUTHORIZED** (raw SQL remains; see risk 6) |
| `run_phase3e_integration.py` | row deletes (owned) | same | same | same | **AUTHORIZED** |
| `run_phase3e_validation.py` | row deletes (owned); `os.unlink` of its own temp files | same | same (DB part); unlink is filesystem, see section 5 | same | **AUTHORIZED** (DB); filesystem temp unlink **UNRESOLVED-low** |
| `run_phase3f_evaluation.py` | row deletes (owned) | same | same | same | **AUTHORIZED** |
| `run_phase4b_evaluation.py` | row deletes (owned) | same | same | same | **AUTHORIZED** |
| `run_dual_path_ablation.py` | row deletes (eval user's rows) | same | same | same | **AUTHORIZED** |
| `run_table_evidence_measurement.py` | ingest then row deletes | same | `_authorize_disposal(url, …)` in `amain`, after `_resolve_database_url()` and before model import | same | **AUTHORIZED** |
| `run_structure_element_measurement.py` | row deletes (eval users) | same | `assert_disposal_authorized` in `guard_evaluation_target` (shared guard) | same | **AUTHORIZED** |
| `run_structure_rrf_calibration.py` | row deletes (eval users) | shared guard from element runner | via `guard_evaluation_target` | same | **AUTHORIZED** (via shared guard) |
| `run_structure_confirmation.py` | row deletes (eval users) | shared guard from element runner | via `guard_evaluation_target` | same | **AUTHORIZED** (via shared guard) |
| `scripts/cleanup_smoke.py` | deletes a named user's documents, rows, **and files**, and removes the user directory with `shutil.rmtree`, against the **application** DATABASE_URL (no guard) | application DSN, by design | None beyond an interactive confirmation unless `--yes` | n/a | **UNRESOLVED** (operator script that is destructive to application data by design; no disposal boundary. Section 5) |
| `scripts/cleanup_orphan_uploads.py` | **filesystem** deletes of orphaned upload files (`path.unlink()`) under the uploads directory; reads the DB for references | application DSN (read only) | `--delete` flag (default dry run); `cleanup_path` containment and symlink checks | n/a | **UNRESOLVED** for the filesystem (see section 5). The DB use is read-only |
| `scripts/cleanup_path.py` | helper: containment and symlink checks only | — | — | — | Not destructive (helper) |
| `storage/file_store.py` `delete_upload` | application file deletion | application runtime | application runtime policy (not an evaluation path) | — | **Out of scope** for evaluation authorization; application behaviour, unchanged |

Filesystem cleanup is reviewed separately. The database gate does not make `cleanup_orphan_uploads.py` or `cleanup_smoke.py`'s file deletion safe. Those files are UNRESOLVED.

## 5. Unresolved paths and why they are not gated

1. **`scripts/cleanup_smoke.py` (application data, by design).** It is a deliberate operator tool. It deletes a user's documents, rows, and files from the *application* database. A disposal gate that refuses the application database would make the tool unusable, and the tool was never intended for disposable databases. Fail-closed options (remove it, or refuse unless an explicit operator flag is set) are an architectural decision for the Coordinator and Security. This step did not make that decision silently. **UNRESOLVED.**
2. **`scripts/cleanup_orphan_uploads.py` (filesystem).** Its deletes are gated only by the `--delete` flag, a dry-run default, and path containment. No disposal boundary exists for files, and the contract is about databases. **UNRESOLVED.** The database access in it is read-only.
3. **`run_phase3e_validation.py` temp-file unlinks.** These delete files the harness itself created in a temp directory. Low risk, but the filesystem boundary has not been audited against a disposal policy. **UNRESOLVED-low.**
4. **`storage/file_store.py` and the application's own upload deletion** are application runtime behaviour. They are not evaluation paths and were not changed.

## 6. Files changed in this step

| File | Owner | Change |
| --- | --- | --- |
| `backend/evaluation/isolation.py` | EVALUATION_AGENT | Added `DISPOSAL_AUTHORIZATION_ENV`, `authorized_disposal_name()`, `assert_disposal_authorized()` (section 3). Existing functions unchanged |
| `backend/tests/fixtures/integration_db.py` | TEST_AGENT | `assert_disposal_authorized` and `_authorized_disposal_name` now delegate to the central contract. Fixture names kept so existing tests apply. Same-server rule retained |
| `backend/evaluation/experiments/run_phase3d_evaluation.py` | EVALUATION_AGENT | Import and `assert_disposal_authorized` call after the validity guard |
| `backend/evaluation/experiments/run_phase3d_upload_integration.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_phase3e_integration.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_phase3e_validation.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_phase3f_evaluation.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_phase4b_evaluation.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_dual_path_ablation.py` | EVALUATION_AGENT | Same |
| `backend/evaluation/experiments/run_table_evidence_measurement.py` | EVALUATION_AGENT | Local import and `_authorize_disposal` call in `amain` after `_resolve_database_url()`, before `_import_all_models()` (so the existing `_resolve_database_url` tests keep their meaning) |
| `backend/evaluation/experiments/run_structure_element_measurement.py` | EVALUATION_AGENT | Import and `assert_disposal_authorized` in the shared `guard_evaluation_target`. Covers rrf-calibration and confirmation |
| `backend/tests/unit/evaluation/test_structure_runner_guard_order.py` | TEST_AGENT | Harness now authorizes the approved target (acceptance-path tests model an authorized operator). New test: unauthorized target refuses before settings or storage |
| `backend/tests/unit/evaluation/test_disposal_authorization_contract.py` | TEST_AGENT | **New.** Contract, configuration-change, fixture/central agreement, and gate-coverage tests |
| `backend/tests/unit/evaluation/test_disposable_database_authorization.py` | TEST_AGENT | Unchanged in this step (passed after the fixture was re-pointed to the central contract) |
| `backend/tests/unit/evaluation/test_phase3_runner_target_order.py` | TEST_AGENT | Unchanged in this step |
| `backend/tests/integration/rag/test_real_e2e_validation.py` | TEST_AGENT | Unchanged in this step |
| `backend/architecture/STEP1_6I_…md` | Coordinator | This report |

No script under `backend/scripts/` was changed. Those are classified UNRESOLVED (section 5).

## 7. Focused tests

All database-free. Patched I/O: `psql_value`, `postgres_available`, `subprocess.run`. No provisioning, no drop or create, no migration, no cleanup, no runner `main()`. The application DSN is always passed explicitly; no `.env` file is read.

### Commands and results

Initial run of the five existing focused files, after the runner edits:

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_structure_runner_guard_order.py -p no:cacheprovider
→ 15 failed, 149 passed   (exit 1)
```

Cause: the structure-runner guard tests run the guard without any disposal authorization, so they now hit the new refusal earlier than they were written to expect. This is correct behaviour under the contract. The fix was in the test harness, which now models an operator who authorized the approved target. A separate test was added that proves an unauthorized target refuses before settings or storage. The refusal-expectation tests were **not** weakened.

Final run of the new and updated focused files:

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_structure_runner_guard_order.py -p no:cacheprovider
→ 214 passed in 2.20s   (exit 0)
```

Source-only cleanup and report scans, run after the runner edits:

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_phase3d_cleanup_scope.py tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py tests/unit/evaluation/test_runner_report_output.py -p no:cacheprovider
→ 123 passed, 1 warning in 22.87s   (exit 0)
```

The warning is the pre-existing `pytest-asyncio` deprecation notice about the fixture loop scope. It is unrelated to this change.

Before running the cleanup-scope files, a regex scan found only source-text matches (`create_async_engine(evaluation_dsn)` inside string-literal assertions). The one exception is `test_legacy_runner_isolation.py:162`, which does `import main`. That file was **not run**.

### Compile

```
cd backend && ./venv/Scripts/python.exe -m py_compile evaluation/isolation.py evaluation/experiments/run_phase3d_evaluation.py evaluation/experiments/run_phase3e_integration.py evaluation/experiments/run_phase3e_validation.py evaluation/experiments/run_phase3f_evaluation.py evaluation/experiments/run_phase4b_evaluation.py evaluation/experiments/run_dual_path_ablation.py evaluation/experiments/run_phase3d_upload_integration.py evaluation/experiments/run_table_evidence_measurement.py evaluation/experiments/run_structure_element_measurement.py tests/fixtures/integration_db.py
→ COMPILE_EXIT=0
```

Compile covered the changed production files and the fixture. The test files were covered by the pytest collection above.

### What the tests cover

- Contract: unset, blank, URL-only, name-convention, exact, whitespace, application-name, host-alias application name, no-name target, and "authorization cannot rescue a failed URL check".
- Configuration change between check and use: authorization removed, changed to another name, or the URL changed to another target after authorization. Each is refused at the next check.
- Fixture and central decide identically over six authorization states.
- Gate coverage: every experiment runner containing a destructive statement is accounted for. Nine are gated directly and placed after their validity guard. Two reach the database through the shared guard, which is checked.
- Fixture provisioning: the gate precedes `postgres_available()`.

## 8. Checks intentionally not run

- **NOT RUN:** any evaluation runner's `main()`.
- **NOT RUN:** the integration fixture's provisioning path, `_drop_database`, `_create_database`, or the `isolated_database` fixture.
- **NOT RUN:** `test_real_e2e_validation.py` (pytest or `__main__`).
- **NOT RUN:** `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, `scripts/setup_db.py`, migrations.
- **NOT RUN:** `test_legacy_runner_isolation.py` and `test_evaluation_isolation.py`. Neither was established as database-free (`import main` at line 162; an earlier run timed out).
- **NOT RUN:** integration, E2E, or any PostgreSQL test.
- **NOT RUN:** linters and type checkers.
- **NOT PERFORMED:** any database connection, including `postgres_available()`.
- **NOT PERFORMED:** reading any `.env` value. The application DSN was passed explicitly in every test.

## 9. Remaining risks and required architectural decisions

1. **Operator declaration is not disposability proof.** `DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE` ensures the destroyed name is the one the operator named. It cannot prove that the database holds no other data, or that the server is not production.
2. **Same-server divergence (decision required).** The fixture requires the same host and port as the application. The contract used by the runners does not. Decide whether to adopt the same-server rule in the central contract, which would change runner behaviour, or to accept the divergence.
3. **Two application-DSN resolvers.** `e2e_config.database_url()` and `isolation.application_database_url()` may read `.env` and the environment with different precedence. The contract takes the application DSN as an explicit argument where it matters, but the two resolvers are not unified.
4. **`scripts/cleanup_smoke.py` (decision required).** Destructive to application data by design, with no disposal boundary. Remove, restrict, or leave with documented risk.
5. **`scripts/cleanup_orphan_uploads.py` (decision required).** Filesystem deletion has no disposal boundary. The contract covers databases only.
6. **Raw SQL in `run_phase3d_upload_integration.py`.** The file still contains raw `text("DELETE …")` statements (its own docstring records them as the remaining raw destructive SQL). The authorization gate guards the whole file, but the raw statements were not reviewed for scope in this step.
7. **Time-of-check versus time-of-use.** The contract re-reads the environment at each check, and the fixture re-checks at each primitive. A process that changes its environment between the last check and a destructive statement inside a runner body is not protected, because runners perform their deletes after the gate without a re-check. This is a residual TOCTOU gap.
8. **Authorization in a shared process.** The gate is an environment check, so any code in the same process can set the variable. It is not a security boundary against a hostile process.
9. **Source-level evidence only.** The gate-coverage tests prove placement in source. They do not prove runtime behaviour. Runtime behaviour requires an approved disposable PostgreSQL target, which does not exist.

## 10. Protected-artifact preservation

No file under `backend/models/documind-qa/**`, `backend/venv/**` (executed only), `backend/phases/phase4f_gpu/**`, `backend/uploads/**`, `.env`, `backend/.env`, `dist/`, or `node_modules/` was written. No frozen benchmark, expected output, model weight, or evaluation algorithm was touched. `backend/evaluation/isolation.py` was changed only by addition; no existing function was altered.

## 11. Final Git state

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged).
- `git status --short`: **384** entries, the same count as at the start of this step.
- Nothing was staged, committed, reset, stashed, cleaned, or reverted.
- Count-only comparison (section 2). Pre-existing tracked deletions and modifications, and untracked paths including `backend/architecture/`, `backend/evaluation/`, `backend/tests/`, remain present.

## 12. Destructive-path final classification (summary)

- **AUTHORIZED:** integration fixture (provisioning, drop, create, pytest fixture, `__main__`); nine evaluation runners (3D, 3D-upload, 3E, 3E-validation, 3F, 4B, dual-path, table-evidence, structure-element; rrf-calibration and confirmation via the shared guard).
- **UNRESOLVED:** `scripts/cleanup_smoke.py` (application data, by design); `scripts/cleanup_orphan_uploads.py` (filesystem); `run_phase3e_validation.py` temp-file unlinks (low).
- **Out of scope:** `storage/file_store.py` (application runtime).

## 13. Handoff

- Coordinator: decide risks 2, 4, and 5, and confirm whether the contract should adopt the same-server rule.
- BACKEND_AGENT (when available): review risk 6 (raw SQL) and the scripts.
- VERIFIER (when available): independently review the diff in section 6, and run the focused files in section 7.
- PostgreSQL verification remains **NO-GO** until the broader readiness blockers are resolved and an explicitly approved, isolated disposable target exists.

## 14. Decisions recorded after the initial report (no code changed)

These three decisions were requested after section 13 was written. No source file was changed to implement them. Each was decided from the code as it stands, and each is recorded here for the Coordinator to confirm.

### 14.1 Should evaluation runners adopt the fixture's same-server rule?

**Decision: no.** The runners keep the contract in section 3 and do not adopt the host-and-port rule.

Reasons:
- The fixture's rule exists because its drop and create run through the *application server's* maintenance connection. A target on another server would be acted on in the wrong place. The runners have no such connection: each builds its engine from the target DSN itself, so the server they act on is the one they name.
- Requiring the application's host and port would forbid a legitimate isolated disposable database on another port or host. The name-level guard and the explicit disposal authorization already prevent the application database from being selected.
- The `run_table_evidence_measurement.py` runner already applies a stricter loopback-only check (`_assert_local`). That is the appropriate place for a locality rule, and it is a per-runner decision.

Remaining exposure: a runner pointed at a remote host with a disposable-looking name is accepted by the contract. Adopting a central loopback rule across all runners would close that, but it changes behaviour for every runner. That is a separate decision and is recorded as open.

### 14.2 Raw DELETE statements in `run_phase3d_upload_integration.py` (lines 519-534)

**Decision: scope accepted for now; convert in a follow-up.**

The four `text("DELETE …")` statements delete rows for the two extra users created by the same run. Each is filtered by `WHERE email = :e`. Both emails carry a per-run random suffix (`phase3d_meta_<uuid8>@test.local` and `phase3d_other_<uuid8>@test.local`), so the filter cannot match a row the run did not create. The child deletes reach their owners through subqueries on `users`, in foreign-key-safe order. The scope is therefore correct.

Two caveats:
- These statements are raw SQL, which the Step 1.6 remediation plan (P1.1) asks to convert to `cleanup_harness_rows`. The conversion is not done here.
- The cleanup is not in a `try/finally`. If the run raises before line 519, the two extra users and their rows are left behind. This is a leftover-data risk, not a scope risk. It is recorded as open.

### 14.3 Should `scripts/cleanup_smoke.py` be removed, restricted, or kept?

**Decision: keep, with documented risk. No code change.**

Reasons:
- The script is an operator tool for the *application* database. It is not an evaluation runner and was never meant to act on a disposable target, so the disposal contract does not apply to it. Removing it would remove a working operator capability without a replacement.
- It is already gated by a human. It deletes by exact email, lists the documents it will remove, and prompts `[y/N]` unless `--yes` is given.
- Its failure modes are real and are recorded as the risk: `delete_upload` swallows `OSError` and returns `False`, so a failed file deletion is reported as "already absent" when the file still exists. `_resolve_stored_path` accepts absolute paths recorded in the database, so a corrupted `stored_path` could direct the deletion outside the upload directory. Its `rmtree` of the user directory uses `ignore_errors=True`.

Recommended follow-up, which needs Coordinator and Security approval because it changes an operator tool: restrict deletions to the upload root with the existing `cleanup_path.is_under` check, and report a failed deletion as an error rather than as absent.

Documented risk: run only against the application database by an operator who intends to remove that user. Do not point it at a disposable or evaluation database, and do not run it unattended.

### Status after these decisions

- Same-server rule: decided not to adopt for runners; loopback rule recorded as an open per-runner decision.
- Upload raw DELETEs: scope accepted; conversion and `try/finally` cleanup recorded as follow-ups.
- `cleanup_smoke.py`: kept with documented risk; hardening recorded as a follow-up.
- `cleanup_orphan_uploads.py` (filesystem) and the `run_phase3e_validation.py` temp-file unlinks remain UNRESOLVED, as in section 5.
