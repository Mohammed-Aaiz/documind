# Step 1.6D — Pre-Engine Database Target Validation

STATUS: COMPLETE for pre-engine validation of the intended target in the three structure runners. Runtime engine configuration and PostgreSQL behaviour are NOT VERIFIED (§7).

Date: 2026-10-10
Predecessors: Step 1.6B (central guard, name-based separation), Step 1.6C (guard-first binding).

## 1. Starting state

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged at the end).
- The three runners, `isolation.py`, and the new test files are **untracked**, so Git cannot show their diffs. Git-status baseline: `/tmp/step16c_baseline_status.txt` (taken before Step 1.6C). Hashes: `/tmp/step16c_hashes.txt`.

## 2. Initialization sequence (VERIFIED FROM SOURCE)

For the element runner. The RRF and confirmation runners call the same function through their binding chain.

1. `main()` reads argv, then calls `bind_database_runtime()` before any work (AST-checked, Step 1.6C).
2. **Configuration resolution.** `application_database_url()` (in `evaluation/isolation.py`) reads `DATABASE_URL` from `backend/.env`. It falls back to `get_settings()` only when the file has no value. `evaluation_database_url(application_url=...)` returns the explicit override, else `DOCUMIND_INTEGRATION_DATABASE_URL`, else the application DSN. An empty override raises.
3. **Central guard.** `assert_safe_evaluation_target(target, application_url=...)`:
   - requires a host and database name on both URLs;
   - refuses non-`postgresql*` schemes and connection-override query parameters (`host`, `hostaddr`, `port`, `dbname`, `service`);
   - refuses any target whose database name equals the application's, case-insensitively.
   It is pure string inspection and opens no connection.
4. **Export and settings check (added in 1.6D).** `DATABASE_URL` is set to the approved target. `config.get_settings` is `lru_cache`d, so `cache_clear()` drops any cached value. `get_settings().database_url` is then read and must equal the approved DSN exactly. Otherwise the function raises `RuntimeError` before storage is imported.
5. **Import.** `chat.rag`, then `storage.database`. The storage module builds its engine from `settings.database_url` through `_asyncpg_engine_args` and `create_async_engine`.
6. **Effective-target verification.** `verify_bound_engine(engine)` compares `engine.url`'s database, host and port with the approved target.

### Construction versus connection

- `get_settings()` → `Settings()` reads the environment and `backend/.env`. It opens no database connection (`backend/config.py`: no import-time side effects, no validators).
- `create_async_engine` → `sqlalchemy.create_engine`: constructs the dialect and pool and registers listeners (`sqlalchemy/engine/create.py`, lines ~729–765). The source contains no `.connect()` call at construction. A connection is made only when a session or connection is requested.
- VERIFIED FROM SOURCE for both. No runtime test of SQLAlchemy was run.

## 3. Changes

Only `run_structure_element_measurement.py` changed in this step. Its `guard_evaluation_target()` gained the effective-settings check in step 4 above. The RRF and confirmation runners already bind through it (Step 1.6C) and were not edited.

Before this step, the settings value was never compared with the approved target. A cached or substituted value would have reached storage unchecked. Only the `engine.url` check ran, and that ran after the engine was built.

## 4. Tests

File: `backend/tests/unit/evaluation/test_structure_runner_guard_order.py` (updated; 1.6C file, same path).

The harness stubs `config` with a model of the effective setting: the environment value behind a cache that `cache_clear` empties. It never reads `backend/.env`. `storage.database` and `chat` are poison entries in `sys.modules`. A storage model builds its engine on first attribute access, at the point where a runner imports it.

Command: `py -m pytest -p no:cacheprovider -q tests/unit/evaluation/test_structure_runner_guard_order.py` (with `set -o pipefail`).
Result: **47 passed in 0.38s, exit 0.**

Coverage:
- Importing a runner creates no engine (3).
- The guard runs before any database import (3).
- A rejected target leaves the database modules unimported (3).
- Missing, empty, malformed, alias and unsupported-scheme configuration fails closed, real guard (15).
- An approved target binds, idempotently, with cache clear then read (3).
- The approved target reaches the engine configuration (3).
- A mismatched engine is refused by `verify_bound_engine` (1).
- A stale cached value is cleared and does not substitute the target (3).
- A settings source that `cache_clear` cannot remove refuses before storage import (3).
- AST checks: no module-scope database import, no module-scope bound-name read, `main()` binds first (9).
- Evaluation constants unchanged (1).

These tests were not run against the pre-1.6D code. The mismatch and stale-cache cases would fail there, because storage would be imported without a settings check. This is reasoned from the code, not observed.

## 5. Static checks

- `py -m py_compile` on the element runner and the test file: exit 0.
- Trailing-whitespace grep on both: 0 hits.
- Source inspection of the guard and binding sequence (§2–§3).

## 6. Confirmations

- **No database was contacted.** Storage and chat are poisoned. The only engine-like object is a `FakeEngine` that parses a URL.
- **No runner, migration, cleanup function, integration test, or end-to-end test was executed.**
- **`backend/.env` was not read by tests.** `config` is stubbed. The runtime `get_settings()` does read `.env`, as the application does, but its value is compared and never printed.
- The real `Settings()` precedence (environment over `.env`) was checked in Step 1.6C with a temporary env file. It was not re-run here.

## 7. Limitations

1. **Runtime engine configuration: NOT VERIFIED.** The tests use a model of storage. The real `storage.database` import, the real `_asyncpg_engine_args`, and the real engine URL were not exercised.
2. **Engine construction still precedes the `engine.url` check.** That check runs after `storage.database` builds the engine. The settings check is the pre-engine barrier. No connection is made at construction, but if storage ever reads its URL from another source, only the settings check would catch it.
3. **The runtime settings read loads `backend/.env`.** This is the application's normal configuration path. The task forbids reading `.env` secrets in tests and in this step, and the tests do not.
4. **The guard is conservative.** A legitimate separate database with the application's name, on another server, is refused until renamed (Step 1.6B).
5. **Other runners** (`run_dual_path_ablation.py` and others) set `DATABASE_URL` and do not clear the settings cache. Unchanged here; follow-up.
6. **The integration fixture** still compares textually (Step 1.6B; unchanged).
7. **The negative tests were not mutation-tested** against the earlier code (see §4).
8. **PostgreSQL behaviour, cleanup scope and concurrency: NOT VERIFIED.**

## 8. Git and artifact preservation

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`, unchanged.
- Status: the 1.6C baseline differs only by the 1.6C report and the test file, both from the prior step. No other entry changed in this step.
- Hashes against `/tmp/step16c_hashes.txt`:
  - `isolation.py`: UNCHANGED.
  - `run_dual_path_ablation.py`: UNCHANGED.
  - `run_structure_rrf_calibration.py` and `run_structure_confirmation.py`: differ from the pre-1.6C hashes. That change came from Step 1.6C. This step did not edit them.
  - `run_structure_element_measurement.py`: changed in this step, as intended.
- Benchmark, model weights, the integration fixture, Alembic configuration, and `config.py` were not modified.
- No stash, reset, checkout, clean, or commit was performed.
