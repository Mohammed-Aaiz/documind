# Step 1.0 — Phase 3E Validation Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent). The specialist roles named in the task
(8, 11, 14, 17, 39, 51, 53, 58, 59, 60, 61, 72, 79, 81, 82, 89) are **role templates**, not separate
runtime agents provided by this repository's runtime. No sub-agent was invoked and none is claimed;
§7 maps each role to the section that answers its concern.
**Scope:** remove the unscoped destructive cleanup from
`backend/evaluation/experiments/run_phase3e_validation.py` (Step 0.5 finding **F-1**, second half) and
replace every raw destructive statement with ownership-scoped ORM operations, with behavioural
regression tests.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (§4 "R5 — UNSAFE"), the Step 0.6 isolation
remediation (documented in `evaluation/README.md`),
`STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md` (F-3),
`STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` (F-1, `run_phase3d_evaluation`),
`STEP0_9_PHASE3E_INTEGRATION_CLEANUP_REMEDIATION_2026-10-09.md` (F-1, `run_phase3e_integration`).

**Explicitly out of scope (not touched):** `run_phase3d_evaluation.py`,
`run_phase3d_upload_integration.py`, `run_phase3e_integration.py` (remediated in Steps 0.8 / 0.7 /
0.9), `run_phase3f_evaluation.py` (10 raw `DELETE FROM`), `run_phase4b_evaluation.py` (10).

---

## 1. Original failure mode

`run_phase3e_validation.py` (769 lines before this change) contained **nine** `DELETE FROM`
statements in three places. That count is pinned by the pre-existing Step 0.6 test
`tests/unit/evaluation/test_legacy_runner_isolation.py`
(`RUNNERS["run_phase3e_validation"].deletes == 9`), and it decomposes exactly as inspected (4 + 1 + 4):

**(a) the final cleanup block** (old L739–744):

```python
async with session_factory() as db:
    await db.execute(text("DELETE FROM reliability_logs WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM document_chunks"))                                          # ← unscoped
    await db.execute(text("DELETE FROM documents WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
    await db.commit()
```

**(b) the step-5 "Cleanup duplicates" pair** (old L475–478): chunks + document for `doc_a_id`, then
chunks + document for `stale_id`, four statements each bound to a document id.

**(c) the step-9 "Cleanup" for the isolation-check user** (old L640):
`DELETE FROM users WHERE email = :e` with the exact random `other_email`.

**The defect is (a)'s second statement.** `DELETE FROM document_chunks` carries no predicate at all, so
it removes **every row of `document_chunks` in whatever database the harness targets** — every owner,
every document, every chunk — including rows created by unrelated experiments that share the same
isolated database (the project's workflow points every isolated runner at one shared
`DOCUMIND_INTEGRATION_DATABASE_URL`, and `tests/fixtures/integration_db.py` re-uses the same
database). This matters more here than anywhere else in the suite: this runner is the *final validation
gate* — it is the harness whose results are used as evidence — and it was deleting the evidence base of
whatever else lived in its target.

**Why isolation alone did not mitigate it.** The Step 0.6 guard
(`evaluation/isolation.py::assert_safe_evaluation_target`) proves the target is *not the application
database*; it cannot prove the target is *empty* or *exclusively yours*. Severity per the Step 0.5
rubric (R5): High — a credible path to corrupting evaluation evidence, never Critical in practice
because the guard genuinely prevents the application database from being reached.

Three secondary observations, all now addressed (§3) — none was a scope bug:

* (b) and (c) were already correctly scoped but written as **raw SQL with string UUID binds**, which
  cannot be exercised by the suite's SQLite fixtures, so they had no regression coverage at all;
* (c) deleted only the `users` row and left the removal of that user's own rows to
  `ON DELETE CASCADE`, i.e. the cleanup depended on cascade for rows it was responsible for;
* this file legitimately keeps **read-only** `text("SELECT ...")` diagnostics (direct database
  inspection is its whole purpose: steps 3, 9, 11 and the retrieval probes). Those are *not* part of
  the defect and were deliberately left untouched — the cleanup conversion had to be delete-specific,
  not "remove all `text()`" (§4, §6).

**Not a defect, deliberately left alone:** the five `os.unlink(...)` calls (old L164, L253, L512,
L658, L705) delete the harness's **own** `tempfile.NamedTemporaryFile` inputs. They are not evaluated
database state, and their ownership boundary is intact.

---

## 2. Evidence-backed ownership boundary

**Boundary: the two user ids this harness creates — and no other row; the step-5 cleanup is narrower
still and stays scoped to the two document ids that step created.**

| Question | Where it was answered |
|---|---|
| Every destructive DB statement and file deletion | whole file read (769 lines); the three blocks in §1; `save_upload` inside the upload route (writes, deletes nothing) |
| Records created | one user `validation_<8 hex>@test.local` (`user_id`); a second temporary user `val_other_<8 hex>@test.local` (step 9); documents + chunks uploaded **through the real API as `user_id`** (fail, ready, dup_a, delete_test, legacy, v2); one stale `documents` row inserted directly with `user_id`; one duplicate document pair deleted in step 5 (`doc_a_id`, `stale_id`); `reliability_logs` for whichever user ran `/api/chat/ask` |
| Ownership keys (schema) | `documents/models.py`: `Document.user_id → users.id` (`ondelete="CASCADE"`, indexed), `DocumentChunk.document_id → documents.id` (CASCADE, indexed) — **a chunk has no owner column**; `chat/models.py`: `ChatSession.user_id → users.id`, `ChatMessage.session_id → chat_sessions.id`; `reliability/models.py`: `ReliabilityLog.user_id → users.id` (unique, CASCADE); `graph/models.py`: `document_graph_edges.document_id`, `document_structure_elements.document_id` (CASCADE) hang off `documents.id` |
| Independent confirmation that rows hang off the user | the upload route scopes each document to the bearer token's user; `chat/routes.py` `/ask` (L452) calls `store_query_reliability(str(current_user.id), …)`, so the reliability row is keyed by the requesting user |
| Ownership marker that survives a run | the exact emails; the 8-hex suffix is **random per run**, so within a run the **id** is the key |
| Existing scoped precedent | `run_dual_path_ablation.py`'s `delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))`; the Step 0.7 / 0.8 / 0.9 helpers |
| Existing regression tests | the Step 0.6 specs pin the guard and the statement *count*, never the scope; nothing referenced this runner's cleanup |
| Guard + prior contracts | `evaluation/isolation.py`; Steps 0, 0.5, 0.6, 0.7, 0.8, 0.9 reports; the current `evaluation/README.md` |
| Working tree | dirty and largely untracked (`backend/evaluation/**` has **no git baseline**: `git ls-files` fails on this runner); no existing change was discarded, reverted or reorganised |

**Explicitly rejected as a scope:** the random email **prefix** (`validation_%` / `val_other_%`) as a
pre-run sweep key — concurrent/interleaved runs would delete each other's live rows, which is exactly
the class of defect removed from `run_phase3d_evaluation` in Step 0.8. The consequence (interrupted
runs leak rows because the per-run emails are random) is recorded honestly in §6 rather than "fixed"
with an unsafe sweep.

**Deliberately not broadened:** the step-5 cleanup was *not* rewritten to the user scope, even though
that would be simpler. At that point in the run the same user still owns `fail_doc`, `ready_doc`,
`legacy`, `v2` and the documents created later — a user-scoped delete there would destroy the evidence
the remaining steps assert on. Document-id scope is the narrowest correct predicate.

---

## 3. Exact changes

One evaluation runner changed. **No** schema, benchmark, corpus, metric, protocol, step ordering or CLI
change: the edit set is exactly the regions listed below, and none of them lies inside a step body, so
the eleven validation steps and their assertions are unchanged. Directly verifiable in the final file,
and pinned by the new tests: all eleven numbered section markers (`=== 1` … `=== 11`) are present, and
`check(` occurs 65 times (the single `def check(` definition plus 64 call sites) — the same 65
occurrences the pre-change file had.

`backend/evaluation/experiments/run_phase3e_validation.py` (769 → 850 lines):

| # | Site | Before | After |
|---|---|---|---|
| 1 | new helper `owned_user_ids(db, *, emails)` (L64) | — | ids of the users this harness owns, by **exact email** (`select(User.id).where(User.email.in_(emails))`) |
| 2 | new helper `cleanup_harness_rows(db, *, user_ids)` (L81) | — | the only deletion implementation; model-bound, FK-safe order, early return on an empty id set |
| 3 | final cleanup (old L739–744) | 4 raw statements, one **unpredicated** | `await cleanup_harness_rows(db, user_ids=[user_id])` (L824) + `await db.commit()` |
| 4 | step-9 cleanup (old L640) | `DELETE FROM users WHERE email = :e` (raw, cascade-dependent) | `other_ids = await owned_user_ids(db, emails=[other_email])` (L722) + `await cleanup_harness_rows(db, user_ids=other_ids)` (L723) + `await db.commit()` |
| 5 | step-5 cleanup (old L475–478) | four raw statements with `str(id)` binds | `delete(DocumentChunk).where(DocumentChunk.document_id.in_([doc_a_id, stale_id]))` then `delete(Document).where(Document.id.in_([doc_a_id, stale_id]))` |
| 6 | imports inside `main()` | `from sqlalchemy import select, text, func` | `from sqlalchemy import delete, func, select, text` (`text` is still needed — read-only diagnostics) |
| 7 | guard `operation=` text (L161) | "…(it deletes rows)" | "…(it deletes rows **it owns**)" — matches the Step 0.7/0.8/0.9 convention |

The helper's body (identical in shape to Steps 0.8 and 0.9, so the three remediated runners share one
reviewable pattern):

```python
owned_sessions = select(ChatSession.id).where(ChatSession.user_id.in_(ids))
owned_documents = select(Document.id).where(Document.user_id.in_(ids))

await db.execute(delete(ReliabilityLog).where(ReliabilityLog.user_id.in_(ids)))
await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(owned_sessions)))
await db.execute(delete(ChatSession).where(ChatSession.user_id.in_(ids)))
await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(owned_documents)))
await db.execute(delete(Document).where(Document.user_id.in_(ids)))
await db.execute(delete(User).where(User.id.in_(ids)))
```

**Why sites 4 and 5 changed even though they were already scoped.** Their predicates were correct;
their *form* was not testable and not cascade-independent. Converting them to model-bound equivalents
with identical predicates (a) removes every raw destructive statement from this runner, so a
reintroduction is caught by an AST pin, (b) binds through the dialect's UUID handling, which is what
lets the regression tests exercise the real statements on SQLite, and (c) makes the deletion order
explicit instead of leaving the isolation-check user's rows to `ON DELETE CASCADE`. The deleted row
sets are provably unchanged: `users WHERE email = :e` ≡ `User.id IN (ids-from-that-email)` (whose
cascade covered exactly the rows the helper now names), and the two step-5 pairs ≡ two `IN (…)`
deletes over the same two document ids, chunks before documents.

**Read-only diagnostics were preserved, not converted.** The runner's `text("SELECT …")` statements
(retrieval probes, `alembic_version`, `information_schema.columns`) are not destructive and were left
byte-identical; a test asserts they are still present, precisely so a future "remove all raw SQL"
sweep cannot quietly strip the validation gate's inspection queries.

**One assertion-hardening change outside this runner (disclosed).** The AST helper that pins "no raw
destructive SQL" — duplicated in the four cleanup-scope test files — collected only plain string
constants, so an f-string statement like `text(f"DELETE FROM {table}")` would have evaded it. While
writing this step's pin it was found to be a real gap; it was fixed in **all four** files
(`test_phase3d_evaluation_cleanup_scope.py`, `test_phase3e_integration_cleanup_scope.py`,
`test_phase3e_validation_cleanup_scope.py`, and `test_legacy_runner_isolation.py`), each now collecting
f-string literal segments too. No runner, production file, expectation or threshold was changed by
that fix; only the collector's coverage increased, and `test_read_only_diagnostics_are_left_alone`
would have failed against the old collector (it did, and that is how the gap surfaced).

---

## 4. Tests and actual results

New file `tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py` (17 tests). All commands were
run from `backend/` with `./venv/Scripts/python.exe`. **Nothing below connects to PostgreSQL, to the
application database, or to any database at all**: the behavioural tests run against the suite's
in-memory SQLite fixtures (with `PRAGMA foreign_keys=ON`), and the guard tests stop before any engine
exists.

| Command | Result |
|---|---|
| `python -m py_compile evaluation/experiments/run_phase3e_validation.py` | OK (exit 0) |
| `python -m pytest -q tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py tests/unit/evaluation/test_legacy_runner_isolation.py` (first run) | **86 passed, 1 failed**, exit 1 — the one failure is in the new file (`test_read_only_diagnostics_are_left_alone`); see below |
| after the collector fix: `python -m pytest -q tests/unit/evaluation` | **320 passed**, exit **0** (37.3 s) — 303 before this change |
| `python -m pytest -q tests/unit` | **823 passed**, exit **0** (66.3 s) — 806 before this change; final run on the frozen tree |

**The one failure, and what it was.** `test_read_only_diagnostics_are_left_alone` failed on the first
run because the runner's `information_schema.columns` probe is an **f-string** and the collector only
read plain constants — i.e. the failure exposed a genuine gap in the security assertion, not in the
runner. The cause was fixed (f-string-aware collector, §3) rather than the assertion relaxed, and the
suites above are the re-run evidence. The claim "no raw destructive SQL remains" is therefore now
checked over f-strings as well.

| Requirement | Test(s) | Evidence type |
|---|---|---|
| **Owned records are removed** | `test_owned_rows_are_removed` — seeds the harness user with a document + 2 chunks + reliability log + chat session + message, runs the real helpers, asserts all six tables drop to 0 | **executed** (SQLite) |
| **Unrelated records survive** | `test_other_experiments_survive_untouched` — a sibling `phase3e_*` user and an unrelated `phase3d_*` user keep their row counts, chunk **ids**, chat rows and logs while the harness's rows go | **executed** (SQLite) |
| **Repeated cleanup is safe** | `test_repeated_cleanup_is_safe_and_does_not_spread` — cleanup twice, no error; an empty id set is a no-op; a second email lookup finds nothing | **executed** (SQLite) |
| **Ownership is the exact email, not a prefix** | `test_ownership_is_selected_by_the_exact_email` — a decoy `…@test.local.bak` is **not** selected | **executed** (SQLite) |
| **Unsafe targets rejected before engine creation** | `test_no_explicit_target_is_refused_before_any_engine` (engine factory spied on; `seen == []`; credential-free message), `test_application_database_is_refused_as_an_explicit_target` (`REFUSING`) | **executed** (no connection possible) |
| **No unscoped/raw destructive SQL can return** | `test_no_raw_sql_delete_exists` (AST over every `text(...)` literal, f-strings included: none contains `DELETE`), `test_own_cleanup_is_keyed_on_the_user_id_set` (all six predicates), `test_both_cleanup_sites_use_the_scoped_helpers` (2 call sites + 1 lookup; no raw variants), `test_step_five_cleanup_stays_scoped_to_the_two_document_ids` (both `IN_([doc_a_id, stale_id])` predicates, chunks before documents) | AST + source pins |
| **Read-only diagnostics intact** | `test_read_only_diagnostics_are_left_alone` (`alembic_version`, `information_schema.columns`, retrieval `document_chunks` probes) | AST |
| **Guard ordering** | `test_the_guard_precedes_the_engine_and_both_cleanups_in_the_source` | source |
| **Evaluation protocol preserved** | `test_the_eleven_step_gate_is_unchanged` (all 11 markers), `test_check_accumulators_still_behave` (functional `check()` semantics, module state restored), `test_exit_code_is_failure_when_any_check_fails`, `test_the_chunker_default_is_restored_after_the_run`, `test_cli_flags_and_entry_points_still_behave` | executed + source |

**One pre-existing test was updated, deliberately.** `test_legacy_runner_isolation.py` pinned
`source.count("DELETE FROM") == 9` for this runner — a pin asserting exactly the code this task had to
remove, so as written it forbade the fix. This runner's spec now carries `scoped_cleanup=True` and the
branch verifies the **stricter** new contract. Because this runner keeps read-only `text("SELECT …")`,
the generic "no `db.execute(text(`" clause used in Steps 0.8/0.9 would have been wrong here, so the
branch now checks the `text(...)` **literals** for `DELETE` (AST, f-strings included) — narrower and
more precise than the original, and it still fails closed if any destructive raw SQL returns. The two
remaining runners keep their exact historical counts (10, 10). No assertion was weakened or skipped.

**Deliberately not executed (therefore not claimed as verified):**

* the validation gate itself — it drives the real FastAPI app, the real chunkers/embeddings, Alembic
  state and PostgreSQL, which this task is neither authorised nor provisioned to run;
* `tests/integration` and `tests/e2e` (they write into the application upload root — Step 0.5 F-4), so
  the full suite was not run;
* no migration, no database create/drop/downgrade, no destructive evaluation.

**Evidence boundary, stated plainly.** The user-scoped cleanup (final + step 9) is proven
**behaviourally on SQLite**. The step-5 document-scoped cleanup is pinned by **source/AST assertions
only** — it lives inline in `main()`, which cannot be invoked without PostgreSQL, so it has no
behavioural coverage in this step. PostgreSQL binding of all these predicates is *inferred*, not
measured: the statements use the same models and the same `delete(...).where(...in_(...))` shape that
`run_dual_path_ablation.py` already executes against a real isolated PostgreSQL database, and the
constructs are dialect-neutral.

---

## 5. Database-isolation and protected-artifact checks

| Artifact | Observed (after every test run) |
|---|---|
| `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | 2026-09-21 02:58 (frozen benchmark, untouched) |
| `models/documind-qa/model.safetensors` | 2026-09-02 02:52 (QA weights, untouched) |
| `evaluation/reports/ablation_A.json` | 2026-10-04 18:16 (untouched); `evaluation/reports/` listing digest `md5 e8d577977cb0d3683afb391cb79a1595` (same as Steps 0.8/0.9) |
| `backend/.env` / `backend/.env.example` | 2026-10-06 07:53 / 2026-09-27 10:00 (untouched) |
| `backend/uploads/` | **1 112** entries (unchanged before/after) |

* **No database was contacted, created, migrated, dropped or queried**, and the validation gate was
  not executed. The guard tests assert the refusal happens with `create_async_engine` never reached
  (`seen == []`).
* **Guard ordering unchanged and pinned:** `assert_safe_evaluation_target(` (L159) precedes
  `os.environ["DATABASE_URL"] = evaluation_dsn`, `create_async_engine(evaluation_dsn)` (L191), and
  both cleanup sites (L722–723, L824).
* **Working tree scope unchanged:** `git status --porcelain` → **384** entries, **34** modified tracked
  files — identical to the pre-task count. (The runner is untracked; the new test file lives inside the
  already-untracked `backend/tests/unit/evaluation/`.)
* No commit, push, deploy, revert or stash; no existing change discarded; the five protected runners
  were not modified (`run_phase3f_evaluation` 10, `run_phase4b_evaluation` 10 raw `DELETE FROM`, and the
  three previously remediated runners unchanged).

**Content digests** (the runner is untracked, so its pre-change content is recoverable only from the
Step 0.5 report's citations and the pre-existing `deletes=9` pin):

```
e5f2495ce73067253317d1e40b8d04c1a8298382a2dcc879fc64597c395aff5b  evaluation/experiments/run_phase3e_validation.py
bf73004ac596b78ea079b1be978363923a0e95ba66c16185b73d7943ce5d061a  tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py
7b094531c222e34389175338f515ce0ae0132bf85130fcc0a6f09956099aea25  tests/unit/evaluation/test_legacy_runner_isolation.py
d2783c1b39b6b420e626140160ae9ecc204acbb99cc31c343aef70298b321e23  tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py
d9d97b4c8d77bf9cbb78d20e0aa9ee47c1df7d4da7b82a159ea0e97db0c2864a  tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py
```

---

## 6. Remaining risks and follow-up work

1. **No PostgreSQL execution.** Scope semantics are proven on SQLite; PostgreSQL binding is inferred.
   A future isolated-database run that observes a foreign user's rows surviving this harness's cleanup
   (and a foreign document's chunks surviving the step-5 cleanup) would close this.
2. **The step-5 cleanup has no behavioural coverage** — it is inline in `main()` and pinned only by
   source/AST assertions (§4). Extracting it into a scoped helper would make it testable; that was not
   done here because it is not the defect and would add a third helper for a single call site.
3. **Interrupted runs leak rows.** The per-run emails are random, so a later run cannot recognise an
   earlier run's leftovers, and **no safe pre-run sweep exists** (a `validation_%`-prefix sweep would
   delete a concurrent run's live data). Fixing this properly means a deterministic identity or run-id
   marker plus a documented single-run policy — a design decision, not a cleanup tweak.
4. **Upload-root risk unchanged and documented:** every upload in this runner goes through the real
   route, so `save_upload` writes into the application storage root (`settings.upload_path`) and
   nothing removes those files (Step 0.5 F-4). The runner deletes its own temporary inputs but not the
   stored copies; that is the F-4 follow-up, unchanged by this step.
5. **The pattern persists in two runners** (Step 0.5 F-1, second half): `run_phase3f_evaluation.py`
   (10 raw `DELETE FROM`) and `run_phase4b_evaluation.py` (10). Each needs the same treatment, one at a
   time, with its own report — explicitly **not** started here.
6. **The gate itself remains unexecuted:** its 64 `check(...)` assertions are unchanged but were never
   run against a live stack, so the *harness* is unverified; only its cleanup boundary, its destructive
   SQL surface, its diagnostics and its CLI surface are.
7. **Provenance (F-5) untouched:** a run on this dirty, largely untracked tree still cannot be
   reproduced from a manifest.
8. **F-2/F-6/F-7/F-9/F-10/F-11/F-12/F-13/F-14** from the Step 0.5 audit remain open.

---

## 7. Operational agent and specialist role templates

Operational agent: **COORDINATOR**, acting directly. This repository's runtime provides one coding agent
plus file/code-search helpers — no separate runtime agents implementing the specialist templates exist,
so none was invoked and none is claimed.

| # | Role template | Where its concern is answered |
|---|---|---|
| 8 | Software Architect | §3 (two module-local helpers; no framework; call sites and commit boundaries preserved) |
| 11 | Database Architect | §2 (ownership keys from the models), §3 (FK-safe order) |
| 14 / 72 | Security Architect / Application Security | §1 (blast radius), §5 (guard ordering, credential-free messages) |
| 17 | Backend Coding Specialist | §3 (exact change, including why raw SQL was replaced with ORM statements) |
| 39 | Model Evaluation Specialist | §3/§4 (eleven-step gate, 64 checks and diagnostics preserved; no metric change) |
| 51 / 53 | Test Architect / Integration Testing | §4 (behavioural SQLite tests; explicit evidence boundary incl. the step-5 gap) |
| 58 | Security Testing | §4 (refusal tests with the engine factory spied on; f-string-aware AST pin) |
| 59 | Code Review | §3, §8 (files changed, final scope verification, disclosed cross-file test fix) |
| 60 | Debugging | §1 (failure mode), §4 (the failing first run, its cause and the fix) |
| 61 | Reliability Engineer | §4 (repeat-cleanup safety), §6 (leakage, remaining risks) |
| 79 / 81 | Documentation / Architecture Documentation | this report, `evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64 |
| 82 | Codebase Knowledge | §2 (inspection record), §6 (inventory of what still carries the pattern) |
| 89 | Database Optimization | §2/§3 (narrowest correct predicate per site; index-supported keys) |

---

## 8. Files changed and final scope verification

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase3e_validation.py` | `owned_user_ids` + `cleanup_harness_rows` added (L64/L81); final, step-9 and step-5 cleanup sites replaced; `delete` imported; guard `operation` text updated | remove the unpredicated chunk delete; make every deletion ownership-scoped, FK-safe and testable |
| `tests/unit/evaluation/test_phase3e_validation_cleanup_scope.py` | **new** (17 tests) | behavioural proof of scope/exact-email ownership/repeat-safety/guard ordering, plus the preserved gate surface and diagnostics |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | this runner's spec gains `scoped_cleanup=True`; delete-specific, f-string-aware literal check; docstring notes the Step 0.8/0.9/1.0 exceptions | the count pin forbade the fix; the generic raw-`text(` clause would have been wrong for a runner with read-only SQL |
| `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py`, `tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py` | AST collector now also reads f-string literal parts | closes an evasion gap in the "no raw destructive SQL" pin (§3); no runner or expectation changed |
| `evaluation/README.md` | new subsection "Phase 3E validation gate — scoped cleanup (Step 1.0, 2026-10-09)" + outstanding list reduced to the last two runners | document the boundary and what is verified |
| `architecture/STEP1_0_PHASE3E_VALIDATION_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

**Not changed:** the five protected runners; the Step 0 / 0.5 / 0.6 / 0.7 / 0.8 / 0.9 reports
(append-only historical evidence — their description of R5 remains an accurate record of the
pre-remediation code); no production module; no migration; no fixture; no benchmark, weight, `.env` or
historical report.

**Verification of the final tree:** `git status` shows the same 384 entries / 34 modified tracked files
as before the task; the only files this step touched are the seven above; the changed Python file
compiles and the test suites were re-run after the last code edit (the 823-passed `tests/unit` run in
§4 is the final one — only Markdown changed afterwards); protected artifacts and `backend/uploads/` are
unchanged (§5). No commit, push, deploy, revert or stash was performed.

**Stop point.** Step 1.0 is complete for `run_phase3e_validation.py` only. No other runner was
inspected, remediated or reported, and Step 1.1 was not begun, pending review.

---

## 9. Mandatory inspection record and acceptance criteria

**Inspection performed (in the order the task requires):**

1. Read the complete runner (all 769 lines) and traced every destructive operation: the final cleanup,
   step 5's duplicate/stale cleanup, step 9's isolation-check cleanup, the five `os.unlink` calls on its
   own temp files, and the read-only `text("SELECT …")` diagnostics — §1.
2. Ownership of every created record established from the schema and the execution flow, with the
   independent evidence that the reliability row is keyed by the requesting user — §2.
3. `backend/evaluation/isolation.py` re-read; the guard call, its ordering and its credential-free
   error path confirmed in the runner — §5.
4. Steps 0, 0.5, 0.6, 0.7, 0.8, 0.9 reports and the current `evaluation/README.md` re-read; the
   ownership-scoping principles reused, and the divergences justified rather than copied (read-only
   diagnostics kept; step-5 scope kept narrow; the generic legacy pin rewritten, not copied) — §3, §4.
5. Working tree inspected before editing; unrelated modifications preserved — §2, §5.
6. Ownership boundary documented before implementing — §2 (this section was written before the edits
   were applied).

**Acceptance criteria check**

| Criterion | Status |
|---|---|
| Only `run_phase3e_validation.py` remediated | ✅ (five protected runners untouched; counts still 10/10 remaining) |
| Every confirmed unscoped destructive operation replaced by a narrow, evidence-supported ORM operation | ✅ (9 raw statements → 2 scoped helpers + 2 document-scoped ORM deletes) |
| FK-safe ordering + transaction boundaries preserved | ✅ (each site keeps its own session/commit; chunks before documents; children before users) |
| Isolation guard ahead of engine creation, DB access and cleanup | ✅ (source-pinned + two refusal tests) |
| Evaluation semantics, CLI, report/console schema preserved | ✅ (11 markers, 65 `check(` occurrences, exit semantics, chunker restore) |
| Behavioural tests: owned rows removed, unrelated rows survive, repeat cleanup safe, unsafe targets refused pre-engine | ✅ (§4; executed on SQLite) |
| Source-level assertions preventing the pattern's return | ✅ (AST over `text(...)` literals incl. f-strings; helper presence/usage; step-5 predicates; read-only diagnostics pinned) |
| No general-purpose cleanup framework | ✅ (two module-local functions, one call-site each; no shared module) |
| Ownership predicates not broadened for convenience | ✅ (step-5 scope deliberately kept at document ids) |
| Temporary-file ownership preserved; upload-root risk documented | ✅ (§1, §6 item 4) |
| Focused tests, isolation tests, evaluation unit suite, full unit suite, compilation run with exit codes | ✅ (§4) |
| SQLite/mock evidence distinguished from PostgreSQL verification | ✅ (§4 "evidence boundary") |
| Protected artifacts, `.env`, benchmark, weights, uploads, historical reports untouched | ✅ (§5) |
| No application-database access, no destructive run, no create/migrate/drop | ✅ (§5) |
| Dated report at the required path with items 1–9 | ✅ (this file) |
| Evaluation README updated + §64 pointer | ✅ (§8) |
| Final diff inspected; only intended files changed | ✅ (§8) |
| No commit/push/deploy/revert of unrelated work | ✅ (§5, §8) |
