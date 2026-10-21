# STEP 1.6X — Remaining Safety Blockers, Test Recovery, Cleanup Coverage, Independent Verification

Date: 2026-10-13
Owner: COORDINATOR (this run)
Predecessor evidence: `backend/architecture/UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md`
Status: **CONDITIONAL PASS** (see §15)

This document is append-only evidence. It records what was actually executed on this host,
what was read from source, and what remains blocked. Where it relies on a previous run's
result instead of a measurement made here, it says so.

---

## 1. Initial repository state and HEAD

| Item | Value |
| --- | --- |
| HEAD at start of run | `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| HEAD at end of run | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged; no commit, no reset) |
| Branch | `main` |
| Working-tree deletions | **295** (pre-existing; see below) |
| Interpreter used | `backend/venv/Scripts/python.exe` |

No `git reset`, `git clean`, `git restore`, checkout, revert or history rewrite was run.

**Pre-existing working-tree state (not caused by this task, deliberately not repaired).** The
working tree carries an in-progress restructure that predates this run: 295 deleted paths
(including `backend/evaluation/harness/evaluator.py`, `phase4d/**`, `phase4e/**`, `phase4f/**`
and the root-level `*_report.json` / `*_audit.txt` artifacts) plus a large modified set; the
package restructure that created `backend/evaluation/experiments/**` and the current
`backend/tests/**` layout is **untracked** relative to HEAD. Consequently `git diff` is not the
review artefact for most of this task's changes — 15 of the 16 changed paths are untracked, so
review was by reading the final files, and `git status --short` is the accurate change inventory
(§11). None of these deletions was caused by, or repaired by, this task.

## 2. Actual agent dispatch results

The named DocuMind specialists (`DATABASE_AGENT`, `SECURITY_AGENT`, `BACKEND_AGENT`,
`FILESYSTEM_AGENT`, `TEST_AGENT`, `EVALUATION_AGENT`, `VERIFIER`) exist in this repository as
markdown contracts under `agents/**`. They are **not registered runtime agents** in this
environment, and no runtime dispatch mechanism for them was found. They therefore have the
status **NOT EXECUTED** and no specialist is claimed to have reviewed anything.

What actually ran, and whose output is quoted or applied below:

| Dispatch | Kind | Count | Scope |
| --- | --- | --- | --- |
| Worker agents (`base3-fast-worker-deepseek-flash`) | generic | 12 | 6 test-module reclassifications; `cleanup_smoke.py`; `file_store.py`; 3 phase runners + artifact test; 2 safety-test files; 1 independent adversarial review |
| `code-searcher` | generic | 2 | deletion-helper call sites, artifact `write_text` sites, `upload_path` sources, test coverage of `file_store` |
| `file-picker` | generic | 0 | not needed; targets were known from the predecessor report |

The coordinator performed Workstream B (lifecycle inspection), the inline raw-SQL gate fix, the
reconciliation of the fan-out, all Tier A–C execution, and this report.

**Independent review.** One worker agent was dispatched as a *different* agent instance with an
explicitly adversarial, falsification-oriented brief and read-only instructions, and it reviewed
the landed artefacts without being given their authorship. Its findings and verdict are recorded
in §10 verbatim in substance. It is **not** the registered `VERIFIER`; the independent-review gate
is therefore satisfied by a second party but **not** by the named contract, and this is recorded
as an outstanding condition rather than as a pass.

## 3. Workstream A — the 24 previously reported failures

**Baseline provenance (honest statement).** The figure "645 passed, 24 failed, 1 skipped" is
**taken from the predecessor report**; it was not re-measured here, because reproducing it would
require reverting already-remediated safety code. What *was* verified here is structural: the six
`*_cleanup_scope.py` modules contain exactly **24** tests that either assert destructive cleanup
succeeded (10) or depend on it to reach their other assertions (14) — that is the 24.

**Common cause.** `evaluation.isolation.assert_cleanup_execution_authorized` refuses
unconditionally (`isolation.py:456-473`), so every test that calls a runner's
`cleanup_harness_rows` and asserts rows were deleted raises
`UnsafeEvaluationTarget: REFUSING <phase> … row cleanup`. The refusal is intentional and was
**not** relaxed.

**Resolution applied** (14 converted, 10 marked; none deleted, none blanket-skipped):

| Module | Converted to refusal + no-mutation assertions | Marked `@requires_disposable_database` |
| --- | --- | --- |
| `test_phase3d_cleanup_scope.py` | `test_unrelated_records_survive_untouched`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_owned_records_are_removed`, `test_ownership_is_the_key_not_the_document_name_or_chunk_text`, `test_cleaning_up_one_user_never_touches_a_second_one` |
| `test_phase3d_evaluation_cleanup_scope.py` | `test_other_experiments_survive_untouched`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_owned_rows_are_removed` |
| `test_phase3e_integration_cleanup_scope.py` | `test_other_experiments_survive_untouched`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_owned_rows_are_removed` |
| `test_phase3e_validation_cleanup_scope.py` | `test_other_experiments_survive_untouched`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_owned_rows_are_removed` |
| `test_phase3f_evaluation_cleanup_scope.py` | `test_an_empty_ownership_set_is_a_no_op`, `test_other_experiments_survive_untouched`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_both_owned_users_are_cleaned_in_one_sweep`, `test_owned_records_are_removed` |
| `test_phase4b_evaluation_cleanup_scope.py` | `test_an_empty_ownership_set_is_a_no_op`, `test_unrelated_users_and_their_records_survive`, `test_repeated_cleanup_is_safe_and_does_not_spread` | `test_both_owned_users_are_cleaned_in_one_sweep`, `test_owned_records_are_removed` |
| **Total** | **14** | **10** |

What a converted test does now: it calls the *same* helper with the *same* arguments inside
`pytest.raises(isolation.UnsafeEvaluationTarget, match="REFUSING")`, keeps every original
survivor assertion, and then asserts with the module's own counting helpers that nothing was
mutated — owner and unrelated rows still at their seeded counts, chunk-id **identity** sets
preserved, chat-message and reliability-log counts unchanged, ownership selection unchanged. The
real `evaluation.isolation` refusal is exercised; no gate is stubbed.

The blocked markers carry the exact unmet requirement
(`tests/fixtures/disposable_db.py:29-36`), so `pytest -rs` shows *why*: a verified disposable
PostgreSQL target plus a documented identity/privilege model. Bodies are preserved intact and
will run unchanged once that authority exists.

**Guard order for the empty-set cases.** `cleanup_harness_rows(db, user_ids=[])` refuses on every
phase because `assert_cleanup_execution_authorized` precedes the `if not ids: return` early exit.
Verified in source for all six runners
(`run_phase3d_evaluation.py:579/588`, `run_phase3d_upload_integration.py:149`,
`run_phase3e_validation.py:113/122`, `run_phase3e_integration.py:113/122`,
`run_phase3f_evaluation.py:750/759`, `run_phase4b_evaluation.py:730/739`).

**A verification-of-a-verification.** The first post-conversion run of the focused set produced
`1 failed, 121 passed, 10 skipped`: one converted test asserted that the ownership selection
still resolved **two** harness users, but that test seeds only one, so the correct expectation is
one. Fixed in `test_phase3d_evaluation_cleanup_scope.py` to
`set(owned_user_ids(...)) == {legacy.id}` — a stronger, order-independent assertion. This is
reported because the failure was *found by execution*, not by the worker that wrote it.

## 4. Filesystem deletion-path inventory (Workstream C)

| Path | Intended root | Root validation | Candidate validation | Link/reparse behaviour | Validation immediately before the effect? | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| `scripts/cleanup_orphan_uploads.py` | `settings.upload_path` | `cleanup_path.intended_root`, before archive or deletion | `validate_candidate` per file and per directory | `os.walk(followlinks=False)`; links reported, never candidates | yes (re-validated per candidate and again before the destructive phase) | `tests/unit/scripts/test_cleanup_orphan_uploads.py` |
| `scripts/cleanup_smoke.py` **(changed)** | `settings.upload_path` | `cleanup_path.intended_root` before any side effect, before the prompt, before any row mutation | `resolve_stored_path` + `cleanup_path.validate_candidate`, and again inside `delete_upload` | candidate, its resolved form and every ancestor below the root checked; links refused | yes | **new** `tests/unit/scripts/test_cleanup_smoke_safety.py` |
| `storage/file_store.delete_upload` **(changed)** | configured root, injectable via `root=` | root provenance left to operator config (documented, see §10) | `_resolved_within` + `_is_link_or_reparse_point` + `_has_link_ancestor` + `S_ISREG` | junction-aware via `st_file_attributes & 0x400` | yes | **new** `tests/unit/documents/test_file_store_deletion_safety.py` |
| `storage/file_store.cleanup_new_file` **(changed)** | same as above | — | now delegates to the guarded `delete_upload` | same | yes | covered via `delete_upload` tests |
| `evaluation/experiments/**` upload writes | runner-owned temp root | out of scope (writes, not deletions) | — | — | — | — |

## 5. Changes to cleanup and artifact-writing paths

**`scripts/cleanup_smoke.py`.** Added `resolve_stored_path(stored_path, root) -> Path | None`,
`delete_upload_files(root, stored_paths) -> (deleted, missing, refused)` and
`prune_user_dir(root, user_id) -> bool`. `cleanup()` now validates the root with
`cleanup_path.intended_root(settings.upload_path)` **before any filesystem side effect and before
the confirmation prompt**, prints a refusal and returns 1 without touching files or rows if the
root is unsafe. Every deletion goes through the guarded `delete_upload(resolved, root=root)`;
there is no bare `unlink()` left in the script. `shutil.rmtree(..., ignore_errors=True)` is
**gone** — `prune_user_dir` validates the directory, requires it to be empty, and reports
failure. The summary now reports deleted / already-absent / refused and returns 1 when anything
was refused, instead of claiming clean success.

**`storage/file_store.py`.** `delete_upload(stored_path, *, root=None) -> bool` now refuses
unless the candidate resolves inside the root, is not itself a symlink or reparse point, has no
link ancestor below the root, and `lstat()` reports a regular file. Every uncertainty returns
`False`; nothing escapes as an exception. The positional call in `documents/routes.py:632` is
unchanged. `cleanup_new_file` — previously an unguarded `unlink()` of whatever path it was handed
— now delegates to the guarded helper, closing the inconsistency the independent review raised.

**Evaluation artifacts (Workstream E).** The three phase runners now reserve and then write their
report through the central append-only mechanism:

| File | Was | Now |
| --- | --- | --- |
| `run_phase3d_evaluation.py` | `out.write_text(json.dumps(report, indent=2), encoding="utf-8")` | `RunOutput(Path("."))` → `reserve(report_name)` → `write_text(report_name, json.dumps(report, indent=2))`; `ArtifactExistsError` → refusal message + `return 2` |
| `run_phase3f_evaluation.py` | same pattern | same pattern |
| `run_phase4b_evaluation.py` | same pattern | same pattern |

The JSON content and key order are unchanged; `RunOutput.write_text` uses exclusive
`open(path, "x")`, so an existing report is refused rather than replaced, and a collision between
reserve and write is also refused. **Recorded behavioural change:** `RunOutput` writes with
`newline="\n"`, so on Windows the report's line endings change from CRLF to LF. That is
deliberate (it is what makes a recorded digest reproducible) but it *is* a byte-level change and
is not described as "byte-identical".

**Not converted — deferred with reason (§15, open item 1).** Direct report writers remain in
`evaluation/runner.py:406,410`, `evaluation/denominator_sensitivity.py:429,432`,
`evaluation/structure_eval.py:827,851`, `experiments/run_phase4c_diagnostics.py:585`,
`experiments/run_structure_confirmation.py:933,934,956,957`,
`experiments/run_structure_element_measurement.py:1908,1911,1914,1963`,
`experiments/run_structure_rrf_calibration.py:1142,1145,1172,1175`,
`experiments/synthesize_structure_discriminating.py:459,461`. Several write fixed publication
names into `REPORTS_DIR` where replacement is the documented intent; converting them is a design
decision per module, not a mechanical edit, and doing it blind would have changed report
semantics for measurement families that must stay comparable with prior runs. **This report
therefore does not claim that evaluation artifacts are append-only in general.**

## 6. Database lifecycle findings (Workstream B)

Verified by reading current source (not the predecessor report):

* `assert_disposal_authorized` (`isolation.py:377-413`), `assert_creation_authorized`
  (`:415-440`), `assert_cleanup_execution_authorized` (`:456-473`), `record_created_database`
  (`:366-372`) and `release_database_proof` (`:476-482`) each end in an unconditional refusal.
  `assert_engine_matches_target` (`:504-522`) only compares, and every caller pairs it with a
  refusing gate. No proof object, issuer marker, registry entry, environment variable, URL
  comparison or database name can authorize anything.
* **Every** destructive row-level site under `backend/evaluation/**` carries its own gate.
  Inventory: `run_dual_path_ablation.py:697,814,877-889` (gates `:622`, `:863-865`);
  `run_phase3d_evaluation.py:597-604` (`:580`); `run_phase3d_upload_integration.py:159-164`
  (`:150`) and the inline raw-SQL block (`:534`, added by this run);
  `run_phase3e_integration.py:130-137` (`:113`) and `:512-514` (`:169`);
  `run_phase3e_validation.py:130-137` (`:113`) and `:580-585` (`:169`);
  `run_phase3f_evaluation.py:768-775` (`:751`); `run_phase4b_evaluation.py:748-755` (`:731`);
  `run_structure_confirmation.py:741,780`; `run_structure_element_measurement.py:1675,1730`;
  `run_structure_rrf_calibration.py:993,1064`; `run_table_evidence_measurement.py:486,646`.
  No `drop_database`, `drop_all` or `TRUNCATE` call exists anywhere in the package.
* **Gap found and closed by this run.** The inline raw-`DELETE FROM` cleanup block in
  `run_phase3d_upload_integration.py` (reliability logs, chunks, documents, users for two
  extra users) was the one destructive site that relied only on the runner-level disposal gate
  rather than carrying a function-level gate. It now calls
  `assert_cleanup_execution_authorized(db, operation="Phase 3D upload inline raw-SQL row
  cleanup")` before its first statement, and
  `tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` asserts by source order that
  the gate precedes every inline `DELETE FROM`. It is unreachable today because the runner-level
  gate refuses first; the change removes a latent bypass for the day authorization exists.
* **Outside the evaluation lifecycle boundary** (application/operational provisioning, not
  evaluation targets): `scripts/setup_db.py` (subprocess `alembic upgrade head` against the
  application DSN), `migrations/env.py`, `main.py` startup migrations, `scripts/create_test_user.py`
  (additive only), and `scripts/db_check.py` (read-only `SELECT`, but it still executes
  `asyncio.run(main())` at import — unchanged, previously reported).

**Requirements that remain unmet for a real lifecycle authority** (what a future enabling change
must supply): an authority external to the process and to caller-supplied objects; verification of
the *live connection's* actual target identity (not a URL comparison); verification of the
connecting role's effective privileges; a disposable-target predicate the operator cannot forge by
editing an environment variable; issuance and closure of a bound lifecycle with durable evidence;
and independent approval of that mechanism before any destructive execution.

**PostgreSQL remains NO-GO.**

## 7. Race-condition analysis and residual risks (Workstream D)

Present mitigations, all verified in source: the root is established once and held; the root is
re-validated immediately before the destructive phase; every candidate is validated immediately
before its own `unlink()`/`rmdir()`; traversal does not follow links; links and reparse points are
never candidates and never deleted; archives are written and CRC-verified before a single file is
deleted, and an archive inside the upload root or over an existing file is refused; dry run is the
default and `--delete` plus confirmation is required; refusals produce non-zero exit codes rather
than silent success.

**Residual risk that this run did not eliminate.** Validating a path and then acting on it remain
separate operations, so a concurrent process that can rewrite the upload tree can still win the
window between check and use. This is a documented limitation, not a fixed defect. Closing it
needs handle-bound deletion: on POSIX, `os.open(parent, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)` followed
by `os.unlink(name, dir_fd=fd)` / `os.rmdir(name, dir_fd=fd)` with `os.lstat(name, dir_fd=fd)`
checks; on Windows, Python exposes no equivalent primitive that both opens relative to a directory
handle and unlinks without following a reparse point, so no reviewed implementation can claim
race-free deletion on this platform. That POSIX approach was **identified but not implemented**:
it cannot be exercised on the supported host (Windows, where the suite runs), and shipping
unexecuted destructive code is not evidence. Further, in `file_store.py` the lexical
link-ancestor walk is reached via `os.path.abspath`, which collapses `..` before the walk, so the
walk can be skipped for a path containing `..`; containment is still enforced on the *resolved*
path, so no escape was constructible, but the two checks are not equivalent and this is recorded
as residual.

**Unattended destructive cleanup remains NO-GO** (§14).

## 8. Exact test commands and outcomes

All commands run from `backend/` with `venv/Scripts/python.exe`. `PIPESTATUS[0]` was captured, so
the exit status is the tested command's own.

| # | Command | Result | Exit |
| --- | --- | --- | --- |
| 1 | `python -m compileall -q scripts storage evaluation tests` | no errors | 0 |
| 2 | `python -m pytest -q -rs tests/unit/scripts/test_cleanup_smoke_safety.py tests/unit/documents/test_file_store_deletion_safety.py tests/unit/evaluation/test_runner_artifact_append_only.py tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` | **51 passed, 3 skipped** | 0 |
| 3 | `python -m pytest -q -rs tests/unit/evaluation` (after the inline-SQL gate) | **641 passed, 10 skipped** | 0 |
| 4 | `python -m pytest -q -rs` over the six `*_cleanup_scope.py` modules + `test_function_cleanup_authorization.py` | **122 passed, 10 skipped, 0 failed** | 0 |
| 5 | `python -m pytest -q -rs -rf tests/unit` (final, after every edit) | **1204 passed, 14 skipped, 0 failed** | 0 |

Rows 2 and 5 were re-measured after the final repairs (`storage/file_store.py` `cleanup_new_file`, the strengthened phase3f assertion); the re-run of row 4 reports exactly the 10 expected block lines and no failure lines, and row 5 — which contains every module in rows 2–4 — exits 0 with zero failures, which is the decisive post-repair evidence.

Skip accounting for the final run — **14 = 10 + 4**:

* **10** are the new explicit `BLOCKED` markers (the "asserts destructive success" tests), each
  printing its unmet requirement under `-rs`.
* **4** are platform capability skips, each naming the reason: `WinError 1314 A required
  privilege is not held by the client` prevents creating file symlinks on this host. Three belong
  to the new tests (`test_cleanup_smoke_safety.py:74`, `:325`,
  `test_file_store_deletion_safety.py:51`) and one is pre-existing
  (`test_cleanup_orphan_uploads.py:145`). **The file-symlink refusal case is therefore not
  exercised on this host** — a real coverage limitation, reported rather than hidden.

No test was deleted, no assertion weakened to pass, and no safety gate was relaxed.

## 9. Protected-artifact and upload-manifest checks (Tier A)

| Check | Result |
| --- | --- |
| Frozen benchmark `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches the expected digest** |
| Real upload tree, files / bytes | **1212 / 7 386 232** |
| Newest mtime under `uploads/`, files modified today | **2026-10-09T21:08:11**, **0** |
| Real upload cleanup sweep | **not run** |
| Secret-shaped literals (`sk-…`, `AKIA…`, `postgresql+asyncpg://user:pass@`) | 4 pre-existing files, one hit each, **none of them touched by this task**: `config.py`, `evaluation/experiments/run_dual_path_ablation.py`, `evaluation/experiments/run_phase3d_upload_integration.py`, `tests/fixtures/e2e_config.py`. Locations and counts only; no value was printed. `config.py`'s hit is the documented insecure-default sentinel that must never be used in production. |
| `.env` / credential files read | **no** |

## 10. Independent review findings

The independent reviewer (a separate agent instance, adversarial brief, read-only) returned
**CONDITIONAL PASS**. In substance:

* **Confirmed:** `cleanup_smoke` cannot delete outside the validated root — absolute, `..`,
  sibling-prefix (`uploads` vs `uploads-old`), UNC, drive-relative, directory, trailing-separator,
  empty/whitespace, and link-shaped candidates were all attempted and all refuse or resolve as
  absent; root validation precedes any side effect and any row mutation; `ignore_errors=True` is
  gone.
* **Confirmed:** the application delete flow is not broken. `save_upload` writes under
  `settings.upload_path` and `delete_document` reads the same pair; **no fixture redirects
  `settings.upload_dir`** (a claim in the review brief to the contrary was itself false and is
  corrected here), so no harness can defeat the guard, and a refusal degrades to an orphan file,
  never to data loss.
* **Confirmed:** every gate refuses, and every destructive database path under
  `backend/evaluation/**` carries its own gate; the operational/application paths listed in §6 are
  correctly classified as outside that boundary.
* **Confirmed:** the 14 converted tests prove non-mutation with real row counts and chunk-id
  identity, not merely "it raised"; exactly 10 markers exist; no gate was stubbed.
* **Partially confirmed:** the artifact claim. The three converted runners are append-only and
  content-preserving, but 8 further modules still write reports directly, and the Windows
  line-ending change is real. The reviewer's requirement — that this report must not describe
  evaluation artifacts as append-only in general — is honoured in §5.
* **Findings acted on in this run:** (a) `cleanup_new_file` was an unguarded sibling deletion
  helper → now delegates to the guarded `delete_upload`; (b) `test_phase3f_…:266` held a
  decorative assertion (`assert {chunk.id for chunk in legacy_chunks}`, which proves nothing about
  the database) → replaced with a read-back comparison of the persisted chunk ids against the
  seeded ids; (c) the symlinked-root policy difference between the helper and the operational
  policy → now documented in the source as a deliberate scope decision rather than as drift.
* **Findings recorded, not fixed:** the residual TOCTOU window (§7); the 8 remaining direct
  report writers (§5); the symlinked-root behaviour itself, which is left as a deliberate,
  documented difference because the root is operator configuration and refusing a symlinked
  `UPLOAD_DIR` would break a legitimate deployment.

## 11. Changed-file inventory

| Path | Change |
| --- | --- |
| `scripts/cleanup_smoke.py` | root + per-candidate validation, guarded deletion, validated prune, refusal reporting |
| `storage/file_store.py` | containment guard for `delete_upload`; `cleanup_new_file` delegates to it; documented policy scope |
| `evaluation/experiments/run_phase3d_evaluation.py` | report write via `RunOutput` (append-only) |
| `evaluation/experiments/run_phase3f_evaluation.py` | report write via `RunOutput` (append-only) |
| `evaluation/experiments/run_phase4b_evaluation.py` | report write via `RunOutput` (append-only) |
| `evaluation/experiments/run_phase3d_upload_integration.py` | function-level gate on the inline raw-SQL cleanup block |
| `tests/fixtures/disposable_db.py` | **new** — the shared blocked-test policy and marker |
| `tests/unit/evaluation/test_phase3d_cleanup_scope.py` | 2 converted, 3 marked |
| `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` | 2 converted, 1 marked, 1 stale surface assertion updated to the new write mechanism |
| `tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py` | 2 converted, 1 marked |
| `tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py` | 2 converted, 1 marked |
| `tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py` | 3 converted, 2 marked, 1 decorative assertion strengthened |
| `tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py` | 3 converted, 2 marked |
| `tests/unit/evaluation/test_runner_artifact_append_only.py` | **new** — append-only writer contract + runner source assertions |
| `tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` | **new** — the inline raw-SQL gate must precede every inline delete |
| `tests/unit/scripts/test_cleanup_smoke_safety.py` | **new** — containment, refusal-before-side-effect, prune and tripwire tests |
| `tests/unit/documents/test_file_store_deletion_safety.py` | **new** — `delete_upload` containment and default-root tests |
| `architecture/STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md` | **new** — this report |

No pre-existing report was overwritten, and no unrelated file was edited.

## 12. Final Git state

HEAD unchanged at `6baaa2a0773df66e5fb26814afbe67647fb43435`. The 295 pre-existing working-tree
deletions and the pre-existing modified set (§1) are untouched. This task's 16 changed files are
present exactly as listed in §11: one tracked file modified (`storage/file_store.py` — which also
carried pre-existing modifications), the rest untracked/new. Nothing was committed, pushed,
staged or restored, and the frozen benchmark, `.env`, the real upload tree and all pre-existing
reports are unchanged.

## 13. Explicit PostgreSQL readiness

**POSTGRESQL VERIFICATION: NO-GO — NOT RUN.** No PostgreSQL test, migration, connection, row
mutation or database lifecycle operation was executed. Blockers: no enforceable,
connection-bound lifecycle authority exists; live-connection target identity and effective role
privileges are not verifiable by any mechanism present in the repository; no verified disposable
target plus identity/privilege model has been approved; and no independent approval of such a
mechanism has been given. The refusal gates remain fail-closed and unchanged.

## 14. Explicit destructive-cleanup readiness

**UNATTENDED DESTRUCTIVE CLEANUP: NO-GO.** No cleanup script was run against the real uploads
tree, and no archive or deletion was performed anywhere outside `tmp_path`. Blockers: the
check-then-use window (§7) cannot be closed with the primitives available on the supported
platform, so race-free unattended deletion cannot be claimed; and independent approval of the
mitigation has not been given. The scripts remain dry-run by default and require explicit
`--delete` plus confirmation; their guards are stricter than before this run, not looser.

## 15. Closure table

| # | In-scope finding | Classification | Evidence |
| --- | --- | --- | --- |
| 1 | 24 failing cleanup-scope tests | **FIXED (classification)** — 14 converted, 10 explicitly blocked | §3; commands 4 and 5 |
| 2 | `cleanup_smoke.py` deleted files with no root or candidate validation | **FIXED** | §5; `test_cleanup_smoke_safety.py` |
| 3 | `cleanup_smoke.py` `rmtree(ignore_errors=True)` hid prune failures | **FIXED** — validated `rmdir`, failures reported, non-zero exit | §5; `prune_user_dir` tests |
| 4 | `delete_upload` had no independent root guard | **FIXED** | §5; `test_file_store_deletion_safety.py` |
| 5 | `cleanup_new_file` was an unguarded sibling deletion helper | **FIXED** (found by independent review) | §5, §10 |
| 6 | Inline raw-SQL cleanup was not function-level gated | **FIXED** (found by this run) | §6; `test_phase3d_upload_inline_sql_guard.py` |
| 7 | Three phase runners silently overwrote fixed-name reports | **FIXED** | §5; `test_runner_artifact_append_only.py` |
| 8 | 8 further modules still write reports directly | **DEFERRED** — per-module design decision; the append-only claim is narrowed accordingly | §5 |
| 9 | TOCTOU between validation and `unlink`/`rmdir` | **BLOCKED BY PLATFORM** — documented; POSIX `dir_fd`/`O_NOFOLLOW` approach identified, not implemented | §7 |
| 10 | Symlinked upload root accepted by the application helper, refused by the operational policy | **DEFERRED (documented as deliberate)** | §5, §10 |
| 11 | Database lifecycle authorization and live connection identity | **BLOCKED BY INFRASTRUCTURE** — requirements enumerated | §6, §13 |
| 12 | File-symlink refusal cases | **NOT EXERCISED ON THIS HOST** — `WinError 1314`, 4 named skips | §8 |
| 13 | Frozen benchmark integrity | **CONFIRMED UNCHANGED** | §9 |
| 14 | Real upload tree untouched | **CONFIRMED** — 0 files modified today | §9 |
| 15 | Named specialist review (`DATABASE_AGENT`…`VERIFIER`) | **NOT EXECUTED** — not registered runtime agents; one independent adversarial agent review performed instead | §2, §10 |

## 16. Verdict and conditions

**CONDITIONAL PASS.**

Implementation and testing are sound: the focused safety suites and the entire database-free unit
suite pass with zero failures, every destructive database entry point is gated by a gate that
refuses unconditionally, the filesystem deletion paths now share one enforceable containment
policy, the 24 previously failing tests are individually classified with the destructive-success
expectations preserved and marked rather than weakened or deleted, and no real upload, database
or protected artefact was touched.

The conditions that prevent a full PASS are: (1) the evaluation-artifact overwrite bypass is
closed for three runners but remains in 8 further modules, so the report does not claim general
append-only protection; (2) the file-symlink refusal cases are not exercised on this host; (3) the
TOCTOU residual is unmitigated on Windows and unattended destructive cleanup stays NO-GO;
(4) PostgreSQL verification is NO-GO and the lifecycle authority remains unimplemented; and
(5) independent review was performed by a separate agent instance but **not** by the registered
`VERIFIER` contract, so the named independent-verification gate is outstanding.
