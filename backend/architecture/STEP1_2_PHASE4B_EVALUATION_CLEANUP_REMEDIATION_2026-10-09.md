# Step 1.2 — Phase 4B Evaluation Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent). The specialist roles listed in the task
(8, 11, 14, 17, 39, 51, 53, 58, 59, 60, 61, 72, 79, 81, 82, 89) are **role templates**, not separate
runtime agents the runtime provides. No sub-agent was invoked and none is claimed; §7 maps each role to
the section that answers its concern.
**Scope:** classify and remediate every destructive statement in
`backend/evaluation/experiments/run_phase4b_evaluation.py` (Step 0.5 finding **F-1**, last runner of the
set), replacing unsafe cleanup with narrowly scoped, ownership-backed ORM operations, plus focused
regression tests.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` §R7 / **F-1**, the Step 0.6 isolation
remediation (documented in `evaluation/README.md`), and
`STEP0_7_…` / `STEP0_8_…` / `STEP0_9_…` / `STEP1_0_…` / `STEP1_1_…` (F-3, and F-1 for the five runners
remediated before this one).

**Explicitly out of scope (not touched):** `run_phase3d_evaluation.py`,
`run_phase3d_upload_integration.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`,
`run_phase3f_evaluation.py` (all previously remediated), and every production module.

---

## 1. Original destructive cleanup statements, classified individually

`run_phase4b_evaluation.py` contained **ten** raw `DELETE FROM` statements in two blocks. The count is
pinned by the pre-existing Step 0.6 test (`RUNNERS["run_phase4b_evaluation"].deletes == 10`), by the
Step 0.7 report's citation of this runner as still carrying the pattern (`L689–694`, `L831–834`), and
by the pre-change inspection recorded in the new test file's header at the moment of the edit. The file
is **untracked** (`backend/evaluation/**` has no git baseline), so no `git show` of the old content
exists; the record below is the contemporaneous whole-file inspection, and every statement in it was
seen before any edit was made.

| # | old line | statement | predicate | execution path | risk class |
|---|---|---|---|---|---|
| 1 | L689 | `DELETE FROM reliability_logs` | **none** | pre-run "Clean" block | database-wide destructive |
| 2 | L690 | `DELETE FROM chat_messages` | **none** | pre-run "Clean" block | database-wide destructive |
| 3 | L691 | `DELETE FROM chat_sessions` | **none** | pre-run "Clean" block | database-wide destructive |
| 4 | L692 | `DELETE FROM document_chunks` | **none** | pre-run "Clean" block | database-wide destructive — removes **every chunk and its embedding** of every owner |
| 5 | L693 | `DELETE FROM documents` | **none** | pre-run "Clean" block | database-wide destructive — documents of every user |
| 6 | L694 | `DELETE FROM users WHERE email LIKE 'phase4b_%'` | **email prefix** | pre-run "Clean" block | pattern-scoped, not ownership-scoped; cascade-dependent |
| 7 | L831 | `DELETE FROM reliability_logs` | **none** | post-report "Cleanup" block | database-wide destructive |
| 8 | L832 | `DELETE FROM document_chunks` | **none** | post-report "Cleanup" block | database-wide destructive (all owners' chunks + embeddings) |
| 9 | L833 | `DELETE FROM documents` | **none** | post-report "Cleanup" block | database-wide destructive |
| 10 | L834 | `DELETE FROM users WHERE email LIKE 'phase4b_%'` | **email prefix** | post-report "Cleanup" block | pattern-scoped, cascade-dependent |

**The ten statements are not equally risky, and they are not one pattern:**

* **Eight unpredicated table deletes (1–5, 7–9).** Run against the shared isolated database the
  project's workflow points every runner at (`DOCUMIND_INTEGRATION_DATABASE_URL`), they remove **every
  row** of `reliability_logs`, `chat_messages`, `chat_sessions`, `document_chunks` and `documents`
  *before the run starts* and three of those tables again after it. The pre-run block is the worse of
  the two: it destroys data that has nothing to do with this harness in order to make the harness's own
  previous run look absent, which is exactly why it survived review — it reads as harmless setup.
* **`document_chunks` (4, 8) is the most damaging single statement.** A chunk carries the embedding and
  the provenance a foreign experiment needs; deleting it does not merely unlink evidence, it forces
  re-ingestion. Statements 4 and 8 are therefore classified higher than the log/chat pair even though
  all five table deletes share the "no predicate" class.
* **Two prefix-scoped user deletes (6, 10).** `email LIKE 'phase4b_%'` is narrower than the table
  deletes but is still not ownership: a pattern is not an identity, and both statements relied on
  `ON DELETE CASCADE` to remove the matched users' own documents, chunks, logs and chat rows. This also
  matched the sibling `phase4b_extra_*`-style user the tests use as a decoy.

**Why isolation alone did not mitigate this.** The Step 0.6 guard
(`evaluation/isolation.py::assert_safe_evaluation_target`) proves the target is *not the application
database*; it cannot prove the target is *empty* or *exclusively yours*. Severity per the Step 0.5
rubric (F-1/R7): **Critical** for the unpredicated deletes, **High** for the prefix pair.

**Non-destructive operations inspected and deliberately left alone:**

* `save_upload(...)` inside `ingest_corpus` — a **write** into the application upload root (Step 0.5
  **F-4**); this runner has no deletion counterpart and none was added (scope boundary, §6).
* `tempfile.TemporaryDirectory()` — the harness's own scratch corpus inputs; Python removes them. No
  `os.unlink` / `shutil.rmtree` appears anywhere in the file.
* **No read-only raw SQL exists in this runner** — every `text()` occurrence was one of the ten
  deletes, so the conversion leaves **zero** `text(...)` calls and the `text` import is gone. (Where a
  runner legitimately keeps read-only diagnostics — Phase 3E validation, Step 1.0 — they were
  preserved; that does not apply here.)

---

## 2. Evidence-backed ownership boundary

**Boundary: the two user ids this harness creates — and no other row.**

| Question | Where it was answered |
|---|---|
| Every destructive statement and file operation | whole-file read (pre-change 934 → post-change 1024 lines); the two blocks in §1; `save_upload` (write, no delete); `TemporaryDirectory` (own scratch) |
| Records created | two users — `phase4b_legacy@test.local` (legacy chunker; arms A and B) and `phase4b_candidate@test.local` (structure-v2; arm C) — each owning a full ingested corpus (documents + chunks + embeddings), plus the `reliability_logs` / `chat_sessions` / `chat_messages` written while running an arm |
| Ownership keys (schema) | `documents/models.py`: `Document.user_id → users.id` (`ondelete="CASCADE"`, indexed), `DocumentChunk.document_id → documents.id` (CASCADE, indexed) — **a chunk has no owner column**; `reliability/models.py`: `ReliabilityLog.user_id → users.id` (CASCADE); `chat/models.py`: `ChatSession.user_id → users.id` (CASCADE), `ChatMessage.session_id → chat_sessions.id` — **a message has no owner column** |
| Ownership marker | the **deterministic** addresses `phase4b_<label>@test.local` (`HARNESS_LABELS = ("legacy", "candidate")`) used by the ingest loop when it creates each `User` |
| Existing scoped precedent | `run_dual_path_ablation.py`'s document-scoped chunk delete; the Step 0.7/0.8/0.9/1.0/1.1 helpers (`owned_user_ids` + `cleanup_harness_rows`) |
| Existing regression tests | the Step 0.6 spec pinned the guard and the statement *count*, never the scope; nothing referenced this runner's cleanup |
| Guard + prior contracts | `evaluation/isolation.py`; Steps 0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1 reports; the current `evaluation/README.md` |
| Working tree | dirty and largely untracked (`backend/evaluation/**` has **no git baseline**); nothing was discarded, reverted or reorganised |

**What determinism buys, and what it does not.** Because the addresses are deterministic, this runner
*keeps* its original "clean previous runs" intent safely: a re-run finds the leftovers of an interrupted
earlier run by **exact email** and removes exactly those rows — an improvement over the Phase 3D/3E
remediations, whose random-suffix emails left interrupted runs unrecoverable. The residual hazard (§6)
is that two **concurrent** instances share those identities, so the second instance's pre-run sweep
would delete the first's live rows. **No concurrency safety is claimed** — the original prefix block had
the same hazard (and, on top of it, wiped whole tables).

**Explicitly rejected:** the `phase4b_%` prefix as a sweep key, and any wider scope. The pre-run sweep
uses the exact two addresses.

---

## 3. Exact implementation changes

One evaluation runner changed. **No** schema, corpus, question, metric, retrieval, protocol, CLI,
transaction or report-format change: every edited region is outside the evaluation body, so arms A/B/C,
`TOP_K = 5`, the 21 summary metric keys, the failure distribution and the
`phase4b_evaluation_report.json` schema are untouched — pinned by the new tests' source assertions on
the protocol markers, metric key list, report path, corpus entry points and exit code.

`backend/evaluation/experiments/run_phase4b_evaluation.py` (934 → 1024 lines):

| # | Site | Before | After |
|---|---|---|---|
| 1 | new `HARNESS_LABELS` / `harness_user_email(label)` / `HARNESS_USER_EMAILS` (L679–685) | the email was built inline in the ingest loop | single source of truth for the harness's identity; the ingest loop now calls `harness_user_email(label)` |
| 2 | new helper `owned_user_ids(db, *, emails)` (L687) | — | ids of the users this harness owns, by **exact email** |
| 3 | new helper `cleanup_harness_rows(db, *, user_ids)` (L697) | — | the only deletion implementation; model-bound, FK-safe order, early return on an empty id set |
| 4 | pre-run "Clean" block (old L689–694) | six raw statements: five **unpredicated** table deletes + `users WHERE email LIKE 'phase4b_%'` | `previous_users = await owned_user_ids(db, emails=HARNESS_USER_EMAILS)` → `if previous_users: await cleanup_harness_rows(db, user_ids=previous_users)` → `await db.commit()` (L831–834) — the same "clean previous runs" intent, narrowed to the harness's own two users |
| 5 | post-report "Cleanup" block (old L831–834) | four raw statements: three **unpredicated** table deletes + the prefix user delete | `await cleanup_harness_rows(db, user_ids=list(users.values()))` + `await db.commit()` (L969–971) |
| 6 | imports of `main()` | `from sqlalchemy import text` (needed only by the deletes) | removed — the file now contains **no raw SQL call at all** |
| 7 | guard `operation=` text | "…(it deletes rows, including unscoped deletes)" | "the Phase 4B evaluation harness (it deletes rows **it owns**)" |

The helper's body (identical in shape to Steps 0.8–1.1, so the six remediated runners share one
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

Design notes:

* **Model-bound, not raw SQL** — the predicates bind through the dialect's UUID handling, which is what
  lets the same statements be exercised on SQLite by the tests; a raw `WHERE user_id = :u` with a `str`
  parameter would silently match nothing there.
* **Empty scope is an explicit no-op** (`if not ids: return`), so "nothing of mine is present" can never
  degenerate into an unpredicated delete — asserted behaviourally.
* **FK-safe and cascade-independent:** logs → messages → sessions → chunks → documents → users; nothing
  relies on `ON DELETE CASCADE` for a row it claims to delete (the two prefix statements did).
* **No framework:** two module-local functions in the runner that uses them; the caller keeps the commit,
  exactly as before.
* **Guard ordering preserved:** `assert_safe_evaluation_target(...)` (L780) precedes
  `os.environ["DATABASE_URL"] = evaluation_dsn` (L793), `create_async_engine(evaluation_dsn)` (L807) and
  both cleanup call sites (L831, L970). No module-level `DATABASE_URL` default exists.
* **Not a general cleanup framework:** nothing outside this runner imports these helpers.

---

## 4. Regression tests and actual results

New file `tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py` (**19 tests**, 499 lines) —
6 behavioural scope tests, 6 source/AST tests, 3 guard tests, 4 interface tests. All commands were run
from `backend/` with `./venv/Scripts/python.exe`. **Nothing below connects to PostgreSQL, to the
application database, or to any database at all** — the behavioural tests run against the suite's
in-memory SQLite fixtures (with `PRAGMA foreign_keys=ON`, via `tests/fixtures/graph_data.py` builders),
and the guard tests stop before any engine exists.

| Command | Result |
|---|---|
| `python -m py_compile evaluation/experiments/run_phase4b_evaluation.py` | OK, exit **0** |
| `python -m compileall -q evaluation/experiments/run_phase4b_evaluation.py tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py tests/unit/evaluation/test_legacy_runner_isolation.py` | OK, exit **0** |
| `python -m pytest -q tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py` | **19 passed**, exit **0** (4.83 s) |
| `python -m pytest -q tests/unit/evaluation/test_legacy_runner_isolation.py` | **70 passed**, exit **0** (21.82 s) |
| `python -m pytest -q tests/unit/evaluation` | **357 passed**, exit **0** (47.11 s) — 338 before this change |
| `python -m pytest -q tests/unit` | **860 passed**, exit **0** (76.27 s) — 841 before this change |

No test failed in this step; every count above is the raw pytest summary of the command as run
(`+19` in both suites is exactly the new file). The only warnings are the pre-existing `pytest-asyncio`
deprecation warnings present in every suite run.

| Required coverage (task §5) | Test(s) | Evidence type |
|---|---|---|
| **Exact ownership selection** | `test_ownership_is_selected_by_the_exact_emails` — both harness addresses plus a decoy sibling (`phase4b_extra_cafe1234@test.local`, which the old prefix *would* have matched) and an unrelated user; exactly the two harness ids are returned | **executed** (SQLite) |
| **Owned records are removed** | `test_owned_records_are_removed`, `test_both_owned_users_are_cleaned_in_one_sweep` — all six tables drop to 0 for one user and for both users in one sweep | **executed** (SQLite) |
| **Unrelated users and their records survive** | `test_unrelated_users_and_their_records_survive` — the prefix-sharing sibling and a `phase3f_legacy@test.local` user keep row counts, chunk **ids**, chat rows and logs | **executed** (SQLite) |
| **Repeated cleanup is safe** | `test_repeated_cleanup_is_safe_and_does_not_spread` — twice, no error; the second sweep finds no owned users | **executed** (SQLite) |
| **Empty ownership sets do not trigger broad deletion** | `test_an_empty_ownership_set_is_a_no_op` — `user_ids=[]` leaves every foreign row intact | **executed** (SQLite) |
| **Dependent rows are deleted in the correct order** | `test_dependent_rows_are_deleted_before_their_parents` (log → message → session → chunk → document → user, from the helper source) | source/AST |
| **Cleanup call sites use the intended scoped helpers** | `test_both_cleanup_call_sites_use_the_scoped_helpers`, `test_ownership_identity_is_single_sourced`, `test_own_cleanup_is_keyed_on_the_user_id_set` | source |
| **No unscoped destructive statement remains** | `test_no_raw_destructive_sql_exists` (AST over every `text(...)` literal, **f-strings included**: none contains `DELETE`/`TRUNCATE`/`UPDATE`/`INSERT`/`DROP`), `test_the_runner_no_longer_imports_text_at_all` (zero `text()` calls) | AST |
| **SQL-literal checks detect destructive statements in plain strings and f-strings** | the `_raw_sql_statements()` / `_literal()` collectors in the new file read `ast.Constant` **and** `ast.JoinedStr` parts (same collector shape as the Step 0.8–1.1 tests); the runner has no `text()` call left to hide one in | AST |
| **…and the collector itself was exercised, not only inspected** | a one-off probe (run from `backend/`, no repo file created) substituted a synthetic module containing `text("DELETE FROM chat_messages")`, `text(f"DELETE FROM {tbl}")` and `text("SELECT 1")` for `runner` and called the real `_raw_sql_statements()`: collected `['DELETE FROM chat_messages', 'DELETE FROM ', 'SELECT 1']`, flagged the first two as destructive and left the `SELECT` alone — exit **0**, assertions inside the probe | **executed** (in-process, no database) |
| **Isolation guard precedes engine creation and cleanup** | `test_no_explicit_target_is_refused_before_any_engine` (engine factory spied on; `seen == []`; credential-free message), `test_application_database_is_refused_as_an_explicit_target` (`REFUSING`), `test_the_guard_precedes_the_engine_and_both_cleanups_in_the_source` | **executed** (no connection possible) + source |
| **Evaluation protocol, metrics, CLI, report behaviour, entry points intact** | `test_protocol_markers_and_report_path_are_unchanged`, `test_metric_protocol_and_arms_are_unchanged`, `test_corpus_and_failure_analysis_entry_points_still_exist`, `test_exit_code_and_entry_points_still_behave` (exit `0`, `--database-url`, coroutine entry points, `harness_user_email`) | source + interface |

**One pre-existing test was updated, deliberately.** `test_legacy_runner_isolation.py` pinned
`source.count("DELETE FROM") == 10` for this runner — a pin asserting exactly the code this task had to
remove. This runner's spec now carries `scoped_cleanup=True` and the branch verifies the **stricter** new
contract (`_raw_sql_delete_literals(module) == []` over `text(...)` literals, f-strings included, no
`text("DELETE`, helper defined and used), while `deletes=10` is retained as the audit record of the
pre-remediation count. No assertion was weakened, skipped or deleted. With this runner converted, **all
five legacy runners tracked by that spec pin the no-raw-SQL contract**.

**Deliberately not executed (therefore not claimed as verified):**

* the harness itself — it ingests a full corpus, needs the QA model, real chunkers/embeddings and
  PostgreSQL + pgvector, which this task is neither authorised nor provisioned to run;
* `tests/integration` / `tests/e2e` (they write into the application upload root — Step 0.5 F-4), so the
  full suite was not run;
* no migration, no database create/drop/downgrade, no destructive evaluation, and **the Phase 4B runner
  was never executed against any database**.

**Evidence boundary, stated plainly.** The scope semantics (which rows are selected, and that foreign
rows survive) are proven **behaviourally on SQLite**. Ordering, call-site coverage and the absence of raw
destructive SQL are **source/AST** evidence. **No PostgreSQL execution was performed**, so the
PostgreSQL binding of the new predicates is *inferred*, not measured — from the identical,
already-PostgreSQL-executed pattern in `run_dual_path_ablation.py` and from the dialect-neutral SQLAlchemy
constructs.

---

## 5. Database isolation and protected-artifact verification

| Artifact | Observed (after every test run) |
|---|---|
| `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | 2026-09-21 02:58 (frozen benchmark, untouched) |
| `models/documind-qa/model.safetensors` | 2026-09-02 02:52 (QA weights, untouched) |
| `evaluation/reports/ablation_A.json` | 2026-10-04 18:16 (untouched); `evaluation/reports/` listing digest `md5 e8d577977cb0d3683afb391cb79a1595` (same as Steps 0.7–1.1) |
| `backend/.env` / `backend/.env.example` | 2026-10-06 07:53 / 2026-09-27 10:00 (untouched) |
| `backend/uploads/` | **1 112** entries (unchanged before/after; nothing deleted or regenerated) |

* **No database was contacted, created, migrated, dropped or queried**, and the harness was not executed.
  The guard tests assert the refusal happens with `create_async_engine` never reached.
* **Guard ordering unchanged and pinned** (see §3): guard L780 < engine L807 < cleanups L831/L970.
* **Working-tree baseline unchanged in size:** `git status --porcelain` → **384** entries, **34**
  modified tracked files — identical to the pre-task count recorded in Step 1.1; no path was deleted,
  reverted, stashed or reorganised.

**Content digests** (the runner and its tests are untracked, so the pre-change content is recoverable
only from the §1 inspection record, the Step 0.5/0.7 citations and the pre-existing `deletes=10` pin):

```
014dc53922abd472950d35ca5d15ab4ec94d69106d5be3c23d54ceaffb0b86cd  evaluation/experiments/run_phase4b_evaluation.py
7de43d96543845db08312e991d74af5712e958f055d11fc73ad6deba97baf24a  tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py
961765040be209d5d6bf692aaec94531883a78dae2c4a0db45cad070951e2b38  tests/unit/evaluation/test_legacy_runner_isolation.py
64e5b2fd22770e34ff2150f254c336088fa1d64970b41dd9eea99da114089868  evaluation/experiments/run_phase3d_upload_integration.py  (unchanged since Step 0.7)
```

---

## 6. Remaining risks and follow-up work

1. **No PostgreSQL execution.** Scope semantics are proven on SQLite; PostgreSQL binding is inferred. A
   future isolated-database run that observes a foreign user's documents, chunks and logs surviving this
   harness's pre-run and final cleanups would close this.
2. **Concurrency caveat (pre-existing, unchanged in kind).** The two evaluation emails are deterministic,
   so two *concurrent* instances sharing one isolated database share identities: the second instance's
   pre-run sweep would delete the first's live rows. **No concurrency safety is claimed.** Mitigation is
   operational (one instance at a time per database); a stronger fix (run-id-scoped identities) is a
   design decision, not a cleanup tweak.
3. **Interrupted runs:** this harness *does* recover its own leftovers via the exact-email pre-run sweep,
   for the two known labels and only if the next run uses the same code version.
4. **Upload-root growth (F-4) unchanged:** `save_upload` writes every corpus document into the
   application storage root and nothing removes those stored copies; the harness's own corpus scratch is
   handled by `tempfile.TemporaryDirectory`. Not in scope here, still open.
5. **The harness itself remains unexecuted** — arms, metrics and reporting are unchanged and pinned, but
   no live run was performed, so the *evaluation results* it produces are unverified in this step.
6. **Provenance (F-5) untouched:** a run on this dirty, largely untracked tree still cannot be
   reproduced from a manifest.
7. **`run_phase3d_upload_integration.py` retains one email-scoped raw-SQL block** (the "cleanup the extra
   users" site, four `text("DELETE … WHERE … email = :e")` statements). It is **not** unscoped — each
   predicate is an exact-email subquery — and it is already documented in the Step 0.7 README section
   ("the two extra users … are still removed by the earlier email-scoped block"), but it does not follow
   the model-bound convention. It was **not** touched here (Phase 3D runner, out of scope) and is
   recorded as a follow-up.
8. **The remediation inventory for Step 0.5 finding F-1 (second half) is now complete**: the six runners
   that carried raw/unscoped cleanup — `run_phase3d_upload_integration`, `run_phase3d_evaluation`,
   `run_phase3e_integration`, `run_phase3e_validation`, `run_phase3f_evaluation`,
   `run_phase4b_evaluation` — all have scoped cleanup, each with its own report
   (Steps 0.7, 0.8, 0.9, 1.0, 1.1, 1.2). **That is not a claim that the evaluation system is safe:**
   F-2 (uninstrumented runners writing fixed historical reports / targeting the app DB directly),
   F-4 (upload-root leakage), F-5 (manifest source digests), F-6…F-14 from the Step 0.5 audit remain
   open, and no runner's post-connection behaviour has been re-demonstrated on PostgreSQL.
9. **Cleanup is still success-path only** for the runners that never had a `finally` cleanup — including
   this one: an exception mid-run leaves that run's rows in place (recoverable here by the next run's
   exact-email sweep). Pre-existing behaviour, unchanged.

---

## 7. Operational agent and specialist role-template mapping

Operational agent: **COORDINATOR**, acting directly. The runtime provides one coding agent plus
file/code-search helpers; the specialist roles are templates, and none is claimed as an independent
runtime agent.

| # | Role template | Where its concern is answered |
|---|---|---|
| 8 | Software Architect | §3 (two module-local helpers; no framework; call sites and commit boundaries preserved) |
| 11 | Database Architect | §2 (ownership keys from the models), §3 (FK-safe, cascade-independent order) |
| 14 / 72 | Security Architect / Application Security | §1 (blast radius and per-statement classification), §5 (guard ordering) |
| 17 | Backend Coding Engineer | §3 (exact change, incl. removing the now-unused `text` import) |
| 39 | Model Evaluation Engineer | §3/§4 (arms, metrics, protocol markers, report path unchanged; no metric change) |
| 51 / 53 | Test Architect / Integration Testing | §4 (behavioural SQLite tests; the explicit SQLite-vs-PostgreSQL boundary) |
| 58 | Security Testing | §4 (refusal tests with the engine factory spied on; f-string-aware AST pin) |
| 59 | Code Review | §3, §8 (files changed; one pre-existing pin updated and explained) |
| 60 | Debugging | §1 (failure-mode classification), §6 (what remains, runner by runner) |
| 61 | Reliability Engineer | §4 (repeat-cleanup and empty-set safety), §6 (concurrency, interrupted runs, F-4) |
| 79 / 81 | Documentation / Architecture Documentation | this report, `evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64 |
| 82 | Codebase Knowledge | §2 (inspection record), §6/§9 (inventory status) |
| 89 | Database Optimization | §2/§3 (narrowest correct predicate; index-supported keys) |

---

## 8. Final diff and scope verification

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase4b_evaluation.py` | ownership constants + `owned_user_ids` + `cleanup_harness_rows` added (L679–755); both cleanup blocks replaced (L831–834, L969–971); ingest loop single-sourced; unused `text` import removed; guard `operation` text updated | remove eight unpredicated deletes and two prefix deletes; keep the "clean previous runs" intent with an exact-email scope |
| `tests/unit/evaluation/test_phase4b_evaluation_cleanup_scope.py` | **new** (19 tests) | behavioural proof of scope, exact-email ownership, empty-set safety, repeat-safety, guard ordering, preserved protocol/metrics/interfaces |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | this runner's spec gains `scoped_cleanup=True`; docstring records the Step 1.2 exception | the count pin forbade the fix; replaced by the stricter literal-level contract |
| `evaluation/README.md` | new "Phase 4B evaluation runner — scoped cleanup (Step 1.2, 2026-10-09)" section; the outstanding-runner list updated and qualified | document the boundary, what is verified, and what is *not* thereby safe |
| `architecture/STEP1_2_PHASE4B_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

**Not changed:** the five previously remediated runners (digest-checked: `run_phase3d_upload_integration.py`
still hashes to its Step 0.7 value `64e5b2fd…`); the Step 0–1.1 reports (append-only historical evidence);
no production module; no migration; no fixture; no benchmark, weight, `.env` or historical report;
nothing under `backend/uploads/`.

**Verification of the final tree:** `git status` shows the same 384 entries / 34 modified tracked files as
before the task; the only files this step touched are the six above; the changed Python files compile and
the suites in §4 were re-run after the last code edit (only Markdown changed afterwards). No commit, push,
deploy, revert or stash was performed. The Phase 4B runner was **not** executed.

**Stop point.** Step 1.2 is complete for `run_phase4b_evaluation.py` only. No new remediation step was
begun, and no other runner was modified.

---

## 9. Inspection record and acceptance criteria

**Inspection record (Phase A, performed before any edit):**

| Item | Finding |
|---|---|
| Imports | module-level: standard library, `evaluation.isolation` (guard helpers), corpus builders; inside `main()`: sqlalchemy engine/session, all models, `documents.chunking`, `passlib` |
| Isolation guard | `assert_safe_evaluation_target(...)` with operation text naming deletes; `os.environ["DATABASE_URL"]` set only after it; engine created after that — guard first in every path |
| DB URL handling | `--database-url` → `DOCUMIND_INTEGRATION_DATABASE_URL` → refusal; no hard-coded DSN, no import-time `DATABASE_URL` default (only `DOCUMIND_DEV` / `QA_MODEL_NAME` defaults remain) |
| Engine / session | one `create_async_engine(evaluation_dsn)` + `async_sessionmaker`; short-lived `async with session_factory() as db:` blocks, each committing its own work |
| Users/documents created | 2 users (`legacy`, `candidate`), one full corpus each (documents + chunks + embeddings) through `ingest_corpus` |
| Cleanup sites | two blocks (pre-run "Clean" and post-report "Cleanup"), 6 + 4 raw statements (§1) |
| Transaction boundaries | each block commits; the report is written between them; `engine.dispose()` after |
| Failure/interruption paths | no `try/finally` cleanup in `main()`: an exception leaves that run's rows (recoverable by the next run's exact-email sweep); no `os.unlink`/`rmtree` anywhere |
| Exit behaviour | prints the summary and `return 0`; `__main__` raises `SystemExit(asyncio.run(main()))` |
| Read-only diagnostics | none — every `text()` call was a delete |
| Pre-change record | 10 `DELETE FROM` statements (6 + 4); protocol markers `PHASE 4B — QA EVALUATION EXPANSION`, `warm-up complete`, per-arm banner, `wrote …`; `TOP_K = 5`; arms A/B/C; report `phase4b_evaluation_report.json`; CLI `--database-url` |
| Prior-contract consistency | same helper names/shape and same FK order as Steps 0.8–1.1; the Step 0.6 spec's `deletes=10` pin noted as the pre-change record |

**Acceptance-criteria check**

| Criterion | Status |
|---|---|
| All 10 original destructive statements individually inspected and classified | ✅ (§1 table; 8 unpredicated, 2 prefix-scoped; nothing else destructive in the file) |
| Unsafe cleanup replaced with narrowly scoped, ownership-backed operations | ✅ (10 raw statements → 2 helper call sites over the harness's own two user ids) |
| Focused behavioural regression tests pass | ✅ (19 tests, exit 0) |
| Relevant evaluation and full unit suites recorded | ✅ (`tests/unit/evaluation` 357, `tests/unit` 860, isolation 70 — all exit 0) |
| Compilation checks pass | ✅ (`py_compile` + `compileall`, exit 0) |
| SQL-safety assertions cover f-string literals | ✅ (AST collector reads `JoinedStr` parts; asserted `{}` result on the runner, and the collector was behaviourally probed against a plain-string **and** an f-string `DELETE` — both flagged, `SELECT` ignored; §4) |
| Isolation guard and evaluation behaviour remain intact | ✅ (guard L780 < engine L807 < cleanups; markers, metrics, arms, report path, CLI, exit code pinned) |
| Protected artifacts and unrelated changes unchanged | ✅ (§5) |
| Report, README entry and project-context pointer present and accurate | ✅ (§8) |
| PostgreSQL and other unverified behaviour explicitly identified | ✅ (§4 evidence boundary, §6.1) |
| No unrelated runner or product functionality modified | ✅ (§8 digest check + final diff) |
| Remediation inventory status stated honestly | ✅ (§6.8–6.9: F-1 second half complete; the evaluation system is **not** thereby declared safe) |
