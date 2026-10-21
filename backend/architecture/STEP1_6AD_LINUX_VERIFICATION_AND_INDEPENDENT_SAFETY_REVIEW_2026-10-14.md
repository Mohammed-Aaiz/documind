# STEP 1.6AD — Authorized Linux Verification and Independent Filesystem Safety Review

Date: 2026-10-14
Owner: COORDINATOR (this run)
Predecessor: `STEP1_6AC_POSIX_EXECUTION_AND_FILESYSTEM_SAFETY_GATE_2026-10-14.md` (`6cafb8ab94741c76`) — unchanged by this step
Verdict: **BLOCKED — no authorized Linux/POSIX runtime is available.** The bounded evidence-gathering
step is complete; the filesystem-safety gate has **not** passed. No production code was changed.

Every claim below is labelled one of: **EXECUTED** (a command ran this session and its output is
quoted), **SOURCE** (read from the current file), **INFERENCE** (reasoned from source, not executed),
**HISTORICAL** (carried from a predecessor report, not re-run here), **SKIPPED** (collected but not
run), **REVIEWER** (an assessment by a non-executing reviewer), **NOT VERIFIED**, or **NOT RUN**. No
database connection, migration, mutation, real cleanup sweep, commit, push or destructive Git
operation was performed; no historical report was overwritten; no `.env` or credential was read.

---

## 1. Executive outcome

**BLOCKED on the Linux execution gate.** The primary objective was to execute the existing targeted
safety tests on a genuine Linux/POSIX runtime and to obtain a genuinely independent review.
**No authorized Linux runtime exists on this host**, and installing one is prohibited this step.

* **Linux/POSIX execution: BLOCKED — NO AUTHORIZED LINUX RUNTIME AVAILABLE** (EXECUTED, §5). The host
  is Git Bash / **MSYS** on Windows (`uname -s` = `MINGW64_NT-10.0-26300`, `/bin/bash` =
  `5.2.12(1)-release (x86_64-pc-msys)`). `wsl.exe` reports the subsystem is **not installed**;
  `docker`/`podman`/MSYS `python3`/`act`/`gh` are absent; the repository has **no CI configuration**.
  The nine POSIX dir_fd-only tests therefore still **skip**. Nothing was installed.
* **Windows targeted run** (EXECUTED, §10): `python -m pytest -q tests/unit/scripts tests/unit/documents`
  → **267 passed, 13 skipped, exit 0**. **Windows** evidence only; **not** Linux evidence.
* **Windows full regression** (EXECUTED, §10): `python -m pytest -q tests/unit` → **1345 passed,
  23 skipped, exit 0**.
* **Compile check** (EXECUTED, §11): `compileall` over the audited packages → clean, exit 0.
* **No production code was changed** (§7). Every in-scope candidate change failed the implementation
  bar because its behaviour cannot be executed on the affected platform (§11). In particular
  `storage/file_store.delete_upload` was **not** touched, and the directory-swap race was **not**
  "fixed" with speculative code.
* **Negative control: freshly EXECUTED with byte-identical restoration** (§9). Neutralizing the prune's
  nested-link refusal at `cleanup_path.py:325` made
  `test_a_link_nested_inside_a_pycache_is_refused` **fail (exit 1)**; the file was restored to its
  pre-mutation SHA-256 (`97dbc1b6559a402a…`) and the test re-ran green (exit 0). No control marker or
  backup remains.
* **Directory-swap race: analysed against current source and recorded as NOT FIXED** (§6, §15). The
  reviewer disputes the predecessor's "bytecode-only / low severity" wording: a directory swap between
  the `lstat` and the recursion in `cleanup_path._remove_validated_tree` can let `iterdir()` **follow a
  junction and delete the target's contents, which may lie outside the root** (REVIEWER R-3). This
  severity correction is adopted in this report.
* **`storage/file_store.delete_upload`: assessed, DEFERRED** (§7.2, §8, §15). It remains
  pathname-based (`file_store.py:195`) with a residual check-then-use window; a POSIX arm or Windows
  handle-bound delete requires execution evidence this host cannot produce.
* **Independent review: NOT SATISFIED** as an organisational control (§12). The reviewer is a
  same-family substitute with **no terminal**; it executed nothing.
* **Verification in one line:** HEAD `6baaa2a…` unchanged, working tree 385 entries unchanged, frozen
  benchmark digest and upload inventory match the historical values, and all predecessor reports are
  byte-identical (§14).

**Why BLOCKED and not PASS/CONDITIONAL PASS:** the single gate this step exists to move — genuine
Linux execution — **cannot proceed at all**, which is §15's definition of BLOCKED. The bounded evidence
collection around it succeeded, so this is a *complete evidence-gathering step* (§14 of the task) but
**not** a passed filesystem-safety gate. PostgreSQL integration, migrations/DB mutation and unattended
destructive cleanup remain **NO-GO** (§18).

---

## 2. Scope, non-goals, and agent assignments

**In scope.** Verify and preserve the repository baseline; genuinely investigate Linux/POSIX
availability without installing anything; audit the current source of every destructive filesystem call
site; analyse the directory-swap race; assess `storage/file_store.delete_upload`; re-run a negative
control with verified restoration; obtain an adversarial review; confirm the database/destructive-
cleanup gates are untouched; produce this report.

**Non-goals (explicit).** Installing WSL, Docker, Podman, a VM, a package, or CI infrastructure;
provisioning cloud resources; creating or triggering a remote workflow; implementing a POSIX-only arm
in `file_store.delete_upload`; implementing a Windows handle-bound delete; closing the directory-swap
race with speculative code; connecting to or mutating PostgreSQL; running migrations; running a real
cleanup sweep; changing protected artifacts; letting any worker write the coordinator-owned report.

### Agent assignments (as actually dispatched — a role name is not proof of execution)

| Contract name | Actual runtime agent | Ran? | Terminal? | Evidence |
| --- | --- | --- | --- | --- |
| `ORCHESTRATOR` | coordinator (this session) | yes | yes | this report; §3/§5/§9/§10/§14 |
| `LINUX_ENVIRONMENT_VERIFIER` | coordinator with terminal | yes | yes | §5 probe table |
| `FILESYSTEM_SAFETY_SPECIALIST` | coordinator (terminal-aided source audit) + one `code-searcher` worker for the destructive-site sweep | yes | coordinator: yes; worker: no | §4, §6 |
| `POSIX_TEST_ENGINEER` | coordinator with terminal | yes | yes | §9, §10, §11 |
| `INDEPENDENT_SECURITY_REVIEWER` | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only | yes (dispatched) | **no** | §12 (substitute, **not independent**; wrote no files) |
| `DATABASE_SAFETY_AUDITOR` | coordinator, source inspection only | yes | yes | §13 |
| `REPORT_AUDITOR` | one `base3-fast-worker-deepseek-flash` worker, cross-check against the repository, no writes | yes (dispatched) | **no** | §12.11 (source/report consistency only) |

Substitutions and gaps are recorded rather than concealed: no named specialist is claimed to have run
as a runtime agent; the reviewer and the report-auditor are same-family workers, not organisational
controls, and neither could execute anything. Neither wrote or modified any file.

---

## 3. Initial and final repository state

| Item | Initial (EXECUTED) | Final (EXECUTED) | Evidence |
| --- | --- | --- | --- |
| Repository root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` | unchanged | `pwd`, `git rev-parse --show-toplevel` |
| Branch | `main` | `main` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | **unchanged** | `git rev-parse HEAD` (start and end) |
| Index (staged) | 0 files | 0 files | `git diff --cached --name-only \| wc -l` |
| Working tree | **385 entries** = 295 deleted + 35 modified + 55 untracked | **385 entries**, identical breakdown | `git status --porcelain` + `awk`/`grep` counts |
| Pre-existing user changes | preserved — nothing reset, cleaned, stashed, checked out or rebased | preserved | EXECUTED |
| `.env` / credentials | not read | not read | — |
| Stray `.tmp`/`.bak`/`.orig`/`.rej`/`~` under `backend/` (excl. `venv/`,`phases/`) | 0 | **0** | `find` |

These **exactly match the Step 1.6AC baseline** (HEAD `6baaa2a…`; 385 = 295 D + 35 M + 55 ??; 0
staged). The Step 1.6AC report is present and **unchanged** (`6cafb8ab94741c76`), and the earlier
predecessors are unchanged (`STEP1_6AB` `96d52e9e0297adc2`, `STEP1_6AA` `426270a54fb91706`). No
discrepancy with the historical record was found. The final count was re-measured after the test runs
and the negative control; the suite's `__pycache__`/`.pytest_cache` output is git-ignored, so the
tracked working-tree state did not change.

---

## 4. Source-grounded destructive-call-site inventory

Built from the **current** source this step (line numbers re-verified by `grep -n`), including a
`code-searcher` worker sweep. Every row is **SOURCE** unless marked.

| # | Operation | Source (current lines) | Validation before it | Race window | Mitigation | Test | This step | Residual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Application delete of an uploaded file | `storage/file_store.py:195` (`candidate.unlink()`; `delete_upload` def `:137`) | `..` refusal `:170-171`; resolved containment `_resolved_within` `:173`; link/reparse candidate+resolved `:176`; link-ancestor walk `_has_link_ancestor` `:184`; `S_ISREG` `:191` | validate → pathname `unlink` (TOCTOU) | none (pathname flow) | `test_file_store_deletion_safety.py` | symlink case **skipped**; others passed | **OPEN — DEFERRED** |
| 2 | Cleanup after failed commit | `storage/file_store.py:201` (`cleanup_new_file` → `delete_upload`) | same | same | none | via row 1 | as row 1 | same |
| 3 | Smoke delete of named uploads | `scripts/cleanup_smoke.py:189` (`unlink_beneath`); Windows fallback path at the `delete_upload(resolved, root=root)` call in `delete_upload_files` (`:194`) | `intended_root` `:259`; `validate_candidate` `:126`; `open_root_fd` `:159` | POSIX closed for parents/root; Windows open | `unlink_beneath` POSIX; fail-closed refusal if the root cannot be held | `test_cleanup_smoke_safety.py`, `test_descriptor_relative_deletion.py` | passed / 9 POSIX-only **SKIPPED** | Windows swap; POSIX arm unexecuted |
| 4 | Smoke prune of a user dir | `scripts/cleanup_smoke.py:246` (`rmdir_beneath`), `:248` (`user_dir.rmdir()` — Windows fallback only when `root_fd is None`) | `validate_candidate` `:226` (expect=directory); `open_root_fd` `:230` | as row 3 | as row 3 | as row 3 | as row 3 | as row 3 |
| 5 | Orphan sweep deletes + prunes | `scripts/cleanup_orphan_uploads.py:391` (`path.unlink()`), `:431` (`path.rmdir()`) | `intended_root` `:283`; `validate_candidate` `:179`/`:367`/`:409`; `open_root_fd` `:354`; `unlink_beneath` `:383`; `rmdir_beneath` `:422` | as row 3 | POSIX descriptor-relative | `test_cleanup_orphan_uploads.py`, `test_race_substitution_deterministic.py` | passed | as row 3 |
| 6 | Archive create/verify | `scripts/cleanup_orphan_uploads.py:202` (`open(archive, "x+b")`), verify `~:216-250` | destination not inside root, not a link, pre-check, candidate validation | exclusive create; verification handle-bound | exclusive create + same-handle CRC; failed write leaves the fragment (no pathname delete) | orphan + race tests | passed | a swapped parent can relocate the archive (no deletion escape) |
| 7 | `__pycache__` prune (server) | `scripts/start_server.py:75` → `scripts/cleanup_path.py:280` (`prune_pycache_beneath`; inner `_remove_validated_tree` `:305`) | `intended_root` `:301`; per-candidate `validate_candidate` `:354`; **per-entry single `lstat` `:321`**, refusal `:325-327`, recursion `:331-332`, `unlink` `:335`, `rmdir` `:340` | `lstat` → recursion (directory-swap; see §6) | containment + link/reparse refusal at each named entry, never intentionally traversed | `test_pycache_prune_safety.py` | passed | **directory-swap residual — NOT FIXED (§6)** |
| 8 | `__pycache__` prune (e2e harness) | `tests/e2e/browser/test_phase6_reliability.py:44-46` → row 7 | as row 7 | as row 7 | as row 7 | source-read guards only (needs a live server) | guard tests passed; harness **NOT RUN** | as row 7 |
| 9 | Publish evaluation evidence | `evaluation/artifacts.py:233` (`os.replace`), `:236` (`temporary.unlink()`) | unique per-process temp name; `write_evidence` append-only | atomic `os.replace`; temp cleanup acts on its own file | append-only publication | `test_writer_collision_*` | passed | none material |
| 10 | Parser temp copy | `documents/parser.py:463` (`os.unlink` in `try/except OSError`) | n/a — parser's own `NamedTemporaryFile` | n/a | failure logged, parse outcome unaffected (1.6AB) | `test_parser_temp_cleanup.py` | passed | non-`OSError` still masks the outcome (**INFERENCE**) |
| 11 | Voice temp audio | `voice.py:261` | n/a — own temp file | n/a | `OSError` caught + warning | integration voice tests | **NOT RUN** (needs services) | none material |
| 12 | Runner fixture uploads | `evaluation/experiments/run_phase3e_integration.py:290,319,387,418,543`; `run_phase3e_validation.py:268,357,630,777,824` | each removes a path the same run created | n/a | runner-level disposal gate refuses before `main()` | guard-order tests | passed (source-read) | runs blocked anyway |
| 13 | Runner inline row deletions / cleanup gates | `evaluation/experiments/*` `assert_cleanup_execution_authorized` sites (e.g. `run_phase3e_integration.py:518`, `run_phase3e_validation.py:586`) | `assert_cleanup_execution_authorized` immediately before | n/a | function-level gate refuses unconditionally (§13) | `test_phase3d_upload_inline_sql_guard.py` | passed | gate refuses; block unreachable |

The sweep found **no** executable `shutil.rmtree`, `ignore_errors=True`, `truncate`, or destructive
`shutil.move` remaining in the searched scope — every such hit was documentation/tests or third-party
code under the forbidden `phases/phase4f_gpu/` tree. A hand-rolled recursive delete built from
unfamiliar primitives would evade this pattern search; none was found (**INFERENCE**).

---

## 5. Linux environment investigation and execution evidence

**Result: LINUX EXECUTION: BLOCKED — NO AUTHORIZED LINUX RUNTIME AVAILABLE.** Probes were bounded;
nothing was installed.

| Probe | Command (EXECUTED) | Observed | Class |
| --- | --- | --- | --- |
| Kernel / OS | `uname -a`, `uname -s`, `uname -r` | `MINGW64_NT-10.0-26300 … x86_64 Msys`; `3.3.6-341.x86_64` — MSYS/Git Bash on Windows, **not Linux** | EXECUTED |
| Shell | `ls /bin/bash`; `/bin/bash --version` | `GNU bash, version 5.2.12(1)-release (x86_64-pc-msys)` — GNU bash, but an **MSYS** build, not a Linux runtime | EXECUTED |
| WSL presence | `/c/Windows/system32/wsl.exe --status` | stderr (UTF-16): *"The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'."* | EXECUTED |
| WSL usability | `wsl.exe -l -v` | same "not installed" message | EXECUTED |
| Containers | `which docker podman` | both absent | EXECUTED |
| POSIX Python | `python --version`, `python3 --version`, `ls /usr/bin/python*` | `command not found`; no `/usr/bin/python*` | EXECUTED |
| CI runners | `which act gh` | absent | EXECUTED |
| Repository CI | `ls .github/workflows`; check `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci` | **no `.github/workflows`**; no other CI config | EXECUTED |
| Windows Python | `backend/venv/Scripts/python.exe --version` | `Python 3.11.0` | EXECUTED |

No Linux runtime is available, so **no Linux test command was executed**, and the required initial
command (`python -m pytest -q tests/unit/scripts tests/unit/documents`) was **not run on Linux**.
MSYS Git Bash is **not** treated as a Linux kernel for this purpose, and the Windows results are not
Linux evidence. Per the task rule, the execution attempt stops here with the blocker recorded rather
than compensated by untested platform-specific code.

---

## 6. Filesystem threat model and the directory-swap race

Cases: **A** lexical traversal, **B** link/reparse traversal, **C** object replacement, **D** parent
replacement, **E** concurrency, **F** archive substitution.

| Operation | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1–2 `file_store.delete_upload` | refused | refused (candidate, resolved, ancestor walk) | **open** (pathname `unlink`) | **open** | open | n/a |
| 3–5 cleanup smoke / orphan sweep | refused | refused | Windows **open**; POSIX name-swap only | POSIX closed, Windows open | reported | n/a |
| 6 archive | refused | refused | closed (exclusive create) | **open** (archive parent not held) | n/a | closed (same-handle verify) |
| 7–8 `__pycache__` prune | refused (`intended_root`, containment) | refused at each named entry | **open — directory swap in `_remove_validated_tree` (§6.1)** | **open** (parents not held) | **open** | n/a |
| 9 `write_evidence` | refused | n/a | closed (exclusive create, atomic `replace`) | n/a | unique temp name | n/a |
| 10 parser temp copy | n/a | n/a | n/a (own temp file) | n/a | n/a | n/a |

Boundary statement this report stands behind: **only handle-bound or descriptor-relative operations
bind a delete to the validated object.** They exist here for POSIX (rows 3–5) but not for Windows
`unlink`/`rmdir`, and they are **not** used by the `__pycache__` prune (row 7), which is pathname-based
on **both** platforms.

### 6.1 The directory-swap race (Workstream D) — answers with source evidence

Implementation of record: `scripts/cleanup_path.py`, `prune_pycache_beneath` (`:280`) and its inner
helper `_remove_validated_tree` (`:305`).

1. **Which operations occur between the safety check and recursive use?** For each entry the helper
   calls `os.lstat(entry)` (`:321`), classifies it from that one result, refuses `S_ISLNK` /
   `FILE_ATTRIBUTE_REPARSE_POINT` (`:325-327`), and for a directory calls
   `_remove_validated_tree(entry)` (`:331-332`). **There is no re-validation of `entry` between the
   `lstat` and the recursion.** The only binding check is the outer `validate_candidate(root,
   candidate, …)` at `:354`, which applies to the top-level `__pycache__` name, not to nested entries.
2. **Can the checked entry be replaced during that interval?** **Yes.** A concurrent process (or a
   local attacker with write access to the parent) can rename the classified directory away and
   substitute a junction/symlink in the same name before `:332`.
3. **Could traversal reach an object outside the intended root?** **Yes — this is an escape channel.**
   The recursion begins with `entries = sorted(directory.iterdir())` (`:315`). On Windows a directory
   junction is followed by `iterdir()`, so the enumeration lists the **target's** contents; those
   entries are real files/directories from the subsequent `lstat`'s point of view, and the helper then
   `os.unlink`s them (`:335`) and recurses. The result can be **deletion of files outside the root** —
   **not** merely "a stale bytecode name" (REVIEWER R-3).
4. **Does the POSIX descriptor-relative path eliminate the relevant race?** **No.** The
   descriptor-relative helpers (`unlink_beneath` `:437`, `rmdir_beneath` `:483`) are **not** used by
   `prune_pycache_beneath`; the prune is pathname-based (`os.unlink(entry)` / `os.rmdir(directory)` /
   `iterdir()` for traversal) on every platform.
5. **Does the Windows path retain a residual race?** **Yes**, and so does the POSIX path for the
   prune. In addition, rows 1–2 (Windows and POSIX `file_store.delete_upload`) and the Windows
   fallbacks in `cleanup_smoke.py:248` retain their own pathname check-then-use windows.
6. **Which test demonstrates the protection?** `test_pycache_prune_safety.py`:
   `test_a_link_nested_inside_a_pycache_is_refused` (`:222`) and
   `test_a_linked_pycache_is_refused_and_its_target_survives` (`:201`) show that a link **already
   present** at `lstat` time is refused and its target survives.
7. **Which test demonstrates the residual race?** **None.** No test performs a swap between the
   `lstat` and the recursion (e.g. hooking `os.lstat` to return DIR and then substituting a junction
   to a populated target). The residual is therefore established by source reasoning only.
8. **What additional runtime evidence is needed?** A test that performs the swap between
   classification and recursion and asserts the target survives; a `prune_pycache_beneath` fix that
   re-validates each subdirectory (or opens it `O_NOFOLLOW` and acts through the descriptor)
   immediately before recursing; the docstring at `:306-309` (which asserts "the entry that is
   classified is the entry that is acted on") corrected to state the residual; and Linux execution of
   the descriptor-relative suite.

**Disposition: NOT FIXED (residual, confirmed).** No speculative fix was attempted, because the
affected platform can neither be exercised here (no Linux) nor be proven safe for the junction case
without a new test; per §11 of the task the change is deferred with the evidence requirement recorded
(§8). Severity is recorded as **medium** (out-of-root deletion channel under a local race), correcting
the predecessor's "bytecode-only / low" wording (REVIEWER R-3, R-10 — adopted).

---

## 7. Verification results and implemented changes

**No production code was changed this step.** No candidate change met the seven-part implementation bar
(§11 of the task) in the available environment; the correct action was to verify, record the deferrals,
and make no edit. The only file written by this step is this report.

### 7.1 Verification performed (EXECUTED)

| Check | Command | Result | Exit |
| --- | --- | --- | --- |
| Targeted suite | `venv/Scripts/python.exe -m pytest -q tests/unit/scripts tests/unit/documents` | 267 passed, 13 skipped | 0 |
| Full unit suite | `venv/Scripts/python.exe -m pytest -q tests/unit` | 1345 passed, 23 skipped | 0 |
| Compile | `… -m compileall -q scripts storage documents evaluation tests/unit/scripts tests/unit/documents` | clean | 0 |
| Negative control | mutate `cleanup_path.py:325` → test → restore → test | fail(1) → restore → pass(0) | 1 / 0 |

### 7.2 `storage/file_store.delete_upload` assessment (Workstream E) — no change

Read from the current `storage/file_store.py` (`delete_upload` def `:137`).

* **How upload paths are validated.** `candidate` is coerced from `stored_path` (`:159`); `base` is
  `root` if supplied else `settings.upload_path` (`:160`). All failures return `False` (fail closed).
* **How `..` components are rejected.** `if ".." in candidate.parts: return False` (`:170-171`),
  refused explicitly rather than left to `os.path.abspath`, which folds `..` textually and is not
  symlink-aware.
* **How containment is established.** `_resolved_within(base, candidate)` (`def :97`, call `:173`)
  resolves both and requires `candidate.relative_to(root)` with no `..` part — component-wise, so
  sibling-name prefixes are not accepted.
* **How symlinks and reparse points are handled.** `_is_link_or_reparse_point(candidate)` **and**
  `…(resolved)` are both refused (`:176`); `_is_link_or_reparse_point` (`def :80`) uses `is_symlink()` OR
  the `FILE_ATTRIBUTE_REPARSE_POINT` bit (needed for NTFS junctions).
* **How ancestors are checked.** `_has_link_ancestor(lexical_root, lexical_candidate)` (`def :117`,
  call `:184`) walks the **lexical** path from root downward and fails closed if the candidate is not
  lexically under the root.
* **How regular-file status is established.** `candidate.lstat()` then `stat.S_ISREG(info.st_mode)`
  (`:188-191`); a non-regular file is refused.
* **Where the final unlink occurs.** `candidate.unlink()` (`:195`) — a **pathname** delete.
* **Which race windows remain.** Between the last check (`S_ISREG` at `:191`) and `unlink()` at `:195`
  — and between resolution at `:173` and `unlink()` — a concurrent process can swap the final object
  or a parent for a link. Bounded to what `unlink` can reach; the deletion can act on an object other
  than the one validated.
* **Is a POSIX descriptor-relative alternative already available?** `cleanup_path.unlink_beneath`
  exists, but `file_store` **deliberately does not import** from `scripts/` (production must not
  depend on the operational package; stated in-source at `file_store.py:60-70`), and its contract
  (hold a root fd + a root-relative path, no pathname fallback) differs from `delete_upload`'s
  `stored_path` contract. **It cannot be applied safely without a design note and execution
  evidence** — applying it naively would either add an untested POSIX branch or a pathname fallback
  that defeats the boundary.
* **Which tests execute on Windows vs require POSIX.** `test_file_store_deletion_safety.py` runs on
  Windows but its **symlink case skips** (`:51`, `WinError 1314`); POSIX-only descriptor behaviour is
  covered by `test_descriptor_relative_deletion.py` (8 methods, **all SKIPPED** here).

**Disposition: DEFERRED** (§8). No POSIX arm and no Windows handle-bound delete were added, because
neither can be executed on the affected platform in this environment.

---

## 8. Deferred changes and reasons for deferral

| Item | Disposition | Reason / evidence needed to revisit |
| --- | --- | --- |
| Directory-swap race in `cleanup_path._remove_validated_tree` (`:321` → `:332`; see §6.1) | **NOT FIXED — DOCUMENTED RESIDUAL** | A safe fix re-validates each subdirectory (or opens it `O_NOFOLLOW`) immediately before recursing. It must be proven with a race test (swap between classification and recursion) on Windows, and reviewed. Adding speculative code without that test is prohibited by §11. |
| Prune docstring at `cleanup_path.py:306-309` ("classified is acted on") | **CORRECTED IN THIS REPORT / SOURCE UNCHANGED** | Recorded accurately in §6; the docstring itself was not edited (no code changes this step). |
| `test_every_deletion_call_is_descriptor_relative` docstring-vacuity hole for `rmdir` (R-7) | **NOT FIXED — test-only, deferred** | The assertion can pass on the `rmdir_beneath` docstring line, which contains `os.rmdir(name, dir_fd=...)`. Fix = assert `dir_fd` on the AST `ast.Call` node. A bounded test-only change, not made during a verification-only step. |
| Descriptor-relative arm for `storage/file_store.delete_upload` (§7.2) | **DEFERRED PENDING REQUIRED TEST ENVIRONMENT** | Forbidden without execution evidence; the four-part bar (POSIX run executing the 9 skipped tests; upload-flow pass; design note on safe-handle acquisition and refusal, never a pathname fallback; review) is unmet. |
| Windows handle-bound delete (`CreateFileW` + `SetFileInformationByHandle`) | **NOT FIXED — DEFERRED BY INSTRUCTION** | Testable on this host in principle, but this phase forbids combining a speculative Windows-API implementation with it. Needs its own design, tests and review. |
| `documents/parser.py` non-`OSError` cleanup failure | **NO CHANGE — REASON DOCUMENTED** (1.6AB) | Widening the handler would swallow programming errors; no realistic trigger. |
| `file_store` accepting a symlinked *root* (R-4 asymmetry) | **NO CHANGE — DELIBERATE** | Operator-config provenance, not untrusted input; documented in-source. |

---

## 9. Negative-control evidence

**Status: freshly EXECUTED this step (1.6AD), with byte-identical restoration verified.** The control
mutates an in-tree source file in place, so it was applied only to a file that was first fingerprinted
and backed up, and restored immediately afterwards. All fixtures are temporary directories; **no real
upload, archive or user file was involved.** No real cleanup sweep was run.

**Control — neutralize the prune's nested-link refusal.**

| Step | Command / action (EXECUTED) | Observed |
| --- | --- | --- |
| 1. fingerprint | `sha256sum scripts/cleanup_path.py` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` |
| 2. mutate | replace `if stat.S_ISLNK(info.st_mode) or (` at `:325` with `if False and (` | applied (anchor count asserted `== 1`) |
| 3. fingerprint | `sha256sum scripts/cleanup_path.py` | `414904ad9a51c253fe0d19600fc9371fa2793f0faeafa1e1cd371dee1e8618f1` (changed) |
| 4. run test | `pytest -q tests/unit/scripts/test_pycache_prune_safety.py -k test_a_link_nested_inside_a_pycache_is_refused` | **1 failed, 13 deselected — exit 1** (the nested junction was followed; its target file was deleted) |
| 5. restore | copy the backup back; remove the backup | restored |
| 6. fingerprint | `sha256sum scripts/cleanup_path.py` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` — **byte-identical to step 1** |
| 7. re-run test | same command against the restored source | **1 passed, 13 deselected — exit 0** |
| 8. residue check | `grep -n 'if False and (' scripts/cleanup_path.py`; `find … -name '*.16ad.bak'` | **no mutation marker remains; no backup remains** |

The failure in step 4 is caused **for the intended reason**: disabling the link/reparse refusal lets
`_remove_validated_tree` recurse into the nested junction and delete the target's `precious.txt`, so
`assert precious.read_bytes() == b"precious"` fails. The protection is therefore load-bearing, proven
by execution on this host (Windows), not merely by reading the source. The reviewer concurred
(R-8: FIXED AND VERIFIED on the strongly-supported understanding that this was executed; it marks the
digests/exit codes UNVERIFIABLE-FROM-HERE because it has no terminal).

---

## 10. Test commands, counts, skips and exit codes

All commands from `backend/`; every exit status is the tested command's own. **EXECUTED this step:**

| # | Command | Observed result | Exit |
| --- | --- | --- | --- |
| 1 | `venv/Scripts/python.exe --version` | `Python 3.11.0` | 0 |
| 2 | `venv/Scripts/python.exe -m pytest -q tests/unit/scripts tests/unit/documents` | **267 passed, 13 skipped** | **0** |
| 3 | `venv/Scripts/python.exe -m pytest -q tests/unit` | **1345 passed, 23 skipped** | **0** |
| 4 | targeted negative-control test with source mutated (§9) | **1 failed** (exit 1), then **1 passed** (exit 0) after restore | 1 / 0 |

**Skip accounting (targeted 13 = 4 + 9; full 23 = 10 + 4 + 9):**

* **4 — platform symlink-privilege skips**, each naming `WinError 1314` / "A required privilege is not
  held by the client": `tests/unit/documents/test_file_store_deletion_safety.py:51`,
  `tests/unit/scripts/test_cleanup_smoke_safety.py:74` and `:466`,
  `tests/unit/scripts/test_cleanup_orphan_uploads.py:145`.
* **9 — POSIX dir_fd-only tests**, each with the reason `requires POSIX dir_fd support (os.unlink in
  os.supports_dir_fd); not available on Windows`:
  `tests/unit/scripts/test_descriptor_relative_deletion.py` (lines 114, 229, 245, 261, 282, 313, 349,
  366 = 8) and `tests/unit/scripts/test_cleanup_smoke_safety.py:385` (1).
* **10 — database-blocked tests** (present in the full-suite total; `BLOCKED`, bodies preserved, never
  counted as passes).

**Distinguishing executed from skipped.** The 267 targeted passes (and 1345 full-suite passes)
**executed** on Windows. The 9 descriptor-relative tests were **collected and SKIPPED** — they say
nothing about POSIX descriptor semantics and are **not** counted as passes. **No Linux test command was
run** (no Linux runtime, §5).

**NOT RUN this step (each with reason):** Linux targeted suite (no runtime); `tests/integration` and
`tests/e2e` (the browser harness starts its own uvicorn on port 8000); `scripts/start_server.py` (runs
an Alembic migration in the app lifespan and binds a port — prohibited); every database-blocked test;
the `voice.py` integration paths (need services). No unrelated suite was run merely to increase output.

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
| Terminal access | **no** — "I executed nothing: no pytest, no compile, no digest, no mutation" |
| Independent execution | **no** |
| Access to final source & execution artifacts | source: **yes**; execution artifacts: only as reported by the coordinator |
| Files written | **none** |
| Gate | **INDEPENDENT REVIEW GATE NOT SATISFIED** |

The reviewer is the **same model/runtime family** as the coordinator and had no terminal, so it is
**not genuinely independent**: its judgements are source-read assessments plus an evaluation of
coordinator-reported evidence. Independence was **attempted** by dispatching a separate reviewer
instance, but the required criteria (separate execution environment, distinct family, terminal) are
unmet. No readiness claim may rest on this review.

### 12.2 Findings R-1 … R-10 (reviewer; source-read; nothing executed independently)

| ID | Question | Severity | Source location | Concrete failure scenario | Test evidence | Missing evidence | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R-1 | Root containment correctly enforced? | medium | `cleanup_path.py:97,158,200,354`; `file_store.py:97,117` | Named/lexical + resolved containment enforced component-wise; the one gap is the nested-entry re-validation (R-3) | prune + validate_candidate tests | no live-swap test | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-2 | Symlink/reparse checks adequate? | low | `cleanup_path.py:325-327`, `is_link_or_reparse_point ~:73` | Static links/junctions refused; reparse-attribute test is the right Windows primitive; adequacy fails for a post-`lstat` swap | `test_a_link_nested_inside_a_pycache_is_refused`, `…target_survives` | post-`lstat` window unproven | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-3 | Recursive cleanup directory-swap race? | **medium (disputes "bytecode-only")** | `cleanup_path.py:321 → :331-332` (recursion `:315` `iterdir`) | Entry swapped for a junction after `lstat`; `iterdir()` follows it; target contents (`os.unlink :335`) deleted **outside the root** | static nested-link test only | a swap-between-classification-and-recursion test; Linux run | **NOT FIXED** (residual) |
| R-4 | Descriptor-relative ops correct? | low (impl) / high (unverified) | `cleanup_path.py:437,483`, `_descend_to_parent`, `_relative_parts` | `O_NOFOLLOW` descent, `dir_fd`-bound final op, `"unsupported"` deletes nothing — no internal pathname fallback; sound by construction | 8 descriptor methods + smoke `:385` — **all SKIPPED** | POSIX execution | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-5 | Upload deletion pathname-race vulnerable? | high (by design, deferred) | `file_store.py:195` (checks `:173,:176,:184,:191`) | Final object/parent swapped before `unlink` | `test_file_store_deletion_safety.py` passes; symlink case **skips** (`:51`) | POSIX run; handle-bound/descriptor arm; design note | **DEFERRED** |
| R-6 | Pathname fallbacks constrained? | low | `cleanup_smoke.py:137` (pathname branch only when `outcome == "unsupported"`), `:248` (`user_dir.rmdir()` only when `root_fd is None`), guarded by `:226` | Fallbacks confined to platforms without dir_fd and pre-validated; they **retain** the check-then-use residual there | `test_cleanup_smoke_safety.py` | POSIX run; Windows race demo | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-7 | Tests meaningful / non-vacuous? | low (vacuity) / medium (coverage) | `test_descriptor_relative_deletion.py` `_deletion_lines()`; `test_every_deletion_call_is_descriptor_relative` | A regression moving the real `rmdir` to a pathname call could still pass via the `rmdir_beneath` docstring line (contains `os.rmdir(name, dir_fd=...)`) | AST `test_the_refusal_check_precedes_the_deletion_call` mitigates | assert `dir_fd` on the AST call node; POSIX execution | **NOT FIXED** (test-only) |
| R-8 | Negative control fails for the intended reason? | info | `cleanup_path.py:325`; `test_pycache_prune_safety.py::test_a_link_nested_inside_a_pycache_is_refused` | Disabling the refusal → recurse into the junction → `precious.txt` deleted → assertion fails (**intended**) | freshly executed (fail 1 → restore `97dbc1b65…` → pass 0) | none for Windows; unobserved on POSIX | **FIXED AND VERIFIED** (Windows; digests UNVERIFIABLE-FROM-HERE to reviewer) |
| R-9 | Execution establishes Linux/POSIX behavior? | high | n/a (environment) | All executed tests ran on Windows; 9 descriptor tests skipped; a skip is not a pass; no Linux/container/CI | 267/13, 1345/23 (Windows) | a genuine POSIX run | **NOT VERIFIED** |
| R-10 | Residual risks / readiness claims accurately stated? | low–medium | `cleanup_path.py:306-309`; predecessor's "bytecode-only" | Docstring overstates; the R-3 residual is **not** bytecode-only (out-of-root deletion) → severity understated | source + static tests only | a race test; Linux run | **DISPUTED, WITH EVIDENCE** — readiness posture (BLOCKED / NOT VERIFIED / NO-GO) is correct; R-3 severity wording too weak, **corrected in §6/§15** |

No finding was silently dismissed. The two that change how this report must be read are **R-3** (a real,
medium residual with a possible out-of-root effect, contradicting the "bytecode-only" wording) and
**R-9** (no POSIX evidence exists). The reviewer's severity correction for R-3 is **adopted** in §6.1
and §15.

### 12.11 `REPORT_AUDITOR` pass

A second same-family worker was dispatched against this report with instructions to cross-check counts,
skip arithmetic, exit codes, line references, digests, agent assignments and readiness conclusions
against the repository, and to write **no** files. It had **no terminal**, so every execution-shaped
claim was **UNVERIFIABLE-FROM-HERE** for it; its value is source/report consistency only and **does not**
constitute independent execution verification. It made **no file writes**. Its findings:

* **PASS:** all 18 sections present and in order; the cited line references match the current source;
the named test files/tests exist (`test_a_link_nested_inside_a_pycache_is_refused` at `:222`, `…target_survives` at `:201`); skip arithmetic consistent (13 = 4 + 9; 23 = 10 + 4 + 9); reviewer findings R-1…R-10 complete with all required fields; the directory-swap residual is **not** understated (the adopted medium/out-of-root wording is confirmed); independence/limitation statements are honest.
* **Three line-reference errors**, verified by the coordinator against the source and **corrected**:

| Auditor finding | Severity | Correction applied |
| --- | --- | --- |
| A-1: §7.2 cited `file_store.py:154-155` for `candidate`/`base`; source has them at `:159`/`:160` | low | corrected to `:159` and `:160` (§7.2) |
| A-2: §7.2 cited `_is_link_or_reparse_point` at `:82`; its `def` is at `:80` | low | corrected to `def :80` (§7.2) |
| A-3: §4 row 3 cited the Windows fallback as being "at `delete_upload_files` (`:137`)"; `:137` is the def and the fallback call `delete_upload(resolved, root=root)` is at `:194` | low | corrected call site to `:194` (§4 row 3) |

All execution-shaped claims (HEAD/tree, §5 probes, §9 digests/exit codes, §10 counts, §11 compile,
§14 digests) remain **UNVERIFIABLE-FROM-HERE** to the auditor and are the coordinator's executed
evidence, not the auditor's.

### 12.12 Coordinator corrections applied after review

* **R-3 severity:** the directory-swap residual is restated as **medium** and as a possible
  **out-of-root deletion channel**, replacing the predecessor's "low / bytecode-only" wording (§6.1,
  §15). This is a substantive correction, not a wording change.
* **R-7:** recorded as a **NOT FIXED** test-only weakness (§8, §15).
* Line references were re-verified against the current source with `grep -n` (EXECUTED) for the
  destructive-call-site rows and the database gates (§4, §13).

---

## 13. Database lifecycle gate results

Documentation and source inspection only — **no connection, migration, mutation or `.env` read.**

| Gate | Location (SOURCE, re-verified) | Behaviour |
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
suite does **not** authorize database execution. No part of this step authorizes database mutation or
destructive lifecycle execution.

---

## 14. Protected-artifact integrity results

All measured EXECUTED this step; digests are SHA-256 prefixes (first 16 hex).

| Check | Result | Class |
| --- | --- | --- |
| Frozen benchmark `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches historical** | EXECUTED |
| Upload tree | 1212 files, 7 386 232 bytes — **matches historical** | EXECUTED |
| `STEP1_6AC_POSIX_EXECUTION_AND_FILESYSTEM_SAFETY_GATE_2026-10-14.md` | `6cafb8ab94741c76` — present, **unchanged** | EXECUTED |
| `STEP1_6AB_…_2026-10-13.md` | `96d52e9e0297adc2` — unchanged | EXECUTED |
| `STEP1_6AA_…_2026-10-13.md` | `426270a54fb91706` — unchanged | EXECUTED |
| `scripts/cleanup_path.py` | `97dbc1b6559a402a` — **byte-identical after the negative control** (§9) | EXECUTED |
| HEAD / index | `6baaa2a…` unchanged; 0 staged | EXECUTED |
| Working tree | 385 entries = 295 D + 35 M + 55 ?? (re-measured after the tests) | EXECUTED |
| Stray `.tmp`/`.bak`/`.orig`/`.rej`/`~` under `backend/` (excl. `venv/`,`phases/`) | **0** | EXECUTED |

No predecessor report was overwritten. The only file written by this step is this report. No
negative-control residue exists: the restored file's digest equals its pre-mutation digest, and the
`.16ad.bak` backup was removed (0 stray temp files).

---

## 15. Remaining race conditions and limitations

| # | Limitation | Status | Owner (contract) |
| --- | --- | --- | --- |
| 1 | Linux/POSIX descriptor-relative deletion has never been executed | **NOT VERIFIED — NO AUTHORIZED LINUX RUNTIME** | POSIX_TEST_ENGINEER / COORDINATOR |
| 2 | **Directory swapped for a junction between `lstat` (`:321`) and recursion (`:332`) in `_remove_validated_tree`** — a possible out-of-root deletion channel | **NOT FIXED — residual (medium)** | FILESYSTEM_SAFETY_SPECIALIST / BACKEND_AGENT |
| 3 | Windows upload deletion keeps a check-then-use residual (`file_store.delete_upload` `:195`) | **OPEN** | BACKEND_AGENT / SECURITY_AGENT |
| 4 | Final-name swap inside a validated directory is unclosable with the standard library | **OPEN, BOUNDED** | SECURITY_AGENT |
| 5 | `storage/file_store.delete_upload` remains pathname-based | **DEFERRED** (bar in §8) | BACKEND_AGENT |
| 6 | Rename between the prune's per-entry `lstat` and its `unlink`/`rmdir` | **NARROWED — RESIDUAL REMAINS** | BACKEND_AGENT |
| 7 | e2e harness prune has source-read evidence only (cannot run here) | **LIMITED EVIDENCE** | TEST_AGENT |
| 8 | Parser cleanup tolerates `OSError` only | **RESIDUAL, DOCUMENTED** | BACKEND_AGENT |
| 9 | `test_every_deletion_call_is_descriptor_relative` can pass on a docstring line (R-7) | **NOT FIXED — test-only** | TEST_AGENT |
| 10 | Independent review not satisfied as an organisational control | **NOT SATISFIED** | COORDINATOR |
| 11 | Report-auditor pass had no terminal (source/report consistency only) | **LIMITED** | COORDINATOR |

Nothing in this list is claimed closed. Item 2 is the materially-important one: it is an **out-of-root
deletion channel under a local race**, recorded at medium severity.

---

## 16. Readiness matrix

| Capability | Decision | Basis |
| --- | --- | --- |
| Database-free targeted tests (scripts + documents) | **GO (Windows only)** | 267 passed, 13 skipped, 0 failed, exit 0 |
| Database-free full unit suite | **GO (Windows only)** | 1345 passed, 23 skipped, 0 failed, exit 0 |
| POSIX descriptor-relative deletion | **BLOCKED / NOT VERIFIED** | no Linux runtime or CI; 9 dir_fd tests skip (§5, §10) |
| Windows filesystem deletion | **CONDITIONAL** | fail-closed refusals everywhere; check-then-use residual + final-name swap remain |
| Recursive `__pycache__` prune | **CONDITIONAL — residual** | guarded/contained per entry; the §6.1 directory-swap channel remains (NOT FIXED) |
| Archive integrity | **CONDITIONAL** | exclusive create + same-handle CRC; a swapped archive parent can relocate the archive with no deletion escape |
| Independent safety review | **NOT SATISFIED** | same-family, non-executing reviewer |
| Report audit | **NOT SATISFIED** | auditor had no terminal (§12.11) |
| PostgreSQL integration | **NO-GO** | six-part contract outstanding |
| Migrations and database mutation | **NO-GO** | unchanged |
| Unattended destructive cleanup | **NO-GO** | limitations 1–6 outstanding |

A green suite authorizes nothing beyond database-free tests; it does not authorize database work,
migrations, or unattended cleanup.

---

## 17. Exact next actions

1. **Run the targeted suite on a genuine Linux host** (the only action that moves limitation 1 from NOT
   VERIFIED to measured): `python -m pytest -q tests/unit/scripts tests/unit/documents`, capturing OS,
   kernel, Python version, exit code, pass/skip counts, with the nine descriptor tests **executing**
   instead of skipping. This requires an authorized Linux environment; adding CI configuration is out
   of scope until such a runner is authorized.
2. **Fix the §6.1 directory-swap residual** as its own change-and-test step: re-validate each
   subdirectory — or open it `O_NOFOLLOW` and act through the descriptor — immediately before
   recursing in `cleanup_path._remove_validated_tree`; add a test that performs the swap between
   classification and recursion and asserts the target survives; correct the docstring at `:306-309`.
   The test is runnable on this Windows host with a junction.
3. **Harden the R-7 test** to assert `dir_fd` on the AST `ast.Call` node rather than on source text.
4. **Then, and only then, design the `file_store.delete_upload` POSIX arm** to the four-part evidence
   bar in §8 (POSIX run first; never a pathname fallback), and separately design the Windows
   handle-bound delete.
5. **Standing:** keep PostgreSQL integration, migrations and unattended destructive cleanup **NO-GO**
   until their separate prerequisites are satisfied and independently approved.

---

## 18. Explicit final authorization decision

| Decision | Status |
| --- | --- |
| Database-free targeted tests (scripts + documents) | **AUTHORIZED (Windows)** — 267/13/0, exit 0 |
| Database-free full unit suite | **AUTHORIZED (Windows)** — 1345/23/0, exit 0 |
| Linux/POSIX descriptor-relative deletion | **NOT AUTHORIZED as verified — BLOCKED (no Linux runtime)** |
| Windows filesystem deletion in the application path | **CONDITIONAL** — supervised use only; residual unchanged |
| Recursive `__pycache__` pruning | **CONDITIONAL — supervised**, with the §6.1 directory-swap residual recorded as NOT FIXED |
| Archive-based cleanup sweep | **CONDITIONAL** — supervised, with the script's own archive preconditions |
| PostgreSQL integration | **NOT AUTHORIZED — NO-GO** |
| Migrations / database mutation | **NOT AUTHORIZED — NO-GO** |
| Unattended destructive cleanup | **NOT AUTHORIZED — NO-GO** until limitations 1–6 are closed or explicitly accepted by an independent authority |
| Independent safety review gate | **NOT SATISFIED** — no authorization may rest on §12 |
| Report audit | **NOT SATISFIED** — §12.11 |

**Overall: BLOCKED.** The bounded evidence-gathering step is complete — baseline measured and
preserved, Linux availability genuinely investigated, current-source safety audit done, targeted and
full Windows tests green with a clean compile, the directory-swap race analysed against current source
and recorded (medium, NOT FIXED), `file_store.delete_upload` assessed, and one load-bearing negative
control freshly executed with byte-identical restoration. But the **single gate this step exists to
move (genuine Linux execution) cannot proceed** because no Linux runtime exists and installing one is
prohibited. No production code was changed; every database and destructive-cleanup restriction is
intact; and no PASS or authorization claim beyond the recorded database-free tests is made.

---

### Compliance statement

No PostgreSQL connection, migration, mutation or reset; no real cleanup sweep, archive deletion or
user-upload deletion; no `.env` file or credential read; no WSL, Docker, Podman, VM, package or CI
infrastructure installed; no cloud resources provisioned; no remote workflow created or triggered; no
`git reset`, `clean`, `restore`, stash, checkout, rebase, commit or push; no predecessor report
overwritten (1.6AC `6cafb8ab94741c76` and earlier digests reproduced unchanged). The one source file
mutated for the negative control was restored byte-identically (digest-verified), the affected test
re-ran green, its backup was removed and no control marker remains. The limitation that governs this
step — no genuine Linux execution — is stated at the top of §1 and in §5/§15 rather than hidden. No
worker wrote or modified this report.
