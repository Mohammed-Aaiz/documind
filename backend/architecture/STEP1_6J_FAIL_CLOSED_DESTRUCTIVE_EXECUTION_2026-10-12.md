# STEP 1.6J — Fail-Closed Destructive Execution

Date: 2026-10-12 (session date; the Step 1.6I report is dated 2026-10-11)
Verdict: **PARTIALLY COMPLETE.** Every destructive path in the integration fixture and in the nine evaluation runners now refuses by default. Two cleanup scripts remain unresolved and are documented as a separate workstream, as the task directs. PostgreSQL verification remains **NO-GO**.

## 1. Agents

- The runtime offers no specialist-agent dispatch. No specialist agent was invoked and no specialist output exists.
- The Coordinator performed every role: authorization model, database-identity review, runner enforcement, test authorship, and verification.
- **Unfulfilled, and not independently performed:** SECURITY_AGENT's independent review of the model, DATABASE_AGENT's independent identity review, BACKEND_AGENT's independent enforcement review, TEST_AGENT's independent test review, and VERIFIER's independent review. No independent verification is claimed.

## 2. Baseline

- Initial HEAD: `6baaa2a0773df66e5fb26814afbe67647fb43435`
- Initial `git status --short`: 384 entries. The full path listing was saved to `/tmp/s16j_baseline_status.txt` before any edit.
- Final `git status --short`: 384 entries, saved to `/tmp/s16j_final_status.txt`.
- Path-level comparison: `diff` of the two listings returned no differences (exit 0).
- **Limitation:** a status listing shows which paths are modified or untracked, not what changed inside them. Every file this step edited was already inside a modified or untracked path, so the path comparison cannot detect these edits. The changes are established by reading the files back and by the test runs below.
- No staging, commit, push, reset, stash, clean, or revert was performed.

## 3. The flaw in Step 1.6I

`DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE` was an operator declaration of a database name. Destruction was permitted when that name equalled the target's. The flaw:

- A declaration is not evidence that a database is disposable. An operator can name a database that holds real data.
- The fixture's `_drop_database` ran before `_create_database`, so `DROP DATABASE … WITH (FORCE)` destroyed any pre-existing database with that name once the declaration matched.
- The evaluation runners destroyed rows on any target whose name matched the declaration. Each runner's validity guard was the only other check.
- Step 1.6I itself stated that a name, a valid URL, the presence of a variable, or a target that differs from the application must not authorize destruction. The name-based model violated that requirement.

## 4. Authorization model

The six questions are kept separate. None implies another.

| # | Question | Mechanism | Sufficient for destruction? |
| --- | --- | --- | --- |
| 1 | URL validity | `assert_safe_evaluation_target` (scheme, parsing, override parameters, malformed port) | No |
| 2 | Application-database isolation | same guard, database name (case-insensitive) | No |
| 3 | Target identity | `database_identity`; literal `assert_engine_matches_target` | No |
| 4 | Explicit operator intent | recorded in documentation; no longer accepted as authority | No |
| 5 | Enforced authorization to destroy | `assert_disposal_authorized(..., proof=...)` requiring a `DisposalProof` | **Yes, when a proof is present** |
| 6 | Evidence that the target is disposable | a proof that **this run created the database** (`record_created_database`, after a successful `CREATE DATABASE`) | Yes, for databases this run created |

Rules enforced by `evaluation/isolation.py`:

- Only `record_created_database()` issues a `DisposalProof`. Its issuer is a private sentinel, so a proof built elsewhere (`DisposalProof(identity)`) is refused.
- A proof covers exactly one identity (host, port, database). A changed target is refused.
- The application's database name is refused even with a proof.
- With no proof, every target is refused. Environment variables, names, URLs, and the difference from the application are ignored as authority.

Rationale: a database this process created cannot hold pre-existing data, so destroying it cannot destroy anyone's data. A database that already existed carries no evidence of being disposable, and nothing in this repository can establish that. So destruction of pre-existing databases is blocked by default.

**Whether destructive provisioning remains blocked:** yes, for every pre-existing database. Provisioning now refuses an existing name and drops only the database it created.

**Interpretation to confirm:** provisioning's create step is non-destructive, so it is not gated by a proof. Its fail-closed behaviour is the refusal to proceed when the name already exists. The Coordinator should confirm whether the create step itself must also refuse.

## 5. Destructive path inventory and final classification

Classifications: **AUTHORIZED** (enforced by a proof issued in this run), **SAFELY BLOCKED** (refuses by default; no path to proceed without new architecture), **UNRESOLVED** (no enforcement; documented, not changed in this task).

| Path | Operation | Gate | Classification |
| --- | --- | --- | --- |
| `tests/fixtures/integration_db.py` `provisioned_integration_database()` → `database_exists` refusal → `_create_database` | create (non-destructive) of a name that does not exist | URL validation; refuses if the name exists | **SAFELY BLOCKED** for any existing database; creation of a new name proceeds |
| same, `finally` → `_drop_database(dsn, proof)` | drop of the database this run created | `assert_disposal_authorized(dsn, proof=proof)`, proof issued at creation | **AUTHORIZED** (proof of creation) |
| `_drop_database` with any other or missing proof | drop of a pre-existing database | refused before any SQL | **SAFELY BLOCKED** |
| `isolated_database` pytest fixture | provisioning as above | as above | same as provisioning |
| `test_real_e2e_validation.py` `__main__` `--use-provisioned-database` | row deletes in an existing target | `assert_authorized_destructive_target()` always refuses (no proof on this path) | **SAFELY BLOCKED** |
| `test_real_e2e_validation.py` `__main__` default path | provisioning as above, then row deletes in the created database | as above | provisioning: as above; row deletes: **AUTHORIZED** (created-by-run database) |
| `run_phase3d_evaluation.py` | row deletes (owned users) | `assert_disposal_authorized` without proof | **SAFELY BLOCKED** |
| `run_phase3d_upload_integration.py` | row deletes, including raw `text("DELETE …")` | same | **SAFELY BLOCKED** |
| `run_phase3e_integration.py` | row deletes (owned) | same | **SAFELY BLOCKED** |
| `run_phase3e_validation.py` | row deletes (owned) | same | **SAFELY BLOCKED** (DB part) |
| `run_phase3f_evaluation.py` | row deletes (owned) | same | **SAFELY BLOCKED** |
| `run_phase4b_evaluation.py` | row deletes (owned) | same | **SAFELY BLOCKED** |
| `run_dual_path_ablation.py` | row deletes (eval user) | same | **SAFELY BLOCKED** |
| `run_table_evidence_measurement.py` | ingest then row deletes | `_authorize_disposal` without proof, after `_resolve_database_url()` | **SAFELY BLOCKED** |
| `run_structure_element_measurement.py` | row deletes (eval users) | `assert_disposal_authorized` in `guard_evaluation_target` | **SAFELY BLOCKED** |
| `run_structure_rrf_calibration.py` | row deletes (eval users) | via `guard_evaluation_target` | **SAFELY BLOCKED** |
| `run_structure_confirmation.py` | row deletes (eval users) | via `guard_evaluation_target` | **SAFELY BLOCKED** |
| `scripts/cleanup_smoke.py` | deletes a named application user's rows, uploaded files, and user directory against the **application** database; no gate | none (operator tool, interactive `[y/N]`) | **UNRESOLVED.** Not gated, and out of scope to modify here. Separate workstream |
| `scripts/cleanup_orphan_uploads.py` | filesystem deletes of orphaned uploads | `--delete` flag, dry run by default, path containment | **UNRESOLVED** (filesystem; separate workstream) |
| `run_phase3e_validation.py` temp-file `os.unlink` | removes the harness's own temp files | none | **UNRESOLVED-low** |
| `storage/file_store.py` `delete_upload` | application runtime file deletion | application policy | Out of scope |

**Operational consequence:** every evaluation runner now refuses before any database work. None can run until a proof-issuing path exists for its target. That is the intended fail-closed behaviour, and it is recorded as a limitation, not a defect.

## 6. Files changed in this step

| File | Owner | Change |
| --- | --- | --- |
| `backend/evaluation/isolation.py` | EVALUATION_AGENT | Removed the name-based variable, `authorized_disposal_name`, and the name-based rules. Added `DisposalProof` (frozen dataclass with a private issuer), `record_created_database()`, and a fail-closed `assert_disposal_authorized(..., proof=None)`. Added `dataclasses` import. Updated the header comment. The validity guard and `assert_engine_matches_target` are unchanged |
| `backend/tests/fixtures/integration_db.py` | TEST_AGENT | Imports `record_created_database`. Authorization wrapper accepts a proof. `assert_authorized_destructive_target()` always refuses. `_drop_database(dsn, proof)` is proof-gated and reads the DSN passed in, not the environment. `_create_database` refuses the empty name and the application name. `provisioned_integration_database` refuses an existing name, creates, issues a proof, and drops only in `finally` with that proof |
| `backend/tests/unit/evaluation/test_structure_runner_guard_order.py` | TEST_AGENT | The harness replaces the disposal check with a recording stub, because these tests check guard order and engine binding. The refusal test restores the real check and asserts the new refusal message |
| `backend/tests/unit/evaluation/test_phase3_runner_target_order.py` | TEST_AGENT | The fixture-order test now checks validation → existence refusal → creation |
| `backend/tests/unit/evaluation/test_disposable_database_authorization.py` | TEST_AGENT | Rewritten for the proof model (section 7) |
| `backend/tests/unit/evaluation/test_disposal_authorization_contract.py` | TEST_AGENT | Rewritten for the proof model (section 7) |
| `backend/architecture/STEP1_6J_…md` | Coordinator | This report |

**Not changed:** the nine evaluation runners' source. They already call the central check after their validity guard, and the check now refuses without a proof. `test_real_e2e_validation.py` is unchanged; its `__main__` call now refuses through the same function. The two cleanup scripts are unchanged, as the task directs.

## 7. Tests

All database-free. I/O is patched to fail: `psql_value`, `postgres_available`, `database_exists`, `_create_database`, `_drop_database`, `alembic_head`, `migrate_to_head`, and `subprocess.run`. No destructive primitive and no provisioning context manager is called. Provisioning and drop order are checked from source text.

### Commands and results

Focused set (new and updated files plus the existing guard-order files):

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_phase3_runner_target_order.py tests/unit/evaluation/test_runner_pre_engine_init.py tests/unit/evaluation/test_isolation_guard_identity.py tests/unit/evaluation/test_structure_runner_guard_order.py -p no:cacheprovider
→ 209 passed in 2.12s   (exit 0)
```

Cleanup-scope and report-output files, rerun because `isolation.py` changed:

```
cd backend && ./venv/Scripts/python.exe -m pytest -q tests/unit/evaluation/test_phase3d_cleanup_scope.py tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py tests/unit/evaluation/test_runner_report_output.py -p no:cacheprovider
→ 123 passed, 1 warning in 22.75s   (exit 0)
```

The warning is the pre-existing `pytest-asyncio` deprecation notice. It is unrelated to this change.

Retired-name check:

```
grep -rln "DISPOSAL_AUTHORIZATION_ENV|authorized_disposal_name|DOCUMIND_INTEGRATION_DISPOSABLE_DATABASE" --include=*.py . (excluding venv)
→ three test files only, each asserting the retired name has no effect
```

### Coverage, mapped to the required tests

- Authorization-name variable set, no proof: refused (`test_retired_variable_naming_the_target_does_not_authorize`, `test_the_retired_variable_naming_the_target_has_no_effect`).
- Different target, unauthorized: refused (`test_different_target_is_not_authorization_without_a_proof`, `test_a_different_target_is_not_authorization`).
- Valid URL is not authorization: refused (`test_valid_url_alone_is_not_authorization`).
- Missing, empty, whitespace, malformed, unsupported, or override-carrying URL: refused safely (parametrized).
- Application database rejected, including with a proof and under a host alias.
- Authorization cannot be bypassed by configuration after validation: the check reads the DSN passed in, not the environment (`test_changing_the_environment_after_a_proof_cannot_redirect_the_destruction`, `test_changing_the_environment_after_issue_does_not_alter_the_decision`).
- Forged proof refused; proof for one identity does not cover another.
- Provisioning refuses an existing name before creating, and drops only in `finally` with the proof it issued (source order).
- Drop gate precedes the `DROP` statement; create never drops (source order).
- `__main__` destructive path refuses without a proof, and uses the gate (behavioural and source).
- All nine runners keep guard order: validity guard before the disposal call. No runner passes, constructs, or issues a proof (`test_no_runner_can_pass_a_proof_it_did_not_create`). The shared guard authorizes after validity and before the database is bound.
- Fixture and central contract refuse identically without a proof.

### Limits of this evidence

These are source-level and mocked tests. They show that the refusals occur as specified, and they do not show runtime database behaviour. The mocked I/O prevents connection; it does not prove that a real server would behave the same way.

## 8. Checks intentionally not run

- **NOT RUN:** the provisioning context manager, `_create_database`, `_drop_database`, `isolated_database`, and `alembic`.
- **NOT RUN:** every evaluation runner's `main()`, and `run_full_validation`.
- **NOT RUN:** `test_real_e2e_validation.py` (pytest and `__main__`), integration tests, and end-to-end tests.
- **NOT RUN:** `scripts/cleanup_smoke.py`, `scripts/cleanup_orphan_uploads.py`, `scripts/setup_db.py`, and migrations.
- **NOT RUN:** `test_legacy_runner_isolation.py` (it imports `main` at line 162) and `test_evaluation_isolation.py` (not established as database-free).
- **NOT RUN:** linters and type checkers.
- **NOT PERFORMED:** any database connection, including `postgres_available()`. No `.env` file was read.

### Compile

```
cd backend && ./venv/Scripts/python.exe -m py_compile evaluation/isolation.py tests/fixtures/integration_db.py tests/integration/rag/test_real_e2e_validation.py tests/unit/evaluation/test_disposable_database_authorization.py tests/unit/evaluation/test_disposal_authorization_contract.py tests/unit/evaluation/test_structure_runner_guard_order.py tests/unit/evaluation/test_phase3_runner_target_order.py
→ COMPILE_EXIT=0
```

## 9. Remaining architecture decisions and risks

1. **No proof path exists for runners.** Every runner is now blocked. Re-enabling one requires a new architecture: for example, an approved, provisioned disposable database that this run creates as the runner's own target. That decision belongs to the Coordinator.
2. **Provisioning's create step** is not gated by a proof. The Coordinator should confirm this interpretation, or require a proof for creation as well.
3. **`cleanup_smoke.py`** is an unresolved, ungated destructive path against the application database. It is out of scope for this task and needs a separate decision. `cleanup_orphan_uploads.py` is unresolved for the same reason on the filesystem.
4. **In-process forgery.** `DisposalProof` is a private-sentinel object, not a security boundary. Any code in the same process can construct a proof by calling `record_created_database()` directly. The guard protects against accidental and configuration-driven destruction, not against deliberate code.
5. **Creation race.** Between `database_exists(name)` and `CREATE DATABASE`, another actor could create the name, in which case `CREATE` fails and nothing is destroyed. After a successful `CREATE`, another actor could connect to the database before the `finally` drop. `WITH (FORCE)` terminates such connections, but the fixture does not coordinate with other actors.
6. **Same-server rule.** The fixture requires the target to be on the application's host and port. The runners' contract does not. This divergence from Step 1.6I is unchanged.
7. **Time-of-check versus time-of-use.** The proof is checked at each drop. The runners' deletes follow a check without a re-check, which is a residual gap.
8. **Created-database drop.** A database this run creates is dropped at the end. If the process is killed, the `finally` does not run and the database remains. This is a leftover-data risk, not a destruction risk.

## 9a. Final classification summary

- **AUTHORIZED:** drop of a database this run created, under a proof issued at creation; row deletes in that created database.
- **SAFELY BLOCKED:** drop of any pre-existing database; provisioning when the name exists; the `__main__` existing-target path; all nine evaluation runners and the shared-guard runners.
- **UNRESOLVED:** `cleanup_smoke.py`; `cleanup_orphan_uploads.py`; `run_phase3e_validation.py` temp-file unlinks.

## 10. Protected-artifact preservation

No file under `backend/models/documind-qa/**`, `backend/venv/**` (executed only), `backend/phases/phase4f_gpu/**`, `backend/uploads/**`, `.env`, `backend/.env`, `dist/`, or `node_modules/` was written. No frozen benchmark, expected output, model weight, or evaluation algorithm was touched. Existing validity and engine-identity checks were not weakened: `assert_safe_evaluation_target` and `assert_engine_matches_target` are unchanged.

## 11. Verdict

**PARTIALLY COMPLETE.** The destructive database paths in the fixture and the evaluation runners are protected by an enforced proof model and are blocked by default. The unresolved items are the two cleanup scripts and the filesystem paths, which the task directs to a separate workstream. Independent review is unfulfilled (section 1). PostgreSQL verification remains **NO-GO**.
