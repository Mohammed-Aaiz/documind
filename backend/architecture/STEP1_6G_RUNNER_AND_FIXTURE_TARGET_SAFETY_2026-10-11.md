# STEP 1.6G — Runner and Integration-Fixture Target Safety

Date: 2026-10-11
Status: **COMPLETE — SOURCE AND FOCUSED UNIT TESTS ONLY**

Overall project status remains **NO-GO for PostgreSQL verification** until the
broader database-safety readiness blockers are reviewed and an explicitly
approved, isolated disposable PostgreSQL target is available.

## 1. Baseline

- Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`
- Initial `git status --short`: a large pre-existing working tree. It includes
  tracked modifications, tracked deletions (including `backend/phase4f/**`,
  `backend/tests/test_*.py`, and root-level `backend/test_*.py`), and many
  untracked paths (`agents/`, `backend/architecture/`, `backend/evaluation/**`,
  `backend/tests/unit/`, `backend/tests/fixtures/`, and others).
- No reset, clean, stash, checkout, revert, commit, or push was performed.

## 2. Files changed in this step

| File | Owner (per `agents/`) | Change |
| --- | --- | --- |
| `backend/evaluation/experiments/run_phase3d_evaluation.py` | EVALUATION_AGENT | Post-configuration settings check and engine-target checks |
| `backend/evaluation/experiments/run_phase3e_integration.py` | EVALUATION_AGENT | Same, plus the application-engine check |
| `backend/tests/fixtures/integration_db.py` | TEST_AGENT | Target validation delegates to the central guard; same-server requirement |
| `backend/tests/unit/evaluation/test_phase3_runner_target_order.py` | TEST_AGENT | New database-free tests (29 tests; 46 run together with the existing `test_runner_pre_engine_init.py`, 17 tests) |
| `backend/architecture/STEP1_6G_RUNNER_AND_FIXTURE_TARGET_SAFETY_2026-10-11.md` | Coordinator-owned (`backend/architecture/**`, append-only) | This report |

Ownership note: the two runners belong to EVALUATION_AGENT and the fixture
belongs to TEST_AGENT. Both edits were made because the task named these
files explicitly. This is a cross-owner edit and should be reviewed by the
owning agents.

The three edited source files and the new test file are **untracked** in git,
so `git diff` cannot show them. Their content was verified by `grep` and by
the tests below, not by a diff against a committed baseline.

## 3. Gap 1 — Phase 3D runner (original failure mode)

Original order: `evaluation_database_url` → `assert_safe_evaluation_target` →
`os.environ["DATABASE_URL"] = evaluation_dsn` → model imports (which import
`storage.database`, which builds the app engine from cached settings) →
`create_async_engine(evaluation_dsn)`.

Failure mode:
- `get_settings()` is `@lru_cache`. A cached `Settings` could name a different
  database than the approved target, and nothing re-checked it.
- The app engine built in `storage.database` was never compared with the
  approved target, so the runner's models and routes could use an engine that
  did not match the guard's decision.
- The runner's own engine was not checked after creation.

Change: after setting `DATABASE_URL`, the runner now calls
`get_settings.cache_clear()` and raises unless `get_settings().database_url`
equals the approved DSN. After the model imports, it imports
`storage.database.engine` and calls `assert_engine_matches_target`. It also
calls `assert_engine_matches_target(engine, evaluation_dsn)` after creating its
own engine. The check compares the central guard's identity values. It does
not add a second URL-normalization policy.

## 4. Gap 2 — Phase 3E integration runner

Same failure mode and same remedy as Gap 1, applied before `from main import app`
and before any route or session can run.

Order after the change (both runners):

1. `assert_safe_evaluation_target(...)` (central guard; string inspection only)
2. `os.environ["DATABASE_URL"] = evaluation_dsn`
3. `get_settings.cache_clear()`, then equality check against the approved DSN
4. SQLAlchemy and model imports (first `storage.database` import happens here)
5. `from storage.database import engine as application_engine` and
   `assert_engine_matches_target(application_engine, evaluation_dsn)`
6. `create_async_engine(evaluation_dsn)` and
   `assert_engine_matches_target(engine, evaluation_dsn)`
7. Session factory, corpus build, and all database work

Mirrors the existing pattern in `run_phase3e_validation.py`.

## 5. Gap 3 — Integration fixture (`tests/fixtures/integration_db.py`)

Mismatch found by inspecting `evaluation/isolation.py` and the fixture:

- The fixture compared `(host, port, database)` **text** equality against the
  application. The central guard refuses any target whose database **name**
  matches the application's (case-insensitively), whatever the host spelling.
- Concrete failure: with `DOCUMIND_INTEGRATION_DATABASE_URL` set to
  `…@127.0.0.1:55433/documind` (application `…@localhost:55433/documind`), the
  fixture's text comparison did not match, so it returned the target. It would
  then run `DROP DATABASE … WITH (FORCE)` on the application's database name.
- The fixture also fell back silently to the derived name when the override was
  empty, and it did not refuse connection-override parameters, unsupported
  schemes, or malformed ports through a central parser.
- The fixture's provisioning runs through the application server's maintenance
  connection, so a target on a different server would be acted on in the wrong
  place.

Change:

- `database_identity` delegates to `evaluation.isolation.database_identity`.
- `integration_database_url()` returns an explicitly set override as-is, even
  when empty, so the guard refuses it. It does not fall back.
- `assert_isolated_target()` calls the central
  `assert_safe_evaluation_target(target, operation=…, application_url=…)`.
  The application DSN is passed explicitly from the fixture's own resolver.
- After the central check, the fixture refuses a target whose lower-cased host
  or port differs from the application's (see Remaining risks).
- The fixture still refuses before any destructive call.
  `provisioned_integration_database()` calls `assert_isolated_target()` before
  `_drop_database`. A source-order test pins this.

Import direction: `tests/` imports from `evaluation/isolation`. This is allowed.
`evaluation/` does not import from `tests/`. `isolation.py` imports `config`
only lazily inside a function, so there is no import-time engine creation and
no cycle.

## 6. Focused database-free tests

New file: `backend/tests/unit/evaluation/test_phase3_runner_target_order.py`

Coverage:
- Source-order checks for both runners. The text of `main()` is read without
  importing the runner, so `main()` never runs. Covers: guard before
  configuration; cache clear and settings check before model imports;
  application-engine check before routes or sessions; runner-engine check after
  creation; central engine check imported; no top-level database import.
- Fixture policy with the application DSN monkeypatched: default derived target
  accepted; explicit isolated override accepted; application name refused;
  case-variant name refused; host alias (`127.0.0.1`) with same name refused;
  empty override refused; override with `host`, `dbname`, a non-postgres
  scheme, a malformed port, an empty database name, or an empty host refused;
  different host or port refused as a different server; unsafe application
  DSN refused.
- Fixture `database_identity` equals the central identity.
- Fixture refuses before the drop (source order).

No live database, migration, cleanup, or fixture provisioning was used.
`tests/conftest.py` has no module-level engine and no autouse fixtures
(checked with `grep` and `pytest.ini`). The new file imports only
`evaluation.isolation`, `tests.fixtures.integration_db` (which imports
`e2e_config` and `paths`, both stdlib-only at import), and `pytest`.

### Commands and results

Command 1 (first run, before a fix to my own test expectation):

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_phase3_runner_target_order.py -p no:cacheprovider
→ 1 failed, 28 passed in 0.19s   (exit 1)
```

The failure was in my test, not the code. The derived default target
correctly keeps the application's credentials, and my expected value wrongly
used the override credentials. I corrected the expectation to the derived value.

Command 2 (final run):

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py -p no:cacheprovider
→ 46 passed in 1.43s   (exit 0)
```

`test_runner_pre_engine_init.py` is an existing DB-free file. It was read in
full before running, and it uses `storage.database` stubs and a subprocess
import check.

A separate attempt to run `tests/unit/evaluation/test_evaluation_isolation.py`
and `test_legacy_runner_isolation.py` in one command timed out at 30 s. Their
database-free status was not established, so they were **NOT RUN** in this
step.

## 7. Static checks

Command:

```
cd backend && ./venv/Scripts/python.exe -m py_compile evaluation/experiments/run_phase3d_evaluation.py evaluation/experiments/run_phase3e_integration.py tests/fixtures/integration_db.py tests/unit/evaluation/test_phase3_runner_target_order.py
→ COMPILE_EXIT=0
```

Grep confirmation of the edits: `get_settings.cache_clear` at 3D:645 and 3E:178;
`storage.database` application-engine checks at 3D:664–666 and 3E:198–200;
runner-engine checks at 3D:674 and 3E:212; fixture `assert_safe_evaluation_target(`
at integration_db.py:161; `different server` refusal at integration_db.py:175.

No linter or type checker was run.

## 8. Not performed (deliberately)

- **NOT RUN:** Phase 3D and Phase 3E runners (no `main()` execution).
- **NOT RUN:** any integration test or end-to-end test.
- **NOT RUN:** `integration_db.provisioned_integration_database` or
  `isolated_database` fixture, including drop, create, `psql`, and alembic.
- **NOT RUN:** `scripts/setup_db.py`, cleanup scripts, or migrations.
- **NOT RUN:** `test_evaluation_isolation.py` and `test_legacy_runner_isolation.py`
  (see section 6).
- **NOT PERFORMED:** any database connection, including `postgres_available()`.
- **NOT PERFORMED:** reading `.env` values. The guard's `.env` read was not
  exercised, and no secret was printed. Test DSNs are synthetic.
- **NOT PERFORMED:** any PostgreSQL verification. No claim is made.

## 9. Protected-artifact preservation

- `backend/models/documind-qa/**`, `backend/venv/**`, `backend/phases/phase4f_gpu/**`,
  `backend/uploads/**`, `backend/.env`, `.env`, `dist/`, `node_modules/`: not
  written. `backend/venv/Scripts/python.exe` was executed only, never modified.
- `backend/architecture/**`: this report is the only new file there. No existing
  file in that directory was changed.
- Frozen benchmark data, model weights, expected outputs, and evaluation
  algorithms were not touched.
- `backend/evaluation/isolation.py`, the central guard, was **not** modified.

Final `git status --short` was checked with
`git status --short -- backend/evaluation/experiments backend/tests backend/architecture`.
The changed files are untracked and nothing was staged, committed, reset,
stashed, or deleted. The pre-existing tracked deletions and modifications listed
in section 1 are still present.

## 10. Remaining risks and blockers

1. **New policy, to review:** the fixture now refuses a target on a different
   host or port, including `localhost` against `127.0.0.1`. This is stricter
   than the central guard, which accepts a different name on any host. It is
   the minimal correct behaviour for a fixture whose provisioning runs on the
   application server, but it is a policy decision for TEST_AGENT and the
   Coordinator.
2. **Two application-DSN resolvers:** the fixture uses `e2e_config.database_url()`,
   and the central guard uses `evaluation.isolation.application_database_url()`.
   The two may read `backend/.env` and the environment in different precedence.
   The fixture is consistent with itself because it passes its own DSN to the
   guard. The two resolvers are not unified; that needs an owner decision.
3. **Stale docstring:** `evaluation/isolation.py` (EVALUATION_AGENT) still says
   the fixture's rules "must be brought into step separately." This is now
   partly done and should be updated by its owner.
4. **Runner tests are source-order, not behavioural.** They prove the order of
   statements in the source. They do not prove runtime behaviour, which needs an
   approved disposable database and was not executed.
5. **Two existing isolation test files not run** (section 6).
6. **Engine identity uses the central literal comparison.** A host spelled
   differently from the approved target is a mismatch by design, so a legitimate
   alias would fail closed.

## 11. Handoff

- EVALUATION_AGENT: review the runner edits (3D, 3E) and update the stale
  docstring in `evaluation/isolation.py`.
- TEST_AGENT: review the fixture policy in risk 1 and the new test file.
- VERIFIER: independently run the two focused test files listed in section 6.
- Coordinator: decide the unified application-DSN resolver (risk 2) and confirm
  the host or port policy (risk 1). The PostgreSQL go/no-go remains **NO-GO**
  until the broader database-safety blockers are reviewed.
