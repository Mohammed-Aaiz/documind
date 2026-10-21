# Step 0.8 — Phase 3D Evaluation Cleanup Remediation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (single runtime agent). The specialist roles named in the task
(8, 11, 14, 17, 39, 51, 53, 58, 59, 60, 61, 72, 79, 81, 82, 89) are **review templates**, not
separate runtime agents that exist in this repository. Their concerns are answered by sections of this
report and by the code/tests themselves; no independent agent participation is claimed.
**Scope:** remove the unscoped destructive cleanup from
`backend/evaluation/experiments/run_phase3d_evaluation.py` (Step 0.5 finding **F-1**, second half)
and replace it with a demonstrably ownership-scoped cleanup, with behavioural regression tests.
**Predecessors:** `STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` (Step 0, guard + R1/R2),
`STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (F-1; §4 "R3 — UNSAFE (critical)"),
the Step 0.6 isolation remediation of the five legacy runners (documented in
`evaluation/README.md`, "Five legacy phase runners — required configuration"), and
`STEP0_7_PHASE3D_DESTRUCTIVE_CLEANUP_REMEDIATION_2026-10-09.md` (F-3, sibling harness).

**Explicitly out of scope (not touched):** `run_phase3e_integration.py`,
`run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`. Their raw
deletes are still pinned by the Step 0.6 isolation test at their pre-existing counts (7, 9, 10, 10).

| Specialist role | Where its concern is answered |
|---|---|
| 8 Software Architect | §3 (call-graph placement of the cleanup), §4 (no new abstraction) |
| 11 Database Architect | §2 (ownership keys from the models), §3 (FK-safe order) |
| 14 / 72 Security Architect / AppSec | §1 (blast radius), §5 (guard ordering) |
| 17 Backend Coding | §4 (exact change) |
| 39 Model Evaluation | §6 F (evaluation surface preserved: arms, metrics, report schema) |
| 51 / 53 Test Architect / Integration Testing | §5 (behavioural SQLite tests; what was **not** executed) |
| 58 Security Testing | §5 (refusal tests with the engine factory spied on) |
| 59 Code Review | §4, §8 (files changed) |
| 60 Debugging | §1 (failure mode), §7 (the pre-existing test pin that had to change, and why) |
| 61 Reliability | §6 (repeat-cleanup safety), §7 (remaining risks) |
| 79 / 81 Documentation | this report, `evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64 |
| 82 Codebase Knowledge | §2 (inspection record), §8 (inventory of what else still carries the pattern) |
| 89 Database Optimization | §3 (narrowest correct predicate), §7 (follow-ups) |

---

## 1. Original failure mode

Before this change, `run_phase3d_evaluation.py` bracketed a run with **two** destructive blocks — one
before ingestion ("clean previous runs") and one after the run ("cleanup") — containing **10**
`DELETE FROM` statements in total (that exact count is pinned by the pre-existing Step 0.6 test
`tests/unit/evaluation/test_legacy_runner_isolation.py::TestEvaluationSurfaceUnchanged::test_destructive_sql_is_untouched`,
`RUNNERS["run_phase3d_evaluation"].deletes == 10`).

The block's shape, as recorded by the Step 0.5 audit (§4, R3; verbatim statements captured during this
inspection):

```python
await db.execute(text("DELETE FROM reliability_logs"))
await db.execute(text("DELETE FROM chat_messages"))
await db.execute(text("DELETE FROM chat_sessions"))
await db.execute(text("DELETE FROM document_chunks"))
await db.execute(text("DELETE FROM documents"))
await db.execute(text("DELETE FROM users WHERE email LIKE 'phase3d_%'"))
```

The Step 0.5 audit lists the same five data tables again in the post-run block (its L534–539 and
L637–640 citations).

**Two independent defects.**

1. **No predicate at all on the five data tables.** `DELETE FROM document_chunks` (and its
   `reliability_logs` / `chat_messages` / `chat_sessions` / `documents` siblings) removes **every row
   of that table in whatever database the runner targets** — every owner, every document, every chunk
   — including rows created by unrelated experiments that share the same isolated database (the
   project's workflow points every isolated runner at one shared
   `DOCUMIND_INTEGRATION_DATABASE_URL`). The application database itself is still protected by the
   Step 0.6 guard, but isolation only proves the target is *not the application's*: it cannot prove the
   target is *empty* or *exclusively yours*. Severity: evaluation-evidence loss.
2. **The one predicate it did have was the wrong one.** `users WHERE email LIKE 'phase3d_%'` matches
   the sibling upload/ask harness's users, which are named
   `phase3d_upload_<8 hex>@test.local` in `run_phase3d_upload_integration.py` (its L237, L371, L459 —
   verified). Deleting those users cascades into *their* rows. This is the same class of defect the
   Step 0.7 remediation removed from the sibling harness.

**Why this was still live.** Step 0.6 secured the five runners' *target resolution* (guard + removal
of the import-time hard-coded DSN), and Step 0.7 fixed the sibling harness's **one** unscoped chunk
delete. Nothing had yet touched R3's ten statements, which are the largest single destructive surface
of the nine runners the Step 0.5 audit flagged (F-1).

---

## 2. Mandatory initial inspection and the proven ownership boundary

| Question | Where it was answered |
|---|---|
| Every destructive SQL statement and file deletion in the target runner | whole file; the two cleanup blocks; `save_upload` in `ingest_corpus` (writes, does not delete) |
| What records does the runner create? | `build_corpus()` → 2 users (`HARNESS_ARMS`) → `ingest_corpus()` writes `Document` + `DocumentChunk` rows under that user; `run_question()` drives the real Brain, which writes `ReliabilityLog` / `ChatSession` / `ChatMessage` rows under the same user |
| Ownership keys (schema) | `documents/models.py`: `Document.user_id → users.id` (`ondelete="CASCADE"`, indexed); `DocumentChunk.document_id → documents.id` (`ondelete="CASCADE"`, indexed) — **a chunk has no owner column**; `reliability/models.py`: `ReliabilityLog.user_id → users.id` (unique, CASCADE); `chat/models.py`: `ChatSession.user_id → users.id`, `ChatMessage.session_id → chat_sessions.id` (both CASCADE) |
| What identifies the runner's own users? | `HARNESS_ARMS` (before this change: the two literal email strings were built inside `main()`); the emails are deterministic (`phase3d_legacy@test.local`, `phase3d_candidate@test.local`) — the only marker that survives an interrupted run |
| Existing scoped precedent | `run_dual_path_ablation.py` `delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))`; the sibling harness's `cleanup_harness_rows` (Step 0.7) |
| Existing regression tests | `tests/unit/evaluation/test_legacy_runner_isolation.py` (Step 0.6) pins only the *guard* and the *statement count*, not the scope |
| Guard + prior contracts | `evaluation/isolation.py`; Step 0 / 0.5 / 0.6 / 0.7 reports and `evaluation/README.md` |
| Working tree | dirty and largely untracked (`backend/evaluation/**` is untracked entirely — `git ls-files` fails on the runner, so it has **no git baseline**); nothing was discarded, reverted or reorganised |

**Boundary: the two evaluation users this harness creates — and no other row.**
`HARNESS_USER_EMAILS` → user ids → `documents.user_id`, `chat_sessions.user_id`,
`reliability_logs.user_id`; chunks and chat messages have no owner column and are reached only through
their parent (`documents.id`, `chat_sessions.id`). Every row the run writes is under one of those two
users: ingestion stores each document with `user_id=user.id` (the runner's own user), and the Brain
registrations in `run_question` are bound to that same user. Nothing in the runner writes rows for any
third party, and the harness creates no other users.

**What was explicitly rejected as a scope.** The document *name* (`CorpusDoc.name` — the corpus is
shared and the sibling harness uses the same corpus names), the chunk *text*, and the
`phase3d_%` **email prefix** (the sibling harness's users match it — §1 defect 2). The Step 0.5 audit
also records that R3's own pre-run block was previously *unguarded* — that half was already fixed in
Step 0.6; the scope question here is only *which rows*, and the evidence above answers it.

---

## 3. FK-safe deletion order (preserved, now explicit)

`cleanup_harness_rows` deletes in the same order the inline blocks used — reliability logs, chat
messages, chat sessions, chunks, documents, users — which is a valid topological order of the FK
graph (`document_chunks` before `documents`, `chat_messages` before `chat_sessions`, everything before
the `users` row). Nothing relies on `ON DELETE CASCADE` for a row the function claims to delete, so the
cleanup cannot be blocked by a foreign key and cannot silently leave orphans behind if a cascade is
unavailable (SQLite without `PRAGMA foreign_keys`, for example).

---

## 4. The exact change

One file of production/research code changed; **no** schema, corpus, metric, protocol, model, output
schema or report-semantics change.

`backend/evaluation/experiments/run_phase3d_evaluation.py` (now 831 lines):

| Item | Before | After |
|---|---|---|
| arm/email ownership | two literal emails built inside `main()` | `HARNESS_ARMS` (L512) + `harness_user_email(arm)` (L518) + `HARNESS_USER_EMAILS` (L532), single-sourced; the ingest loop (L688) uses `harness_user_email(arm)` (L692) |
| selecting the harness's users | implied by the email `LIKE` predicate | `async def owned_user_ids(db, *, emails)` (L537) — `select(User.id).where(User.email.in_(emails))` |
| deleting the harness's rows | 5 unscoped `DELETE FROM <table>` per block | `async def cleanup_harness_rows(db, *, user_ids)` (L547) |
| pre-run cleanup call site | inline raw SQL | `previous_users = await owned_user_ids(db, emails=HARNESS_USER_EMAILS)` (L679) → `await cleanup_harness_rows(db, user_ids=previous_users)` (L681) → `await db.commit()` |
| post-run cleanup call site | inline raw SQL | `await cleanup_harness_rows(db, user_ids=list(users.values()))` (L784) → `await db.commit()` |
| documentation | — | module guidance + the helper's derivation recorded in its docstring; the guard's `operation=` text (L626) now reads "the Phase 3D evaluation harness (it deletes rows it owns)" |

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

Design notes that matter:

* **Model-bound, not raw SQL.** The predicate binds through the dialect's UUID handling, so the
  identical scope is exercised by PostgreSQL and by the SQLite fixtures the tests use. A raw
  `WHERE user_id = :u` bound to a `str` would silently match nothing on SQLite and could not be tested
  behaviourally. This matches the pattern already executed against PostgreSQL in
  `run_dual_path_ablation.py`.
* **Empty scope is an explicit no-op** (`if not ids: return`) rather than an `IN ()` — the intent
  ("nothing of mine is present") is stated instead of implied.
* **No general cleanup framework** was introduced: two module-level functions in the runner that owns
  them, the caller keeps the commit, exactly as before.
* Nothing was extracted into shared production code, and no production (`backend/`) module was touched.

---

## 5. Tests executed, with exact results

All commands were run from `backend/` with `./venv/Scripts/python.exe`. **Nothing here connects to
PostgreSQL, to the application database, or to any database at all**: the behavioural tests run against
the suite's in-memory SQLite fixtures and the guard tests stop before any engine exists.

| Command | Result |
|---|---|
| `python -m py_compile evaluation/experiments/run_phase3d_evaluation.py tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` | OK (exit 0) |
| `python -m pytest -q tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` | **16 passed**, exit **0** (5.0 s) |
| `python -m pytest -q tests/unit/evaluation` | **287 passed**, exit **0** (30.9 s) — 271 before this change |
| `python -m pytest -q tests/unit` | **790 passed**, exit **0** (61.0 s) — 774 before this change |
| after the final docstring/constant edit: `python -m pytest -q tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py tests/unit/evaluation/test_legacy_runner_isolation.py` | **86 passed**, exit **0** (26.3 s) |
| final re-run of the frozen tree, after every code/doc edit: `python -m pytest -q tests/unit` | **790 passed**, exit **0** (59.8 s) |

The Step 0 guard suite `tests/unit/evaluation/test_evaluation_isolation.py` and the Step 0.6 isolation suite are collected inside both `tests/unit/evaluation` and `tests/unit` above; no failure occurred in either run.

New file `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` (379 lines, 16 tests):

| Requirement | Test(s) | Evidence type |
|---|---|---|
| **A** the harness's own records are cleaned | `test_harness_owns_exactly_its_own_evaluation_users`, `test_owned_rows_are_removed` — seeds both evaluation users with document + 2 chunks + reliability log + chat session + message, runs the real `owned_user_ids` + `cleanup_harness_rows`, asserts all six tables drop to 0 | **executed** (SQLite) |
| **B** unrelated records survive | `test_other_experiments_survive_untouched` — a sibling-prefix user and an unrelated user each keep their row counts, chunk **ids** and message/log rows while the harness's rows go | **executed** (SQLite) |
| **C** repeated cleanup is safe | `test_repeated_cleanup_is_safe_and_does_not_spread` — cleanup twice, no error, survivor intact; a second `owned_user_ids` sweep returns `[]` and an empty sweep is a no-op | **executed** (SQLite) |
| **D** ownership boundary is the user set, not text/prefix | `test_the_email_prefix_predicate_is_gone` (`email LIKE 'phase3d_%'` absent from the source) plus the B test's sibling user (whose email matches the old prefix and is byte-identical in shape to the real upload harness's) | **executed** + source/AST pin |
| **E** isolation still enforced, and before cleanup | `test_no_explicit_target_is_refused_before_any_engine`, `test_application_database_is_refused_as_an_explicit_target` (both with `create_async_engine` spied on; `seen == []`, credential-free message), `test_the_guard_precedes_both_cleanup_calls_in_the_source` | **executed** (no connection possible) |
| **F** evaluation surface preserved | `test_metric_protocol_constants_are_unchanged` (`TOP_K == 5`), `test_arm_matrix_is_unchanged` (A/B/C matrix), `test_report_output_semantics_are_unchanged` (`phase3d_evaluation_report.json`, `indent=2` write, `print_summary`), `test_cli_flags_still_behave`, `_raw_sql_statements()` AST check asserting **no** raw `DELETE FROM` remains | source assertions + AST |
| — no unscoped delete can come back | `test_no_raw_sql_delete_exists`, `test_cleanup_is_keyed_on_the_user_id_set` (all six predicates), `test_ownership_is_single_sourced` | AST + source |

**One pre-existing test was updated, deliberately** (§7): `test_legacy_runner_isolation.py`'s
`test_destructive_sql_is_untouched` pinned `source.count("DELETE FROM") == 10` for this runner — a pin
that asserted precisely the code this task was asked to remove. It now branches on a new
`RunnerSpec.scoped_cleanup` flag and asserts the **stricter** new contract for
`run_phase3d_evaluation` (no `db.execute(text(` at all, no `text("DELETE` literal, the scoped helper
defined and used), while the other four runners keep their exact historical counts (7, 9, 10, 10)
unchanged.

**Deliberately not executed (therefore not claimed as verified):**

* the runner itself — it needs an isolated PostgreSQL + pgvector database plus the QA model, which this
  task is neither authorised nor provisioned to use;
* `tests/integration` and `tests/e2e` (they write into the application upload root — Step 0.5 F-4), so
  the full suite was not run;
* no migration, no database create/drop/downgrade, no destructive evaluation run.

**Inference (explicitly not measured here).** PostgreSQL binding of the new predicates is *inferred*,
not executed: the statements use the same models and the same `delete(...).where(...in_(...))` shape
that `run_dual_path_ablation.py` already executes against a real isolated PostgreSQL database, and the
constructs are dialect-neutral. The SQLite execution proves the **semantics** (which rows are
selected); it does not prove the PostgreSQL plan.

---

## 6. Evaluation behaviour preserved (what the change deliberately does **not** touch)

* `TOP_K = 5`; the three-arm matrix A (legacy chunks + char context), B (legacy + token context),
  C (structure-v2 + token context); the corpus (`build_corpus`), the unanswerable set, the metrics
  aggregation (`recall@k`, `precision@k`, coverage, answerability, abstention, duplicate rate,
  latency), `chunk_stats`, and the per-question report.
* The output artifact and its schema: `phase3d_evaluation_report.json`, `json.dumps(report, indent=2)`.
* `print_summary`, `parse_args` / `--database-url`, and the `if __name__ == "__main__"` entry point.
* The guard: `assert_safe_evaluation_target(` (L624) still precedes
  `os.environ["DATABASE_URL"] = evaluation_dsn` (L637), `create_async_engine(evaluation_dsn)` (L654),
  and **both** cleanup call sites (L679–681, L784) — asserted by a test.
* Cleanup happens after the report is written, exactly as before, so no recorded result can change.

---

## 7. Why the pre-existing test pin changed (an intentional, explained check change)

`tests/unit/evaluation/test_legacy_runner_isolation.py` (Step 0.6) contained:

```python
assert source.count("DELETE FROM") == spec.deletes, (
    f"{name}: the isolation change must not alter evaluation SQL"
)
```

Its purpose was to prove that the *isolation* change touched no evaluation SQL. Step 0.8's requested
behaviour is exactly to change that SQL for this runner, so the pin as written would have been a test
that forbids the fix. It was replaced with a stronger, scope-aware contract:

* `run_phase3d_evaluation` (`scoped_cleanup=True`): `"db.execute(text(" not in source`,
  `'text("DELETE' not in source`, `"async def cleanup_harness_rows" in source`,
  `"cleanup_harness_rows(db, user_ids=" in source`;
* the other four runners: the original count assertion, unchanged (`deletes` retained in the dataclass
  as the audit record, documented as the pre-Step-0.8 count).

No other test was weakened, skipped or deleted; the failure this produced
(`assert 1 == 10`) was examined and resolved by making the test express the new requirement, not by
relaxing it.

---

## 8. Files changed

| File | Change | Why |
|---|---|---|
| `evaluation/experiments/run_phase3d_evaluation.py` | `HARNESS_ARMS` / `harness_user_email` / `HARNESS_USER_EMAILS` / `owned_user_ids` / `cleanup_harness_rows` added; both cleanup call sites replaced; guard `operation` text updated | remove 10 raw/unscoped deletes, keep the same ordering, scope and evaluation surface |
| `tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py` | **new** (379 lines, 16 tests) | behavioural proof of the scope, repeat-safety, guard ordering, and the preserved evaluation surface |
| `tests/unit/evaluation/test_legacy_runner_isolation.py` | `RunnerSpec.scoped_cleanup` flag + branched assertion + docstring note | the Step 0.6 pin forbade the Step 0.8 fix; replaced with a stricter contract (§7) |
| `evaluation/README.md` | new subsection "Phase 3D evaluation runner — scoped cleanup (Step 0.8, 2026-10-09)" | document the ownership boundary and what is verified |
| `architecture/STEP0_8_PHASE3D_EVALUATION_CLEANUP_REMEDIATION_2026-10-09.md` | **new** (this report) | audit-trail record |
| `DOCUMIND_PROJECT_CONTEXT.md` | one line in §64 | canonical pointer, existing convention |

**Not changed:** the other four runners; the Step 0 / 0.5 / 0.6 / 0.7 reports (append-only historical
evidence — their description of R3 remains an accurate record of the pre-remediation code); no
production module; no migration; no test fixture.

**Content digests** (the runner is untracked, so the pre-change content is only recoverable from the
Step 0.5 report's citations):

```
ee78a82e74cb08e0b9d88983479ce6c23c1290bd02c51ebc5300da5b727743ab  evaluation/experiments/run_phase3d_evaluation.py
b91001b96211c879444528256c0f6308a5e15d928c3c6cdb59db532e50f4e5b2  tests/unit/evaluation/test_phase3d_evaluation_cleanup_scope.py
c30ef6454d76857d6334d78eaecd5fc16d66ea7247284fdd99d0ef9349688c2c  tests/unit/evaluation/test_legacy_runner_isolation.py
```

---

## 9. Protected-artifact and database-safety checks

Verified after every test run (mtimes/listing/counts unchanged):

| Artifact | Observed |
|---|---|
| `phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | 2026-09-21 02:58 (frozen benchmark, untouched) |
| `models/documind-qa/model.safetensors` | 2026-09-02 02:52 (QA weights, untouched) |
| `evaluation/reports/ablation_A.json` | 2026-10-04 18:16 (untouched); `evaluation/reports/` listing digest `md5 e8d577977cb0d3683afb391cb79a1595` |
| `backend/.env` / `backend/.env.example` | 2026-10-06 07:53 / 2026-09-27 10:00 (untouched) |
| `backend/uploads/` | **1 112** entries (unchanged before/after) |

* **No database was contacted, created, migrated, dropped or queried.** The guard's own tests assert
  the refusal happens with `create_async_engine` never reached (`seen == []`), and no other test in the
  new file touches a connection string.
* **Working tree scope unchanged:** `git status --porcelain` → **384** entries, **34** modified tracked
  files — identical to the pre-task count recorded in Step 0.7. (The whole
  `backend/evaluation/experiments/` tree is untracked, so the runner has no git baseline; the new test
  file is inside the already-untracked `backend/tests/unit/evaluation/` directory.)
* No commit, push, deploy, revert or stash; no existing change was discarded; the four other runners
  were not modified.

---

## 10. Remaining risks and follow-up tasks

1. **Not executed against PostgreSQL.** The scope semantics are proven on SQLite; PostgreSQL binding is
   inferred from a sibling precedent. A future isolated-database run that *observes* rows surviving a
   foreign user's cleanup would close this.
2. **The pattern persists in four runners** (Step 0.5 F-1, second half): unscoped deletes remain in
   `run_phase3e_integration.py` (L389 `DELETE FROM document_chunks`), `run_phase3e_validation.py`,
   `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py`. Each needs the same treatment, one at a
   time, with its own report — explicitly **not** started here.
3. **The runner's own report is still written to a CWD-relative path**
   (`Path("phase3d_evaluation_report.json")`) and its uploads still go to the application storage root
   (Step 0.5 F-4). Unchanged by this task; larger decisions (RunOutput/`--out`, storage-root
   redirection) are Step 0.5 recommendations 3 and 4.
4. **Provenance (F-5) untouched:** a run on this dirty, largely untracked tree still cannot be
   reproduced from a manifest.
5. **The runner was never executed end-to-end**, so the new code path (`owned_user_ids` finding nothing
   on a first run, then `cleanup_harness_rows` after the report) is unit-tested but not integration-
   tested against a live database.
6. **F-2/F-6/F-7/F-9/F-10/F-11/F-12/F-13/F-14** from the Step 0.5 audit remain open; nothing here
   addresses them.

**Stop point.** This report is the Step 0.8 completion gate for `run_phase3d_evaluation.py` only. No
further runner was inspected, remediated or reported, pending review.

---

## 11. Acceptance criteria check

| Criterion | Status |
|---|---|
| Only `run_phase3d_evaluation.py` remediated | ✅ (four siblings untouched; counts still 7/9/10/10) |
| Every confirmed unscoped destructive DB operation replaced by the narrowest correct scope | ✅ (10 raw statements → 6 model-bound, user-id-scoped deletes) |
| FK-safe order preserved | ✅ (§3) |
| Methodology, corpus, metrics, output schema, report semantics preserved | ✅ (§6) |
| Established SQLAlchemy/model patterns reused | ✅ (as in `run_dual_path_ablation.py`) |
| Centralized guard retained, still first | ✅ (§6; asserted in source) |
| No production behaviour changed; no general cleanup framework | ✅ |
| Behavioural regression tests: own rows removed, unrelated intact | ✅ (§5 A/B, executed) |
| Repeat-cleanup safety | ✅ (§5 C, executed) |
| Guard-ordering test | ✅ (§5 E) |
| Source-text assertion not the *only* proof | ✅ (behavioural SQLite tests are primary; AST/source pins are secondary) |
| Focused + isolation + relevant unit tests run, with exit codes | ✅ (§5) |
| Compile/lint check for changed files | ✅ (`py_compile` exit 0) |
| No connection to / modification of the application database | ✅ (§9) |
| Protected artifacts untouched | ✅ (§9) |
| Dated report at the required path, with failure mode, boundary, changes, tests, safety checks, risks | ✅ (this file) |
| Evaluation documentation updated + §64 pointer | ✅ (`evaluation/README.md`, `DOCUMIND_PROJECT_CONTEXT.md`) |
| Final diff inspected; only intended files changed | ✅ (§8, §9) |
| Limitations explicit; executed vs inferred distinguished | ✅ (§5) |
