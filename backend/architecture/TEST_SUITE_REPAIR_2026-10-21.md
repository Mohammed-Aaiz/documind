# Test-suite repair — benchmark provenance, migration portability, E2E disposition (2026-10-21)

Status: **IMPLEMENTED — MEASURED**. Two files changed (`migrations/versions/008_add_generation_verification.py`,
`tests/integration/documents/test_table_row_migration.py`). No model, prompt, retrieval,
threshold, ORM model, benchmark byte, annotation, expected-hash or security gate was changed.
No commit was made.

Reported starting state (`[USER-REPORTED]`, not reproduced verbatim): 1,859 passed,
100 skipped, 5 failed, 6 errors.

Measured starting state on this checkout (`[CONFIRMED]`, `python -m pytest -q`, 297.48 s,
exit 1): **1,936 passed, 29 skipped, 4 failed, 1 error**. Same 1,970 collected tests, so the
difference is environment, not collection: this checkout has `backend/.env` and the local
model/PDF artifacts, the reporting checkout evidently did not (see §1 and §3).

## 1. Benchmark dataset — present, intact, and untracked

`[CONFIRMED]`

* `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` exists: 182 rows,
  116,271 bytes, SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0`
  — the value pinned by `evaluation/experiments/run_generation_benchmark.py:40` and
  `tests/unit/evaluation/test_run_artifacts.py:21`, and by the file's own
  `benchmark_checksum.txt`. **Integrity check unchanged and passing.**
* The file is **untracked**: `git status --porcelain phases/phase4f/phase4f_5d/benchmark/` →
  `?? backend/phases/phase4f/phase4f_5d/benchmark/`, and it is not gitignored.
* HEAD still tracks the *pre-migration* path
  `backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` (blob `58455eea…`, 182 rows,
  116,089 bytes, SHA-256 `5dff5aaa…`) — the LF rendition. `core.autocrlf=true` and there is no
  `.gitattributes`, so the working copy is CRLF.
* Content is identical modulo line endings, proven both ways:
  `tr -d '\r' < phases/…/qa_benchmark_v1.jsonl | sha256sum` → `5dff5aaa…` (the historical
  blob), and `git cat-file -p 58455eea… | sed 's/$/\r/'  | sha256sum` → `1166bf4f…`
  (the expected digest).

**Root cause:** incomplete path migration (`backend/phase4f/` → `backend/phases/phase4f/`,
see `PATH_MIGRATION.md`) that was never committed; `evaluation/artifacts.py:52-59` reads the
new path. Nothing is lost and no recovery is required on this machine. On any fresh checkout
1,970-test run, `tests/unit/evaluation/test_run_artifacts.py::test_frozen_benchmark_digest_is_recorded_and_unchanged`
fails (`benchmark_digest()` returns `{"status": "unavailable"}`) and every benchmark
experiment is unrunnable — which accounts for the reported 5th failure.

Two conditions remain, both outside the test layer:

1. the new path must be committed for a clone to contain it;
2. `backend/.dockerignore:21` (`backend/phases/`) excludes it from images, so containerised
   test runs lack it regardless;
3. the pinned digest is **line-ending sensitive** (LF `5dff5aaa…` vs CRLF `1166bf4f…`), so a
   Linux checkout of the same bytes hashes differently. Fixing that means either a byte-pinned
   `.gitattributes` entry (`*.jsonl -text`) or re-pinning the digest — a deliberate,
   Coordinator-owned decision. The expected hash was *not* modified here.

## 2. Migration 008 — PostgreSQL behaviour preserved, SQLite made executable

`[CONFIRMED]` — reproduced before the change (4 failures, exit 1):

```
FAILED test_table_row_migration.py::...::test_upgrade_creates_the_table_and_downgrade_removes_it
FAILED test_table_row_migration.py::...::test_upgrade_is_repeatable_on_an_already_migrated_database
FAILED test_table_row_migration.py::...::test_revision_chain_has_exactly_one_head
FAILED test_table_row_migration.py::...::test_the_new_table_is_additive_for_the_element_stream
E  sqlalchemy.exc.UnsupportedCompilationError: Compiler <SQLiteTypeCompiler> can't render element of type JSONB
E  assert 1 == 0   (test_revision_chain_has_exactly_one_head: "007" in output; `alembic heads` prints "008 (head)")
```

Two independent defects, therefore two fixes:

* **Non-portable type.** `008` added `generation_json` as bare `postgresql.JSONB`. The suite's
  SQLite rules (`tests/conftest.py:68`, `@compiles(postgresql.JSONB, "sqlite")`) are registered
  inside the pytest process; this test drives real Alembic in a **subprocess**, which never
  imports `conftest.py`, so nothing rendered the type. Fixed at the source: the revision now
  declares `postgresql.JSONB().with_variant(sa.JSON(), "sqlite")`. PostgreSQL DDL is
  byte-identical — `CreateColumn(...).compile(dialect=postgresql.dialect())` →
  `generation_json JSONB` — and SQLite renders `generation_json JSON`. Because revision 008 may
  already be applied to a live PostgreSQL database, the identical DDL is what makes editing it
  safe: the recorded schema does not move.
* **Stale expectation.** `test_revision_chain_has_exactly_one_head` asserted `"007" in output`
  from when 007 was head. Replaced with a check derived from the revision scripts themselves
  (`revision`/`down_revision` literals): exactly one `(head)` line, equal to the single revision
  no other revision descends from, plus a separate test that the head descends from the 006
  anchor so staging at 006 still exercises 007. Adding a revision can no longer make it stale.
* **Precondition the stamp does not create.** `alembic stamp 006` runs no DDL, so the throwaway
  SQLite file has no `reliability_logs` — revision 001 creates it with PostgreSQL-only
  `UUID`/`JSONB` DDL that cannot run here. 008 only *alters* that table, so the test now stands
  up the minimal precondition (a bare `reliability_logs(id)` table) in one named helper,
  `_stage_at_previous_revision`. The `ALTER TABLE` and its `downgrade` still execute against a
  real table; a new test asserts the added column's SQLite declaration (`JSON`, nullable) and
  that the downgrade removes it.

Migration history stays linear: `000 → 001 → … → 007 → 008`, `alembic heads` → `008 (head)`.

## 3. `test_real_e2e_validation` — an intentional refusal, not a skip candidate

`[DECIDED — pre-existing]` The error is the project's own fail-closed guard, not a defect:

```
evaluation.isolation.UnsafeEvaluationTarget: REFUSING the isolated database fixture:
missing enforceable create authorization. A valid isolated URL and an absent database name
do not authorize creation.            (evaluation/isolation.py:437)
```

`assert_creation_authorized` refuses unconditionally — "No accepted create authorization is
implemented" — so **no** environment can pass this fixture today. Multiple decision records
already state the intended disposition: “`test_real_e2e_validation` errors by design — a skipped
suite is never a pass”
(`DOCUMIND_MULTI_AGENT_IMPLEMENTATION_PLAN_REVISED_R5_2026-10-14.md:1280`,
`DOCUMIND_EXAM_ANSWER_DIAGRAM_OCR_CAPABILITY_AUDIT_2026-10-14.md:358,573`), and
`tests/fixtures/integration_db.py` says the same in its docstring and in
`test_isolated_fixture_requires_authority_before_reachability_probe`, which pins that
authorization is evaluated **before** the reachability probe
(`tests/unit/evaluation/test_lifecycle_authorization.py:125`).

**Determination: it must not be converted to a skip.** Skipping would turn "unverified" into
"passed" — the exact inversion those records forbid — and would require either weakening the
gate or bypassing the source-order invariant another test pins. The message the reporting
checkout saw (`No DATABASE_URL could be resolved for the E2E harness …`,
`tests/fixtures/e2e_config.py:143`) is the *other* case: `backend/.env` absent or without
`DATABASE_URL`. That is a configuration precondition (copy `.env.example`), not a code defect,
and no database is substituted or borrowed.

Resolution requires an enforceably-authorized disposable database (gate 1.6K) plus PostgreSQL
with pgvector — neither available here. Reported as **BLOCKED**, never as passing.

## 4. Verification

| Command | Result |
| --- | --- |
| `pytest -q tests/integration/documents/test_table_row_migration.py` (before) | 4 failed, exit 1 |
| same (after) | **6 passed**, exit 0 (4 original + 2 new) |
| `pytest -q` full suite (before) | 1,936 passed, 29 skipped, **4 failed**, 1 error, 297.48 s, exit 1 |
| `pytest -q` full suite (after) | **1,942 passed, 29 skipped, 0 failed, 1 error**, 327.64 s, exit 1 |
| `compileall` on both changed files | exit 0 |
| `pytest -q tests/unit/storage/test_sqlite_type_isolation.py tests/unit/evaluation/test_lifecycle_authorization.py tests/unit/evaluation/test_run_artifacts.py` | **57 passed**, exit 0 |
| `alembic heads` | `008 (head)`, exit 0 |
| PostgreSQL vs SQLite column DDL | `generation_json JSONB` / `generation_json JSON` |
| Benchmark SHA-256 after the change | `1166bf4f…`, unchanged |

Suite exit status remains **1** solely because of the by-design E2E refusal in §3.

## 5. Limitations

* The reported 1,859 / 100 / 5 / 6 distribution is not reproducible on this checkout; the 71–77
  extra skips there are consistent with absent local model/PDF artifacts, the 5th failure with
  the untracked benchmark (§1), and 6 errors with an absent `backend/.env`. No suite-wide run was
  executed in that configuration.
* PostgreSQL was not reachable here, so migration 008 was executed on SQLite only. PostgreSQL DDL
  equivalence is proven by compilation (`JSONB`), not by an applied migration.
* `tests/e2e` skipped for lack of a live server; no browser, PostgreSQL or production-path run.
* The line-ending sensitivity of the pinned benchmark digest (§1) is unresolved by design.

## 6. Addendum — restructure mission (2026-10-21)

The line-ending limitation in §5 is now addressed, and **not** by changing the digest:

* `.gitattributes` (new, repository root) pins
  `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` with `-text`, so git
  stores the CRLF bytes it is given and writes them back verbatim on every platform.
* The file also pins **itself** (`.gitattributes -text`).  Measured trap: a CRLF copy of the
  attributes file keeps the trailing `\r` in the pattern, and every rule inside it silently
  stops matching (`git check-attr` → `text: unspecified`).  With `core.autocrlf=true` a
  checkout would otherwise produce exactly that file.
* Regression test
  `backend/tests/unit/evaluation/test_benchmark_checkout_reproducibility.py` pins the rule,
  the self-pin, the absence of CR bytes, and the loader's exact path.
* Checkout simulation through a scratch index (real git objects, real attributes; the
  repository index is never written), `core.autocrlf` = `false` / `true` / `input`:
  **116,271 bytes, 182 rows, sha256 `1166bf4f…` in all three modes.**  A HEAD-only checkout
  has **no** file at the canonical path and only the obsolete `backend/phase4f/…` copy.
* Operational documentation corrected: `runbooks/api-down.md` and `runbooks/README.md`
  referenced `backend/start_server.py` (now `backend/scripts/start_server.py`) and a 20 s
  readiness wait (current `READY_TIMEOUT_SECONDS = 120`); `runbooks/README.md` also claimed
  migration head `006` (`alembic heads` → `008 (head)`).
* Measured after these changes: full suite **1,945 passed, 29 skipped, 1 error** (the §3
  guard), exit 1; `tests/unit` **1,646 passed, 23 skipped**; the migration file **6 passed**;
  `compileall` exit 0; `pytest --collect-only` exit 0, 1,975 collected.
* Still open: nothing is staged or committed, so a real clean checkout cannot contain the
  benchmark until the restructure commit is made.  The proposed commit groups and the
  deliberately excluded items are listed in the mission report.
