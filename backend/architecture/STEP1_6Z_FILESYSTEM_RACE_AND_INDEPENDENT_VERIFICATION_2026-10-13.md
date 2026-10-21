# STEP 1.6Z — Filesystem Race Mitigation and Independent Verification

Date: 2026-10-13
Owner: COORDINATOR (this run)
Predecessors: `STEP1_6Y_ARTIFACT_AND_FILESYSTEM_VERIFICATION_2026-10-13.md` (SHA-256 prefix `92ee2315822071b2`),
`STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md` (`b0cbefef7d9cab14`),
`UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` (`66b53544ebffd2d0`)
Verdict: **CONDITIONAL PASS** (§16)

Append-only evidence. Every status below carries the evidence that was actually observed. Where a
claim rests on source reading rather than execution it says so. No database mutation, no real
cleanup sweep, no archive deletion, no commit, no push and no destructive Git operation was
performed.

---

## 1. Executive summary

Step 1.6Z investigated the check-then-use windows in upload deletion, directory pruning, orphan
sweeps and archive handling, implemented the mitigations that the platform's own guarantees can
support, and had the result reviewed adversarially. What actually changed:

1. **Descriptor-relative deletion (POSIX).** `scripts/cleanup_path.py` gained
   `open_root_fd` / `unlink_beneath` / `rmdir_beneath`: the root is held as a directory descriptor,
   every intermediate component is opened with `O_NOFOLLOW`, and the final `os.unlink` / `os.rmdir`
   is descriptor-relative. The delete is bound to the *directory object* that was opened, so
   neither the root nor a parent directory can be redirected between validation and the syscall.
2. **The two failure modes no longer collapse (finding B, medium).** `open_root_fd` previously
   returned `None` both for "this platform cannot do it" and for "this root could not be opened",
   so a caller fell back to a pathname delete exactly when the tree looked wrong. It now raises
   `RuntimeError` in the second case, and all three callers refuse instead of retrying by pathname.
3. **Archive creation is now an exclusive create, and verification reads the same handle.** A
   destination planted between the pre-check and the open can no longer be truncated and replaced,
   and the archive that is verified is provably the object that was written. A failed write leaves
   the incomplete archive in place rather than issuing a pathname unlink (§6.6).
4. **Test integrity (finding A, medium).** Every substitution hook installed by the race suite is
   now registered and asserted to have fired; a hook that never runs fails its test instead of
   leaving the test vacuously green. The archive-substitution test gained the same kind of
   falsification guards (§7).
5. **Function-level authorization for two inline deletions.** The inline row deletions inside
   `run_phase3e_integration.py` and `run_phase3e_validation.py` now carry
   `assert_cleanup_execution_authorized` on their own code path, so enabling lifecycle
   authorization later cannot silently create an ungated destructive entry point.

What did **not** change, and why: the Windows flow (no `dir_fd` primitive), the application-side
`storage/file_store.delete_upload` (pathname-based, documented residual), and `start_server.py`'s
pre-existing `__pycache__` sweep (outside this step's scope; flagged in §13).

Verification in one line: **1328 passed, 23 skipped, 0 failed** on the final code
(`venv/Scripts/python.exe -m pytest -q tests/unit`, exit 0), with the frozen benchmark digest, the
upload tree and the published report directory provably unchanged.

**Overall verdict: CONDITIONAL PASS.** The scoped changes are verified on Windows; POSIX
execution evidence does **not** exist on this host or in this repository, the Windows path keeps a
documented check-then-use residual, and the independent-review gate is **NOT SATISFIED** as an
organisational control (§11, §15). Unattended destructive cleanup remains **NO-GO**.

---

## 2. Baseline repository state

| Item | Value |
| --- | --- |
| HEAD at start and at end | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged; nothing committed, staged, pushed, reset, cleaned or restored) |
| Branch | `main` |
| Staged files | 0 (`git diff --cached --name-only` → empty) |
| Working-tree inventory | `git status --porcelain` → 385 entries; the pre-existing deletions/modified set and the untracked `evaluation/**`, `scripts/**`, `tests/**` layout carried over from before Step 1.6X are untouched (they are the baseline, not this step's output) |
| Interpreter used for the reported runs | `backend/venv/Scripts/python.exe` — Python **3.11.0** (the interpreter of the Step 1.6Y baseline). Re-run under the system interpreter (`py -3`, Python 3.13.12, pytest 8.3.4) with **identical counts**, so nothing here is version-specific |
| Host | Windows, `uname -s` = `MINGW64_NT-10.0-26300` (Git Bash on Windows — **not** POSIX) |
| Prior reports | `STEP1_6X…` `b0cbefef7d9cab14`, `UNIFIED_SAFETY_REMEDIATION…` `66b53544ebffd2d0` — both **identical to the prefixes recorded in Step 1.6Y**, so neither was overwritten; `STEP1_6Y…` `92ee2315822071b2`, file time 19:12:23, i.e. written before any 1.6Z edit and not rewritten |
| `.env` / credentials | **not read** |
| Real cleanup sweep / archive deletion / production deletion | **not run** (all destructive-path tests confined to `tmp_path`) |

Files this step touched (mtime after the Step 1.6Y report at 19:12), enumerated from the working
tree rather than assumed:

| Time | Path |
| --- | --- |
| 19:40–19:41 | `evaluation/experiments/run_phase3e_integration.py`, `evaluation/experiments/run_phase3e_validation.py`, `tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` |
| 19:54–19:59 | `scripts/cleanup_path.py`, `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py` |
| 20:01–20:05 | `tests/unit/scripts/test_race_substitution_deterministic.py`, `test_cleanup_orphan_uploads.py`, `test_cleanup_smoke_safety.py`, `test_descriptor_relative_deletion.py` |

No other `.py` file under `backend/` (excluding `phases/`, `models/`, `__pycache__`) was modified.

---

## 3. Step 1.6Y claims independently rechecked

| Step 1.6Y claim | Still true? | Evidence taken in 1.6Z |
| --- | --- | --- |
| HEAD unchanged, nothing committed | **Yes** | `git rev-parse HEAD` → `6baaa2a…`; 0 staged |
| Frozen benchmark untouched | **Yes** | `qa_benchmark_v1.jsonl` SHA-256 = `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches the 1.6Y digest exactly** |
| Upload tree unchanged (1212 files / 7 386 232 bytes) | **Yes** | 1212 files, 7 386 232 bytes, **0 modified today** — identical to 1.6Y |
| Published reports unchanged (51 files, newest 2026-10-06) | **Yes** | 51 files; newest real artifact `evaluation/reports/table_evidence_measurement_analysis.json`, 2026-10-06; only `__pycache__/__init__.cpython-311.pyc` carries today's date; 0 stray `*.tmp`/`*.bak` under `backend/` |
| Ten database-blocked tests, bodies preserved | **Yes** | 10 skipped `BLOCKED` markers; unchanged text |
| Four symlink-privilege skips (`WinError 1314`) | **Yes — still 4** | `test_cleanup_smoke_safety.py:74`, `:466`, `test_cleanup_orphan_uploads.py:145`, `test_file_store_deletion_safety.py:51` |
| Windows junction branch executes (22 passed, 0 skipped) | **Yes** | `test_reparse_points_and_race_safety.py` → 22 tests collected, all execute |
| No POSIX runner; no CI configuration | **Yes** | `uname -s` = `MINGW64_NT-10.0-26300`; no `.github/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci` |
| Six-part PostgreSQL authorization contract outstanding | **Yes** | §12; no lifecycle code touched this step |
| VERIFIER contract not a registered runtime agent | **Yes** | §11 |
| "Check-then-use race BLOCKED — no testable mitigation" | **Superseded in part** | The POSIX mitigation is now **implemented** with POSIX-only tests, so the window is *narrowed where the platform supports it* — but not on the host that runs the suite, so the overall status moves from BLOCKED to **PARTIAL / NOT VERIFIED** (§9, §15). It is not claimed closed |

---

## 4. Filesystem threat model

Cases are distinguished exactly as the task requires: **A** lexical traversal, **B**
link/reparse-point traversal, **C** object replacement, **D** parent replacement, **E** concurrent
operations, **F** archive substitution.

| # | Operation | Untrusted/mutable input | Containment check | Link/reparse check | Object validated | The gap | Case | Consequence if replaced | Platform primitive that narrows it |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete an uploaded file (app runtime, `storage/file_store.delete_upload`) | stored DB path | resolved containment + `relative_to` | candidate + every ancestor below root; explicit `..` refusal | the *path* | validate → pathname `unlink()` | **C/D** | wrong file deleted **inside or outside** the root on Windows; inside-root on POSIX | none used here (see §6.8) |
| 2 | Clean up a newly created upload after a failed operation | the just-written path | same helper (`cleanup_new_file` delegates) | same | the path | validate → `unlink()` | **C** | a substituted candidate is removed | same as #1 |
| 3 | Prune a user upload directory (`cleanup_smoke.prune_user_dir`) | `user_id` | `validate_candidate(..., expect="directory")` + emptiness | link/reparse refusal | directory object | validate → `rmdir` | **C/D** | an empty directory elsewhere removed / parent redirected | `rmdir_beneath` on POSIX |
| 4 | Remove orphaned uploads (`cleanup_orphan_uploads.run_sweep`) | every on-disk file under root | `intended_root` + per-candidate re-validation | link/reparse refusal; links never deleted | the path | validate → `unlink()` | **C/D/E** | unvalidated file deleted | `unlink_beneath` on POSIX |
| 5 | Create, verify and remove a cleanup archive | archive destination, orphan set | `archive.exists()` pre-check; destination may not be inside the root | archive path + candidates | the *name* | check → `open(..., "w")`; verify → re-open by pathname | **C/F** | truncation/replacement of an unrelated file; verification of a substituted object | exclusive `open(..., "x+b")` + verify on the same handle (§6.4–6.5) |
| 6 | Replace/redirect a validated root | configured upload root | `intended_root` (lexical vs resolved agreement) + `forbid_symlink_roots` re-check | root must not be a link/reparse point | the root path | re-validation → first syscall | **D** | every deletion redirected | root held as a descriptor on POSIX; **not** on Windows |
| 7 | Write published evaluation evidence | destination artifact | `write_evidence` append-only + pre-flight | n/a | the path | check → exclusive `open("x")` | **C** | an existing report replaced | exclusive create already in place (1.6Y); re-verified unchanged |

The essential point, stated so it cannot be read as stronger than it is: **a check that resolves a
path and later calls `unlink()`/`rmdir()` by pathname does not establish that the deleted object is
the object that was validated.** Only operation 5 (creation), operation 7 and the POSIX arms of
operations 3, 4 and 6 have a primitive that binds the operation to the validated object; the Windows
arms of 1, 2, 3, 4 and 6 do not.

---

## 5. Race windows identified

| Window | Platform | Status before 1.6Z | Status now | Verified how |
| --- | --- | --- | --- | --- |
| Root replaced after validation, before the delete | POSIX | open | **closed for parents/root** (descriptor held; component-wise `O_NOFOLLOW` descent) | POSIX-only tests written; **not executed here** |
| Same window | Windows | open | **unchanged, documented** — no `dir_fd` primitive exists | not exercisable on Windows |
| Parent directory replaced after validation | POSIX | open | **closed** (delete is relative to the held parent descriptor) | POSIX-only tests; not executed here |
| Parent directory replaced after validation | Windows | open | **unchanged, documented** | — |
| Candidate (final name) swapped for another object inside the same validated directory | POSIX + Windows | open | **still open by construction** — no stdlib primitive binds a name to an earlier `lstat`; consequence is bounded to the already-validated directory | stated in code and tests, not claimed fixed |
| Archive destination appearing/planted after the existence check | POSIX + Windows | **exploitable** (`open(..., "w")` truncated it) | **closed** — exclusive `open(..., "x+b")` makes creation the refusal | `test_a_file_appearing_after_the_existence_check_is_not_overwritten`, plus a negative control: reverting to mode `"w"` makes the test fail |
| Archive verified by pathname re-open after an in-handle write | POSIX + Windows | open (verified object not bound to the written object) | **closed** — verification reads the same handle | positive test `test_verified_archive_is_written_before_deletion`; the first implementation used write-only `"xb"` and the test failed with `BadZipFile`, which is direct evidence the handle-bound path is genuinely exercised |
| Failed archive removed by pathname | POSIX + Windows | open (pathname `unlink` after a failed write) | **closed** — the incomplete archive is left in place for the operator; no pathname delete remains on that path | archive-write-failure test updated and re-run |
| Two concurrent sweeps over one candidate | POSIX + Windows | open | unchanged (first delete wins; the second reports `missing`/`refused`); no data-loss escalation found | idempotence test + `test_a_declined_descriptor_delete_never_falls_back_to_pathname` |
| Root swapped for a link between the last validation and the delete | POSIX | open | **narrowed**: `open_root_fd` raises → callers refuse (finding B) | `test_an_unholdable_root_on_a_supporting_platform_is_a_refusal` (forced gate, runs on Windows), `TestUnholdableRootRefusesCleanup` |
| Same window | Windows | open | unchanged | — |

---

## 6. Mitigations implemented and their platform guarantees

Each entry uses the task's decision rule.

### 6.1 Descriptor-relative deletion for the operational cleanup path — **IMPLEMENTED, PLATFORM VERIFICATION PENDING (POSIX)**

`scripts/cleanup_path.py`: `POSIX_DIR_FD_SUPPORTED` (`os.unlink in os.supports_dir_fd`, POSIX only),
`open_root_fd` (`os.open(root, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)`), `_descend_to_parent` (each
component opened relative to the previous descriptor with `O_NOFOLLOW`, previous descriptor closed
as it goes), `unlink_beneath` (`os.unlink(name, dir_fd=parent_fd)`) and `rmdir_beneath`
(`os.rmdir(name, dir_fd=parent_fd)`, never recursing into a non-empty directory).

Guarantee: the removal is bound to the directory object that was opened; renaming or replacing the
root after `open_root_fd` cannot change which directory the descriptor refers to. Return values are
`"unlinked" | "refused" | "failed" | "unsupported"`, and an `"unsupported"`/`"refused"` outcome is
**never** retried by pathname.

What it does not close, stated in the module docstring rather than papered over: the final *name* can
still be swapped inside that same held directory. Windows exposes no equivalent primitive, so the
pathname flow remains there with its documented residual.

### 6.2 The two failure modes no longer collapse — **IMPLEMENTED AND VERIFIED (both platforms)**

Finding B (medium). Before: `open_root_fd` returned `None` for an unsupported platform **and** for a
root it could not open, so callers silently fell back to a pathname delete exactly when the tree
looked wrong (root swapped for a symlink between validation and the call, permission change, I/O
error). After: `None` means only "this platform cannot do it"; an unopenable root on a supporting
platform raises `RuntimeError`, and all three callers refuse:

* `scripts/cleanup_smoke.py` `delete_upload_files` → every candidate counted as refused, nothing deleted;
* `scripts/cleanup_smoke.py` `prune_user_dir` → `False`, directory untouched;
* `scripts/cleanup_orphan_uploads.py` `run_sweep` → prints the abort and returns 1 with nothing deleted.

Verified on this host by forcing the platform gate on and making `os.open` fail
(`test_an_unholdable_root_on_a_supporting_platform_is_a_refusal`), plus three caller-level tests that
run on Windows (§7). The real-`os.open` variant is a POSIX-only test.

### 6.3 Fail-closed callers, never a pathname retry — **IMPLEMENTED AND VERIFIED**

The descriptor path is attempted first on POSIX; `"refused"`/`"failed"` outcomes are reported as
refusals. When the platform cannot hold a root, the pathname flow is used *with its documented
residual* — the same behaviour as before, which is why §13 keeps destructive cleanup NO-GO.

### 6.4 Archive creation as an exclusive create — **IMPLEMENTED AND VERIFIED**

`_archive_orphans` previously checked `archive.exists()` and then opened the destination with mode
`"w"` (truncating), so a file created in the window was silently replaced and the sweep still
deleted its orphans. The destination is now created with `open(archive, "x+b")`: an existing path —
or one that appeared since the check — raises `FileExistsError`, which is reported and returns 3
with nothing archived or deleted.

Evidence: the substitution test passes, and a negative control (temporarily restoring mode `"w"`)
makes it **fail** — the test discriminates the mitigation rather than merely observing a refusal.

### 6.5 Archive verification bound to the written object — **IMPLEMENTED AND VERIFIED**

Verification no longer re-opens the archive by pathname. It seeks the creation handle to 0 and runs
`zipfile.ZipFile(handle)` → `testzip()` (CRC over every entry) plus the entry-count comparison on
that same handle, so the verified object is the written object. `zipfile.BadZipFile` is caught with
`OSError` so a corrupt archive aborts with nothing deleted instead of propagating after a partial
archive exists.

Evidence of genuineness: the first version of this change kept the write-only `"xb"` mode, and
`test_verified_archive_is_written_before_deletion` failed with
`BadZipFile('File is not a zip file')`. The mode was corrected to `"x+b"` (exclusive *and*
readable) and the test passes. That failure is recorded rather than hidden: it is proof the
handle-bound verification path is exercised.

### 6.6 No pathname deletion of a failed archive — **IMPLEMENTED AND VERIFIED**

On a write/verification failure the incomplete archive is deliberately **left in place**, and the
operator is told to remove it by hand. Rationale: the only deletion primitive reachable there is a
pathname unlink, which is precisely the operation this step removes; leaving it also makes a silent
re-run impossible, because the next sweep refuses an existing archive (exit 3). The corresponding
test now asserts the fragment exists instead of asserting its removal.

### 6.7 Function-level authorization for the two inline deletions — **IMPLEMENTED (gate refuses by design)**

`run_phase3e_integration.py` and `run_phase3e_validation.py` perform inline `delete(DocumentChunk)` /
`delete(Document)` blocks inside `main()`. Both now call
`assert_cleanup_execution_authorized(db, operation=...)` immediately before the first delete, so the
function-level policy holds independently of the runner-level disposal gate. Both blocks are
unreachable today because the gate refuses unconditionally; the tests assert the gate's presence and
the exact operation string per runner by reading the runner as text (no import, no engine, no
connection).

### 6.8 Investigated; not changed

* **`storage/file_store.delete_upload` — INVESTIGATED; NOT IMPLEMENTED IN THIS STEP.** This is the
  most attacker-reachable deletion (upload paths originate from user uploads), and it remains
  pathname-based: resolved containment, link/reparse refusal for the candidate and every ancestor,
  `..` refusal, `S_ISREG` requirement, all failures returning `False`. Adding a descriptor-relative
  arm here means duplicating the `scripts/cleanup_path.py` policy inside production code (the two are
  deliberately kept in step by hand, because production must not import `scripts/`), and on this
  host the POSIX arm could not be executed even once. Shipping an unrunnable production deletion
  path was judged worse than the documented residual, so the decision is recorded, not implemented.
  This is the single highest-value remaining item (§13, §16).
* **`scripts/start_server.py:62` pre-existing `__pycache__` sweep — ACCEPTED WITH DOCUMENTED
  LIMITATION.** `shutil.rmtree(..., ignore_errors=True)` runs at import with no containment check, so
  a `__pycache__` that had been replaced by a link would be recursed into. It is outside this step's
  upload/cleanup/archive scope, it is not reachable from the upload path, and it deletes only
  directories named `__pycache__`. Recommended bounded fix recorded in §13.
* **`evaluation/artifacts.py`** — **not modified**: reconnaissance and testing surfaced no integrity
  defect in this step; its append-only behaviour was re-verified unchanged (§3).
* **A merge of the POSIX and Windows flows into one abstraction** — not attempted; the platform
  guarantee differs, and a single abstraction would have to claim the weaker one.

---

## 7. Tests added or changed

| File | Tests | Change and invariant asserted |
| --- | --- | --- |
| `tests/unit/scripts/test_race_substitution_deterministic.py` | 7 (new in 1.6Z) | Deterministic substitution at the syscall boundary: root redirected, candidate replaced by a link, prune target redirected outward, two-sweep concurrency, archive destination substituted after the check, repeated sweeps, traversal/prefix/missing-root refusals. Each deletion/prune test asserts survivors byte-for-byte. |
| `tests/unit/scripts/test_descriptor_relative_deletion.py` | 31 (23 execute, 8 POSIX-only skips) | The descriptor helpers: platform gate and refusal logic run everywhere; real unlink/rmdir, `O_NOFOLLOW` descent, parent swap, symlinked intermediate and "replacement stays inside the root" tests are POSIX-marked. |
| `tests/unit/scripts/test_cleanup_smoke_safety.py` | 26 (+2 this step) | Added: an unholdable root refuses every candidate; the prune path refuses an unholdable root. Both stub `open_root_fd` to raise and make the pathname delete unreachable. |
| `tests/unit/scripts/test_cleanup_orphan_uploads.py` | 34 (+1 this step) | Added `TestUnholdableRootRefusesCleanup`: the sweep aborts with exit 1 and deletes nothing. Updated the archive-write-failure test to the leave-the-fragment-in-place contract. |
| `tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` | 13 (extended this step) | Now covers all three inline destructive blocks with their exact per-runner operation strings, including the two 3E runners gated in this step. |

**Falsification controls introduced (finding A, medium).** The race suite installs substitution hooks
at three delete boundaries and two prune boundaries, with one shared one-shot guard. A hook that is
installed but never fires makes its test vacuous — the asserted invariant then holds because nothing
was substituted. Every hook is now registered in `_INSTALLED_HOOKS` and an autouse fixture fails the
test if any installed hook did not run. Verified in both directions:

* positive: all six hook-using tests still pass with enforcement on (they fire on the real boundary);
* negative control: a temporary test that installs a hook and never triggers a delete **fails** at
  teardown with `a substitution hook was installed but never fired, so the test would have passed
  without exercising the race window` (exit 1). The injected test was then removed and the file
  restored byte-for-byte from a backup taken immediately before the injection; no backup file remains.

The archive-substitution test carries the same kind of guards: it asserts that the patched `exists`
was actually consulted for the archive *and* that the refusal came from the creation branch
(`appeared before it could be created`) rather than the pre-check branch (`already exists`), because
otherwise the test would pass on the pre-check alone without touching the mitigation.

Tests were not weakened anywhere: no assertion was relaxed, no test deleted, no safety gate disabled
and no skipped test counted as a pass. Where an implementation decision changed a test's expected
outcome (the incomplete archive is now kept), the test was updated to assert the new, deliberate
behaviour together with the reason.

---

## 8. Exact commands and observed results

All commands run from `backend/`; each exit status is the tested command's own (captured after any
output filtering, `PIPESTATUS[0]` / explicit `$?`).

| # | Command | Observed result | Exit |
| --- | --- | --- | --- |
| 1 | `venv/Scripts/python.exe -m compileall -q scripts storage tests/unit/scripts` | clean, no output | **0** |
| 2 | `venv/Scripts/python.exe -m pytest -q tests/unit/scripts` | **108 passed, 12 skipped** | **0** |
| 3 | `venv/Scripts/python.exe -m pytest -q tests/unit` (final, after every edit) | **1328 passed, 23 skipped, 0 failed**, 66.24s | **0** |
| 4 | same suite under the system interpreter `py -3` (Python 3.13.12, pytest 8.3.4) | **1328 passed, 23 skipped** — identical | **0** |
| 5 | `pytest -q tests/unit/scripts/test_race_substitution_deterministic.py` | 7 passed | **0** |
| 6 | negative control: injected an unfired-hook test into that module | **fails** (teardown `AssertionError`), exit 1; injected test removed, file restored | **1** (intended) |
| 7 | negative control: `open(archive, "x+b")` temporarily reverted to `"w"` | the archive-substitution test **fails**; mode restored, then 7 passed | **1** (intended) |
| 8 | benchmark digest, upload tree, report directory, stray-temp scan | digest `1166bf…a41d0` **matches**; uploads 1212 files / 7 386 232 bytes / 0 modified today; reports 51 files, newest 2026-10-06; 0 stray `*.tmp`/`*.bak` | **0** |
| 9 | `git rev-parse HEAD`, `git status --porcelain`, `git diff --cached --name-only` | `6baaa2a…`; 385 working-tree entries; **0 staged** | **0** |

**Skip accounting for row 3 — 23 = 10 + 4 + 9.** Ten are the explicit database-`BLOCKED` markers
(unchanged from 1.6Y). Four are the platform symlink-privilege skips, each printing
`WinError 1314` and its own reason. Nine are the **new POSIX dir-fd-only tests** of this step (8 in
`test_descriptor_relative_deletion.py`, 1 in `test_cleanup_smoke_safety.py`), each skipping with
`requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); not available on Windows`. **No
skipped test is counted as a pass, and the nine new skips are the honest measure of what cannot be
verified here (§9).**

The Step 1.6Y baseline run was 1282 passed / 14 skipped, taken *before* the new race, descriptor and
inline-SQL test files of this step existed; the +46 passed and +9 skipped are those tests. Neither
count is presented as a comparison of like with like.

---

## 9. POSIX verification evidence or explicit blocker

**No real POSIX execution occurred. POSIX-specific verification: NOT VERIFIED.**

| Facility | Available? | Evidence |
| --- | --- | --- |
| POSIX kernel on this host | **No** | `uname -s` → `MINGW64_NT-10.0-26300` (Git Bash on Windows) |
| WSL | **No** | Recorded in Step 1.6Y: `wsl.exe` reports the subsystem is not installed; re-invoking it here was not needed and was avoided because it blocks the shell |
| Linux container | **No Docker CLI on PATH in this shell** | `command -v docker` produced no usable result within the command budget; no container was started |
| Repository CI (any Linux job) | **None exists** | No `.github/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci` |

Consequently: the descriptor-relative deletion helpers, the POSIX symlink cases, and the
`O_NOFOLLOW` descent are covered by tests that **skip** on this host. They are not counted as
verified, and Windows junction behaviour is **not** treated as a substitute for POSIX symbolic-link
behaviour — a junction is a reparse point that `Path.is_symlink()` does not report, whereas the
POSIX tests exercise true symbolic links and `dir_fd` syscalls.

Smallest safe way to close it: run
`python -m pytest -q tests/unit/scripts tests/unit/documents` on a Linux host (or a Linux CI job) in
this working tree, so the nine skipped POSIX tests execute and their assertions — real unlink/rmdir
beneath a held descriptor, `O_NOFOLLOW` refusal of a swapped parent, and the "replacement stays
inside the root" bound — are observed rather than skipped. No CI configuration was added: there is no
existing CI architecture to extend, and inventing one could not be verified from here.

---

## 10. Windows-specific findings and limitations

* **No `dir_fd` equivalent.** `os.unlink in os.supports_dir_fd` is `False` on Windows, so
  `_descend_to_parent`/`unlink_beneath`/`rmdir_beneath` report `"unsupported"` and the pathname flow is
  used. Nothing in the POSIX implementation is copied into the Windows path, because the guarantee
  does not exist there.
* **Reparse points vs symlinks.** `Path.is_symlink()` reports NTFS **junctions** as `False`; the
  attribute bit (`FILE_ATTRIBUTE_REPARSE_POINT`) is what the code checks. Junction-based tests
  execute (22 in `test_reparse_points_and_race_safety.py`, 0 skipped), which is real coverage of the
  reparse branch — but it is not POSIX coverage.
* **File symlink creation still needs privilege.** Four tests skip with `WinError 1314` and print
  their reason; they are reported as skips, never as passes.
* **Object-bound deletion is not available.** Where the platform cannot bind a delete to a validated
  object, the residual is documented in the code and repeated in §13 — including the fact that
  `O_NOFOLLOW` protects against a *link* component, not against a component replaced by a real
  directory, and not against the final-name swap.
* **The measured guarantee on this host is therefore:** the specific substitutions the tests perform
  are refused, and every refusal is reported (non-zero exit / refusal counts) rather than swallowed.
  That is weaker than race-freedom and is described as such.

---

## 11. Independent review identity, scope, findings and limitations

| Item | Value |
| --- | --- |
| Reviewer | A separate agent instance (worker agent), **same model family as the author**, no terminal, no web, source reading only |
| Scope | The final source of `scripts/cleanup_path.py`, `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, `storage/file_store.py`, `evaluation/artifacts.py` and the race/descriptor tests |
| Brief | Adversarial: attempt to falsify the safety claims, answer ten specific questions, give severity, file/line, reproduction steps and remediation |
| Verdict returned | **CONDITIONAL PASS**, with self-declared caveats |
| Registered `VERIFIER` contract | **NOT EXECUTED** — the named contracts in `agents/*.md` are markdown, not registered runtime agents |

**Documented limitation, stated plainly:** the reviewer is **not organisationally independent** — it
shares the author's model family and execution context, and it could execute nothing (no terminal,
no pytest, no POSIX host), so every judgement it made is source reading. **The independent-review
gate is therefore NOT SATISFIED as an organisational control.** The review's findings are also not a
committed artifact; the dispositions below are keyed to the finding substance recorded in this run.

Answered questions (reviewer, pre-fix; re-checked by the coordinator after the fixes — source
reading plus the tests in §8):

1. **Can a path component be replaced between validation and deletion?** Yes — the final name always;
   parents/root no longer on POSIX (descriptor-relative), unchanged on Windows.
2. **Is deletion bound to the validated object?** On POSIX, for parents and root, yes. The final name
   is not bound; no stdlib primitive does that, and the code says so.
3. **Can a parent or the root be redirected?** Not on POSIX after the descriptor is held. On Windows,
   yes, in principle.
4. **Do the tests exercise the actual race window, or only nearby behaviour?** Per test: hooks fire on
   the real boundary and (now) are asserted to have fired; the archive-substitution test additionally
   asserts the creation branch refused. The residual honest statement is that these are
   *deterministic simulations at the boundary*, not proofs of race-freedom.
5. **Are Windows and POSIX guarantees accurately distinguished?** Yes in the code and in this report;
   junction coverage is never presented as POSIX coverage.
6. **Can a failed archive or cleanup operation still delete unrelated files?** Not through the
   archive path (creation is exclusive, verification is handle-bound, no pathname delete remains);
   through the Windows cleanup path, a substituted candidate inside the validated directory remains
   possible and is documented.
7. **Are authorization checks enforced at the actual destructive boundary?** For the two inline
   evaluation deletions, yes (function-level gates added). For the cleanup scripts, authorization is
   the operator confirmation plus the root gate; unattended cleanup stays NO-GO.
8. **Are any tests skipped, weakened or misleadingly named?** 23 skips, all with reasons (10
   database-`BLOCKED`, 4 symlink privilege, 9 new POSIX-only); no assertion weakened; the one
   renamed/reworded test (`test_close_root_fd_accepts_none_on_every_platform`) was retitled because
   it no longer claims what its old name said.
9. **Does any code path bypass the shared safety boundary?** `storage/file_store.delete_upload` keeps
   its own hand-maintained policy (documented, §6.8) — the same boundary by convention, not by code
   sharing. `start_server.py`'s `__pycache__` sweep is outside the boundary entirely (§6.8, §13).
10. **Is the readiness verdict justified by observed evidence?** Yes: the matrix in §15 states
    blocked and unverified areas separately and does not collapse them into a test count.

Findings and dispositions:

| # | Finding | Severity | Status |
| --- | --- | --- | --- |
| A | Substitution hooks could be installed but never fire, leaving race tests vacuously green (the prune test passed on invariants that held anyway) | medium (test integrity) | **FIXED AND RETESTED** — hook registry + autouse fixture; positive and negative controls observed (§7) |
| B | `open_root_fd` collapsed "platform unsupported" and "root could not be opened" into `None`, so callers fell back to a pathname delete exactly when the tree looked wrong | medium (safety) | **FIXED AND RETESTED** — `RuntimeError` + three fail-closed callers + four tests (§6.2) |
| D | A failed archive was removed with a pathname `unlink` | low | **FIXED AND RETESTED** — fragment left in place, no pathname delete on that path (§6.6) |
| E | Archive verification re-opened the archive by pathname, so the verified object was not provably the written object | low | **FIXED AND RETESTED** — verification on the creation handle (§6.5) |
| F | Archive-substitution test could pass on the pre-check alone | low | **FIXED AND RETESTED** — consulted-`exists` and branch-message assertions (§7) |
| C | `scripts/start_server.py`'s import-time `__pycache__` `rmtree(ignore_errors=True)` sits outside the shared safety boundary | low | **ACCEPTED WITH DOCUMENTED LIMITATION** — pre-existing, non-upload path, out of this step's scope; recommended fix recorded (§13) |
| — | `storage/file_store.delete_upload` has no descriptor-relative arm | low/medium residual | **ACCEPTED WITH DOCUMENTED LIMITATION** — see §6.8, §13; not implemented because the POSIX arm cannot be executed here |
| — | The reviewer had no terminal, shares the author's model family, and the `VERIFIER` contract is not a runtime agent | process | **NOT FIXED — limitation recorded**; gate NOT SATISFIED (§15) |

No finding was marked "NOT REPRODUCED WITH EVIDENCE" by treating it as unimportant; the two
documented limitations are live, unfixed risks.

**Finding detail — location, reproduction, remediation** (line numbers are current as of this
report):

* **A — hooks could fire never (test integrity, medium).** Location: the sanitised hook helpers
  `_one_shot` (`tests/unit/scripts/test_race_substitution_deterministic.py:135`),
  `_hook_delete_boundary` (`:174`), `_hook_prune_boundary` (`:211`) — none recorded whether the
  substitution ran. Reproduction: install a hook and run a test body that performs no deletion; the
  asserted invariants then hold vacuously and the test passes green (this was literally happening for
  the prune-redirect test). Remediation: a hook registry plus an autouse fixture
  (`_INSTALLED_HOOKS` `:158`, `_substitution_hooks_must_fire` `:162`) that fails the test if any
  installed hook did not run. Retested positively (six hook-using tests still pass) and negatively
  (an injected unfired hook fails at teardown, exit 1).
* **B — collapsed failure modes (safety, medium).** Location: `scripts/cleanup_path.py:246-277`
  (`open_root_fd`), consumed by `scripts/cleanup_smoke.py:158-168` (delete),
  `scripts/cleanup_smoke.py:230-236` (prune) and `scripts/cleanup_orphan_uploads.py:354` (sweep).
  Reproduction: force the platform gate on, make `os.open` raise (`PermissionError`); before the
  fix the helper returned `None` and the caller issued a pathname `unlink()`/`rmdir()` — the guard was
  lowered precisely when the root looked wrong. Remediation: raise `RuntimeError` and refuse in all
  three callers. Retested: `test_an_unholdable_root_on_a_supporting_platform_is_a_refusal`,
  the two smoke caller tests, and `TestUnholdableRootRefusesCleanup`.
* **D — pathname delete of a failed archive (low).** Location:
  `scripts/cleanup_orphan_uploads.py` archive failure branch (`:236`, message `:244`); before the fix
  the branch called `archive.unlink()` by pathname. Reproduction: make `ZipFile.write` raise and
  observe the destination removed via a path not bound to the validated object. Remediation: the
  incomplete archive is left in place for the operator, and the next sweep refuses it (exit 3).
  Retested by the updated archive-write-failure test.
* **E — verification re-opened by pathname (low).** Location: same file, handle-bound write/verify
  (`open(archive, "x+b")` `:202`, `seek(0)` `:225`, `close()` `:250`); before the fix verification
  ran `zipfile.ZipFile(archive)` on the path. Reproduction: substitute the destination between the
  write and the verification; the pathname re-open can verify a different object. Remediation: verify
  through the creation handle. Retested by `test_verified_archive_is_written_before_deletion` — and
  by the observed failure with the write-only `"xb"` mode (§6.5).
* **F — archive-substitution test could pass on the pre-check alone (low).** Location:
  `tests/unit/scripts/test_race_substitution_deterministic.py:536-538` (the `consulted` list and
  `lying_exists`). Reproduction: leave the destination in place so the sweep aborts at its own
  `exists()` pre-check; the test still saw exit 3 with the destination untouched. Remediation: assert
  the patched `exists` was consulted **and** that the refusal came from the creation branch
  (`appeared before it could be created`, not `already exists`). Retested positively, and negatively
  by reverting the create mode to `"w"` (test fails).
* **C — `__pycache__` sweep outside the shared boundary (low, pre-existing).** Location:
  `scripts/start_server.py:61-62` (`shutil.rmtree(..., ignore_errors=True)` at import, no containment
  check). Reproduction: replace a `__pycache__` directory with a link before the sweep runs; the
  recursion would follow it. Remediation proposed, not applied: gate each candidate on
  `cleanup_path.is_under(backend_root, candidate)` plus a link/reparse-point refusal, and report
  failures instead of ignoring them. Not applied because it is not upload/cleanup/archive behaviour.
* **Residual — no descriptor arm in the application delete path.** Location:
  `storage/file_store.py` (`candidate.unlink()`, ~`:195`). Reproduction: the same substitution
  windows as §5, on the application's own delete. Remediation proposed, not applied: extend the
  descriptor-relative arm there with POSIX-marked tests, which requires the POSIX run of §9 first.
* **Residual — review independence.** Location: process, not code. Reproduction: the review is
  reproducible only by re-dispatching work in this same session; the registered `VERIFIER` contract
  in `agents/verifier.md` has no runtime registration. Remediation: an external reviewer or a
  separate environment.

---

## 12. Database lifecycle status

Documentation and source review only; **no database connection, no migration, no row mutation, no
`.env` read** occurred in this step.

* `assert_disposal_authorized`, `assert_creation_authorized`, `assert_cleanup_execution_authorized`,
  `record_created_database` and `release_database_proof` still end in unconditional refusals.
* This step **added** a function-level call site (two inline deletions in the 3E runners, §6.7) and
  **removed** none; no destructive test was made unconditional, no URL-equality check replaced an
  authorization decision, and no direct SQL deletion bypasses the boundary.
* The ten database-blocked tests remain blocked with their bodies preserved.

**Preserved, unchanged:** PostgreSQL integration **NO-GO**; migrations and database mutations
**NO-GO**; destructive cleanup **NO-GO**. The six-part infrastructure contract of Step 1.6Y §9
(external authority, live connection identity, effective privileges, non-forgeable disposable
predicate, durable evidence, independent approval) remains outstanding in full.

---

## 13. Unresolved risks

| # | Risk | Affected operation | Why it remains | Smallest safe next action |
| --- | --- | --- | --- | --- |
| 1 | **POSIX descriptor-relative deletion is unexecuted** — the mitigation exists but no POSIX run has ever exercised it | POSIX upload deletion, pruning, sweeps | no POSIX host, no CI | run `python -m pytest -q tests/unit/scripts tests/unit/documents` on Linux; keep unattended cleanup NO-GO until then |
| 2 | **Windows cleanup keeps a check-then-use residual** — parent/root redirectable between validation and `unlink`/`rmdir` | Windows upload deletion, pruning | the platform exposes no descriptor-relative delete | keep destructive cleanup NO-GO; if it is ever needed, require an operator-supervised window and an OS-level lock |
| 3 | **Final-name swap inside the validated directory** | all deletion paths | no standard-library primitive binds a name to an earlier `lstat` | bounded already; document per run; do not claim race-freedom |
| 4 | **`storage/file_store.delete_upload` remains pathname-based** | the application's own delete | duplicate production policy; POSIX arm unrunnable here | implement the descriptor-relative arm in `storage/file_store.py` with POSIX-marked tests *and* a POSIX run, or keep the app's delete operator-supervised under a NO-GO |
| 5 | **`start_server.py` `__pycache__` `rmtree(ignore_errors=True)`** | developer/import-time side effect | pre-existing, out of scope | gate it on `cleanup_path.is_under(backend_root, candidate)` and refuse link/reparse candidates; report failures instead of ignoring them |
| 6 | **Independent-review gate not satisfied** | verification process | reviewer shares model family, no terminal; `VERIFIER` not registered | obtain a review by a genuinely separate reviewer or environment; treat the current review as supplementary |
| 7 | **Incomplete archives are left on disk by design** | orphan sweep after a failed write | removing them would need a pathname unlink | operator removes them; the next sweep refuses while one exists (fail-closed) |

---

## 14. Files changed and reasons

| Path | Change | Reason |
| --- | --- | --- |
| `scripts/cleanup_path.py` | Descriptor-relative deletion helpers (`open_root_fd`, `_descend_to_parent`, `unlink_beneath`, `rmdir_beneath`, `close_root_fd`); `open_root_fd` now raises `RuntimeError` on an unholdable root; module docstring states what the helpers do and do not close | Workstream B — close the parent/root redirect window where the platform allows it, and stop collapsing the two failure modes (finding B) |
| `scripts/cleanup_orphan_uploads.py` | Root hold is fail-closed (abort, exit 1); archive destination created with exclusive `open(..., "x+b")`; write and verification share one handle; `BadZipFile` handled; incomplete archive left in place with no pathname delete | Workstream B/D/E — remove the truncating-create window, bind verification to the written object, remove the last pathname delete from the archive path |
| `scripts/cleanup_smoke.py` | `delete_upload_files` and `prune_user_dir` refuse (nothing deleted) when the validated root cannot be held on a supporting platform | Workstream B — the guard must not be lowered when the tree looks wrong |
| `evaluation/experiments/run_phase3e_integration.py` | `assert_cleanup_execution_authorized(db, operation="Phase 3E integration inline document-row cleanup")` before the inline deletes | Function-level cleanup authorization: the inline block must carry its own gate |
| `evaluation/experiments/run_phase3e_validation.py` | Same gate for `"Phase 3E validation inline document-row cleanup"` | Same |
| `tests/unit/scripts/test_race_substitution_deterministic.py` | New; hook-firing enforcement (registry + autouse fixture); archive-substitution falsification guards | Workstream C — deterministic boundary substitution, and tests that cannot pass without exercising the window (finding A/F) |
| `tests/unit/scripts/test_descriptor_relative_deletion.py` | New; platform gate, refusal logic, unlink/rmdir contract (including the new refusal contract for an unholdable root) | Workstream C — prove the refusal logic here and mark what only POSIX can prove |
| `tests/unit/scripts/test_cleanup_smoke_safety.py` | Two tests: unholdable root refuses deletion / pruning | Finding B, caller level |
| `tests/unit/scripts/test_cleanup_orphan_uploads.py` | One test: the sweep aborts when the root cannot be held; archive-write-failure test updated to the leave-the-fragment contract | Finding B and §6.6 |
| `tests/unit/evaluation/test_phase3d_upload_inline_sql_guard.py` | Extended to cover all three inline destructive blocks with per-runner operation strings | Function-level authorization coverage |
| `architecture/STEP1_6Z_FILESYSTEM_RACE_AND_INDEPENDENT_VERIFICATION_2026-10-13.md` | **new — this report** | Evidence of record |

Not changed on purpose: `storage/file_store.py`, `evaluation/artifacts.py`, `scripts/start_server.py`,
`evaluation/isolation.py`, `backend/tests/fixtures/**`, and every historical report.

---

## 15. Final readiness matrix

| Area | Conclusion | Basis |
| --- | --- | --- |
| Database-free unit tests | **GO** | 1328 passed, 23 skipped, 0 failed, exit 0 (Python 3.11 venv), identical under 3.13 |
| Upload deletion safety | **CONDITIONAL** | POSIX: descriptor-relative + fail-closed callers (unexecuted here); Windows: pathname residual |
| Directory pruning safety | **CONDITIONAL** | Same split; emptiness proved before removal; refusals reported |
| Archive cleanup safety | **CONDITIONAL** | Exclusive create + handle-bound verification + no pathname delete; a parent swap can still place the archive elsewhere (no deletion escape) |
| TOCTOU race mitigation | **PARTIAL** | Parents/root bound on POSIX; final-name swap and the whole Windows flow unchanged; POSIX unverified |
| Windows reparse-point behavior | **VERIFIED** | 22 junction tests execute and pass, 0 skipped |
| POSIX symlink behavior | **NOT VERIFIED** | No POSIX host; 9 dir-fd tests skip with reasons |
| Evidence artifact integrity | **GO** | Benchmark digest matches; reports untouched (51 files, newest 2026-10-06); 0 stray temp files; `artifacts.py` not modified |
| Database lifecycle authorization | **NO-GO** | Six-part contract outstanding; gates still refuse |
| PostgreSQL integration | **NO-GO** | No authority, no disposable-database proof |
| Unattended destructive cleanup | **NO-GO** | Windows residual (risk 2) plus unexecuted POSIX mitigation (risk 1) |
| Independent adversarial review | **NOT SATISFIED** | Same model family, no terminal; `VERIFIER` contract not a runtime agent |

---

## 16. Final verdict and recommended next step

**CONDITIONAL PASS.**

The changes delivered in this step are real and verified *within the scope this host can verify*: the
POSIX descriptor-relative deletion path exists and never falls back to a pathname delete; an
unholdable root is now a refusal rather than a silent downgrade (finding B, verified by tests that
run here); archive creation is an exclusive create and verification is bound to the written handle,
both demonstrated by tests that fail when the mitigation is reverted; a vacuous-test hole in the race
suite is closed with controls that were observed to fire in both directions; and the two inline
evaluation deletions now carry their own authorization gate. The frozen benchmark, the upload tree,
the published reports and the historical reports are provably unchanged, the working tree contains no
stray artifacts, and HEAD, the index and the repository history are untouched.

The conditions that withhold a full PASS, all of which are material:

1. **No POSIX execution occurred.** Nine POSIX-only tests skip; the descriptor-relative mitigation has
   never actually run. POSIX symlink behavior: **NOT VERIFIED**.
2. **The Windows check-then-use residual is unchanged**, and the final-name swap is not closable with
   the standard library. Unattended destructive cleanup therefore stays **NO-GO**.
3. **The independent-review gate is NOT SATISFIED** as an organisational control (same model family,
   no terminal, unregistered `VERIFIER`).
4. **PostgreSQL integration and all database mutation remain NO-GO**, with the six-part
   authorization contract outstanding.
5. The highest-value remaining item is risk 4: `storage/file_store.delete_upload` is still
   pathname-based, and it is the deletion path an attacker can most easily influence.

**Recommended next step (smallest, safest, highest value):** obtain POSIX execution — run
`python -m pytest -q tests/unit/scripts tests/unit/documents` on a Linux host or Linux CI job against
this working tree — and only then decide whether the Windows residual is acceptable, since that run
is the one piece of evidence that converts risks 1 and 3 into measured results. Do not authorize
unattended destructive cleanup, PostgreSQL integration, migrations or database mutation on the
strength of this report.

---

### Compliance statement

No database mutation, migration, real cleanup sweep, archive deletion or production-data deletion
was performed. No commit, push, reset, clean, restore, rebase or other destructive Git operation was
run: HEAD is `6baaa2a0773df66e5fb26814afbe67647fb43435` and the index is empty. No `.env` file or
credential was read. No historical safety report was overwritten. All destructive-path tests were
confined to `tmp_path`, and the temporary artifacts used for the two negative controls were removed
(`/tmp` scratch files, plus a byte-for-byte restore of the one test module that was temporarily
mutated).
