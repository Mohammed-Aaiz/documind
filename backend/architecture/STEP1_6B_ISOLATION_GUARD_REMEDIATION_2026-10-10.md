# Step 1.6B — Central Isolation Guard Remediation

STATUS: COMPLETE for the central guard only. The three structure runners are NOT changed (Step 1.6C). Guard-level unresolved items are listed in §8.

Date: 2026-10-10
Predecessor: `backend/architecture/STEP1_6A_GUARD_FIRST_REMEDIATION_2026-10-10.md` (BLOCKED on this guard)

## 1. Original failure and reproduction

The guard compared `(host, port, database)` textually. Probe (VERIFIED BY TEST in 1.6A; pure string, no connection; application `localhost:5432/documind`):

| Target | Old result | Same database? |
|---|---|---|
| `127.0.0.1:5432/documind` | ACCEPTED | yes |
| `localhost/documind` (default port) | ACCEPTED | yes |
| `LOCALHOST:5432/documind` | REJECTED | yes (rejected only by accident of lower-casing) |

## 2. Identity assumptions

- Postgres identifies a database by **server + name**. A server is a host and port. Two strings cannot prove that two hostnames name the same server or different servers without DNS or a connection, and this guard performs neither.
- Therefore the guard does not use hostnames or ports to prove separation. It uses the **database name**, compared case-insensitively after percent-decoding.
  - Different name → separate database → accepted.
  - Same name → cannot be shown separate → refused, whatever the hosts and ports.
- Consequence (documented limitation): a legitimate separate database that happens to share the application's name, on another server, is refused until it is renamed. The guard fails closed here by design (see §7).
- Port normalization and loopback recognition were considered and not used for the decision. They are unnecessary once the rule is name-based, and a tunnel can map one server to several local ports, so they cannot prove separation either.
- Schemes: only `postgresql*` URLs (drivers such as `+asyncpg`) are accepted. No DSN is parsed for host equality.
- Application URL: `application_url=None` means "resolve from `backend/.env`" (existing behaviour, unchanged for runners that pass nothing). An **empty string** no longer falls back to settings. It fails closed.

## 3. Guard implementation changes (`backend/evaluation/isolation.py`)

1. `database_identity`: a malformed port raises `UnsafeEvaluationTarget` with a fixed message that does not echo the URL. The database name is percent-decoded.
2. `display_dsn`: malformed URLs render as `<malformed database URL>`.
3. `evaluation_database_url` and `describe_targets`: the application URL is used when it is not `None`, so an empty value is not replaced by settings.
4. `assert_safe_evaluation_target`:
   - Refuses a target or application URL with no host or no database name (unchanged messages).
   - Refuses an empty application URL (its identity is then unresolvable).
   - New `_refuse_unverifiable_url` for both URLs: refuses any scheme that is not `postgresql*`, and any connection-override parameter (`host`, `hostaddr`, `port`, `dbname`, `service`, case-insensitive). Messages name keys only, never values.
   - Compares database names case-insensitively. A shared name is refused with a message that names the target and the application database (credential-free). A different name is accepted.
5. Module docstring updated to describe name-based separation and the integration-layer mirror gap.

No runner, Alembic, model, benchmark, or application file was changed.

## 4. Tests

- New: `backend/tests/unit/evaluation/test_isolation_guard_identity.py`. Pure string tests. No engine, no connection, no `.env`, no fixtures import. Application URLs are passed explicitly. Covers the 12 required categories (aliases, IPv4/IPv6, default vs explicit port, case and percent-encoding, missing application URL with settings-resolver tripwire, missing evaluation URL, unsupported and malformed URLs, different names on a shared host, unknown host equivalence, credential and query-value non-disclosure, legitimate isolated targets, fail-closed overrides).
- Updated (2 tests that pinned the old rule): in `backend/tests/unit/evaluation/test_evaluation_isolation.py`:
  - `test_identity_is_compared_not_only_the_name` → `test_same_name_on_another_host_is_refused`.
  - `test_port_difference_alone_is_enough` → `test_port_difference_alone_is_refused`.

Results (VERIFIED BY TEST, actually run):
- `py -m pytest -p no:cacheprovider -q tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_evaluation_isolation.py -k "not test_application_dsn_resolution_matches and not test_missing_env_file_still_resolves"` → **61 passed, 2 deselected**, exit 0.
- Deselected by design, not run: `test_application_dsn_resolution_matches` (reads `backend/.env` for comparison) and `test_missing_env_file_still_resolves_a_dsn` (loads application settings). Both would touch configuration this task must not read.
- Not run: `test_legacy_runner_isolation.py`, `test_phase3d_*`, `test_phase3e_*`, `test_phase3f_*`, `test_phase4b_*`. They import the runner modules, which import `storage.database` at module scope (engine creation at import). That is outside the safe-execution constraints. Source review shows their same-name assertions (`REFUSING` for `documind` on the same server) still hold under the new rule, and the "permitted but unreachable" case uses a different name (`documind_eval`), which stays accepted. They are NOT verified by execution.

## 5. Static checks

- `py -m py_compile evaluation/isolation.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_evaluation_isolation.py` → exit 0.
- `git diff --check -- backend/tests/unit/evaluation/test_evaluation_isolation.py` → exit 0.
- Trailing-whitespace grep on `isolation.py` and the new test file → 0 hits.
- `git diff --check` cannot cover `isolation.py` or the test files, because Git lists both as untracked (see §6).

## 6. Git preservation

- HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`, unchanged.
- Against the 1.6A baseline (`/tmp/step16a_baseline_status.txt`), the only new status entries are this report (1.6A) and `backend/tests/unit/evaluation/test_isolation_guard_identity.py` (new in 1.6B). The pre-existing dirty tree is otherwise intact.
- **Important:** `backend/evaluation/isolation.py` and `backend/tests/unit/evaluation/test_evaluation_isolation.py` were **already untracked** before this task (`??` in the baseline). Git therefore cannot show their diffs. The pre-change content of `isolation.py` is only available from the 1.6B session transcript. The pre-change `test_evaluation_isolation.py` differed from the current file only in the two tests in §4. Reviewers should compare against those descriptions, not a Git diff.
- Unchanged, verified by MD5 against the 1.6A baseline: `run_structure_rrf_calibration.py`, `run_structure_element_measurement.py`, `run_structure_confirmation.py`.
- The MD5 of `isolation.py` changed, which is the intended edit.
- No tracked file was modified. No stash, reset, checkout, clean, or commit was performed.

## 7. Behaviour changes (for reviewers)

| Case | Before | After |
|---|---|---|
| `localhost` vs `127.0.0.1`, same name | accepted | refused |
| default port vs explicit `5432`, same name | accepted | refused |
| same name, different unknown host | accepted | refused |
| same name, different port | accepted | refused |
| name differs in case or percent-encoding | accepted | refused |
| empty application URL | fell back to settings | refused (fail closed) |
| malformed port | `ValueError` | `UnsafeEvaluationTarget` (no URL echo) |
| non-`postgresql` scheme | only failed if hostless | refused |
| `host`/`hostaddr`/`port`/`dbname`/`service` in URL | accepted | refused |
| different name, different host or port | accepted | accepted (unchanged) |

**Operator input required:** to use a separate database that shares the application's name, rename it, or give it a different name on the same server. Intended configuration (`documind_integration`) is unaffected.

## 8. Unresolved limitations

1. **The three structure runners are still unsafe until Step 1.6C.** They import `storage.database` at module scope and do not call the guard. This task did not change them, by instruction.
2. **The test-layer mirror `backend/tests/fixtures/integration_db.py` still compares textually.** It is outside this task's scope. It must be brought in step, or its alias gap remains. Its guard is used only by the integration suite, which was not run.
3. Hostname equivalence is never established. This is deliberate. A name-based rule cannot prove separation for two different databases with the same name, so those are refused.
4. Runner-level behaviour is not verified by execution. See §4 for the runner tests that were not run.
5. Runtime behaviour is NOT VERIFIED: no runner was executed, and no database was contacted.
6. `isolation.py` and its test file are untracked in Git. Their history is not recoverable from Git.

## 9. Confirmation

- No database was contacted. No `create_async_engine` or `connect` call was made, and the guard is checked by an existing test to contain none.
- No evaluation runner, migration, cleanup function, integration test, or end-to-end test was executed.
- `backend/.env` was not read by this task's tests. The two `.env`-touching tests were deselected, and the isolation module's `.env` resolution was not called in the focused run.
- The frozen benchmark, model weights, and `backend/architecture/**` other than this report were not modified.
