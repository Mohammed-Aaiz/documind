# Step 0.7 — Phase 3D Destructive Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent; the specialist roles in the task are review
*templates*, not separate runtime agents — no other agent was invoked, and none is claimed).
**Scope:** remove the unscoped `DELETE FROM document_chunks` from
`backend/evaluation/experiments/run_phase3d_upload_integration.py` and replace it with a
demonstrably scoped cleanup.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (finding **F-3**),
`STEP0_6` remediation (the five legacy runners).

---

## 1. Original failure mode

Before this change the harness ended a run with:

```python
# --- cleanup -------------------------------------------------------
await db.execute(text("DELETE FROM reliability_logs WHERE user_id = :u"), {"u": str(user_id)})
await db.execute(text("DELETE FROM document_chunks"))            # ← unscoped
await db.execute(text("DELETE FROM documents WHERE user_id = :u"), {"u": str(user_id)})
await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
await db.commit()
```

(pre-change line 553; the surrounding lines were 552–557, and the same statement is described in the
module docstring at old line 37 and recorded in the run manifest at old line 604.)

**Failure mode.** `DELETE FROM document_chunks` carries no predicate: it removes **every row of
`document_chunks` in whatever database the harness targets** — every owner, every document, every
chunk, including rows created by other research runs that share the same isolated database (the
project's operator workflow points every isolated runner at one shared
`DOCUMIND_INTEGRATION_DATABASE_URL`, and `tests/fixtures/integration_db.py` re-uses the same
database). The neighbouring statements were already scoped to the run's own user, so this one
statement was an isolated outlier, not a protocol requirement.

**Why database isolation alone did not mitigate it.** The Step 0 guard
(`evaluation/isolation.py::assert_safe_evaluation_target`) proves the target is *not the application
database*. It cannot prove the target is *empty* or *exclusively yours*. The unscoped delete was
therefore still capable of destroying another experiment's evidence — Evaluation-contamination
severity, not application-data severity.

**Severity per the Step 0.5 rubric:** High (F-3) — a credible path to corrupting evaluation
evidence. Verified by source inspection (the guard genuinely prevents the application database from
being reached, so it was never Critical in practice).

---

## 2. Mandatory initial inspection (what was read, and what it established)

| Question | Where it was answered |
|---|---|
| Where is the statement, and what else does the cleanup do? | `run_phase3d_upload_integration.py` cleanup block (pre-change L549–557), read in full |
| Who are the harness's rows attached to? | `main()`: one `User` created at L209–218 (`user_id = user.id`, a `uuid.UUID`, never reassigned — verified by grep: only one assignment), logs in as that user (L220–223), and performs **all** ingestion through the real HTTP route `POST /api/documents/upload` under that user's bearer token (`upload()`, L229–241; legacy L243, structure-v2 L253) |
| Extra users created for isolation checks | `meta_user` (L324) and `other_user` (L412); both are cleaned by the **already scoped** email-based block (now L504–519), which deletes chunks via `document_id IN (SELECT id FROM documents WHERE user_id IN (SELECT id FROM users WHERE email = :e))` |
| What ownership keys exist? | `documents/models.py`: `Document.user_id → users.id` (`ondelete="CASCADE"`, indexed) and `DocumentChunk.document_id → documents.id` (`ondelete="CASCADE"`, indexed). **A chunk has no owner column of its own** |
| What is removed with the user? | `auth/models.py` (`users`), `reliability/models.py` (`ReliabilityLog.user_id → users.id`, unique, `ondelete="CASCADE"`), `chat/models.py` (`chat_sessions.user_id`, `chat_messages.session_id`, both CASCADE) |
| Existing scoped precedent | the same file's email-scoped block (L504–519) and `run_dual_path_ablation.py` L853–865 (`delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))`) |
| Existing regression tests | none referenced this harness (`grep -rln "run_phase3d_upload_integration\|phase3d_upload" tests/` matched only a docstring in `tests/unit/chat/test_phase3d_reconciliation.py`) — so tests had to be written |
| Guard and Step 0/0.5/0.6 contracts | `evaluation/isolation.py`, the Step 0 / Step 0.5 / Step 0.6 reports |
| Working tree | dirty and largely untracked; no existing change was discarded, reverted or reorganised |

---

## 3. The proven ownership boundary

**Boundary: the harness's own evaluation user (`user_id`), reached through
`documents.user_id`, and a chunk through `document_chunks.document_id`.**

Why this is correct, from the repository itself:

1. `Document.user_id` is the only ownership key a document has (schema, `documents/models.py`).
2. `DocumentChunk` has no owner column; its only edge to an owner is `document_id → documents.id`.
   Any scope narrower or wider than "chunks of this user's documents" would either leave orphan rows
   behind or delete rows the run does not own.
3. Every document the harness creates is ingested **through the application's upload route by its own
   user** (`upload()` → `POST /api/documents/upload` with that user's token), so `user_id` reaches
   every row the run owns. The harness never writes chunks for another user; the two extra users it
   creates exist only to prove *retrieval isolation* and are cleaned by their own scoped block.
4. The pre-existing neighbouring statements already use exactly this key for the same run
   (`reliability_logs WHERE user_id = :u`, `documents WHERE user_id = :u`, `users WHERE id = :u`),
   and the file's other cleanup uses the same shape via a subquery. The scoped form therefore
   preserves the run's cleanup semantics rather than changing them.
5. Ordering constraint: at cleanup time the run's documents still exist (the chunk delete precedes
   `DELETE FROM documents`), so the subquery resolves.

---

## 4. The precise change

**One new module-level function + one call site + three documentation strings.** No schema, protocol,
metric, corpus, model or output-schema change.

`evaluation/experiments/run_phase3d_upload_integration.py`:

* **Added** `async def cleanup_harness_rows(db, *, user_id) -> None` (L117; body L152–159) — the only
  cleanup implementation, documented with the ownership derivation above:

  ```python
  owned_documents = select(Document.id).where(Document.user_id == user_id)

  await db.execute(delete(ReliabilityLog).where(ReliabilityLog.user_id == user_id))
  await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(owned_documents)))
  await db.execute(delete(Document).where(Document.user_id == user_id))
  await db.execute(delete(User).where(User.id == user_id))
  ```

* **Replaced** the four inline raw-SQL statements (old L549–557) with
  `await cleanup_harness_rows(db, user_id=user_id)` + `await db.commit()` (L602–604). The caller still
  owns the commit; the deletion order (logs → chunks → documents → user) is unchanged.
* **Updated** the module docstring (L37–40) and the manifest `database.operation` string (L650–653),
  both of which previously described an unscoped delete and would otherwise now be false.
* The email-scoped cleanup for `meta_user` / `other_user` (L504–519) is **untouched**.

Model-bound statements were chosen over raw SQL for one reason that matters here: the predicate binds
through the dialect's UUID handling, so the identical scope is exercised by the PostgreSQL run and by
the SQLite fixtures the regression tests use — a raw `WHERE user_id = :u` with a string parameter
would silently match nothing on SQLite and could not be tested behaviourally. This matches the
existing cleanup pattern in `run_dual_path_ablation.py`.

---

## 5. Why unrelated records can no longer be deleted through this cleanup

* Every statement is keyed on the run's own `user_id` (or on `documents.user_id` for chunks).
  There is no statement that names a table without a predicate.
* A chunk is reached **only** through `documents.user_id == user_id`; a chunk whose document belongs
  to another user cannot satisfy the subquery, regardless of its content, page, chunker version,
  heading path or insertion order.
* Dependents are deleted before their parents (`document_chunks` before `documents`, `documents`
  before `users`), so the cleanup never relies on cascade for rows it claims to remove, and it cannot
  be blocked by a foreign key.
* The identification is by ownership, not by heuristics: the regression suite seeds an unrelated
  user's document with the **same document name and byte-identical chunk text** and shows it
  survives.
* Running the cleanup twice is a no-op on already-clean state (verified).

---

## 6. Tests executed, with exact results

All commands were run from `backend/` with `./venv/Scripts/python.exe`. Nothing below connects to
PostgreSQL, to the application database, or to any database at all: the behavioural tests run against
the suite's in-memory SQLite fixtures and the guard tests stop before any engine exists.

| Command | Result |
|---|---|
| `python -m pytest -q tests/unit/evaluation/test_phase3d_cleanup_scope.py` | **17 passed**, exit **0** (3.95 s) |
| `python -m pytest -q tests/unit/evaluation` | **271 passed**, exit **0** (27.87 s) — 254 before this change |
| `python -m pytest -q tests/unit` | **774 passed**, exit **0** (52.12 s) — 757 before this change |
| `python -m py_compile evaluation/experiments/run_phase3d_upload_integration.py` | OK |

New file `tests/unit/evaluation/test_phase3d_cleanup_scope.py` (332 lines, 17 tests) covers:

| Requirement | Test(s) | Evidence type |
|---|---|---|
| **A** owned records are cleaned up | `test_owned_records_are_removed` — seeds user+document+2 chunks+log, runs the real cleanup, asserts 0 logs / 0 chunks / 0 documents / 0 users | **executed** (SQLite) |
| **B** unrelated records survive | `test_unrelated_records_survive_untouched` (another user's 3 chunks, content and ids verified intact), `test_cleaning_up_one_user_never_touches_a_second_one` | **executed** (SQLite) |
| **C** repeated cleanup is safe | `test_repeated_cleanup_is_safe_and_does_not_spread` — cleanup twice, no error, unrelated rows still present | **executed** (SQLite) |
| **D** ownership boundary is correct | `test_ownership_is_the_key_not_the_document_name_or_chunk_text` (identical name + identical chunk text, foreign row survives) — behavioural; plus `test_cleanup_uses_the_ownership_key_and_not_a_bare_table_delete`, `test_the_unscoped_chunk_delete_is_gone`, `test_every_raw_sql_delete_is_scoped_by_a_predicate`, `test_the_only_chunk_delete_is_keyed_on_document_ownership` as secondary pins | **executed** + AST/source assertions |
| **E** isolation still enforced | `test_no_explicit_target_is_refused_before_any_engine`, `test_application_database_is_refused_as_an_explicit_target` (both with `create_async_engine` spied on; asserted `seen == []`, credential-free message), `test_the_guard_call_precedes_the_cleanup_call_in_the_source` | **executed** (no connection possible) |
| **F** evaluation behaviour preserved | `test_check_count_is_unchanged` (40 `check(` calls), `test_checks_json_payload_shape_is_unchanged`, `test_run_restores_the_production_chunker_default`, `test_entry_points_and_flags_still_behave`, `test_result_schema_documents_the_guard_and_the_scope` | source assertions (the harness itself cannot run without a database) |

**Deliberately not executed** (and therefore not claimed as verified):

* the harness itself. It drives the real application, the QA model and PostgreSQL, ingests
  documents and writes rows; running it needs an isolated PostgreSQL + pgvector database that this
  task is not authorised to provision or use.
* `tests/integration` and `tests/e2e`: they write into the application's upload root
  (Step 0.5 finding F-4), so the full suite was deliberately not run.
* No migration, no database create/drop, no destructive evaluation.

**Inference (explicitly not executed here):** the model-bound predicates compile and bind correctly on
PostgreSQL because (a) they use the same models and the same
`delete(...).where(...in_(...))` pattern that `run_dual_path_ablation.py` already executes against a
real isolated PostgreSQL database (Step 0 execution evidence: 40/0 checks, artifacts written), and
(b) the SQLAlchemy constructs are dialect-neutral. The SQLite execution in the new tests proves the
semantics; the PostgreSQL execution path is supported by that sibling precedent, not re-measured in
this task.

---

## 7. Safety checks confirming no application-database access

* The guard is unchanged and still runs first: `assert_safe_evaluation_target(` at **L192**, before
  `os.environ["DATABASE_URL"] = evaluation_dsn` (L204) and before
  `create_async_engine(evaluation_dsn)` (L240); the scoped cleanup is called at **L603**. A test
  asserts this ordering in the source, and two tests assert the refusal happens with the engine
  factory never reached.
* No database was contacted, created, migrated, dropped or queried during this task.
* Protected artifacts verified unchanged by mtime after every test run:
  `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` (2026-09-21),
  `models/documind-qa/model.safetensors` (2026-09-02), `evaluation/reports/*` (listing digest
  unchanged; `ablation_A.json` still 2026-10-04), `.env` (2026-10-06), `.env.example` (2026-09-27),
  and `backend/uploads/` (1 112 entries, unchanged before/after the test runs).
* No commit, push, deploy, revert or stash; no working-tree change was discarded.

**Post-change content digests** (this file is untracked, so no git baseline exists — the pre-change
content is only recoverable from the Step 0.5 report's citations):

```
64e5b2fd22770e34ff2150f254c336088fa1d64970b41dd9eea99da114089868  evaluation/experiments/run_phase3d_upload_integration.py
7a7b7f6ad639138a8888247948eb94dd3ada99b688208214982fc07f36bf2e84  tests/unit/evaluation/test_phase3d_cleanup_scope.py
d523f2ff4fc098c777e04b5d2f75f4ad4f4eeaa238fc86881322812dc1a4c6c5  evaluation/README.md
```

---

## 8. Files changed

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase3d_upload_integration.py` | added `cleanup_harness_rows`; call site replaced; module docstring + manifest `operation` string updated | remove the unscoped deletion, keep the same cleanup ordering and scope |
| `tests/unit/evaluation/test_phase3d_cleanup_scope.py` | **new** (17 tests) | behavioural proof of the scope plus regression pins |
| `evaluation/README.md` | new subsection "Phase 3D upload/ask harness — scoped cleanup (Step 0.7)" | document the ownership key and what is verified |
| `architecture/STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

No other file was modified: `git status` before and after shows the same pre-existing set of
modified/untracked paths, with only the five above touched by this task. The Step 0.5 audit report
and the Step 0 / Step 0.6 reports were **not** rewritten — they are append-only historical evidence
of the state at their time (`F-3` there remains an accurate description of the pre-remediation code).

---

## 9. Remaining risks and follow-up work

1. **`run_phase3d_upload_integration.py` cleanup is still success-path only.** If the harness raises
   mid-run, no cleanup runs (the `finally` block writes the manifest, not the deletes). Pre-existing
   behaviour, unchanged by this task; a failure-path cleanup would be a separate, larger decision
   (it must be safe against a half-created run, which is exactly why it was not bundled here).
2. **Other unscoped deletes survive in the codebase** (out of scope here, tracked by Step 0.5):
   `run_phase3d_evaluation.py` (unscoped `reliability_logs` / `chat_messages` / `chat_sessions` /
   `document_chunks` / `documents`, L534–539 and L637–640) and `run_phase3e_integration.py`
   (unscoped `document_chunks`, L389), `run_phase3e_validation.py` (L695), `run_phase3f_evaluation.py`
   (L709–714) and `run_phase4b_evaluation.py` (L689–694, L831–834). Step 0.6 made their *targets*
   safe; their *scope* is the same class of defect as F-3 and should be remediated the same way.
3. **Still-uninstrumented runners** (Step 0.5 F-2): `run_table_evidence_measurement`,
   `run_structure_confirmation`, `run_structure_element_measurement`,
   `run_structure_rrf_calibration` still default to the application database.
4. **Upload-root leakage** (Step 0.5 F-4) and **manifest source digests** (F-5) remain outstanding.
5. The harness's cleanup does not remove the files it stored through `save_upload` (application
   storage root) — unchanged by this task, same finding F-4.

**Recommended next task:** apply the same scoped-cleanup remediation to the remaining unscoped
deletions in R3/R4/R5/R6/R7 (item 2), one runner at a time with the same behavioural test pattern.

---

## 10. Completion criteria check

| Criterion | Status |
|---|---|
| Unscoped deletion removed or replaced by a demonstrably safe scoped operation | **Met** — no `DELETE FROM document_chunks` without a predicate remains (verified by grep and by an AST test) |
| Regression tests prove owned rows are cleaned and unrelated rows survive | **Met** — executed on SQLite (A/B/C/D) |
| Evaluation-database isolation remains enforced | **Met** — guard unchanged, ordering asserted, refusal tested with no engine created |
| Evaluation methodology and frozen artifacts unchanged | **Met** — no metric/corpus/model/benchmark/schema change; protected mtimes verified |
| Documentation accurately describes the verified implementation | **Met** — README subsection + this report, with executed vs inferred separated |
| Final report distinguishes verified evidence from assumptions | **Met** — §6 lists executed tests and the PostgreSQL inference explicitly |

**Stopped after verification and reporting.** No Step 0.8 work, no feature work, no commit/push/deploy.
