# STEP 1.6AF — Windows Filesystem API Verification, Linux Execution Readiness, and Independent Safety Review

Date: 2026-10-14
Owner: COORDINATOR (this run)
Mode: **Verification, design review, and test planning only.** Production source changes PROHIBITED. Database operations PROHIBITED. Destructive cleanup PROHIBITED.
Predecessor: `STEP1_6AE_LINUX_VERIFICATION_AND_FILESYSTEM_REMEDIATION_DESIGN_2026-10-14.md` (`a742b7892ef95a35`) — unchanged by this step
Verdict: **CONDITIONAL PASS** (design-and-verification work complete for what was possible). The filesystem-safety gate has **NOT** passed. **LINUX EXECUTION: BLOCKED.** **INDEPENDENT REVIEW: NOT SATISFIED.** **Windows handle-bound deletion: UNVERIFIED.** Implementation is **NOT authorized**.

Evidence labels used throughout: **VERIFIED** (direct evidence), **PROPOSED** (design, not implemented),
**UNVERIFIED** (insufficient evidence), **BLOCKED** (required environment/permission unavailable),
**FAILED** (a required check did not pass), **HISTORICAL** (from a predecessor step), **SOURCE** (read
from the current file), **DOC** (authoritative vendor documentation).

---

## 1. Executive Summary

This step asked whether the proposed cross-platform filesystem remediation can be implemented safely
and tested meaningfully on Windows and Linux/POSIX. The honest answer: **the POSIX side cannot be
verified here (no Linux runtime), and the Windows handle-bound design cannot meet the POSIX containment
objective with documented Win32 primitives alone.**

* **Linux/POSIX execution: BLOCKED — NO AUTHORIZED LINUX RUNTIME** (§4). Host is MSYS Git Bash on
  Windows; `wsl.exe` reports *not installed*; no Docker/Podman/POSIX Python/CI. The POSIX verification
  matrix (§9/§4.3) is prepared but **unexecuted**.
* **Windows API findings (§6):** the load-bearing claim — *can a handle bind a delete to a validated
  object without re-resolving a pathname?* — is **only partly supported by documentation**. Win32
  `CreateFileW`/`SetFileInformationByHandle` **do** provide handle-bound **deletion** and
  no-follow-open, but Win32 exposes **no documented `dir_fd` equivalent** for opening a child *relative
  to a held directory handle*. `FILE_FLAG_OPEN_REPARSE_POINT` affects only the **final** path
  component, so an attacker-controlled **intermediate** component is still re-resolved. Consequence: a
  Windows implementation **cannot claim full parity** with the POSIX descriptor-relative design; the
  safe outcome may be **refuse** (§8).
* **Directory-swap race (§10): CONFIRMED against current source, NOT FIXED.** `cleanup_path.py`
  classifies an entry from one `lstat` (`:321`) and recurses (`:332`); a junction swapped in during
  that interval is followed by `iterdir()` (`:315`) and its **target's** contents can be deleted outside
  the root.
* **Upload deletion (§11):** `storage/file_store.delete_upload` is pathname-based (`:195`) with a TOCTOU
  window; a contract-preserving `storage/_contained_fs.py` design is proposed.
* **Regression-test matrix (§12):** a concrete, non-vacuous test set including a deterministic
  directory-swap race test and invariant tests that assert on **operations/outcomes**, not docstrings.
* **Negative control (§13):** strategy documented; **no production source was mutated this step** (the
  task forbids modifying production code). The 1.6AD/1.6AE executed controls stand as HISTORICAL.
* **Independent review: NOT SATISFIED** (§14) — same-family, non-executing substitute.
* **Preservation (§3): VERIFIED** — HEAD `6baaa2a…` unchanged, tree 385, benchmark/upload digests match,
  source digests unchanged, no markers/temp files.

**No production code was changed. No race is claimed fixed. Implementation is not authorized by this
evidence.**

---

## 2. Scope and Non-Goals

**In scope.** Repository preservation; Linux/POSIX availability determination and an execution matrix;
authoritative Windows API documentation research with explicit uncertainty; adversarial design review
of the race, the Windows design, and the upload-deletion contract; a concrete regression-test matrix and
a negative-control strategy; the verdict.

**Non-goals (explicit).** Modifying `scripts/cleanup_path.py`, `storage/file_store.py`, database
authorization code, cleanup runners, or startup code; adding test hooks to production code; installing
WSL/Docker/Podman/CI or system dependencies; provisioning cloud resources; triggering external
workflows; running integration tests, migrations, server startup, or any real cleanup sweep; changing
protected artifacts; committing or pushing; letting any worker write the coordinator-owned report. This
is **not** an implementation step.

---

## 3. Baseline and Repository Preservation

Rechecked at the start and after the test runs (all **VERIFIED** by command):

| Item | Expected | Observed | Status |
| --- | --- | --- | --- |
| Repository root | `…/stitch_documind_futuristic_3d_ui` | same | VERIFIED |
| Branch | `main` | `main` | VERIFIED |
| HEAD | `6baaa2a0773df66e5fb26814afbe67647fb43435` | identical | VERIFIED |
| Working tree | 385 = 295 deleted + 35 modified + 55 untracked | identical | VERIFIED |
| Staged | 0 | 0 | VERIFIED |
| Benchmark SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` | identical | VERIFIED |
| Upload inventory | 1,212 files / 7,386,232 bytes | identical | VERIFIED |
| `scripts/cleanup_path.py` | (baseline) | `97dbc1b6559a402a…` (unchanged before and after) | VERIFIED |
| `storage/file_store.py` | (baseline) | `ac3f8b43edd7ca8f…` (unchanged) | VERIFIED |
| `STEP1_6AE` report | `a742b7892ef95a35` | identical | VERIFIED |
| Mutation markers / `.16a*.bak` / stray temp | none | none | VERIFIED |

**No production source file changed. No destructive Git operation run. No `.env`/credential read.** The
repository state matches the historical baseline exactly; no discrepancy to report.

---

## 4. Environment and Platform Availability

### 4.1 Probes (all **VERIFIED**, bounded; nothing installed)

| Probe | Command | Observed | Class |
| --- | --- | --- | --- |
| Kernel/OS | `uname -a` | `MINGW64_NT-10.0-26300 … x86_64 Msys` — MSYS, **not Linux** | VERIFIED |
| WSL | `wsl.exe --status` | *"The Windows Subsystem for Linux is not installed."* | VERIFIED |
| Containers | `which docker podman` | absent | VERIFIED |
| POSIX Python | `which python python3` | absent | VERIFIED |
| CI runners | `which act gh` | absent | VERIFIED |
| Repo CI | `.github/workflows`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`, `.circleci`, `.woodpecker.yml`, `bitbucket-pipelines.yml` | none present | VERIFIED |
| Windows Python | `backend/venv/Scripts/python.exe --version` | `Python 3.11.0` | VERIFIED |

### 4.2 Determination

**LINUX EXECUTION: BLOCKED — NO AUTHORIZED LINUX RUNTIME.** No native POSIX host, no authorized Linux
CI runner or workflow, and no other authorized POSIX environment exist. Installing one is prohibited.
MSYS Git Bash is **not** a Linux runtime and its results are not POSIX evidence. The minimum environment
needed: any authorized Linux host (or Linux CI job) with this repository checked out at this tree and
Python 3.11 + the test dependencies, able to run pytest with real `dir_fd` support.

### 4.3 POSIX execution matrix (prepared, UNEXECUTED — for future use)

| # | Verification item | How it is checked | Required platform | Status |
| --- | --- | --- | --- | --- |
| M1 | Descriptor-relative directory traversal | `unlink_beneath`/`rmdir_beneath` happy path removes only the named entry | POSIX | BLOCKED |
| M2 | `O_DIRECTORY` rejects non-directories | open a file path with `O_DIRECTORY` → `ENOTDIR` | POSIX | BLOCKED |
| M3 | `O_NOFOLLOW` refuses a symlinked component | swap an intermediate component for a symlink; expect refusal | POSIX | BLOCKED |
| M4 | `dir_fd` support for exact ops | assert `os.unlink/rmdir/open in os.supports_dir_fd`; run the 8 descriptor tests | POSIX | BLOCKED |
| M5 | Symlink / directory replacement race | deterministic swap between validation and use; assert target survives | POSIX | BLOCKED |
| M6 | Out-of-root deletion prevention | root/parent swap; assert nothing outside root deleted | POSIX | BLOCKED |
| M7 | FD cleanup & error handling | inject `EMFILE`/`ENFILE`; assert refusal + no fd leak | POSIX | BLOCKED |
| M8 | Unsupported-platform behavior | force the gate off; assert refuse, nothing deleted | any | BLOCKED |

None of M1–M8 may be reported as passed: **no Linux execution occurred.**

---

## 5. Previous-Step Evidence

| Item | Source | Class | Note |
| --- | --- | --- | --- |
| Targeted suite `tests/unit/scripts tests/unit/documents` | revalidated this step | **VERIFIED** | **267 passed, 13 skipped, exit 0** |
| Full suite `tests/unit` | revalidated this step | **VERIFIED** | **1345 passed, 23 skipped, exit 0** |
| `compileall` over audited packages | revalidated this step | **VERIFIED** | clean, exit 0 |
| Skip accounting | this step | **VERIFIED** | 13 = 4 symlink-privilege (`WinError 1314`) + 9 POSIX `dir_fd`; full 23 = 10 DB + 4 + 9 |
| Negative control (mutate `cleanup_path.py:325`, test, restore) | 1.6AE / 1.6AD | **HISTORICAL** | fail exit 1 → restore byte-identical → pass exit 0 |
| Directory-swap race identified | 1.6AD/1.6AE + re-analysed here (§10) | **SOURCE** | NOT FIXED |
| `delete_upload` pathname TOCTOU | 1.6AC–1.6AE + re-analysed here (§11) | **SOURCE** | NOT FIXED |

**Limits:** Windows success does **not** establish POSIX correctness; the 9 descriptor-relative tests
**skipped** and are **not** passes. The Windows revalidation proves only that the Windows-reachable
tests still pass and the tree still compiles — nothing about POSIX behaviour.

---

## 6. Windows API Documentation Findings

All rows are **DOC** (authoritative Microsoft Learn pages, cited) reconciled with **SOURCE** analysis of
what the design needs. The recurring theme: Windows documents handle-bound **deletion** and
no-follow-open for the **final** component, but does **not** document a `dir_fd` equivalent for opening
a child *relative to a held directory handle*.

| Claim | Authoritative documentation | Exact supported guarantee | Remaining uncertainty | Required disposable-fixture experiment | Safe fallback |
| --- | --- | --- | --- | --- | --- |
| `CreateFileW` can open a target **without following a reparse point** | `CreateFileW` (fileapi.h) — `FILE_FLAG_OPEN_REPARSE_POINT` 0x00200000 | "Normal reparse point processing will not occur; `CreateFile` will attempt to open the reparse point… **If the file is not a reparse point, then this flag is ignored.**" Scoping the flag to the **final** component is our **INFERENCE** (the docs do not state it); §8 W2 is the experiment that must confirm it. | Intermediate (parent) components are **still** re-resolved/traversed; behavior with filter drivers; flag is inert on filesystems without reparse points (FAT/exFAT) and on network shares. | In `%TEMP%`: open a junction to a populated dir with the flag; confirm the handle refers to the junction (not target). Separately, confirm a **junction in a parent component IS followed**. | **Refuse** if the object must be inspected but cannot be opened no-follow. |
| A reparse point can be **identified through the handle** | `FILE_ATTRIBUTE_TAG_INFO` (winbase.h) "Used for any handles. Use only when calling `GetFileInformationByHandleEx`. The reparse tag." | `GetFileInformationByHandleEx(h, FileAttributeTagInfo, …)` returns `FileAttributes` + `ReparseTag` for the open handle. | ReparseTag is 0 for non-reparse objects; requires the handle to already be open. | Query a junction handle and a plain-dir handle; confirm `FILE_ATTRIBUTE_REPARSE_POINT` bit and a mount-point tag. | **Refuse** if attributes cannot be read. |
| A **file** can be deleted through the handle | `SetFileInformationByHandle` (fileapi.h): `FileDispositionInfo` → `FILE_DISPOSITION_INFO`; "the file would need **DELETE** access requested in… `CreateFile`." | Mark-for-delete via a handle with `DELETE` access; deletion occurs on `CloseHandle` (deferred) unless POSIX semantics are requested. | `FileDispositionInfo` (non-Ex) defers deletion until **all** handles close and link count is 0 — a concurrent open handle can delay/prevent it. | Mark a file for deletion via handle; open a second handle and observe deferred behavior. | **Refuse** if deletion cannot be guaranteed to complete. |
| **POSIX-style immediate** delete | `FILE_DISPOSITION_INFORMATION_EX` (ntddk.h): `FILE_DISPOSITION_DELETE` 0x1, `FILE_DISPOSITION_POSIX_SEMANTICS` 0x2; "the link is removed from the visible namespace as soon as the POSIX delete handle has been closed…" | Struct-level semantics documented (kernel `ZwSetInformationFile`). | The **user-mode** `SetFileInformationByHandle` (fileapi.h, last updated 2021) class table lists `FileDispositionInfo` but **not** `FileDispositionInfoEx`; user-mode availability/class value (Windows 10+) is **NOT confirmed by that page**. | Call `SetFileInformationByHandle(h, FileDispositionInfoEx, …)` on a file handle; confirm success and that the name disappears immediately. | **Refuse** or fall back to documented `FileDispositionInfo` (deferred semantics) — never a pathname `DeleteFile`. |
| A **directory** can be deleted through the handle | `CreateFileW`: `FILE_FLAG_BACKUP_SEMANTICS` 0x02000000 "You **must** set this flag to obtain a handle to a directory." `RemoveDirectory` (fileapi.h): "marks a directory for deletion on close… not removed until the last handle… closed." | A directory handle requires `FILE_FLAG_BACKUP_SEMANTICS`; `RemoveDirectory` marks-for-deletion. | Whether `SetFileInformationByHandle(FileDispositionInfo(Ex))` deletes a **directory** (as opposed to `RemoveDirectory`), and whether a dir handle with `DELETE` access can be dispositioned, is **UNVERIFIED** — the doc does not state it. | On a disposable **empty** dir in `%TEMP%`: open with `FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT` + `DELETE`; call `SetFileInformationByHandle(FileDispositionInfoEx, DELETE|POSIX_SEMANTICS)`; confirm removal. | **Refuse**, or `RemoveDirectory` on a name validated under a held parent handle (only if the parent can be held — see below). |
| Handle-based directory deletion is **non-recursive** | `DeleteFile` (winbase.h): "To recursively delete the files in a directory, use the `SHFileOperation` function." (corrected attribution, auditor A-2); `RemoveDirectory` (fileapi.h): marks for deletion on close, fails on a non-empty directory. | `RemoveDirectory` fails on a non-empty directory. | Same likely for `FileDispositionInfo`. | Attempt handle-deletion of a non-empty dir; confirm refusal. | Recurse only via validated child handles; **refuse** on error. |
| **Sharing** and concurrent replacement | `CreateFileW` `dwShareMode` table; `FILE_SHARE_DELETE` 0x00000004 "Enables subsequent open operations… to request delete access." | Sharing is enforced per handle; a conflicting open fails with `ERROR_SHARING_VIOLATION`. POSIX-delete lets existing handles keep reading. | A concurrent handle opened **without** `FILE_SHARE_DELETE` can make our open fail; conversely, holding `FILE_SHARE_DELETE` weakens our own anchor. | Open a file, hold it without share-delete, attempt our open; confirm the failure mode and error code. | **Refuse**, report the refusal; never retry by pathname. |
| Holding a directory handle **anchors** the root for child opens | *(no Win32 primitive found)* — Win32 `CreateFileW`/`SetFileInformationByHandle` expose **no documented `dir_fd`-equivalent**; relative-to-handle opens are not documented in the fileapi set. The native `NtCreateFile` `OBJECT_ATTRIBUTES.RootDirectory` is the only such primitive and is **undocumented for general use**. | **NONE documented for Win32.** | Whether any supported path provides an anchored child-open; whether `NtCreateFile`+`RootDirectory` is acceptable in production is a policy/**unverified** question. | Investigate/experiment with `NtCreateFile(RootDirectory=parentHandle, …)` on a disposable tree; determine support and risk. | **This is the crux:** without an anchored child-open, a Windows handle-bound design **cannot close the parent-replacement race** and must **refuse** rather than claim parity with POSIX. |

**File-identity APIs (auditor A-10):** the `SetFileInformationByHandle` page names `GetFileInformationByHandle`
and `GetFileInformationByHandleEx` as the handle-query counterparts; file identity (volume serial +
file index) can be captured from a handle. Identity supports **detection** of a swapped object but does
**not** by itself bind a later pathname operation to the object; its exact fields were **not
independently read this step (UNVERIFIED)**.

**Conclusion from the documentation:** Windows can bind a **deletion** to a handle and can open the
**final** component without following a reparse point, but **cannot** (with documented Win32) open a
child **relative to a held directory handle**. Therefore a Windows implementation matches the POSIX
containment objective only for the **final** component, not for **intermediate** path components.

---

## 7. Windows Handle-Bound Deletion Design (PROPOSED — not implemented; key claims UNVERIFIED)

Objective: delete an object bound to a validated handle, never re-resolving an attacker-controlled
pathname, and **refuse** when the guarantee cannot be established.

1. Obtain a handle to the **root** directory: `CreateFileW(root, FILE_LIST_DIRECTORY, FILE_SHARE_READ|
   WRITE|DELETE, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, NULL)`.
   If it fails → **refuse**.
2. For the **final** object: open with `FILE_FLAG_OPEN_REPARSE_POINT` (no-follow for the final
   component) + `DELETE` access, then identify reparse points via
   `GetFileInformationByHandleEx(h, FileAttributeTagInfo, …)`; any reparse point → **refuse**.
3. Delete **by handle**: `SetFileInformationByHandle(h, FileDispositionInfoEx, {DELETE |
   POSIX_SEMANTICS})`. If the class is unavailable (UNVERIFIED), fall back to documented
   `FileDispositionInfo` **only if** its deferred semantics are acceptable; otherwise **refuse**.
4. For **intermediate** it must not claim containment it cannot enforce (§6, last row): because there
   is no documented anchored child-open, the design must either (a) accept the parent-swap residual and
   say so, or (b) **refuse** any operation whose containment depends on an intermediate component. The
   design **chooses (b): refuse** rather than claim parity.

**Note (auditor A-8):** because Win32 exposes no anchored child-open (§6 last row), the step-1 root
handle provides **no containment benefit** for Windows child operations — it is retained only for
fidelity with the POSIX shape and for a possible `NtCreateFile(RootDirectory=…)` implementation; it
does **not** anchor the traversal.

**This design is not production-ready.** §8 lists the experiments required before it could be.

---

## 8. Windows Limitations and Required Experiments

| # | Limitation | Status | Required disposable-fixture experiment | Safe fallback |
| --- | --- | --- | --- | --- |
| W1 | No documented Win32 anchored child-open (`dir_fd` equivalent) | **UNVERIFIED / design-blocking** | Investigate `NtCreateFile(RootDirectory=…)` support and safety on a temp tree | **Refuse** operations needing intermediate-component containment |
| W2 | `FILE_FLAG_OPEN_REPARSE_POINT` binds only the final component | **DOC** | Confirm intermediate junction is still followed | Refuse if an intermediate component could be hostile |
| W3 | `FileDispositionInfoEx` user-mode availability | **UNVERIFIED** | Call it on a temp file handle; check success/errno | Fall back to `FileDispositionInfo` (deferred semantics) or refuse |
| W4 | Handle-deletion of a **directory** | **UNVERIFIED** | Delete a temp empty dir by handle; confirm | `RemoveDirectory` under a held parent, or refuse |
| W5 | Non-recursive dir deletion | **DOC** | Delete a non-empty dir by handle; confirm refusal | Recurse via validated child handles; refuse on error |
| W6 | Concurrent-handle / sharing effects | **DOC/UNVERIFIED** | Hold a non-share-delete handle; observe our open/deletion | Refuse, report; never pathname-retry |

**Operational impact of refusal:** if W1 cannot be resolved, a Windows handle-bound `__pycache__` prune
**cannot** meet the POSIX objective and would **refuse** on this platform — which would make
`start_server.py:75`'s prune a **no-op on Windows** (the R-10 concern from 1.6AE). That trade-off
(refuse vs. functional-but-pathname-based cleanup) **must be an explicit operator decision**, and no
unsafe pathname fallback is permitted merely to preserve functionality.

---

## 9. POSIX Descriptor-Relative Design (PROPOSED — unexecuted on POSIX)

1. `intended_root(root)` validates the root; hold it with
   `os.open(root, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)`; failure → **refuse** (never pathname retry).
2. Recurse by opening each child `os.open(name, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC,
   dir_fd=parent_fd)` — the open *is* the validation and the binding; `O_NOFOLLOW` refuses a symlinked
   component, `O_DIRECTORY` refuses a non-directory.
3. Enumerate with `os.scandir(child_fd)`; classify from the **dirent**
   (`is_symlink()`, `is_dir(follow_symlinks=False)`) — never from a re-resolved pathname.
4. Remove a regular file with `os.unlink(name, dir_fd=fd)` (never follows a final symlink); remove a
   directory with `os.rmdir(name, dir_fd=fd)` (refuses a non-empty dir and a symlink).
5. Availability gate: `os.open/unlink/rmdir in os.supports_dir_fd` and `O_NOFOLLOW`/`O_DIRECTORY` →
   else **refuse**. Bound recursion depth; handle `EMFILE`/`ENFILE` by refusing.
6. **Residual (documented):** the final *name* in a held directory can still be swapped; the effect is
   bounded to that held directory (unlink removes the link, rmdir refuses) — **no escape**.

**Do not treat as validated:** this is **PROPOSED** and has not run on an authorized POSIX system
(§4.3, M1–M8 all BLOCKED).

---

## 10. Directory-Swap Race Analysis (SOURCE — confirmed; NOT FIXED)

Current implementation: `scripts/cleanup_path.py` — `prune_pycache_beneath` (`:280`), inner
`_remove_validated_tree` (`:305`).

Sequence (each **SOURCE**, line-verified):

1. `entries = sorted(directory.iterdir())` (`:315`).
2. `info = os.lstat(entry)` (`:321`) — the **single** classification.
3. Refusal `stat.S_ISLNK(info.st_mode) or (st_mode & FILE_ATTRIBUTE_REPARSE_POINT)` (`:325`).
4. `if stat.S_ISDIR(info.st_mode): _remove_validated_tree(entry)` (`:332`) — **no re-validation**.
5. `os.unlink(entry)` (`:335`) / `os.rmdir(directory)` (`:340`).

**Answers:**
1. **Between check and use:** the reparse refusal (`:325`) and the `S_ISDIR` branch (`:331`); no
   re-validation of `entry`. The outer `validate_candidate(root, candidate)` (`:354`) covers only the
   top-level `__pycache__` name.
2. **Replaceable?** Yes — a concurrent writer with access to the parent can rename the entry away and
   substitute a junction/symlink before `:332`.
3. **Out-of-root reach?** Yes — the recursion's `iterdir()` (`:315`) follows a junction, enumerating the
   **target's** contents; `os.unlink` (`:335`) then deletes them. **This is an escape channel, not
   "bytecode-only."**
4. **Do descriptor-relative helpers protect this path?** No — `unlink_beneath` (`:437`) and
   `rmdir_beneath` (`:483`) are not used by the prune; it is pathname-based (`iterdir`, `os.unlink`,
   `os.rmdir`) on both platforms.
5. **Windows residual?** The same prune race, plus pathname deletes in `file_store.py:195` and the
   Windows fallbacks in `cleanup_smoke.py` (`:194`, `:248`). **POSIX residual?** The prune race and
   `file_store.py:195`.
6. **Tests for static refusal:** `test_pycache_prune_safety.py::test_a_link_nested_inside_a_pycache_is_refused`
   (`:222`), `…::test_a_linked_pycache_is_refused_and_its_target_survives` (`:201`) — pass on this host.
7. **Tests for replacement between check and traversal?** **None.**
8. **Evidence needed:** the deterministic race test (§12) plus POSIX execution (§4.3).

**Disposition: NOT FIXED.** The POSIX design (§9) would close it **if implemented and verified**; the
Windows design (§7) **cannot** close the intermediate-component case (§6). Do not claim closed.

---

## 11. Upload Deletion Design (`storage/file_store.delete_upload`) (PROPOSED)

Current (SOURCE, `file_store.py`): `delete_upload` def `:137`; `candidate`/`base` `:159-160`; `..`
refusal `:170-171`; `_resolved_within` call `:173`; link/reparse `:176`; `_has_link_ancestor` call
`:184`; `S_ISREG` `:191`; pathname `candidate.unlink()` `:195`. **TOCTOU** between the last check and
`:195` (and between `:173` and `:195`). Callers: `documents/routes.py:632` (`delete_upload(stored_path)`,
return ignored), `documents/routes.py:448`/`:459` (`cleanup_new_file(stored_path)`, returns None),
`scripts/cleanup_smoke.py:194` (`if delete_upload(resolved, root=root)`, return **used**).

**Contract to preserve:** `delete_upload(stored_path, *, root=None) -> bool` — `True` = deleted, `False`
= refusal; `cleanup_new_file(...) -> None`; refusals never raise and never delete outside the root.

**Proposed hardening (PROPOSED — not implemented; no import from `scripts/`):** a production module
`storage/_contained_fs.py` exposing `contained_unlink(root, relative_name) -> Status`:
1. **Trusted root** from `settings.upload_path` (operator config), validated once (not a link/reparse
   point; resolves to itself).
2. **Candidate → root-relative name** `lexically` (`candidate.relative_to(base)` after `..` rejection
   `:170-171`); **no** `os.path.relpath`/`resolve` after the root is held.
3. **Traversal** opens the root descriptor and each component `O_NOFOLLOW` relative to the previous
   descriptor (POSIX), so intermediate components are never re-resolved from a pathname.
4. **Deletion bound** to the verified parent descriptor (`os.unlink(name, dir_fd=…)`); Windows uses the
   §7 handle-bound path **only** where §6/§8 guarantees hold, else refuses.
5. **Failures leave the upload untouched** (refusal, orphan retained).
6. **Callers distinguish** success from refusal via the preserved `bool` (mapped from `Status`).
7. **No unsafe pathname fallback** is permitted; an unsupported platform → `Status.UNSUPPORTED` → `False`.

**Do not modify `storage/file_store.py` this step.** Disposition: **DEFERRED.**

---

## 12. Regression-Test Matrix (PROPOSED; all fixtures under `tmp_path`/`%TEMP%`)

| ID | Test name (proposed) | Threat model | Setup | Expected safe result | Non-vacuity | Platform | Current status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1a | `test_directory_swap_documents_todays_vulnerability` | Concurrent dir→junction swap | `root/pkg/__pycache__/real.pyc` + `outside-target/precious.txt`; hook `os.lstat` (`:321`) to swap the entry for a junction after classification | `outside-target/precious.txt` **destroyed on today's code** (documents the bug) | asserts **filesystem outcome** | Windows (junction) | NOT IMPLEMENTED |
| T1b | `test_directory_swap_is_refused_after_fix` | Same, post-fix | drive the fix through a **shared seam** (`_open_child_dir(parent_fd, name, nofollow=True)` / `_classify(entry, parent_fd)`) present in **both** implementations; swap inside the seam | call **refuses**; `outside-target/precious.txt` **survives**; refusal reported | seam exists in both impls, so it cannot pass vacuously (R-7) | POSIX (and Windows via junction) | NOT IMPLEMENTED |
| T2 | `test_parent_swap_during_traversal_cannot_delete_outside_root` | Parent replacement (case D) | swap an intermediate parent for a link before descent | refusal; nothing outside root deleted | asserts target content unchanged | POSIX | NOT IMPLEMENTED |
| T3 | `test_final_name_swap_is_bounded_to_held_directory` | Final-name swap | swap the final name for a link in the held dir | `unlink` removes the link (not target); `rmdir` refuses a symlink | asserts the **target** file survives | POSIX | NOT IMPLEMENTED |
| T4 | `test_symlink_and_junction_static_refusal_survives` | Link/reparse present | insert a symlink/junction; run prune | refused; target survives | differential (link vs real dir) — already partly covered | Windows + POSIX | PARTIAL (existing tests) |
| T5 | `test_descriptor_relative_removes_only_named_entry` | Correct descriptor-relative delete | tmp tree; call `unlink_beneath`/`rmdir_beneath` | only named entry removed; siblings survive | asserts filesystem state | POSIX | SKIPPED today |
| T6 | `test_windows_handle_bound_delete_refuses_when_unverifiable` | Unsupported guarantee (§8 W1/W3/W4) | force the capability check to fail | refuse; nothing deleted | asserts nothing deleted | Windows | NOT IMPLEMENTED |
| T7 | `test_delete_upload_refuses_out_of_root_and_survives_race` | `delete_upload` TOCTOU | swap target between validation and delete | `False`; target survives | asserts return + filesystem state | POSIX + Windows | NOT IMPLEMENTED |
| T8 | `test_unsupported_platform_refuses_without_pathname_fallback` | Missing primitive | force `supports_dir_fd`/capability off | refuse (`UNSUPPORTED`); nothing deleted | asserts no deletion occurred | any | NOT IMPLEMENTED |
| T9 | `test_dir_fd_asserted_on_ast_call_node` | Vacuous docstring assertion | parse `unlink_beneath`/`rmdir_beneath` | `dir_fd` present on the **`ast.Call` node** | AST-based (not text) | any | PROPOSED (hardens existing) |

**Note (auditor A-7):** T6 covers only the Windows **refusal** path; there is no positive Windows
handle-bound **success** test, because the §8 APIs are UNVERIFIED — add it only after the §8
experiments succeed.

**Rule:** T1a must fail on today's source (it documents the vulnerability by destroying the target);
T1b/T2/T3/T7 must **fail on today's source and pass only after** an implemented, reviewed fix, and T1b
must use the **shared seam** so it cannot pass vacuously (R-7). They must not run against real
repository/upload/user data.

---

## 13. Negative-Control Strategy

**This step did not mutate production source.** The task forbids modifying production code, so no fresh
in-place mutation was performed. The strategy for the future implementation step:

1. Fingerprint the implementation file (SHA-256).
2. Apply the **minimum** mutation that disables the specific protection (e.g. make the file's
   containment/reparse refusal a no-op, or replace the anchored open with a raw `open`).
3. Run the targeted protection test (§12, e.g. T1) and require it to **fail** (intended reason).
4. Restore the original bytes; verify **byte-identical** (digest).
5. Re-run the test and require it to **pass**.
6. Confirm no marker, backup, or temp artifact remains.

**Historical executed controls (HISTORICAL — not re-run this step):** 1.6AE/1.6AD neutralizing
`cleanup_path.py:325` made `test_a_link_nested_inside_a_pycache_is_refused` fail (exit 1), the file was
restored byte-identically (`97dbc1b6559a402a…`), and the test re-ran green (exit 0). That control proves
the **static** nested-link refusal is load-bearing; it does **not** cover the directory-swap race (T1).

---

## 14. Independent Review Findings (HISTORICAL from 1.6AE; no review was dispatched this step)

**This step dispatched no independent security reviewer (Agent F was not performed).** The findings
below are **HISTORICAL** — the adversarial review from Step 1.6AE, carried forward because it challenges
exactly the points this step formalises. They are **not** a fresh review and are **not** evidence of
independence. **INDEPENDENT REVIEW: NOT SATISFIED.** In 1.6AE the reviewer was a
`base3-fast-worker-deepseek-flash` worker — the **same model/runtime family** as the coordinator,
read-only, **no terminal**, executed nothing, wrote no files: no separate execution environment, no
distinct family, no ability to run tests. This unmet requirement is recorded as a blocker, not
disguised.

The reviewer's R-1…R-10 findings (from 1.6AE) challenge exactly the points this step formalises, and
their substance is carried into §6/§8/§10/§11:

| ID | Finding | Disposition here |
| --- | --- | --- |
| R-1 | fd/root acquisition re-resolves the root path; parent could be swapped before open | Noted as residual in §9.1 (provenance bounds it) |
| R-2 | Design must not contradict itself on symlink handling (refuse vs remove-link) | §9.4 states both cases explicitly |
| R-3 | Directory-swap race is real and out-of-root (not bytecode-only) | §10 confirms; NOT FIXED |
| R-4 | `os.scandir(fd)`/dirent classification asserted, not verified | Added to §4.3 matrix |
| R-5 | Windows reparse/deletion claim asserted, not verified | §6/§8: marked UNVERIFIED; experiments listed |
| R-6 | `delete_upload` relative-name derivation underspecified | §11.2 fixes it (lexical, no post-root relpath) |
| R-7 | Race test could pass vacuously after the fix removes the seam | §12 T1 + rule "must fail on today's source" |
| R-8 | Negative control valid but covers only the static case | §13 states the limit |
| R-9 | No POSIX evidence | §4.2 BLOCKED |
| R-10 | Refusal fallback would make the prune a no-op on Windows | §8 owns it as an explicit operator trade-off |

**This section records a reviewer's assessment, not independent verification.** No finding was silently
dismissed.

---

## 15. Risks, Blockers, and Unverified Claims

| # | Risk / blocker | Status | Owner (contract) |
| --- | --- | --- | --- |
| 1 | No authorized Linux/POSIX runtime → POSIX design unexecuted | **BLOCKED** | LINUX_ENVIRONMENT_VERIFIER / COORDINATOR |
| 2 | Directory-swap race in `_remove_validated_tree` (`:321→:332`) | **NOT FIXED** | FILESYSTEM_SECURITY_ARCHITECT / BACKEND_AGENT |
| 3 | Win32 lacks a documented anchored child-open (`dir_fd` equivalent) | **UNVERIFIED / design-blocking** | WINDOWS_FILESYSTEM_SPECIALIST |
| 4 | `FileDispositionInfoEx` user-mode availability; directory handle-deletion | **UNVERIFIED** | WINDOWS_FILESYSTEM_SPECIALIST |
| 5 | Refusal on Windows would make the bytecode prune a no-op | **OPERATOR DECISION REQUIRED** | COORDINATOR / operator |
| 6 | `storage/file_store.delete_upload` pathname TOCTOU (`:195`) | **NOT FIXED** | BACKEND_AGENT |
| 7 | Test suite could pass without detecting the vulnerability | **MITIGATED BY DESIGN** (§12 T1/T2/T3/T7) | TEST_AGENT |
| 8 | Independent review not satisfied | **NOT SATISFIED** | COORDINATOR |
| 9 | Final-name swap inside a held directory is unclosable in the stdlib (bounded) | **OPEN, BOUNDED** | SECURITY_AGENT |

No implementation is authorized while #1–#4 stand.

---

## 16. Database and Destructive-Operation Gates

Source inspection only — **no connection, migration, mutation or `.env` read.** Gates (`evaluation/isolation.py`,
re-verified): `_proof_is_live` `:363` (returns `False`), `record_created_database` `:369`,
`assert_disposal_authorized` `:377`, `assert_creation_authorized` `:415`, `assert_row_cleanup_authorized`
`:443`, `assert_cleanup_execution_authorized` `:456`, `release_database_proof` `:477`,
`assert_engine_bound_to_proof` `:485` — all refuse; none relaxed this step.

**Explicit NO-GO (unchanged):** PostgreSQL integration **NO-GO**; database migrations **NO-GO**;
database mutations **NO-GO**; unattended destructive cleanup **NO-GO**; production filesystem
remediation **NOT AUTHORIZED IN THIS STEP**; commit and push **PROHIBITED**. Passing filesystem tests
do **not** authorize database work.

---

## 17. Final Verdict and Exit Criteria

**Verdict: CONDITIONAL PASS** for the design-and-verification work that was actually possible. The
filesystem-safety gate has **NOT** passed, and **implementation is NOT authorized** by this evidence.

Sub-gates:

| Gate | Result |
| --- | --- |
| Repository baseline preserved | **VERIFIED** |
| Windows API claims documented with explicit uncertainty | **VERIFIED** (DOC §6) |
| Linux/POSIX execution | **BLOCKED** |
| Directory-swap race | **NOT FIXED** |
| Windows handle-bound deletion design | **UNVERIFIED** (§8 experiments required) |
| POSIX descriptor-relative design | **PROPOSED, unexecuted** |
| Upload-deletion design | **PROPOSED, deferred** |
| Regression-test matrix | **PROPOSED** (T1/T2/T3/T7 must fail on today's source) |
| Independent safety review | **NOT SATISFIED** |
| Database / destructive-cleanup gates | **NO-GO** |

**Exit criteria:** all (§9 of the task) met except those the environment blocks (Linux execution) and
those the review cannot satisfy (independence), each documented rather than improvised. **The report
does not claim the gate passed** despite: a reasonable-looking design, passing Windows tests, missing
Linux tests, or a same-family agreement.

**Note on the verdict rule (auditor A-11):** §7 of the task says to "use BLOCKED if a required
execution environment or permission is unavailable." The Linux-execution sub-gate is therefore recorded
as **BLOCKED**; the overall step is labelled **CONDITIONAL PASS** only because §7 also permits that
label "for completion of the design-and-verification work that was actually possible." If a single
overall label is required, **BLOCKED** is the more conservative reading and should be preferred —
either way, **implementation is not authorized and the filesystem-safety gate has not passed.**

---

## 18. Evidence Index and Reproducibility

**Report identity:** `backend/architecture/STEP1_6AF_WINDOWS_API_LINUX_READINESS_AND_INDEPENDENT_REVIEW_2026-10-14.md`
Report SHA-256 (this whole line is excluded from its own digest; reproduce with `grep -v '^Report SHA-256' STEP1_6AF_WINDOWS_API_LINUX_READINESS_AND_INDEPENDENT_REVIEW_2026-10-14.md | sha256sum`): `ce9d46fe84e22f6f42247e7404d6530970b6bac3e78c2997a7e9807ab14fb9ac` (short 16-hex: `ce9d46fe84e22f6f`)

**Commands executed this step (from `backend/`; exit codes are the tested command's own):**

| # | Command | Result | Exit |
| --- | --- | --- | --- |
| 1 | `git rev-parse HEAD` / `git status --porcelain` (start and end) | `6baaa2a…`; 385 entries | 0 |
| 2 | `sha256sum phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | `1166bf4f…` | 0 |
| 3 | `find uploads -type f \| wc -l`, `du -sb uploads` | 1212 / 7386232 | 0 |
| 4 | `sha256sum scripts/cleanup_path.py storage/file_store.py` | `97dbc1b6…` / `ac3f8b43…` | 0 |
| 5 | `venv/Scripts/python.exe -m pytest -q tests/unit/scripts tests/unit/documents` | 267 passed, 13 skipped | 0 |
| 6 | `venv/Scripts/python.exe -m pytest -q tests/unit` | 1345 passed, 23 skipped | 0 |
| 7 | `venv/Scripts/python.exe -m compileall -q …` | clean | 0 |
| 8 | `wsl.exe --status`; `which docker podman python python3 act gh` | MSYS; all absent | — |

**Authoritative documentation cited (§6), all Microsoft Learn:**
`CreateFileW` — https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew ·
`SetFileInformationByHandle` — https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle ·
`FILE_DISPOSITION_INFORMATION_EX` — https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_file_disposition_information_ex ·
`Reparse Points and File Operations` — https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations ·
`FILE_ATTRIBUTE_TAG_INFO` — https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_attribute_tag_info ·
`RemoveDirectory` — https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-removedirectorya

**Source references (current tree):** `scripts/cleanup_path.py` (`:280`, `:305`, `:315`, `:321`,
`:325`, `:332`, `:335`, `:340`, `:354`, `:437`, `:483`); `storage/file_store.py` (`:137`, `:159-160`,
`:170-171`, `:173`, `:176`, `:184`, `:191`, `:195`, `:201`); `scripts/cleanup_smoke.py` (`:189`,
`:194`, `:226`, `:246`, `:248`, `:259`); `scripts/start_server.py:75`; `documents/routes.py` (`:448`,
`:459`, `:632`); `evaluation/isolation.py` (`:363`–`:485`).

**Reproducibility:** re-run commands #1–#7 to reproduce the preservation and Windows-test results.
**Nothing here establishes POSIX behaviour** — that requires the §4.3 matrix on an authorized Linux
host.

---

### Compliance statement

No production source file was modified (the temp-mutation negative control was executed as a single
control in 1.6AD and again in 1.6AE, and as a set of three in 1.6AB; **none** was executed in 1.6AF); no destructive Git operation, commit or push; no PostgreSQL connection, migration,
mutation or reset; no SQL; no real cleanup sweep, archive deletion or user-upload deletion; no `.env`
or credential read; no WSL/Docker/Podman/CI/system dependency installed; no cloud resource provisioned;
no external workflow triggered; no predecessor report overwritten (1.6AE `a742b7892ef95a35` and earlier
digests unchanged). All §12 tests are PROPOSED and were not implemented or executed against real data.
No worker wrote or modified this report.
