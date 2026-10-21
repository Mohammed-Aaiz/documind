# STEP 1.6V — Filesystem Guard Remediation Design

Date: 2026-10-13
Owner: COORDINATOR.
Task type: **design only.** No source, test, configuration or safety gate was modified. No cleanup, deletion, test, database or migration operation was executed.

## PROVISIONAL — INDEPENDENT REVIEW GATE NOT SATISFIED

The named specialists (`SECURITY_AGENT`, `TEST_AGENT`, `EVALUATION_AGENT`, `VERIFIER`) are **NOT EXECUTED — runtime dispatch unavailable** (§2). A single coordinator performed all analysis with generic read-only search workers. The design in §7 is a coordinator proposal; it has not been challenged by an independent verifier. **The filesystem is not safe merely because this design exists.**

**Label convention used throughout** (per §7 of the task):

| Label | Meaning |
|---|---|
| `[OBS]` | Direct source observation — read from the current file at the cited lines |
| `[INF]` | Inference from source — a conclusion drawn from those observations, not itself observed |
| `[PLAT]` | Platform-dependent assumption — needs verification on the target OS |
| `[PROP]` | Unverified proposal — designed here, never executed |

---

## 1. Executive verdict and scope

**Verdict: both Step 1.6U findings are CONFIRMED against current source, and the practical impact is larger than 1.6U recorded.**

1. `[OBS]` `backend/scripts/cleanup_path.py:48` compares `root.resolve(strict=False)` with `root_real`, which is assigned at `:44` from the *same* expression on the *same* unchanged object. `Path.resolve()` is idempotent, so the condition is always false and the refusal at `:49-51` is unreachable.
2. `[OBS]` `filesystem_supports_relative_symlinks()` returns the constant `True` at `:66`; its docstring `:60-64` states the real check is deferred. The import-time gate at `cleanup_orphan_uploads.py:50-51` therefore cannot fail closed.
3. `[OBS]` Beyond the two reported items, three further ordering/coverage facts are visible in the current source:
   - `forbid_symlink_roots(root)` is called at `cleanup_orphan_uploads.py:197` — **after** the archive step at `:192-195`, so with a symlinked root the sweep copies file contents into a zip before any root validation runs.
   - The directory-prune pass (`:214-226`) calls `path.rmdir()` at `:223` with **no** `is_under` call, no `forbid_symlink_roots` call, and a bare `except OSError: pass` at `:225-226`.
   - `is_under` is called exactly once in the deletion loop (`:203`); `rmdir` at `:223` has no containment check of any kind.
4. `[INF]` Consequently, on a host where symlinks can be created, a symlinked upload root is **not refused**: `is_under(root, path)` at `:203` resolves both sides through the link, agrees they are contained, and the loop deletes the files in the *link target*. The existing test `test_symlinked_upload_root_is_rejected` (`tests/unit/scripts/test_cleanup_orphan_uploads.py:203-230`) asserts `exit code == 1` and that the real files survive; the current code would return `0` from `:238` and delete them. `[INF]` The test can only be reached on a symlink-capable host, and silently `pytest.skip`s at `:210` otherwise — which is why this defect has survived.
5. `[OBS]` The helpers have **one** production importer: `cleanup_orphan_uploads.py:46`. No other module in the repository imports `scripts.cleanup_path` (§4).

Scope: design for path validation and orphan-upload cleanup as directed by the six design questions V-01…V-06. Out of scope and untouched: database lifecycle authorization, evaluation runners, the `cleanup_smoke.py` deletion path (flagged as adjacent in §4.4, requires separate authorization), and the upload/write path.

## 2. Named-agent dispatch and actual-execution evidence

| Named specialist | Dispatch attempted | Actual status | Execution evidence | Files/findings it would have covered | Output |
|---|---|---|---|---|---|
| COORDINATOR | n/a (self) | **EXECUTED** | this report | all | plan, inventory, design, decisions |
| SECURITY_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | the runtime exposes only generic subagents; no target instantiates the role defined in `agents/security-agent.md` | V-01…V-05, call sites | none (role never ran) |
| TEST_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | V-06 | none (role never ran) |
| EVALUATION_AGENT | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | caller/authorization preservation | none (role never ran) |
| VERIFIER | Yes | **NOT EXECUTED — runtime dispatch unavailable** | as above | challenge of §7 | none (role never ran) |
| Generic `code-searcher` #1 | Yes | EXECUTED | 5 query batches; 43 / 9 / 16 / 5 / 193 matches returned with file:line | helper call sites, `upload_path`, resolve/symlink usage | call-site inventory (§4.3) |
| Generic `code-searcher` #2 | Yes | EXECUTED | 5 query batches; 14 / 13 / 165 / 37 / 2 matches with file:line | test definitions, skip conditions | test inventory (§9) |

**Integrity statement.** Generic search workers are evidence-gathering tools, not specialists. No independent review, no test-agent design review, and no verifier challenge has occurred. Every design decision in §7 is unreviewed.

## 3. Source-artifact availability

| Artifact | Exists | Size | Lines | Used as |
|---|---|---|---|---|
| `backend/scripts/cleanup_path.py` | YES | 2,407 B | 66 | Primary subject `[OBS]` |
| `backend/scripts/cleanup_orphan_uploads.py` | YES | 9,278 B | 259 | Primary subject `[OBS]` |
| `backend/tests/unit/scripts/test_cleanup_orphan_uploads.py` | YES | 9,925 B | 255 | Test definitions `[OBS]` |
| `backend/evaluation/isolation.py` | YES | 22,240 B | 522 | Authorization boundary to preserve `[OBS]` |
| `backend/architecture/STEP1_6U_INDEPENDENT_FINDING_ADJUDICATION_2026-10-13.md` | YES | 33,814 B | — | Prior findings U-03, U-05 |
| `backend/architecture/STEP1_6T_MANIFEST_CLASSIFICATION_AND_SAFETY_BOUNDARIES_2026-10-13.md` | YES | 37,817 B | — | Prior findings T-R03, caller mapping |
| `backend/config.py` | YES | 7,135 B | 184 | Root source (`upload_path`, `:140-143`) |
| `backend/storage/file_store.py` | YES | 2,147 B | 79 | Writer side / adjacent deletion |
| `backend/scripts/cleanup_smoke.py` | YES | 6,587 B | 184 | Adjacent unguarded deletion path (§4.4) |

No required artifact is absent. Where a prior report's claim was checked against the current file, the file governs; no contradiction was found between 1.6U/1.6T and current source for the items in §5.

## 4. Current implementation and call-site map

### 4.1 The three helpers `[OBS]`

| Helper | Lines | Body |
|---|---|---|
| `is_under(root, path) -> bool` | `cleanup_path.py:18-34` | resolves both (`:26-27`), `OSError` → `False` (`:28-29`), strips trailing separators (`:31-32`), returns `path_str == root_str or path_str.startswith(root_str + os.sep)` (`:34`) |
| `forbid_symlink_roots(root) -> None` | `:37-51` | `root_real = root.resolve(strict=False)` (`:44`), `OSError` → `RuntimeError` (`:45-46`), then `if root.resolve(strict=False) != root_real:` (`:48`) → `RuntimeError` (`:49-51`) — **condition is always false** |
| `filesystem_supports_relative_symlinks(path=None) -> bool` | `:54-66` | body is `return True` (`:66`) |

Note `[OBS]`: the module docstring (`:1-10`) claims the helpers "never follow symlink escape" and "never delete anything" — the second is true, the first is not established by the code.

### 4.2 Complete call-site inventory `[OBS]`

A repository-wide search for the three names returns exactly these sites — there is no hidden caller:

| Call site | Kind | Note |
|---|---|---|
| `cleanup_orphan_uploads.py:46` | import | the **only** importer of `scripts.cleanup_path` in production |
| `cleanup_orphan_uploads.py:50` | gate | `if not filesystem_supports_relative_symlinks():` → `RuntimeError` at `:51`, evaluated **at import time** |
| `cleanup_orphan_uploads.py:197` | call | `forbid_symlink_roots(root)` — before the deletion loop, after the archive |
| `cleanup_orphan_uploads.py:203` | call | `is_under(root, path)` — the only containment call |
| `test_cleanup_orphan_uploads.py:32` | import | test module import |
| `test_cleanup_orphan_uploads.py:239` | call | `assert not is_under(Path("/tmp/root"), Path("/tmp/outside.txt"))` |
| `test_cleanup_orphan_uploads.py:244` | call | `assert is_under(Path("/tmp/root"), Path("/tmp/root/file.txt"))` |
| `test_cleanup_orphan_uploads.py:255` | call | `with pytest.raises(RuntimeError, match="symlink"): forbid_symlink_roots(symlink_root)` |

`cleanup_smoke.py` does **not** import or call any of the three helpers.

### 4.3 Data flow through `run_sweep` `[OBS]`

```
:48  settings = get_settings()                        module scope, import time
:50  capability gate (constant True)                  import time
:135-140  read DB reference set; on failure ABORT → return 2
:148-150  root missing → "Nothing to do" → return 0   (no deletion path)
:152  files, entries = _scan_uploads()                root.rglob("*") :86, root.iterdir() :87
:154-156  orphans / kept / bytes classification
:158-162  empty_entries (independent rglob)
:175-177  DRY RUN → return 0
:183-190  confirmation prompt → return 1 on refusal
:192-195  _archive_orphans(orphans, root, archive)    archive written + CRC-verified ; failure → return 3
:197  forbid_symlink_roots(root)                      ← root checked only HERE, after the archive
:201-212  deletion loop: is_under(:203) → stat(:209) → path.unlink()(:210)
:214-226  prune pass: independent rglob(:217) → rmdir(:223), bare `except OSError: pass`(:225-226)
:232-235  verification re-scan ; :238 return 0 or 1
```

Root provenance `[OBS]`: `settings.upload_path` (`config.py:140-143`) is a property that returns `Path(self.upload_dir)` and **creates it** with `mkdir(parents=True, exist_ok=True)` if missing — so "root exists" is true by construction, and the `:148` missing-root branch is largely unreachable in practice. It is read at `:85` (inside `_scan_uploads`), `:132` (`run_sweep`) and `main.py:81` (startup mkdir).

### 4.4 Adjacent unguarded deletion path (out of scope, flagged) `[OBS]`

`cleanup_smoke.py` deletes upload files without using any of the helpers: it resolves a stored path with `settings.upload_path.parent / path` (`:61`) and calls `delete_upload(resolved)` (`:113`, implemented in `storage/file_store.py:53-65`, whose body is `stored_path.unlink()` at `:61` guarded only by an `OSError` swallow at `:63-64`), then `shutil.rmtree(user_dir)` (`:136`). No containment check, no symlink check. This was noted as P19 in Step 1.6P. **It is not part of this design's scope and no change to it is proposed here**; it needs its own authorization and reviewer.

## 5. V-01 … V-06 — evidence-backed findings

### V-01 — Symlink-root detection

- **Why it behaves as it does** `[OBS]`: the author's intent was "if resolving the root changes the value, the root was a symlink". The comparison at `:48` uses `root.resolve(strict=False)` on the left and `root_real` — assigned from `root.resolve(strict=False)` at `:44` — on the right. Since `resolve()` is idempotent (`resolve(resolve(p)) == resolve(p)`), the two sides are equal for every possible filesystem state; the branch is unreachable. `[INF]` The idea is salvageable only if the two sides are *independently computed*: "does the lexical absolute form differ from the resolved form" compares two different derivations, whereas "does the resolved form differ from the resolved form" compares one derivation with itself.
- **What is missing** `[OBS]`: nothing in `cleanup_path.py` ever calls `is_symlink()`, `lstat()`, or inspects reparse attributes. The configured path itself (`settings.upload_path`) is never retained as a separate value; `run_sweep` re-reads `settings.upload_path` at `:132` and `_scan_uploads` re-reads it at `:85`, so there is no single pinned "intended root" object.
- **Five quantities the design must keep distinct** (task §4/V-01):

| Quantity | Definition (design) | Status today |
|---|---|---|
| configured path | `settings.upload_dir` / `settings.upload_path` as configured | exists, never treated as authoritative |
| lexical absolute | `os.path.abspath(configured)` — no filesystem access, no link following | never computed |
| resolved target | `os.path.realpath(configured)` / `Path.resolve(strict=…)` | computed at `:44,:48` and discarded |
| intended root | the directory the operation is authorized to modify | **never independently established** |
| actually traversed | the directory `rglob`/`unlink`/`rmdir` actually act on | `settings.upload_path` re-read per function (`:85`, `:132`, `:217`) |

- **Verdict** `[OBS]`: confirmed defect. `is_symlink(lstat)`-based or `abspath != realpath`-based detection is absent, and with `strict=False` a **missing or unresolvable root is indistinguishable from a valid one** `[OBS]` (`:44` succeeds lexically). Detection must additionally treat a missing/inaccessible root as a refusal in the destructive path.

### V-02 — Path containment

- **Current invariant** `[OBS]`: string prefix on twice-resolved paths (`:31-34`), with `os.sep` appended — `path_str == root_str or path_str.startswith(root_str + os.sep)`.
- **Why this is not an identity-based containment proof** `[INF]`:
  - it compares **strings**, not filesystem objects: two different directories that render the same string (alternate separators, Windows 8.3 short names, trailing dots/spaces, case variants, UNC vs mapped-drive prefixes) are indistinguishable to it;
  - `strict=False` at `:26-27` means **non-existent paths are resolved lexically**, so containment can be "proved" for a path that does not exist — the guard no longer speaks about real files;
  - it is evaluated once, per file, at `:203`, with the destructive use at `:210` and the prune `rmdir` at `:223` outside it;
  - a symlinked *ancestor* resolves consistently on both sides, so a path reached through a link is reported as contained — which is exactly the state that must be refused, because the operation will act on the link target.
- **What containment must mean** (design answer): containment is a property of the **resolved pair measured against the intended root**, not of the string; and when the root itself resolves elsewhere than its configured/lexical form, "containment" is **undefined and the operation is refused** (`[PROP]`, §7).
- **Required handling** — the design must state observable behavior for each input class (`[PROP]`, detailed in §7.4):

| Input | Required behaviour |
|---|---|
| absolute path | resolve; must be inside the intended root; otherwise refuse |
| relative path | resolve against the **intended root**, never against the process CWD; otherwise refuse |
| `..` component | permitted only if the fully resolved path remains inside the intended root; any residual `..` in the relative path ⇒ refuse |
| symlinked ancestor | refuse the candidate (do not follow, do not delete) |
| symlinked descendant | refuse that entry; do not traverse directory links during enumeration |
| missing file | refuse the deletion action; never report it as deleted; never abort the whole sweep solely for absence (existing behaviour at `:148-150` must be preserved for the root) |
| permission failure | refuse; non-zero exit; never fall back to a weaker check |
| change after validation | residual risk, §V-03 |

- **Verdict** `[OBS]`+`[INF]`: the current check is a lexical, non-atomic, prefix comparison used once per file; it is not an identity-based containment invariant, and it is absent from the `rmdir` pass entirely.

### V-03 — Check-then-use risk

- **Actual sequence** `[OBS]`: enumerate (`:83-89`, `rglob` at `:86`) → classify (`:154-156`) → optionally archive (each `zf.write(path…)` opens by path at `:114`) → root check (`:197`) → per-file check (`:203`) → `stat` (`:209`) → `unlink(path)` (`:210`) → separate re-enumeration and `rmdir` (`:216-223`).
- **Windows where the window matters** `[INF]`:
  1. **`is_under` (`:203`) → `unlink` (`:210`)**: a parent directory component replaced by a symlink between the two calls redirects the deletion. The check and the use are separate path resolutions with no held handle binding them.
  2. **`_scan_uploads` (`:86`) → `unlink` (`:210`)**: the widest window; the intervening archive of a large tree (`:112-127`) can take minutes, and the orphan list holds *paths*, not file identities.
  3. **`zf.write(path)` (`:114`) → later deletion**: archived content is read through paths never individually checked; a link swapped in before archiving copies external content into the zip.
  4. **prune re-enumeration (`:217`) → `rmdir` (`:223`)**: the re-enumerated paths are never validated at all, and `except OSError: pass` (`:225-226`) swallows failures, so a partial or wrong-tree prune is silent.
- **Honest conclusion** `[INF]`: no portable path check eliminates this. Only binding the operation to a **held directory handle** does, and that is not portable. Mitigation options and their limits:

| Approach | Availability | Effect | Label |
|---|---|---|---|
| POSIX `dir_fd` + `os.unlink(name, dir_fd=fd)` / `os.rmdir(name, dir_fd=fd)` relative to a held, validated root fd | POSIX only; Python does not support `dir_fd` for `unlink`/`rmdir` on Windows | closes windows 1-2-4 for entries reachable relative to the held fd | `[PLAT]` |
| `os.open(path, O_NOFOLLOW)` before the destructive syscall | POSIX only | refuses a final-component link at use time | `[PLAT]` |
| `os.walk(root, followlinks=False)` + `os.lstat` per entry | portable | removes directory-link traversal and closes window 4 | `[PROP]` |
| re-validate immediately before each single operation, abort the sweep on any mismatch | portable | narrows (does not close) windows 1-2 | `[PROP]` |
- **Residual risk to document, not hide** `[INF]`: on Windows the race cannot be closed by any Python-level path API available to this project; the design must state that explicitly and require an explicit operator acknowledgement for destructive runs on such platforms, or accept and record the residual.
- **Verdict**: plausible risk requiring dynamic evidence for exploitability; the *absence of any binding between check and use* is a confirmed source-level property `[OBS]`.

### V-04 — Capability-check contract

- **Answers to the four sub-questions** `[OBS]`:
  1. **Real capability check?** No — `:66` returns the constant `True`.
  2. **Constant?** Yes.
  3. **Used as a gate intended to stop cleanup?** Yes — `cleanup_orphan_uploads.py:50-51` raises `RuntimeError` when it is falsy, so the author's intent was fail-closed; the constant makes the gate inert.
  4. **What is the property actually needed?** Nothing in `run_sweep` or `_archive_orphans` creates, resolves, or depends on a **relative** symlink `[OBS]` — the sweep only enumerates, zips, unlinks and rmdirs. `[INF]` The gate therefore guards a capability the workflow does not use; it is both unimplemented and unnecessary in its current position.
- **Required contract** (`[PROP]`, §7.5) — three-valued, evaluated at the point of use:

| Result | Required behaviour |
|---|---|
| `SUPPORTED` | continue |
| `UNSUPPORTED` | refuse the sweep; non-zero exit; no deletion |
| `INDETERMINATE` (probe could not run: permissions, read-only temp, unknown platform) | refuse; never treat an indeterminate probe as support |

- **Constraint** `[INF]`: the check must not be performed at import time if it is given a real implementation — import-time I/O would make importing the module environment-dependent, would break `--help`, and would make `test_importing_the_script_does_not_start_the_sweep` (`:101-117`) depend on the host. Design position: since the property is unused, the minimum correct action is to **remove the gate and the stub**, and to reintroduce a real probe only if a future feature needs relative links.
- **Verdict**: confirmed defect (constant stub guarding an unused property, positioned at import time). No live probe was run in this task.

### V-05 — Archive and deletion ordering

- **Current order** `[OBS]`: DB read (`:135`) → existence (`:148`) → scan (`:152`) → classification (`:154`) → dry-run (`:175`) → confirmation (`:183`) → **archive write + verify (`:192-195`, body `:91-127`)** → **root check (`:197`)** → per-file check (`:203`) → `unlink` (`:210`) → unguarded prune (`:216-226`).
- **Ordering defects** `[OBS]`:
  1. The root is validated **after** the archive has already copied file contents out of the tree (`:192` precedes `:197`).
  2. The archive's own containment check (`:102-110`) is the only validation the archive gets, and it compares `archive.resolve().relative_to(root.resolve())` — both sides `resolve()`d, so it inherits the same "resolved vs intended" confusion as V-01.
  3. The prune pass performs destructive `rmdir` with no root or containment check at all.
- **Required ordering** (`[PROP]`, §7.6): validate root → enumerate (no link traversal) → classify → dry-run gate → confirmation → validate archive destination outside root → write archive → verify archive → **re-validate root and each candidate immediately before each destructive operation** → delete one validated candidate at a time → prune only directories that were themselves validated.
- **Required failure behaviour** (`[PROP]`):
  - failed archive creation or verification ⇒ **delete nothing**, non-zero exit (current code already does this: `return 3` at `:195`; preserve); the four existing abort messages are at `:99`, `:107`, `:119`, `:124`;
  - invalid root ⇒ refused **before** any archive or scan work (move `:197` earlier);
  - failed safety check ⇒ never fall back to a weaker check (no such fallback exists today `[OBS]`; the design forbids adding one);
  - dry-run default (`:175-177`) and the explicit `--delete` / `--yes` authorization (`:183-190`, plus argparse at `:242-253`) must remain intact and unweakened — in particular the design must not let `--yes` imply consent to an unvalidated root;
  - exit codes must stay meaningful: `0` success (incl. dry run / nothing to do), `1` refusal or residual orphans (`:190`, `:238`), `2` unreadable DB (`:140`), `3` archive failure (`:195`); new refusals need their own distinct codes (`[PROP]`).
- **Verdict**: confirmed ordering defects (root-after-archive; unguarded prune). Archive-before-**delete** ordering itself is correct and must be preserved.

### V-06 — Regression-test design

Covered in §9 with the required per-case fields. Key observations from the existing suite `[OBS]`:

- The suite is already well-constructed for its scope: dry-run resistance, unreadable-DB abort (`:120-151`), unlinked references (`:154-177`), archive-inside-root refusal (`:180-201`), symlinked-root refusal (`:203-230`), helper reachability (`:236-255`).
- Two tests assert behaviour the current implementation **cannot** produce: `:203-230` expects exit `1` with the target's files intact (the code returns `0` and deletes them `[INF]`), and `:246-255` expects `RuntimeError` from `forbid_symlink_roots` (`:48` cannot raise `[OBS]`). Both would fail on a symlink-capable host — evidence that the suite has not run there.
- Both symlink tests **silently skip** on hosts where `os.symlink` raises (`:210`, `:252`) — no visibility, no CI signal.
- No existing test covers: a symlinked *descendant*, a *directory* symlink during traversal, `..` in a candidate, the prune pass, a candidate outside the root in a real filesystem, capability-unsupported refusal, or the check-then-use window.

## 6. Confirmed defects versus plausible risks

| ID | Finding | Classification | Severity | Evidence |
|---|---|---|---|---|
| D-1 | `forbid_symlink_roots` comparison compares one derivation with itself; refusal unreachable | **Confirmed source-level defect** | High | `[OBS]` `cleanup_path.py:44,48` |
| D-2 | `filesystem_supports_relative_symlinks()` returns a constant; the import-time gate cannot fail closed | **Confirmed source-level defect** | High | `[OBS]` `:66`; `cleanup_orphan_uploads.py:50-51` |
| D-3 | Root validated only at `:197`, after the archive step at `:192-195` | **Confirmed source-level defect** (ordering) | High | `[OBS]` |
| D-4 | Prune pass `rmdir` (`:223`) has no root or containment check; failures swallowed (`:225-226`) | **Confirmed source-level defect** | High | `[OBS]` `:214-226` |
| D-5 | `is_under` is a lexical prefix comparison on `strict=False` resolutions — not an identity-based containment proof; asserts containment for non-existent paths | **Confirmed source-level defect** (invariant weakness) | Medium | `[OBS]` `:26-34` |
| D-6 | No pinned "intended root"; `settings.upload_path` re-read at `:85`, `:132`, `:217` | **Confirmed source-level defect** (design) | Medium | `[OBS]` |
| D-7 | Missing/inaccessible root indistinguishable from a valid one (`strict=False`) | **Confirmed source-level defect** | Medium | `[OBS]` `:44` vs §7.3 |
| D-8 | Symlink tests silently skip instead of reporting capability absence | **Confirmed source-level defect** (test design) | Medium | `[OBS]` `:210`, `:252` |
| P-1 | Check-then-use (TOCTOU) window between validation and `unlink`/`rmdir` is exploitable in a concurrent local process | **Plausible** — needs dynamic evidence | Medium | `[OBS]` sequence; `[INF]` exploitability |
| P-2 | Windows junction / reparse-point detection: `os.path.islink` may not report junctions, so a junction could pass a link check | **Plausible** — needs platform evidence | Medium | `[PLAT]` |
| P-3 | `rmdir` on a directory junction / reparse point behaves differently from POSIX and is swallowed at `:225-226` | **Plausible** — needs platform evidence | Low–Medium | `[PLAT]` |
| P-4 | Archive read (`:114`) occurs before any per-candidate validation, widening exposure of file contents | **Plausible** | Low | `[OBS]` ordering |

Not claimed: exploitability of P-1, any Windows junction outcome, and any statement about the target host's filesystem — all require dynamic evidence not gathered here.

## 7. Proposed minimum corrective design

Design principles satisfied: fail closed; one explicit intended root; symlink handling as a security boundary; honest about races; preserves existing authorization; no database/evaluation changes; observable behavior for every error; minimum separated from optional; platform limits named; no broad refactoring. All of §7 is `[PROP]`.

### 7.1 One intended root, validated once, reused everywhere

`[PROP]` Establish, at the start of `run_sweep`, a single `IntendedRoot` value holding: the configured path, its lexical absolute form (`os.path.abspath`, no filesystem access), and its resolved form (`os.path.realpath`). Pass it to every helper instead of re-reading `settings.upload_path` at `:85`, `:132`, `:217`. Validation refuses unless **all** hold:

1. the configured path is not itself a symlink/reparse point (`os.path.islink` for POSIX/`[PLAT]` Windows; on Windows additionally `stat.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`);
2. `os.path.abspath(configured) == os.path.realpath(configured)` — two **independent** derivations, which is the correction of the D-1 idea;
3. the root exists and is a directory (`os.stat` with `follow_symlinks=False`), so a missing/inaccessible root is a refusal rather than a silent pass (fixes D-7).

### 7.2 `forbid_symlink_roots` — minimum fix (D-1, D-7)

`[PROP]` Keep the name, signature and exception contract (`RuntimeError`) — `test_cleanup_orphan_uploads.py:254` depends on `RuntimeError` whose message matches `"symlink"`. Replace the body with: resolve with `strict=True` inside the existing `try`; raise `RuntimeError` when the path is a link/reparse point or when `abspath != realpath`; keep the `OSError` → `RuntimeError` conversion at `:45-46` for a missing/unresolvable root. Rationale for choosing `islink`+`abspath/realpath` over `os.open(O_NOFOLLOW)`: the question here is a property of the *configured root* — a one-time, operator-controlled check — not of a racing candidate, so a `[PLAT]`-available cheap check is sufficient and keeps the change minimal; `O_NOFOLLOW` belongs to the per-candidate path (§7.4).

### 7.3 `filesystem_supports_relative_symlinks` / its gate (D-2, V-04)

`[PROP]` **Minimum:** delete the import-time gate at `cleanup_orphan_uploads.py:50-51` and the function, because no code in the sweep uses relative symlinks `[OBS]` — a gate guarding an unused capability cannot protect anything, and deleting it removes both the constant and the import-time side effect. **If** the Coordinator prefers to retain the check pending a future need, it must be three-valued (`SUPPORTED`/`UNSUPPORTED`/`INDETERMINATE`), evaluated at the point of use, refusing on anything but `SUPPORTED`, and never called at import. Both variants are stated so the reviewer can choose; the recommendation is removal.

### 7.4 Per-candidate validation used by every destructive operation (D-4, D-5, P-1, P-2)

`[PROP]` Add one helper — conceptually `validate_candidate(root: IntendedRoot, candidate: Path) -> bool` — and call it **immediately before each destructive operation**, replacing the bare `is_under` at `:203` and covering the prune pass at `:223`:

1. reject relative candidates outright (require absolute; resolve any relative input against the intended root, never the CWD);
2. `resolved = os.path.realpath(candidate)`; reject any candidate whose resolved path is not `root.resolved` itself or a descendant of it, measured component-wise via `os.path.commonpath([root_resolved, resolved]) == root_resolved` **and** a `relative_to(root_resolved)` check that rejects any `..` component — two independent formulations, neither of which is a prefix match;
3. reject when `os.path.realpath(candidate) != os.path.abspath(candidate)` for the *parent* chain, i.e. when any ancestor between the root and the candidate is a link/reparse point — this is the "symlinked ancestor ⇒ refuse" rule;
4. `os.lstat(candidate)` and refuse if it is a link/reparse point (the "symlinked descendant ⇒ refuse" rule), using `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` on Windows `[PLAT]`;
5. require `stat.S_ISREG` before deletion and `S_ISDIR` before `rmdir`; a missing candidate ⇒ treat as absent (skip, do not error), never counted as deleted;
6. any `OSError` ⇒ refuse (return False), never fall through to a weaker check.

Justification of the API choice rather than a handle-bound one: `realpath`/`lstat`/`stat` are the only file-identity primitives available on **both** target platforms, and they satisfy invariants 1-6 *at the moment of the call*; they cannot satisfy them *between* calls, which is stated as residual in §7.7 rather than papered over.

### 7.5 Enumeration without link traversal (D-4, P-2)

`[PROP]` Replace the bare `root.rglob("*")` (`:86`, and `:217`) with an explicit walk that does not follow directory links, refusing/skipping reparse points and reporting skipped entries. This is the portable half of the prune fix; it removes link-following from the *enumeration* even where the race in *use* remains.

### 7.6 Ordering (D-3, V-05)

`[PROP]` Reorder `run_sweep` to: validate intended root (§7.1) → DB read (`:135`) → existence → walk (§7.5) → classify → dry-run gate → confirmation → archive destination check (keep `:102-110`, upgraded to the §7.4 primitives) → archive write → archive verify (`:116-125`, keep) → per-candidate validate-then-act loop (§7.4) → prune (validated directories only, deepest first) → verification (`:232-235`). Archive-before-delete stays; root-before-archive is new. Failure behaviour exactly as listed in §5/V-05.

### 7.7 Observable behaviour table (required by §5 principle 7)

| Condition | Exit | Files deleted | Message |
|---|---|---|---|
| root is a symlink/reparse point | new code `4` | none | explicit refusal naming the configured root |
| root missing/unresolvable | `4` | none | explicit refusal |
| candidate outside root | `1` (or dedicated `5`) | none | per-candidate SKIP line |
| candidate is a link/descendant link | `1` (or `5`) | none for that entry | per-candidate SKIP line |
| DB unreadable | `2` | none | existing message (`:138-139`) |
| archive failure/verification failure | `3` | none | existing messages (`:99`,`:107`,`:119`,`:124`) |
| capability unsupported (if retained) | new code | none | explicit refusal |
| permission failure on a candidate | `1` | none for that entry | surfaced, not swallowed |

### 7.8 What the minimum correction does **not** do

`[PROP]` It does not make deletion atomic; it does not cover `cleanup_smoke.py`; it does not add `dir_fd`/`O_NOFOLLOW` binding; it does not change the database, the evaluation runners, `isolation.py`, the archive format, the CLI flags, the dry-run default, the confirmation prompt, or the exit codes `0/1/2/3` meaning.

## 8. Optional improvements (separately authorized, not part of the minimum)

| Option | Benefit | Cost / limit | Label |
|---|---|---|---|
| Handle-bound POSIX deletion (`dir_fd`, `O_NOFOLLOW`, root fd held open) | closes windows 1-2-4 on POSIX | POSIX only; not available on Windows; larger change | `[PLAT]` |
| `--accept-check-then-use-risk` required for destructive runs where `os.supports_dir_fd`/`O_NOFOLLOW` are unavailable | fail-closed by default platform-wide | new operator-facing flag; UI/doc work | `[PROP]` |
| Guard the `cleanup_smoke.py` deletion path (`:61`,`:113`,`:136`) with the same primitives | removes the adjacent unguarded path | separate ownership (P19) and separate authorization | `[PROP]` |
| Windows case/alias normalization inside containment (8.3 names, trailing dots, UNC vs mapped drive) | fewer false accepts/refuses | needs platform-specific evidence | `[PLAT]` |
| Structured report (`--json`) of skipped/refused candidates and exit-code table | auditability of partial runs | additive | `[PROP]` |
| Make the archive destination `strict=False` resolution explicit / require an existing parent | removes a lexical-resolution ambiguity (`:103`) | minor | `[PROP]` |

## 9. Regression-test matrix (specified, **not executed**)

No test below was run. "Expected" means the behaviour the design requires, not an observed result. All rows are `[PROP]`.

| # | Test name | Preconditions | Setup | Action | Expected result | Expected FS state after | Platform-dependent | Skip reporting |
|---|---|---|---|---|---|---|---|---|
| T-01 | `test_normal_directory_root_sweeps_orphans` | symlink support irrelevant | tmp root with referenced + orphan files; faked `_referenced_keys` | `run_sweep(delete=True, assume_yes=True)` | exit 0; orphan removed | referenced file present, orphan absent | No | n/a |
| T-02 | `test_symlinked_root_is_refused_before_archive` | symlink creation available | tmp real root; `symlink_root -> real_root`; archive path outside | `run_sweep(delete=True, assume_yes=True, archive=archive)` | exit 4 (or documented refusal code); **no archive written**; message names the root | all real files present; archive absent | Yes (symlink capability) | `pytest.skip(reason=...)` with reason + `-rs`, plus a POSIX guard test asserting symlink support so the suite cannot silently degrade |
| T-03 | `test_forbid_symlink_roots_rejects_symlinked_root` | symlink creation available | as existing `:246-255` | call helper | `RuntimeError` matching `"symlink"` | unchanged | Yes | as T-02 |
| T-04 | `test_symlinked_descendant_file_is_skipped` | symlink creation available | root with `real/x.pdf`, `link.pdf -> ../outside/y.pdf` | `run_sweep(delete=True, assume_yes=True)` | link entry skipped; `y.pdf` untouched | `y.pdf` present; link untouched or removed-as-link only if designed so | Yes | as T-02 |
| T-05 | `test_symlinked_descendant_directory_is_not_traversed` | symlink creation available | root with `linkdir -> ../outside` containing orphans | `run_sweep(delete=True, assume_yes=True)` | traversal stops at the link | outside files intact | Yes | as T-02 |
| T-06 | `test_candidate_outside_root_is_refused` | real filesystem (no links) | root + sibling file; force an entry outside root into the candidate list via the walk seam | delete loop | candidate skipped, non-zero if residual | outside file present | No | n/a |
| T-07 | `test_dotdot_candidate_is_refused` | none | candidate expressed with `..` that resolves inside vs outside | `validate_candidate` | inside ⇒ True; outside ⇒ False | unchanged | No | n/a |
| T-08 | `test_missing_root_is_not_a_deletion_path` | none | point `upload_path` at a non-existent path (bypassing the `mkdir` in `config.py:140-143` via monkeypatch) | `run_sweep(delete=True, assume_yes=True)` | defined outcome, **no** deletion attempt, documented exit | nothing created/deleted | No | n/a |
| T-09 | `test_inaccessible_root_is_refused` | POSIX permissions (skip on Windows) | chmod root to remove read/execute | `run_sweep` | refusal, non-zero, no fallback | unchanged | Yes (POSIX) | explicit `skip` on Windows with reason |
| T-10 | `test_root_replaced_between_validation_and_use` | injection seam | monkeypatch the pre-delete validation to swap the root to a symlink before the first `unlink` | delete loop | sweep aborts; nothing outside root deleted | outside files intact | No (if seam exists) / Yes (if real race) | report whether the seam or a real race was used |
| T-11 | `test_unsupported_capability_refuses` (only if V-04 variant B is chosen) | stub the probe to `UNSUPPORTED` | monkeypatch probe | `run_sweep(delete=True, assume_yes=True)` | refusal, no deletion | unchanged | No | n/a; becomes obsolete under the recommended removal variant |
| T-12 | `test_archive_inside_root_is_rejected` | existing `:180-201` | as existing | archive inside root | exit 3; archive absent | unchanged | No | n/a |
| T-13 | `test_archive_creation_failure_deletes_nothing` | none | make archive destination unwritable / pre-existing | `run_sweep(delete=True, assume_yes=True, archive=...)` | exit 3; no deletion | all files present | Yes (permission semantics) | explicit reason where permissions cannot be simulated |
| T-14 | `test_archive_verification_failure_deletes_nothing` | none | inject a corrupt archive (monkeypatch verification) | as above | exit 3; no deletion | all files present | No | n/a |
| T-15 | `test_unreadable_database_aborts` | existing `:120-151` | as existing | `run_sweep(delete=True, assume_yes=True)` | exit 2 | unchanged | No | n/a |
| T-16 | `test_dry_run_deletes_nothing` | existing dry-run path `:175-177` | real tmp root | `run_sweep(delete=False, ...)` | exit 0; report only | unchanged | No | n/a |
| T-17 | `test_prune_only_removes_validated_empty_directories` | none | root with empty nested dirs and a link dir | `run_sweep(delete=True, assume_yes=True)` | empty real dirs pruned; link dir not `rmdir`d | outside/real state as specified | Partly (link) | as T-02 |
| T-18 | `test_symlink_support_is_available_on_posix` | POSIX | none | `os.symlink` in tmp | succeeds | — | Yes | must **fail**, not skip, on POSIX — prevents silent capability degradation |
| T-19 | `test_is_under_containment_cases` (extend `:236-244`) | none | table of sibling/prefix-confusion paths (`/tmp/root` vs `/tmp/root-sibling`) | `validate_candidate` | outside ⇒ False; direct child ⇒ True | unchanged | No | n/a |
| T-20 | `test_exit_codes_are_distinct` | none | drive each refusal | `main()`/`run_sweep` | each documented code observed | unchanged | No | n/a |

Skip policy `[PROP]`: every symlink/permission-dependent case must skip **with a reason string** and must be visible (`-rs`, or a CI job that fails when the count of skipped security tests exceeds zero on POSIX). T-18 exists specifically so a POSIX runner cannot pass while all link coverage is skipped.

## 10. Platform assumptions and unresolved filesystem guarantees

| # | Assumption | Status |
|---|---|---|
| A-1 | `Path.resolve()` / `os.path.realpath()` is idempotent, so the `:48` comparison can never be true | `[OBS]` source shape + language semantics; not executed |
| A-2 | `os.path.islink()` returns `True` for symbolic links on Windows | `[PLAT]` |
| A-3 | `os.path.islink()` is **not reliable for NTFS junctions**; reparse-point detection needs `stat.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` | `[PLAT]` — must be verified on the target Windows version before relying on §7.4(4) |
| A-4 | `dir_fd`-relative `unlink`/`rmdir` and `O_NOFOLLOW` are unavailable on Windows, so the race cannot be closed there | `[PLAT]` |
| A-5 | Creating symlinks on Windows needs privilege/developer mode, which is why the existing tests skip; junctions may be creatable without it | `[PLAT]` |
| A-6 | Case-insensitive and 8.3/short-name aliasing on Windows is not normalized by the proposed containment | `[PLAT]` — affects false accepts/refuses |
| A-7 | `config.py:140-143` creates the root on read, so "root exists" is not independent evidence of operator intent | `[OBS]` |

**Unresolved guarantees** (explicitly not established): that deletion cannot escape the intended tree under a concurrent adversary (P-1); that junctions are refused on Windows (A-3); that the prune pass behaves on junction trees (P-3); that any of the proposed checks work as designed (all `[PROP]`, unexecuted).

## 11. Implementation sequence and acceptance criteria

Sequence `[PROP]`:
1. Pin the intended root (§7.1) and thread it through `_scan_uploads` / `run_sweep` / prune — no behavior change yet.
2. Fix `forbid_symlink_roots` (§7.2) and move its call before the archive/scan (§7.6).
3. Add `validate_candidate` (§7.4) and use it before `unlink` and before `rmdir`; replace the walk (§7.5).
4. Decide V-04 (§7.3): remove the gate/stub (recommended) or make it three-valued at the point of use.
5. Add the §9 regression tests; keep the existing `RuntimeError`/exit-code contracts so the current tests remain meaningful.
6. Run the unit safety suite on a symlink-capable POSIX host and record results (§9 skip policy).

Acceptance criteria `[PROP]`: both superseded tests (`:203-230`, `:246-255`) pass or are rewritten only with the Coordinator's approval and only to a *stricter* assertion; no new fallback path exists; dry-run default, `--delete`/`--yes`, archive-before-delete and exit codes `0/1/2/3` are unchanged in meaning; every new refusal is observable and tested; no database, migration, evaluation-runner or `isolation.py` file is touched; a recorded test run exists before any claim that U-03 is closed.

## 12. Git preservation evidence

- HEAD before this task: `6baaa2a0773df66e5fb26814afbe67647fb43435` (`git rev-parse HEAD`).
- Baseline snapshot `%TEMP%/step16v-status-before.txt` = `git status --porcelain=v1 --untracked-files=all`, sorted, **1,147 rows** (already contains the Step 1.6U report and every pre-existing working-tree change). Prior `step16r/s/u-*` snapshots were not overwritten.
- Working-tree changes strictly preserved: no file was edited, moved, deleted, reset, stashed, reverted or cleaned.
- Post-report comparison: §16.

## 13. Decision — implementation authorization

**AUTHORIZED, with conditions, for a bounded non-destructive source change:** the minimum corrective design in §7 (plus its regression tests) may be implemented, because D-1/D-2 are confirmed fail-open defects, the design preserves every existing authorization gate, and it touches no database or evaluation file. **Conditions:** (a) a SECURITY_AGENT-class review of the implemented diff is required before the change is described as closing U-03; (b) the existing `RuntimeError`/exit-code contracts must be preserved; (c) no optional item from §8 may be folded in without its own authorization. This authorization is for **source edits and unit tests only** — it does not authorize running the sweep.

## 14. Decision — destructive cleanup testing

**NO-GO.** No destructive run is authorized: the confirmed defects mean a symlinked or raced root can delete the wrong tree, no test result has been recorded for this path on any host, and the check-then-use residual (P-1) is documented rather than closed. Verifying the fix requires a symlink-capable POSIX host running the unit suite against tmp directories — not the production `uploads/` tree, and not `--delete` against any real root.

## 15. Recommended next bounded task

**Bounded implementation task:** apply §7.1-§7.6 to `backend/scripts/cleanup_path.py` and `backend/scripts/cleanup_orphan_uploads.py`, add the §9 tests (T-01…T-20 minus the variant-B case), preserve the existing exception/exit-code contracts, and record a unit-suite run on a symlink-capable POSIX host. Excluded: `cleanup_smoke.py`, `isolation.py`, the database, and every destructive invocation.

## 16. Post-report status comparison

- `git status --porcelain=v1 --untracked-files=all` re-sorted and compared against the 1,147-row baseline: **exactly one added path** — `?? backend/architecture/STEP1_6V_FILESYSTEM_GUARD_REMEDIATION_DESIGN_2026-10-13.md` — **0 removed**, **0 changed**.
- HEAD final: `6baaa2a0773df66e5fb26814afbe67647fb43435` (**unchanged**).

---

**Restated:** this report is a provisional coordinator design. The named specialists did not execute, the design has not been independently challenged, and nothing here was executed. **The filesystem is not established as safe by this document.** Verification method: static source reading, ripgrep searches and line-anchored inspection only — no test, import, cleanup, deletion, database or migration operation was performed, and no `.env`, credential or secret was read.
