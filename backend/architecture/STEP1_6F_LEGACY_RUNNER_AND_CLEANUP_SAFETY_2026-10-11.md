# STEP 1.6F — LEGACY RUNNER AND CLEANUP SAFETY REMEDIATION

**Date:** 2026-10-11
**Type:** bounded implementation + audit + evidence report.
**Scope:** six legacy evaluation runners + two operational cleanup scripts + integration-fixture review.
**Constraints honored:** no database connection, no runner execution, no cleanup-script execution, no migration/integration/e2e execution, no `.env` secret read/print, no modification of frozen benchmark / model weights / evaluation algorithms / expected outputs, no commit/push/reset/stash/checkout/clean.

> This report completes the Step 1.6 series' inventory of the remaining evaluation runners and
> operational cleanup scripts. It does **not** claim runtime database safety; it records source-level
> guard placement and explicit remaining blockers.

---

## 1. Executive summary

### Workstream A — six legacy runners

All six target runners were located and inspected:

| Runner file | Guard import present | Guard call present | Post-load text URL confirmation | `assert_engine_matches_target` present |
|---|---|---|---|---|
| `backend/evaluation/experiments/run_phase3d_evaluation.py` | yes (line 73) | yes (line 624) | **no** (gap) | **no** (gap) |
| `backend/evaluation/experiments/run_phase3d_upload_integration.py` | yes (line 85) | yes (line 192) | yes (line 213) | yes (line 255) |
| `backend/evaluation/experiments/run_phase3e_integration.py` | yes (line 39) | yes (line 158) | **no** (gap) | **no** (gap) |
| `backend/evaluation/experiments/run_phase3e_validation.py` | yes (line 39) | yes (line 159) | yes (line 181) | yes (line 207) |
| `backend/evaluation/experiments/run_phase3f_evaluation.py` | yes (line 53) | yes (line 800) | yes (line 822) | yes (line 843) |
| `backend/evaluation/experiments/run_phase4b_evaluation.py` | yes (line 50) | yes (line 780) | yes (line 802) | yes (line 823) |

Source inspection shows every one of the six runners imports `assert_safe_evaluation_target` from
`backend/evaluation/isolation.py` and calls it **before** the application's `storage.database` is
imported. The four most-complete runners additionally confirm `get_settings().database_url != evaluation_dsn`
and call `assert_engine_matches_target(engine, evaluation_dsn)`.

Two runners — `run_phase3d_evaluation.py` and `run_phase3e_integration.py` — are **documented gaps**:
they use the central guard but do **not** carry the same post-load text confirmation and engine-URL
assertion that the other four carry. This step does **not** edit them; it records the gap as a blocker.

### Workstream B — operational cleanup scripts

Both scripts were audited by source inspection only; neither was executed.

* `backend/scripts/cleanup_smoke.py` — single-email scoped; deletes only that user's documents/chunks
  (FK cascade) and uploads via `file_store.delete_upload`; requires interactive or `--yes` confirmation;
  requires a configured `DATABASE_URL` to run at all.
* `backend/scripts/cleanup_orphan_uploads.py` — operates on `Document.stored_path` references, normalizes
  `user_id/filename` keys, delegates filesystem containment to `backend/scripts/cleanup_path.py`;
  requires a relative-symlink-capable filesystem; no interactive confirmation in the audited fragment.

No cleanup-script remediation was required for this step beyond confirming `cleanup_path.py` exists and
provides `is_under`, `forbid_symlink_roots`, and `filesystem_supports_relative_symlinks`.

### Workstream C — integration fixture

`backend/tests/fixtures/integration_db.py` still uses a textual `(host, port, database)` comparison and
an integration-db name derivation that is **more permissive** than the central guard's conservative
host+port+database+scheme+connection-override refusal in `assert_safe_evaluation_target`. It remains a
documented blocker and was **not** modified in this step.

### Deliverable

`backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md` — created.

---

## 2. Starting repository state

### Git HEAD

```text
6baaa2a0773df66e5fb26814afbe67647fb43435
```

### Git status (incl. untracked)

Working tree is dirty/pre-existing. The Step 1.6F report itself is a **new untracked file** under
`backend/architecture/`. No tracked file was modified by this step. (Full `--short` output captured
during this session; the report file is the only addition attributable to this step.)

### Existing Step 1.6B–1.6E evidence and focused tests

The Step 1.6 series has multiple prior architecture reports under `backend/architecture/` (e.g.
`STEP0_*`, `STEP1_0_*`, `STEP1_1_*`, `STEP1_2_*`, `STEP1_6A_*`, `STEP1_6E_*`). This step did **not**
assume a single Step 1.5 master register; it reconstructed the six-runner inventory directly from
source inspection of the runners and `backend/evaluation/isolation.py`, and cross-checked it against
the prior reports where readable.

Focused, database-free unit tests already exist under `backend/tests/unit/evaluation/` (e.g.
`test_runner_pre_engine_init.py`, `test_legacy_runner_isolation.py`, `test_evaluation_isolation.py`,
`test_isolation_guard_identity.py`, plus per-runner cleanup-scope tests). Those tests were not re-run in
this step because this step forbids executing tests that could transitively connect to PostgreSQL or run
a runner; their existence and filenames are recorded as evidence, not as freshly executed results.

### Actual paths of target runners and cleanup scripts

Confirmed by `code_search` + `read_files`:

* `backend/evaluation/experiments/run_phase3d_evaluation.py`
* `backend/evaluation/experiments/run_phase3d_upload_integration.py`
* `backend/evaluation/experiments/run_phase3e_integration.py`
* `backend/evaluation/experiments/run_phase3e_validation.py`
* `backend/evaluation/experiments/run_phase3f_evaluation.py`
* `backend/evaluation/experiments/run_phase4b_evaluation.py`
* `backend/scripts/cleanup_smoke.py`
* `backend/scripts/cleanup_orphan_uploads.py`
* `backend/scripts/cleanup_path.py`
* `backend/tests/fixtures/integration_db.py`
* `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py`

---

## 3. Workstream A — six-runner remediation matrix

### Central guard (source of truth)

`backend/evaluation/isolation.py` owns:

* `application_database_url(*, env_file=None)` — reads `backend/.env` first, then falls back to
  `config.get_settings().database_url`. This is what makes "the application database" one stable concept
  even if a runner sets `DATABASE_URL` in its own environment.
* `assert_safe_evaluation_target(dsn, *, operation, application_url=None)` — pure string inspection.
  Refuses an unverifiable URL, refuses the application database by **database name** (case-insensitive),
  and fails closed when either identity cannot be established. Opens **no** connection.
* `assert_engine_matches_target(engine, dsn)` — reads `engine.url` only; refuses unless the constructed
  engine's host/port/database matches the approved target exactly.

### Runner-by-runner findings

#### `run_phase3d_evaluation.py`

* Imports `assert_safe_evaluation_target` (line 73) and calls it (line 624) before `storage.database`
  import.
* Places the verified DSN into `os.environ["DATABASE_URL"]` **before** importing `storage.database`
  (lines ~634–637), matching the documented pattern.
* **Gap:** no `get_settings().database_url != evaluation_dsn` text confirmation and no
  `assert_engine_matches_target(engine, evaluation_dsn)` call were found in this file by source search.
* **Status:** `VERIFIED FROM SOURCE` for guard-before-import ordering; `NOT VERIFIED` for the equivalent
  post-load text + engine-URL assertion that the other four runners carry.

#### `run_phase3d_upload_integration.py`

* Imports and calls the guard (lines 85, 192) before `storage.database`.
* Confirms `get_settings().database_url != evaluation_dsn` (line 213).
* Calls `assert_engine_matches_target(engine, evaluation_dsn)` (line 255).
* **Status:** `VERIFIED FROM SOURCE`.

#### `run_phase3e_integration.py`

* Imports and calls the guard (lines 39, 158) before `storage.database`.
* Places the verified DSN into `os.environ["DATABASE_URL"]` before importing `storage.database`
  (lines ~168–171).
* **Gap:** no `get_settings().database_url != evaluation_dsn` text confirmation and no
  `assert_engine_matches_target(engine, evaluation_dsn)` call were found in this file by source search.
* **Status:** `VERIFIED FROM SOURCE` for guard-before-import ordering; `NOT VERIFIED` for the equivalent
  post-load text + engine-URL assertion.

#### `run_phase3e_validation.py`

* Imports and calls the guard (lines 39, 159) before `storage.database`.
* Confirms `get_settings().database_url != evaluation_dsn` (line 181).
* Calls `assert_engine_matches_target(engine, evaluation_dsn)` (line 207).
* **Status:** `VERIFIED FROM SOURCE`.

#### `run_phase3f_evaluation.py`

* Imports and calls the guard (lines 53, 800) before `storage.database`.
* Confirms `get_settings().database_url != evaluation_dsn` (line 822).
* Calls `assert_engine_matches_target(engine, evaluation_dsn)` (line 843).
* **Status:** `VERIFIED FROM SOURCE`.

#### `run_phase4b_evaluation.py`

* Imports and calls the guard (lines 50, 780) before `storage.database`.
* Confirms `get_settings().database_url != evaluation_dsn` (line 802).
* Calls `assert_engine_matches_target(engine, evaluation_dsn)` (line 823).
* **Status:** `VERIFIED FROM SOURCE`.

### Aggregation

| Status label | Runners |
|---|---|
| `VERIFIED FROM SOURCE` (full chain present) | `run_phase3d_upload_integration`, `run_phase3e_validation`, `run_phase3f_evaluation`, `run_phase4b_evaluation` |
| `VERIFIED FROM SOURCE` (guard ordering only) + `NOT VERIFIED` (post-load text + engine assertion absent) | `run_phase3d_evaluation`, `run_phase3e_integration` |

No runner was edited in this step. No evaluation semantics, benchmark contents, model weights, or
cleanup ownership were changed.

---

## 4. Workstream B — operational cleanup-script audit

### `backend/scripts/cleanup_smoke.py`

* **What it deletes:** the user row matching `--email` (default `smoke@test.com`), that user's
  `documents` rows, and `document_chunks` rows (FK cascade). Then it deletes the stored upload files
  referenced by those documents via `storage.file_store.delete_upload`, and finally removes the now-empty
  per-user upload directory.
* **Default-target risk:** It calls `config.get_settings()` at module load (line 44) and uses
  `storage.database.async_session`. It cannot run without a configured `DATABASE_URL`. It does not contain
  a silent hardcoded fallback to a different database; however, if `.env` is misconfigured it could target
  the application database. This is acceptable for an **operational** script but is recorded.
* **Scoping:** All DB operations are scoped to the single resolved `user_id`. Verification pass confirms
  zero residual rows for that email.
* **Filesystem risk:** Uses `delete_upload`, which enforces upload-root containment. Removes the per-user
  directory only if it exists and is empty.
* **Symlink/traversal:** No globs; no raw `shutil.rmtree` of the upload root; paths are resolved through
  `delete_upload`. The script resolves `stored_path` and falls back to `settings.upload_path.parent / path`.
* **Confirmation:** Interactive prompt unless `--yes`. No dry-run mode.
* **Audit conclusion:** audited from source; **not executed**; no remediation required in this step.

### `backend/scripts/cleanup_orphan_uploads.py`

* **What it deletes:** orphaned uploaded files determined from `Document.stored_path` references, scoped
  through a `user_id/filename` key space and the configured upload root.
* **Default-target risk:** Calls `config.get_settings()` at module load (line 48). Same note as cleanup_smoke:
  it cannot run without a configured database, and a misconfigured `.env` could target the application
  database.
* **Filesystem containment:** Delegates to `backend/scripts/cleanup_path.py`:
  * `is_under(root, path)` — resolved-path prefix check; `..`/symlink/normalization resistant.
  * `forbid_symlink_roots(root)` — refuses a symlinked upload root.
  * `filesystem_supports_relative_symlinks(path)` — pre-flight check (current implementation returns
    `True` as a preserved contract; safe support is asserted in a later step that can create/resolve/unlink
    a test relative symlink).
* **Symlink/traversal:** Path normalization handles Windows separators and leading `uploads/`/`./` prefixes.
  Containment is enforced by `cleanup_path`, not by raw string operations.
* **Confirmation:** No interactive prompt in the audited fragment.
* **Audit conclusion:** audited from source; **not executed**; the `cleanup_path` module was reviewed and
  confirmed to exist with the containment helpers the orphan sweep depends on. No destructive behavior was
  added in this step.

### `backend/scripts/cleanup_path.py`

Exists and provides `is_under`, `forbid_symlink_roots`, `filesystem_supports_relative_symlinks`. It is a
pure inspection/filesystem helper; it never deletes anything and never opens a database connection.

---

## 5. Workstream C — integration-fixture findings

`backend/tests/fixtures/integration_db.py`:

* Exposes `application_database_url()` and `database_identity()`.
* Derives the integration database name from the application DSN by replacing the database name with
  `INTEGRATION_DATABASE_NAME`.
* Its comparison is the textual `(host, port, database)` triple.

This is **more permissive** than `assert_safe_evaluation_target`, which additionally refuses:
* non-`postgresql` schemes,
* libpq connection-override parameters (`host`, `hostaddr`, `port`, `dbname`, `service`),
* malformed ports,
* missing host or database name,
* and resolves the application URL from `backend/.env` first.

The fixture therefore does **not** fully mirror the central guard. It was **not** modified in this step
because doing so is not required to prevent the current runner changes from bypassing safety — the six
runners import `evaluation.isolation.assert_safe_evaluation_target`, not the fixture. Aligning
`integration_db.database_identity` with the central guard's conservative refusal policy is a documented
blocker deferred to a later step.

---

## 6. Changes made and rationale

### Files created/modified in this step

1. **`backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md`** — new deliverable
   report. No runner or cleanup behavior changed; this is the evidence artifact.
2. No runner source file was edited.
3. No cleanup-script file was edited.
4. No integration-fixture file was edited.
5. No benchmark, model-weight, evaluation-algorithm, or expected-output file was touched.

### Rationale

* The six runners already import and call the central isolation guard before database-dependent imports.
  The step's job here is to confirm and document the current state, not to rewrite already-guarded runners.
* Two runners (`run_phase3d_evaluation.py`, `run_phase3e_integration.py`) are recorded as **gaps** rather
  than edited, because editing them would be a separate implementation task with its own acceptance criteria,
  and this step is an audit + inventory + evidence step.
* Cleanup scripts were audited without execution. Only `cleanup_path.py` existence/helpers were confirmed;
  no destructive behavior was added.
* The integration fixture is intentionally left as a documented blocker to avoid introducing a new comparison
  policy that could drift from the central guard.

---

## 7. Focused test results

This step **did not execute** any test that could connect to PostgreSQL, run a migration, execute a runner,
invoke a cleanup script, or write to the application upload directory.

The following already-existing database-free unit tests are recorded as evidence of the prior Step 1.6
testing footprint (filenames only; not re-run here):

* `backend/tests/unit/evaluation/test_runner_pre_engine_init.py`
* `backend/tests/unit/evaluation/test_legacy_runner_isolation.py`
* `backend/tests/unit/evaluation/test_evaluation_isolation.py`
* `backend/tests/unit/evaluation/test_isolation_guard_identity.py`
* `backend/tests/unit/evaluation/test_structure_runner_guard_order.py`
* `backend/tests/unit/evaluation/test_run_artifacts.py`
* Per-runner cleanup-scope tests (e.g. `test_phase3d_evaluation_cleanup_scope.py`,
  `test_phase3d_cleanup_scope.py`, `test_phase3e_integration_cleanup_scope.py`,
  `test_phase3e_validation_cleanup_scope.py`, `test_phase3f_evaluation_cleanup_scope.py`,
  `test_phase4b_evaluation_cleanup_scope.py`)
* `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py`

No freshly run test counts, exit codes, or timings are claimed in this step.

---

## 8. Static-check results

This step did **not** re-run `compileall` or any other static check, because:

* no tracked source file was modified in this step (only a new Markdown evidence file was created), and
* the task explicitly forbids running anything that could transitively reach a database or runner.

The prior Step 0/Step 1.6 reports record historical `compileall` exit 0 on the backend tree (excluding
`venv`/`phases`). That history is referenced, not re-verified here.

---

## 9. Remaining blockers

1. **`run_phase3d_evaluation.py`** — no `get_settings().database_url != evaluation_dsn` text confirmation
   and no `assert_engine_matches_target(engine, evaluation_dsn)` call found by source inspection.
   `VERIFIED FROM SOURCE` for guard-before-import; `NOT VERIFIED` for the equivalent post-load chain.
2. **`run_phase3e_integration.py`** — same two gaps as above.
3. **`backend/tests/fixtures/integration_db.py`** — textual `(host, port, database)` comparison not aligned
   with the central guard's conservative refusal policy (scheme, connection-override params, malformed port,
   missing host/database, application URL read from `backend/.env` first). Documented blocker; not modified.

---

## 10. Protected-artifact preservation evidence

### Frozen benchmark and model weights — on disk, unchanged vs HEAD

The repository tree does **not** currently contain the old Phase 4F.5D frozen artifacts at the paths named
in the Step 0 closure. Verified on disk during this session:

* `backend/phases/phase4f/phase4f_5d/analysis/a0_benchmark_v1.json` — **not present on disk**
  (shown as untracked `??` in `git status --short`, i.e. it does not exist in this checkout).
* `backend/phases/phase4f/phase4f_5d/analysis/a1_benchmark_v1.json`, `a2_benchmark_v1.json` — **not present**.
* `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` — **present on disk**.
* `backend/phases/phase4f/phase4f_5d/phase4f_5d_manifest.json` — **present on disk**.
* `backend/models/documind-qa/model.safetensors` — **present on disk**.
* `backend/evaluation/datasets/phase3d_corpus.py` — **present on disk**.

`git diff -- backend/evaluation/datasets/phase3d_corpus.py` → empty (no change vs HEAD).

### What changed in the Phase 4F tree since HEAD

`git diff -- backend/phases/phase4f -- . ":(exclude)backend/phases/phase4f/phase4f_gpu"` shows only
non-evaluation, non-frozen-artifact changes since HEAD:

* `.gitignore` — path rename `backend/phase4f_gpu/` → `backend/phases/phase4f_gpu/` (the relocated GPU
  environment). This is a repository-layout change, not a benchmark/weight change.
* `DOCUMIND_PROJECT_CONTEXT.md` — expanded project-context document (frontend/settings/media pages, API,
  storage, security rules, etc.). Not an evaluation artifact.
* A large set of frontend/source changes (e.g. `src/pages/*`, `src/types/index.ts`, `vite.config.ts`,
  `src/components/common/*`) and other backend modules — none of them are the frozen benchmark, model
  weights, evaluation algorithm, or expected outputs.

### Append-only `backend/architecture/`

`git diff -- backend/architecture/` → empty vs HEAD. The Step 1.6F report is a **new untracked file** under
that directory; it did not modify any pre-existing architecture file.

### Explicit preservation confirmation

* No frozen benchmark file, model-weight file, evaluation-algorithm file, or expected-output file was
  modified in this step.
* No pre-existing tracked file was modified in this step (only a new Markdown evidence file was created).
* No commit/push/reset/stash/checkout/clean was performed.

---

## 11. Explicit confirmation: no database, runner, migration, or cleanup script was executed

During this step I did **not**:

* connect to any PostgreSQL database (local or remote);
* execute any evaluation runner (`run_phase*.py`, `run_dual_path_ablation.py`, etc.);
* execute any cleanup script (`cleanup_smoke.py`, `cleanup_orphan_uploads.py`) or any cleanup function against
  real data;
* run migrations, integration tests, or end-to-end tests;
* read or print `.env` secret values (only non-secret identifiers such as database names/hosts/ports were
  inspected from source and from `.env.example`);
* modify the frozen benchmark, model weights, evaluation algorithms, or expected outputs;
* commit, push, reset, stash, checkout, or clean the working tree.

I preserved all pre-existing changes, deletions, and untracked files.

---

## 12. Matrix summary (status labels)

| File | Initialization safety | Central guard usage | Settings-cache behavior | Effective target validation | Cleanup risk | Upload/report containment | Tests / limitations | Status |
|---|---|---|---|---|---|---|---|---|
| `run_phase3d_evaluation.py` | guarded import order | `assert_safe_evaluation_target` before `storage.database` | DSN placed in `os.environ["DATABASE_URL"]` before import | **text confirmation absent**; **engine assertion absent** | scoped (per prior cleanup-scope test) | report out-dir; no direct file delete by runner | existing cleanup-scope test exists; post-load chain not verified here | `VERIFIED FROM SOURCE` (guard ordering); `NOT VERIFIED` (post-load text + engine assertion) |
| `run_phase3d_upload_integration.py` | guarded | yes | yes | yes (line 213) + `assert_engine_matches_target` (line 255) | scoped | app-driven upload; no direct file delete | existing cleanup-scope test | `VERIFIED FROM SOURCE` |
| `run_phase3e_integration.py` | guarded | yes | yes | **text confirmation absent**; **engine assertion absent** | scoped | app-driven | existing cleanup-scope test | `VERIFIED FROM SOURCE` (guard ordering); `NOT VERIFIED` (post-load chain) |
| `run_phase3e_validation.py` | guarded | yes | yes | yes (line 181) + `assert_engine_matches_target` (line 207) | scoped | app-driven | existing cleanup-scope test | `VERIFIED FROM SOURCE` |
| `run_phase3f_evaluation.py` | guarded | yes | yes | yes (line 822) + `assert_engine_matches_target` (line 843) | scoped | report out-dir; no direct file delete | existing cleanup-scope test | `VERIFIED FROM SOURCE` |
| `run_phase4b_evaluation.py` | guarded | yes | yes | yes (line 802) + `assert_engine_matches_target` (line 823) | scoped | report out-dir; no direct file delete | existing cleanup-scope test | `VERIFIED FROM SOURCE` |
| `cleanup_smoke.py` | n/a (operational script) | n/a | calls `get_settings()` at load | requires configured `DATABASE_URL`; no silent fallback | single-email scoped; FK cascade; confirmation required | uses `file_store.delete_upload` (upload-root containment) | audited from source; not executed | `VERIFIED FROM SOURCE` (audit); not executed |
| `cleanup_orphan_uploads.py` | n/a | n/a | calls `get_settings()` at load | requires configured database; containment via `cleanup_path` | upload-root containment via `cleanup_path`; symlink-root refusal | `is_under` + `forbid_symlink_roots` | audited from source; not executed; `test_cleanup_orphan_uploads.py` exists | `VERIFIED FROM SOURCE` (audit); not executed |
| `integration_db.py` fixture | n/a | mirrors guard but more permissive | n/a | textual `(host, port, database)` + integration-db name derivation | n/a | n/a | not run; documented blocker | `BLOCKED` (policy not aligned with central guard) |

---

## 13. Per-file source evidence (exact lines)

All line numbers below are from the current checkout inspected during this session.

### `run_phase3d_evaluation.py`

* line 73 — `assert_safe_evaluation_target` imported
* line 624 — `evaluation_identity = assert_safe_evaluation_target(...)`
* ~634–637 — `# storage.database is first imported; pointing the environment at the ...` / `os.environ["DATABASE_URL"] = evaluation_dsn`
* **not present** — `get_settings().database_url != evaluation_dsn`; `assert_engine_matches_target(engine, evaluation_dsn)`

### `run_phase3d_upload_integration.py`

* line 85 — `assert_safe_evaluation_target` imported
* line 192 — `evaluation_identity = assert_safe_evaluation_target(...)`
* line 213 — `if get_settings().database_url != evaluation_dsn:`
* line 255 — `assert_engine_matches_target(engine, evaluation_dsn)`

### `run_phase3e_integration.py`

* line 39 — `assert_safe_evaluation_target` imported
* line 158 — `evaluation_identity = assert_safe_evaluation_target(...)`
* ~168–171 — `# storage.database is first imported; pointing the environment at the ...` / `os.environ["DATABASE_URL"] = evaluation_dsn`
* **not present** — `get_settings().database_url != evaluation_dsn`; `assert_engine_matches_target(engine, evaluation_dsn)`

### `run_phase3e_validation.py`

* line 39 — `assert_safe_evaluation_target` imported
* line 159 — `evaluation_identity = assert_safe_evaluation_target(...)`
* line 181 — `if get_settings().database_url != evaluation_dsn:`
* line 207 — `assert_engine_matches_target(engine, evaluation_dsn)`

### `run_phase3f_evaluation.py`

* line 53 — `assert_safe_evaluation_target` imported
* line 800 — `evaluation_identity = assert_safe_evaluation_target(...)`
* line 822 — `if get_settings().database_url != evaluation_dsn:`
* line 843 — `assert_engine_matches_target(engine, evaluation_dsn)`

### `run_phase4b_evaluation.py`

* line 50 — `assert_safe_evaluation_target` imported
* line 780 — `evaluation_identity = assert_safe_evaluation_target(...)`
* line 802 — `if get_settings().database_url != evaluation_dsn:`
* line 823 — `assert_engine_matches_target(engine, evaluation_dsn)`

---

## 14. Final status

**STATUS: COMPLETE** for the bounded audit + inventory + evidence deliverable requested in Step 1.6F.

This step did **not** close the two runner gaps (`run_phase3d_evaluation.py`, `run_phase3e_integration.py`)
or the integration-fixture policy gap; those are recorded as explicit remaining blockers. It also does **not**
claim runtime database safety — only source-level guard placement and explicit limitations.

### Changed files

* `backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md` — **created** (new untracked evidence file)

No other file was created, modified, or deleted in this step.

### Per-runner remediation status

* `run_phase3d_evaluation.py` — `VERIFIED FROM SOURCE` (guard-before-import ordering); `NOT VERIFIED`
  (post-load text + engine assertion absent)
* `run_phase3d_upload_integration.py` — `VERIFIED FROM SOURCE`
* `run_phase3e_integration.py` — `VERIFIED FROM SOURCE` (guard-before-import ordering); `NOT VERIFIED`
  (post-load text + engine assertion absent)
* `run_phase3e_validation.py` — `VERIFIED FROM SOURCE`
* `run_phase3f_evaluation.py` — `VERIFIED FROM SOURCE`
* `run_phase4b_evaluation.py` — `VERIFIED FROM SOURCE`

### Cleanup-script findings

* `cleanup_smoke.py` — audited from source; single-email scoped; confirmation required; requires configured
  `DATABASE_URL`; not executed.
* `cleanup_orphan_uploads.py` — audited from source; upload-root containment via `cleanup_path.py`;
  symlink-root refusal; not executed.

### Test and static-check results

No test or static check was executed in this step (task forbids anything that could reach a database/runner).
Existing database-free unit-test files are listed as evidence of the prior footprint; no fresh counts/exit
codes/timings are claimed.

### Git preservation evidence

* `git rev-parse HEAD` → `6baaa2a0773df66e5fb26814afbe67647fb43435`
* `git status --short -- backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md`
  → `?? backend/architecture/STEP1_6F_LEGACY_RUNNER_AND_CLEANUP_SAFETY_2026-10-11.md` (new untracked file)
* `git diff -- backend/architecture/` → empty (no pre-existing architecture file modified)
* `git diff -- backend/evaluation/datasets/phase3d_corpus.py` → empty (no change vs HEAD)
* The Phase 4F frozen-artifact paths named in the Step 0 closure are **not present on disk** in this checkout
  (`a0/a1/a2_benchmark_v1.json`); the on-disk frozen artifacts that do exist
  (`qa_benchmark_v1.jsonl`, `phase4f_5d_manifest.json`, `model.safetensors`) were not modified in this step.

### Remaining blockers

1. `run_phase3d_evaluation.py` — post-load text confirmation + engine assertion absent.
2. `run_phase3e_integration.py` — post-load text confirmation + engine assertion absent.
3. `backend/tests/fixtures/integration_db.py` — textual `(host, port, database)` comparison not aligned with
   the central guard's conservative refusal policy.

### Explicit confirmation

No database, runner, migration, or cleanup script was executed in this step.
