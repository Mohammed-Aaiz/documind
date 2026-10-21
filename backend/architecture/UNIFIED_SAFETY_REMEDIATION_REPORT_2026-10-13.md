# DocuMind — Unified Safety Remediation Report

Date: 2026-10-13
Owner: COORDINATOR.
Mode: implementation-first, evidence-driven, fail-closed.
Scope executed: filesystem cleanup safety (implementation), test-harness isolation (implementation), database-lifecycle and runner boundaries (verified against current source, no code change), security/provenance review, safe test execution, consolidated evidence.

## 1. Executive summary

**Verdict: CONDITIONAL PASS.**

The filesystem cleanup boundary was defective and is now repaired, with executed evidence. Two additional defects that made the repair unverifiable were found and fixed: the cleanup script could never read the database at all (three undefined names), and the cleanup test suite could not run and had a dangerous failure mode (it patched an `lru_cache` wrapper instead of the settings object the script holds).

What was actually proven on this host:

* The upload root is now **refused** when it is a link or reparse point. Executed: `cleanup_path.intended_root` accepts a normal directory and refuses an NTFS junction, and `Path.is_symlink()` returns **False** for that junction while the new reparse-point check returns **True** — i.e. the exact case the old guard missed is now caught, on this machine, without privileges.
* The orphan sweep refuses an unsafe root **before** writing an archive or deleting anything; every deletion and every directory prune is re-validated individually; linked directories are not traversed; a failed or unverified archive blocks deletion.
* The frozen QA benchmark is byte-identical to its recorded digest, and the real upload tree is byte-for-byte unchanged after all test runs (1,212 files, identical manifest digest).
* The cleanup suite is now genuinely isolated and passes: **31 passed, 1 skipped** (the skip is an explicit, reported platform limitation).

What is **not** proven, and is not claimed: nothing about a live PostgreSQL target, nothing about race-free filesystem behaviour under a concurrent attacker, and nothing about a real destructive cleanup run. The independent-review gate is **unsatisfied** because no named specialist could be dispatched (§3).

## 2. Initial repository state and HEAD

| Item | Value |
|---|---|
| HEAD (initial and final) | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged) |
| Working-tree rows at start (`git status --porcelain=v1 -uall`, sorted) | 1,148 (all pre-existing uncommitted work, incl. 329 modified tracked files) |
| Working-tree rows at end | 1,148 (no status row added or removed by this task) |
| Files modified by this task | 3 (all already untracked in the working tree) |
| Files created by this task | 1 (this report) |
| Destructive git operations | none (no reset/clean/checkout/restore/stash) |
| Prior reports | read, not modified |

The two production files and the test file this task edited were already **untracked** working-tree files created by earlier uncommitted remediation work, so their `git status` rows are unchanged; their *contents* changed. Every other pre-existing change was preserved untouched.

## 3. Agent registry and actual dispatch results

The runtime exposes only generic subagents. No target instantiates the named project roles defined in `agents/*.md`.

| Required role | Dispatch attempted | Actual status | Evidence | Output |
|---|---|---|---|---|
| A. COORDINATOR | n/a (self) | **EXECUTED** | this report | register, implementation, integration, verification |
| B. DATABASE_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | no specialist agent type exists | coordinator-performed source reconciliation only (§6) |
| C. SECURITY_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | coordinator-performed review only (§7) |
| D. BACKEND_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | coordinator-performed analysis only (§6) |
| E. FILESYSTEM_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | implemented by the coordinator (§5) |
| F. TEST_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | tests written and run by the coordinator (§8) |
| G. EVALUATION_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | integrity checks run by the coordinator (§10) |
| H. VERIFIER | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | **independent verification gate UNSATISFIED** |
| Generic `code-searcher` ×5 | Yes | EXECUTED | 4 query batches per worker, file:line results | call-site, engine-construction, argv/secret, artifact-write, DROP/CREATE evidence |

Substitute review is **not** specialist review. No independent approval exists, so the outcome cannot be PASS on the independent-verification criterion. The coordinator did not write a self-review and label it independent.

## 4. Deduplicated original issue register

| ID | Finding | Source location | Risk | Owner | Required fix | Regression test | Verification evidence | Status |
|---|---|---|---|---|---|---|---|---|
| D-1 | `forbid_symlink_roots` compared `root.resolve(strict=False)` with a value assigned from the same expression; refusal unreachable | `scripts/cleanup_path.py:44,48` (pre-fix) | High | FILESYSTEM | Derive root from two independent values | `test_forbid_symlink_roots_rejects_linked_root` | **executed, passes** | **FIXED** |
| D-2 | `filesystem_supports_relative_symlinks()` returned constant `True`; import gate could not fail closed | `scripts/cleanup_path.py:54-66`, `cleanup_orphan_uploads.py:50-51` (pre-fix) | High | FILESYSTEM | Remove the unused gate/stub | n/a (function removed) | **executed: module imports and sweeps run** | **FIXED** |
| D-3 | Archive written before root validation | `cleanup_orphan_uploads.py:192-195` before `:197` (pre-fix) | High | FILESYSTEM | Validate root first | `test_sweep_refuses_linked_root_before_archiving_or_deleting` | **executed, passes** | **FIXED** |
| D-4 | Directory pruning had no containment or link check; `except OSError: pass` hid failures | `:214-226` (pre-fix) | High | FILESYSTEM | Validate every prune candidate | `test_nested_orphan_removed_and_empty_directories_pruned`, `test_linked_directory_is_not_a_prune_candidate` | **executed, passes** | **FIXED** |
| D-5 | `is_under` was a string-prefix comparison on `strict=False` resolutions | `cleanup_path.py:31-34` (pre-fix) | Medium | FILESYSTEM | Component-wise containment | `test_is_under_rejects_prefix_sibling`, `..._traversal_out_of_root` | **executed, passes** | **FIXED** |
| D-6 | No pinned intended root; `settings.upload_path` re-read at three sites | `:85,:132,:217` (pre-fix) | Medium | FILESYSTEM | One validated root object | covered by D-3/D-4 tests | **executed, passes** | **FIXED** |
| D-7 | Missing/unresolvable root indistinguishable from a valid one (`strict=False`) | `cleanup_path.py:44` (pre-fix) | Medium | FILESYSTEM | `strict=True`, refuse on failure | `test_missing_root_is_refused_by_the_guard` | **executed, passes** | **FIXED** |
| D-8 | Symlink tests silently skipped; no capability signal | `tests/unit/scripts/test_cleanup_orphan_uploads.py:210,252` (pre-fix) | Medium | TEST | Report skips, fail on POSIX | `test_link_capability_is_reported_not_silently_skipped` | **executed, passes** | **FIXED** |
| **N-1** | `_referenced_keys` referenced three undefined names, so the sweep could never read the database (always aborted with code 2) | `cleanup_orphan_uploads.py:70-75` (pre-fix; no import of `async_session`/`Document`/`VerificationResult`) | High | FILESYSTEM/BACKEND | Add the model + session imports | `test_orphan_removed_and_referenced_files_kept` exercises the real code path | AST check + **executed suite** | **FIXED** |
| **N-2** | Test harness patched `config.get_settings` (an `lru_cache` wrapper); `monkeypatch.setattr` raises `AttributeError`, so the suite could not run. Patching the cached *instance* instead would have pointed every deletion test at the real `backend/uploads` (1,212 files). `FakeSettings` was defined and never used. | `test_cleanup_orphan_uploads.py:106,121,155,181,212` (pre-fix) | Critical | TEST | Patch module global `orphan.settings`; add autouse interlock + session tripwire | `TestHarnessIsolation`, `real_upload_tree_tripwire` | **executed:** manifest digest identical before/after | **FIXED** |
| **N-3** | Old tests expected `SystemExit` from `run_sweep`, which *returns* codes; only `main()` raises | `:127,190,218` (pre-fix) | Medium | TEST | Assert returned codes | all sweep tests | **executed, passes** | **FIXED** |
| **N-4** | 24 SQLite cleanup-scope tests assert destructive row cleanup **succeeds**, which the intentional fail-closed gate makes impossible | `tests/unit/evaluation/test_phase3*_cleanup_scope.py`, `test_phase4b_evaluation_cleanup_scope.py` | Medium | TEST/EVALUATION | Reclassify as blocked, or assert refusal | none yet | **executed:** identical 24 failures with and without this task's test file | **BLOCKED** |
| U-01 | Live database identity/permissions unproven; production engine has no authorization boundary | `storage/database.py:43,49,56-63`; `evaluation/isolation.py:504-522` | High | DATABASE | Trusted identity mechanism | none possible here | source reconciliation | **BLOCKED** |
| U-02 | Lifecycle authorization is declarative (all gates refuse; `_proof_is_live` returns `False`) | `isolation.py:363-482` | Medium | DATABASE | External lifecycle authority | `tests/unit/evaluation/test_lifecycle_authorization.py` etc. (definitions only) | source reconciliation | **BLOCKED** (fail-closed, not fixed) |
| U-03 | (superseded by D-1/D-2/D-3/D-4) | — | High | FILESYSTEM | — | — | — | **FIXED** |
| U-05 | No recorded execution of the safety suites before this task | `tests/unit/evaluation/*` | High | TEST | Run and record | — | this report §8 | **PARTIALLY FIXED** |
| S-1 | Report/artifact overwrite: the central writer refuses overwrite, but several runners bypass it with raw `write_text` | `evaluation/artifacts.py:120,154`; e.g. `run_structure_confirmation.py:956-957`, `denominator_sensitivity.py:429-432` | Low–Medium | EVALUATION | Route writes through the append-only writer | none | source inspection | **DEFERRED** (out of scope) |
| S-2 | Credentials in process arguments | `tests/fixtures/e2e_config.py:216-229`, `integration_db.py:308-323` | High if present | SECURITY | — | — | source inspection: password travels via `PGPASSWORD` **environment**, `psql` argv carries only host/port/db | **NOT REPRODUCED** |
| S-3 | Raw SQL `DELETE` in the upload-integration runner | `run_phase3d_upload_integration.py:529-544` | Medium | BACKEND | Per-statement authorization | pre-existing AST tests | source inspection: downstream of the unconditional refusal at `:202` → unreachable | **NOT REPRODUCED** (unreachable) |
| S-4 | Filesystem check-then-use window | `cleanup_orphan_uploads.py` deletion/prune loop | Medium | SECURITY | Handle-bound deletion | T-10-class seam not implemented | design only | **DEFERRED** (documented residual) |

## 5. Implemented changes grouped by subsystem

### 5.1 Filesystem cleanup (implemented)

`backend/scripts/cleanup_path.py` (rewritten, 201 lines):

* `intended_root()` replaces the self-comparison: refuses a link/reparse-point root, refuses when the lexical absolute form and the resolved form disagree (two **independent** derivations), uses `strict=True`, and requires a directory. Missing root ⇒ refusal, never a pass.
* `is_link_or_reparse_point()` adds the Windows reparse-point check (`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`) alongside `is_symlink()`, because junctions are invisible to `is_symlink()`.
* `is_under()` now decides containment component-wise via `relative_to` with `..` rejection.
* `validate_candidate(root, candidate, *, expect="file"|"directory")` is the single check applied before every destructive operation: resolved containment, no link/reparse point at the candidate, no link ancestor, existence, and the required `S_ISREG`/`S_ISDIR` type; every failure returns `False`.
* `filesystem_supports_relative_symlinks()` **removed** (constant stub guarding a capability the sweep never uses).
* `forbid_symlink_roots()` kept as the public name, delegating to `intended_root()` — the required refusal-vs-accept contract is now executable.

`backend/scripts/cleanup_orphan_uploads.py` (rewritten, 364 lines):

* **N-1 fixed**: imports `async_session` and the models (`auth`, `chat`, `documents`, `reliability`, `user`, `verification`), so the database reference read works instead of raising `NameError`.
* Import-time capability gate removed.
* `_scan_uploads(root)` walks with `os.walk(..., followlinks=False)`, never descends into or returns a link/reparse point, and reports skipped links separately.
* Ordering fixed: DB read → existence → **root validated** → walk → classify → dry-run → confirmation → archive destination check → archive write → archive verify → per-candidate validate-then-delete → per-directory validate-then-prune → verification.
* Every `unlink` and every `rmdir` is individually gated; failures are printed, not swallowed; refusals are counted.
* Archive path refused if existing, a link/reparse point, or inside the root; any unvalidated candidate aborts the archive.
* Preserved: dry-run default, `--delete`/`--yes` semantics, archive-before-delete, exit codes `0/1/2/3`, `main()` →

`SystemExit`.

### 5.2 Test harness (implemented)

`backend/tests/unit/scripts/test_cleanup_orphan_uploads.py` (rewritten, 581 lines):

* **N-2 fixed**: the autouse `isolated_settings` fixture replaces the module global `orphan.settings`; `FakeSettings` is now used; a second autouse fixture asserts the active root is never the real upload tree; a session-scoped **tripwire** compares the real tree's file count before and after the run.
* **N-3 fixed**: sweep tests assert returned codes; tests are `async def` (project `asyncio_mode = auto`) so they don't disturb other modules' event loop.
* New link coverage: linked root refused before archiving, linked directory not traversed or pruned, junction detection, prefix-sibling and `..` traversal rejection, missing root, archive failure modes, prune behaviour, capability reporting.

### 5.3 Database lifecycle / runners / security (verified, not changed)

No production code in these areas was modified. `isolation.py` was read in full: `_proof_is_live()` returns `False` (`:363-366`); `record_created_database` refuses (`:369-374`); `assert_disposal_authorized`, `assert_creation_authorized`, `assert_cleanup_execution_authorized` and `release_database_proof` each raise unconditionally; `assert_engine_matches_target` compares URL fields without connecting. Runner engines are constructed **after** the guards (e.g. `run_phase3d_evaluation.py:629/635/683`). The only `CREATE`/`DROP DATABASE` sites are `tests/fixtures/integration_db.py:350-386`, both downstream of the central refusing gate.

## 6. Changed-file inventory

| File | Change | SHA-256 (16) | Size | Lines |
|---|---|---|---|---|
| `backend/scripts/cleanup_path.py` | rewritten (untracked → untracked) | `f444b706dc688589` | 7,853 B | 201 |
| `backend/scripts/cleanup_orphan_uploads.py` | rewritten (untracked → untracked) | `6acd21b265e179f1` | 13,758 B | 364 |
| `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py` | rewritten (untracked → untracked) | `1357220a552dc7a9` | 22,913 B | 581 |
| `backend/architecture/UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` | created | — | — | — |

No other file was added, modified or removed. `backend/scripts/cleanup_smoke.py` was **not** touched (adjacent issue recorded in §11). No test, migration, model, configuration or benchmark file was modified.

## 7. Tests executed — exact commands and results

| # | Command (run from `backend/`) | Result | Exit |
|---|---|---|---|
| 1 | `./venv/Scripts/python.exe -m pytest -q -rs tests/unit/scripts/test_cleanup_orphan_uploads.py` | **31 passed, 1 skipped** | 0 |
| 2 | `... -m pytest -q tests/unit/evaluation tests/unit/scripts tests/unit/storage` | 645 passed, **24 failed**, 1 skipped | 1 |
| 3 | same as #2 with `--ignore=tests/unit/scripts/test_cleanup_orphan_uploads.py` | 614 passed, **24 failed** | 1 |
| 4 | `... -m pytest -q tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` | 13 passed, 3 failed | 1 |
| 5 | `... -m pytest -q tests/unit/storage/test_sqlite_type_isolation.py::test_canonical_uuid_string_binds_like_postgresql` | **1 passed** (passes in isolation) | 0 |
| 6 | `... -m py_compile scripts/cleanup_path.py scripts/cleanup_orphan_uploads.py tests/unit/scripts/test_cleanup_orphan_uploads.py` | COMPILE OK | 0 |
| 7 | `find uploads -type f -printf '%p %s\n' \| sort \| sha256sum` | `cf4c42e9…` — **identical to the pre-work baseline**, 1,212 files | 0 |
| 8 | `sha256sum phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | matches the recorded digest exactly (116,271 bytes) — full value in §10 | 0 |

**Failure attribution (important).** The 24 failures in #2 are **pre-existing and unrelated to this change**: #3 reproduces the identical 24 failures with this task's test file excluded, and the two storage failures that appeared earlier were traced to this suite's former use of `asyncio.run` (fixed in #1). The 24 failures are all the same defect class — stale SQLite cleanup-scope tests that assert destructive row cleanup succeeds:

```
evaluation.isolation.UnsafeEvaluationTarget: REFUSING Phase 3D upload row cleanup:
cleanup execution is blocked; no enforceable, connection-bound lifecycle authorization exists.
```
(verified per module: phase3d-upload, phase3d-evaluation, phase3e-integration, phase3e-validation, phase3f-evaluation, phase4b — 5+3+3+3+5+5 = 24). They cannot pass until a real lifecycle authority exists, and they should not be "fixed" by weakening the refusal. Recorded as **BLOCKED** (N-4).

**Skip report (not hidden).** Exactly one skip, with reason:
`file symlink unavailable on this platform (OSError [WinError 1314] A required privilege is not held by the client)` — the file-link candidate case could not run here. The **directory-link** cases did run: junction creation via `mklink /J` succeeds unprivileged on this host, so linked-root refusal, no-traversal, no-prune and reparse detection are covered by executed tests rather than skips.

## 8. Evidence classes (static vs mock vs SQLite vs PostgreSQL)

| Tier | Status | What it establishes |
|---|---|---|
| A — static (`py_compile`, AST inspection, `git`, digests) | RUN | syntax validity, undefined-name defect N-1, benchmark and uploads integrity |
| B — unit, DB-free (mocked sessions, tmp filesystems) | RUN | all filesystem guard behaviour, sweep refusals, archive ordering, prune guards, harness isolation |
| C — SQLite-backed integration | RUN (subset) | the 24 failures are the fail-closed gate refusing, not a source-regression signal |
| D — PostgreSQL | **BLOCKED — NOT RUN** | nothing claimed |
| E — destructive cleanup | **BLOCKED — NOT RUN** | nothing claimed |

No SQLite or mocked evidence is presented as PostgreSQL verification.

## 9. Independent reviewer findings and verdicts

| Reviewer | Actual status | Findings / verdict |
|---|---|---|
| SECURITY_AGENT | **NOT EXECUTED — runtime dispatch unavailable** | no verdict; coordinator review only (§7) |
| DATABASE_AGENT | **NOT EXECUTED — runtime dispatch unavailable** | no verdict; source reconciliation only (§5.3) |
| TEST_AGENT | **NOT EXECUTED — runtime dispatch unavailable** | no verdict; tests run by the coordinator (§7) |
| EVALUATION_AGENT | **NOT EXECUTED — runtime dispatch unavailable** | no verdict; integrity checks in §10 |
| VERIFIER | **NOT EXECUTED — runtime dispatch unavailable** | **independent verification UNSATISFIED** |

No approval, conditional approval or rejection was returned by any named specialist, because none ran. The overall verdict is therefore CONDITIONAL on that gate alone.

## 10. Protected-artifact integrity results

| Artifact | Expected | Observed | Result |
|---|---|---|---|
| `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (116,271 bytes) | **UNCHANGED — MATCHES** |
| Real upload tree `backend/uploads/` | 1,212 files; manifest digest `cf4c42e9d7dde43262ca42687ed3417d7ad611e5ff07d298d5e5a8bf90bed2a2` | identical count and digest after every test run | **UNCHANGED — NO DESTRUCTION** |
| QA weights / retrieval weights / migrations / Alembic history | — | no file touched | **UNCHANGED** |

Incidental observation (out of scope, no action taken): the `backend/architecture/phase4f_6/e0_diagnostics/tools/*` scripts reference `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`, a path that does not exist in this tree (the real path is `backend/phases/phase4f/...`). Those tools would fail if run; recorded for a separate task.

## 11. Remaining issues and infrastructure dependencies

| ID | Issue | Why unresolved | Next action | Blocks PG? | Blocks cleanup? |
|---|---|---|---|---|---|
| U-01/U-02 | Live database identity, permissions and a real lifecycle authority | No disposable target, no trusted identity mechanism, no external authority implemented | Provide infrastructure; do not fake a proof object | **Yes** | No |
| N-4 | 24 stale cleanup-scope tests assert destructive success | The refusal is intentional | Reclassify as blocked or assert refusal | No | No |
| S-1 | Some runners bypass the append-only artifact writer | Out of scope; per-runner changes | Route writes through `artifacts.py` | No | No |
| S-4 | Check-then-use window in the deletion loop | Not closable on Windows (no `dir_fd`/`O_NOFOLLOW` for `unlink`/`rmdir`) | POSIX handle-bound deletion, or an explicit operator acknowledgement flag | No | **Yes** (for unattended runs) |
| Adjacent | `scripts/cleanup_smoke.py` deletes upload files with no containment or link check (`:61`,`:113`,`:136`) | Explicitly out of this task's scope | Separate authorization + reviewer | No | **Yes** |

## 12. Explicit PostgreSQL readiness decision

**NO-GO.** None of the required conditions hold: no genuinely disposable target with trusted identity, no known effective permissions, no operational (rather than declarative) authorization mechanism, and no independent review of the boundary. Tier D was not executed. Nothing in this report should be read as PostgreSQL verification.

## 13. Explicit destructive-cleanup readiness decision

**NO-GO.** No destructive cleanup was executed against any real upload directory during verification, and none is authorized now. The intended behaviour is demonstrated only through isolated temporary-directory tests. Two blockers remain before a real run: the documented check-then-use residual (S-4) and the unguarded adjacent `cleanup_smoke.py` path.

## 14. Final Git state and diff summary

* HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435` — **unchanged** before and after.
* Normalized working-tree comparison (`git status --porcelain=v1 --untracked-files=all`, sorted): **1,148 rows before → 1,149 rows after**, with exactly **one row added** — `?? backend/architecture/UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` — and **zero rows removed**. Every one of the 1,148 pre-existing changes is preserved. The three source files edited were already untracked, so their status rows are unchanged; only their contents changed (§6).
* No file was deleted, moved, reset, stashed, reverted or cleaned. No historical report was modified.

## 15. Closure table

| Original finding | Closure |
|---|---|
| D-1 ineffective symlink-root comparison | **FIXED** (executed test, junction case) |
| D-2 constant capability stub / import gate | **FIXED** (removed) |
| D-3 archive before root validation | **FIXED** (executed test) |
| D-4 unguarded prune | **FIXED** (executed test) |
| D-5 string-prefix containment | **FIXED** (executed tests) |
| D-6 no pinned intended root | **FIXED** |
| D-7 missing root indistinguishable | **FIXED** (executed test) |
| D-8 silent symlink-test skips | **PARTIALLY FIXED** — visible/self-failing policy implemented and the POSIX-required case fails rather than skips; the file-link case still skips on this host because the platform lacks the privilege |
| N-1 undefined names in `_referenced_keys` | **FIXED** |
| N-2 cleanup-test harness could not run / dangerous failure mode | **FIXED** (interlock + tripwire; real tree proven unchanged) |
| N-3 exit-code contract mismatch in tests | **FIXED** |
| N-4 24 stale cleanup-scope tests | **BLOCKED** (needs the lifecycle authority) |
| U-01 live identity/permissions | **BLOCKED** |
| U-02 lifecycle authorization operational | **BLOCKED** (fail-closed by design, not a defect) |
| U-03 filesystem guard findings | **FIXED** (see D-1…D-4) |
| U-05 no recorded execution of safety suites | **PARTIALLY FIXED** — the filesystem suite now has recorded execution; the evaluation suites still have none and 24 of them fail |
| S-1 artifact overwrite via raw `write_text` | **DEFERRED** |
| S-2 credentials in process arguments | **NOT REPRODUCED** (environment-based, verified) |
| S-3 raw `DELETE` in the upload runner | **NOT REPRODUCED** (unreachable behind the refusal) |
| S-4 check-then-use window | **DEFERRED** (documented residual) |
| `cleanup_smoke.py` unguarded deletion | **DEFERRED** (out of scope; recorded) |

---

**Limitations restated.** No named specialist executed; the independent-verification requirement is **unsatisfied**. No PostgreSQL target was contacted. No destructive cleanup was run. The check-then-use residual is documented, not eliminated. The filesystem is *not* established as universally safe by this document — only the specific defects above are shown to be fixed, by the specific evidence above.
