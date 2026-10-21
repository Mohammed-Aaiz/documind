# Step 1.1 — Phase 3F Evaluation Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent). The specialist roles listed in the task
(8, 11, 14, 17, 39, 51, 53, 58, 59, 60, 61, 72, 79, 81, 82, 89) are **role templates**, not separate
runtime agents the runtime provides. No sub-agent was invoked and none is claimed; §7 maps each role to
the section that answers its concern.
**Scope:** classify and remediate every destructive statement in
`backend/evaluation/experiments/run_phase3f_evaluation.py` (Step 0.5 finding **F-1**), replacing unsafe
cleanup with narrowly scoped, ownership-backed ORM operations, plus focused regression tests.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (§4 "R6 — UNSAFE"), the Step 0.6 isolation
remediation (documented in `evaluation/README.md`), and
`STEP0_7_…`/`STEP0_8_…`/`STEP0_9_…`/`STEP1_0_…` (F-3, and F-1 for the three runners before this one).

**Explicitly out of scope (not touched):** `run_phase3d_evaluation.py`,
`run_phase3d_upload_integration.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py` (all
previously remediated), and `run_phase4b_evaluation.py` — the **last** remaining runner with raw
deletes (10), reserved for the next step.

---

## 1. Original destructive cleanup patterns, classified

`run_phase3f_evaluation.py` (1111 lines before this change) contained **ten** raw `DELETE FROM`
statements in two blocks. The count is pinned by the pre-existing Step 0.6 test
(`RUNNERS["run_phase3f_evaluation"].deletes == 10`), and it decomposes as 6 + 4. **The ten statements
do not carry equal risk**, so each is classified below rather than treated as one pattern.

| # | old line | statement | predicate | execution path | risk class |
|---|---|---|---|---|---|
| 1 | L755 | `DELETE FROM reliability_logs` | **none** | before ingest ("Clean") | database-wide destructive |
| 2 | L756 | `DELETE FROM chat_messages` | **none** | before ingest | database-wide destructive |
| 3 | L757 | `DELETE FROM chat_sessions` | **none** | before ingest | database-wide destructive |
| 4 | L758 | `DELETE FROM document_chunks` | **none** | before ingest | database-wide destructive (all owners' chunks **and their embeddings**) |
| 5 | L759 | `DELETE FROM documents` | **none** | before ingest | database-wide destructive (documents of every user) |
| 6 | L760 | `DELETE FROM users WHERE email LIKE 'phase3f_%'` | **email prefix** | before ingest | pattern-scoped, not ownership-scoped; also broader than the harness's own two users |
| 7 | L945 | `DELETE FROM reliability_logs` | **none** | after the report is written | database-wide destructive |
| 8 | L946 | `DELETE FROM document_chunks` | **none** | after the report | database-wide destructive |
| 9 | L947 | `DELETE FROM documents` | **none** | after the report | database-wide destructive |
| 10 | L948 | `DELETE FROM users WHERE email LIKE 'phase3f_%'` | **email prefix** | after the report | pattern-scoped, cascade-dependent |

**Why this is the highest-blast-radius runner of the set.** Eight of the ten statements have no
predicate at all: run against the shared isolated database the project's workflow points every runner
at (`DOCUMIND_INTEGRATION_DATABASE_URL`, re-used by `tests/fixtures/db`-style fixtures), they delete
**every row of `reliability_logs`, `chat_messages`, `chat_sessions`, `document_chunks` and
`documents` in that database** — every owner, every document, every chunk — before the run even starts,
and three of those tables again afterwards. `document_chunks` carries the embeddings, so a foreign
experiment's evidence is not merely unlinked but must be re-ingested to be restored. The runner also
*creates* that situation for whoever runs next: the pre-run block makes the harness look "clean" by
deleting everything, which is precisely why the pattern survived review — it was read as harmless
setup.

**The other two statements (6, 10)** use `email LIKE 'phase3f_%'`. That is narrower than the table
deletes but still not ownership: a pattern is not an identity, and it would also match any user whose
address merely begins that way. Both also depended on `ON DELETE CASCADE` to remove the matched users'
own rows.

**Why isolation alone did not mitigate any of this.** The Step 0.6 guard
(`evaluation/isolation.py::assert_safe_evaluation_target`) proves the target is *not the application
database*; it cannot prove the target is *empty* or *exclusively yours*. Severity per the Step 0.5
rubric (R6): High — a credible path to destroying evaluation evidence.

**Non-destructive operations inspected and deliberately left alone:**

* `save_upload(...)` (L270, inside `ingest_corpus`) — a **write** into the application upload root; no
  deletion counterpart exists in this runner (Step 0.5 F-4, unchanged, §6).
* `tempfile.TemporaryDirectory()` (L252) — the harness's **own** scratch inputs; Python removes them,
  and no `os.unlink`/`shutil.rmtree` appears anywhere in the file.
* The runner performs **no read-only raw SQL at all**: every `text()` occurrence in the file was one of
  the ten deletes (the other matches for `text(` are `extract_text(`, `chunk_text(`, `cleaned_text=`,
  `question.text`, `write_text(`, `CryptContext`). There was therefore no diagnostic `text("SELECT …")`
  to preserve — this is asserted in the tests, and §3 states what that means for the conversion.

---

## 2. Evidence-backed ownership boundary

**Boundary: the two user ids this harness creates — and no other row.**

| Question | Where it was answered |
|---|---|
| Every destructive statement and file operation | whole file read (1111 lines); the two blocks in §1; `save_upload` (write), `TemporaryDirectory` (its own scratch) |
| Records created | two users — `phase3f_legacy@test.local` (legacy chunker; arms A and B) and `phase3f_candidate@test.local` (structure-v2; arm C) — each owning a full ingested corpus (documents + chunks), plus any `reliability_logs` / `chat_sessions` / `chat_messages` written while running an arm |
| Ownership keys (schema) | `documents/models.py`: `Document.user_id → users.id` (`ondelete="CASCADE"`, indexed), `DocumentChunk.document_id → documents.id` (CASCADE, indexed) — **a chunk has no owner column**; `reliability/models.py`: `ReliabilityLog.user_id → users.id` (unique, CASCADE); `chat/models.py`: `ChatSession.user_id → users.id`, `ChatMessage.session_id → chat_sessions.id`; `graph/models.py`: `document_graph_edges.document_id` / `document_structure_elements.document_id` (CASCADE) hang off `documents.id` |
| Ownership marker | the **deterministic** emails `phase3f_<label>@test.local` (`HARNESS_LABELS = ("legacy", "candidate")`), created by the ingest loop at L767 (old numbering) — deterministic, unlike the random-suffix emails of the Phase 3D/3E runners |
| Existing scoped precedent | `run_dual_path_ablation.py`'s document-scoped chunk delete; the Step 0.7/0.8/0.9/1.0 helpers (`owned_user_ids` + `cleanup_harness_rows`) |
| Existing regression tests | the Step 0.6 spec pinned the guard and the statement *count*, never the scope; nothing referenced this runner's cleanup |
| Guard + prior contracts | `evaluation/isolation.py`; Steps 0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 reports; the current `evaluation/README.md` |
| Working tree | dirty and largely untracked (`backend/evaluation/**` has **no git baseline**); nothing was discarded, reverted or reorganised |

**What the deterministic emails buy, and what they do not.** Because the addresses are deterministic,
this runner *can* keep its original "clean previous runs" intent safely: a re-run finds the leftovers of
an interrupted earlier run by **exact email** and removes exactly those rows. That is a real improvement
over the Phase 3E remediation steps, whose random-suffix emails left interrupted runs unrecoverable. The
residual hazard (§6) is that two **concurrent** instances of this harness share those identities, so the
second instance's pre-run sweep would delete the first's live rows — a property the original
prefix-based block had as well (it deleted those same users, plus everything else).

**Explicitly rejected:** the `phase3f_%` prefix as a sweep key, and any wider scope. The prefix is
broader than ownership; the pre-run sweep uses the exact two addresses.

---

## 3. Exact code changes

One evaluation runner changed. **No** schema, corpus, metric, protocol, CLI or transaction change: the
edit set is exactly the regions listed below, and none of them lies inside the evaluation body, so the
harness's arms, questions, metrics and reporting are unchanged. Directly verifiable in the final file
and pinned by the new tests: protocol markers `PHASE 3F EVALUATION`, `warm-up complete`, the per-arm
banner, `wrote …`, `PHASE 3F IMPLEMENTATION VALIDATION`, the data-leakage lines, the `AC1`/`AC18` lines,
the report path `phase3f_evaluation_report.json`, `TOP_K = 5`, the three-arm matrix and all metric keys.

`backend/evaluation/experiments/run_phase3f_evaluation.py` (1111 → 1201 lines):

| # | Site | Before | After |
|---|---|---|---|
| 1 | new `HARNESS_LABELS` / `harness_user_email(label)` / `HARNESS_USER_EMAILS` (L686–707) | the email was built inline inside the ingest loop | single source of truth for the harness's identity; the ingest loop now uses `email=harness_user_email(label)` (L860) |
| 2 | new helper `owned_user_ids(db, *, emails)` (L707) | — | ids of the users this harness owns, by **exact email** |
| 3 | new helper `cleanup_harness_rows(db, *, user_ids)` (L717) | — | the only deletion implementation; model-bound, FK-safe order, early return on an empty id set |
| 4 | pre-run "Clean" block (old L754–761) | six raw statements: five **unpredicated** table deletes + `users WHERE email LIKE 'phase3f_%'` | `previous_users = await owned_user_ids(db, emails=HARNESS_USER_EMAILS)` → `if previous_users: await cleanup_harness_rows(db, user_ids=previous_users)` → `await db.commit()` (L851–854) — the same "clean previous runs" intent, narrowed to the harness's own two users |
| 5 | final "Cleanup" block (old L944–949) | four raw statements: three **unpredicated** table deletes + the prefix user delete | `await cleanup_harness_rows(db, user_ids=list(users.values()))` + `await db.commit()` (L1038–1039) |
| 6 | imports inside `main()` | `from sqlalchemy import text` (needed only by the deletes) | removed — the file now contains **no raw SQL call at all** |
| 7 | guard `operation=` text (L801) | "…(it deletes rows, including unscoped deletes)" | "…(it deletes rows **it owns**)" |

The helper's body (identical in shape to Steps 0.8–1.0, so the five remediated runners share one
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
  degenerate into an unpredicated delete — and a test asserts that behaviourally.
* **FK-safe and cascade-independent:** logs → messages → sessions → chunks → documents → users; nothing
  relies on `ON DELETE CASCADE` for a row it claims to delete (the two prefix statements did).
* **No framework:** two module-local functions in the runner that uses them; the caller keeps the
  commit, exactly as before.
* **`text` removed from the import, not "kept for later":** this runner had no read-only raw SQL, so the
  conversion leaves zero `text(...)` calls. (Where a runner *does* keep read-only diagnostics — Phase 3E
  validation, Step 1.0 — they were preserved, and its tests pin their presence.)

---

## 4. Regression tests and actual results

New file `tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py` (**18 tests**). All commands
were run from `backend/` with `./venv/Scripts/python.exe`. **Nothing below connects to PostgreSQL, to
the application database, or to any database at all** — the behavioural tests run against the suite's
in-memory SQLite fixtures (with `PRAGMA foreign_keys=ON`), and the guard tests stop before any engine
exists.

| Command | Result |
|---|---|
| `python -m py_compile evaluation/experiments/run_phase3f_evaluation.py` | OK (exit 0) |
| `python -m pytest -q tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py tests/unit/evaluation/test_legacy_runner_isolation.py` | **88 passed**, exit **0** (26.6 s) — 18 new + 70 isolation tests |
| `python -m pytest -q tests/unit/evaluation` | **338 passed**, exit **0** (41.7 s) — 320 before this change |
| `python -m pytest -q tests/unit` | **841 passed**, exit **0** (71.1 s) — 823 before this change; final run on the frozen tree |
| `python -m pytest -q tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py` | **18 passed**, exit **0** (5.4 s) |

No test failed in this step. (The docstring of the new test file was corrected once, describing eight
unpredicated statements rather than eleven — a documentation error in the test header, fixed at the
cause; the suites above were re-run afterwards.)

| Required coverage | Test(s) | Evidence type |
|---|---|---|
| **Exact ownership selection** | `test_ownership_is_selected_by_the_exact_emails` — both harness emails plus a decoy `…@test.local.bak` and an unrelated user; exactly the two harness ids are returned | **executed** (SQLite) |
| **Owned records are removed** | `test_owned_records_are_removed`, `test_both_owned_users_are_cleaned_in_one_sweep` — all six tables drop to 0 for one user and for both in one sweep | **executed** (SQLite) |
| **Unrelated users and their documents/chunks survive** | `test_other_experiments_survive_untouched` — a sibling `phase3f_upload_*` user and a `phase3d_*` user keep row counts, chunk **ids**, chat rows and logs | **executed** (SQLite) |
| **Repeated cleanup is safe** | `test_repeated_cleanup_is_safe_and_does_not_spread` — twice, no error; the second sweep finds no users | **executed** (SQLite) |
| **Empty ownership sets do not cause broad deletion** | `test_an_empty_ownership_set_is_a_no_op` — `user_ids=[]` leaves every foreign row intact | **executed** (SQLite) |
| **Dependent rows are deleted in a safe order** | `test_dependent_rows_are_deleted_before_their_parents` (log → message → session → chunk → document → user, from the helper source) | source/AST |
| **All cleanup call sites use the intended scoped operations** | `test_both_cleanup_call_sites_use_the_scoped_helpers` (2 helper calls + 1 exact-email lookup; no prefix predicate; no raw chunk delete), `test_ownership_identity_is_single_sourced` | source |
| **No raw destructive SQL remains, f-strings included** | `test_no_raw_destructive_sql_exists` (AST over every `text(...)` literal incl. f-strings: none contains `DELETE`/`TRUNCATE`/`UPDATE`/`INSERT`/`DROP`), `test_the_runner_no_longer_imports_text_at_all` (zero `text()` calls) | AST |
| **Unsafe targets rejected before engine creation / cleanup** | `test_no_explicit_target_is_refused_before_any_engine` (engine factory spied on; `seen == []`; credential-free message), `test_application_database_is_refused_as_an_explicit_target` (`REFUSING`) | **executed** (no connection possible) |
| **Guard ordering** | `test_the_guard_precedes_the_engine_and_both_cleanups_in_the_source` | source |
| **Evaluation behaviour and interfaces intact** | `test_protocol_markers_and_report_path_are_unchanged`, `test_metric_protocol_and_arms_are_unchanged` (`TOP_K`, three-arm matrix, 14 metric keys), `test_exit_code_and_entry_points_still_behave` (exit `0`, `--database-url`, coroutine entry points, `harness_user_email`) | source + interface |

**One pre-existing test was updated, deliberately.** `test_legacy_runner_isolation.py` pinned
`source.count("DELETE FROM") == 10` for this runner — a pin asserting exactly the code this task had to
remove. This runner's spec now carries `scoped_cleanup=True`; the branch verifies the **stricter** new
contract (`_raw_sql_delete_literals(module) == []` over `text(...)` literals, f-strings included, no
`text("DELETE`, helper defined and used). `run_phase4b_evaluation` keeps its historical count (10).
No assertion was weakened, skipped or deleted.

**Deliberately not executed (therefore not claimed as verified):**

* the harness itself — it ingests a full corpus, needs the QA model, real chunkers/embeddings and
  PostgreSQL + pgvector, which this task is neither authorised nor provisioned to run;
* `tests/integration` / `tests/e2e` (they write into the application upload root — Step 0.5 F-4), so the
  full suite was not run;
* no migration, no database create/drop/downgrade, no destructive evaluation.

**Evidence boundary, stated plainly.** The scope semantics (which rows are selected, and that foreign
rows survive) are proven **behaviourally on SQLite**. Ordering, call-site coverage and the absence of
raw destructive SQL are **source/AST** evidence. **No PostgreSQL execution was performed**, so the
PostgreSQL binding of the new predicates is *inferred*, not measured — from the identical, already
PostgreSQL-executed pattern in `run_dual_path_ablation.py` and from the dialect-neutral SQLAlchemy
constructs.

---

## 5. Isolation and protected-artifact verification

| Artifact | Observed (after every test run) |
|---|---|
| `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | 2026-09-21 02:58 (frozen benchmark, untouched) |
| `models/documind-qa/model.safetensors` | 2026-09-02 02:52 (QA weights, untouched) |
| `evaluation/reports/ablation_A.json` | 2026-10-04 18:16 (untouched); `evaluation/reports/` listing digest `md5 e8d577977cb0d3683afb391cb79a1595` (same as Steps 0.8–1.0) |
| `backend/.env` / `backend/.env.example` | 2026-10-06 07:53 / 2026-09-27 10:00 (untouched) |
| `backend/uploads/` | **1 112** entries (unchanged before/after; nothing deleted or regenerated) |

* **No database was contacted, created, migrated, dropped or queried**, and the harness was not
  executed. The guard tests assert the refusal happens with `create_async_engine` never reached.
* **Guard ordering unchanged and pinned:** `assert_safe_evaluation_target(` (L800) precedes
  `os.environ["DATABASE_URL"] = evaluation_dsn`, `create_async_engine(evaluation_dsn)` (L827) and both
  cleanup call sites (L851–853, L1038).
* **Working tree scope unchanged:** `git status --porcelain` → **384** entries, **34** modified tracked
  files — identical to the pre-task count.
* No commit, push, deploy, revert or stash; no unrelated change touched; the previously remediated
  runners and `run_phase4b_evaluation.py` unmodified (the latter still has its 10 raw `DELETE FROM`).

**Content digests** (the runner is untracked, so its pre-change content is recoverable only from the
Step 0.5 report's citations and the pre-existing `deletes=10` pin):

```
fbfca13dacf6482a64f4e7df66471ed7f2c067323ff483b1dad556fdb21e0b06  evaluation/experiments/run_phase3f_evaluation.py
034df413cfe99538b390b7b50cade90334ae959f5fe5bc976af625182a94dba5  tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py
1c17ed92316d8692a7b8032ac10b078e211dc1c90f7cc0c110d79f98369c6866  tests/unit/evaluation/test_legacy_runner_isolation.py
```

---

## 6. Remaining risks and unverified behaviour

1. **No PostgreSQL execution.** Scope semantics are proven on SQLite; PostgreSQL binding is inferred.
   A future isolated-database run that observes a foreign user's documents, chunks and logs surviving
   this harness's pre-run and final cleanups would close this.
2. **Concurrency caveat (pre-existing, unchanged in kind).** The two evaluation emails are
   deterministic, so two *concurrent* instances sharing one isolated database share identities: the
   second instance's pre-run sweep would delete the first's live rows. The original prefix-based block
   had the same hazard (and, on top of it, wiped whole tables). Mitigation is operational — run one
   instance of this harness at a time against a given database — and a stronger fix (run-id-scoped
   identities) is a design decision, not a cleanup tweak.
3. **Interrupted runs:** unlike the Phase 3D/3E runners (random emails), this harness *does* recover
   its own leftovers via the exact-email pre-run sweep — but only for the two known labels, and only if
   the next run uses the same code version.
4. **Upload-root growth (F-4) unchanged:** `save_upload` writes every corpus document into the
   application storage root and nothing removes those stored copies; the harness's own scratch inputs
   are handled by `tempfile.TemporaryDirectory`. Not in scope here, still open.
5. **The harness itself remains unexecuted** — its arms, metrics and reporting are unchanged and
   pinned, but no live run was performed, so the *evaluation results* it produces are unverified in this
   step.
6. **Provenance (F-5) untouched:** a run on this dirty, largely untracked tree still cannot be
   reproduced from a manifest.
7. **One runner remains** (Step 0.5 F-1): `run_phase4b_evaluation.py` (10 raw `DELETE FROM`) — the
   recommended next step (Step 1.2); explicitly **not** started here.
8. **F-2/F-6/F-7/F-9/F-10/F-11/F-12/F-13/F-14** from the Step 0.5 audit remain open. Remediating this
   runner does **not** make the project safe: the pattern still exists in the Phase 4B runner, and the
   audit's other findings are untouched.

---

## 7. Operational agent and specialist role-template mapping

Operational agent: **COORDINATOR**, acting directly. The runtime provides one coding agent plus
file/code-search helpers; the specialist roles are templates, and none is claimed as an independent
runtime agent.

| # | Role template | Where its concern is answered |
|---|---|---|
| 8 | Software Architect | §3 (two module-local helpers; no framework; call sites and commit boundaries preserved) |
| 11 | Database Architect | §2 (ownership keys from the models), §3 (FK-safe, cascade-independent order) |
| 14 / 72 | Security Architect / Application Security | §1 (blast radius and per-statement risk classification), §5 (guard ordering) |
| 17 | Backend Coding Engineer | §3 (exact change, incl. removing the now-unused `text` import) |
| 39 | Model Evaluation Engineer | §3/§4 (arms, metrics, protocol markers, report path unchanged; no metric change) |
| 51 / 53 | Test Architect / Integration Testing | §4 (behavioural SQLite tests; the explicit SQLite-vs-PostgreSQL boundary) |
| 58 | Security Testing | §4 (refusal tests with the engine factory spied on; f-string-aware AST pin) |
| 59 | Code Review | §3, §8 (files changed; one pre-existing pin updated and explained) |
| 60 | Debugging | §1 (failure mode classification), §4 (the test-docstring error found and fixed at cause) |
| 61 | Reliability Engineer | §4 (repeat-cleanup and empty-set safety), §6 (concurrency caveat, leakage, F-4) |
| 79 / 81 | Documentation / Architecture Documentation | this report, `evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64 |
| 82 | Codebase Knowledge | §2 (inspection record), §6 (what still carries the pattern) |
| 89 | Database Optimization | §2/§3 (narrowest correct predicate; index-supported keys) |

---

## 8. Final diff and scope verification

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase3f_evaluation.py` | ownership constants + `owned_user_ids` + `cleanup_harness_rows` added (L686–770); both cleanup blocks replaced; ingest loop single-sourced; unused `text` import removed; guard `operation` text updated | remove eight unpredicated deletes and two prefix deletes; keep the "clean previous runs" intent with an exact-email scope |
| `tests/unit/evaluation/test_phase3f_evaluation_cleanup_scope.py` | **new** (18 tests) | behavioural proof of scope, exact-email ownership, empty-set safety, repeat-safety, guard ordering, preserved protocol/metrics/interfaces |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | this runner's spec gains `scoped_cleanup=True`; docstring notes the Step 0.8/0.9/1.0/1.1 exceptions | the count pin forbade the fix; replaced by the stricter literal-level contract |
| `evaluation/README.md` | new "Phase 3F evaluation runner — scoped cleanup (Step 1.1, 2026-10-09)" section; outstanding list reduced to `run_phase4b_evaluation` | document the boundary and what is verified |
| `architecture/STEP1_1_PHASE3F_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

**Not changed:** `run_phase4b_evaluation.py` and the five previously remediated runners; the Step
0–1.0 reports (append-only historical evidence); no production module; no migration; no fixture; no
benchmark, weight, `.env` or historical report; nothing under `backend/uploads/`.

**Verification of the final tree:** `git status` shows the same 384 entries / 34 modified tracked files
as before the task; the only files this step touched are the six above; the changed Python file
compiles and the suites in §4 were re-run after the last code edit (the 841-passed `tests/unit` run is
the final one — only Markdown changed afterwards); protected artifacts and `backend/uploads/` are
unchanged (§5). No commit, push, deploy, revert or stash was performed.

**Stop point.** Step 1.1 is complete for `run_phase3f_evaluation.py` only. No other runner was
modified, and Step 1.2 was not begun, pending review.

---

## 9. Inspection record and acceptance criteria

**Inspection record (Phase 1, performed before any edit):**

| Item | Finding |
|---|---|
| Imports | module-level: standard library, `evaluation.isolation`, `evaluation.datasets.phase3d_corpus`, `evaluation.harness.{corpus,extraction}`; inside `main()`: sqlalchemy engine/session, all models, `documents.chunking`, `passlib` |
| Isolation guard | `assert_safe_evaluation_target(...)` at L707 (old numbering) with operation text naming unscoped deletes; `os.environ["DATABASE_URL"]` at L720; engine created at L735 — guard first in every path |
| DB URL handling | `--database-url` → `DOCUMIND_INTEGRATION_DATABASE_URL` → application DSN; no hard-coded DSN, no import-time default |
| Engine / session | one `create_async_engine(evaluation_dsn)` + `async_sessionmaker`; several short-lived `async with session_factory() as db:` blocks, each committing its own work |
| Users/documents created | 2 users in the ingest loop (`legacy`, `candidate`), one full corpus each (documents + chunks + embeddings), through `ingest_corpus` |
| Cleanup sites | two blocks (pre-run and post-run), 6 + 4 raw statements (§1) |
| Transaction boundaries | `main()` commits inside each block; the report is written between them; `engine.dispose()` after |
| Failure/interruption paths | no `try/finally` cleanup in `main()`: an exception after ingest leaves that run's rows in place (recoverable by the next run's exact-email sweep); no `os.unlink`/`rmtree` anywhere |
| Exit behaviour | prints the summary and `return 0`; `__main__` raises `SystemExit(asyncio.run(main()))` |
| Read-only diagnostics | none — every `text()` call was a delete |
| Pre-change record | 10 `DELETE FROM` statements; protocol markers `PHASE 3F EVALUATION` / `warm-up complete` / per-arm banner / `wrote …` / `PHASE 3F IMPLEMENTATION VALIDATION`; `TOP_K = 5`; arms A/B/C; report `phase3f_evaluation_report.json`; CLI `--database-url` |

**Acceptance criteria check**

| Criterion | Status |
|---|---|
| Every destructive statement inspected and classified | ✅ (§1 table; 8 unpredicated, 2 prefix-scoped; nothing else destructive in the file) |
| Unsafe cleanup replaced by narrowly scoped, ownership-backed operations | ✅ (10 raw statements → 2 helper call sites over the harness's own two user ids) |
| Focused regression tests pass | ✅ (18 tests, exit 0) |
| Relevant unit suites + compilation recorded | ✅ (`tests/unit/evaluation` 338, `tests/unit` 841, `py_compile` — all exit 0) |
| SQL-safety assertions cover f-string literals | ✅ (AST collector reads f-string literal parts; asserted `{}` result) |
| Existing evaluation behaviour and interfaces preserved | ✅ (markers, metrics, arms, report path, CLI, exit code, commit boundaries pinned) |
| Protected artifacts and unrelated changes unchanged | ✅ (§5) |
| Report, README and project-context pointer present and accurate | ✅ (§8) |
| Limitations explicit | ✅ (§4 evidence boundary, §6) |
| No other runner modified | ✅ (`run_phase4b_evaluation.py` still has its 10 statements) |
