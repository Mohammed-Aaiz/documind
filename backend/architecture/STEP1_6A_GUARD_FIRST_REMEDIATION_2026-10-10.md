# Step 1.6A — Guard-First Remediation for Three Structure Runners

STATUS: BLOCKED

Date: 2026-10-10
Plan reference: `backend/architecture/STEP1_5_EVALUATION_SAFETY_P0_REMEDIATION_PLAN_2026-10-09.md`

## 1. Scope and starting repository state

- Starting HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`
- Starting working tree: already dirty before this task (1,115 entries in `git status --porcelain`, including the prior Step 1.5 report). A baseline was saved to `/tmp/step16a_baseline_status.txt` and file hashes to `/tmp/step16a_hashes.txt` (outside the repository).
- Target runners (confirmed by path):
  - `backend/evaluation/experiments/run_structure_rrf_calibration.py`
  - `backend/evaluation/experiments/run_structure_element_measurement.py`
  - `backend/evaluation/experiments/run_structure_confirmation.py`
- Central guard: `backend/evaluation/isolation.py` (`assert_safe_evaluation_target`).

## 2. Why the work stopped

The task requires the central guard to reject unsafe or ambiguous targets before engine creation, and says to stop and report if it cannot. The guard cannot. Its identity check compares `(host, port, database)` literally, so an alias of the application database passes as "different".

### Evidence (VERIFIED BY TEST, pure string inspection, no connection)

A probe called `assert_safe_evaluation_target` with `application_url = postgresql+asyncpg://u:p@localhost:5432/documind`. No connection was made, no `.env` was read, and no runner was executed.

| Candidate target | Result | Actually the same database? |
|---|---|---|
| `postgresql+asyncpg://u:p@127.0.0.1:5432/documind` | ACCEPTED | Yes (same server, same database name) |
| `postgresql+asyncpg://u:p@localhost/documind` | ACCEPTED | Yes (default port 5432) |
| `postgresql+asyncpg://u:p@LOCALHOST:5432/documind` | REJECTED | Yes (only rejected because `urlsplit` lowercases the host) |

The guard therefore accepts the application database under a different host spelling or an omitted default port. It is not a reliable guarantee, so per the task it cannot be relied on as the isolation control.

Reproduction: `cd backend && .env/Scripts/python.exe -c "..."` against `evaluation.isolation` with the three candidate DSNs above. The probe used only the stdlib module `evaluation.isolation`.

## 3. Original unsafe import paths (VERIFIED FROM SOURCE)

- `run_structure_rrf_calibration.py` line 69: `from storage.database import async_session, engine`, at module scope. Line 71 imports `run_structure_element_measurement`, which also imports `storage.database` at module scope.
- `run_structure_element_measurement.py` line 88: `from storage.database import async_session, engine`, at module scope.
- `run_structure_confirmation.py` line 75: `from storage.database import async_session, engine`, at module scope. Lines 77–78 import the two runners above.
- None of the three files imports or calls `assert_safe_evaluation_target` or any other part of `evaluation.isolation`.

`storage/database.py` builds the global engine at import time from `settings.database_url`.

## 4. Changes made

None. No runner, test, or other repository file was edited. Blocking on the guard came before any runner edit, so no partial edits exist.

## 5. Guard-ordering evidence

Not established. Because the guard is not called in any of the three runners, the required ordering cannot yet be enforced. The source facts in §3 are what remains to be fixed.

## 6. Tests added

None. The required tests would need the guard to be trustworthy first. Writing guard-ordering tests on top of an unreliable guard would have certified the wrong property.

## 7. Static checks

- Source inspection (VERIFIED FROM SOURCE): the import locations in §3.
- Probe in §2 (VERIFIED BY TEST, pure string, no database).
- No compilation or `git diff --check` was run as a gate, because no code changed.

## 8. Database connection

No database connection was attempted. The probe in §2 only evaluated strings.

## 9. Runner execution

No evaluation runner, migration, cleanup function, integration test, or end-to-end test was executed.

## 10. Protected artifact preservation

- Benchmark files and model weights were not touched.
- No tracked file was modified by this task.
- The only file created is this report.
- Git HEAD should remain `6baaa2a0773df66e5fb26814afbe67647fb43435`. Pre-existing working-tree changes were not restored, reset, stashed, or cleaned.

## 11. Required fix before 1.6A can proceed

A follow-up task is needed to make the central guard reject aliases. It must be owned by the agent that owns `evaluation/isolation.py`, and must be approved in advance, since that file is outside this task's listed scope. Options:

1. Normalize the identity before comparing. Map `localhost`, `127.0.0.1`, and `::1` to one canonical loopback form, and fill the default port (5432) when none is given. Keep the current fail-closed behaviour for empty host or database.
2. Stricter alternative: require that the target's database name differs from the application's database name, regardless of host. This is conservative and removes the host-alias problem, but also rejects a legitimate same-name database on another server. It needs an operator decision.

After the guard is fixed and tested with the alias table above, the runner work in §4 of the original task can proceed. Unit tests for the guard must use the pure-string probe only.

## 12. Remaining limitations and follow-ups

- VERIFIED BY TEST: alias bypass of the central guard (§2).
- VERIFIED FROM SOURCE: three runners import `storage.database` at module scope and never call the guard (§3).
- NOT VERIFIED: runtime behaviour. The runners were not executed, and no database was contacted.
- Decision needed from the operator: option 1 or option 2 in §11.
- Harness identity and cleanup-ownership remediation remain separate items, as the plan says.

## 13. Git preservation

Confirmed at the end of this run:
- HEAD is `6baaa2a0773df66e5fb26814afbe67647fb43435` (unchanged).
- `git status` differs from the baseline only by the new report (`?? backend/architecture/STEP1_6A_GUARD_FIRST_REMEDIATION_2026-10-10.md`).
- MD5 hashes of the three runners and `isolation.py` match the baseline.
- `git diff --check` exited 2 with CRLF trailing-whitespace warnings in `DOCUMIND_PROJECT_CONTEXT.md`, a file modified before this task. This task did not cause them and did not touch that file. The check is therefore not a clean pass for the working tree.
- The report file is the only intended change.
