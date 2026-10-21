# STEP 1.6H — Destructive Integration Database Authorization

Date: 2026-10-11
Status: **COMPLETE FOR THE INTEGRATION FIXTURE — SOURCE AND FOCUSED UNIT TESTS ONLY.**
The same authorization gap still exists in the evaluation runners (section 7) and is **BLOCKED** there.

PostgreSQL verification remains **NO-GO** until the broader readiness blockers are resolved and an explicitly approved, isolated disposable PostgreSQL target is available.

## 1. Baseline

- Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`
- Initial `git status --short`: 384 entries (a large pre-existing working tree, including tracked modifications and deletions and many untracked paths). Recorded by count only; the full listing was not saved to a file.
- No database was contacted. No fixture provisioning, runner, migration, cleanup, or integration/E2E test was executed. No `.env` value was read or printed.

## 2. Destructive execution paths (Workstream A)

Traced by reading `tests/fixtures/integration_db.py`, `evaluation/isolation.py`, `tests/fixtures/e2e_config.py`, and the callers.

| Path | Target URL source | Connection that performs the operation | Validated before first destructive op? | What authorized it before this step |
| --- | --- | --- | --- | --- |
| `provisioned_integration_database()` → `_drop_database(name)` / `_create_database(name)` | `integration_database_url()`: `DOCUMIND_INTEGRATION_DATABASE_URL` if set, else the application DSN with the database name replaced by `documind_integration` | `psql_value(application_database_url(), …)`, the application server's maintenance connection | Yes, `assert_isolated_target()` ran before drop. Checked URL identity against the application's | **URL validation only.** Name differing from the application's, or same server |
| `_drop_database` in the `finally` block | same `name` | same | Same check, run once before | Same |
| `isolated_database` pytest fixture | calls `provisioned_integration_database()` | same | same | same |
| `test_real_e2e_validation.py` `__main__`, `--use-provisioned-database` branch | `DOCUMIND_INTEGRATION_DATABASE_URL` set by the caller | in-process `run_full_validation()` **deletes rows** from `users`, `documents`, `document_chunks` | Only `assert_isolated_target()`. **No provisioning, so no drop gate.** | **URL validation only** |
| `test_real_e2e_validation` pytest test | the `isolated_database` fixture | `run_full_validation()` | Through the fixture | Same as the fixture |
| Evaluation runners 3D / 3E / 3F / 4B / dual-path (`evaluation/experiments/`) | `--database-url` → `DOCUMIND_INTEGRATION_DATABASE_URL` → application DSN | runner's own engine deletes rows it owns | Central `assert_safe_evaluation_target` (name-based). Not in this fixture | **URL validation only**. Out of scope for this fixture; see section 7 |

Answers to the required questions:

1. **Which URL supplies the target?** `DOCUMIND_INTEGRATION_DATABASE_URL` if set, else the application DSN with `documind_integration` as the database name.
2. **Which connection performs the operation?** The application server's maintenance connection (`e2e_config`'s host, port, user, and password), with the target's *database name*. The target DSN's host and port are not used for the connection. Step 1.6G added a same-server requirement, so the target and maintenance connection now refer to the same server.
3. **Validated before the first destructive operation?** Yes, for the provisioning path. The `__main__` branch was validated only by `assert_isolated_target()`, which is correct for the URL but had no disposal gate.
4. **What authorized the target for deletion before this step?** Nothing beyond URL validation. A name differing from the application's name, a well-formed URL, or the presence of the URL variable was sufficient.
5. **Could a non-application database be selected and destroyed through configuration alone?** **Yes.** Setting `DOCUMIND_INTEGRATION_DATABASE_URL` to any well-formed PostgreSQL URL on the application server with a different database name would have passed every check and let `DROP DATABASE … WITH (FORCE)` destroy that database. This is the gap this step closes.

## 3. Authorization mechanism (Workstream B)

**Search result:** the repository contains **no** existing operator-controlled allow-list or disposal-authorization mechanism. Searches for `allowlist`, `DISPOSABLE`, `authoriz`, `DESTRUCTIVE`, and `ALLOW_DESTR` found only the CORS allow-list, HTTP auth headers, and documentation describing `documind_integration` naming. None of these authorizes destruction.

**Policy implemented: fail closed, with an explicit operator allow-list.**

- New variable: `DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE`. Its value must be the **exact database name** of the target (after surrounding whitespace is stripped).
- It is a separate variable from the URL. Setting the URL never authorizes destruction. Unset or blank refuses.
- It is an operator declaration, not proof that the database is disposable. The operator asserts it by naming it. The gate guarantees only that the destroyed name is the one named.

Two checks now, kept distinct:

- `assert_isolated_target()`: URL validation. Explicit target, well-formed PostgreSQL URL, central guard (`assert_safe_evaluation_target`), not the application database by name, same server. Performs no I/O.
- `assert_disposal_authorized(dsn)`: permission. Refuses if the variable is unset or blank, or if it does not equal the target's name exactly. Performs no I/O.
- `assert_authorized_destructive_target()`: runs both, in that order. This is the entry point for every destructive path.

The primitives are gated too. `_drop_database` and `_create_database` each call `_assert_name_authorized(name)` before any SQL. That refuses an empty name, the application database's name (case-insensitive), or any name other than the authorized one. This is defence in depth: a future caller cannot bypass the gate by calling a primitive directly.

## 4. Files changed in this step

| File | Change |
| --- | --- |
| `backend/tests/fixtures/integration_db.py` | Added `DISPOSAL_AUTHORIZATION_ENV`, `assert_disposal_authorized`, `assert_authorized_destructive_target`, `_assert_name_authorized`. `provisioned_integration_database()` now calls `assert_authorized_destructive_target()` before any I/O. `_drop_database` and `_create_database` call `_assert_name_authorized` before SQL |
| `backend/tests/integration/rag/test_real_e2e_validation.py` | `__main__` `--use-provisioned-database` branch now calls `assert_authorized_destructive_target()` instead of `assert_isolated_target()`. Added the import |
| `backend/tests/unit/evaluation/test_phase3_runner_target_order.py` | One source-order anchor updated from `assert_isolated_target()` to `assert_authorized_destructive_target()`, because the provisioning function now calls the stricter gate. This is a tightened expectation, not a weakened one |
| `backend/tests/unit/evaluation/test_disposable_database_authorization.py` | **New.** 34 database-free tests (section 6) |
| `backend/architecture/STEP1_6H_…md` | **New.** This report |

Not changed: `backend/evaluation/isolation.py`, `e2e_config.py`, the Step 1.6G runner edits, and all evaluation runners. Runner edits were verified, not rewritten (section 5).

Ownership note: `tests/fixtures/integration_db.py` and `tests/integration/rag/` are TEST_AGENT-owned, and `backend/tests/unit/evaluation/` is in the test tree. The changes follow the task's explicit scope.

## 5. Step 1.6G runner changes preserved (Workstream E)

Verified by the source-order tests, not by running the runners:

- `run_phase3d_evaluation.py` and `run_phase3e_integration.py` still contain `assert_safe_evaluation_target(` before `os.environ["DATABASE_URL"] = evaluation_dsn`.
- `get_settings.cache_clear()` followed by `if get_settings().database_url != evaluation_dsn` precedes the first model import.
- `from storage.database import engine as application_engine` followed by `assert_engine_matches_target(application_engine, evaluation_dsn)` precedes route and session use.
- `engine = create_async_engine(evaluation_dsn)` followed by `assert_engine_matches_target(engine, evaluation_dsn)` and then the session factory.

These are the same as Step 1.6G. Both runners were verified by source-order tests only and were **not executed**.

## 6. Focused database-free tests (Workstream D)

New file: `backend/tests/unit/evaluation/test_disposable_database_authorization.py` (34 tests).

Isolation of these tests:
- An autouse fixture clears `DOCUMIND_INTEGRATION_DATABASE_URL` and the new authorization variable. It fixes `application_database_url` to a synthetic DSN. It replaces `psql_value`, `postgres_available`, and `subprocess.run` with functions that raise `AssertionError`, so any I/O attempt fails the test.
- The provisioning context manager and the drop and create primitives are **never called**. Source order is checked by reading the fixture's text.
- A regex scan of `tests/unit/**` checks that no other unit test calls them. Matches inside string literals are ignored.

Coverage by the requested cases:

1. Missing URL: derived target passes URL validation; authorization still refused. With a matching authorization, accepted.
2. Empty or whitespace-only URL: refused, not derived.
3. Malformed URL or unsupported scheme: refused even when authorized.
4. Target equal to the application database, or same name under a `127.0.0.1` alias: refused even when authorized.
5. Different target without authorization: refused. Blank authorization is not authorization. Naming conventions (`integration`, `test`, `documind_integration_old`) never authorize.
6. Explicit authorization: accepted, including surrounding whitespace.
7. Mismatched authorization (`other_db`, `DOCUMIND_INTEGRATION`, the application's own name): refused.
8. Rejection before destructive setup: the gate raises `RuntimeError` with I/O patched to fail. The primitives' gate refuses before SQL. Source order: authorization precedes `postgres_available()` and `_drop_database(name)`. Each primitive runs its gate before `psql_value(`.
9. No unit test calls the context manager or primitives: regex scan of `tests/unit/**`. The integration test's `__main__` call is outside this scope by design.
10. URL validation and authorization are separate: URL passes without authorization. Authorization cannot rescue a failed URL check. The combined gate calls the URL check first.
11. The `__main__` path uses the combined gate (source check).

### Commands and results

Command (first run, before fixing two of my own checks):

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py -p no:cacheprovider
→ 2 failed, 78 passed in 2.58s   (exit 1)
```

Failures and causes:
- `test_no_unit_test_calls_destructive_provisioning`: the scanner matched `_drop_database(` inside a string literal in the Step 1.6G test. Fixed by ignoring matches inside quotes. This is not a call.
- `test_fixture_drops_only_after_guard_in_source_order`: expected the old anchor `assert_isolated_target()`. The function now calls the stricter gate. Fixed by updating the anchor.

Command (final run):

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py -p no:cacheprovider
→ 80 passed in 1.52s   (exit 0)
```

Breakdown: 34 new authorization tests, 29 Step 1.6G order and fixture tests, 17 existing runner tests.

## 7. Static checks

```
cd backend && ./venv/Scripts/python.exe -m py_compile tests/fixtures/integration_db.py tests/integration/rag/test_real_e2e_validation.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_phase3_runner_target_order.py evaluation/experiments/run_phase3d_evaluation.py evaluation/experiments/run_phase3e_integration.py
→ COMPILE_EXIT=0
```

No linter or type checker was run.

## 8. Checks deliberately not run

- **NOT RUN:** `provisioned_integration_database()`, the `isolated_database` fixture, `_drop_database`, `_create_database`, `alembic`, `psql`, and any `subprocess` call the fixture makes.
- **NOT RUN:** `test_real_e2e_validation.py`, both its pytest path and its `__main__` path. `run_full_validation` was not executed.
- **NOT RUN:** the Phase 3D and 3E runners, and any evaluation runner's `main()`.
- **NOT RUN:** integration tests and end-to-end tests.
- **NOT RUN:** `scripts/setup_db.py`, cleanup scripts, migrations.
- **NOT RUN:** `test_evaluation_isolation.py` and `test_legacy_runner_isolation.py` (not established as database-free in Step 1.6G).
- **NOT PERFORMED:** any database connection, including `postgres_available()`.
- **NOT PERFORMED:** reading `.env` values. Test DSNs are synthetic.

## 9. Remaining risks and blockers

1. **Evaluation runners remain unauthorized (BLOCKED).** The evaluation runners (3D, 3E, 3F, 4B, dual-path, and table-evidence) delete rows on the target they resolve. Their only gate is the central name-based guard. They have **no disposal authorization**, so a non-application database name configured through `--database-url` or `DOCUMIND_INTEGRATION_DATABASE_URL` is accepted. This step does not change them. They belong to EVALUATION_AGENT, and they should adopt `DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE` or an equivalent. Decision needed from the Coordinator.
2. **Operator assertion, not proof.** A correctly named authorization still rests on the operator's word that the database is disposable. The gate ensures the destroyed name is the one named. It cannot prove that the server holds no other data.
3. **Host and port separation.** The fixture requires the target to be on the application's server. Its operations run through that server's maintenance connection. Step 1.6G introduced this requirement, which is stricter than the central guard. It has not been independently reviewed.
4. **Two application-DSN resolvers.** `e2e_config.database_url()` and `evaluation.isolation.application_database_url()` may read `backend/.env` and the environment with different precedence. The fixture is internally consistent, but the two are not unified.
5. **Same-server assumption.** The gate cannot prove that the maintenance connection and the target are on the same physical server beyond the textual host and port comparison. DNS and aliases are not resolved.
6. **Source-order tests** prove the order of statements, not runtime behaviour. Runtime behaviour requires an approved disposable PostgreSQL target, which does not exist yet.
7. **Two existing isolation test files are not run** (section 8).

## 10. Protected-artifact preservation

Protected paths (`backend/models/documind-qa/**`, `backend/venv/**`, `backend/phases/phase4f_gpu/**`, `backend/uploads/**`, `backend/.env`, `.env`, `dist/`, `node_modules/`) were not written by this step. `backend/venv/Scripts/python.exe` was executed only. `backend/evaluation/isolation.py` (the central guard) is unchanged. Frozen benchmarks, expected outputs, model weights, and evaluation algorithms were not touched.

## 11. Final Git status

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged).
- `git status --short`: 384 entries. The count matches the initial count recorded in section 1.
- Paths touched by this step appear as untracked: `backend/architecture/`, `backend/tests/fixtures/`, `backend/tests/integration/rag/`, `backend/tests/unit/evaluation/`, `backend/evaluation/experiments/run_phase3d_evaluation.py`, `backend/evaluation/experiments/run_phase3e_integration.py`. Several of these are untracked directories that contain pre-existing files, so the status line does not isolate this step's edits.
- Nothing was staged, committed, reset, stashed, cleaned, or reverted. Unrelated pre-existing tracked and untracked changes are preserved. The count is the same, but the baseline listing was not saved to a file, so this is evidence by count, not by file-by-file comparison.

## 12. Verdict

- **Integration fixture and its `__main__` path:** a verifiable disposal-authorization gate is enforced before every destructive path it owns, with focused database-free tests. **COMPLETE — SOURCE AND FOCUSED UNIT TESTS ONLY.**
- **Evaluation runners:** the same authorization gap remains. **BLOCKED** pending a Coordinator decision (risk 1).
- **PostgreSQL verification:** **NO-GO.**

## 13. Handoff

- Coordinator: decide whether evaluation runners adopt `DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE` (risk 1), and confirm the same-server rule (risk 3).
- EVALUATION_AGENT: the runners' destructive paths need the same authorization gate. The enforcement pattern is `assert_disposal_authorized` in `integration_db.py`.
- TEST_AGENT: review the new authorization tests and the `__main__` change.
- VERIFIER: independently run the three focused test files in section 6.
