# Step 0.9 — Phase 3E Integration Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent). The specialist roles named in the task
(8, 11, 14, 17, 39, 51, 53, 58, 59, 60, 61, 72, 79, 81, 82, 89) are **role templates**, not separate
runtime agents provided by this repository's runtime. No sub-agent was invoked, and none is claimed;
their concerns are answered by sections of this report and by the code/tests. §7 maps each role to
where its concern is addressed.
**Scope:** remove the unscoped destructive cleanup from
`backend/evaluation/experiments/run_phase3e_integration.py` (Step 0.5 finding **F-1**, second half)
and replace it with a demonstrably ownership-scoped cleanup, with behavioural regression tests.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (§4 "R4 — UNSAFE"),
the Step 0.6 isolation remediation (documented in `evaluation/README.md`),
`STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md` (F-3, upload/ask harness) and
`STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` (F-1, `run_phase3d_evaluation`).

**Explicitly out of scope (not touched):** `run_phase3e_validation.py` (9 raw `DELETE FROM`),
`run_phase3f_evaluation.py` (10), `run_phase4b_evaluation.py` (10), `run_phase3d_evaluation.py` and
`run_phase3d_upload_integration.py` (remediated in Steps 0.8 / 0.7 and left untouched).

---

## 1. Original failure mode

`run_phase3e_integration.py` (453 lines before this change) contained **seven** `DELETE FROM`
statements in three places — that count is pinned by the pre-existing Step 0.6 test
`tests/unit/evaluation/test_legacy_runner_isolation.py`
(`RUNNERS["run_phase3e_integration"].deletes == 7`), and it decomposes exactly as inspected:

**(a) the final cleanup block** (old L432–L438):

```python
async with session_factory() as db:
    await db.execute(text("DELETE FROM reliability_logs WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM document_chunks"))                                          # ← unscoped
    await db.execute(text("DELETE FROM documents WHERE user_id = :u"), {"u": str(user_id)})
    await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
    await db.commit()
```

**(b) the step-8 isolation-check cleanup** (old L364):
`DELETE FROM users WHERE email = :e` with the exact random `other_email`.

**(c) the step-9 stale-document cleanup** (old L405–L406):
`DELETE FROM document_chunks WHERE document_id = :id` and
`DELETE FROM documents WHERE id = :id`, both bound to `str(stale_id)`.

**The defect is (a)'s second statement.** `DELETE FROM document_chunks` carries no predicate at all,
so it removes **every row of `document_chunks` in whatever database the harness targets** — every
owner, every document, every chunk, including rows created by unrelated experiments that share the
same isolated database (the project's workflow points every isolated runner at one shared
`DOCUMIND_INTEGRATION_DATABASE_URL`, and `tests/fixtures/integration_db.py` re-uses the same
database). The neighbouring statements in the same block were already scoped to the run's own user,
so this was an isolated outlier, not a protocol requirement — and the step-9 block shows the scoped
shape (`WHERE document_id = :id`) the same file already knew how to write.

**Why isolation alone did not mitigate it.** The Step 0.6 guard
(`evaluation/isolation.py::assert_safe_evaluation_target`) proves the target is *not the application
database*; it cannot prove the target is *empty* or *exclusively yours*. The unscoped delete was
therefore still able to destroy another experiment's evidence. Severity per the Step 0.5 rubric:
High — a credible path to corrupting evaluation evidence (never Critical in practice, because the
guard genuinely prevents the application database from being reached).

Two secondary observations, both now addressed (see §3) — neither was a scope bug:

* (b) and (c) were already correctly scoped, but written as **raw SQL with string UUID binds**
  (`{"id": str(stale_id)}`), which cannot be exercised by the suite's SQLite fixtures and so had no
  regression coverage at all;
* deleting only the `users` row in (b) left the removal of that user's own rows to
  `ON DELETE CASCADE`, i.e. the cleanup depended on cascade for rows it was responsible for.

**Not a defect, deliberately left alone:** the five `os.unlink(...)` calls (old L184, L213, L281,
L312, L425) delete the harness's **own** `tempfile.NamedTemporaryFile` inputs. They are not
evaluated-database state and are out of the ownership question.

---

## 2. Mandatory inspection and the evidence-backed ownership boundary

| Question | Where it was answered |
|---|---|
| Every destructive DB statement and file deletion | whole file read; the three blocks in §1; `save_upload` inside the upload route (writes, does not delete) |
| What records does the runner create? | one user (`phase3e_<8 hex>@test.local`, `user_id`), a second temporary user (`phase3e_other_<8 hex>@test.local`) for the isolation check, documents + chunks uploaded **through the real API as `user_id`**, one `reliability_logs` row written by `/api/chat/ask`, and one directly-inserted stale `documents` row (`user_id`) in step 9 |
| Ownership keys (schema) | `documents/models.py`: `Document.user_id → users.id` (CASCADE, indexed); `DocumentChunk.document_id → documents.id` (CASCADE, indexed) — **no owner column on a chunk**; `chat/models.py`: `ChatSession.user_id → users.id`, `ChatMessage.session_id → chat_sessions.id`; `reliability/models.py`: `ReliabilityLog.user_id → users.id` (unique, CASCADE) |
| Independent evidence that all the run's rows hang off `user_id` | `chat/routes.py` `/ask` (L452) calls `store_query_reliability(str(current_user.id), …)`, so the reliability row is keyed by the requesting user; the upload route scopes the document to the token's user; `graph/models.py` `document_graph_edges.document_id` and `document_structure_elements.document_id` (CASCADE) are reached only through `documents.id` |
| What identifies the harness's own users? | the exact emails `phase3e_<8 hex>@test.local` / `phase3e_other_<8 hex>@test.local` — the suffix is **random per run** (§6 limitation), so within a run the **id** is the ownership key |
| Existing scoped precedent | `run_dual_path_ablation.py` `delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))`; the Step 0.7 and Step 0.8 helpers |
| Existing regression tests | `tests/unit/evaluation/test_legacy_runner_isolation.py` (Step 0.6) pinned the guard and the statement *count*, never the scope; no test referenced this runner at all (`grep` over `tests/` matched nothing) |
| Guard + prior contracts | `evaluation/isolation.py`; the Step 0 / 0.5 / 0.6 / 0.7 / 0.8 reports and `evaluation/README.md` |
| Working tree | dirty and largely untracked (`backend/evaluation/**` has **no git baseline** — `git ls-files` fails on this runner); nothing was discarded, reverted or reorganised |

**Boundary: the two user ids this harness creates — and no other row.**

* `user_id` reaches every document (`documents.user_id`), every chunk (`documents` → `document_chunks`),
  the reliability row (`reliability_logs.user_id`), and any chat rows
  (`chat_sessions.user_id` → `chat_messages.session_id`); graph/structure rows follow their document
  by cascade.
* the temporary isolation-check user is selected by its **exact email** and then cleaned by the same
  user-id scope.

**Explicitly rejected as a scope:** the random email **prefix** (`phase3e_%` / `phase3e_other_%`) as a
*pre-run* sweep key. Concurrent or interleaved runs would delete each other's live rows — precisely
the class of defect the Step 0.8 remediation removed from `run_phase3d_evaluation`. The consequence
(interrupted runs leak rows, because the per-run emails are random) is recorded honestly in §6 as a
remaining limitation rather than "fixed" with an unsafe sweep.

---

## 3. Exact code changes

One evaluation runner changed. **No** schema, benchmark, corpus, metric, protocol, step ordering or
CLI change: the edit set is exactly the seven regions below, and none of them lies inside a step
body, so the ten evaluation steps and their assertions are unchanged.  Directly verifiable in the
final file, and pinned by the new tests: all ten numbered step markers (steps 1–10) are present,
one `print` each, and `check(` appears 39 times across 39 separate lines — the single `def check(`
definition plus 38 call sites (one occurrence per line).

`backend/evaluation/experiments/run_phase3e_integration.py` (453 → 530 lines):

| # | Site | Before | After |
|---|---|---|---|
| 1 | new helper `owned_user_ids(db, *, emails)` (L64) | — | ids of the users this harness owns, looked up by **exact email** (`select(User.id).where(User.email.in_(emails))`) |
| 2 | new helper `cleanup_harness_rows(db, *, user_ids)` (L81) | — | the only deletion implementation; model-bound, FK-safe order, early return on an empty id set |
| 3 | final cleanup (old L432–438) | 4 raw statements, one of them **unpredicated** | `await cleanup_harness_rows(db, user_ids=[user_id])` (L514) + `await db.commit()` |
| 4 | step-8 cleanup (old L364) | `DELETE FROM users WHERE email = :e` (raw, cascade-dependent) | `other_ids = await owned_user_ids(db, emails=[other_email])` (L440) + `await cleanup_harness_rows(db, user_ids=other_ids)` (L441) + `await db.commit()` |
| 5 | step-9 cleanup (old L405–406) | two raw statements with `str(stale_id)` binds | `delete(DocumentChunk).where(DocumentChunk.document_id == stale_id)` and `delete(Document).where(Document.id == stale_id)` |
| 6 | imports inside `main()` | `from sqlalchemy import select, text` | `from sqlalchemy import delete, select` (`text` is no longer used anywhere in the file) |
| 7 | guard `operation=` text (L160) | "…(it deletes rows)" | "…(it deletes rows **it owns**)" — matches the Step 0.7/0.8 convention |

The helper's body:

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
with identical predicates (a) removes the last raw SQL `DELETE` from this runner — so a future
reintroduction of an unpredicated delete is caught by a source/AST pin (§4), (b) binds through the
dialect's UUID handling, which is what lets the regression tests exercise the same statements on
SQLite that PostgreSQL executes, and (c) makes the deletion order explicit instead of leaving the
isolation-check user's rows to `ON DELETE CASCADE`. The deleted row sets are provably unchanged:
`users WHERE email = :e` ≡ `User.id IN (ids-from-that-email)`, and the user row's cascade covered
exactly the rows the helper now names.

Model-bound statements were chosen over raw SQL for the reason recorded in Step 0.7: a raw
`WHERE user_id = :u` bound to a `str` would silently match nothing on SQLite and could not be tested
behaviourally. This matches the existing cleanup pattern in `run_dual_path_ablation.py`.

**Caller transaction/commit behaviour is preserved** — each of the three sites still runs inside its
own `async with session_factory() as db:` block and still commits itself; the helpers never commit.

---

## 4. Regression tests and actual results

New file `tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py` (16 tests). All commands
were run from `backend/` with `./venv/Scripts/python.exe`; **nothing below connects to PostgreSQL, to
the application database, or to any database at all** — the behavioural tests run against the suite's
in-memory SQLite fixtures (with `PRAGMA foreign_keys=ON`), and the guard tests stop before any engine
exists.

| Command | Result |
|---|---|
| `python -m py_compile evaluation/experiments/run_phase3e_integration.py` | OK (exit 0) |
| `python -m pytest -q tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py` | **16 passed**, exit **0** (3.6 s) |
| `python -m pytest -q tests/unit/evaluation` | **303 passed**, exit **0** (35.2 s) — 287 before this change |
| `python -m pytest -q tests/unit` | **806 passed**, exit **0** (63.5 s) — 790 before this change; this is the final run on the frozen tree (every later edit was documentation) |

| Requirement | Test(s) | Evidence type |
|---|---|---|
| **Owned records are removed** | `test_owned_rows_are_removed` — seeds the harness user with a document + 2 chunks + reliability log + chat session + message, runs the real helpers, asserts all six tables drop to 0 and the chunks are gone | **executed** (SQLite) |
| **Unrelated users' records survive** | `test_other_experiments_survive_untouched` — a sibling `phase3e_other_*` user and a `phase3d_*` user keep their row counts, chunk **ids**, chat rows and logs while the harness's rows go | **executed** (SQLite) |
| **Repeated cleanup is safe** | `test_repeated_cleanup_is_safe_and_does_not_spread` — cleanup twice, no error; an empty id set is a no-op; a second email lookup finds nothing | **executed** (SQLite) |
| **Ownership is the exact email, not a prefix** | `test_ownership_is_selected_by_the_exact_email` — a decoy user whose email is `…@test.local.bak` (same prefix) is **not** selected | **executed** (SQLite) |
| **Unsafe targets refused before engine creation** | `test_no_explicit_target_is_refused_before_any_engine` (engine factory spied on; `seen == []`; credential-free message), `test_application_database_is_refused_as_an_explicit_target` (`REFUSING`) | **executed** (no connection possible) |
| **No unscoped delete can return** | `test_no_raw_sql_delete_exists` (AST scan of every `text(...)` literal + `db.execute(text(` absent), `test_own_cleanup_is_keyed_on_the_user_id_set` (all six predicates), `test_all_three_cleanup_sites_use_the_scoped_helpers` (2 call sites + 1 lookup, no raw chunk/user variants), `test_step_nine_delete_is_scoped_to_the_one_document` | AST + source pins |
| **Guard ordering** | `test_the_guard_precedes_the_engine_and_both_cleanups_in_the_source` | source |
| **Evaluation protocol preserved** | `test_the_ten_step_protocol_is_unchanged` (all ten section markers), `test_check_accumulators_still_behave` (functional `check()` PASS/FAIL semantics, module state restored), `test_exit_code_is_failure_when_any_check_fails`, `test_the_chunker_default_is_restored_after_the_run`, `test_cli_flags_and_entry_points_still_behave` | executed + source |

**One pre-existing test was updated, deliberately.** `test_legacy_runner_isolation.py`'s
`test_destructive_sql_is_untouched` pinned `source.count("DELETE FROM") == 7` for this runner — a pin
asserting exactly the code this task was asked to remove, so as written it forbids the fix. As in
Step 0.8, the spec entry now carries `scoped_cleanup=True` and the assertion verifies the **stricter**
new contract (`db.execute(text(` absent, `text("DELETE` absent, `cleanup_harness_rows` defined and
used). The other three runners keep their exact historical counts (9, 10, 10) unchanged. No other test
was weakened, skipped or deleted, and no assertion was relaxed to make anything pass.

**Deliberately not executed (therefore not claimed as verified):**

* the harness itself — it drives the real FastAPI app, the real chunkers/embeddings and PostgreSQL,
  which this task is neither authorised nor provisioned to run;
* `tests/integration` and `tests/e2e` (they write into the application upload root — Step 0.5 F-4), so
  the full suite was not run;
* no migration, no database create/drop/downgrade, no destructive evaluation.

**Inference (explicitly not measured here).** PostgreSQL binding of the new predicates is *inferred*,
not executed: the statements use the same models and the same `delete(...).where(...in_(...))` shape
that `run_dual_path_ablation.py` already executes against a real isolated PostgreSQL database, and the
constructs are dialect-neutral. The SQLite execution proves the **semantics** (which rows are
selected); it does not prove the PostgreSQL plan.

---

## 5. Protected-artifact and database-safety checks

Verified after every test run (mtimes/listing/counts unchanged, and identical to the Step 0.8
snapshot):

| Artifact | Observed |
|---|---|
| `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | 2026-09-21 02:58 (frozen benchmark, untouched) |
| `models/documind-qa/model.safetensors` | 2026-09-02 02:52 (QA weights, untouched) |
| `evaluation/reports/ablation_A.json` | 2026-10-04 18:16 (untouched); `evaluation/reports/` listing digest `md5 e8d577977cb0d3683afb391cb79a1595` (same as Step 0.8) |
| `backend/.env` / `backend/.env.example` | 2026-10-06 07:53 / 2026-09-27 10:00 (untouched) |
| `backend/uploads/` | **1 112** entries (unchanged before/after) |

* **No database was contacted, created, migrated, dropped or queried**, and the runner was not
  executed. The guard tests assert the refusal happens with `create_async_engine` never reached
  (`seen == []`).
* **Working tree scope unchanged:** `git status --porcelain` → **384** entries, **34** modified tracked
  files — identical to the pre-task count. (The whole `backend/evaluation/experiments/` tree is
  untracked, so the runner has no git baseline; the new test file lives inside the already-untracked
  `backend/tests/unit/evaluation/`.)
* No commit, push, deploy, revert or stash; no existing change was discarded; the five other runners
  were not modified (re-verified: `run_phase3e_validation` 9, `run_phase3f_evaluation` 10,
  `run_phase4b_evaluation` 10 raw `DELETE FROM` statements, unchanged).

**Content digests** (the runner is untracked, so the pre-change content is recoverable only from the
Step 0.5 report's citations and the pre-existing `deletes=7` pin):

```
da131f427bc7068c938f3ac0c2609fe85d85d973e9783c08fa649d7459b57605  evaluation/experiments/run_phase3e_integration.py
d20e12c37fd09e2a9cef9331559d7eccc34d9ae75fb69a3596ff20cc2a64b6ac  tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py
03235643c69c9cf2735f8ff87a207d34f1fca24db09a26e91f814752cb08eb10  tests/unit/evaluation/test_legacy_runner_isolation.py
```

---

## 6. Remaining limitations and follow-up tasks

1. **Not executed against PostgreSQL.** The scope semantics are proven on SQLite; PostgreSQL binding is
   inferred from a sibling precedent. A future isolated-database run that observes a foreign user's
   rows surviving this harness's cleanup would close this.
2. **Interrupted runs leak rows.** Because the two user emails carry a random 8-hex suffix, a later run
   cannot recognise an earlier run's leftovers, and **no safe pre-run sweep exists** — a
   `phase3e_%`-prefix sweep would delete a concurrent run's live data, which is exactly the class of
   defect remediated in Step 0.8. Fixing this properly means giving the harness a deterministic
   identity (or a run-id marker) *plus* a documented single-run policy; that is a design decision, not
   a cleanup tweak, and was deliberately not taken here.
3. **The pattern persists in three runners** (Step 0.5 F-1, second half): raw counts still
   `run_phase3e_validation.py` (9), `run_phase3f_evaluation.py` (10), `run_phase4b_evaluation.py` (10).
   Each needs the same treatment, one at a time, with its own report — explicitly **not** started here.
4. **The thirty-eight (38) `check(...)` assertions and the ten steps are unchanged but were never executed
   end-to-end** against a live stack, so the *harness* remains unverified; only its cleanup boundary
   and surface are.
5. **Uploads still go to the application storage root** (`save_upload` through the real route, Step 0.5
   F-4) — unchanged by this task; the report output is console-only (no report files), also unchanged.
6. **Provenance (F-5) untouched:** a run on this dirty, largely untracked tree still cannot be
   reproduced from a manifest.
7. **F-2/F-6/F-7/F-9/F-10/F-11/F-12/F-13/F-14** from the Step 0.5 audit remain open; nothing here
   addresses them.

---

## 7. Operational agent and specialist role templates

Operational agent: **COORDINATOR**, acting directly. This repository's runtime provides one coding
agent plus file/code search helpers — no separate runtime agents implementing the specialist templates
exist, so none was invoked and none is claimed.

| # | Role template | Where its concern is answered |
|---|---|---|
| 8 | Software Architect | §3 (two module-local helpers; no framework; call sites and commit boundaries preserved) |
| 11 | Database Architect | §2 (ownership keys from the models), §3 (FK-safe order) |
| 14 / 72 | Security Architect / Application Security | §1 (blast radius), §5 (guard ordering, credential-free messages) |
| 17 | Backend Coding Specialist | §3 (the exact change) |
| 39 | Model Evaluation Specialist | §3/§4 (ten-step protocol and all checks preserved; no metric change) |
| 51 / 53 | Test Architect / Integration Testing | §4 (behavioural SQLite tests; the inference/execution boundary) |
| 58 | Security Testing | §4 (refusal tests with the engine factory spied on) |
| 59 | Code Review | §3, §8 (files changed, final scope verification) |
| 60 | Debugging | §1 (failure mode), §4 (the pre-existing pin that had to change, and why) |
| 61 | Reliability Engineer | §4 (repeat-cleanup safety), §6 (leakage, remaining risks) |
| 79 / 81 | Documentation / Architecture Documentation | this report, `evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64 |
| 82 | Codebase Knowledge | §2 (inspection record), §6 (inventory of what still carries the pattern) |
| 89 | Database Optimization | §2/§3 (narrowest correct predicate; index-supported keys) |

---

## 8. Files changed and final scope verification

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase3e_integration.py` | `owned_user_ids` + `cleanup_harness_rows` added (L64/L81); final, step-8 and step-9 cleanup sites replaced; `delete` imported, unused `text` removed; guard `operation` text updated | remove the unpredicated chunk delete; make every deletion ownership-scoped, FK-safe and testable |
| `tests/unit/evaluation/test_phase3e_integration_cleanup_scope.py` | **new** (16 tests) | behavioural proof of the scope, prefix-vs-exact-email ownership, repeat-safety, guard ordering, preserved surface |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | this runner's spec gains `scoped_cleanup=True`; docstring notes both Step 0.8 and Step 0.9 exceptions | the Step 0.6 count pin forbade the fix; replaced with a stricter contract (§4) |
| `evaluation/README.md` | new subsection "Phase 3E integration runner — scoped cleanup (Step 0.9, 2026-10-09)" | document the ownership boundary and what is verified |
| `architecture/STEP0_9_PHASE3E_INTEGRATION_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

**Not changed:** the five other runners; the Step 0 / 0.5 / 0.6 / 0.7 / 0.8 reports (append-only
historical evidence — their description of R4 remains an accurate record of the pre-remediation code);
no production module; no migration; no fixture; no benchmark, weight, `.env` or historical report.

**Verification of the final tree:** `git status` shows the same 384 entries / 34 modified tracked files
as before the task; the only files this step touched are the six above; all six were re-read after
editing; the changed Python file compiles and the test suites were re-run after the last code edit
(the 806-passed `tests/unit` run in §4 is the final one — only Markdown changed afterwards);
protected artifacts and `backend/uploads/` are unchanged (§5). No commit, push, deploy, revert or
stash was performed.

**Stop point.** Step 0.9 is complete for `run_phase3e_integration.py` only. No other runner was
inspected, remediated or reported, and Step 1.0 was not begun, pending review.
