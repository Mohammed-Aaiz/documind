# STEP 1.6AE — Authorized Linux Verification and Filesystem Remediation Design

Date: 2026-10-14
Owner: COORDINATOR (this run)
Predecessor: `STEP1_6AD_LINUX_VERIFICATION_AND_INDEPENDENT_SAFETY_REVIEW_2026-10-14.md` (`e16438b2d9fc2eba`) — unchanged by this step
Verdict: **CONDITIONAL PASS** (design substantially complete; Linux execution **BLOCKED**; independent review **NOT SATISFIED**; the filesystem-safety gate has **not** passed). No production code was changed.

Every claim below is labelled one of: **EXECUTED** (a command ran this session and its output is
quoted), **SOURCE** (read from the current file), **INFERENCE** (reasoned from source, not executed),
**HISTORICAL** (carried from a predecessor report, not re-run here), **PROPOSED DESIGN** (a plan, not
implemented), **UNVERIFIED** (a claim that needs platform experiments / authoritative API
verification), **SKIPPED** (collected, not run), **REVIEWER** (assessment by a non-executing
reviewer), **NOT VERIFIED**, or **NOT RUN**. No database connection, migration, mutation, real cleanup
sweep, commit, push or destructive Git operation was performed; no historical report was overwritten;
no `.env` or credential was read.

---

## 1. Executive outcome

**CONDITIONAL PASS.** The design deliverable is substantially complete from current source; the
platform-execution and independent-review gates remain open.

* **Linux/POSIX execution: LINUX EXECUTION: BLOCKED — NO AUTHORIZED LINUX RUNTIME AVAILABLE**
  (EXECUTED, §5). Host is Git Bash / **MSYS** on Windows (`uname -s` = `MINGW64_NT-10.0-26300`).
  `wsl.exe` reports the subsystem is **not installed**; `docker`/`podman`/MSYS `python3`/`act`/`gh`
  are absent; there is **no CI configuration**. The nine POSIX dir_fd-only tests therefore still
  **skip**. Nothing was installed.
* **Windows targeted run** (EXECUTED, §10): `python -m pytest -q tests/unit/scripts tests/unit/documents`
  → **267 passed, 13 skipped, exit 0**. **Windows** evidence only.
* **Windows full regression** (EXECUTED, §10): `python -m pytest -q tests/unit` → **1345 passed,
  23 skipped, exit 0**.
* **Compile check** (EXECUTED, §11): `compileall` over the audited packages → clean, exit 0.
* **No production code was changed** (§2). The only file written by this step is this report.
* **Directory-swap race: analysed against current source and confirmed** (§7). A directory classified
  from a single `lstat` at `cleanup_path.py:321` is recursed into at `:332`; a junction/symlink swapped
  in during that interval is followed by `iterdir()` (`:315`) and its **target's contents can be
  deleted outside the root**. Disposition: **NOT FIXED**; a design is proposed (§8).
* **Remediation designs produced (no implementation):** a **POSIX** descriptor-relative algorithm and a
  **Windows** handle-bound algorithm (§8), both with a **safe-refusal fallback contract**; and a
  production-appropriate **upload-deletion contract** for `storage/file_store.delete_upload` (§9). The
  Windows design contains claims explicitly marked **UNVERIFIED** pending platform experiments.
* **Regression-test plan** specified, including a deterministic race-injection test that actually
  creates the validation→use interleaving (§10). **No such test exists today.**
* **Negative control: freshly EXECUTED with byte-identical restoration** (§11).
* **Independent review: NOT SATISFIED** as an organisational control (§12). The reviewer is a
  same-family substitute with no terminal; it executed nothing and wrote no files.
* **Verification in one line:** HEAD `6baaa2a…` unchanged, working tree 385 entries unchanged, frozen
  benchmark digest and upload inventory match the historical values, all predecessor reports are
  byte-identical (§14).

**Why CONDITIONAL PASS, not PASS — DESIGN READY:** the design is substantially complete, but §16's
"PASS — DESIGN READY" requires "sufficient source **and review** evidence"; the independent-review gate
is **NOT SATISFIED**, and the Windows design carries **UNVERIFIED** API claims, so **clearly identified
design/review issues remain open**. The Linux-execution sub-gate is **BLOCKED**. The filesystem-safety
gate has **not** passed. PostgreSQL integration, migrations/DB mutation and unattended destructive
cleanup remain **NO-GO** (§18).

---

## 2. Scope, non-goals, and agent assignments

**In scope.** Verify and preserve the baseline; freshly investigate Linux availability; analyse the
directory-swap race and `storage/file_store.delete_upload`; produce POSIX and Windows remediation
**designs**; specify a regression-test plan; re-run a negative control with verified restoration;
obtain an adversarial review of the design; confirm the database/destructive-cleanup gates are
untouched; produce this report. **This is a design-and-verification step.**

**Non-goals (explicit).** Modifying `scripts/cleanup_path.py`, `storage/file_store.py`, database
authorization code, cleanup runners, or production startup code; installing WSL/Docker/Podman/CI or
system dependencies; provisioning cloud resources; triggering external workflows; running integration
tests, migrations, server startup, or any real cleanup sweep; changing protected artifacts; letting any
worker write the coordinator-owned report. A later implementation step is required before any race is
described as fixed.

### Agent assignments (as actually dispatched — a role name is not proof of execution)

| Contract name | Actual runtime agent | Ran? | Terminal? | Evidence |
| --- | --- | --- | --- | --- |
| `ORCHESTRATOR` | coordinator (this session) | yes | yes | this report; §3/§5/§10/§11/§14 |
| `LINUX_ENVIRONMENT_VERIFIER` | coordinator with terminal | yes | yes | §5 probe table |
| `FILESYSTEM_SECURITY_ARCHITECT` | coordinator (source analysis + design) + one `code-searcher` worker for the destructive-site sweep | yes | coordinator: yes; worker: no | §4, §6, §7, §8, §9 |
| `POSIX_TEST_ENGINEER` | coordinator with terminal (source + test inventory; no POSIX run) | yes | yes | §10, §11 |
| `WINDOWS_FILESYSTEM_SPECIALIST` | coordinator (source analysis); Windows API claims marked UNVERIFIED | yes | yes | §8.3 |
| `INDEPENDENT_SECURITY_REVIEWER` | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only | yes (dispatched) | **no** | §12 (substitute, **not independent**; wrote no files) |
| `DATABASE_SAFETY_AUDITOR` | coordinator, source inspection only | yes | yes | §13 |
| `REPORT_AUDITOR` | one `base3-fast-worker-deepseek-flash` worker, cross-check against the repository, no writes | yes (dispatched) | **no** | §12.8 (source/report consistency only) |

Substitutions and gaps are recorded rather than concealed: no named specialist is claimed to have run
as a runtime agent; the reviewer and the report-auditor are same-family workers, not organisational
controls, and neither could execute anything. Neither wrote or modified any file.

---

## 3. Initial and final repository state

| Item | Initial (EXECUTED) | Final (EXECUTED) | Evidence |
| --- | --- | --- | --- |
| Repository root | `C:/Users/moham/OneDrive/Desktop/stitch_documind_futuristic_3d_ui` | unchanged | `git rev-parse --show-toplevel` |
| Branch | `main` | `main` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | **unchanged** | `git rev-parse HEAD` |
| Index (staged) | 0 files | 0 files | `git diff --cached --name-only \| wc -l` |
| Working tree | **385 entries** = 295 deleted + 35 modified + 55 untracked | **385 entries**, identical breakdown | `git status --porcelain` + `awk` |
| Pre-existing user changes | preserved — nothing reset/cleaned/stashed/checked out/rebased | preserved | EXECUTED |
| `.env` / credentials | not read | not read | — |
| Mutation markers / `.16a*.bak` backups | none | **none** | `grep`, `find` |

These **exactly match the Step 1.6AD baseline** (HEAD `6baaa2a…`; 385 = 295 D + 35 M + 55 ??; 0
staged). The Step 1.6AD report is present and **unchanged** (`e16438b2d9fc2eba`, matching the recorded
predecessor value). No discrepancy with the historical record was found.

---

## 4. Source-grounded destructive-call-site inventory

Built from the **current** source this step (line numbers re-verified with `grep -n`), including a
`code-searcher` worker sweep. Every row is **SOURCE** unless marked.

| # | Operation | Source (current lines) | Validation before it | Race window | Mitigation | This step |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Application delete of an uploaded file | `storage/file_store.py:195` (`candidate.unlink()`; def `:137`) | `..` refusal `:170-171`; `_resolved_within` call `:173`; link/reparse `:176`; `_has_link_ancestor` call `:184`; `S_ISREG` `:191` | validate → pathname `unlink` (TOCTOU) | none (pathname flow) | symlink case **SKIPPED**; others passed |
| 2 | Cleanup after failed commit | `storage/file_store.py:201` (`cleanup_new_file` → `delete_upload`) | same | same | none | as row 1 |
| 3 | Smoke delete of named uploads | `scripts/cleanup_smoke.py:189` (`unlink_beneath`); Windows fallback call `delete_upload(resolved, root=root)` `:194` | `intended_root` `:259`; `validate_candidate` `:126`; `open_root_fd` `:159` | POSIX closed for parents/root; Windows open | `unlink_beneath` POSIX; fail-closed refusal if the root cannot be held | passed / 9 POSIX **SKIPPED** |
| 4 | Smoke prune of a user dir | `scripts/cleanup_smoke.py:246` (`rmdir_beneath`), `:248` (`user_dir.rmdir()` — Windows fallback only when `root_fd is None`) | `validate_candidate` `:226`; `open_root_fd` `:230` | as row 3 | as row 3 | as row 3 |
| 5 | Orphan sweep deletes + prunes | `scripts/cleanup_orphan_uploads.py:391` (`path.unlink()`), `:431` (`path.rmdir()`) | `intended_root` `:283`; `validate_candidate` `:179`/`:367`/`:409`; `open_root_fd` `:354`; `unlink_beneath` `:383`; `rmdir_beneath` `:422` | as row 3 | POSIX descriptor-relative | passed |
| 6 | Archive create/verify | `scripts/cleanup_orphan_uploads.py:202` (`open(archive, "x+b")`), verify `~:216-250` | destination not inside root, not a link, pre-check, candidate validation | exclusive create; verification handle-bound | exclusive create + same-handle CRC; failed write leaves the fragment | passed |
| 7 | `__pycache__` prune (server) | `scripts/start_server.py:75` → `scripts/cleanup_path.py:280` (`prune_pycache_beneath`; inner `_remove_validated_tree` `:305`) | `intended_root` `:301`; `validate_candidate` `:354`; **per-entry `lstat` `:321`**, refusal `:325-327`, recursion `:331-332`, `unlink` `:335`, `rmdir` `:340` | **`lstat` → recursion (directory-swap — §7)** | per-entry link/reparse refusal | passed |
| 8 | `__pycache__` prune (e2e harness) | `tests/e2e/browser/test_phase6_reliability.py:44-46` → row 7 | as row 7 | as row 7 | as row 7 | source-read guards passed; harness **NOT RUN** |
| 9 | Publish evaluation evidence | `evaluation/artifacts.py:233` (`os.replace`), `:236` (`temporary.unlink()`) | unique per-process temp name; append-only | atomic `os.replace` | append-only publication | passed |
| 10 | Parser temp copy | `documents/parser.py:463` (`os.unlink` in `try/except OSError`) | own `NamedTemporaryFile` | n/a | failure logged (1.6AB) | passed |
| 11 | Voice temp audio | `voice.py:261` | own temp file | n/a | `OSError` caught | **NOT RUN** (needs services) |
| 12 | Runner fixture uploads | `evaluation/experiments/run_phase3e_integration.py:290,319,387,418,543`; `run_phase3e_validation.py:268,357,630,777,824` | own-run fixtures | n/a | runner-level disposal gate | passed (source-read) |
| 13 | Runner inline row deletions / gates | `evaluation/experiments/*` `assert_cleanup_execution_authorized` sites (e.g. `run_phase3e_integration.py:518`) | gate immediately before | n/a | function-level gate refuses (§13) | passed |

No executable `shutil.rmtree`, `ignore_errors=True`, `truncate`, or destructive `shutil.move` remains
in the searched scope (hits were documentation/tests or third-party code under the forbidden
`phases/phase4f_gpu/` tree). **INFERENCE**: a hand-rolled recursive delete using unfamiliar primitives
would evade the pattern search; none was found.

---

## 5. Linux environment investigation and execution evidence

**Result: LINUX EXECUTION: BLOCKED — NO AUTHORIZED LINUX RUNTIME AVAILABLE.** Probes bounded; nothing
installed.

| Probe | Command (EXECUTED) | Observed | Class |
| --- | --- | --- | --- |
| Kernel / OS | `uname -a` | `MINGW64_NT-10.0-26300 … x86_64 Msys` — MSYS/Git Bash on Windows, **not Linux** | EXECUTED |
| WSL presence/usability | `wsl.exe --status` | stderr (UTF-16): *"The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'."* | EXECUTED |
| Containers | `which docker podman` | absent | EXECUTED |
| POSIX Python | `which python python3` | absent | EXECUTED |
| CI runners | `which act gh` | absent | EXECUTED |
| Repository CI | `ls .github/workflows`; `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci`, `.woodpecker.yml`, `bitbucket-pipelines.yml` | **none present** | EXECUTED |
| Windows Python | `backend/venv/Scripts/python.exe --version` | `Python 3.11.0` | EXECUTED |

No Linux runtime is available under any authorization basis, so the required initial Linux command
(`python -m pytest -q tests/unit/scripts tests/unit/documents`) was **not run on Linux**. MSYS Git Bash
is **not** treated as a Linux runtime and the Windows results are not Linux evidence.

---

## 6. Filesystem threat model

Cases: **A** lexical traversal, **B** link/reparse traversal, **C** object replacement, **D** parent
replacement, **E** concurrency (check-then-use), **F** archive substitution.

**Assets.** The upload root (`settings.upload_path`), and — for the bytecode prune — the backend tree.
**Adversary.** A local process (or a compromised sibling component) with write permission in a
directory *inside* a cleanup root, that can `rename`/replace entries concurrently with the cleanup.
**Not in scope.** Kernel/root attackers; the operator-supplied root itself being hostile (operator
config provenance, per `file_store.py:60-70`). **Cleanup context.** Runs as the backend service
account.

| Operation | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- |
| 1–2 `file_store.delete_upload` | refused | refused | **open** (pathname `unlink`) | **open** | open | n/a |
| 3–5 cleanup smoke / orphan sweep | refused | refused | Windows **open**; POSIX name-swap only | POSIX closed, Windows open | reported | n/a |
| 6 archive | refused | refused | closed (exclusive create) | **open** (archive parent not held) | n/a | closed (same-handle verify) |
| 7–8 `__pycache__` prune | refused (`intended_root`, containment) | refused at each named entry | **open — directory swap `:321→:332` (§7)** | **open** | **open** | n/a |
| 9 `write_evidence` | refused | n/a | closed | n/a | unique temp name | n/a |

**Security invariant this step proposes (design):** *No cleanup operation may follow a replaced
filesystem entry, or delete an object outside the authorized root.* Formally: every destructive syscall
must act on an object bound by a **descriptor or handle** opened no-follow relative to the validated
root, and every traversal step must re-establish containment from that held descriptor/handle — never
from a re-resolved pathname.

---

## 7. Directory-swap race analysis

Implementation of record: `scripts/cleanup_path.py`, `prune_pycache_beneath` (`:280`) and its inner
helper `_remove_validated_tree` (`:305`). Answers to the eight required questions:

1. **Operations between the safety check and recursive use.** For each entry: `info = os.lstat(entry)`
   (`:321`); classify; refuse `S_ISLNK` / `FILE_ATTRIBUTE_REPARSE_POINT` (`:325-327`); for a directory,
   recurse `_remove_validated_tree(entry)` (`:331-332`). **No re-validation of `entry` occurs between
   the `lstat` and the recursion.** The outer `validate_candidate(root, candidate, …)` (`:354`) applies
   to the top-level `__pycache__` name only, not to nested entries. **CONFIRMED (SOURCE).**
2. **Can an entry be replaced during that interval?** **Yes.** A concurrent writer with write access to
   the parent directory can rename the classified directory away and substitute a junction/symlink in
   the same name before `:332`. **CONFIRMED (SOURCE reasoning).**
3. **Can traversal reach an object outside the intended root?** **Yes — this is an escape channel.** The
   recursion begins with `entries = sorted(directory.iterdir())` (`:315`). On Windows a directory
   junction is followed by `iterdir()`, so the enumeration lists the **target's** contents; those
   entries are real files/directories from the subsequent `lstat`'s view, and the helper `os.unlink`s
   them (`:335`) and recurses. The result can be **deletion outside the root** — **not** merely a stale
   bytecode name. **CONFIRMED (SOURCE reasoning); severity: medium.**
4. **Do the existing descriptor-relative helpers protect this cleanup path?** **No.** `unlink_beneath`
   (`:437`) and `rmdir_beneath` (`:483`) are **not** used by `prune_pycache_beneath`; the prune is
   pathname-based (`os.unlink(entry)`, `os.rmdir(directory)`, `iterdir()` traversal) on **both**
   platforms. **CONFIRMED (SOURCE).**
5. **Which race conditions remain on Windows?** The prune race in question 3, **plus** the pathname
   deletes in `file_store.delete_upload` (`:195`) and the Windows fallbacks in `cleanup_smoke.py`
   (`:194`, `:248`). On POSIX, the same prune race remains, plus `file_store.delete_upload` (`:195`).
   **CONFIRMED (SOURCE).**
6. **Which tests verify static symlink/junction refusal?** `tests/unit/scripts/test_pycache_prune_safety.py`:
   `test_a_link_nested_inside_a_pycache_is_refused` (`:222`) and
   `test_a_linked_pycache_is_refused_and_its_target_survives` (`:201`). Both execute on this host
   (junctions need no elevation). **CONFIRMED (EXECUTED — they pass).**
7. **Which tests exercise replacement between checking and traversal?** **None.** No test performs a
   swap between the `lstat` and the recursion. **CONFIRMED (SOURCE; the residual is established by
   reasoning only).**
8. **What execution evidence and regression tests are required?** (a) A deterministic race-injection
   test that hooks the classification step and swaps the entry for a junction to a populated target
   before recursion, asserting the target survives and a refusal is reported (§10.3). (b) A
   re-validating implementation (§8). (c) A POSIX run of the descriptor-relative suite. §10 specifies
   the tests; §8 specifies the implementation.

**Disposition: NOT FIXED.** No speculative fix was attempted (this is a design step). Severity is
recorded as **medium** (out-of-root deletion channel under a local race), consistent with Step 1.6AD.

---

## 8. Recursive-cleanup remediation design (PROPOSED DESIGN — not implemented)

### 8.1 Security contract and threat model

**Invariant.** *No cleanup operation may follow a replaced filesystem entry, or delete an object outside
the authorized root.* Enforcement rule: **every destructive syscall acts on an object bound by a
descriptor/handle opened no-follow relative to the validated root; no pathname is re-resolved after the
root is held; any failure to establish that binding is a refusal, never a pathname fallback.**

**Threat model.** Local concurrent writers inside the root (case E); links/reparse points already
present (case B); parent/root replacement (case D). Out of scope: kernel/root attackers, hostile
operator config.

### 8.2 POSIX algorithm (PROPOSED DESIGN)

1. Establish the validated root with the existing `intended_root` (`:97`), then hold it:
   `root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)`.
   If this fails → **refuse** (never retry by pathname).
2. `remove(relative_parts)` walks **relative to a held descriptor**, one component at a time:
   - `child_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)`.
     `O_NOFOLLOW` refuses a symlink **at the moment of open**; `O_DIRECTORY` refuses a non-directory. The
     single open both validates and binds the object — there is no separate check to race.
   - Enumerate with `os.scandir(child_fd)` and classify each entry from the **dirent**
     (`entry.is_symlink()`, `entry.is_dir(follow_symlinks=False)`) — never from a re-resolved pathname.
   - Regular file → `os.unlink(entry.name, dir_fd=child_fd)`. POSIX `unlink` never follows a final
     symlink, so a name swapped for a symlink is removed **as the link** (its target untouched) — this
     is safe and is **not** traversal.
   - Directory → recurse with `child_fd`; then `os.rmdir(entry.name, dir_fd=child_fd)`. `rmdir` never
     follows a final symlink, so a name swapped for a symlink is **refused**, not traversed.
   - **Consistency with §8.4 (reviewer R-2, reconciled).** A symlink/reparse point encountered as an
     **intermediate** component is **refused** (`O_NOFOLLOW`); a symlink swapped in for the **final**
     name is **never followed** — `unlink` removes the link, `rmdir` refuses. The design does **not**
     change the current static refusal into a traversal, and no live link is ever followed.
   - `finally`: close every fd.
3. **Availability gate:** require `os.open in os.supports_dir_fd`, `os.unlink in os.supports_dir_fd`,
   `os.rmdir in os.supports_dir_fd`, and `os.O_NOFOLLOW`/`os.O_DIRECTORY`. Missing → **refuse**.
4. **Resource safety:** bound recursion depth and detect `EMFILE`/`ENFILE`; on exhaustion, stop and
   report the refusal (fail closed) rather than degrade to pathnames.
5. **Residual (documented, not a fix):** the final *name* inside a held directory can still be swapped
   before the syscall — unavoidable in the stdlib — but the consequence is **bounded to that held
   directory** (an unlink removes the swapped link, not its target; `rmdir` refuses a swapped symlink),
   so **no escape from the root** is possible.

### 8.3 Windows algorithm (PROPOSED DESIGN — claims requiring platform experiments are UNVERIFIED)

Windows has no `dir_fd`. The handle-bound approach:

1. Open the root with `CreateFileW(root, FILE_LIST_DIRECTORY, FILE_SHARE_READ|WRITE|DELETE,
   OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)`. If it fails → **refuse**.
2. For each entry, open it **without following a reparse point** (`FILE_FLAG_OPEN_REPARSE_POINT`) and
   inspect the reparse tag via `GetFileInformationByHandleEx(FileAttributeTagInfo)`:
   `IO_REPARSE_TAG_MOUNT_POINT` (junction), `IO_REPARSE_TAG_SYMLINK`, or `FILE_ATTRIBUTE_REPARSE_POINT`.
   Any reparse point → **refuse; never traverse**.
3. Capture file identity (`GetFileInformationByHandle` → `dwVolumeSerialNumber` + `nFileIndexHigh/Low`)
   at open time; because the **same handle** is used for deletion, the delete is bound to the validated
   object, so a name swap between validation and delete is inert.
4. Delete **by handle**: `SetFileInformationByHandle(h, FileDispositionInfo, …)` with `FILE_DISPOSITION_DELETE`
   (opened with `DELETE` access); for directories use `FileDispositionInfoEx` with
   `FILE_DISPOSITION_POSIX_SEMANTICS` where available. Because step 2 **refuses every reparse point
   before deletion**, no junction/symlink object ever reaches this step, so there is no junction-deletion
   case to define (reviewer R-5 removed the earlier, self-contradictory junction claim). **Whether a
   directory handle opens with sufficient access to permit deletion, and the exact disposition
   semantics, are UNVERIFIED — see step 5.**
5. **UNVERIFIED — requires platform experiments / authoritative API verification (marked, not claimed):**
   (i) exact `FileDispositionInfo`/`FileDispositionInfoEx` semantics and availability for **directories**
   on the target Windows build; (ii) whether `FILE_DISPOSITION_POSIX_SEMANTICS` is supported;
   (iii) whether a directory handle opened without following a reparse point succeeds in all cases
   (e.g. requiring `FILE_FLAG_BACKUP_SEMANTICS`); (iv) behavior on non-NTFS/ReFS filesystems
   (FAT/exFAT, network shares). These must be established by experiment before implementation.

### 8.4 Fallback contract (both platforms)

| Condition | Behavior |
| --- | --- |
| Unsupported platform | **Refuse** (report `unsupported`); delete nothing. Never a pathname fallback. |
| Filesystem lacks the required semantics | **Refuse.** |
| Handle/descriptor cannot be obtained | **Refuse** (never retry by pathname). |
| Entry changes during traversal | The binding makes the change inert or the syscall fails → **refuse**, report. |
| Insufficient permissions | **Refuse**, report. |
| Unexpected reparse point/symlink | **Refuse; never traverse.** A final name swapped for a symlink is unlinked as the link, never followed (§8.2). |

**Default: safe refusal, never a weaker pathname-based deletion.**

**Cross-platform reconciliation (reviewer R-10).** `prune_pycache_beneath` is called on **this Windows
host** by `start_server.py:75`, so an unconditional refusal fallback would make the prune a **no-op on
Windows**. The design therefore requires the §8.3 Windows handle-bound path to **land together with**
the refusal switch in the same implementation step. Until that step, the **current** Windows pathname
flow stays in place and its residual stands — it is explicitly **not** converted to a no-op, and
operators must be told that after the switch, bytecode caches on Windows are cleared only through the
handle-bound path.

### 8.5 Design deliverable summary and readiness

Threat model (§8.1), invariants (§6/§8.1), POSIX algorithm (§8.2), Windows algorithm (§8.3), fallback
(§8.4), required APIs (POSIX: `open/unlink/rmdir` with `dir_fd` + `O_NOFOLLOW`/`O_DIRECTORY`; Windows:
`CreateFileW` + `GetFileInformationByHandle(Ex)` + `SetFileInformationByHandle`), error contract
(§8.4), regression plan (§10), verification requirements (§10, §15), limitations (§15).
**Implementation-readiness for recursive cleanup: NOT READY.** Prerequisites: a Windows platform
experiment confirming the §8.3 UNVERIFIED claims; a deterministic race test (§10.3); a POSIX run;
independent review. See §16.

---

## 9. Upload-deletion remediation design (`storage/file_store.delete_upload`) (PROPOSED DESIGN)

**Current behaviour (SOURCE, `file_store.py`).** `candidate = Path(stored_path)` (`:159`); `base = root
or settings.upload_path` (`:160`); `..` refusal (`:170-171`); `_resolved_within` (`:173`, def `:97`);
candidate+resolved link/reparse refusal (`:176`, `_is_link_or_reparse_point` def `:80`);
`_has_link_ancestor` (`:184`, def `:117`); `candidate.lstat()` + `S_ISREG` (`:188-191`); pathname
`candidate.unlink()` (`:195`). **TOCTOU window:** between the last check (`:191`) — and between
resolution (`:173`) — and `unlink()` (`:195`), a parent or the final object can be swapped for a link.

**Module boundary.** `file_store` **deliberately does not import from `scripts/`** (production must not
depend on the operational package; stated in-source at `:60-70`). Therefore the design introduces a
**production-appropriate abstraction inside `storage/`** (e.g. `storage/_contained_delete.py`)
providing `contained_unlink(root, name) -> Status` — **not** an import of `cleanup_path`. The POSIX
algorithm of §8.2 is the same primitive; the Windows algorithm of §8.3 applies on Windows.

Design requirements and answers:

1. **Trusted root.** Established by operator config (`settings.upload_path`) and validated once at
   startup or first use (not a symlink/reparse point; resolves to itself). Provenance is operator
   config, not untrusted input.
2. **Target identity relative to the root.** Derive the root-relative name **lexically** —
   `candidate.relative_to(base)` after the `..` refusal (`:170-171`) — and **not** via
   `os.path.relpath`/`resolve` after the root is held (that would re-introduce the very follow step the
   design removes; reviewer R-6). The relative name (no drive, no rooted component, no `..`) is then
   opened component-by-component `O_NOFOLLOW` relative to the held root descriptor. The public signature
   `delete_upload(stored_path, root=...)` is unchanged, so call sites are unaffected. A path not
   component-wise under the root is refused.
3. **Containment across validation and deletion.** Hold the root (POSIX fd / Windows handle) and delete
   via `dir_fd` / handle-relative so containment is bound, not re-resolved.
4. **Replacement races.** Bound by the descriptor/handle; a swap either is inert or causes the syscall
   to fail → refusal.
5. **Unsupported platforms.** Refuse (`Status.UNSUPPORTED`); **never** a pathname `unlink`.
6. **Caller contract.** Keep the public signature/return of `delete_upload` as `bool` (True = deleted;
   False = refusal) so `documents/routes.py` and `cleanup_smoke.py` call sites are unchanged; internally
   map `Status` → bool. A refusal leaves an orphan (acceptable; the caller logs it).
7. **Tests demonstrating the invariant.** §10.2/§10.3: a validation→use race-injection test proving the
   target survives and a refusal is returned; plus the existing positive/negative cases.

**Do not modify `storage/file_store.py` during this step.** Disposition: **DEFERRED** (§15).

---

## 10. Test inventory and proposed regression tests

### 10.1 Existing tests (inventory; SOURCE + EXECUTED status)

| File | Coverage | Windows status |
| --- | --- | --- |
| `tests/unit/scripts/test_pycache_prune_safety.py` | prune containment; linked root refused; linked `__pycache__` refused; nested link refused; differential non-vacuity; `start_server`/e2e call sites (source-read guards) | executes; junctions used (no elevation) |
| `tests/unit/scripts/test_descriptor_relative_deletion.py` | refusal logic + AST checks run everywhere; real descriptor-relative deletion is 8 tests marked POSIX-only | 8 **SKIPPED** (“requires POSIX dir_fd … not available on Windows”) |
| `tests/unit/scripts/test_cleanup_smoke_safety.py` | smoke containment, fallback/refusal, descriptor flow | mostly executes; 2 symlink-privilege **skips**; 1 POSIX **skip** |
| `tests/unit/scripts/test_cleanup_orphan_uploads.py` | orphan sweep containment/refusal | executes; 1 symlink-privilege **skip** |
| `tests/unit/scripts/test_race_substitution_deterministic.py` | deterministic substitution at the descriptor boundary | executes |
| `tests/unit/documents/test_file_store_deletion_safety.py` | inside-root delete; refusals (prefix/absolute/`..`/symlink/dir/missing); default root | executes; symlink case **SKIPS** (`:51`) |
| `tests/unit/documents/test_parser_temp_cleanup.py` | parser temp-copy cleanup | executes |

**Vacuous-by-construction candidates (flagged):** `test_every_deletion_call_is_descriptor_relative`
asserts `"dir_fd=" in line` over source text that includes the `rmdir_beneath` **docstring** line — it
can pass on a docstring (reviewer R-7). Mitigated but not closed by the AST-based
`test_the_refusal_check_precedes_the_deletion_call`.

### 10.2 Gap analysis

No existing test exercises: (a) a directory **replaced between classification and recursion** in
`_remove_validated_tree`; (b) a **parent-directory replacement** during a cleanup traversal; (c) a
**target replacement after validation but before** `delete_upload`’s `unlink`; (d) an
unsupported-platform **refusal** enforced at the new abstraction boundary.

### 10.3 Proposed regression tests (PROPOSED DESIGN)

1. **Race-injection (prune) — two complementary tests, because the seam differs by implementation
   (reviewer R-7).**
   (a) **Regression-of-today** against the *current* source: in `tmp_path` build
   `root/pkg/__pycache__/real.pyc` plus an `outside-target/` holding `precious.txt`; monkeypatch
   `os.lstat` (the `:321` classify step) so that after it returns DIR for a chosen entry the fixture
   swaps that entry for a junction/symlink to `outside-target` before the recursion; assert
   `outside-target/precious.txt` is **destroyed on today’s code** (this documents the vulnerability and
   is expected to be re-pointed when the code changes).
   (b) **Invariant test against the fixed code:** drive the fix through a seam that exists in **both**
   implementations — a module-level `_open_child_dir(parent_fd, name, nofollow=True)` /
   `_classify(entry, parent_fd)` seam the implementation must call — and swap the entry for a junction
   inside that seam; assert the call **refuses**, `outside-target/precious.txt` **survives**, and the
   refusal is reported. A single `os.lstat` hook cannot be the load-bearing control because the §8.2 fix
   **removes** the `os.lstat` classification (R-7’s non-vacuity defect); the plan therefore does **not**
   assert one fail-then-pass on a seam the fix deletes. Runs entirely in `tmp_path`; **never touches
   real data.**
2. **Parent-swap race (cleanup traversal).** Replace a parent directory with a link between validation
   and descent; assert the descriptor/handle flow refuses and nothing outside the root is deleted.
3. **Bounded final-name swap.** Swap the final name for a link in the held directory; assert `unlink`
   removes the link (not the target) and `rmdir` refuses a swapped symlink.
4. **Unsupported-platform refusal.** Force the platform gate off; assert `Status.UNSUPPORTED` and that
   nothing is deleted (no pathname fallback).
5. **`delete_upload` invariant.** The §10.3(1) interleaving against `contained_unlink`; assert
   `delete_upload` returns `False` and the target survives.
6. **Non-vacuity hardening (R-7).** Assert `dir_fd` on the **AST `ast.Call` node** of
   `unlink_beneath`/`rmdir_beneath`, not on source text.
7. **POSIX execution.** Run the 8 `test_descriptor_relative_deletion.py` tests and
   `test_cleanup_smoke_safety.py:385` on real POSIX and require them to **execute** (not skip).

Each proposed test is a **design**, not implemented; each states what it exercises and its platform
requirement. No destructive race test may run against a real repository/upload/user tree.

---

## 11. Negative-control evidence

**Status: freshly EXECUTED this step (1.6AE), isolated, with byte-identical restoration.** The control
mutates an in-tree source file, so it was applied only to a file that was first fingerprinted and
backed up, and restored immediately afterwards. All fixtures are temporary directories; **no real
upload, archive or user file was involved**, and no real cleanup sweep was run.

| Step | Action (EXECUTED) | Observed |
| --- | --- | --- |
| 1. fingerprint | `sha256sum scripts/cleanup_path.py` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` |
| 2. mutate | `if stat.S_ISLNK(info.st_mode) or (` at `:325` → `if False and (` | applied (anchor asserted `== 1`) |
| 3. fingerprint | `sha256sum` | `414904ad9a51c253fe0d19600fc9371fa2793f0faeafa1e1cd371dee1e8618f1` (changed) |
| 4. run test | `pytest -q tests/unit/scripts/test_pycache_prune_safety.py -k test_a_link_nested_inside_a_pycache_is_refused` | **1 failed, 13 deselected — exit 1** |
| 5. restore | copy the backup back; remove the backup | restored |
| 6. fingerprint | `sha256sum` | `97dbc1b6559a402ab6605c00147e8ba1583a46c97312706374ec3ac809914737` — **byte-identical to step 1** |
| 7. re-run test | same command | **1 passed, 13 deselected — exit 0** |
| 8. residue | `grep -c 'if False and (' scripts/cleanup_path.py`; `ls scripts/*.16ae.bak` | `0` markers; no backup |

The failure in step 4 is caused **for the intended reason**: disabling the refusal lets
`_remove_validated_tree` recurse into the nested junction and delete its target, failing
`assert precious.read_bytes() == b"precious"`. The protection is load-bearing, proven by execution on
this host (Windows). The reviewer’s R-8 assessment concurs on the reason (marked
UNVERIFIABLE-FROM-HERE for the digests, as it has no terminal). **No production code was modified as
part of the control** beyond the temporary in-place mutation, which was restored byte-identically.

---

## 12. Independent-review status and findings

### 12.1 Identity and independence

| Item | Value |
| --- | --- |
| Reviewer | one `base3-fast-worker-deepseek-flash` worker, adversarial brief, read-only |
| Terminal access | **no** |
| Independent execution | **no** — executed nothing |
| Access | final source: yes; execution artifacts: only as reported by the coordinator |
| Files written | **none** |
| Gate | **INDEPENDENT REVIEW GATE NOT SATISFIED** |

The reviewer is the **same model/runtime family** as the coordinator with no terminal, so it is **not
genuinely independent**. Independence was attempted by dispatching a separate reviewer instance against
the design, but the required criteria (separate execution environment, distinct family, terminal) are
unmet. No readiness claim may rest on this review.

### 12.2 Findings R-1 … R-10 (the reviewer's ACTUAL output, challenging the design; source-read; nothing executed independently)

| ID | Focus | Severity | Reference | Failure scenario | Missing verification | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| R-1 | Root containment | low | §8.2 step 1; `cleanup_path.py:97,246,158,200` | `intended_root` returns a **resolved** path and §8.2 then `os.open`s it, so a **parent** of the root could be swapped between resolution and open (case D); the design does not state this residual (bounded by operator-config provenance). | design-clarity; hold the fd as early as possible | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-2 | Symlink / reparse handling | **medium** | §8.2 vs §8.4; `cleanup_path.py:325-327` | §8.2 said a swapped symlink "is removed as the link" while §8.4 says "refuse; never traverse" — **two behaviours for one object, and a behaviour change from today's refuse-and-abort**. | reconciled in §8.2/§8.4 + a test | **DISPUTED, WITH EVIDENCE — reconciled** |
| R-3 | Directory-swap race | medium (design) / high if untested | §8.2 vs `cleanup_path.py:321→:331-332`, `iterdir` `:315` | The §8.2 binding (open each subdir `O_NOFOLLOW` + `dir_fd` ops) **does close** the `iterdir()`-follows-junction escape; but it is **entirely unexecuted** and one sub-claim (fd-backed `scandir`) needs verification (R-4). | race-injection test; POSIX run | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-4 | Descriptor-relative POSIX design | medium | §8.2 steps 2–3 | The design **asserts** `os.scandir(child_fd)` + dirent classification works but does not list it as needing verification; a mis-classification would be silent. | POSIX run; a targeted `scandir(fd)` test; add to verification reqs | **FIXED, EXECUTION EVIDENCE INCOMPLETE** |
| R-5 | Windows handle-bound design | **high** | §8.3 steps 2, 4, 5 | Step 4 stated a junction "removed as the link" **as fact**, was **not** in the UNVERIFIED list, and **contradicted step 2** (refuse all reparse points). | Windows experiments (directory disposition, POSIX_SEMANTICS, reparse-open, non-NTFS) | **DISPUTED, WITH EVIDENCE — corrected** |
| R-6 | Upload-deletion contract | high | §9 item 2; `file_store.py:159-160,173,176,184,191,195` | The rule "derive a root-relative name" was **underspecified**: `os.path.relpath(resolved, root)` would re-introduce the very follow step the design removes. | concrete derivation rule + tests | **DEFERRED — corrected in §9** |
| R-7 | Test validity / non-vacuity | **medium** | §10.3(1); `test_descriptor_relative_deletion.py` | The proposed race test hooked `os.lstat`, but the §8.2 fix **removes** that seam, so the test would create no interleaving and could pass **vacuously**. Also, `test_every_deletion_call_is_descriptor_relative` can pass on a docstring line (`dir_fd=`). | two tests on a shared seam; AST-node assertion | **NOT FIXED — corrected in §10.3** |
| R-8 | Negative-control quality | low | §11; `cleanup_path.py:325` | Valid and fails for the intended reason, but covers only the **static** nested-link case — **not** the R-3 directory-swap race. | R-3-specific test (does not exist) | **FIXED AND VERIFIED (for what it covers); NOT VERIFIED for R-3** |
| R-9 | Linux/POSIX execution evidence | **high** | §5; §10 | None exists: all executed tests ran on Windows/MSYS; the 9 descriptor tests skip; a skip is not a pass. | a genuine POSIX run | **NOT VERIFIED** |
| R-10 | Fallback behavior & remaining risks | **medium** | §8.4 vs `start_server.py:75` | Unconditional refusal would make `prune_pycache_beneath` a **no-op on Windows**, yet `start_server.py:75` calls it on this host — a real behavior/regression the design must own. | reconcile the refusal switch with the Windows path (land §8.3 together) | **DISPUTED, WITH EVIDENCE — reconciled in §8.4** |

No finding was silently dismissed. **Cross-cutting process finding P-1 (medium):** the draft §12.2 table
was pre-populated before this review ran; it has been **replaced** with the reviewer's actual output
above, and must not have been treated as review evidence. **P-2 (low):** the reviewer flagged the
`is_link_or_reparse_point ~:73` citation; verified and corrected to `def :74`. The material findings are
**R-2, R-5, R-7, R-10** (design inconsistencies, all now reconciled), plus **R-6** (contract detail),
with **R-3/R-4** sound-but-unexecuted and **R-9** unverified.

### 12.8 `REPORT_AUDITOR` pass (actual findings — filled)

A second same-family worker cross-checked counts, skip arithmetic, exit codes, line references,
digests, agent assignments and readiness conclusions, and wrote **no** files. It had **no terminal**, so
every execution-shaped claim was **UNVERIFIABLE-FROM-HERE** for it; its value is source/report
consistency only. Its findings:

* **PASS:** exactly the 18 required sections, in order; every spot-checked line reference matches the
  current source; the named test files/tests exist (`test_a_linked_pycache_is_refused_and_its_target_survives`
  `:201`, `test_a_link_nested_inside_a_pycache_is_refused` `:222`, `test_every_deletion_call_is_descriptor_relative`
  `:166`, `test_file_store_deletion_safety.py:51` symlink skip); skip arithmetic consistent
  (13 = 4 + 9; 23 = 10 + 4 + 9; 267 targeted; 1345 full); R-1…R-10 present; §8/§9 clearly marked
  **PROPOSED DESIGN** with §8.3 Windows claims **UNVERIFIED**; verdict **CONDITIONAL PASS** with Linux
  **BLOCKED** and review **NOT SATISFIED**.
* **A-1 (real, low):** §1 cited the non-existent `§12.5`. **Corrected** to `§2`.
* **A-2 (real, low):** §12.8/§12.9 were unfilled forward references. **Corrected** by inserting this
  audit's findings and the applied corrections.

### 12.9 Coordinator corrections applied after review

All substantive reviewer findings were reconciled against current source and applied rather than
defended: **R-2** (§8.2/§8.4 symlink behaviour made consistent and explicit); **R-5** (the §8.3 step-4
junction claim removed as contradictory with step 2 and its disposition semantics marked **UNVERIFIED**);
**R-6** (§9 now specifies the **lexical** root-relative-name derivation, no post-root `relpath`);
**R-7** (§10.3(1) split into a regression-of-today test and a shared-seam invariant test, avoiding the
vacuity of hooking a seam the fix removes); **R-10** (§8.4 now reconciles the refusal fallback with the
Windows prune call and requires §8.3 to land with it); **R-1/R-4** residuals noted. **P-2**
(`is_link_or_reparse_point`): verified with `grep -n` as `def :74`. **A-1** dead cross-reference fixed;
**A-2** sections filled. Line references re-verified with `grep -n` against the current source.

---

## 13. Database lifecycle gate results

Documentation and source inspection only — **no connection, migration, mutation or `.env` read.**

| Gate | Location (SOURCE, re-verified) | Behaviour |
| --- | --- | --- |
| `_proof_is_live` | `evaluation/isolation.py:363` | returns `False` unconditionally |
| `record_created_database` | `:369` | raises `UnsafeEvaluationTarget` |
| `assert_disposal_authorized` | `:377` | raises `UnsafeEvaluationTarget` at the end |
| `assert_creation_authorized` | `:415` | raises `UnsafeEvaluationTarget` |
| `assert_row_cleanup_authorized` | `:443` | delegates to `assert_disposal_authorized` |
| `assert_cleanup_execution_authorized` | `:456` | raises immediately |
| `release_database_proof` | `:477` | raises `UnsafeEvaluationTarget` |
| `assert_engine_bound_to_proof` | `:485` | refusal path preserved |

**Status: BLOCKED — no change.** No guard was relaxed; no blocked test was made unconditional; this step
touched no lifecycle code. **PostgreSQL integration: NOT VERIFIED. Migrations and database mutation:
NO-GO.** Passing filesystem tests does **not** authorize database operations, and none were attempted.

---

## 14. Protected-artifact integrity results

All measured EXECUTED this step; digests are SHA-256 prefixes (first 16 hex).

| Check | Result | Class |
| --- | --- | --- |
| Frozen benchmark `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matches** | EXECUTED |
| Upload tree | 1212 files, 7 386 232 bytes — **matches** | EXECUTED |
| `STEP1_6AD_…_2026-10-14.md` | `e16438b2d9fc2eba` — present, **unchanged** | EXECUTED |
| `STEP1_6AC_…_2026-10-14.md` | `6cafb8ab94741c76` — unchanged | EXECUTED |
| `scripts/cleanup_path.py` | `97dbc1b6559a402a` — **byte-identical after the negative control** (§11) | EXECUTED |
| `storage/file_store.py` | unmodified (no code changes) | EXECUTED |
| HEAD / index | `6baaa2a…` unchanged; 0 staged | EXECUTED |
| Working tree | 385 entries = 295 D + 35 M + 55 ?? | EXECUTED |
| Mutation markers / `.16a*.bak` / stray temp under `backend/` (excl. `venv/`,`phases/`) | **0** | EXECUTED |

No predecessor report was overwritten. The only file written by this step is this report.

---

## 15. Platform limitations and unresolved risks

| # | Limitation / risk | Status | Owner (contract) |
| --- | --- | --- | --- |
| 1 | Linux/POSIX descriptor-relative deletion never executed | **NOT VERIFIED — LINUX EXECUTION BLOCKED** | POSIX_TEST_ENGINEER / COORDINATOR |
| 2 | Directory-swap in `_remove_validated_tree` (`:321→:332`) — possible out-of-root deletion | **NOT FIXED** (design §8; test §10.3) | FILESYSTEM_SECURITY_ARCHITECT / BACKEND_AGENT |
| 3 | Windows handle-bound design rests on **UNVERIFIED** API claims | **UNVERIFIED — needs platform experiments** | WINDOWS_FILESYSTEM_SPECIALIST |
| 4 | `storage/file_store.delete_upload` pathname `unlink` (`:195`) TOCTOU | **NOT FIXED** (design §9) | BACKEND_AGENT |
| 5 | Final-name swap inside a held directory is unclosable in the stdlib (bounded) | **OPEN, BOUNDED** | SECURITY_AGENT |
| 6 | Windows cleanup-script pathname fallbacks (`cleanup_smoke.py:194/:248`) | **OPEN on Windows** | BACKEND_AGENT |
| 7 | `test_every_deletion_call_is_descriptor_relative` docstring vacuity (R-7) | **NOT FIXED** (test §10.3(6)) | TEST_AGENT |
| 8 | e2e harness prune has source-read evidence only | **LIMITED EVIDENCE** | TEST_AGENT |
| 9 | Independent review not satisfied as an organisational control | **NOT SATISFIED** | COORDINATOR |
| 10 | Report-auditor pass had no terminal | **LIMITED** | COORDINATOR |

Nothing here is claimed closed. **The designs in §8/§9 are proposed, not implemented; no race is
claimed fixed.**

---

## 16. Implementation-readiness matrix

| Item | Decision | Prerequisites still missing |
| --- | --- | --- |
| Database-free targeted tests (scripts + documents) | **GO (Windows only)** | — (1345/23/0 full, 267/13/0 targeted) |
| POSIX descriptor-relative deletion | **BLOCKED / NOT VERIFIED** | authorized Linux runtime |
| Recursive-cleanup race fix (§8) | **NOT READY** | Windows platform experiment for §8.3 UNVERIFIED claims; deterministic race test (§10.3); POSIX run; independent review |
| Windows handle-bound delete | **NOT READY / UNVERIFIED** | platform experiment confirming directory-disposition + POSIX_SEMANTICS + reparse-open behavior |
| `delete_upload` containment fix (§9) | **NOT READY** | POSIX + Windows execution of the new abstraction; invariant test; design review |
| Independent security review | **NOT SATISFIED** | genuinely independent, terminal-capable reviewer |
| PostgreSQL integration | **NO-GO** | six-part contract outstanding |
| Migrations / database mutation | **NO-GO** | unchanged |
| Unattended destructive cleanup | **NO-GO** | limitations 1–6 outstanding |

Completion of the design step does **not** mean the filesystem-safety gate has passed.

---

## 17. Exact next actions

1. **Obtain a real Linux/POSIX run** of `python -m pytest -q tests/unit/scripts tests/unit/documents`,
   capturing OS/kernel/Python/exit code/skip reasons, with the nine descriptor tests **executing** —
   the only step that moves limitation 1 to measured. Requires an authorized Linux environment.
2. **Confirm the Windows §8.3 UNVERIFIED claims by platform experiment** (`SetFileInformationByHandle`
   `FileDispositionInfo(Ex)` semantics for directories, `FILE_DISPOSITION_POSIX_SEMANTICS` availability,
   reparse-open behavior, non-NTFS behavior) before writing any Windows deletion code.
3. **Implement the §8 binding behind the deterministic race test (§10.3(1))** — the test must fail on
   today’s source and pass only after the fix — then correct the `:306-309` docstring.
4. **Implement the §9 `contained_unlink` abstraction inside `storage/`** (no `scripts/` import), keep
   `delete_upload`’s `bool` contract, and add the §10.3(5) invariant test.
5. **Harden the R-7 test** to assert `dir_fd` on the AST `ast.Call` node.
6. **Provide a genuinely independent review** (separate execution environment and family) before any
   implementation is accepted.
7. **Standing:** keep PostgreSQL integration, migrations and unattended destructive cleanup **NO-GO**.

---

## 18. Explicit final authorization decision

| Decision | Status |
| --- | --- |
| Design deliverable (§7–§10) | **ACCEPTED (CONDITIONAL)** — complete from source; open review/verification items noted |
| Production code changes this step | **NONE AUTHORIZED / NONE MADE** |
| Database-free targeted tests (Windows) | **AUTHORIZED** — 267/13/0, exit 0 |
| Database-free full unit suite (Windows) | **AUTHORIZED** — 1345/23/0, exit 0 |
| Linux/POSIX descriptor-relative deletion | **NOT AUTHORIZED as verified — BLOCKED (no Linux runtime)** |
| Recursive-cleanup race fix implementation | **NOT AUTHORIZED — NOT READY** (prerequisites §16) |
| Windows handle-bound delete implementation | **NOT AUTHORIZED — design UNVERIFIED** |
| `storage/file_store.delete_upload` change | **NOT AUTHORIZED — NOT READY** (§16) |
| PostgreSQL integration | **NOT AUTHORIZED — NO-GO** |
| Migrations / database mutation | **NOT AUTHORIZED — NO-GO** |
| Unattended destructive cleanup | **NOT AUTHORIZED — NO-GO** until limitations 1–6 are closed or explicitly accepted by an independent authority |
| Independent safety review gate | **NOT SATISFIED** — no authorization may rest on §12 |
| Report audit | **NOT SATISFIED** — §12.8 |

**Overall: CONDITIONAL PASS.** The design-and-verification deliverable is substantially complete from
current source (race analysis, POSIX + Windows remediation designs, `delete_upload` contract,
regression-test plan, fresh negative control), but **clearly identified design/review issues remain
open**: the Linux-execution gate is **BLOCKED**, the independent-review gate is **NOT SATISFIED**, and
the Windows design carries **UNVERIFIED** API claims. No production code was changed; the
directory-swap race and the `delete_upload` TOCTOU remain **NOT FIXED**; and every database and
destructive-cleanup restriction is intact.

---

### Compliance statement

No PostgreSQL connection, migration, mutation or reset; no SQL; no real cleanup sweep, archive deletion
or user-upload deletion; no `.env` file or credential read; no WSL, Docker, Podman, VM, package or CI
infrastructure installed; no cloud resources provisioned; no remote workflow created or triggered; no
`git reset`, `clean`, `restore`, stash, checkout, rebase, commit or push; no predecessor report
overwritten (1.6AD `e16438b2d9fc2eba`, 1.6AC `6cafb8ab94741c76` and earlier digests reproduced
unchanged). No production source file was modified: `scripts/cleanup_path.py`, `storage/file_store.py`,
database authorization code, cleanup runners and startup code are all unchanged (the only in-place
change was the negative control’s temporary mutation, restored byte-identically and verified). The
limitation that governs this step — no genuine Linux execution and no independent review — is stated at
the top of §1 and in §5/§12/§15 rather than hidden. No worker wrote or modified this report.
