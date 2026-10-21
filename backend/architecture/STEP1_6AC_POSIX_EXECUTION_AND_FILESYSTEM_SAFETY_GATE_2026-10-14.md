# STEP 1.6AC — POSIX Execution Evidence and Filesystem Safety Gate

Date: 2026-10-14
Owner: COORDINATOR (this run)
Previous step: Step 1.6AB — POSIX Execution and Filesystem Safety Gate
Predecessors: `STEP1_6AB_…_2026-10-13.md` (`96d52e9e0297adc2`),
`STEP1_6AA_…_2026-10-13.md` (`426270a54fb91706`),
`STEP1_6Z_…_2026-10-13.md` (`1660eab85357e9eb`) — all three unchanged by this step
Verdict: **BLOCKED (POSIX execution gate) — the bounded evidence-gathering step succeeded; the
filesystem-safety gate itself has NOT passed; no production code changed.**

Every claim below is labelled one of: **EXECUTED** (a command ran this session and its output is
quoted), **SOURCE** (read from the current file), **INFERENCE** (reasoned from source, not executed),
**HISTORICAL** (carried from a predecessor report, not re-run here), **NOT VERIFIED**, or **NOT RUN**.
No database connection, migration, mutation, real cleanup sweep, commit, push or destructive Git
operation was performed; no historical report was modified; no `.env` or credential was read.

> **Process note (recorded, not hidden).** A same-family worker dispatched as the
> `INDEPENDENT_REVIEWER` returned a coordinator-style summary and additionally **wrote a draft of this
> report file**. That draft asserted that the terminal had been lost and that the negative control was
> not re-executed. **Both assertions were false** — the coordinator had terminal access throughout and
> the negative control was executed successfully (§9). The coordinator (owner of `architecture/**`)
> has replaced that draft with this corrected, executed-evidence version, and preserved the worker's
> genuine review findings in §12 with correct attribution.

---

## 1. Executive outcome

**BLOCKED on the POSIX execution gate.** The primary objective was to establish whether the existing
filesystem-safety protections can be verified on a genuine POSIX runtime. **They cannot be — no
authorized POSIX runtime exists on this host**, and installing one is out of scope.

* **POSIX execution: NOT VERIFIED — ENVIRONMENT BLOCKER** (EXECUTED, §5). The host is Git Bash / MSYS
  on Windows (`uname -s` = `MINGW64_NT-10.0-26300`). `wsl.exe` exists but reports the subsystem is
  **not installed**. `docker`, `podman`, MSYS `python3`, `act`, `gh` are absent, and the repository has
  **no CI configuration**. Nine POSIX dir_fd-only tests therefore still skip. Nothing was installed.
* **Targeted Windows test run** (EXECUTED, §10): `python -m pytest -q tests/unit/scripts
  tests/unit/documents` → **267 passed, 13 skipped, 1 warning, exit 0**. This is **Windows** evidence
  and is **not** treated as POSIX evidence.
* **Full regression** (EXECUTED, §10): `python -m pytest -q tests/unit` → **1345 passed, 23 skipped,
  exit 0** — identical to the 1.6AB baseline.
* **Compile check** (EXECUTED, §11): `compileall` over the audited packages → clean, exit 0.
* **No production code was changed** (§7). The step's default is verification; no in-scope defect met
  the six-part implementation bar while no POSIX runtime exists to execute its test, so nothing was
  edited. In particular `storage/file_store.delete_upload` was **not** touched to "demonstrate
  activity".
* **Negative control: freshly EXECUTED** (§9). Neutralizing the prune's nested-link refusal at
  `cleanup_path.py:325` made `test_a_link_nested_inside_a_pycache_is_refused` **fail (exit 1)**; the
  file was then restored **byte-identically** (SHA-256 `97dbc1b6559a402a…`before and after) and the
  test re-ran green (exit 0).
* **Independent review: NOT SATISFIED** as an organisational control (§12) — the reviewer is a
  same-family substitute with **no terminal**, and executed nothing.
* **Verification in one line:** HEAD `6baaa2a…` unchanged, working tree 385 entries unchanged, frozen
  benchmark digest and upload inventory match 1.6AB, all predecessor reports byte-identical (§14).

**Why BLOCKED and not PASS/CONDITIONAL PASS:** the single gate this step exists to move — POSIX
execution — **cannot proceed at all**, which is §14's definition of BLOCKED ("a required verification
cannot proceed because the necessary environment … is unavailable"). The bounded evidence collection
around it succeeded, so this is a *successful evidence-gathering step* (§13 of the task) but **not** a
passed filesystem-safety gate. PostgreSQL integration, migrations/DB mutation and unattended
destructive cleanup remain **NO-GO** (§18).

---

## 2. Scope, non-goals, and agent assignments

**In scope.** Re-establish and preserve the current repository state; genuinely investigate POSIX
availability; audit the current source of every destructive filesystem call site; run the approved
targeted tests on whatever genuine environment exists; obtain an adversarial review; confirm the
database/destructive-cleanup gates are untouched; produce this report.

**Non-goals (explicit).** Installing WSL, Docker, Podman, a VM, a package, or CI infrastructure;
creating or triggering a remote workflow; implementing a POSIX-only deletion arm in
`storage/file_store.delete_upload`; implementing a Windows handle-bound delete; connecting to or
mutating PostgreSQL; running migrations; running a real cleanup sweep; changing protected artifacts.

### Agent assignments (as actually dispatched — no role is claimed to have executed as a runtime agent)

| Contract name | Actual runtime agent | Ran? | Terminal? | Evidence |
| --- | --- | --- | --- | --- |
| `ORCHESTRATOR` | coordinator (this session) | yes | yes | this report; §3/§5/§9/§10/§14 |
| `ENVIRONMENT_VERIFIER` | coordinator with terminal | yes | yes | §5 probe table |
| `FILESYSTEM_SAFETY_SPECIALIST` | coordinator (terminal-aided source audit) + one `code-searcher` worker for the destructive-site sweep | yes | coordinator: yes; worker: no | §4 |
| `TEST_ENGINEER` | coordinator with terminal | yes | yes | §9, §10, §11 |
| `INDEPENDENT_REVIEWER` | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only | yes (dispatched) | **no** | §12 (substitute, **not independent**) |
| `DATABASE_SAFETY_AUDITOR` | coordinator, source inspection only | yes | yes | §13 |
| `REPORT_AUDITOR` | one `base3-fast-worker-deepseek-flash` worker, cross-check against the repository | yes (dispatched) | **no** | §12.6 (source/report consistency only; **not executed independently**) |

Substitutions and gaps are recorded rather than concealed: no named specialist is claimed to have run
as a runtime agent; the reviewer and the report-auditor are same-family workers, not organisational
controls, and neither could execute anything.

---

## 3. Initial and final repository state

| Item | Initial (EXECUTED) | Final (EXECUTED) | Evidence |
| --- | --- | --- | --- |
| Repository root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` | unchanged | `pwd`, `git rev-parse --show-toplevel` |
| Branch | `main` | `main` | EXECUTED |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | **unchanged** | `git rev-parse HEAD` (run at start and re-run at end) |
| Index (staged) | 0 files | 0 files | `git diff --cached --name-only \| wc -l` |
| Working tree | **385 entries** = 295 deleted + 35 modified + 55 untracked | **385 entries**, identical breakdown | `git status --porcelain` + `awk`/`grep` counts |
| Pre-existing user changes | preserved — nothing reset, cleaned, stashed, checked out or rebased | preserved | EXECUTED |
| `.env` / credentials | not read | not read | — |

These **exactly match the Step 1.6AB baseline** (HEAD `6baaa2a…`; 385 entries = 295 D + 35 M + 55 ??).
The Step 1.6AB report is present at
`backend/architecture/STEP1_6AB_POSIX_EXECUTION_AND_FILESYSTEM_SAFETY_GATE_2026-10-13.md` (EXECUTED
`ls`), and **all six predecessor reports reproduce their 1.6AB digests unchanged** (§14). No
discrepancy with the historical record was found.

The final count was **re-measured after the tests** and is still exactly 385 entries: the suite's
`__pycache__`/`.pytest_cache` output is git-ignored, so the targeted and full runs did not change the
tracked working-tree state. No tracked file was edited.

---

## 4. Source-grounded destructive-call-site inventory

Built from the **current** source this step with searches over `backend/` (excluding `phases/`,
`models/`, `venv/`, `**/__pycache__/**`): `shutil.rmtree`, `ignore_errors=True`,
`os.remove|os.unlink|os.rmdir|os.replace`, `.unlink(|.rmdir(`, `truncate`, `shutil.move`, plus a
`code-searcher` worker sweep. Every line number below was verified by `grep -n` against the current
file this step (EXECUTED). Every row is **SOURCE** unless marked.

| # | Operation | Source (current lines) | Validation before it | Race window | Mitigation in place | Test | This step | Residual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Application delete of an uploaded file | `storage/file_store.py:195` (`candidate.unlink()`; `delete_upload` def `:137`) | `..` refusal `:170-171`; resolved containment `_resolved_within` `:173`; link/reparse candidate+resolved `:174-176`; link-ancestor walk `:184`; `S_ISREG` `:191` | validate → pathname `unlink` | none (pathname flow) | `test_file_store_deletion_safety.py` | symlink case skipped; others passed | **OPEN — DEFERRED** |
| 2 | Cleanup after failed commit | `storage/file_store.py:201` (`cleanup_new_file` → `delete_upload`) | same | same | none | via row 1 | as row 1 | same |
| 3 | Smoke delete of named uploads | `scripts/cleanup_smoke.py:189` (`unlink_beneath`), `:248` (`user_dir.rmdir()` Windows fallback) | `intended_root` `:259`; per-candidate `validate_candidate` `:126`; `open_root_fd` `:159` | POSIX closed for parents/root; Windows open | `unlink_beneath` POSIX; fail-closed refusal if the root cannot be held | `test_cleanup_smoke_safety.py`, `test_descriptor_relative_deletion.py` | passed / 9 POSIX-only skipped | Windows swap; POSIX arm unexecuted |
| 4 | Smoke prune of a user dir | `scripts/cleanup_smoke.py:246` (`rmdir_beneath`), `:248` (`user_dir.rmdir()` Windows fallback) | `validate_candidate` `:226` (expect=directory); `open_root_fd` `:230` | as row 3 | as row 3 | as row 3 | as row 3 | as row 3 |
| 5 | Orphan sweep deletes + prunes | `scripts/cleanup_orphan_uploads.py:391` (`path.unlink()`), `:431` (`path.rmdir()`) | `intended_root` `:283`; `validate_candidate` `:179`/`:367`/`:409`; `open_root_fd` `:354`; `unlink_beneath` `:383`; `rmdir_beneath` `:422` | as row 3 | POSIX descriptor-relative | `test_cleanup_orphan_uploads.py`, `test_race_substitution_deterministic.py` | passed | as row 3 |
| 6 | Archive create/verify | `scripts/cleanup_orphan_uploads.py:202` (`open(archive, "x+b")`), verify `:216-250` | destination not inside root, not a link, pre-check, candidate validation | creation exclusive; verification handle-bound | exclusive create + same-handle CRC; failed write leaves the fragment (no pathname delete) | orphan + race tests | passed | a swapped parent can relocate the archive (no deletion escape) |
| 7 | `__pycache__` prune (server) | `scripts/start_server.py:75` → `scripts/cleanup_path.py:280` (`prune_pycache_beneath`) | `intended_root` `:301`; per-candidate `validate_candidate` `:354`; per-entry single `lstat` `:325-326` | narrow window between that `lstat` and `unlink`/`rmdir` (`:335`, `:340`) — **INFERENCE** | containment + link/reparse refusal, never traversed | `test_pycache_prune_safety.py` | passed | rename/swap inside the window (reviewer F-2) |
| 8 | `__pycache__` prune (e2e harness) | `tests/e2e/browser/test_phase6_reliability.py:44-46` → row 7 | as row 7 | as row 7 | as row 7 | source-read guards only (needs a live server) | guard tests passed; harness **NOT RUN** | as row 7 |
| 9 | Publish evaluation evidence | `evaluation/artifacts.py:233` (`os.replace`), `:236` (`temporary.unlink()`) | unique per-process temp name; `write_evidence` append-only by default | atomic `os.replace`; temp cleanup acts on its own file | append-only publication | `test_writer_collision_*` | passed | none material |
| 10 | Parser temp copy | `documents/parser.py:463` (`os.unlink` in `try/except OSError`) | n/a — parser's own `NamedTemporaryFile` | n/a | failure logged, parse outcome unaffected (1.6AB) | `test_parser_temp_cleanup.py` | passed | non-`OSError` still masks the outcome (INFERENCE) |
| 11 | Voice temp audio | `voice.py:261` | n/a — own temp file | n/a | `OSError` caught + warning | integration voice tests | NOT RUN (needs services) | none material |
| 12 | Runner fixture uploads | `evaluation/experiments/run_phase3e_integration.py:290,319,387,418,543`; `run_phase3e_validation.py:268,357,630,777,824` | each removes a path the same run created | n/a | runner-level disposal gate refuses before `main()` | guard-order tests | passed (source-read) | runs blocked anyway |
| 13 | Inline row deletions / cleanup gates in runners | `evaluation/experiments/*` `assert_cleanup_execution_authorized` sites (e.g. `run_phase3e_integration.py:518`, `run_phase3e_validation.py:586`) | `assert_cleanup_execution_authorized` immediately before | n/a | function-level gate refuses unconditionally (§13) | `test_phase3d_upload_inline_sql_guard.py` | passed | gate refuses; block unreachable |

The `code-searcher` sweep found **no** executable `shutil.rmtree`, `ignore_errors=True`, `truncate`,
or destructive `shutil.move` remaining in the searched scope — every such hit was documentation/tests
or third-party code under the forbidden `phases/phase4f_gpu/` tree. A hand-rolled recursive delete
built from unfamiliar primitives would evade this pattern search; none was found (**INFERENCE**).

---

## 5. POSIX environment investigation and execution evidence

**Result: POSIX: NOT VERIFIED — ENVIRONMENT BLOCKER.** Probes were bounded; nothing was installed.

| Probe | Command (EXECUTED) | Observed | Class |
| --- | --- | --- | --- |
| Kernel | `uname -a`, `uname -r` | `MINGW64_NT-10.0-26300 … x86_64 Msys`; `3.3.6-341.x86_64` — MSYS/Git Bash, **not POSIX** | EXECUTED |
| WSL presence | `which wsl` | `/c/Windows/system32/wsl` exists | EXECUTED |
| WSL usability | `wsl.exe --status`; `wsl.exe -l -v`; `wsl.exe -e uname -a` | stderr (UTF-16): *"The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'."*; exits 50 / 1 / 1 | EXECUTED |
| Containers | `which docker` | absent | EXECUTED |
| POSIX Python | `python --version`, `python3 --version` (in MSYS) | `command not found` for both | EXECUTED |
| Windows Python | `backend/venv/Scripts/python.exe --version` | `Python 3.11.0` | EXECUTED |
| CI runners | `which act`, `which gh` | absent (msys shell) | EXECUTED |
| Repository CI | `ls .github/workflows/`; repo-wide `*.yml`/`*.yaml` scan | **no `.github/workflows`**; only `./compose.yaml` | EXECUTED |

No POSIX runtime is available, so **no POSIX test command was executed**. Windows Git Bash is not
treated as a POSIX kernel for this purpose, and the Windows test results are not POSIX evidence. The
nine tests that would execute on POSIX and currently skip are enumerated in §10. Per the task rule,
the attempt is stopped here with the blocker recorded rather than compensated by speculative code.

---

## 6. Filesystem threat model

Cases: **A** lexical traversal, **B** link/reparse traversal, **C** object replacement,
**D** parent replacement, **E** concurrency, **F** archive substitution.

| Operation | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1–2 `file_store.delete_upload` | refused | refused (candidate, resolved, ancestor walk) | **open** (pathname `unlink`) | **open** | open | n/a |
| 3–5 cleanup smoke / orphan sweep | refused | refused | Windows **open**; POSIX name-swap only | POSIX closed, Windows open | reported | n/a |
| 6 archive | refused | refused | closed (exclusive create) | **open** (archive parent not held) | n/a | closed (same-handle verify) |
| 7–8 `__pycache__` prune | refused (`intended_root`, containment) | refused (root, candidates, every entry) | **INFERENCE**: narrow window after the per-entry `lstat` | **open** — plus the directory-swap residual (below) | n/a | n/a |
| 9 `write_evidence` | refused | n/a | closed (exclusive create, atomic `replace`) | n/a | unique temp name | n/a |
| 10 parser temp copy | n/a | n/a | n/a (own temp file) | n/a | n/a | n/a |

Boundary statement this report stands behind: **only handle-bound or descriptor-relative operations
bind a delete to the validated object.** They exist here for POSIX (rows 3–5) but not for Windows
`unlink`/`rmdir`. Nothing here is claimed to have *eliminated* a race. **Residual surfaced this step:**
in `cleanup_path._remove_validated_tree`, an entry classified as a real directory from a single `lstat`
(`:325-326`) can be swapped for a junction before the recursive call (`:334-335`); the recursion would
then list/empty the junction's target (reviewer F-2, **NOT FIXED**, low severity, bytecode-only). The
block docstring's claim that "the entry that is classified is the entry that is acted on" is **too
strong** for that specific path.

---

## 7. Implemented changes and their tests

**None — no production, test, script, evaluation or documentation source file was modified this step.**
The six-part implementation bar (§10 of the task) could not be met by any in-scope candidate change
while no POSIX runtime exists to execute its test, so the correct action was to make no change and
record the deferrals (§8). The only file written by this step is this report. This is a deliberate,
evidence-driven outcome, not a shortfall papered over with an untestable change.

---

## 8. Deferred changes and the reason for deferral

| Item | Disposition | Reason / evidence needed to revisit |
| --- | --- | --- |
| Descriptor-relative arm for `storage/file_store.delete_upload` (row 1) | **BOUNDED — DEFERRED PENDING REQUIRED TEST ENVIRONMENT** | The rules forbid untested platform-specific destructive code, and no POSIX runtime exists (§5). Evidence bar (from 1.6AB, unchanged): (i) an authorized POSIX run executing the 9 currently-skipped descriptor tests; (ii) `test_file_store_deletion_safety.py` and the upload flow passing there; (iii) a design note on safe-handle acquisition and the refusal when it cannot be acquired — never a pathname fallback; (iv) review of that specific change. |
| Windows handle-bound delete (`CreateFileW` + `SetFileInformationByHandle`) | **NOT FIXED — DEFERRED BY INSTRUCTION** | Testable on this host, but this phase forbids combining a speculative Windows-API implementation with it. Needs its own design, tests and review. |
| `cleanup_path._remove_validated_tree` directory-swap-during-recursion (reviewer F-2) | **NOT FIXED — DOCUMENTED RESIDUAL** | A fix means re-validating each subdirectory (or `O_NOFOLLOW`-opening it) immediately before recursing; testable on this Windows host with a junction. Out of this step's verification-only scope. |
| `test_every_deletion_call_is_descriptor_relative` docstring-vacuity hole for `rmdir` (reviewer F-8) | **DEFERRED — LOW PRIORITY (test-only)** | Should assert `dir_fd` on the AST call node rather than on source text (the `rmdir` docstring line itself contains `os.rmdir(... dir_fd=...)`). A bounded test-only change, but changing tests during a verification-only step was not warranted. |
| Prune docstring over-claims (reviewer F-9) | **CORRECTED IN THIS REPORT / SOURCE UNCHANGED** | Recorded accurately in §6 and here; the docstring itself was not edited (no code changes this step). |
| `documents/parser.py` non-`OSError` cleanup failure | **NO CHANGE — REASON DOCUMENTED** (1.6AB) | Widening the handler would swallow programming errors; no realistic trigger. |
| `file_store` accepting a symlinked *root* (reviewer F-4 asymmetry) | **NO CHANGE — DELIBERATE** | Operator-config provenance, not untrusted input; documented in-source. |

---

## 9. Negative-control evidence

**Status: freshly EXECUTED this step, with byte-identical restoration verified.** The control mutates
an in-tree source file in place, so it was applied only to a file that was first fingerprinted and
backed up, and restored immediately afterwards. All fixtures it uses are temporary directories; **no
real upload, archive or user file was involved.**

**Control (c) — neutralize the prune's nested-link refusal.**

| Step | Command / action (EXECUTED) | Observed |
| --- | --- | --- |
| 1. fingerprint | `sha256sum scripts/cleanup_path.py` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` |
| 2. mutate | replace `if stat.S_ISLNK(info.st_mode) or (` at `:325` with `if False and (` | mutation applied (anchor count asserted `== 1`) |
| 3. fingerprint | `sha256sum scripts/cleanup_path.py` | `414904ad9a51c253fe0d19600fc9371fa2793f0faeafa1e1cd371dee1e8618f1` (changed) |
| 4. run test | `pytest -q tests/unit/scripts/test_pycache_prune_safety.py -k test_a_link_nested_inside_a_pycache_is_refused` | **1 failed, 13 deselected — exit 1**; `FileNotFoundError: …\outside-target\precious.txt` — the nested junction was followed and its target file deleted |
| 5. restore | copy the backup back over the file; remove the backup | restored |
| 6. fingerprint | `sha256sum scripts/cleanup_path.py` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` — **byte-identical to step 1** |
| 7. re-run test | same targeted command against the restored source | **1 passed, 13 deselected — exit 0** |

The failure in step 4 is caused **for the intended reason**: disabling the link/reparse refusal lets
`_remove_validated_tree` recurse into the nested junction and delete `outside-target/precious.txt`, so
the assertion `precious.read_bytes() == b"precious"` fails. The protection is therefore load-bearing,
demonstrated by execution on this host (Windows), not merely by reading the source.

**Controls (a) and (b) — HISTORICAL (1.6AB), not re-run here.** They are preserved rather than
re-presented as new: (a) replacing the parser's `try/except OSError` cleanup with a bare `os.unlink`
made `test_a_failed_temp_copy_unlink_does_not_fail_the_parse` fail (exit 1); (b) restoring the
harness's `shutil.rmtree(..., ignore_errors=True)` sweep made the `TestE2eHarnessCallSite` guards fail
(3 failed, exit 1). Both were verified in 1.6AB; this step did not repeat them, and does not claim it
did. One freshly executed, load-bearing negative control with verified restoration satisfies the
step's requirement ("At least one meaningful negative control must be supported by recorded
evidence").

---

## 10. Test commands, counts, skips and exit codes

All commands from `backend/`; every exit status is the tested command's own. **EXECUTED this step:**

| # | Command | Observed result | Exit |
| --- | --- | --- | --- |
| 1 | `venv/Scripts/python.exe --version` | `Python 3.11.0` | 0 |
| 2 | `venv/Scripts/python.exe -m pytest -q tests/unit/scripts tests/unit/documents` | **267 passed, 13 skipped, 1 warning in 84.71s** | **0** |
| 3 | same, with `-rs` (skip reasons) | 13 skips listed below; **267 passed, 13 skipped** | **0** |
| 4 | `venv/Scripts/python.exe -m pytest -q tests/unit` (full regression) | **1345 passed, 23 skipped, 1 warning in 69.09s** | **0** |
| 5 | targeted negative-control test with source mutated (§9) | **1 failed** (exit 1), then **1 passed** (exit 0) after restore | 1 / 0 |

**Skip accounting (targeted 13 = 4 + 9; full 23 = 10 + 4 + 9), EXECUTED from the `-rs` output:**

* **4 — platform symlink-privilege skips**, each naming `WinError 1314` / "A required privilege is not
  held by the client":
  `tests/unit/documents/test_file_store_deletion_safety.py:51`,
  `tests/unit/scripts/test_cleanup_smoke_safety.py:74` and `:466`,
  `tests/unit/scripts/test_cleanup_orphan_uploads.py:145`.
* **9 — POSIX dir_fd-only tests**, each with the reason
  `requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); not available on Windows`:
  `tests/unit/scripts/test_descriptor_relative_deletion.py` (lines 114, 229, 245, 261, 282, 313, 349,
  366 = 8) and `tests/unit/scripts/test_cleanup_smoke_safety.py:385` (1).
* **10 — database-blocked tests** (present in the full-suite total; explicitly `BLOCKED`, bodies
  preserved, never counted as passes).

**Distinguishing executed from collected/skipped.** The 267 targeted passes (and the 1345 full-suite
passes) **executed** on Windows. The 9 descriptor-relative tests were **collected and skipped** — they
say nothing about POSIX descriptor semantics. No failing test was waived and no assertion was
weakened.

**NOT RUN this step (each with reason):** `tests/integration` and `tests/e2e` (the browser harness
starts its own uvicorn on port 8000); `scripts/start_server.py` (runs an Alembic migration in the app
lifespan and binds a port — prohibited); every database-blocked test; the `voice.py` integration paths
(need services). No POSIX test command was run because no POSIX runtime exists (§5).

---

## 11. Compile-check results

| Command | Result | Exit |
| --- | --- | --- |
| `venv/Scripts/python.exe -m compileall -q scripts storage documents evaluation tests/unit/scripts tests/unit/documents` | clean, no output | **0** |

No Python source file was changed this step, so this check confirms the audited tree still compiles
after the negative-control restore (§9) and adds no risk to the no-change outcome. No source-change
claim rests on a compile result.

---

## 12. Independent-review status and findings

### 12.1 Identity and independence

| Item | Value |
| --- | --- |
| Reviewer | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only |
| Scope | `scripts/cleanup_path.py`, `storage/file_store.py`, `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, `scripts/start_server.py`, `tests/unit/scripts/test_descriptor_relative_deletion.py`, `tests/unit/scripts/test_pycache_prune_safety.py`, `tests/unit/documents/test_file_store_deletion_safety.py`, `evaluation/isolation.py` |
| Self-declared | same model family; **no terminal**; executed nothing; edited no files |
| Gate | **INDEPENDENT REVIEW GATE NOT SATISFIED** |

The reviewer confirmed all its judgements are **source-read only** and that it cannot confirm any
count, digest or runtime behaviour. It also (unexpectedly) produced a coordinator-style draft of this
report, which the coordinator corrected against executed evidence (process note, top of report).
Because neither independent execution nor a distinct organisational control was available, the gate is
recorded **NOT SATISFIED**.

### 12.2 Findings and dispositions (reviewer, source-read only)

| ID | Severity | Finding (file:line) | Disposition |
| --- | --- | --- | --- |
| F-1 | high | `file_store.delete_upload` remains pathname-based after validation (`storage/file_store.py:195`) | **DEFERRED** (coordinator agrees; not fixable in a verification-only step) |
| F-2 | low | `_remove_validated_tree` can follow a directory swapped to a junction after its `lstat` (`cleanup_path.py:325-326` → recursion `:334-335`); the docstring overstates | **NOT FIXED (residual, documented)** — §6, §8 |
| F-3 | info | Containment boundary otherwise preserved; `validate_candidate` (`:200`) gates every delete | **CONFIRMED** |
| F-4 | low | Symlink/reparse checks adequate; `file_store` root-provenance asymmetry vs `intended_root` (`file_store.py:60-70`) | **CONFIRMED as deliberate** |
| F-5 | medium | Remaining check-then-use races; only F-2 can act outside the validated directory | **NOT FIXED (residual)** — §15 |
| F-6 | medium | Pathname destructive ops still outside the descriptor boundary: `file_store.py:195`, orphan `:391`/`:431`, smoke `:248` fallbacks | **DEFERRED (documented)** |
| F-7 | info | Archive create/verify sound; a failed write leaves the fragment (no pathname delete) | **FIXED AND VERIFIED (source)** |
| F-8 | low | `test_every_deletion_call_is_descriptor_relative` can pass on the `rmdir` docstring line (it contains `os.rmdir(... dir_fd=...)`) | **DEFERRED — test-only, low** (§8) |
| F-9 | low | Two prune docstrings overstate ("classified is acted on"; "not an escape from the root") | **CORRECTED IN THIS REPORT** — §6, §8 |
| F-10 | low | The symlink-refusal test for `delete_upload` skips on Windows (`WinError 1314`) | **CONFIRMED** — §10 |
| F-11 | info | Negative control (c) would fail for the intended reason | **NOW EXECUTED AND CONFIRMED** — §9 (the coordinator ran it after the reviewer's source-level prediction) |
| F-12 | high | The available evidence does not establish POSIX behaviour | **CONFIRMED — POSIX NOT VERIFIED** |
| F-13 | info | Database/hostile-lifecycle gates intact by source (`evaluation/isolation.py`) | **CONFIRMED** — §13 |

No finding was silently dismissed. The two that change how this report must be read are F-2 (a real,
low residual the docstrings understate) and F-12 (no POSIX evidence exists). Reviewer F-11 was a
source-level prediction; the coordinator subsequently **executed** it and it held (§9), upgrading that
one finding from SOURCE to EXECUTED.

### 12.5 What the reviewer could not do

Execute anything: no terminal, no pytest, no POSIX host, no file mutation. It verified no counts,
digests or manifests and claimed none. Its F-2/F-8/F-9 caveats are the actionable ones and are
recorded in §8 and §15.

### 12.6 `REPORT_AUDITOR` pass

A second `base3-fast-worker-deepseek-flash` worker was dispatched against this report with
instructions to cross-check counts, paths, line references and integrity claims against the
repository and to reject unsupported claims. It had **no terminal**, so every execution-shaped claim
was necessarily **UNVERIFIABLE-FROM-HERE** for it; its value was source/report consistency. Its
conclusions are limited accordingly and **do not** constitute independent execution verification. (The
coordinator's own line references were verified by `grep -n` against the current source; self-checking
is not audit.)

It confirmed all **18 sections present and in order**, that the cited line references match the
current source (spot-checked across `cleanup_path.py`, `file_store.py`, `cleanup_smoke.py`,
`cleanup_orphan_uploads.py`, `evaluation/isolation.py`), that the named test files and tests exist,
and that the arithmetic is internally consistent (13 = 4 + 9; 23 = 10 + 4 + 9; 267 = 122 + 145;
1345 matches 1.6AB). It raised one **real error**, which the coordinator verified and corrected:

| Auditor finding | Severity | Correction applied |
| --- | --- | --- |
| A-1: §4 row 1 cited the `..` refusal at `file_store.py:169-170`; the source has the test at `:170` and `return False` at `:171` | low | corrected to `:170-171` (§4 row 1) |

Its remaining findings were **PASS/acceptable**: it independently corroborated reviewer F-2 (the
`lstat`→recursion swap) and F-8 (the `rmdir` docstring-vacuity hole), and it correctly declined to
treat its own inability to run commands as evidence either way for the executed results. Nothing else
in the report was found stronger than a source read supports.

---

## 13. Database lifecycle gate results

Documentation and source inspection only — **no connection, migration, mutation or `.env` read.**

| Gate | Location (SOURCE) | Behaviour |
| --- | --- | --- |
| `_proof_is_live` | `evaluation/isolation.py:363` | returns `False` unconditionally |
| `record_created_database` | `:369` | raises `UnsafeEvaluationTarget` |
| `assert_disposal_authorized` | `:377` | raises `UnsafeEvaluationTarget` at the end (after isolation checks) |
| `assert_creation_authorized` | `:415` | raises `UnsafeEvaluationTarget` |
| `assert_row_cleanup_authorized` | `:443` | delegates to `assert_disposal_authorized` |
| `assert_cleanup_execution_authorized` | `:456` | raises immediately, before inspecting any caller object |
| `release_database_proof` | `:477` | raises `UnsafeEvaluationTarget` |
| `assert_engine_bound_to_proof` | `:485` | refusal path preserved |

**Status: BLOCKED — no change.** No guard was relaxed; no blocked test was made unconditional; no URL
comparison replaced an authorization decision; this step touched no lifecycle code. **PostgreSQL
integration: NOT VERIFIED. Migrations and database mutation: NO-GO.** A successful filesystem test
suite does **not** authorize database execution.

---

## 14. Protected-artifact integrity results

All measured EXECUTED this step; predecessor digests (SHA-256 prefix, first 16 hex) cross-check the
values 1.6AB recorded for the same files.

| Check | Result | Class |
| --- | --- | --- |
| Frozen benchmark `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches 1.6AB** | EXECUTED |
| Upload tree | 1212 files, 7 386 232 bytes — **matches 1.6AB** | EXECUTED |
| `UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` | `66b53544ebffd2d0` — unchanged | EXECUTED |
| `STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md` | `b0cbefef7d9cab14` — unchanged | EXECUTED |
| `STEP1_6Y_ARTIFACT_AND_FILESYSTEM_VERIFICATION_2026-10-13.md` | `92ee2315822071b2` — unchanged | EXECUTED |
| `STEP1_6Z_FILESYSTEM_RACE_AND_INDEPENDENT_VERIFICATION_2026-10-13.md` | `1660eab85357e9eb` — unchanged | EXECUTED |
| `STEP1_6AA_POSIX_VERIFICATION_AND_INDEPENDENT_SAFETY_GATE_2026-10-13.md` | `426270a54fb91706` — unchanged | EXECUTED |
| `STEP1_6AB_POSIX_EXECUTION_AND_FILESYSTEM_SAFETY_GATE_2026-10-13.md` | `96d52e9e0297adc2` — present, unchanged | EXECUTED |
| `scripts/cleanup_path.py` | `97dbc1b6559a402a` — **byte-identical after the negative control** (§9) | EXECUTED |
| HEAD / index | `6baaa2a…` unchanged; 0 staged | EXECUTED |
| Working tree | 385 entries = 295 D + 35 M + 55 ?? (re-measured after the tests) | EXECUTED |
| Stray `.tmp`/`.bak`/`.orig`/`.rej`/`~` under `backend/` (excl. `venv/`,`phases/`) | **0** | EXECUTED |

No historical report was overwritten. The only file written by this step is this report. No
negative-control residue exists: the restored file's digest equals its pre-mutation digest, and the
`.16ac.bak` backup was removed (0 stray temp files).

---

## 15. Remaining race conditions and limitations

| # | Limitation | Status | Owner (contract) |
| --- | --- | --- | --- |
| 1 | POSIX descriptor-relative deletion has never been executed | **NOT VERIFIED — ENVIRONMENT BLOCKER** | TEST_AGENT / COORDINATOR |
| 2 | Windows upload deletion keeps a check-then-use residual (`file_store.delete_upload`, cleanup scripts) | **OPEN** | BACKEND_AGENT / SECURITY_AGENT |
| 3 | Final-name swap inside a validated directory is unclosable with the standard library | **OPEN, BOUNDED** | SECURITY_AGENT |
| 4 | `storage/file_store.delete_upload` remains pathname-based | **DEFERRED** (bar in §8) | BACKEND_AGENT |
| 5 | Rename between the prune's per-entry `lstat` and its `unlink`/`rmdir` | **NARROWED — RESIDUAL RACE REMAINS** (INFERENCE) | BACKEND_AGENT |
| 6 | Directory swapped to a junction between the prune's `lstat` and its recursion (reviewer F-2) | **NOT FIXED — residual; docstring understates** | BACKEND_AGENT |
| 7 | e2e harness change has source-read evidence only (cannot run here) | **LIMITED EVIDENCE** | TEST_AGENT |
| 8 | Parser cleanup tolerates `OSError` only | **RESIDUAL, DOCUMENTED** | BACKEND_AGENT |
| 9 | `test_every_deletion_call_is_descriptor_relative` can pass on a docstring line (F-8) | **TEST WEAKNESS — DEFERRED** | TEST_AGENT |
| 10 | Independent review not satisfied as an organisational control | **NOT SATISFIED** | COORDINATOR |
| 11 | Report-auditor pass had no terminal (source/report consistency only) | **LIMITED** | COORDINATOR |

Nothing in this list is claimed closed. Items 5 and 6 are **narrowing / known residuals, not closure.**

---

## 16. Readiness matrix

| Capability | Decision | Basis |
| --- | --- | --- |
| Database-free targeted tests (scripts + documents) | **GO** | 267 passed, 13 skipped, 0 failed, exit 0 (Windows, Python 3.11.0) |
| Database-free full unit suite | **GO** | 1345 passed, 23 skipped, 0 failed, exit 0 |
| POSIX descriptor-relative deletion | **BLOCKED / NOT VERIFIED** | no POSIX runtime or CI; 9 dir_fd tests skip (§5, §10) |
| Windows filesystem deletion | **CONDITIONAL** | fail-closed refusals everywhere; check-then-use residual + final-name swap remain (rows 2–3) |
| Archive integrity | **CONDITIONAL** | exclusive create + same-handle CRC; failed write leaves the fragment; a swapped archive parent can relocate the archive with no deletion escape |
| `__pycache__` pruning | **CONDITIONAL** | guarded, contained, refusals reported; F-2 directory-swap residual remains |
| Independent safety review | **NOT SATISFIED** | same-family, non-executing reviewer |
| Report audit | **NOT SATISFIED** | auditor had no terminal (§12.6) |
| PostgreSQL integration | **NO-GO** | six-part contract outstanding |
| Migrations and database mutation | **NO-GO** | unchanged |
| Unattended destructive cleanup | **NO-GO** | limitations 1–6 outstanding |

A green suite authorizes nothing beyond database-free tests; it does not authorize database work,
migrations, or unattended cleanup.

---

## 17. Exact next actions

1. **Obtain a POSIX execution result** — the only action that moves limitation 1 from NOT VERIFIED to
   measured. On a Linux host or an authorized Linux CI job checked out at this tree, run
   `python -m pytest -q tests/unit/scripts tests/unit/documents` and capture OS, Python version, exact
   command, exit code, and pass/skip counts, with the nine descriptor tests **executing** instead of
   skipping. Adding CI configuration is out of scope until such a runner is authorized.
2. **Fix F-2 properly:** re-validate each subdirectory (or `O_NOFOLLOW`-open it) immediately before
   recursing in `cleanup_path._remove_validated_tree`, with a junction-based negative control on this
   Windows host, and correct the two over-claiming docstrings (F-9). This warrants a change-and-test
   step, not this verification-only step.
3. **Harden the F-8 test** to assert `dir_fd` on the AST call node rather than on source text.
4. **Then, and only then, design the `file_store.delete_upload` POSIX arm** to the four-part evidence
   bar in §8 (POSIX run first; never a pathname fallback), and separately design the Windows
   handle-bound delete.
5. **Standing:** keep PostgreSQL integration, migrations and unattended destructive cleanup **NO-GO**
   until their separate prerequisites are satisfied and independently approved.

---

## 18. Explicit final authorization decision

| Decision | Status |
| --- | --- |
| Database-free targeted tests (scripts + documents) | **AUTHORIZED** — 267/13/0, exit 0 |
| Database-free full unit suite | **AUTHORIZED** — 1345/23/0, exit 0 |
| POSIX descriptor-relative deletion | **NOT AUTHORIZED as verified — BLOCKED (no POSIX runtime)** |
| Windows filesystem deletion in the application path | **CONDITIONAL** — supervised use only; residual unchanged |
| Archive-based cleanup sweep | **CONDITIONAL** — supervised, with the script's own archive preconditions |
| `__pycache__` pruning (server script, e2e harness) | **AUTHORIZED (guarded, contained)** — with the F-2 residual recorded |
| PostgreSQL integration | **NOT AUTHORIZED — NO-GO** |
| Migrations / database mutation | **NOT AUTHORIZED — NO-GO** |
| Unattended destructive cleanup | **NOT AUTHORIZED — NO-GO** until limitations 1–6 are closed or explicitly accepted by an independent authority |
| Independent safety review gate | **NOT SATISFIED** — no authorization may rest on §12 |
| Report audit | **NOT SATISFIED** — §12.6 |

**Overall: BLOCKED.** The bounded evidence-gathering step succeeded — baseline measured and preserved,
POSIX availability genuinely investigated, current-source safety audit complete, targeted and full
Windows tests green with a clean compile, and one load-bearing negative control freshly executed with
byte-identical restoration. But the **single gate this step exists to move (POSIX execution) could not
be attempted** because no POSIX runtime exists and installing one is out of scope. No production code
was changed; every database and destructive-cleanup restriction is intact; and no PASS or
authorization claim beyond the recorded database-free tests is made.

---

### Compliance statement

No PostgreSQL connection, migration, mutation or reset; no real cleanup sweep, archive deletion or
user-upload deletion; no `.env` file or credential read; no WSL, Docker, Podman, VM, package or CI
infrastructure installed; no remote workflow created or triggered; no `git reset`, `clean`, `restore`,
stash, checkout, rebase, commit or push; no historical report overwritten (all predecessor digests
reproduced unchanged). The one source file mutated for the negative control was restored
byte-identically (digest-verified) and the affected test re-ran green; its backup was removed and the
tree holds 0 stray temp files. The limitation that governs this step — no POSIX execution — is stated
at the top of §1 and in §5/§15 rather than hidden.
