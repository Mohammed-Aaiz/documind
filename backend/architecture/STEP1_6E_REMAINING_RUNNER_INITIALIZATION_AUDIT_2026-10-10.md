# STEP 1.6E — Remaining Runner Database Initialization Audit

Date: 2026-10-10. Scope: `backend/evaluation/` runners and the shared isolation module.
No database was contacted. No evaluation runner, migration, cleanup function,
integration test, or end-to-end test was executed.

## 1. Executive summary

- **Status: INCOMPLETE.** Eight research runners still show remediation-required
  initialization gaps (section 2). Only the table-evidence and dual-path runners
  were remediated in this step.
- **Remediated:** `run_table_evidence_measurement.py` and `run_dual_path_ablation.py`.
  A shared engine-target check was added to `evaluation/isolation.py`.
- **Tests:** 17 new database-free tests in
  `tests/unit/evaluation/test_runner_pre_engine_init.py` pass. The full
  `tests/unit/evaluation` directory passes (458 tests, exit 0).
- **Not established:** the Step 1.5 master-register IDs (E1–E13) were not
  re-read in this step, so the inventory below is keyed by file, not by register ID.
- **Limitation:** no PostgreSQL verification. The integration fixture still
  compares database identity as text (section 7).

## 2. Remaining-runner inventory

Labels: `SAFE FROM SOURCE` · `REMEDIATION REQUIRED` · `NOT VERIFIED` ·
`OUT OF SCOPE — JUSTIFICATION REQUIRED`. Paths are under `backend/evaluation/experiments/`.

| # | Runner | Guard | Settings cache | Effective-settings check | Engine URL check | Label |
|---|---|---|---|---|---|---|
| 1 | `run_dual_path_ablation.py` | `assert_safe_evaluation_target` before imports (l.615) | `cache_clear()` added (l.631) | added (l.632) | `assert_engine_matches_target` after engine import (l.670) | `SAFE FROM SOURCE` (init path). Cleanup not re-audited here. |
| 2 | `run_table_evidence_measurement.py` | `assert_safe_evaluation_target` in `_resolve_database_url` (l.269) | `cache_clear()` added (l.285) | added (l.286) | `assert_engine_matches_target` after `create_async_engine` (amain l.1099) | `SAFE FROM SOURCE` (init path). Cleanup not re-audited here. |
| 3 | `run_phase3d_evaluation.py` | yes (l.624) | none | none | none (`create_async_engine(evaluation_dsn)` l.654) | `REMEDIATION REQUIRED` |
| 4 | `run_phase3d_upload_integration.py` | yes (l.192) | none | none | none (l.240) | `REMEDIATION REQUIRED` |
| 5 | `run_phase3e_integration.py` | yes (l.158) | none | none | none (l.193) | `REMEDIATION REQUIRED` |
| 6 | `run_phase3e_validation.py` | yes (l.159) | none | none | none (l.191) | `REMEDIATION REQUIRED` |
| 7 | `run_phase3f_evaluation.py` | yes (l.800) | none | none | none (l.827) | `REMEDIATION REQUIRED` |
| 8 | `run_phase4b_evaluation.py` | yes (l.780) | none | none | none (l.807) | `REMEDIATION REQUIRED` |
| 9 | `run_structure_confirmation.py` | Step 1.6C | Step 1.6C | Step 1.6C | — | `SAFE FROM SOURCE` per 1.6C; not re-verified here |
| 10 | `run_structure_rrf_calibration.py` | Step 1.6C | Step 1.6C | Step 1.6C | — | `SAFE FROM SOURCE` per 1.6C; not re-verified here |
| 11 | `run_structure_element_measurement.py` | Step 1.6C (l.1811) | `cache_clear()` (l.1830) | Step 1.6C | — | `SAFE FROM SOURCE` per 1.6C; not re-verified here |

Rows 3–8: the static search found no `cache_clear`, no effective-settings
comparison, and no engine-URL comparison. Each builds its own engine with
`create_async_engine(evaluation_dsn)` after a guard. Because `storage.database`
is imported lazily or not at all, the application engine is not built at import,
but a settings value cached before the run could still name the application
database. Their `application_database_url()` fallback behaviour was **not
verified** line by line in this step.

Rows 9–11 were remediated in Step 1.6C. Their ordering is covered by existing
`tests/unit/evaluation/test_structure_runner_guard_order.py`. They were not re-audited here.

**Out of scope — justification required:**
- `backend/scripts/db_check.py`, `create_test_user.py`, `cleanup_smoke.py`,
  `cleanup_orphan_uploads.py`: operational scripts, not evaluation runners.
  `cleanup_smoke.py` and `cleanup_orphan_uploads.py` contain deletes and are
  **NOT VERIFIED** here; they need their own audit.
- `backend/evaluation/runner.py`: library module, no entry point. Imported
  transitively; not separately inventoried.
- `backend/phases/**` (archived research, EVALUATION_AGENT-owned): `phase4d/oracle_eval.py`
  uses in-memory SQLite only. The rest of `phases/` was **NOT VERIFIED**. `phase4f_gpu/**` is forbidden and was not touched.

## 3. Import-order and settings-cache findings

- `storage/database.py` builds the global engine from `get_settings()` at import
  time. Any module importing it before the guard runs builds the application
  engine first.
- **Table runner (before):** a module-level `_import_all_models()` ran before
  any guard, and the resolver fell back to the application URL. Both were removed.
  The models are now imported only from `amain()`, after the guard. Tests confirm
  that import builds no engine.
- **Dual-path runner (before):** the guard ran before imports, but cached settings
  were not cleared and no engine check existed. Both were added.
- **Shared helper:** `assert_engine_matches_target(engine, dsn)` in
  `evaluation/isolation.py` reads only `engine.url` and compares
  `(host, port, database)` literally. It opens no connection.

## 4. Changes made and rationale

1. `backend/evaluation/isolation.py` — added `assert_engine_matches_target`. It is
   the single engine-URL comparison, so runners do not carry their own checks.
2. `backend/evaluation/experiments/run_table_evidence_measurement.py`
   - removed the module-level `_import_all_models()` call and the application
     fallback. `EVAL_DB_ENV` is now required and non-blank.
   - guard, then loopback check, then export of the approved DSN and
     `cache_clear()`, then an effective-settings check, then the storage import.
   - `amain()` checks the engine URL after creating it.
3. `backend/evaluation/experiments/run_dual_path_ablation.py`
   - `cache_clear()` and an effective-settings check before the first
     database-dependent import.
   - `assert_engine_matches_target` after the storage import.

Evaluation semantics, the frozen benchmark, and the expected outputs are unchanged.

## 5. Focused test results

Command: `./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_runner_pre_engine_init.py`
— **17 passed, exit 0.** Coverage:
- importing each runner does not import `storage.database` (subprocess, both runners);
- a missing or blank target, an application-equal target, and a remote host each
  refuse before storage is imported (`storage.database` is replaced with an
  import-failing stub);
- cached settings naming another database are refused with `RuntimeError`;
- an effective setting that matches the target is accepted, and the cache is cleared;
- `amain()` orders guard, models, and engine correctly; no top-level model import;
- dual-path ordering: cache clear and settings check precede model and storage imports;
- `assert_engine_matches_target` accepts a match and refuses a different name,
  port, or host spelling, with no connection.

Command: `./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation`
— **458 passed, exit 0** (includes the 17 above).

## 6. Static-check results

- `py_compile` on the three changed source files and the new test file: **exit 0**.
- `git diff --check` on the three changed source files: **exit 0**.
- Protected artifacts were not edited in this step (section 8).

## 7. Integration-fixture limitation

`backend/tests/fixtures/integration_db.py` line 153 still compares
`database_identity(target) == application` as a textual `(host, port, database)`
tuple. It does not refuse host aliases such as `localhost` versus `127.0.0.1`,
which `evaluation/isolation.py` now refuses. It was **not executed and not modified**
in this step. It needs a separate remediation that brings its rules in line with
`isolation.py`.

## 8. Protected-artifact preservation

- No edits to the frozen benchmark, model weights, `phases/phase4f_gpu/**`,
  `backend/uploads/**`, `backend/.env`, `.env`, or `backend/architecture/**`
  (other than this report).
- No commit, push, reset, stash, checkout, or clean was run in this step.
- `git status` shows many pre-existing modified, deleted, and untracked entries
  (for example `backend/phases/`, `backend/models/whisper/`, `backend/evaluation/reports/`).
  This step did not create them, but they were not individually audited here.
- Starting HEAD was not recorded at the step's start. No Git operations were run in
  this step, so ending HEAD `6baaa2a0773df66e5fb26814afbe67647fb43435` is also the
  HEAD for this step.

## 9. Remaining risks and next steps

1. **Remediate rows 3–8** (phase3d evaluation and upload integration, phase3e
   integration and validation, phase3f, phase4b). Each needs the same pattern as
   rows 1–2: cache clear, effective-settings check, and an engine-URL check, plus
   database-free tests. Confirm the `application_database_url()` fallback for each.
2. **Remediate the integration fixture** identity comparison (section 7).
3. **Audit `scripts/cleanup_smoke.py` and `scripts/cleanup_orphan_uploads.py`**
   for scope and target safety.
4. **Re-read the Step 1.5 master register** and map every row in this inventory to
   its E-ID, so the completeness claim can be checked against it.
5. **Re-audit cleanup behaviour** for rows 1–2 (not covered by this step).
6. Run PostgreSQL-backed verification only after the operator provides an isolated
   database. None was run here.
