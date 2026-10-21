# STEP 1.6AB — POSIX Execution and Filesystem Safety Gate

Date: 2026-10-13
Owner: COORDINATOR (this run)
Predecessors: `STEP1_6AA_POSIX_VERIFICATION_AND_INDEPENDENT_SAFETY_GATE_2026-10-13.md` (`426270a54fb91706`),
`STEP1_6Z_FILESYSTEM_RACE_AND_INDEPENDENT_VERIFICATION_2026-10-13.md` (`1660eab85357e9eb`) — both unchanged by this step
Verdict: **CONDITIONAL PASS**

Every claim below is labelled: **EXECUTED** (a command ran and its output is quoted), **SOURCE**
(read from the current file), **INFERENCE** (reasoned from source, not executed), or **NOT VERIFIED**.
No database connection, migration, mutation, real cleanup sweep, commit, push or destructive Git
operation was performed; no historical report was modified.

---

## 1. Executive outcome

**CONDITIONAL PASS.**

* **POSIX execution: NOT VERIFIED** — freshly re-probed, not copied from 1.6Z/1.6AA: the host is Git
  Bash on Windows (`uname -s` = `MINGW64_NT-10.0-26300`), `wsl.exe` reports the subsystem is not
  installed, `docker`/`podman`/`python3`/`act`/`gh` are absent, and no CI configuration exists in the
  repository. Nine POSIX dir-fd-only tests therefore still skip. Nothing was installed (§5).
* **Two bounded remediations landed**, both closing items 1.6AA recorded as *not fixed* — one
  **verified by execution** on this host, the other verifiable only by **source-read guards**
  (stated as such in §7.2):
  1. `documents/parser.py` — the transient PDF copy was removed with a bare `os.unlink` in a
     `finally`, so a cleanup failure (a scanner or indexer holding the handle is enough on Windows)
     replaced a successful parse with an exception. It is now best-effort, logged, and cannot change
     the parse outcome **for the `OSError` failure modes that occur in practice** (§7.1, residual in
     §8). Latent on the current code paths: every production caller passes a path, not bytes.
     Evidence class: **executed** (3 tests, plus a negative control).
  2. `tests/e2e/browser/test_phase6_reliability.py` — the last unguarded, link-following recursive
     `__pycache__` sweep in the repository now goes through `prune_pycache_beneath(_BACKEND_DIR)`
     (§7.2). It cannot be executed here (it starts its own server), so its evidence is source-read
     guards, clearly labelled as such.
* **Negative controls: three, all load-bearing** — disabling the parser's tolerance, reverting the
  e2e harness sweep, and removing the prune's link/reparse refusal each made a specific test fail
  (exit 1); every mutated file was restored byte-identically and the suites re-run green (§9).
* **Independent review: NOT SATISFIED** as an organisational control — a separate agent instance in
  the same model family, with no terminal. Its findings F-1…F-11 were all dispositioned; the three
  actionable ones (stale docstring, a temp-file leak in the new test, a fragile assertion) were
  fixed and re-verified (§12).
* **Deferred, deliberately:** the descriptor-relative arm for `storage/file_store.delete_upload`.
  The step's own rules forbid untested platform-specific destructive code, and no POSIX runtime
  exists to give it execution evidence (§8).
* **Verification in one line:** full unit suite **1345 passed, 23 skipped, 0 failed**, exit 0, on
  both interpreters; benchmark digest, upload tree, published reports and all five predecessor
  reports provably unchanged (§10, §14).

**Why not PASS:** POSIX remains unverified, the Windows check-then-use residual and the unclosable
final-name swap stand, `file_store.delete_upload` stays pathname-based, and the independent-review
gate is unsatisfied. PostgreSQL integration, migrations/DB mutation and unattended destructive
cleanup remain **NO-GO** (§18).

---

## 2. Scope and non-goals

**In scope.** Revalidate the current repository state and the destructive-operation inventory from
current source; re-investigate POSIX availability; audit the filesystem boundary; land only
remediations whose safety properties and tests can be justified on this host; run focused and full
verification with at least one negative control; obtain an adversarial review of the final source;
confirm the database/lifecycle gates are untouched; produce this report.

**Explicit non-goals.** Installing WSL, Docker, Podman, virtual machines, packages or CI
infrastructure; implementing a POSIX-only deletion path in `storage/file_store.delete_upload`;
implementing a Windows handle-bound delete (`CreateFileW` + `SetFileInformationByHandle`) — the task
forbids combining that speculative change with this phase; connecting to or mutating PostgreSQL;
running migrations; running any real cleanup sweep; changing protected artifacts.

### Agent assignments (as actually dispatched)

| Contract name | Actual runtime agent | Status | Evidence returned |
| --- | --- | --- | --- |
| `ORCHESTRATOR` | coordinator (this session) | EXECUTED | this report; all commands below |
| `ENVIRONMENT_VERIFIER` | coordinator with terminal (no separate agent exists for this role) | EXECUTED | §5 probe table |
| `FILESYSTEM_SAFETY_SPECIALIST` | coordinator (terminal-aided source audit) + one `code-searcher` worker for the destructive-site sweep | EXECUTED | §4 inventory |
| `TEST_ENGINEER` | coordinator with terminal | EXECUTED | §9, §10 |
| `INDEPENDENT_REVIEWER` | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only, no terminal | DISPATCHED — substitute, **not independent** | §12 (F-1…F-11) |
| `DATABASE_SAFETY_AUDITOR` | coordinator, source inspection only | EXECUTED (source-only) | §13 |
| `REPORT_AUDITOR` | one `base3-fast-worker-deepseek-flash` worker, instructed to cross-check this report against the repository | DISPATCHED | §12.6 |

Substitutions are recorded rather than hidden: no named specialist is claimed to have run as a
runtime agent, and the two worker dispatches are ordinary same-family workers, not organisational
controls.

---

## 3. Initial and final repository state

| Item | Initial | Final | Evidence |
| --- | --- | --- | --- |
| Repository root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` | unchanged | `pwd`, `git rev-parse --show-toplevel` |
| Branch | `main` | `main` | EXECUTED |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | **unchanged** | EXECUTED |
| Index (staged) | 0 files | 0 files | EXECUTED |
| Working tree | 385 entries — 295 deleted (pre-existing), 35 modified (pre-existing), 55 untracked | **385 entries**, unchanged counts | EXECUTED (`git status --porcelain`) |
| Pre-existing user changes | preserved — nothing was reset, cleaned, stashed, checked out, rebased, committed or pushed | preserved | EXECUTED |
| `.env` / credentials | not read | not read | — |

The pre-existing deletions/modified set and the untracked `evaluation/**`, `scripts/**`, `tests/**`
layout are the baseline carried from before Step 1.6X. No discrepancy with the historical record was
found.

---

## 4. Source-grounded destructive-call-site inventory

Built from the current source with these searches over `backend/` (excluding `phases/`, `models/`,
`venv/`, `**/__pycache__/**`): `shutil.rmtree`, `ignore_errors=True`, `os.remove|os.unlink|os.rmdir|os.replace`,
`.unlink(|.rmdir(`, `truncate`, `shutil.move`, `def delete_upload|def cleanup_new_file`, plus a
`code-searcher` worker re-running an equivalent sweep. Every row is **SOURCE** unless marked.

| # | Operation | Source (current lines) | Validation before it | Race window | Mitigation in place | Test | Execution this step | Residual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Application delete of an uploaded file | `storage/file_store.py:195` | `..` refusal `:170-171`; resolved containment `:173`; link/reparse refusal candidate+resolved `:176-177`; link-ancestor walk `:184`; `S_ISREG` `:191` | validate → pathname `unlink` | none (pathname flow) | `test_file_store_deletion_safety.py`, `test_reparse_points_and_race_safety.py` | passed (unit) | **Open** — deferred, §8 |
| 2 | Cleanup after failed commit | `storage/file_store.py:201-214` → row 1 | same | same | none | via row 1 | passed | same |
| 3 | Smoke delete of named uploads | `scripts/cleanup_smoke.py:189`, prune `:248` | `intended_root` first; per-candidate `resolve_stored_path` + `validate_candidate` | POSIX closed for parents/root; Windows open | `unlink_beneath`/`rmdir_beneath` POSIX; fail-closed refusal when the root cannot be held | `test_cleanup_smoke_safety.py` (26), `test_descriptor_relative_deletion.py` | passed / 8 POSIX-only **skipped** | Windows swap; POSIX arm unexecuted |
| 4 | Orphan sweep deletes + prunes | `scripts/cleanup_orphan_uploads.py:391` (`path.unlink()`), `:431` (`path.rmdir()`) | `intended_root`; per-candidate `validate_candidate`; referenced-set check | as row 3 | `unlink_beneath`/`rmdir_beneath` POSIX | `test_cleanup_orphan_uploads.py` (34), `test_race_substitution_deterministic.py` (7) | passed | as row 3 |
| 5 | Archive create/verify/failure | `scripts/cleanup_orphan_uploads.py:202` (`open(..., "x+b")`), `:216-250` | destination not inside root, not a link, pre-check, candidate validation | creation exclusive; verification handle-bound | exclusive create + same-handle CRC; failed write leaves the fragment (no pathname delete) | orphan + race tests | passed | a swapped parent can relocate the archive (no deletion escape) |
| 6 | `__pycache__` prune (server) | `scripts/start_server.py:75` → `scripts/cleanup_path.py:280-363` | `intended_root` `:301`; per-candidate `validate_candidate` `:354`; per-entry single `lstat` `:321-330` | narrow window between that `lstat` and `unlink`/`rmdir` (`:335`, `:340`) — **inference**, same class as row 1 | containment + link/reparse refusal, never traversed; refusals returned and printed | `test_pycache_prune_safety.py` (14) | passed (14/14) | rename inside the window; bytecode only |
| 7 | `__pycache__` prune (e2e harness) | `tests/e2e/browser/test_phase6_reliability.py:36-49` → row 6 | as row 6 | as row 6 | as row 6 | source-read guards only (cannot run: needs a live server) | **guards passed**; harness **not executed** | rename inside the window; bytecode only |
| 8 | Publish evaluation evidence | `evaluation/artifacts.py:233,236` | unique per-process temp name; `write_evidence` append-only by default | atomic `os.replace`; temp cleanup acts on its own file | append-only publication | `test_writer_collision_*` | passed | none material |
| 9 | Parser temp copy | `documents/parser.py:463` (`os.unlink` in `try/except OSError`, block `:454-467`) | n/a — parser's own `NamedTemporaryFile` | n/a (own temp file) | **new**: failure logged, parse outcome unaffected | `test_parser_temp_cleanup.py` (3) | passed (3/3) | non-`OSError` would still mask the outcome — inference, no realistic trigger |
| 10 | Voice temp audio | `voice.py:258-262` | n/a — own temp file | n/a | `OSError` caught + warning | integration voice tests | not run (needs services) | none material |
| 11 | Runner fixture uploads | `run_phase3e_integration.py:290,319,387,418,543`; `run_phase3e_validation.py:268,357,630,777,824` | each removes a path the same run created | n/a | runner-level disposal gate refuses before `main()` body | guard-order tests | passed (source-read) | none material; runs blocked anyway |
| 12 | Inline row deletions in runners | gate at `run_phase3e_integration.py:518`, `run_phase3e_validation.py:586` (the gated blocks begin at `:512` / `:580`) | `assert_cleanup_execution_authorized` immediately before | n/a | function-level gate refuses unconditionally | `test_phase3d_upload_inline_sql_guard.py` (13) | passed | gate refuses; block unreachable |

Rows 1–12 are the complete set: the `code-searcher` sweep returned the same list, with **no
executable `shutil.rmtree`, `ignore_errors=True`, `truncate`, or destructive `shutil.move`**
remaining anywhere in the searched scope, and no hand-rolled recursive delete other than
`prune_pycache_beneath` itself (*inference: the pattern search covers these call shapes; a delete
built from unfamiliar primitives would evade it — none was found*).

---

## 5. POSIX environment investigation and execution evidence

**Result: POSIX: NOT VERIFIED.** Probes were bounded (`wsl.exe` with stdin redirected so it cannot
block; no interactive commands).

| Probe | Command | Observed |
| --- | --- | --- |
| Kernel | `uname -s`, `uname -r` | `MINGW64_NT-10.0-26300`, `3.3.6-341.x86_64` — MSYS/Git Bash on Windows, not POSIX |
| WSL | `wsl.exe -l -q < /dev/null` | "The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'." (exit 0, UTF-16) |
| Containers | `command -v docker podman` | both absent |
| POSIX Python | `command -v python3` | absent (only Windows builds: `py -3`, `venv/Scripts/python.exe`) |
| CI runners | `command -v act gh` | absent |
| Repository CI | existence check of `.github/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci`, `.woodpecker.yml`, `bitbucket-pipelines.yml` | **none present** |

No POSIX runtime is available, so **no POSIX test command was executed**. Nothing was installed. The
nine tests that would execute there and currently skip are enumerated in §10. Windows results and
skipped tests are **not** treated as POSIX evidence, and Git Bash is not a POSIX kernel for this
purpose.

---

## 6. Filesystem threat model

Cases: **A** lexical traversal, **B** link/reparse traversal, **C** object replacement, **D** parent
replacement, **E** concurrency, **F** archive substitution.

| Operation | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1–2 `file_store.delete_upload` | refused | refused (candidate, resolved, ancestor walk) | **open** (pathname `unlink`) | **open** | open | n/a |
| 3–4 cleanup smoke / orphan sweep | refused | refused | Windows **open**; POSIX name-swap only | POSIX closed, Windows open | reported | n/a |
| 5 archive | refused | refused | closed (exclusive create) | **open** (archive parent not held) | n/a | closed (same-handle verify) |
| 6–7 `__pycache__` prune | refused (`intended_root`, containment) | refused (root, candidates, every entry) | *inference*: narrow window after the per-entry `lstat` | **open** (parents not held) | n/a | n/a |
| 8 `write_evidence` | refused | n/a | closed (exclusive create, atomic `replace`) | n/a | unique temp name | n/a |
| 9 parser temp copy | n/a | n/a | n/a (own temp file) | n/a | n/a | n/a |

The boundary statement this report stands behind: **only handle-bound or descriptor-relative
operations bind a delete to the validated object**, and they exist here for POSIX (rows 3–5) but not
for Windows `unlink`/`rmdir`. Nothing in this step is claimed to have eliminated a race; rows 6–7 are
*narrowed*, row 1 is *deferred*, and the final-name swap is unclosable with the standard library.

---

## 7. Implemented changes and their tests

### 7.1 `documents/parser.py` (`948f87679a249ef1`) — temp-copy cleanup must not decide the parse

**Defect (SOURCE).** `parse_pdf` adapts byte input through a `NamedTemporaryFile` and removed it with
a bare `os.unlink(tmp_path)` inside a `finally`. A cleanup failure therefore replaced a *successful*
parse with an exception — and would equally have replaced the extractor's own exception. On Windows,
an antivirus scanner or search indexer holding the handle is enough to trigger it.

**Change.** `import logging` (`:126`) and a module logger (`:141`) were added following the
convention used by `voice.py:30/43` and `documents/routes.py:17/60`; the cleanup is now

```python
try:
    os.unlink(tmp_path)
except OSError:
    logger.warning("Failed to remove the temporary PDF copy for %s", label)
```

and the docstring statement "that is always removed" was reworded to match, now `:435-436`
(reviewer F-1). `label` is bound at `:447`, before the `try`, and is never the temporary path (the
docstring sentence at `:439` guarantees that), so the log call cannot leak the temp path.

**Scope of the defect — stated precisely to avoid over-claiming (reviewer F-7):** it is **latent**.
All six production call sites pass a path, not bytes (`documents/routes.py:268` and the three
evaluation runners), so the bytes branch is reached by tests and by future callers. Only `OSError` is
tolerated; a non-`OSError` raised by `os.unlink` would still mask the outcome (reviewer F-8) —
recorded as a residual, not widened, because widening would start swallowing programming errors.

**Tests (`tests/unit/documents/test_parser_temp_cleanup.py`, new, 3 tests, all EXECUTED):**
`test_a_failed_temp_copy_unlink_does_not_fail_the_parse` (a refused `unlink` no longer fails the
parse, and the failure is logged with its own message), `test_the_temp_copy_is_removed_on_the_success_path`
(exactly one transient copy is removed and is gone from disk), and
`test_extractor_failure_still_propagates_and_the_copy_is_still_removed` (a real extractor error
still propagates unchanged and the copy is still cleaned up). They monkeypatch `os.unlink` for
`.pdf` paths only, restore it in a `finally`, and delete every copy they leave behind.

### 7.2 `tests/e2e/browser/test_phase6_reliability.py` (`393209d4c8d2430a`) — the last unguarded sweep

**Defect (SOURCE).** `main()` swept `__pycache__` with `os.path.isdir(...)` + `shutil.rmtree(...,
ignore_errors=True)`: no containment, a link-following `isdir`, and every failure swallowed.

**Change.** It now bootstraps the backend root onto `sys.path` and calls
`prune_pycache_beneath(_BACKEND_DIR)`, printing each refusal — the same guarded helper the server
script uses (`scripts/start_server.py:75`), which refuses a linked root, refuses (never traverses)
links and reparse points, classifies every entry from a single `lstat` and stays inside the root.

**Evidence limit, stated plainly (reviewer F-5).** This harness starts its own uvicorn against a live
server on port 8000, so it was **not executed**. Its evidence is three **source-read guards** in
`tests/unit/scripts/test_pycache_prune_safety.py` (`TestE2eHarnessCallSite`: no `shutil.rmtree`, no
`ignore_errors=True`, the helper is used on `_BACKEND_DIR`, and the bootstrap precedes the import
while the prune precedes `subprocess.Popen`). Those guards prove the source text, not behaviour; the
behaviour they call is covered by the 11 executed prune tests.

### 7.3 Test-file changes

`tests/unit/scripts/test_pycache_prune_safety.py` (`4a3a5f1e1f5e2d4f`) grew from 11 to **14** tests:
the three harness guards above. No existing assertion was weakened or removed, and no test was
converted from skipped to passing.

---

## 8. Deferred changes and the reason for deferral

| Item | Disposition | Reason |
| --- | --- | --- |
| Descriptor-relative arm for `storage/file_store.delete_upload` (row 1) | **BOUNDED — DEFERRED PENDING REQUIRED TEST ENVIRONMENT** | The rules for this phase forbid adding untested platform-specific destructive code, and no POSIX runtime exists to execute it (§5). The reviewer agreed (F-9) and set the evidence bar: (i) an authorized POSIX run executing the 9 currently-skipped descriptor tests; (ii) `test_file_store_deletion_safety.py` and the upload flow passing on that runtime; (iii) a design note on safe-handle acquisition and the refusal when it cannot be acquired — never a pathname fallback; (iv) review of that specific change |
| Windows handle-bound delete (`CreateFileW` + `SetFileInformationByHandle`) | **NOT FIXED — DEFERRED BY INSTRUCTION** | Testable on this host, but the phase explicitly forbids combining a speculative Windows API implementation with it "merely to claim the pathname race is solved". It needs its own design note, tests and review |
| `documents/parser.py` non-`OSError` cleanup failure | **NOT FIXED — REASON AND RISK DOCUMENTED** | Widening the handler would swallow programming errors; `tmp_path` is always a `Path`, so no realistic trigger exists |
| `voice.py:258-262` temp cleanup, runner fixture deletions | **NO CHANGE — ALREADY CORRECT / OWNED FIXTURES** | Their own temp files; `OSError` already handled (voice) or fixture-scoped (runners) |

---

## 9. Negative-control evidence

Each control was applied **in place** to the final source, the targeted test run, and the file
restored from bytes captured before the mutation. All fixtures are temporary directories; no real
upload, archive or user file was involved.

| Control | Protection disabled by | Targeted test | Observed |
| --- | --- | --- | --- |
| (a) | replacing the parser's `try/except OSError` cleanup with the bare `os.unlink` | `test_a_failed_temp_copy_unlink_does_not_fail_the_parse` | **1 failed, exit 1** |
| (b) | restoring the harness's `shutil.rmtree(..., ignore_errors=True)` sweep | `TestE2eHarnessCallSite` (3 guards) | **3 failed, exit 1** |
| (c) | neutralizing the prune's single-`lstat` link/reparse refusal (`if False and (...)`) | `test_a_link_nested_inside_a_pycache_is_refused` | **1 failed, exit 1** |

Restoration was verified by SHA-256 prefix, not by inspection: `documents/parser.py` →
`948f87679a249ef1`, `tests/e2e/browser/test_phase6_reliability.py` → `393209d4c8d2430a`,
`scripts/cleanup_path.py` → `97dbc1b6559a402a` — all reported byte-identical after every control. The
suites were then re-run: `tests/unit/documents tests/unit/scripts` → **267 passed, 13 skipped, exit
0**, and the 17 tests of the two touched test files → **17 passed, exit 0**.

Additional hygiene control from the review (F-2): the earlier version of the new parser test leaked
one transient `.pdf` copy per run into the OS temp directory. Measured before/after a re-run of the
fixed test: three leftovers (timestamps 20:49:38/49/54 from the pre-fix runs), **0 newly created by
the fixed test**, and the three leftovers were removed — 0 remaining.

---

## 10. Full test commands, counts, skips and exit codes

All commands from `backend/`; every exit status is the tested command's own.

| # | Command | Observed result | Exit |
| --- | --- | --- | --- |
| 1 | `venv/Scripts/python.exe -m pytest -q tests/unit` (final) | **1345 passed, 23 skipped, 0 failed** | **0** |
| 2 | same suite under `py -3` (Python 3.13.12) | **1345 passed, 23 skipped** — identical | **0** |
| 3 | `... -m pytest -q tests/unit/scripts` | **122 passed, 12 skipped** | **0** |
| 4 | `... -m pytest -q tests/unit/documents` | **145 passed, 1 skipped** | **0** |
| 5 | `... -m pytest -q tests/unit/documents tests/unit/scripts` (after controls) | **267 passed, 13 skipped** | **0** |
| 6 | `... -m pytest -q tests/unit/documents/test_parser_temp_cleanup.py tests/unit/scripts/test_pycache_prune_safety.py` | **17 passed** (3 + 14) | **0** |

**Skip accounting (23 = 10 + 4 + 9), unchanged from 1.6AA:**

* **10** — explicitly `BLOCKED` database tests (no authorized runtime; bodies preserved, never
  counted as passes).
* **4** — platform symlink-privilege skips, each naming `WinError 1314`:
  `tests/unit/documents/test_file_store_deletion_safety.py:51`,
  `tests/unit/scripts/test_cleanup_smoke_safety.py:74` and `:466`,
  `tests/unit/scripts/test_cleanup_orphan_uploads.py:145`.
* **9** — POSIX dir-fd-only tests of the descriptor-relative deletion work:
  `tests/unit/scripts/test_descriptor_relative_deletion.py` (8) and
  `tests/unit/scripts/test_cleanup_smoke_safety.py:385` (1), each skipping with
  `requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); not available on Windows`.

**Not run at all:** the e2e/browser harness row 7 (needs a live server and would start one);
`scripts/start_server.py` itself (it runs an Alembic migration inside the app lifespan and binds a
port — prohibited); `voice.py` integration paths (need services); every database-blocked test.

**Test-count delta:** 1339 → 1345 (+6: 3 parser tests, 3 harness guards). No pre-existing test was
modified except the harness source it guards.

---

## 11. Compile-check results

| Command | Result | Exit |
| --- | --- | --- |
| `venv/Scripts/python.exe -m compileall -q documents scripts evaluation tests/unit/documents tests/unit/scripts` | clean, no output | **0** |

`documents/parser.py` (the only production file changed) compiles clean, and its behaviour is
additionally exercised by 145 passing document tests including the three new ones.

---

## 12. Independent-review status and findings

### 12.1 Identity and independence

| Item | Value |
| --- | --- |
| Reviewer | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only, **no terminal** |
| Scope | the final source of `documents/parser.py`, the new parser tests, the e2e harness call site and its guards, `scripts/cleanup_path.py` (prune), `storage/file_store.py`, plus an independent destructive-site sweep |
| Self-declared | same model family and execution context; executed nothing; **edited no files**; "useful adversarial review but not an organisational independent control" |
| Gate | **INDEPENDENT REVIEW GATE NOT SATISFIED** |

### 12.2 Claim verdicts

| # | Claim | Verdict |
| --- | --- | --- |
| 1 | parser cleanup is best-effort and cannot decide the parse outcome | **CONFIRMED** (for `OSError` subclasses), plus F-1 and F-8 |
| 2 | the three parser tests are meaningful and non-vacuous | **CONFIRMED by construction**, plus F-2/F-3/F-4 |
| 3 | the harness has no unguarded recursive delete and still prunes before launch | **CONFIRMED as source fact**, execution limit noted |
| 4 | the harness guards are sufficient evidence | **PARTIALLY CONFIRMED** — they prove source text, not behaviour (F-5) |
| 5 | no unguarded destructive call site remains | **CONFIRMED** by independent re-search (F-6), inventory reproduced exactly |
| 6 | deferring the `file_store` POSIX arm is correct | **CONFIRMED as a judgement**, with the evidence bar of F-9 |
| 7 | over-claim risks | four flagged (F-5, F-7, F-10, F-11) |

### 12.3 Findings and dispositions

| ID | Severity | Finding (file:line) | Disposition |
| --- | --- | --- | --- |
| F-1 | low | `documents/parser.py:435-436` docstring still said the copy "is always removed", contradicting the new best-effort cleanup | **FIXED AND RETESTED** — reworded before this report |
| F-2 | low | the new parser test leaked one `.pdf` copy into the OS temp dir per run, invisible to a `backend/`-only artifact scan | **FIXED AND MEASURED** — the test now removes its leftover; before/after measurement: 3 stale (pre-fix runs) → 0 new, leftovers removed |
| F-3 | low | the "warning logged" assertion matched any warning from the logger, so it could pass for the wrong reason | **FIXED AND RETESTED** — assertion now matches the message text and the logger name |
| F-4 | low | `_is_transient_pdf_copy` keyed on the interpreter's temp dir, a needless fragility | **FIXED** — the filter is the `.pdf` suffix alone; tests re-run green |
| F-5 | low | harness guards do not pin ordering and are not behaviour evidence | **FIXED (ordering) / LABELLED** — an ordering guard (bootstrap → import → prune → `Popen`) was added, and §7.2 states plainly that these are source-read guards |
| F-6 | info | independent sweep reproduced the inventory exactly, nothing missing | **ACCEPTED** — §4 |
| F-7 | info | no production caller passes bytes, so the parser defect is latent | **ACCEPTED** — §7.1 wording |
| F-8 | info (inference) | only `OSError` is tolerated | **ACCEPTED AS RESIDUAL** — §8 |
| F-9 | — | deferral of the `file_store` POSIX arm | **CONFIRMED** with a four-part evidence bar (§8) |
| F-10 | info | the prune docstring opens with absolutes while the rename-window residual sits further down | **ACCEPTED** — §6 and §15 repeat the residual beside the guarantee |
| F-11 | info | source-read guards ≠ behaviour evidence; same-family review ≠ independence | **ACCEPTED** — stated in §7.2, §12.1 |

### 12.4 Quotes the reviewer used (source facts worth preserving)

`parser.py:454-467` shows the `try/except OSError` + `logger.warning` (`os.unlink` at `:463`);
`:447` binds `label` before the `try`; `:439` states the source is never the temp path; `:126`/`:141` add `logging` and the
module logger; the `finally` can no longer replace the extractor's exception. The harness bootstrap
mirrors `cleanup_smoke.py`/`cleanup_orphan_uploads.py` and imports only `os`/`stat`/`pathlib`. The
prune refuses `S_ISLNK`/`FILE_ATTRIBUTE_REPARSE_POINT` from one `lstat` (`cleanup_path.py:321-330`)
after `intended_root` (`:301`) and `validate_candidate` (`:354`).

### 12.5 What the review could not do

Execute anything: no terminal, no pytest, no POSIX host. Every judgement is source reading. It
verified no counts, digests or manifests, and it explicitly made no claim about them. Its caveats
(F-2/F-3/F-4 about test hygiene) were the actionable ones and are fixed above.

### 12.6 `REPORT_AUDITOR` pass

A second worker was dispatched against the written report with instructions to cross-check counts,
paths, line references and integrity claims against the repository, and to reject unsupported
claims. It could execute nothing, so it correctly marked every execution-shaped claim
UNVERIFIABLE-FROM-HERE; its source-level audit found **five line-reference errors**, all of which
were re-verified by the coordinator against the source and corrected in this report rather than
defended:

| Auditor finding | Correction applied |
| --- | --- |
| `storage/file_store.py` validation cluster cited 3–7 lines early (`:167-190`) | corrected to the verified lines: `..` `:170-171`, containment `:173`, link/reparse `:176-177`, ancestor walk `:184`, `S_ISREG` `:191` (§4 row 1) |
| prune's `validate_candidate` gate cited as `:337-338` | corrected to `:354` (§4 row 6) |
| parser `os.unlink` cited as `:462` | corrected to `:463`, block `:454-467` (§4 row 9) |
| parser docstring refs `:433` / `:436` imprecise | corrected to `:435-436` (the reworded sentence) and `:439` ("never a temporary path") (§7.1, §12.3, §12.4) |
| runner inline gates cited at the comment line (`:512` / `:580`) | corrected to the gate calls at `:518` / `:586`, with the block starts noted (§4 row 12) |

It also flagged two over-claims in this report's own summary, both fixed: "both verifiable on this
host" contradicted §7.2 (the harness has source-read evidence only), and "cannot change the parse
outcome" needed the `OSError` qualifier. It confirmed, by reading the source, that the test names and
counts cited here exist and are internally consistent (3 + 14 = 17; 122 + 145 = 267; 23 = 10 + 4 + 9;
1339 + 6 = 1345), while explicitly declining to treat its own inability to run pytest as evidence of
absence. Everything it could not check — every pass count, exit code, SHA-256 prefix, `HEAD`/index
state and the temp-leftover measurement — is the coordinator's executed evidence, restated here, not
the auditor's.

---

## 13. Database lifecycle gate results

Documentation and source inspection only — **no connection, migration, mutation or `.env` read**.

| Gate | Location | Behaviour (SOURCE) |
| --- | --- | --- |
| `_proof_is_live` | `evaluation/isolation.py:363` | returns `False` unconditionally |
| `record_created_database` | `:369` | raises `UnsafeEvaluationTarget` |
| `assert_disposal_authorized` | `:377` | raises `UnsafeEvaluationTarget` at the end (`:405-411`) |
| `assert_creation_authorized` | `:415` | raises `UnsafeEvaluationTarget` |
| `assert_row_cleanup_authorized` | `:443` | delegates to `assert_disposal_authorized` |
| `assert_cleanup_execution_authorized` | `:456` | raises immediately, before inspecting any caller object |
| `release_database_proof` | `:477` | raises `UnsafeEvaluationTarget` |
| `assert_engine_bound_to_proof` | `:485` | refusal path preserved |

**Status: BLOCKED — no change.** No guard was relaxed, no blocked test was made unconditional, no
URL comparison replaced an authorization decision, and this step touched no lifecycle code. The
six-part infrastructure contract of Step 1.6Y §9 remains outstanding. **PostgreSQL integration: NOT
VERIFIED. Migrations and database mutation: NO-GO.**

---

## 14. Protected-artifact integrity results

| Check | Result |
| --- | --- |
| Frozen benchmark `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches** |
| Upload tree | 1212 files, 7 386 232 bytes, **0 modified today** |
| Published reports | 51 files; newest real artifact `table_evidence_measurement_analysis.json`, 2026-10-06 |
| `UNIFIED_SAFETY_REMEDIATION_REPORT_2026-10-13.md` | `66b53544ebffd2d0` — unchanged |
| `STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md` | `b0cbefef7d9cab14` — unchanged |
| `STEP1_6Y_ARTIFACT_AND_FILESYSTEM_VERIFICATION_2026-10-13.md` | `92ee2315822071b2` — unchanged |
| `STEP1_6Z_FILESYSTEM_RACE_AND_INDEPENDENT_VERIFICATION_2026-10-13.md` | `1660eab85357e9eb` — unchanged |
| `STEP1_6AA_POSIX_VERIFICATION_AND_INDEPENDENT_SAFETY_GATE_2026-10-13.md` | `426270a54fb91706` — unchanged (not overwritten by this step) |
| HEAD / index / tree | `6baaa2a…` unchanged; 0 staged; 385 working-tree entries |
| Stray `.tmp`/`.bak`/`.orig`/`.rej`/`~` under `backend/` | **0** |
| Negative-control residue in the tree | **0** (all three mutated files restored byte-identically) |
| OS temp leftovers created by this step's tests | **0** (measured; §9) |

Files this step changed, with SHA-256 prefixes: `documents/parser.py` `948f87679a249ef1`;
`tests/e2e/browser/test_phase6_reliability.py` `393209d4c8d2430a`;
`tests/unit/documents/test_parser_temp_cleanup.py` `78afdf1fa6e76e3b` (new);
`tests/unit/scripts/test_pycache_prune_safety.py` `4a3a5f1e1f5e2d4f`; and this report. Unchanged but
relied on: `scripts/cleanup_path.py` `97dbc1b6559a402a`, `scripts/start_server.py` `1eaf6c34be7058e7`.

---

## 15. Remaining race conditions and limitations

| # | Limitation | Status | Owner (contract) |
| --- | --- | --- | --- |
| 1 | POSIX descriptor-relative deletion has never been executed | **NOT VERIFIED** | TEST_AGENT / COORDINATOR |
| 2 | Windows upload deletion keeps a check-then-use residual (`file_store.delete_upload`, cleanup scripts) | **OPEN** | BACKEND_AGENT / SECURITY_AGENT |
| 3 | Final-name swap inside a validated directory is unclosable with the standard library | **OPEN, BOUNDED** | SECURITY_AGENT |
| 4 | `storage/file_store.delete_upload` remains pathname-based | **DEFERRED** (evidence bar in §8) | BACKEND_AGENT |
| 5 | A rename between the prune's per-entry `lstat` and its `unlink`/`rmdir` | **NARROWED — RESIDUAL RACE REMAINS** (inference) | BACKEND_AGENT |
| 6 | The e2e harness change has source-read evidence only (it cannot be executed here) | **LIMITED EVIDENCE** | TEST_AGENT |
| 7 | Parser cleanup tolerates `OSError` only | **RESIDUAL, DOCUMENTED** | BACKEND_AGENT |
| 8 | Independent review not satisfied as an organisational control | **NOT SATISFIED** | COORDINATOR |

Nothing in this list is claimed closed. Item 5 in particular is **narrowing, not closure**: the
operation remains check-then-use with a shorter window.

---

## 16. Readiness matrix

| Capability | Decision | Basis |
| --- | --- | --- |
| Database-free unit tests | **GO** | 1345 passed, 23 skipped, 0 failed, exit 0 (both interpreters); scripts 122/12, documents 145/1 |
| POSIX descriptor-relative deletion | **NOT VERIFIED** | 9 POSIX-only tests skip; no POSIX runtime or CI (§5) |
| Windows filesystem deletion | **CONDITIONAL** | fail-closed refusals everywhere; check-then-use residual and final-name swap remain (risks 2–3) |
| Archive integrity | **CONDITIONAL** | exclusive create + same-handle CRC verification; failed write leaves the fragment; swapped archive parent can relocate the archive with no deletion escape |
| Shared cleanup authorization boundary | **CONDITIONAL** | last unguarded recursive delete removed (rows 6–7); `file_store` keeps a hand-maintained copy of the policy (deferred) |
| Independent safety review | **NOT SATISFIED** | same-family, non-executing reviewer; no external reviewer available |
| PostgreSQL integration | **NO-GO** | six-part contract outstanding |
| Migrations and database mutation | **NO-GO** | unchanged |
| Unattended destructive cleanup | **NO-GO** | limitations 1–3 outstanding |

A green suite authorizes nothing beyond database-free tests; it does not authorize database work or
unattended cleanup.

---

## 17. Exact next actions

1. **Obtain a POSIX execution result** — the only action that moves limitation 1 from NOT VERIFIED to
   measured. Smallest safe step: on a Linux host or Linux CI job checked out at this tree, run
   `python -m pytest -q tests/unit/scripts tests/unit/documents` and capture OS, Python version,
   exact command, exit code, and the pass/skip counts, with the nine descriptor tests executing
   instead of skipping. Adding CI configuration is out of scope until such a runner is authorized.
2. **Then, and only then, design the `file_store.delete_upload` hardening** to the four-part evidence
   bar in §8 (POSIX run first; no pathname fallback when a safe handle cannot be acquired).
3. **Separately design the Windows handle-bound delete** (`CreateFileW` with
   `FILE_FLAG_OPEN_REPARSE_POINT` + `SetFileInformationByHandle(FileDispositionInfo)`), which is
   testable on this host, with its own tests and its own review — not as an adjunct to this phase.
4. **Optional, low priority:** give `documents/parser.py` the same tolerance for a non-`OSError`
   cleanup failure only if a realistic trigger is ever identified (currently none).
5. **Standing:** keep PostgreSQL integration, migrations and unattended destructive cleanup NO-GO
   until their separate prerequisites are satisfied and independently approved.

---

## 18. Explicit final authorization decision

| Decision | Status |
| --- | --- |
| Database-free unit tests | **AUTHORIZED** — 1345/23/0, exit 0 |
| POSIX descriptor-relative deletion | **NOT AUTHORIZED as verified** — NOT VERIFIED until a POSIX run exists |
| Windows filesystem deletion in the application path | **CONDITIONAL** — supervised use only; residual unchanged |
| Archive-based cleanup sweep | **CONDITIONAL** — supervised, with the script's own archive preconditions |
| `__pycache__` pruning (server script, e2e harness) | **AUTHORIZED** — guarded, contained, refusals reported |
| Parser temp-file cleanup change | **AUTHORIZED** — 3 executed tests, defect latent, no contract change |
| PostgreSQL integration | **NOT AUTHORIZED — NO-GO** |
| Migrations / database mutation | **NOT AUTHORIZED — NO-GO** |
| Unattended destructive cleanup | **NOT AUTHORIZED — NO-GO** until limitations 1–3 are closed or explicitly accepted by an independent authority |
| Independent safety review gate | **NOT SATISFIED** — no authorization may rest on the review in §12 |

**Overall: CONDITIONAL PASS.** Two bounded defects were fixed with executed evidence and three
load-bearing negative controls; POSIX remains NOT VERIFIED with a documented blocker and a concrete
next step; the deferrals are justified rather than hidden; and every database and destructive-cleanup
restriction is intact.

---

### Compliance statement

No PostgreSQL connection, migration, mutation or reset; no real cleanup sweep, archive deletion or
user-upload deletion; no `.env` file or credential read or printed; no WSL, Docker, Podman, VM,
package or CI infrastructure installed; no `git reset`, `clean`, `restore`, stash, checkout, rebase,
commit or push (HEAD and the index unchanged); no historical report overwritten. All destructive
tests and all three negative controls ran in temporary directories; each mutated file was restored
byte-identically (verified by digest) and the affected suites were re-run green afterwards; the test
leftovers created by the pre-fix version of the new test were removed, and the fixed test was measured
to create none.
