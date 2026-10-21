# STEP 1.6Y — Evaluation Artifact Integrity, Cross-Platform Filesystem Safety, Independent Verification

Date: 2026-10-13
Owner: COORDINATOR (this run)
Predecessors: `STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md`, `UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md`
Verdict: **CONDITIONAL PASS** (§16)

Append-only evidence. Every status below carries evidence; where a claim rests on a previous run's
measurement rather than one taken here, it says so.

---

## 1. Initial repository state and HEAD

| Item | Value |
| --- | --- |
| HEAD at start | `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| HEAD at end | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged; nothing committed, staged, pushed or restored) |
| Branch | `main` |
| Interpreter | `backend/venv/Scripts/python.exe` (Windows, `MINGW64_NT-10.0-26300`) |
| Pre-existing working-tree state | 295 deletions plus a large modified set, carried over from before Step 1.6X; the current `evaluation/**` and `tests/**` layout is **untracked** relative to HEAD, so `git status --short` — not `git diff` — is the change inventory (§14) |

No `git reset`, `git clean`, `git restore`, checkout, blanket revert or history rewrite was run.
No `.env` or credential file was read. No real cleanup sweep, migration or database mutation was
performed. The only writes outside `tmp_path` were `__pycache__` bytecode from the compilation
check of §10 (`compileall`), which is a cache, not evidence.

## 2. Previous findings reconciled against current source

| Step 1.6X finding | Still true? | Current evidence |
| --- | --- | --- |
| Eight evaluation modules write reports directly | **Yes — exactly 8 confirmed** | Reinspected each; the eight are listed in §4. A ninth writer candidate was *not* hidden: the eight-module list was right, but this run's own Tier A scan showed my initial fan-out had converted only 7 of them (`run_structure_rrf_calibration.py` was unassigned), which the coordinator then closed |
| Four filesystem symlink tests skipped (no privilege) | **Yes — still 4 skips** | `WinError 1314`; the skips are legitimate. Mitigated, not removed: junction-based tests now *execute* the reparse branch (§7) |
| Ten tests blocked pending a disposable database | **Yes — unchanged** | 10 explicit `BLOCKED` markers, body preserved, reason printed under `-rs` |
| Remaining check-then-use race | **Yes — unchanged** | §6. No mitigation implemented, because none is testable on the supported platform |
| PostgreSQL verification and destructive cleanup NO-GO | **Yes — unchanged** | §9, §15 |
| Named specialist roles not registered runtime agents | **Yes — unchanged** | §3 |
| VERIFIER gate unsatisfied | **Yes — unchanged** | §3, §13 |
| *(new)* `replace=True` did not actually replace | **Defect in this round's own code — fixed** | Found by worker 4 within minutes of the central helper landing; §5 |
| *(new)* `write_evidence(replace=True)` temp-name clobber | **Defect in this round's own code — fixed** | Found by the independent reviewer (R1); §6 |

## 3. Actual agent dispatch results

The named contracts (`BACKEND_AGENT`, `SECURITY_AGENT`, `FILESYSTEM_AGENT`, `TEST_AGENT`,
`EVALUATION_AGENT`, `DATABASE_AGENT`, `VERIFIER`) remain **markdown contracts, not registered
runtime agents**: the runtime registry exposes only generic helpers (`file-picker`,
`code-searcher`, worker agents). They are therefore **NOT EXECUTED** for this step, and no
specialist is claimed to have reviewed anything.

Dispatched this round:

| Role (contract) | Actual runtime agent | Assignment | Completed | Evidence |
| --- | --- | --- | --- | --- |
| BACKEND_AGENT | worker agent #1 | phase4c + synthesize writers | Yes | report names 3 files; §5 |
| BACKEND_AGENT | worker agent #2 | structure_confirmation + element_measurement | Yes | 3 files; §5 |
| BACKEND_AGENT | worker agent #3 | `evaluation/runner.py` + its tests | Yes | 3 files; §5 |
| BACKEND_AGENT | worker agent #4 | denominator_sensitivity + structure_eval + their tests | Yes | 4 files; §5 |
| FILESYSTEM_AGENT / TEST_AGENT | worker agent #5 | reparse-point and race tests; `cleanup_path` audit | Yes | 1 new test file, `cleanup_path.py` unchanged; §7 |
| COORDINATOR | coordinator | `write_evidence`, `..` refusal, the 8th writer, integration, all test execution, this report | Yes | §§5–6, 10 |
| VERIFIER | worker agent #6 (adversarial, read-only) | independent review of the final source | Yes, with a stated caveat | §13 |

The reviewer itself recorded that it is **not** organisationally independent (same model family as
the author) and that the registered `VERIFIER` contract did not execute. That caveat is accepted
here: the independent-review gate is *partially* satisfied (a different agent instance, adversarial
brief, source-level verification) and **not** satisfied by the named contract.

## 4. The eight-module artifact-writer inventory

| Module | Artifact | Write path before | Overwrite risk | Required action (done) | Test |
| --- | --- | --- | --- | --- | --- |
| `evaluation/runner.py` (`out_dir is None` branch) | `<name>.json`, `<name>.md` in `evaluation/reports/` | `Path.write_text`, replacing a same-named report | **High — documented historical replacement** | `write_evidence` for both files, two-destination collision pre-flight, explicit `replace=False` keyword | `test_writer_collision_runner.py`; updated `test_runner_report_output.py` |
| `evaluation/denominator_sensitivity.py` | `<name>.json`, `<name>.md` | `Path.write_text` | **High (fixed name)** | `write_evidence` + pre-flight + `replace` keyword + `--replace` CLI | `test_writer_collision_library…` (via updated `test_denominator_sensitivity.py`) |
| `evaluation/structure_eval.py` | `<name>.json`, `<name>.md` | `Path.write_text` | **High (fixed name)** | same | updated `test_structure_eval.py` |
| `experiments/run_phase4c_diagnostics.py` | `phase4c_failure_matrix.json` (CWD) | `Path.write_text` | **High (fixed name in CWD)** | `write_evidence` + `--replace`; new `save_results()` seam; `__main__` now sets a real exit code | `test_writer_collision_diagnostics_and_synthesize.py` |
| `experiments/synthesize_structure_discriminating.py` | `structure_discriminating_analysis.json`, `…_ablation_report.md` | `Path.write_text` (default `REPORTS_DIR`) | **High** | `write_evidence` for both, `replace` keyword + `--replace` | same file |
| `experiments/run_structure_confirmation.py` | `structure_confirmation.json`, `…_report.md` | `Path.write_text` into `REPORTS_DIR` | **High** | pre-flight both + `write_evidence`, `--replace`, refusal exits 2 | `test_writer_collision_structure_runners.py` |
| `experiments/run_structure_element_measurement.py` | `…_control/_treatment/_analysis.json` | `Path.write_text` into `REPORTS_DIR` | **High** | pre-flight all three + `write_evidence`, `--replace`, refusal exits 2 | same file |
| `experiments/run_structure_rrf_calibration.py` | `structure_rrf_calibration.json`, `…_report.md` | `Path.write_text` into `REPORTS_DIR` | **High** | pre-flight both + `write_evidence`, `--replace`, refusal exits 2 | `test_writer_collision_rrf_calibration.py` |

**Explicitly out of scope and left unchanged** (documented dispositions, not oversights):

* The `tempfile.mkdtemp` `--smoke` branches in three structure runners and in
  `run_structure_confirmation.py`/`run_structure_element_measurement.py`/`run_structure_rrf_calibration.py`:
  caller-scoped **scratch** output, never recorded evidence, deliberately mutable.
* `evaluation/datasets/**` (heading/phase3d/phase4b corpora): they write generated *corpus
  documents* into caller-provided or temp paths, not evaluation evidence.
* The three phase runners converted in Step 1.6X (`run_phase3d_evaluation.py`,
  `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`): already append-only via `RunOutput`
  and re-verified unchanged.

No fixed-path direct write remains in `evaluation/**`: the only surviving `write_text` calls in
that tree are the corpus writers, the scratch smoke branches, and `RunOutput.write_text` itself.

## 5. Changes and tests for each confirmed bypass

**The shared mechanism (coordinator).** `evaluation/artifacts.py` gained
`write_evidence(path, text, *, replace=False)`: refuses an existing destination with
`ArtifactExistsError` (message names the path and the `replace=True` remedy), refuses a file that
appears between the check and the exclusive `open(path, "x")`, creates parents, and writes with
`encoding="utf-8"`, `newline="\n"` — the same rule as `RunOutput.write_text`, deliberately not a
second abstraction. `replace=True` is the explicit, never-inferred opt-in for a deliberate
re-publication, and it never truncates the evidence it replaces: the bytes go to a uniquely named
sibling (`<name>.<pid>.<hex>.tmp`) and are moved into place with `os.replace`.

Two defects in this round's own code were found and fixed before the final test run:

1. **`replace=True` did not replace.** The first version still used the exclusive-create branch, so
   every deliberate re-publication raised `ArtifactExistsError` — reported by worker 4, which
   declined to work around it in a file it did not own, and fixed by the coordinator with the
   temp-file swap (§2 row 8).
2. **Fixed temp name.** The reviewer showed that a fixed `<name>.tmp` is shared by concurrent
   re-publications and would clobber an unrelated file of that name; it is now unique per process
   (§13, R1).

**Behaviour change, stated plainly:** the default for all eight writers changed from silent
replacement to refusal, with a non-zero exit (or a raised `ArtifactExistsError` for the library
writers) and an actionable message. A deliberate re-publication remains possible and visible via
`--replace` / `replace=True`. Report **content** is unchanged at every site: the same
`json.dumps(..., indent=2, sort_keys=True)` / `canonical(...)` / markdown renderer expressions are
used, and the tests assert the written bytes against those exact expressions. The only byte-level
difference remains the `newline="\n"` normalisation recorded in Step 1.6X.

**Three existing test files were updated, not weakened** (verified by the independent reviewer at
`test_runner_report_output.py:196-231`, `test_denominator_sensitivity.py:163-186`,
`test_structure_eval.py:243-262`): each keeps its original assertions (including the
determinism/byte-equality expectations) and *adds* a refusal assertion plus a byte-preservation
assertion, with the deliberate repeat passing the explicit opt-in.

**No-false-success property:** every refusal path prints a `REFUSING …` block and returns 2 before
any success line; verified by source assertions in the new tests.

## 6. Filesystem race analysis

| Threat | Platform | Operation protected | Test | Remaining limitation |
| --- | --- | --- | --- | --- |
| Candidate replaced by a link between validation and use | Windows + POSIX | `file_store.delete_upload`, `cleanup_smoke.delete_upload_files` | `test_reparse_points_and_race_safety.py` (junction substitution; refusal reported as `(0, 0, 1)`) | The specific substitution is refused; the *general* TOCTOU window is unchanged |
| Root replaced/redirected after validation | Windows + POSIX | `cleanup_path.intended_root` / the pre-destructive re-validation | same file (root swapped for a junction → refused on the next gate run) | A swap *between* the last check and the syscall is still possible in principle |
| Directory-pruning race | Windows + POSIX | `prune_user_dir` / prune loop | prune-refusal tests (1.6X) | Same window |
| Archive-destination substitution | Windows + POSIX | `_archive_orphans` | existing orphan tests | Same window |
| `..` normalization hiding a link ancestor | Windows + POSIX | `file_store.delete_upload` | §8; new tests | **Closed for the app helper** (explicit `..` refusal); audited as NOT REPRODUCED for `cleanup_path` (§8) |
| Concurrent re-publication sharing one temp file | any | `write_evidence(replace=True)` | reviewer finding R1 → fixed to a unique temp name | — |

**Not implemented, deliberately:** directory-handle-relative deletion
(`os.open(parent, O_DIRECTORY|O_NOFOLLOW)` + `os.unlink(name, dir_fd=…)`) is the identified POSIX
mitigation, but it cannot be exercised on this host (Windows, where the suite runs) and the task
forbids shipping an untestable mitigation whose properties are unproven. **The residual
check-then-use window therefore remains OPEN between validation and the `unlink()`/`rmdir()`
syscall**, and unattended destructive cleanup stays **NO-GO**.

## 7. Cross-platform test results

| Environment | Available? | Result |
| --- | --- | --- |
| Windows (this host) | Yes | Reparse-point branch now **exercised**: `test_reparse_points_and_race_safety.py` creates real NTFS **junctions** via `cmd /c mklink /J`, which need no elevation → **22 passed, 0 skipped** |
| Windows symlink privilege | **No** (`WinError 1314`) | The 4 file/dir-*symlink* cases still skip, each naming the OS error; they are **not** counted as passes |
| POSIX runner | **No** | `wsl.exe` reports "Windows Subsystem for Linux is not installed"; `uname -s` is `MINGW64_NT-10.0-26300`, i.e. Git Bash on Windows, not POSIX |
| Repository CI | **None** | No `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `.circleci/config.yml` or `Jenkinsfile` exists, so there is no existing CI architecture in which to add a POSIX job |

**Tier D (POSIX filesystem verification): NOT VERIFIED — no POSIX environment exists in this
repository or on this host.** Exact external requirement to close it: a POSIX runner (Linux CI
job or a Linux developer host) with `python -m pytest tests/unit/scripts
tests/unit/documents` executed there, so that the symlink-creation branches run instead of
skipping. Adding a CI job was **not** done: there is no CI configuration to extend, and inventing
one was not asked for and could not be verified from here.

Requirement 4 of the task ("Windows junctions and reparse points") moved from *unexercised* to
*exercised and passing* on this host. Requirements 1–3 (symlinked root, symlinked candidate,
directory symlink) remain split: the junction form runs, the true-symlink form skips with a reason.

### 7b. The 20 required test cases, one by one

| # | Required case | Status | Evidence (test) |
| --- | --- | --- | --- |
| 1 | Symlinked upload roots | **PASS** (junction form) | `test_junction_as_upload_root_is_refused`, `test_forbid_symlink_roots_rejects_linked_root`, `test_symlinked_upload_root_is_refused` |
| 2 | Symlinked file candidates | **PARTIAL — SKIPPED with reason** | junction form passes (`test_file_reached_through_a_junction_is_refused_by_delete_upload`); the true-symlink cases skip: `test_file_link_inside_root_is_refused_and_its_target_survives`, `test_symlink_inside_root_is_refused_and_target_survives`, `test_link_capability_is_reported_not_silently_skipped` — all reason `WinError 1314` |
| 3 | Directory symlinks | **PASS** (junction form) | `TestDirectorySymlinksPortable` (3 tests) |
| 4 | Windows junctions and reparse points | **PASS** | `TestWindowsReparsePoints` (7 tests, real `mklink /J`) |
| 5 | Traversal attempts | **PASS** | `test_traversal_out_of_root_is_refused`, `test_traversal_out_of_the_root_is_refused`, `test_is_under_rejects_traversal_out_of_root`, `test_dotdot_candidate_that_resolves_outside_is_refused` |
| 6 | Adjacent paths sharing a textual prefix | **PASS** | `test_prefix_sibling_directory_is_refused`, `test_sibling_sharing_a_string_prefix_is_refused`, `test_is_under_rejects_prefix_sibling` |
| 7 | Missing roots | **PASS** | `test_missing_root_is_refused_by_the_guard`, `test_missing_directory_is_refused` |
| 8 | Non-regular file candidates | **PASS** | `test_directory_candidate_is_refused`, `test_directory_at_the_candidate_path_is_refused`, `test_validate_candidate_requires_the_expected_type`, `test_validated_file_replaced_by_a_directory_is_refused` |
| 9 | Archive destination inside the protected root | **PASS** | `test_archive_inside_upload_root_is_rejected` (exit 3, nothing deleted) |
| 10 | Existing archive destinations | **PASS** | `test_existing_archive_path_deletes_nothing` |
| 11 | Archive-write failure | **PASS — added during this final check** | `test_archive_write_failure_deletes_nothing` (the failure propagates loudly and nothing is deleted) |
| 12 | Archive-verification failure | **PASS** | `test_archive_verification_failure_deletes_nothing`; positive control `test_verified_archive_is_written_before_deletion` |
| 13 | Deletion refusal before side effects | **PASS** | `test_every_refusal_mode_leaves_the_outside_tree_byte_identical`, `test_root_is_validated_before_any_filesystem_side_effect` |
| 14 | Directory-pruning refusal | **PASS** | `TestPruneUserDir` (4 tests), `test_linked_directory_is_not_a_prune_candidate` |
| 15 | Dry-run behaviour | **PASS** | `test_dry_run_deletes_nothing` |
| 16 | Explicit deletion authorization | **PASS** | `test_refusing_the_prompt_deletes_nothing` (and the `assume_yes=True` paths) |
| 17 | Partial failure reporting | **PASS** | `test_mixed_batch_reports_deleted_missing_and_refused` (returns `(2, 1, 1)`), `test_substituted_candidate_is_refused_and_reported` |
| 18 | Repeated cleanup attempts | **PASS** | `test_repeated_cleanup_is_safe_and_does_not_spread` in all six `*_cleanup_scope.py` modules |
| 19 | Root replacement or redirection | **PASS** (the specific substitution) | `test_replaced_root_is_refused_by_the_root_gate`, `test_root_gate_refuses_a_root_swapped_after_validation` |
| 20 | Candidate replacement | **PASS** (the specific substitution) | `test_junction_replacing_a_regular_file_is_refused`, `test_candidate_swapped_for_a_link_after_validation_is_refused` |

Cases 19–20 prove the *substitution performed* is refused; they do **not** prove race-freedom (§6).
Case 2 is the only one whose essential branch is not exercised on this host, and it is reported as a
skip with its OS error, never as a pass.

## 8. Shared deletion-path verification

* `storage/file_store.delete_upload` — containment on the resolved path, link/reparse-point refusal
  for the candidate and every ancestor below the root, `S_ISREG` requirement, all failures returning
  `False`; **new**: any candidate containing a `..` part is refused *before* those checks, because
  `os.path.abspath` collapses `..` textually and is not symlink-aware. `save_upload` produces
  `uploads/<user_id>/<uuid>.<ext>` and `documents/routes.py` records exactly that, so no legitimate
  upload contains `..` — the refusal cannot break the application delete flow (verified by the
  reviewer, `storage/file_store.py:166-172`).
* `storage/file_store.cleanup_new_file` — delegates to the guarded helper (Step 1.6X); it can no
  longer bypass it.
* `scripts/cleanup_smoke.py` — root validated before any side effect, per-candidate validation, no
  bare `unlink`, validated prune, refusals reported with a non-zero exit (Step 1.6X, re-verified).
* `scripts/cleanup_path.py` — **unchanged this round**: the `..`/normalization audit reported
  **NOT REPRODUCED** as a defect, and the independent reviewer also failed to construct a
  counterexample. Attempted falsifications: a lexically-inside/resolved-outside candidate (refused
  by the resolved containment check), a link inside the root (found by the lexical walk), `..`
  stepping out of the root (refused by the fail-closed branch). `validate_candidate` requires
  containment **and** not-a-link **and** no link ancestor **and** the expected `lstat` type.

## 9. Database lifecycle readiness and infrastructure requirements

Reinspected; **nothing material has changed.** `assert_disposal_authorized`
(`isolation.py:377-413`), `assert_creation_authorized` (`:415-440`),
`assert_cleanup_execution_authorized` (`:456-473`), `record_created_database` (`:366-372`) and
`release_database_proof` (`:476-482`) each end in an unconditional refusal; no new bypass was
introduced by this round (no lifecycle code was touched).

Requirements to authorize PostgreSQL integration, stated as an infrastructure contract:

1. **External authority** — issuance/closure of a bound lifecycle by something outside the process
   and outside caller-supplied objects (no in-process registry, no boolean, no proof dataclass).
2. **Live connection identity** — the *connected* target verified (server-side identity such as the
   connected database's OID/`current_database()` over the actual connection), not a URL comparison.
3. **Effective privileges** — proof that the connecting role can, and may, drop and recreate only
   the disposable database (e.g. a role whose grants are limited to the disposable name).
4. **Non-forgeable disposable predicate** — an operator-supplied decision that ordinary
   configuration values, environment variables or a test-looking database name cannot satisfy.
5. **Durable evidence** — the successful-creation evidence that `record_created_database`
   currently refuses to fabricate.
6. **Independent approval** of the above before any destructive execution.

Until all six exist: the 10 blocked tests stay blocked, and **POSTGRESQL VERIFICATION: NO-GO**.

## 10. Exact test commands and results

All run from `backend/`; each exit status is the tested command's own (`PIPESTATUS[0]` captured
after any output filtering).

| # | Command | Result | Exit |
| --- | --- | --- | --- |
| 1 | `python -m compileall -q evaluation tests scripts storage` | clean | 0 |
| 2 | `python -m pytest -q` on `tests/unit/evaluation tests/unit/scripts tests/unit/documents` | **903 passed, 14 skipped, 0 failed** | 0 |
| 3 | `python -m pytest -q` on the four filesystem safety modules | **83 passed, 4 skipped** (all 4 are the named symlink-privilege skips) | 0 |
| 4 | `python -m pytest -q` on `test_reparse_points_and_race_safety.py` | **22 passed, 0 skipped** (junctions execute) | 0 |
| 5 | `python -m pytest -q -k "write_evidence or collision or artifact" tests/unit` | **92 passed, 1203 deselected** | 0 |
| 6 | `python -m pytest -q` on `test_writer_collision_rrf_calibration.py` | **6 passed** | 0 |
| 7 | `python -m pytest -q -rs -rf tests/unit` (final, after every code edit) | **1282 passed, 14 skipped, 0 failed** | 0 |

Skip accounting for row 7 — **14 = 10 + 4**: ten are the explicit `BLOCKED` database markers; four
are the platform symlink-privilege skips (`test_cleanup_smoke_safety.py:74`, `:325`,
`test_file_store_deletion_safety.py:51`, `test_cleanup_orphan_uploads.py:145`), each printing
`WinError 1314`. **No skipped test is counted as passed.** No test was deleted, no assertion
weakened, and no safety gate relaxed to make anything pass.

Note on one self-inflicted failure, reported rather than hidden: the first version of
`test_writer_collision_rrf_calibration.py::test_no_bare_write_text_remains_at_the_publication_site`
asserted `.write_text(` was absent from `main()`, which wrongly flagged the legitimate
`tempfile.mkdtemp` scratch writes. It was made **precise** (only `write_text` lines referencing
`REPORTS_DIR` fail, and each surviving line must be `out_dir`-based) rather than deleted or
loosened; it now passes. The reviewer independently assessed that direction as correct.

## 11. Protected-artifact integrity

| Artifact | Check | Result |
| --- | --- | --- |
| `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches the expected digest** |
| `architecture/UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` | SHA-256 prefix | `66b53544ebffd2d0`, unchanged; not opened for writing |
| `architecture/STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md` | SHA-256 prefix | `b0cbefef7d9cab14`, unchanged; not overwritten (this is a new file) |
| Secret-shaped literals (`sk-…`, `AKIA…`, `postgresql+asyncpg://user:pass@`) | locations and counts only | 6 pre-existing files, one hit each: `config.py` (the documented insecure-default sentinel), `evaluation/experiments/run_dual_path_ablation.py`, `evaluation/experiments/run_phase3d_upload_integration.py`, `tests/fixtures/e2e_config.py`, `tests/unit/evaluation/test_disposable_database_authorization.py`, `tests/unit/evaluation/test_disposal_authorization_contract.py`. **None is a file changed by this step**, and no value was printed. |
| `.env` / credentials | read? | **No** |

## 12. Upload-tree manifest comparison

| Metric | Start of Step 1.6X | End of Step 1.6Y | Change |
| --- | --- | --- | --- |
| Files under `backend/uploads/` | 1212 | **1212** | none |
| Total bytes | 7 386 232 | **7 386 232** | none |
| Files modified today | 0 | **0** | none |

Real cleanup: **not run**. All destructive filesystem tests were confined to `tmp_path`; the
existing real-uploads tripwire fixture in `test_cleanup_smoke_safety.py` is intact.

The real publication directory `evaluation/reports/` was also checked: 51 files, newest real
artifact `2026-10-06`, and the only path with today's timestamp is
`__pycache__/__init__.cpython-311.pyc` (bytecode created by the compilation check of §10). **No test
or runner wrote a report there**, and no `*.tmp` file exists anywhere under `backend/`
(0 matches), which is the expected state of the new temp-file swap.

## 13. Independent reviewer findings

The reviewer ran as a separate agent instance with an adversarial, read-only brief and inspected
the source directly. Its own caveats are recorded in §3. Findings:

| # | Finding | Severity | Status |
| --- | --- | --- | --- |
| R1 | `write_evidence(replace=True)` opened a **fixed** `<name>.tmp`, so a leftover temp from a crashed run was silently overwritten and two concurrent re-publications shared one temp name | low, real | **FIXED by the coordinator** — the temp name now carries the pid and a random suffix; the docstring records that only a hard crash can leave an orphan temp |
| R2 | An `os.replace` failure (e.g. cross-device `EXDEV`) propagates as a bare `OSError`, which the eight callers catch only as `ArtifactExistsError` | low, informational | **DOCUMENTED, not changed** — propagating is fail-closed (loud non-zero end, never a false success); the docstring now states it |
| — | `is_under`'s `".." in relative.parts` test is vestigial because `resolve()` output cannot contain `..` | informational | **NOT REPRODUCED as a defect**; containment is carried by `relative_to`, and the behaviour is fail-closed either way. Not touched |
| — | The temporary-vs-destination swap is not atomic with respect to a *reader* | informational | **ACCEPTED** — `os.replace` is atomic on both supported platforms for same-directory moves; the destination is never partially written |

Per-claim verdicts returned by the reviewer: CLAIM 1 (`write_evidence`) **CONFIRMED**; CLAIM 2 (nine
writers) **CONFIRMED**; CLAIM 3 (existing tests strengthened) **CONFIRMED**; CLAIM 4 (new tests are
real evidence) **CONFIRMED**; CLAIM 5 (`..` refusal cannot break a legitimate upload) **CONFIRMED**;
CLAIM 6 (`cleanup_path` NOT REPRODUCED) **CONFIRMED — the reviewer also could not construct a
counterexample**. Overall reviewer verdict: **CONDITIONAL PASS**, with the conditions being no
execution on its side, same-model-family (not organisationally independent), POSIX/symlink coverage
unexercised, and R1/R2.

## 14. Changed-file inventory and final Git state

| Path | Change |
| --- | --- |
| `evaluation/artifacts.py` | **new** `write_evidence` (append-only by default, unique-temp `replace`) |
| `evaluation/runner.py` | historical `out_dir is None` path is append-only; two-destination pre-flight; `replace` keyword |
| `evaluation/denominator_sensitivity.py` | `write_evidence`; pre-flight; `replace` keyword; `--replace` |
| `evaluation/structure_eval.py` | same |
| `evaluation/experiments/run_phase4c_diagnostics.py` | `save_results()` seam + `write_evidence`; `--replace`; real exit code |
| `evaluation/experiments/synthesize_structure_discriminating.py` | `write_evidence` for both artifacts; `replace` keyword; `--replace` |
| `evaluation/experiments/run_structure_confirmation.py` | pre-flight + `write_evidence`; `--replace`; refusal exits 2 |
| `evaluation/experiments/run_structure_element_measurement.py` | pre-flight all three + `write_evidence`; `--replace`; refusal exits 2 |
| `evaluation/experiments/run_structure_rrf_calibration.py` | pre-flight both + `write_evidence`; `--replace`; refusal exits 2 |
| `storage/file_store.py` | explicit `..` refusal before the containment/link checks |
| `tests/unit/evaluation/test_runner_report_output.py`, `test_denominator_sensitivity.py`, `test_structure_eval.py` | updated to the explicit opt-in; strengthened, not diluted |
| `tests/unit/evaluation/test_writer_collision_{diagnostics_and_synthesize,structure_runners,runner,rrf_calibration}.py` | **new** collision/append-only regression tests |
| `tests/unit/scripts/test_reparse_points_and_race_safety.py` | **new** junction, symlink-guarded, `..`-audit and substitution tests |
| `tests/unit/scripts/test_cleanup_orphan_uploads.py` | added the missing case-11 test (`test_archive_write_failure_deletes_nothing`); no existing test changed |
| `architecture/STEP1_6Y_ARTIFACT_AND_FILESYSTEM_VERIFICATION_2026-10-13.md` | **new** — this report |

HEAD unchanged at `6baaa2a0773df66e5fb26814afbe67647fb43435`. The 295 pre-existing deletions and the
pre-existing modified set are untouched; nothing was committed, staged, pushed or restored; no
historical report was overwritten.

## 15. Closure status for every in-scope finding

| # | Finding | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `evaluation/runner.py` historical path replaced same-named reports | **FIXED** | §5; `test_writer_collision_runner.py`; updated `test_runner_report_output.py` |
| 2 | `denominator_sensitivity.write_report` overwrote fixed names | **FIXED** | §4–5; updated `test_denominator_sensitivity.py` |
| 3 | `structure_eval.write_report` overwrote fixed names | **FIXED** | §4–5; updated `test_structure_eval.py` |
| 4 | `run_phase4c_diagnostics.py` overwrote `phase4c_failure_matrix.json` | **FIXED** | §4; `test_writer_collision_diagnostics_and_synthesize.py` |
| 5 | `synthesize_structure_discriminating.py` overwrote both artifacts | **FIXED** | §4; same file |
| 6 | `run_structure_confirmation.py` overwrote two `REPORTS_DIR` artifacts | **FIXED** | §4; `test_writer_collision_structure_runners.py` |
| 7 | `run_structure_element_measurement.py` overwrote three | **FIXED** | §4; same file |
| 8 | `run_structure_rrf_calibration.py` overwrote two | **FIXED** (found unassigned by this run's Tier A scan) | §2, §4; `test_writer_collision_rrf_calibration.py` |
| 9 | Three phase runners overwrote their report | **FIXED in 1.6X, re-verified** | §4; `test_runner_artifact_append_only.py` |
| 10 | `replace=True` never replaced | **FIXED** (self-inflicted, found by worker 4) | §5 |
| 11 | `replace=True` shared a fixed temp name | **FIXED** (reviewer R1) | §13 |
| 12 | `os.replace` failure propagates as `OSError` | **DEFERRED, documented** — fail-closed by design | §13 (R2) |
| 13 | `..` normalization could skip the lexical link-ancestor walk in the app helper | **FIXED** — explicit `..` refusal added | §8; `test_reparse_points_and_race_safety.py` |
| 14 | Same question for `cleanup_path.py` | **NOT REPRODUCED** — audited, no reachable defect; reviewer also failed to falsify | §8 |
| 15 | File-symlink refusal branches unexercised | **PARTIALLY FIXED** — junctions now execute the reparse branch (22 passed, 0 skipped); true-symlink and POSIX cases still skip | §7 |
| 16 | Check-then-use race | **BLOCKED** — no testable mitigation on the supported platform | §6 |
| 17 | Database lifecycle authority | **BLOCKED** — six-part infrastructure contract recorded | §9 |
| 18 | Ten database-blocked tests | **BLOCKED** — explicit markers, bodies preserved | §10 |
| 19 | Frozen benchmark integrity | **CONFIRMED UNCHANGED** | §11 |
| 20 | Upload tree unchanged | **CONFIRMED** — 1212 files, 0 modified today | §12 |
| 21 | Named specialist review | **NOT EXECUTED** — not registered runtime agents | §3 |
| 22 | Registered `VERIFIER` gate | **BLOCKED** — separate-instance adversarial review obtained; the named contract did not run | §3, §13 |

## 16. Verdict

**CONDITIONAL PASS.**

All eight previously identified artifact writers — plus a ninth site found by this run's own static
scan — now publish through the central append-only mechanism, with collision pre-flight, unchanged
serialization, loud non-zero refusals and visible `--replace` opt-ins, all covered by new
regression tests; the shared deletion path additionally refuses `..` normalization; the Windows
reparse-point branch moved from skipped to genuinely executed via junctions; and the full unit
suite passes after the final edits with the benchmark and upload tree provably untouched.

The conditions that withhold a full PASS: (1) no POSIX environment exists in this repository or on
this host, so symlink-specific and POSIX filesystem verification remains **NOT VERIFIED**;
(2) the check-then-use window is unchanged and unattended destructive cleanup stays **NO-GO**;
(3) PostgreSQL verification stays **NO-GO** with a six-part infrastructure contract outstanding;
(4) four platform symlink-privilege skips and ten database-blocked tests remain, none of them
counted as passes; and (5) the registered `VERIFIER` contract did not execute — the independent
review was a separate agent instance in the same model family, which the reviewer itself flagged as
not organisationally independent.
