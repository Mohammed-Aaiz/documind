# STEP 1.6AA — POSIX Verification and Independent Safety Gate

Date: 2026-10-13
Owner: COORDINATOR (this run)
Predecessor: `STEP1_6Z_FILESYSTEM_RACE_AND_INDEPENDENT_VERIFICATION_2026-10-13.md` (SHA-256 prefix `1660eab85357e9eb`, unchanged by this step)
Verdict: **CONDITIONAL PASS**

Append-only evidence. Facts, inferences and unverified claims are labelled as such. No database
connection, migration, mutation, real cleanup sweep, commit, push or destructive Git operation was
performed. Historical reports were not overwritten.

---

## 1. Executive summary and final verdict

**Verdict: CONDITIONAL PASS.**

What this step actually did, with the evidence that supports it:

1. **Re-validated the current safety boundary from source** (Workstream A): a complete
   destructive-operation inventory of `backend/` (excluding `phases/`, `models/`, `venv/`,
   `tests/`) — every `unlink`, `rmdir`, `rmtree`, `os.remove`, `os.replace`, `truncate`, destructive
   `move` and temp-file cleanup site, with its validation, race window, available mitigation, test
   and residual risk (§4).
2. **Rechecked the environment instead of repeating 1.6Z** (Workstream B): `uname -s` is
   `MINGW64_NT-10.0-26300`; `wsl.exe` reports "The Windows Subsystem for Linux is not installed";
   `docker`, `podman`, `python3` are absent; there is no `.github/`, `.gitlab-ci.yml`,
   `azure-pipelines.yml`, `Jenkinsfile`, `.circleci`, `.woodpecker.yml` or `bitbucket-pipelines.yml`;
   `act`/`gh` are absent. The origin remote exists but has no CI configuration to run.
   **POSIX execution: NOT VERIFIED** — with fresh evidence, not a copied conclusion (§7, §8).
3. **Closed the one in-scope, testable bypass** the inventory found (Workstream C): the import-time
   `__pycache__` sweep in `scripts/start_server.py`, which 1.6Z recorded as finding C and which
   Workstream A names for inspection. It used
   `shutil.rmtree(..., ignore_errors=True)` on every `__pycache__` name found while walking the CWD:
   no containment, no reparse-point check, every failure swallowed, and a `__pycache__` replaced by a
   junction would have been recursed into and its target emptied. It now goes through a new shared
   helper, `cleanup_path.prune_pycache_beneath`, and reports every refusal (§9).
4. **Hardened that helper against two reviewer findings while implementing it** (F-0, F-1): the root
   is now validated with `intended_root` (a linked root was previously accepted, and `Path.is_dir()`
   follows a link), and every entry is classified from a single `lstat` so a link is refused rather
   than traversed (§9, §12).
5. **Produced three negative controls that each fail a specific test** when their protection is
   disabled — root validation, the inner link refusal, and the candidate containment gate are all
   load-bearing, not decorative — then restored the implementation byte-identically and re-ran the
   suite (§11).
6. **Obtained an adversarial review** of the final source by a separate agent instance, with six
   findings (F-0…F-5) tracked, two fixed, two confirmed-safe, one recorded as an explicit residual
   and one correcting the inventory. The reviewer is **not** organisationally independent:
   `INDEPENDENT REVIEW GATE NOT SATISFIED` (§12).

**What did not change, deliberately:** `storage/file_store.delete_upload` remains pathname-based.
Adding a descriptor-relative or handle-bound arm there would ship destructive production code in the
path users depend on for upload deletion that **cannot be executed on this host at all**; the
reviewer agreed with this bounding (§12 F-5), and it stays a documented residual (risk 4, §14) with
the POSIX run as its precondition.

**Verification in one line:** `venv/Scripts/python.exe -m pytest -q tests/unit` → **1339 passed,
23 skipped, 0 failed**, exit 0, with the frozen benchmark digest, the upload tree, the published
reports and all four predecessor reports provably unchanged (§16).

**Why not PASS:** POSIX descriptor-relative deletion and POSIX symlink behavior are still
unexecuted; the Windows pathname residual remains; the independent-review gate is not satisfied as
an organisational control; and PostgreSQL integration, migrations/DB mutation and unattended
destructive cleanup stay NO-GO (§15, §17).

---

## 2. Initial repository state and preservation evidence

| Item | Value |
| --- | --- |
| HEAD at start and end | `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged) |
| Branch | `main` |
| Staged files | 0 (`git diff --cached --name-only` → empty) |
| Working-tree inventory | `git status --porcelain` → **385 entries**, identical in count to the 1.6Z end state; the pre-existing deletions/modified set and the untracked `evaluation/**`, `scripts/**`, `tests/**` layout are the baseline, not this step's output |
| Interpreter used | `backend/venv/Scripts/python.exe` — Python **3.11.0** (the 1.6Y/1.6Z baseline interpreter); the full suite was also run under `py -3` (3.13.12, pytest 8.3.4) with **identical counts** |
| Host | Windows, `uname -s` = `MINGW64_NT-10.0-26300`, `uname -r` = `3.3.6-341.x86_64` (Git Bash, `uname` is MSYS, not a POSIX kernel) |
| `.env` / credentials | **not read** |
| Real cleanup sweep, archive deletion, production deletion | **not run** |
| Destructive tests | confined to `tmp_path` / `tempfile.mkdtemp` |

Preserved operations: no `git reset`, `clean`, `restore`, stash, checkout, rebase or history
rewrite; nothing committed or pushed; no historical report modified (§16).

Files this step touched (all after the 1.6Z report):

| Path | Change |
| --- | --- |
| `scripts/cleanup_path.py` | new `prune_pycache_beneath` (guarded `__pycache__` removal) |
| `scripts/start_server.py` | the import-time sweep now calls that helper; `shutil` import removed; `sys.path` bootstrap added |
| `tests/unit/scripts/test_pycache_prune_safety.py` | **new** — 11 tests (containment, link refusal, linked root, differential non-vacuity, refusal reporting, caller source guards) |
| `architecture/STEP1_6AA_POSIX_VERIFICATION_AND_INDEPENDENT_SAFETY_GATE_2026-10-13.md` | **new — this report** |

No other `.py` file under `backend/` was modified: the change set was enumerated from file mtimes in
the working tree and cross-checked against the diff of every file named above.

---

## 3. Revalidation of Step 1.6Z claims

| 1.6Z claim | Rechecked how | Result |
| --- | --- | --- |
| Descriptor-relative helpers exist and never fall back to a pathname delete | read `scripts/cleanup_path.py:246-277, 321-349, 352-395, 398-428` | **Confirmed** (fact: source) |
| `open_root_fd` raises instead of returning `None` when a root cannot be held on a supporting platform | read `:266-277`; tests run | **Confirmed** — `test_an_unholdable_root_on_a_supporting_platform_is_a_refusal` still passes |
| Callers refuse rather than degrade | `scripts/cleanup_smoke.py:158-168, 230-236`; `scripts/cleanup_orphan_uploads.py:354-360` | **Confirmed** |
| Archive creation is exclusive and verification uses the same handle | `scripts/cleanup_orphan_uploads.py:202, 216-250` | **Confirmed** |
| An incomplete archive is left in place; no pathname delete remains on that path | `:236-250` | **Confirmed** |
| Function-level authorization gates were added to the two 3E inline deletions | `evaluation/experiments/run_phase3e_integration.py:512`, `run_phase3e_validation.py:580` | **Confirmed** |
| Benchmark, upload tree, reports unchanged; historical reports not overwritten | digests and manifests (§16) | **Confirmed**; the 1.6Z report itself is byte-identical (`1660eab85357e9eb`) |
| Race window "BLOCKED — no testable mitigation" | see §6 | **Superseded in part** — mitigated on POSIX (unexecuted here), open on Windows; now recorded as PARTIAL, not closed |
| `scripts/start_server.py` `rmtree(ignore_errors=True)` outside the boundary | read `:61-62` in the 1.6Z state; inventory | **Confirmed, and now FIXED** (§9) |
| Independent review not satisfied; `VERIFIER` not a runtime agent | §12 | **Confirmed** |

---

## 4. Current destructive-operation inventory

`backend/`, excluding `phases/`, `models/`, `venv/`, `eval`-irrelevant trees. Every row is a source
fact unless marked *(inference)*. "Execution" is what was actually observed in this step.

| # | Operation | Source | Validation before the operation | Race window | Mitigation | Test | Execution | Residual risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Delete an uploaded file (application runtime) | `storage/file_store.py:195` (`candidate.unlink()`) | `..` refusal (`:171`), resolved containment (`:167`), link/reparse refusal for candidate and resolved path (`:168-170`), link-ancestor walk (`:178-180`), `S_ISREG` (`:188-190`) | validate → pathname `unlink` | none (pathname flow) | `tests/unit/scripts/test_file_store_deletion_safety.py`, `test_reparse_points_and_race_safety.py` | passed (unit) | **Open**: a swap between validation and `unlink` deletes an unvalidated file inside the root. *Not closed deliberately* (§12 F-5) |
| 2 | Clean up a newly created upload after a failed DB commit | `storage/file_store.py:201-214` → `delete_upload` | same as row 1 | same | none | covered via row 1 | passed | same as row 1 |
| 3 | Delete named upload files (smoke helper) | `scripts/cleanup_smoke.py:189` (`unlink_beneath`), `:248` (`user_dir.rmdir()`) | `intended_root` before any side effect; per-candidate `resolve_stored_path` + `validate_candidate` | POSIX: closed for parents/root; Windows: validate → pathname unlink | `unlink_beneath` / `rmdir_beneath` on POSIX; fail-closed refusal if the root cannot be held | `test_cleanup_smoke_safety.py` (26 tests), `test_descriptor_relative_deletion.py` | passed (23) / POSIX-only **skipped (8)** | Windows parent/candidate swap; POSIX arm unexecuted here |
| 4 | Remove orphaned uploads (sweep) | `scripts/cleanup_orphan_uploads.py:391` (`path.unlink()`), `:431` (`path.rmdir()`) | `intended_root`, per-candidate `validate_candidate`, referenced-set check | POSIX: closed for parents/root; Windows: open | `unlink_beneath` / `rmdir_beneath` on POSIX | `test_cleanup_orphan_uploads.py` (34), `test_race_substitution_deterministic.py` (7) | passed | same split as row 3 |
| 5 | Create/verify/remove a cleanup archive | `scripts/cleanup_orphan_uploads.py:202` (`open(..., "x+b")`), `:216-250` | destination not inside root, not a link, `archive.exists()` pre-check, candidate validation | creation is exclusive; verification is handle-bound | exclusive create + same-handle CRC verification; failed write leaves the fragment (no pathname delete) | orphan tests + race tests | passed (incl. a negative control) | a parent swapped for a link can place the archive elsewhere (no deletion escape) |
| 6 | Clear bytecode caches at import | `scripts/start_server.py:75` → `scripts/cleanup_path.py:280-363` (`prune_pycache_beneath`) | `intended_root(root)` (missing/linked/mismatched root refuses), per-candidate `validate_candidate`, single-`lstat` entry classification | *narrows* prior behavior; a swap between the per-entry `lstat` and the `unlink`/`rmdir` remains *(inference, same class as row 1)* | new helper: containment, link/reparse refusal (never traversed), refusals returned and printed | `tests/unit/scripts/test_pycache_prune_safety.py` (11) | **passed (11)**; helper callable via the same bootstrap from an unrelated CWD | a `rename` inside the cache tree in that window; cache trees are repository bytecode, not user data |
| 7 | Second `__pycache__` sweep | `tests/e2e/browser/test_phase6_reliability.py:40` (`shutil.rmtree(pycache, ignore_errors=True)`) | none | as above | none | not run (e2e, needs a live server) | **not run** | same class as the fixed site; test harness, not operational code. *Reviewer F-2(a). Recorded, not fixed in this step* |
| 8 | Publish evaluation evidence (temp swap) | `evaluation/artifacts.py:232-236` (`os.replace`, `temporary.unlink()`) | unique per-process temp name `<name>.<pid>.<8 hex>.tmp`, created by the immediately preceding `open(...)` | destination replacement is atomic; temp cleanup acts on its own file | `write_evidence` append-only by default; `replace=True` explicit | `test_writer_collision_*` | passed | none material; reviewer F-2(b) **confirmed safe** |
| 9 | Remove its own temp file after a parse | `documents/parser.py:445-451` (`os.unlink(tmp_path)` in a bare `finally`) | none needed (its own `NamedTemporaryFile`) | n/a (own temp file) | none | `tests/unit/documents/test_structured_extraction.py` | passed | a failed unlink on Windows turns a successful parse into an exception. *Reviewer F-2(c); recorded, not fixed — out of this step's scope* |
| 10 | Remove its own TTS temp file | `voice.py:258-261` (`os.unlink`, `OSError` caught) | n/a (own temp file) | n/a | `OSError` caught | n/a | not exercised | none material |
| 11 | Delete harness fixture uploads | `evaluation/experiments/run_phase3e_integration.py:290,319,387,418,543`; `run_phase3e_validation.py:268,357,630,777,824` | each removes a path the same run created under `tempfile` | n/a (own fixtures) | runner-level disposal gate refuses before `main()` body | `test_phase3_runner_target_order.py`, inline-SQL guard tests | passed (text-based) | none material; the runs are blocked anyway |
| 12 | Inline row deletions inside phase runners | `run_phase3e_integration.py:512`, `run_phase3e_validation.py:580` (ORM `delete(...)`) | `assert_cleanup_execution_authorized` immediately before | n/a | function-level gate that refuses unconditionally | `test_phase3d_upload_inline_sql_guard.py` (13) | passed | none: gate refuses, so the block is unreachable |

Searches run to build this table: `shutil.rmtree`, `os.remove|os.unlink|os.rmdir|os.replace`,
`.unlink(|.rmdir(`, `def delete_upload|def cleanup_new_file|ignore_errors=True`, and
`unlink_beneath|rmdir_beneath|open_root_fd`, each with `-g '!phases/**' -g '!models/**'
-g '!venv/**' -g '!**/__pycache__/**'`. **No other destructive call site exists** in the searched
scope (reviewer F-5 re-searched independently and confirmed the same set).

---

## 5. Filesystem threat model

Cases: **A** lexical traversal, **B** link/reparse traversal, **C** object replacement, **D** parent
replacement, **E** concurrent operations, **F** archive substitution.

| Operation | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1–2 `file_store.delete_upload` | refused (`..`, containment) | refused (candidate, resolved path, ancestor walk) | **open** (pathname `unlink`) | **open** (parent not held) | open | n/a |
| 3 `cleanup_smoke` | refused | refused | **open on Windows**, closed on POSIX (name swap only) | POSIX closed, **Windows open** | reported (`missing`/`refused`) | n/a |
| 4 orphan sweep | refused | refused | as row 3 | as row 3 | reported | n/a |
| 5 archive | refused (destination may not be inside the root) | refused (archive path) | closed (exclusive create) | **open** (archive parent not held; no deletion escape) | n/a | closed (create + verify on one handle) |
| 6 `prune_pycache_beneath` | refused (`intended_root`, containment) | refused (root, every candidate, every entry — never traversed) | *(inference)* narrow window between per-entry `lstat` and `unlink`/`rmdir` | **open** (parent directories not held) | n/a | n/a |
| 8 `write_evidence` | refused | n/a | closed (exclusive create; atomic `os.replace`) | n/a | temp name unique per process | n/a |

The honest statement of the boundary: **a validation result must never be reused for an object that
may have changed, and only handle-bound or descriptor-relative operations can bind a delete to the
validated object.** Rows 3–5 achieve that on POSIX (unexecuted here) and cannot on Windows, where the
platform exposes no equivalent primitive for `unlink`/`rmdir`. Row 6 was the one site where a
*recursive* delete could be redirected out of any tree at all; that is now bounded (§9).

---

## 6. Race windows and platform-specific guarantees

| Window | Platform | Before this step | After this step | Evidence |
| --- | --- | --- | --- | --- |
| Root replaced between validation and delete | POSIX | open | **closed for parents/root** (descriptor held, `O_NOFOLLOW` descent) | source + POSIX-only tests (**not executed here**) |
| Same | Windows | open | **unchanged, documented** | — |
| Parent replaced between validation and delete | POSIX / Windows | open / open | closed / unchanged | as above |
| Entry replaced inside a held directory (final name) | both | open | **still open by construction** — no stdlib primitive binds a name to an earlier `lstat`; consequence bounded to the already-validated directory | stated in `cleanup_path.py` docstring; not claimed fixed |
| `__pycache__` candidate replaced by a link, or a link nested inside it | both | **open and unguarded** (`shutil.rmtree`, `ignore_errors=True`, no containment) | **refused (never followed), and reported** | 11 passing tests, 3 negative controls (§11) |
| Root given to the cache prune is itself a link | both | open (`Path.is_dir()` follows it) | **refused** (`intended_root`) | `test_a_linked_root_is_a_refusal` + negative control (a) |
| Archive destination planted after the existence check | both | closed in 1.6Z (exclusive create) | unchanged | re-verified: test + negative control in 1.6Z |
| Archive verified by pathname re-open | both | closed in 1.6Z (same handle) | unchanged | re-verified |
| Root cannot be held on a platform that supports holding | POSIX | open (silent pathname fallback) | **closed** (raises; callers refuse) | 1.6Z tests still pass |
| Concurrent sweeps over one candidate | both | reported | unchanged | idempotence test |

**Platform guarantees (fact):** POSIX provides descriptor-relative `unlink`/`rmdir`
(`os.unlink in os.supports_dir_fd`) and `O_NOFOLLOW` — used. Windows provides neither for
`unlink`/`rmdir`; the standard library exposes no handle-bound delete, so no equivalent guarantee is
implemented, and none is claimed. A Windows handle-bound delete exists in the Win32 API
(`CreateFileW` with `FILE_FLAG_OPEN_REPARSE_POINT` + `SetFileInformationByHandle`), but it would be
raw `ctypes` destructive code in the production upload-deletion path and is **not** proposed as a
blind edit in this step; it is recorded as the concrete follow-up (§18).

---

## 7. POSIX environment availability investigation (fresh, not copied)

| Facility | Probe | Observed |
| --- | --- | --- |
| POSIX kernel | `uname -s`, `uname -r` | `MINGW64_NT-10.0-26300`, `3.3.6-341.x86_64` — Git Bash/MSYS on Windows |
| `/proc` | `ls /proc/version` | present but MSYS-emulated; reports `MINGW64_NT-10.0-26300 version 3.3.6-341.x86_64` |
| WSL | `wsl.exe -l -q < /dev/null` | "The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'." (UTF-16 output; exits 0) — **bounded probe, stdin redirected so it cannot block** |
| Docker / Podman | `command -v docker podman podman-compose` | all **absent** |
| POSIX Python | `command -v python3` | **absent** (only `py -3` / `venv/Scripts/python.exe`, both Windows builds) |
| Repository CI | existence check of `.github/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci`, `.woodpecker.yml`, `bitbucket-pipelines.yml` | **none present** |
| CI runners locally | `command -v act gh` | **absent** |
| Remote | `git remote -v` | `origin https://github.com/Mohammed-Aaiz/documind.git` — exists, but the repository contains no CI configuration to trigger, and running a remote workflow would require pushing (prohibited) |

No WSL, Docker, CI platform or other heavyweight infrastructure was installed, and no system change
was made: the task forbids it and no progress would be genuine.

---

## 8. Exact POSIX test commands and results, or the documented blocker

**POSIX-specific verification: NOT VERIFIED.**

* Commands intended for a POSIX host (not run here, because no POSIX host exists):
  `python -m pytest -q tests/unit/scripts tests/unit/documents`.
* What that run would execute, and what currently skips instead: 9 POSIX dir-fd-only tests —
  `tests/unit/scripts/test_descriptor_relative_deletion.py` (8: real `unlink_beneath` /
  `rmdir_beneath`, `O_NOFOLLOW` descent, symlinked intermediate, parent swap, "replacement stays
  inside the root", missing-root refusal against the real `os.open`) and
  `tests/unit/scripts/test_cleanup_smoke_safety.py:385` (the real descriptor-path removal).
  Each skips with `requires POSIX dir_fd support (os.unlink in os.supports_dir_fd); not available
  on Windows`.
* Windows tests are **not** treated as POSIX evidence. The new `__pycache__` tests are the one place
  where the same scenarios run on both platforms by construction: they use junctions on Windows and
  real directory symlinks on POSIX (`sys.platform == "win32"` branch), so they will execute rather
  than skip when a POSIX host exists.
* Exact blocker: **no POSIX kernel and no CI runner available in this environment or repository**,
  with the probes of §7 as evidence. The smallest safe way to close it is a Linux host or a Linux CI
  job running the two test paths above against this working tree; adding CI configuration was not
  done, because there is no existing CI architecture to extend and a new one could not be verified
  from here.

---

## 9. Implementation changes and why each was necessary

### 9.1 `scripts/cleanup_path.py` — `prune_pycache_beneath(root) -> (removed, refused)`

**Why:** the inventory found an import-time recursive delete (`scripts/start_server.py:61-62` in the
1.6Z state) that was contained by nothing and followed whatever a `__pycache__` name pointed at,
with `ignore_errors=True` hiding every failure. A `__pycache__` replaced by a junction — the exact
substitution this project already models in its upload tests — would have had its target emptied
silently.

**What it does** (`scripts/cleanup_path.py:280-363`): establishes the root with `intended_root` (so a missing root, a linked/reparse root
and a lexical-vs-resolved mismatch are refusals); walks with `os.walk(..., followlinks=False)`,
skipping the candidate inside the walk and never descending into it; validates each candidate with
`validate_candidate(root, candidate, expect="directory")`; then removes that tree depth-first, where
every entry is classified from a **single `os.lstat`** — `S_ISLNK` or the `FILE_ATTRIBUTE_REPARSE_POINT`
bit is a refusal that is *never* traversed, `S_ISDIR` recurses, anything else is `os.unlink`ed. Every
refusal is appended to the returned list and printed by the caller.

**Why the root validation and the single-`lstat` decision are part of the change** (reviewer F-0 and
F-1, both found after the first draft of this helper): `Path.is_dir()` follows a link, so a *linked
root* was accepted and its target swept; and `entry.is_dir()` follows a link too, adding a syscall
between the link check and the type decision. Both are now decided from validated or single-syscall
evidence. The remaining `rename`-after-`lstat` window is recorded as a residual (§14), not claimed
closed.

### 9.2 `scripts/start_server.py` — call site

The bare sweep is replaced by:

```python
_pruned, _refused = cleanup_path.prune_pycache_beneath(_BACKEND_DIR)
print(f"Cleared {_pruned} __pycache__ directory(ies)")
for _entry in _refused:
    print(f"  skipped: {_entry}")
```

plus the `sys.path` bootstrap the other scripts in `scripts/` already use, so
`import scripts.cleanup_path` works when the file is launched as
`python scripts/start_server.py` from `backend/`. `import shutil` was removed with its only use. The
prune still runs before `subprocess.Popen` (asserted by test).

**Facts about this change:** it has no database access, no `.env` read and no heavy import
(`scripts/cleanup_path` imports only `os`, `stat`, `pathlib`), so it cannot change startup behaviour
beyond the sweep itself; the uvicorn child runs with `-B` and its own `PATH`/`sys.path`, so the
parent's bootstrap cannot affect it. **Not run:** `scripts/start_server.py` executes a port check, an
Alembic migration inside the app lifespan and a 120-second readiness loop, so executing it is
prohibited here (it would run migrations and start a server). Its behaviour is pinned by source-read
tests plus an out-of-process check that the helper is importable and callable exactly as the script
calls it (§10).

### 9.3 Not changed, and why

* `storage/file_store.delete_upload` — descriptor/handle-bound arm **not implemented**: it would be
  destructive production code that cannot be executed on this host (the task's own rule), in the path
  users depend on for upload deletion. Reviewer concurred (F-5) with the conditions that it stays in
  the unresolved-risk table and that whoever adds it runs the POSIX suite first. Risks 1 and 4 (§14).
* `tests/e2e/browser/test_phase6_reliability.py:40` — the same `rmtree(..., ignore_errors=True)`
  class in an e2e harness. Recorded (row 7) rather than edited: it needs a live server to verify and
  is not operational code.
* `documents/parser.py:451` — its own temp file, bare `finally` without `OSError` handling. Recorded
  (row 9); out of scope for a filesystem-safety step.
* `evaluation/artifacts.py` — re-inspected, no change: reviewer confirmed its temp cleanup acts only
  on its own uniquely named file (F-2(b)).

---

## 10. Deterministic race-test evidence

New file: `tests/unit/scripts/test_pycache_prune_safety.py` — **11 tests, all executed here, 0
skipped** (junctions need no elevation; on POSIX the same tests use real directory symlinks).

| Test | Invariant asserted | Determinism mechanism |
| --- | --- | --- |
| `test_removes_real_pycache_directories_and_nothing_else` | only caches are removed; sibling sources and parent dirs survive | real nested tree in `tmp_path` |
| `test_a_linked_root_is_a_refusal` | a linked root is refused and its target's cache survives (F-0) | junction/symlink root created before the call |
| `test_a_regular_directory_is_removed_where_the_link_is_refused` | **differential**: same shape, only the link differs → `removed == 1`, the link reported, the target untouched | both candidates present in one call, so a sweep that removed nothing or removed everything fails |
| `test_a_linked_pycache_is_refused_and_its_target_survives` | a candidate that is itself a link is refused; target bytes identical | junction/symlink substituted at the candidate path |
| `test_a_link_nested_inside_a_pycache_is_refused` | a link *inside* the cache is refused and never traversed | link nested one level down; asserts the target's file is byte-identical |
| `test_a_pycache_outside_the_root_is_not_touched` | reach is bounded by the root (containment by construction — stated as such in the docstring) | outside tree with a sentinel |
| `test_a_file_named_pycache_is_never_a_candidate` | a file named `__pycache__` is left alone | real file at the candidate name |
| `test_a_missing_root_is_a_refusal_not_a_no_op` | `RuntimeError`, never a silent no-op | missing path |
| `test_no_bare_recursive_delete_remains` / `test_the_shared_boundary_helper_is_used` / `test_the_prune_happens_before_the_server_starts` | no `shutil.rmtree`, no `ignore_errors`, the helper is used and precedes `Popen` | source read as text (executable lines only, comments excluded), the established pattern for files that cannot be imported safely |

Cross-process check of the call shape (`scripts/start_server.py` cannot be imported, so this was run
out of process): from an unrelated CWD, with the same `sys.path` bootstrap, `prune_pycache_beneath`
on a temporary tree removed the real cache and left an unrelated linked directory untouched. Not a
claim about the server's behaviour — a claim that the helper is importable and callable exactly as
the script calls it.

Re-verified unchanged from 1.6Z (tests re-run, not assumed): the archive-substitution test with its
consulted-`exists` and creation-branch guards, the descriptor-refusal tests, the fail-closed
root-hold tests, and the sweep-abort test.

---

## 11. Negative-control results

Three controls, each performed against the **final** implementation in an isolated temporary
fixture — never against real user data, real uploads or production paths. Each mutation was applied
in place, the targeted test run, then the file restored from bytes captured before the mutation.

| Control | Protection disabled by | Targeted test | Observed |
| --- | --- | --- | --- |
| (a) | replacing `root = intended_root(root)` with `root = Path(root)` | `test_a_linked_root_is_a_refusal` | **1 failed**, exit 1 |
| (b) | neutralizing the single-`lstat` link/reparse refusal | `test_a_link_nested_inside_a_pycache_is_refused` | **1 failed**, exit 1 |
| (c) | neutralizing the per-candidate `validate_candidate` gate | `test_a_regular_directory_is_removed_where_the_link_is_refused` | **1 failed**, exit 1 — the walk then entered the linked candidate and emptied the outside target |

Control (c) is the most informative: the candidate gate is **not** redundant defence-in-depth — it is
what stops the walk from entering a linked candidate at all, and removing it is observable from a
test that runs on this host.

Restoration: `scripts/cleanup_path.py` returned to SHA-256 prefix `97dbc1b6559a402a`, verified
byte-identical after every control, and the full 11-test file then passed (`exit 0`). No control
touched any path outside its temporary fixture, and no stray artifact remains (§16).

From 1.6Z, still valid and re-checked by re-running their tests: reverting the archive create mode
from `"x+b"` to `"w"` fails the archive-substitution test; an injected unfired substitution hook
fails its test at teardown.

---

## 12. Independent review identity, findings and limitations

| Item | Value |
| --- | --- |
| Reviewer | a separate agent instance (worker agent), adversarial brief, **read-only**, no terminal, no web |
| Scope | the final source of `scripts/cleanup_path.py` (including `prune_pycache_beneath`), `scripts/start_server.py`, the new test file, `storage/file_store.py:137-214`, `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, plus an independent destructive-site search |
| Verdicts returned | claims 1 **PARTIALLY CONFIRMED**, 2 CONFIRMED, 3 CONFIRMED, 4 CONFIRMED, 5 **CONFIRMED as a judgement**, 6 **REFUTED as complete** |
| Independence | **NOT SATISFIED** — same model family, same execution context, could execute nothing; it stated this itself, and it edited no files. **INDEPENDENT REVIEW GATE NOT SATISFIED** |

| ID | Severity | Finding (source location) | Disposition |
| --- | --- | --- | --- |
| F-0 | low | `prune_pycache_beneath` validated its root only with `Path.is_dir()`, which follows a link, so a linked root would have been swept via its target (`cleanup_path.py:299` in the version reviewed) | **FIXED AND RETESTED** — root now established with `intended_root`; `test_a_linked_root_is_a_refusal` added; negative control (a) proves the test is load-bearing |
| F-1 | low | `entry.is_dir()` followed links, adding a separate syscall between the link check and the type decision (`cleanup_path.py:316`) | **PARTIAL: narrowed, residual recorded.** Every entry is now classified from one `os.lstat` (`S_ISLNK`/reparse → refuse, `S_ISDIR` → recurse, else unlink). A `rename` after that `lstat` and before the `unlink`/`rmdir` remains and is documented as a residual (§14 risk 3) — not claimed closed |
| F-2 | informational | the inventory omitted three sites: the e2e harness `rmtree` (`tests/e2e/browser/test_phase6_reliability.py:40`), `evaluation/artifacts.py:236` (which the reviewer **confirmed safe**), and `documents/parser.py:445-451` (own temp file, bare `finally`) | **ACCEPTED** — all three are now rows 7, 8 and 9 of §4; only row 8 is confirmed safe, the other two are recorded limitations, not silently dropped |
| F-3 | informational | `start_server.py` prints refusals and then starts the server regardless; and a mid-tree refusal leaves already-unlinked files deleted while the directory survives | **ACCEPTED, documented** — a refusal is reported, never hidden, but "refused" is not "nothing changed". Stated as such in §10 and risk 3 |
| F-4 | informational | two of the nine tests were weaker than their names suggest: the outside-root test proves containment by construction, and the `__pycache__`-file test asserts the absence of a report | **FIXED (test quality)** — docstrings now say exactly that, and a **differential** test was added (real directory removed *and* linked candidate refused in one call) so the protection is falsified by a failing test rather than assumed |
| F-5 | — | the decision not to add descriptor/handle-bound deletion to `storage/file_store.delete_upload` | **CONFIRMED acceptable**, with the conditions the reviewer attached (kept in the unresolved-risk table; operation stays supervised; POSIX suite run first) — all conditions are met in §14/§18 |

The reviewer also confirmed, with quoted lines: containment holds even when `os.walk` descends into
a junction (Windows `os.walk` does not treat a junction as a symlink), so the linked candidate is
caught twice; the `sys.path` bootstrap matches the convention already used by
`cleanup_smoke.py:66/81` and `cleanup_orphan_uploads.py:54/69` and introduces no circular or heavy
import; and the prune ordering before `Popen` is provable from the text.

Honest limitation of this gate: a same-family reviewer that cannot execute anything is a useful
adversary, not an independent safety authority. Nothing above should be read as independent
verification.

---

## 13. Database lifecycle status

Documentation and source inspection only — **no connection, no migration, no mutation, no `.env`
read** in this step.

* Every gate still refuses unconditionally, each raising `UnsafeEvaluationTarget`:
  `record_created_database` (`evaluation/isolation.py:369`), `assert_disposal_authorized` (`:377`,
  ending in a refusal at `:405-411`), `assert_creation_authorized` (`:415`),
  `assert_row_cleanup_authorized` (`:443`, delegating), `assert_cleanup_execution_authorized`
  (`:456`, refusing before inspecting any caller object), `release_database_proof` (`:477`); and
  `_proof_is_live` (`:363`) still returns `False` unconditionally.
* The only lifecycle change in the 1.6Z/1.6AA window **added** two call sites (the two inline
  deletions in the 3E runners). No check was removed, no URL-equality comparison replaced an
  authorization decision, no blocked test was made unconditional, and no direct SQL deletion bypasses
  the boundary.
* Status: **BLOCKED / NO-GO**, with the six-part infrastructure contract of 1.6Y §9 outstanding in
  full (external authority, live connection identity, effective privileges, non-forgeable disposable
  predicate, durable evidence, independent approval).

---

## 14. Unresolved safety risks and their owners

| # | Risk | Owner (contract) | Why it remains | Bounding measure in force |
| --- | --- | --- | --- | --- |
| 1 | POSIX descriptor-relative deletion has never been executed | TEST_AGENT / COORDINATOR | no POSIX host or CI runner exists (§7) | operation stays supervised; POSIX tests exist and will run on such a host |
| 2 | Windows upload deletion keeps a check-then-use residual (`file_store.delete_upload`, the cleanup scripts) | BACKEND_AGENT / SECURITY_AGENT | no `dir_fd` and no stdlib handle-bound delete on Windows | fail-closed refusals; unattended destructive cleanup NO-GO |
| 3 | A `rename` inside the window between the per-entry `lstat` and the `unlink`/`rmdir` (rows 3–6) | SECURITY_AGENT | no primitive binds a name to an earlier `lstat` | shortest possible interval; refusals reported; consequence bounded to the validated directory |
| 4 | `storage/file_store.delete_upload` remains pathname-based | BACKEND_AGENT | closing it needs code that cannot be executed here (reviewer F-5) | five independent refusal checks before `unlink`; documented in three reports |
| 5 | Refused prune on a tree already partially unlinked | BACKEND_AGENT | depth-first removal is not atomic | refusal returned and printed; cache trees are repository bytecode |
| 6 | E2E harness sweep (`test_phase6_reliability.py:40`) | TEST_AGENT | needs a live server to verify; not run | flagged in the inventory; not reachable from the unit suite |
| 7 | `documents/parser.py:451` temp cleanup can raise in a bare `finally` | BACKEND_AGENT | out of scope for this step | own temp file; no containment implication |
| 8 | Independent review not satisfied as an organisational control | COORDINATOR | no external reviewer or separate environment available | reviewer's findings tracked and remediated; limitation stated in three reports |
| 9 | Refused prune does not stop the server from starting | COORDINATOR | developer convenience script | refusal printed (reviewer F-3); documented |

---

## 15. Final readiness matrix

| Capability | Decision | Basis |
| --- | --- | --- |
| Database-free unit tests | **GO** | 1339 passed, 23 skipped, 0 failed, exit 0 (Python 3.11 venv), identical under 3.13.12; `tests/unit/scripts` → 119 passed, 12 skipped, exit 0 |
| POSIX descriptor-relative deletion | **NOT VERIFIED** | implemented; 9 POSIX-only tests skip; no POSIX host or CI (§7, §8) |
| Windows filesystem deletion | **CONDITIONAL** | every path refuses links/`..`/non-regular candidates and reports refusals; the check-then-use residual and the unclosable final-name swap remain (risks 2, 3) |
| Archive integrity | **CONDITIONAL** | exclusive create, same-handle CRC verification, incomplete archive left in place, no pathname delete on the failure path; a swapped archive parent can relocate the archive, with no deletion escape |
| Shared cleanup authorization boundary | **CONDITIONAL** | the last out-of-boundary recursive delete is closed and tested; `file_store.delete_upload` keeps a hand-maintained copy of the policy (risk 4) and the e2e harness sweep is flagged (risk 6) |
| Independent safety review | **NOT SATISFIED** | same-family, non-executing reviewer; no external reviewer available |
| PostgreSQL integration | **NO-GO** | six-part contract outstanding (§13) |
| Migrations and database mutation | **NO-GO** | unchanged |
| Unattended destructive cleanup | **NO-GO** | risks 1–3 outstanding |

A green suite does not authorize database operations or unattended cleanup; nothing in this report
should be read as doing so.

---

## 16. Git and protected-artifact integrity results

| Check | Result |
| --- | --- |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` — unchanged |
| Index | 0 staged files |
| Working tree | `git status --porcelain` → 385 entries (same count as the 1.6Z end state); no `.tmp`, `.bak` or negative-control artifacts |
| Frozen benchmark | `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` SHA-256 = `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches** |
| Upload tree | 1212 files, 7 386 232 bytes, **0 modified today** |
| Published reports | 51 files; newest real artifact `evaluation/reports/table_evidence_measurement_analysis.json`, 2026-10-06 |
| Predecessor reports | `UNIFIED…` `66b53544ebffd2d0`, `STEP1_6X…` `b0cbefef7d9cab14`, `STEP1_6Y…` `92ee2315822071b2`, `STEP1_6Z…` `1660eab85357e9eb` — all **unchanged** |
| Stray temp/backup artifacts under `backend/` | **0** |
| Compilation | `compileall` on `scripts evaluation tests/unit/scripts` → clean, exit 0 |
| Real `.env` / credentials read | **no** |

No discrepancy with the 1.6Z baseline was found. The only working-tree change is the file set listed
in §2, all of which is this step's own work.

---

## 17. Explicit authorization decision

| Decision | Status |
| --- | --- |
| Database-free unit tests | **AUTHORIZED** — pass with the counts above |
| POSIX descriptor-relative deletion | **NOT AUTHORIZED as verified** — remains unverified until a POSIX run exists (§8) |
| Windows filesystem deletion in the application path | **CONDITIONAL** — supervised use only; the residual of risks 2–3 is unchanged |
| Archive-based cleanup sweep | **CONDITIONAL** — supervised, with the archive preconditions enforced by the script itself |
| PostgreSQL integration | **NOT AUTHORIZED — NO-GO** |
| Migrations / database mutation | **NOT AUTHORIZED — NO-GO** |
| Unattended destructive cleanup | **NOT AUTHORIZED — NO-GO** until risks 1, 2 and 3 are closed or explicitly accepted by an independent authority |
| Independent safety review gate | **NOT SATISFIED** — no authorization may rest on this review |

---

## 18. Recommended next bounded step

**Obtain POSIX execution first.** The single highest-value, lowest-risk action is a run of
`python -m pytest -q tests/unit/scripts tests/unit/documents` on a Linux host or Linux CI job against
this working tree. It converts risks 1 and 3 from unverified to measured, and it is the precondition
the reviewer attached to touching `storage/file_store.delete_upload` (risk 4).

Only after that run:

1. Add the same descriptor-relative arm to `storage/file_store.delete_upload` — keeping the two
   implementations in step by hand as the module comment requires — with POSIX tests that execute on
   the new host, then re-run the upload deletion tests on both platforms.
2. Consider the Windows handle-bound route for the same path (`CreateFileW` with
   `FILE_FLAG_OPEN_REPARSE_POINT` + `SetFileInformationByHandle(FileDispositionInfo)`), which *is*
   testable on this host because it is a Windows API, and which would close the Windows candidate
   substitution window that no stdlib primitive can. It is raw `ctypes` in a destructive production
   path, so it needs its own design note, its own tests and its own review before any edit.
3. Optional, low priority: route the e2e harness sweep (`tests/e2e/browser/test_phase6_reliability.py:40`)
   through `prune_pycache_beneath`, and give `documents/parser.py:451` the same `OSError` tolerance
   `voice.py:261` already has.

**Do not** authorize unattended destructive cleanup, PostgreSQL integration, migrations or database
mutation on the strength of this report.

---

### Compliance statement

No database connection, migration, mutation or reset was performed; no real cleanup sweep, archive
deletion or user-upload deletion was run; no `.env` file or credential was read; no WSL, Docker, CI
platform or other heavyweight infrastructure was installed; no `git reset`, `clean`, `restore`,
stash, checkout, rebase, commit or push was issued (HEAD and the index are unchanged); no historical
report was overwritten. All destructive-path tests and all three negative controls ran inside
temporary directories, and `scripts/cleanup_path.py` was verified byte-identical
(`97dbc1b6559a402a`) after each control, with 11/11 tests passing on the restored implementation and
no stray artifacts left in the repository.
