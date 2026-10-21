# Step 1.6C — Guard-First Structure Runners

STATUS: COMPLETE for import and binding order in the three runners. Not verified: PostgreSQL behaviour, and any runner execution (none was run, by instruction). See §9.

Date: 2026-10-10
Predecessors: Step 1.6A (BLOCKED on the guard), Step 1.6B (guard fixed, name-based separation).

## 1. Starting state

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged at the end).
- Git status: 1,118 entries before this task. The three runners and `isolation.py` are **untracked**, so Git cannot show their diffs. Baseline: `/tmp/step16c_baseline_status.txt`. Hashes before editing: `/tmp/step16c_hashes.txt`.

## 2. Original import paths and risks (VERIFIED FROM SOURCE)

| Runner | Module-scope database import | Other module-scope import chain | Guard |
|---|---|---|---|
| `run_structure_element_measurement.py` | `storage.database` (engine and session factory built on import) | imports `run_dual_path_ablation` (safe) | none |
| `run_structure_rrf_calibration.py` | `storage.database` | imports the element runner (which imports storage), and `chat.rag` | none |
| `run_structure_confirmation.py` | `storage.database` | imports the element and calibration runners, and `chat.rag` | none |

Risks:
- Importing any of the three builds the global engine from `settings.database_url`, which defaults to the application database.
- The calibration and confirmation runners reach storage indirectly through the element runner, so moving one import would not have been enough.
- `config.get_settings` is `lru_cache`d and `storage.database` reads it once at import. Exporting `DATABASE_URL` alone would not reach the engine if settings were already cached (VERIFIED FROM SOURCE, `backend/config.py`).
- The destructive operations (`delete`, user cleanup) are in `main`, after the engine.

## 3. Changes

Only the import header, a new binding block, and the first lines of `main()` changed in each runner. No evaluation logic was edited.

**Element runner** (`run_structure_element_measurement.py`):
- Storage and chat imports removed from module scope. `async_session`, `engine`, `rag` are `None` placeholders.
- Imports `application_database_url`, `assert_safe_evaluation_target`, `database_identity`, `describe_identity`, `evaluation_database_url` from `evaluation.isolation` (stdlib-only module).
- `guard_evaluation_target()` resolves the target, calls the central guard, prints the identities, exports `DATABASE_URL`, clears the settings cache, and records `APPROVED_EVALUATION_DSN`.
- `verify_bound_engine(engine)` refuses unless the engine's database, host and port equal the approved target.
- `bind_database_runtime()` runs the guard, then imports `chat.rag` and `storage.database`, verifies the engine, and binds the names. Idempotent.
- `main()` calls `bind_database_runtime()` after reading argv, before any work.

**RRF runner** (`run_structure_rrf_calibration.py`):
- Module-scope `storage.database` and `chat.rag` imports removed. `async_session`, `engine`, `rag`, `RRF_K` are placeholders.
- `bind_database_runtime()` first calls `base.bind_database_runtime()`, which runs the central guard, then imports and verifies its own names.
- `main()` calls `bind_database_runtime()` first.

**Confirmation runner** (`run_structure_confirmation.py`):
- Same pattern. `bind_database_runtime()` first calls `calib.bind_database_runtime()`, which in turn runs the guard through the element runner.

The guard is the single central one. No runner-specific guard was written, and there is no application-database fallback. Execution still requires `DOCUMIND_INTEGRATION_DATABASE_URL` (or the runner's implicit application target, which the guard refuses).

## 4. Guard-before-engine ordering evidence

- **VERIFIED BY TEST** (`test_guard_runs_before_any_database_module_is_imported`): the guard is called exactly once, and the storage and chat poison is replaced only inside that call, so any earlier import would have failed.
- **VERIFIED BY TEST** (`test_rejected_target_never_replaces_the_database_modules`): a refused target leaves `storage.database` and `chat` unimported and `DATABASE_URL` unset.
- **VERIFIED BY TEST** (`test_importing_a_runner_creates_no_engine`): importing any runner, with storage and chat poisoned, succeeds, and `engine`, `async_session`, `rag` are `None`.
- **VERIFIED FROM SOURCE** (AST, `test_no_module_scope_import_reaches_the_database`): no module-scope import of a database package in any of the three files.
- **VERIFIED FROM SOURCE** (AST, `test_no_module_scope_code_reads_a_bound_name`): no module-scope or default-argument read of a bound name.
- **VERIFIED FROM SOURCE** (AST, `test_main_binds_the_database_before_any_work`): the first non-assignment statement of `main()` is the bind call.

## 5. Focused tests and results

File: `backend/tests/unit/evaluation/test_structure_runner_guard_order.py` (new). Poison entries in `sys.modules` for `storage.database` and `chat` make any import raise. `config` is a stub whose `get_settings` raises if called. The application URL is patched in the element runner. No `.env` read, no engine, no connection. The runners are never executed. Only binding functions are called.

Command: `py -m pytest -p no:cacheprovider -q tests/unit/evaluation/test_structure_runner_guard_order.py` (with `set -o pipefail`).
Result: **38 passed in 0.32s, exit 0.**

Coverage by case: import without engine (3); guard before import (3); refused target (3); fail-closed real guard, five cases across three runners (15: unset, empty, malformed port, host alias, unsupported scheme); approved target binds and is verified, idempotent (3); engine for another target refused (1); AST checks (9); constants unchanged (1).

Not run: the element, RRF and confirmation runners, `run_dual_path_ablation.py`, the legacy and phase cleanup tests (they import runner modules and are outside the safe-test constraints), and the integration fixture.

## 6. Static checks

- `py -m py_compile` on the three runners and the new test file: exit 0.
- `git diff --check` on the three runners: exit 0. They are untracked, so Git does not cover them fully. Trailing-whitespace grep on the new test file: 0 hits.
- Source review of the edit scope: each runner's changes are the header, the new binding block, and the first lines of `main()`. Function bodies were not touched.

## 7. Confirmations

- **No database was contacted.** The tests poison the database modules. The only engine-related code that runs is the stand-in `FakeEngine`, which holds a parsed URL and connects to nothing.
- **No evaluation runner, migration, cleanup function, integration test, or end-to-end test was executed.**
- `backend/.env` was not read by any test. `config` was stubbed.

## 8. Protected-artifact and Git preservation

- HEAD unchanged: `6baaa2a0773df66e5fb26814afbe67647fb43435`.
- Status diff against the 1.6C baseline: only the new test file was added. No other entry changed.
- Hashes: the three runners changed, as intended. `isolation.py` and `run_dual_path_ablation.py` are unchanged (MD5 OK).
- Frozen benchmark, model weights, the integration fixture, Alembic configuration, and `config.py` were not modified.
- No tracked file was modified. No stash, reset, checkout, clean, or commit was performed.

## 9. Remaining limitations and follow-up

1. **Behaviour change for the runners.** They used to run against the application database by default. Now they refuse unless `DOCUMIND_INTEGRATION_DATABASE_URL` names an isolated database with a different name. This is intended, and it is the only way they run now.
2. **Settings precedence: VERIFIED BY TEST (post-run check).** `Settings(_env_file=<temp file>)` with `DATABASE_URL` in the environment returned the environment value, not the file value. The real `backend/.env` was not read. `verify_bound_engine` catches a mismatch after import; it does not prevent the engine being built.
3. **Same cache risk in other runners.** `run_dual_path_ablation.py` sets `DATABASE_URL` before importing storage, without clearing the settings cache. It was not changed here. It is a follow-up, NOT VERIFIED either way.
4. **Engine creation happens before the post-import check.** `verify_bound_engine` runs after `storage.database` builds its engine. No connection is made at creation, but a mismatch is detected after the engine object exists, not before.
5. **The integration fixture still compares textually** (from Step 1.6B; untouched here).
6. **Other runners** that bind the database at module scope were not inspected in this task.
7. **PostgreSQL behaviour, cleanup scope and concurrency**: NOT VERIFIED.
8. **Runners are untracked in Git.** Their pre-change content exists only in this session's reads; reviewers must compare against the description in §2–§3.
