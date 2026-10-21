# Step 0.5 — Remaining Evaluation Runner Safety Audit

**Date:** 2026-10-09
**Type:** READ-ONLY AUDIT — inspection and reporting only. No implementation was performed.
**Scope:** every evaluation/research entry point in the repository that could affect evaluation
reliability, with the Step 0 implementation (`backend/evaluation/isolation.py`,
`backend/evaluation/artifacts.py`, the two instrumented runners) reviewed in detail.
**Predecessors:** `backend/architecture/PHASE0_CLOSURE_2026-10-09.md` (F-07),
`backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md`.

---

## 1. Operational agent and actual specialist participation

**Operational agent: COORDINATOR.** The audit was performed directly, as a read-only inspection, by
the single operational COORDINATOR. No sub-agent was invoked, because the specialist roles named in
the task are **review responsibilities**, not runtime agents that exist in this repository — claiming
they participated would be fabricating agent activity.

| # | Specialist role | Where its concern is answered in this report |
|---|---|---|
| 8 | Software Architect | §4 (engine/dependency boundaries), §5 (guard placement in the call graph) |
| 11 | Database Architect | §4, §5, §7A (connections, URL resolution, destructive SQL) |
| 14 | Security Architect | §5 (fail-closed semantics, credential handling), §10 F-6/F-7 |
| 39 | Model Evaluation Specialist | §8 (metric discrepancy), §9 (coverage gaps) |
| 51 | Test Architect | §12 (proposed tests), §10 F-8 |
| 53 | Integration Testing Specialist | §7B (integration-write side effects) |
| 54 | E2E Testing Specialist | §4 (R23), §9C (live-server e2e) |
| 57 | AI Evaluation Specialist | §8, §9 (contamination and provenance) |
| 58 | Security Testing Specialist | §5, §12 |
| 59 | Code Review Specialist | all findings are sourced to exact files/lines |
| 61 | Reliability Specialist | §7B, §10 F-4 |
| 62 | DevOps Specialist | §4 (R17–R22), §5 (config sources) |
| 68 | Observability Specialist | §6 (manifests/provenance), §8 |
| 72 | Application Security Specialist | §4, §7A |
| 79 | Documentation Specialist | this report |
| 81 | Architecture Documentation Specialist | §3, §4, `DOCUMIND_PROJECT_CONTEXT.md` §64 pointer |
| 82 | Codebase Knowledge Specialist | §3 (complete inventory) |
| 89 | Database Optimization Specialist | §7A (cleanup scoping), §7B (orphan accumulation) |

Nothing in this report depends on a claimed agent action. Every statement is either sourced to
repository code with line numbers, to `git` output, or to previously recorded Step 0 execution
evidence, and is labelled as such.

---

## 2. Repository state at audit start

| Item | Value (verified) |
|---|---|
| Branch | `main` |
| `HEAD` | `6baaa2a` — "fix: stabilize backend runtime and database migrations" (4 commits total: `6baaa2a`, `d17e1d2`, `c7082bb`, `c6c55d7`) |
| Commits touching `backend/chat/rag.py` | 3 (`c6c55d7`, `c7082bb`, `d17e1d2`) — none of the dual-path retrieval code |
| Working tree | **dirty and largely untracked.** `git status --porcelain`: 384 entries — **34** modified tracked files, **295** tracked deletions (the old `backend/phase4*/**` and `backend/test_*.py` trees), **55** untracked entries (`backend/evaluation/**`, `backend/phases/**`, `backend/tests/{unit,integration,e2e,fixtures}/**`, `backend/graph/**`, `backend/scripts/**`, `backend/architecture/**` — directory entries are collapsed by git). |
| Databases | No connection was opened and no database was started, created, migrated, dropped or queried during this audit. |
| Benchmark | `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` — 182 examples, 42 of them carrying `unanswerable_reason` (read only). |
| Historical reports | `backend/evaluation/reports/*` are untracked working-tree files (e.g. `ablation_A.json` mtime `2026-10-04 18:16`). |

This state matters for §8: because the retrieval/answer stack the A–D ablation calls is uncommitted,
there is **no committed baseline** against which any of its numbers can be compared.

---

## 3. Complete discovered runner inventory

Search space: `backend/evaluation/**`, `backend/phases/**`, `backend/scripts/**`,
`backend/tests/**`, plus a whole-repository sweep for SQLAlchemy engines, `asyncpg`, `DATABASE_URL`,
alembic/psql, `DELETE`/`TRUNCATE`, fixed output paths, `save_upload`, and `from_pretrained`.

**Runners (executable entry points), 24 total + 2 groups:**

| ID | Path | Entry point | DB? |
|---|---|---|---|
| R1 | `evaluation/experiments/run_dual_path_ablation.py` | `async def main()` / `__main__` | yes — **instrumented (Step 0)** |
| R2 | `evaluation/experiments/run_phase3d_upload_integration.py` | `async def main()` / `__main__` | yes — **instrumented (Step 0)** |
| R3 | `evaluation/experiments/run_phase3d_evaluation.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R4 | `evaluation/experiments/run_phase3e_integration.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R5 | `evaluation/experiments/run_phase3e_validation.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R6 | `evaluation/experiments/run_phase3f_evaluation.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R7 | `evaluation/experiments/run_phase4b_evaluation.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R8 | `evaluation/experiments/run_structure_confirmation.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R9 | `evaluation/experiments/run_structure_element_measurement.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R10 | `evaluation/experiments/run_structure_rrf_calibration.py` | `def main()` / `__main__` | yes — **uninstrumented** |
| R11 | `evaluation/experiments/run_table_evidence_measurement.py` | `def main()` / `__main__` | yes — **uninstrumented**, has its own loopback guard |
| R12 | `evaluation/experiments/run_phase4c_diagnostics.py` | `def main()` / `__main__` | no |
| R13 | `evaluation/experiments/synthesize_structure_discriminating.py` | `argparse` main | no |
| R14 | `evaluation/denominator_sensitivity.py` | `def parse_args` / `__main__` | no |
| R15 | `evaluation/structure_eval.py` | `argparse` main | no |
| R16 | `evaluation/datasets/structure_discriminating_v1.py` | `--validate/--summary/--json` | no |
| R17 | `scripts/cleanup_smoke.py` | `__main__` | yes — destructive by design (application DB) |
| R18 | `scripts/cleanup_orphan_uploads.py` | `__main__` | filesystem unlink |
| R19 | `scripts/setup_db.py` | `__main__` | schema/migrations |
| R20 | `scripts/create_test_user.py` | `__main__` | yes |
| R21 | `scripts/db_check.py` | `__main__` | yes (read-only check) |
| R22 | `scripts/start_server.py` | script | starts the app |
| R23 | `tests/e2e/browser/*` (6 files) | live HTTP against a running server | yes (through the app) |
| R24 | `backend/phases/**` (the 40-module phase tree **outside** the forbidden `phase4f_gpu/`) | 27 modules with `if __name__ == "__main__"` + 1 `main()`-only module | **no PostgreSQL anywhere**; one in-memory SQLite |
| — | `tests/fixtures/integration_db.py` | test fixture (guard mirror) | yes (isolated DB, TEST_AGENT-owned) |

**Exclusions (and why):**

* Ordinary unit/integration/e2e test modules are excluded: they are collected by pytest
  (`pytest.ini` → `testpaths = tests`) and are not standalone evaluation runners. The only
  test-layer artifact treated as a runner is R23 (manually executable browser harnesses that need a
  live server) and the R24 phase modules.
* `evaluation/isolation.py`, `evaluation/artifacts.py`, `evaluation/runner.py`,
  `evaluation/harness/**`, `evaluation/metrics/**` are libraries/harness code, not entry points;
  they are reviewed in §5–§7.
* `backend/phases/phase4f_gpu/**` is a forbidden path and was **not inspected**. It does exist on disk — it is a vendored Python environment (13 071 of the tree's 13 111 `.py` files) and is git-ignored (`.gitignore:77 backend/phases/phase4f_gpu/`), which is why the code-search tool does not surface it. Every statement in this report about `backend/phases/**` refers to the 40-file phase tree outside it.
* Archived-script names (`test_*.py` at `backend/` root, `backend/phase4d/**`, …) appear in
  `git status` as **deleted** — they no longer exist on disk and are therefore not runners.

**Correction to the Step 0 count.** The Step 0 report said "ten other research runners remain
uninstrumented". Verified against the tree: there are **9** DB-touching, non-instrumented runners
(R3–R11). Counting every other runnable entry point in `evaluation/experiments/` (9 + R12 + R13 =
11) also does not give ten. The exact integer therefore depends on the definition; what is
actionable is the verified set: **R3–R11 (9 runners)**.

---

## 4. Individual safety assessment

Columns: engine source (where the DB connection comes from) · URL resolution · hardcoded DSN ·
isolated override · app-DB identity check · destructive scope · process-wide env mutation · fixed
output path (overwrite possible) · manifest · writes app storage · evidence level.

### R1 `run_dual_path_ablation.py` — **SAFE (guarded)**
* Engine: `from storage.database import async_session, engine` inside `main()`, **after** the guard
  (L656; comment L137-L141 explains the deliberate ordering).
* URL: `evaluation_database_url(override=args.database_url, application_url=…)` (L611) →
  `DOCUMIND_INTEGRATION_DATABASE_URL` → application DSN; `assert_safe_evaluation_target(...)` (L614)
  runs **before** `os.environ["DATABASE_URL"] = evaluation_dsn` (L623) and before any connection.
* Destructive scope: deletes are scoped to its own user/`doc_ids` (L853–L865).
* Output: `--out` **required** (L91, L588), `RunOutput` + reserved names (L640), manifest written
  last; a repeat run into the same directory is refused (Step 0 execution evidence).
* App storage: `save_upload` (L198) writes into `settings.upload_path` — see §7B; **no
  `delete_upload` anywhere** in the runner.
* Evidence: **Verified** (source) + **verified by execution** in Step 0 (isolated-DB run, refusal
  path, collision refusal) and 26 unit tests.

### R2 `run_phase3d_upload_integration.py` — **SAFE by guard, with an unscoped cleanup (see F-3)**
* Guard at L139–L142 (operation text names the deletion), env set L154, own engine from the guarded
  DSN L190. The guard is therefore guaranteed to run before every deletion when the module is
  invoked through `main()`/`__main__` (all deletes are inside `main()`).
* Deletes: a **scoped** cleanup at L454–L469, and an **unscoped `DELETE FROM document_chunks`** at
  L553 (§7A).
* Output: `--out` optional; when given, `checks.json` + `run_manifest.json` via `RunOutput`
  (L159–L160, L564); when omitted nothing is written (console only). No fixed report path.
* App storage: drives the real app in-process; uploads are stored through the app into
  `settings.upload_path` (§7B).
* Evidence: **Verified** (source) + Step 0 execution evidence (40/0 checks, manifest).

### R3 `run_phase3d_evaluation.py` — **UNSAFE (critical)**
* **Module-level environment mutation with a hardcoded credential-bearing DSN** (L63–L67):
  `os.environ.setdefault("DOCUMIND_DEV", "1")`, `os.environ.setdefault("QA_MODEL_NAME", …)`,
  `os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://documind:documind@localhost:5432/documind")`.
  The default target is the **application database** (`documind`).
* Own engine: `create_async_engine(...)` (L510) from that DSN; no identity check, no override
  variable, no guard.
* Destructive: **unscoped multi-table `DELETE`** — `reliability_logs`, `chat_messages`,
  `chat_sessions`, `document_chunks`, `documents` (L534–L539) and again L637–L640, plus
  `DELETE FROM users WHERE email LIKE 'phase3d_%'`.
* Output: phase report paths; no manifest.
* Evidence: **Verified** (source). Behaviour under a live app DB was **not** executed (prohibited).

### R4 `run_phase3e_integration.py` — **UNSAFE**
Same hardcoded `DATABASE_URL` default (L32, import time); own engine (L69); unscoped
`DELETE FROM document_chunks` (L389) alongside scoped deletes (L388–L391); writes HTTP-uploaded
files through the app (§7B); deletes its own temp files with `os.unlink` (L138, L379…).
Evidence: **Verified** (source).

### R5 `run_phase3e_validation.py` — **UNSAFE**
Hardcoded default DSN (L32), own engine (L66), no guard, no manifest. No unscoped delete found; it
*writes* rows into whatever DB the DSN names. Evidence: **Verified** (source).

### R6 `run_phase3f_evaluation.py` — **UNSAFE**
Hardcoded default DSN (L46), own engine (L687), `save_upload` (L259) → app storage. Evidence:
**Verified** (source).

### R7 `run_phase4b_evaluation.py` — **UNSAFE**
Hardcoded default DSN (L43), own engine (L667), `save_upload` (L234). Evidence: **Verified** (source).

### R8 `run_structure_confirmation.py` — **UNSAFE for the application DB; overwrites fixed reports**
* Engine: `from storage.database import async_session, engine` (L75) → **`settings.database_url`,
  i.e. the application database**, with no identity check and no override.
* Output: unconditionally writes `evaluation/reports/structure_confirmation.json` and
  `..._report.md` (L928–L932, plain `Path.write_text` = replace).
* Evidence: **Verified** (source).

### R9 `run_structure_element_measurement.py` — **UNSAFE** (same shape)
`storage.database` import (L88), fixed `REPORTS_DIR` writes (L1841–L1854), `save_upload` (L176).
Evidence: **Verified** (source).

### R10 `run_structure_rrf_calibration.py` — **UNSAFE** (same shape)
`storage.database` import (L69), fixed writes `structure_rrf_calibration.json` / `_report.md`
(L1144–L1148). Evidence: **Verified** (source).

### R11 `run_table_evidence_measurement.py` — **CONDITIONALLY SAFE**
* Engine: `get_settings().database_url` — the application DSN — but `_assert_local(url)`
  (L262–L271) refuses any host that is not loopback, and `_ensure_schema` (L273+) refuses unless the
  table-row schema is present. So it cannot write to a **remote** database, and cannot silently run
  against an un-migrated one.
* It still writes to the **local application database** when `documind` happens to be the local DSN,
  and it overwrites four fixed report paths (L188–L191, L1205–L1213) on every run.
* Evidence: **Verified** (source).

### R12 `run_phase4c_diagnostics.py` — **not DB-touching; CWD-dependent fixed paths**
Reads `phase4b_evaluation_report.json` and writes `phase4c_failure_matrix.json` relative to the
**current working directory** (L278, L585). Wrong CWD ⇒ wrong input / stray output. Evidence:
**Verified** (source).

### R13–R16 (report-only analysis scripts) — **no DB, fixed/default output**
`denominator_sensitivity.py` (`--output` default), `structure_eval.py`, `synthesize_structure_
discriminating.py` (`--reports-dir`), `datasets/structure_discriminating_v1.py` (validation CLI).
They read/write evaluation reports; no engine, no DSN, no process-wide env mutation was found.
Evidence: **Verified** (source, whole-file import sweep).

### R17 `scripts/cleanup_smoke.py` — **operator script; destructive against the application DB by design**
`delete(Document).where(Document.id.in_(doc_ids))` (L123), `delete(User)` (L127),
`shutil.rmtree(user_dir)` (L136). Invoked deliberately with `--email`; not an evaluation runner.
Evidence: **Verified** (source).

### R18 `scripts/cleanup_orphan_uploads.py` — **operator script; unlinks files**
`path.unlink()` (L213) with an explicit confirmation flag (`--yes`). It can delete files under the
application storage root; it is the documented counterpart of the accumulation found in §7B.
Evidence: **Verified** (source).

### R19–R22 — **operator scripts** (`setup_db.py` schema/migrations, `create_test_user.py`, `db_check.py`
read-only check, `start_server.py`). Not evaluation runners. Evidence: **Verified** (source).

### R23 `tests/e2e/browser/*` (6 files) — **conditionally executable; skipped without a live server**
`tests/fixtures/live_server.py` L33–L37 calls `pytest.skip("live server not reachable …")`;
the Phase 0 baseline recorded exactly 6 such skips. `test_phase6_reliability.py` L99 uses a
**CWD-relative fixed path** `os.path.join('uploads', 'phase6_test.pdf')`, and the other browser
harnesses write their source PDFs into a test-owned scratch dir
(`fixtures/e2e_config.py` L91, `GENERATED_UPLOADS_DIR = tests/e2e/browser/uploads`), not the
application storage root. Evidence: **Verified** (source) + recorded skip counts.

### R24 `backend/phases/**` — **no application/PostgreSQL access; out of DB-safety scope**
* The **only** database engine anywhere under the inspected phase tree (40 `.py` files outside the
  forbidden, git-ignored `phase4f_gpu/`) is an in-memory SQLite engine,
  `create_async_engine("sqlite+aiosqlite:///:memory:")` at `phases/phase4d/oracle_eval.py:347`.
  No `asyncpg`, no `psycopg`, no `DATABASE_URL`, no `storage.database` import was found there.
* They are not risk-free: they write JSON/JSONL artifacts into fixed phase directories, and
  `phases/phase4f/balance_gate.py:571` fetches a Hub tokenizer
  (`AutoTokenizer.from_pretrained("distilbert-base-cased")`) — a network/model-download dependency
  (see F-11). The remaining `from_pretrained(...)` calls take local model directories.
* Evidence: **Verified** (source sweep).

---

## 5. Step 0 guard review (`backend/evaluation/isolation.py`)

| Required property | Verdict | Evidence |
|---|---|---|
| Application DB identity resolution | Correct | `application_database_url()` reads `backend/.env` first (`_read_env_file_value`), then falls back to `config.get_settings().database_url` — the same source the application uses. |
| Consistent host/port/database comparison | Correct | `database_identity()` → `(hostname, port, path)`; compared for equality in `assert_safe_evaluation_target`. |
| Fails closed on missing/malformed identity | Correct | A target or application identity with no host or no database name raises `UnsafeEvaluationTarget`; an *empty but set* override raises instead of falling back. |
| Credentials excluded from errors/logs | Correct | `display_dsn()` renders `scheme://host:port/db`; `describe_identity()` renders `host:port/db`. No user info is interpolated anywhere in the module. |
| Explicit evaluation DB configuration honoured | Correct | Precedence: `--database-url` → `DOCUMIND_INTEGRATION_DATABASE_URL` → application DSN. |
| Unreachable, explicitly requested target fails without fallback | Correct | Resolution returns the override verbatim; the guard runs before connecting; connection failure propagates (Step 0 execution evidence: unreachable target → non-zero exit, no artifacts, no directory created). |
| Guard runs before the first connection/destructive operation | Correct for R1/R2 | R1: guard L614 < env L623 < `storage.database` import L656. R2: guard L142 < env L154 < engine L190; every delete is later inside `main()`. |
| DB creation/deletion/migration protection | Correct by absence | Neither module creates, migrates or drops a database; no `CREATE/DROP DATABASE`, no alembic, no psql invocation exists under `evaluation/`. |
| Same DB **name** on a different server | Allowed by design (documented) | Identity includes host/port, so `documind` on another host is *permitted*. If that other server hosts a sensitive copy, the guard cannot know. See F-6. |
| Operator could point a runner at another sensitive DB | **Yes — for R3–R11** | Those runners have no guard at all; §4. |
| CLI exposes credentials via process listings | **Yes** | `--database-url` accepts a full DSN (R1 L588, R2 L114 and following). The guard's own messages are credential-free, but the argv is not. See F-7. |

**Residual properties explicitly NOT verified:** the guard behaves as analysed for R1/R2, but no
execution was repeated in this audit (Step 0's isolated-DB runs are the execution evidence). The
guard's behaviour against a database reachable on a *different host with the same name* was not
exercised, and cannot be, without provisioning such a server.

---

## 6. Artifact and report-overwrite review (`backend/evaluation/artifacts.py` and writers)

| Required property | Verdict | Evidence |
|---|---|---|
| Output directory caller-controlled | Yes (new) / **no (legacy)** | `RunOutput(directory)` uses the caller's path; `runner.write_report(out_dir=None)` still writes to `REPORTS_DIR` (`evaluation/reports/`) — L400–L411, whose comment states re-running "replaces a same-named report". |
| All files of a run protected against collisions | Yes | `reserve()` pre-flights every name; `write_text` uses `open(path, "x")`; `write_report` reserves `name.json`/`name.md` together (L413–L424). |
| No-overwrite under concurrency | Yes | Exclusive create (`"x"`) plus pre-flight reservation; verified by a Step 0 repeat-run collision refusal (byte-identical artifacts, non-zero exit). |
| Partial runs cannot leave misleading results | Mostly | The manifest is written last (absent manifest ⇒ interrupted run). But a run that is killed mid-way after `reserve()` has still written some files; whether a run wrote 7 of 10 artifacts is discoverable only by comparing `plannedFiles`/`filesWritten` in the manifest — which does not exist for a killed run. |
| Manifests distinguish completed/failed runs | Yes | `result.status` ∈ `completed` / `completed_with_failures` / `incomplete` (R1/R2 write it in a `finally`-style path). |
| Credentials / documents / sensitive data in artifacts | No credentials found | Manifest records DB **identities**, relative paths and digests; no env value, no DSN, no document text. Corpus/benchmark **question text** may appear inside per-question details of legacy `RunReport` JSON — research corpus content, not user data. Evidence: **Probable** (source + Step 0 digest inspection), not exhaustively re-verified. |
| Any runner still overwrites historical reports by default | **Yes — 4 runners + the legacy `write_report` default** | R8 L928–L932; R9 L1841–L1854; R10 L1144–L1148; R11 L188–L191 + L1205–L1213 (`_write_deterministic` uses mode `"w"`); `runner.write_report(out_dir=None)` L400–L411. |
| Frozen benchmark ever modified | **No** | The only reference to `qa_benchmark_v1.jsonl` outside the artifact itself is `artifacts.py:58` (read-only digest). Step 0 verified its bytes/digest unchanged. |
| Output written unexpectedly inside the repo / app storage | Partly | Report-only runners write into `evaluation/reports/` by design; R12 writes relative to CWD; R1/R2 write into app storage via `save_upload` (§7B). |

**Step 0-covered vs legacy:** R1 and R2 are append-only and manifest-backed (with `--out`).
R3–R11 retain legacy behaviour outright: fixed report paths (R8–R11), no manifest (R3–R11), and the
legacy default-overwrite path in `evaluation/runner.py` remains live for any caller that omits
`--out`.

---

## 7. Findings on the unscoped deletion and test-storage side effects

### 7A. Phase 3D unscoped `DELETE FROM document_chunks`

`backend/evaluation/experiments/run_phase3d_upload_integration.py:553`.

* **What it can delete.** Every row of `document_chunks` in the **target** database — for all
  documents and all owners, not only the rows this harness created. (`document_chunks` is
  `DocumentChunk`, `backend/documents/models.py`; embeddings live on the same row, so re-ingestion is
  required to restore them.) The surrounding deletes are scoped (`reliability_logs WHERE user_id`,
  `documents WHERE user_id`, `users WHERE id`), and the *other* cleanup site in the same file
  (L454–L469) is fully scoped — so the unscoped statement is an isolated outlier, not a protocol
  requirement.
* **Is the guard guaranteed to run first?** Yes, for the only supported entry point. `main()`
  resolves the target and calls `assert_safe_evaluation_target` at L139–L142, sets the environment at
  L154, imports the app and creates the engine at L190; the deletion happens later inside the same
  `main()` call. There is no second entry point that reaches the delete without the guard.
  Therefore the application database **cannot** be reached — but any *other* database that the
  operator points the harness at is wiped of all chunks.
* **Can cleanup be scoped without changing the protocol?** Yes. Cleanup runs **after** all
  assertions (the checks are evaluated earlier, output is written afterwards at L564+), so changing
  its scope cannot alter recorded results. The scoped pattern already exists at L454–L469.
* **Regression tests needed before fixing** (see §12 T1–T3): an isolated-DB integration test that a
  foreign user's chunk survives cleanup; a source-level assertion that no unscoped
  `DELETE FROM document_chunks` remains in the runner; and a unit test that the cleanup SQL is
  parameterized by the harness's own `document_id`s.
* **Not modified in this audit.** No query, runner or test was edited.

### 7B. Evaluation-suite side effects under the application storage root

**Verified mechanisms** (all write through `storage.file_store.save_upload`, which resolves to
`config.get_settings().upload_path` — `config.py:60` `upload_dir = "./uploads"`, resolved against the
process CWD at `config.py:140–144`; `backend/.gitignore:44` ignores `uploads/`):

| Writer | Reads | Writes app storage |
|---|---|---|
| `evaluation/experiments/run_dual_path_ablation.py` L198 | `save_upload` | yes (12 PDFs per run); **no** `delete_upload` |
| `run_phase3d_evaluation.py` L155, `run_phase3f_evaluation.py` L259, `run_phase4b_evaluation.py` L234, `run_structure_element_measurement.py` L176 | `save_upload` | yes |
| `run_phase3d_upload_integration.py` / `run_phase3e_integration.py` | upload through the real HTTP/in-process app | yes |
| `tests/integration/documents/test_file_validation.py` L332 | asserts `settings.upload_path / str(user.id)` **exists and contains files** | yes — and the test *depends* on the file persisting |
| `tests/integration/documents/test_document_mutation_id_validation.py` (`_upload_txt`, L79–L83) and other documents/RAG integration tests | upload through the API | yes |

* **Cleanup: none in the test layer.** The only test reference to `upload_path` is that assertion
  (a repository-wide grep of `tests/` for `upload_dir|upload_path` returns one hit). No fixture
  redirects the storage root (an import sweep of `tests/fixtures/**` found no reassignment), and no
  fixture removes files afterwards. `tests/conftest.py` only owns the SQLite DB fixtures.
* **Observed accumulation:** `backend/uploads/` currently holds **1 112 entries** (per-user UUID
  directories). Their provenance (test artifacts vs. local manual use) cannot be separated without
  inspecting the application database, which is out of scope; the *mechanism* — writes into the
  application storage root with no removal — is verified in code.
* **Consequences.** (1) disk growth; (2) rows and files diverge: the test suite's DB is in-memory
  SQLite, so every test-created document row disappears while its file remains — i.e. the suite
  manufactures exactly the orphan files that `scripts/cleanup_orphan_uploads.py` exists to sweep, and
  that script (L213) *unlinks* files when invoked with `--yes`; (3) a runner or test that resolves
  `./uploads` from a different CWD would write to a *different* storage root, silently splitting
  state (R12 already shows the CWD-dependent failure mode of this codebase).
* **Real user data:** no code path here overwrites an existing file — `save_upload` writes into a
  fresh `uploads/<user-uuid>/` directory, and no test targets a real user's id. The risk is
  accumulation and maintenance confusion, not user-data destruction.
* **Not deleted during this audit** (per §11 prohibitions).

---

## 8. Analysis of the `chat/rag.py` change and the metric discrepancy

**Facts verified from the repository (no execution):**

1. `backend/chat/rag.py` is modified and **uncommitted**; its mtime is `2026-10-06 03:04`.
2. The working-tree diff against `HEAD` removes **exactly one line** —
   `from dataclasses import dataclass` replaced by `from dataclasses import dataclass, replace`
   (`git diff HEAD -- backend/chat/rag.py | grep "^-"` ⇒ one line) — and **appends 639 lines** at the
   end of the file (`@@ -497,0 +564,639 @@`; `HEAD` version = 497 lines, working tree = 1 136).
   The appended block adds imports (`os`, `graph.service`, `Mapping/Sequence`), 36 lines of optional
   provenance fields on `SourceChunk` (all defaulted), and the dual-path/table-evidence module.
3. The functions the ablation actually calls are **not in `HEAD` at all**:
   `async def retrieve_dual_path` (worktree L1149), `retrieve_structural_candidates` (L904),
   `retrieve_structural_element_candidates` (L991), `retrieve_table_row_evidence` (L846),
   `order_evidence_bands` (L881), `fuse_dual_path` (L1070), `dual_path_enabled` (L601).
   `HEAD` defines only `retrieve_chunks`, `build_context`, `build_qa_context`, `rag_answer`.
   ⇒ The retrieval stack used by `run_dual_path_ablation.py` exists **only in the uncommitted working
   tree**; git holds no earlier revision of it, so no baseline exists for comparison.
4. The recorded report (`evaluation/reports/ablation_A.json`, mtime `2026-10-04 18:16`, and
   `evaluation/README.md:132`) records `R@5 0.7738 / EM 0.5238 / F1 0.6296` for variant A. Step 0's
   fresh isolated-DB run recorded `R@5 0.7738 / EM 0.4524 / F1 0.5701` — **identical retrieval,
   different answer metrics** (EM differs by 3 of 42 questions; `0.5238 × 42 = 22` vs
   `0.4524 × 42 = 19`).
5. Files on the ablation's retrieval/answer path, by last write vs the `2026-10-04 18:16` report:

   | File | mtime | After the report? | Diff vs `HEAD` |
   |---|---|---|---|
   | `evaluation/harness/corpus.py` | 09-30 02:31 | no | import-path fix only (`tests.phase3d_corpus` → `evaluation.datasets.phase3d_corpus`) |
   | `chat/qa_model.py` | 09-30 02:34 | no | `torch`/`transformers` imports moved inside functions (behaviour-neutral for inference) |
   | `embeddings/model.py` | 09-29 21:39 | no | +70 lines (additive) |
   | `documents/routes.py` | 10-03 20:44 | no | +? (additive) |
   | **`documents/processing.py`** | **10-04 21:04** | **yes (+2h48)** | +92 lines |
   | **`documents/structure.py`** | **10-06 02:28** | **yes** | +? |
   | **`graph/service.py`** | **10-06 02:49** | **yes** | untracked file |
   | **`brain/adapters.py`** | **10-06 02:50** | **yes** | +? (`_augment_with_structure`, L353 of the ablation) |
   | **`chat/routes.py`** | **10-06 02:52** | **yes** | +79 lines |
   | **`chat/rag.py`** | **10-06 03:04** | **yes** | 1 changed import line + 639 appended lines (item 2–3) |

**Assessment.**

* **Refuted:** `chat/qa_model.py` and `evaluation/harness/corpus.py` cannot explain the difference.
  Both predate the report, and their diffs are a pure import relocation and an import-path fix. The
  Step 0 report's phrase "an uncommitted post-report `chat/rag.py` change" is therefore *not* the
  whole story, and the two candidate files it implies are excluded on evidence.
* **Not determinable from the repository:** whether the change is *in* `rag.py`, or in `graph/service.py`,
  `brain/adapters.py`, `documents/structure.py`, `documents/processing.py`, or in the run
  environment. All of the post-report candidates touch either the evidence text handed to the QA
  model (`processing.py`, `structure.py`) or the composition/ordering of that evidence
  (`rag.py`, `graph/service.py`, `brain/adapters.py`) — which is exactly the surface that can move
  answer metrics while leaving doc-level `R@5` unchanged. **Hypothesis (unverified): the delta
  originates in the uncommitted evidence-composition/ingestion stack, changed between
  `2026-10-04 21:04` and `2026-10-06 03:04`.** It cannot be confirmed, because no revision of that
  code was ever committed and the `2026-10-04` report carries **no manifest** (`artifacts.py` did
  not exist yet), so the exact inputs, corpus state, model digest and working-tree state of the
  0.5238 run are unrecoverable.
* **Independent of the cause**, the episode demonstrates the provenance gap in F-5: the manifest
  records `repository.commit`, `workingTree: dirty` and a *count* of changed paths — not the content
  of the modules that produced the number. On an uncommitted research tree, "dirty" is not enough to
  reproduce or even to rank hypotheses.
* **No model or benchmark was modified to test this.** The QA weights digest recorded by Step 0
  (`cb9f1dde…`) and the frozen benchmark digest (`1166bf4f…50a41d0b`, 182 examples) are unchanged;
  the benchmark file's only reference in code is the read-only digest helper.
* **The file was not reverted or edited** (prohibited).

---

## 9. Evaluation coverage gaps

**A. Corpus-level abstention.** Infrastructure exists but is not wired to the headline suite:
`evaluation/datasets/phase3d_corpus.py:566` `unanswerable_questions()` and
`evaluation/harness/corpus.py:198–206` `get_unanswerable()` / all-questions, plus a dedicated unit
test (`tests/unit/evaluation/test_unsupported_answer_denominator.py`). The A–D ablation's
structure-discriminating corpus contains 3 unanswerable questions of 42, so abstention is *touched*
per question, and Step 0 added per-question `detail` output — but no first-class, manifest-backed
abstention metric exists for the ablation.

**B. Frozen benchmark's answerable/unanswerable tiers.** The frozen benchmark
(`phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`, 182 examples, single `split`, of which
**42 carry `unanswerable_reason`**) is consumed by the Phase 4F model-evaluation harness under
`backend/phases/**`, **not** by the current `evaluation/` suite, which uses `phase3d`,
`heading`, `phase4b` and `structure_discriminating_v1` corpora. So the project's frozen, human-audited
answerable/unanswerable set currently has no runner inside the hardened evaluation infrastructure.
Minimum infrastructure: an isolated-DB runner that drives the real RAG path over the benchmark's
42 unanswerable examples and reports an abstention/`unsupported_answer` denominator with a manifest
(corpus digest + model digest + result).

**C. Browser/live-server E2E.** 6 browser harnesses self-skip unless a live server answers
(`tests/fixtures/live_server.py:33–37`); the Phase 0 baseline recorded 6 skips. So end-to-end
*product* behaviour (upload → ingest → ask → cite, RAG over real PostgreSQL) is covered only when an
operator starts the stack; there is no CI-able variant. Minimum infrastructure: an explicit, opt-in
e2e job (env-gated) that starts Postgres + the API and runs the 6 harnesses, plus a documented
skip policy so the skip is visible rather than silent.

**D. Lecturer-specific datasets.** **None exist.** `grep -rli lecturer` matches only narrative
documents — `DOCUMIND_PROJECT_CONTEXT.md` (L1490, L1499, L1547, L1767, L1822, and L1878 "A separately
versioned suite exists; the lecturer's …" under *Phase 0 acceptance (planned)*) and
`architecture/PHASE0_CLOSURE_2026-10-09.md`. No corpus module, dataset file or runner implements a
lecturer suite. This is an unbuilt requirement, not an instrumentation gap.

**E. Retrieval metrics and per-question diagnostics.** Present and healthy: `evaluation/retrieval_
metrics.py`, `qa_metrics.py`, `harness/metrics.py`, `schemas.py`, with unit coverage
(`test_metrics.py`, `test_structure_eval.py`, `test_denominator_sensitivity.py`) and Step 0's
per-question `detail` + `includes_per_question_detail`. The remaining gap is not metrics but
**provenance on dirty trees** (F-5) and coverage of the 9 uninstrumented runners (F-1/F-2).

No next experiment was begun.

---

## 10. Prioritized findings with evidence and severity

### F-1 — **Critical** (Verified) — five legacy runners default to the application database and delete unscoped
`run_phase3d_evaluation.py:63–67` (module-level `os.environ.setdefault("DATABASE_URL",
"postgresql+asyncpg://documind:documind@localhost:5432/documind")`), with unscoped
`DELETE FROM reliability_logs|chat_messages|chat_sessions|document_chunks|documents`
(L534–L539, L637–L640); same DSN default at `run_phase3e_integration.py:32` with unscoped
`DELETE FROM document_chunks` (L389); same default at `run_phase3e_validation.py:32`,
`run_phase3f_evaluation.py:46`, `run_phase4b_evaluation.py:43`. No guard, no identity check, no
override variable. Running one without an env override writes into — and for R3/R4 **deletes from** —
the live application database. Step 0 does not cover these files.

### F-2 — **High** (Verified) — four runners write fixed historical reports and target the app DB directly
`run_structure_confirmation.py:75` + `:928–932`; `run_structure_element_measurement.py:88` +
`:1841–1854`; `run_structure_rrf_calibration.py:69` + `:1144–1148`;
`run_table_evidence_measurement.py:188–191` + `:1205–1213` (`_write_deterministic` uses mode `"w"`).
Plus the still-live legacy default in `evaluation/runner.py:400–411`
(`write_report(out_dir=None)` → `REPORTS_DIR` with `Path.write_text`). A re-run silently replaces
recorded evidence; nothing records the previous content. (R11 is additionally
loopback-constrained, which lowers only its *remote* blast radius.)

### F-3 — **High** (Verified) — Phase 3D keeps a database-wide `DELETE FROM document_chunks`
`run_phase3d_upload_integration.py:553`, inside a runner whose guard proves only that the target is
*not the application* database. Any other database the operator points it at loses **all** chunks,
including data created by unrelated experiments that share that isolated database. The scoped
precedent is 20 lines away (L454–L469) and cleanup runs after all assertions, so scoping is
protocol-neutral.

### F-4 — **High** (Verified mechanism) — research runners and tests write into the application storage root and never clean up
`save_upload` at `run_dual_path_ablation.py:198`, `run_phase3d_evaluation.py:155`,
`run_phase3f_evaluation.py:259`, `run_phase4b_evaluation.py:234`,
`run_structure_element_measurement.py:176`; uploads through the app in R2/R4/R23;
`tests/integration/documents/test_file_validation.py:332` asserts the file persists. No
`delete_upload` call exists anywhere under `evaluation/experiments/`; no test fixture redirects or
sweeps `settings.upload_path`. `backend/uploads/` currently holds 1 112 entries. The suite
manufactures orphan files that `scripts/cleanup_orphan_uploads.py:213` exists to unlink.

### F-5 — **High** (Verified) — provenance is insufficient to reproduce (or diagnose) research runs on a dirty tree
The A–D ablation's entire retrieval/answer stack (`chat/rag.py` L846–L1149 etc. and its
`graph.service`/`brain.adapters` collaborators) is **uncommitted**; the recorded 0.5238 report has no
manifest. `artifacts.collect_run_manifest` records commit + `workingTree: dirty` + a changed-path
**count**, not the content/digest of the modules that produced the numbers. Result: the Step 0
metric discrepancy (EM 0.5238 → 0.4524 at identical `R@5 0.7738`) is **not attributable** from the
repository (§8), and the older number cannot be reproduced.

### F-6 — **Medium** (Verified) — two incompatible guard policies, and a same-named database on another host is permitted
`evaluation/isolation.py` compares `(host, port, database)` identity; `run_table_evidence_
measurement.py:262–271` only asserts loopback. A remote database named `documind` passes the
Step 0 guard by design (identity differs), and no runner refuses a *sensitive-looking* target.
Operator error (pointing a runner at a staging copy) is therefore possible.

### F-7 — **Medium** (Verified) — credentials are accepted on the command line
`--database-url` (R1 L588, R2 L114) takes a full DSN, which is visible in process listings and shell
history. The guard's output is credential-free, but the transport is not.

### F-8 — **Medium** (Verified) — no regression coverage for any uninstrumented runner
A repository-wide grep of `tests/` for the nine runner module names returns **no matches**. Their
safety properties are inferred from source only; nothing prevents a future edit from re-introducing
an unscoped delete or a fixed report path.

### F-9 — **Medium** (Verified) — CWD-dependent fixed paths
`run_phase4c_diagnostics.py:278` (reads `phase4b_evaluation_report.json`) and `:585` (writes
`phase4c_failure_matrix.json`) resolve against the process CWD; `tests/e2e/browser/test_phase6_
reliability.py:99` uses a relative `uploads/phase6_test.pdf`. Running from a different directory
reads/writes the wrong location (and, in the e2e case, the wrong storage root).

### F-10 — **Medium** (Verified) — the frozen benchmark's 42 unanswerable examples are not exercised by the hardened suite
See §9B. The benchmark is read-only and digest-recorded; it simply has no runner in the new
evaluation infrastructure.

### F-11 — **Medium** (Verified) — archived phase runners depend on the network and fixed artifact directories
`phases/phase4f/balance_gate.py:571` fetches `distilbert-base-cased` from the model Hub; the
phase4d/4e/4f modules write into fixed phase directories. They touch no application database
(the only engine is in-memory SQLite at `phases/phase4d/oracle_eval.py:347`), so this is a
reproducibility/network concern, not a data-safety one.

### F-12 — **Low** (Verified) — empty baseline packages mislead readers
`evaluation/baselines/{vector_only,structure_only,dual_path}/` contain only `__init__.py`; nothing
imports them (the only `baselines` matches in `evaluation/**` are prose inside two dataset modules).
The A–D variants live inside `run_dual_path_ablation.py`, so the packages suggest a frozen-baseline
architecture that does not exist.

### F-13 — **Low** (Verified) — `chat/qa_model.py` no longer exposes module-level `torch`/`transformers`
The uncommitted diff moved both imports inside the functions that use them (L60, L219); every
remaining `torch.*` use is inside `answer_question` (L251–L317), and no module references
`qa_model.torch`/`qa_model.transformers` (verified by grep). Behaviour is unchanged, but any future
module-scope use of those names will raise `NameError` instead of failing at import.

### F-14 — **Low** (Verified) — a runner documents its own destructive behaviour without warning the operator at runtime
`run_phase3d_upload_integration.py:37` and `:604` state the unscoped delete; the runtime message
names the operation but not the *scope* ("deletes rows (incl. an unscoped DELETE FROM
document_chunks)"). Documentation is accurate; discoverability could be better.

---

## 11. Recommended fixes in dependency order

Ordered so that each step is useful on its own and no later step depends on an unlanded earlier one.

1. **F-1 (Critical).** Bring R3–R7 under `evaluation/isolation.py`: delete the module-level
   `os.environ.setdefault("DATABASE_URL", …)` blocks with their hardcoded credentials, resolve the
   target through `evaluation_database_url()` + `assert_safe_evaluation_target()`, and set the
   environment only after the guard — the pattern already proven in R1/R2. Remove the literal
   credentials from the source entirely. This is the single highest-value change.
2. **F-3 (High).** Scope `run_phase3d_upload_integration.py:553` to the harness's own documents
   (`document_id IN (…)`, as at L454–L469) and update the operation text to describe the scope.
3. **F-2 (High).** Route R8–R11 through `RunOutput` (caller-supplied `--out`, refusal on collision,
   manifest last) and delete/withdraw the legacy `out_dir=None` overwrite branch in
   `evaluation/runner.py:400–411` (or make it raise). Keep the historical reports untouched.
4. **F-4 (High).** Give the runners and the test layer a storage root of their own: redirect
   `settings.upload_dir` to a temp directory in the runners (they already create
   `tempfile.TemporaryDirectory()` for inputs), and add a session-scoped fixture that points
   `upload_dir` at a test-owned directory and removes it — so no test or runner writes into
   `backend/uploads/` again. Only after that, sweep the existing 1 112 entries with
   `scripts/cleanup_orphan_uploads.py` (needs explicit operator authorization).
5. **F-5 (High).** Extend the manifest with **source digests** of the modules on the run's code path
   (a `sourceDigest` map: `chat/rag.py`, `graph/service.py`, `brain/adapters.py`,
   `documents/processing.py`, `documents/structure.py`, `evaluation/**`) plus the corpus digest, and
   refuse — or loudly mark — a research run on a `dirty` tree. This is what would have made
   §8 diagnosable.
6. **F-6/F-7 (Medium).** Unify the guard policy: one module, one identity comparison; make
   `run_table_evidence_measurement.py` use it; document that a same-named remote database is
   permitted, and prefer `DOCUMIND_INTEGRATION_DATABASE_URL` over `--database-url` (keep the flag for
   compatibility, but do not print argv in errors/logs).
7. **F-8 (Medium).** Add the regression tests in §12 so the conventions above are enforced.
8. **F-9/F-12/F-13/F-14 (Low).** Make runner paths repo-anchored (`Path(__file__)`-relative) rather
   than CWD-relative; delete the empty `evaluation/baselines/*` packages or populate them; either
   restore a module-level import guard or document the lazy-import rule in `chat/qa_model.py`.

---

## 12. Exact proposed tests for each high-priority fix

All proposed tests belong to `backend/tests/unit/evaluation/` or `backend/tests/integration/evaluation/`
(TEST_AGENT-owned paths) and must run under `python -m pytest`.

**T1 — no legacy environment mutation survives (F-1).**
`backend/tests/unit/evaluation/test_legacy_runner_isolation.py`
For each of `run_phase3d_evaluation`, `run_phase3e_integration`, `run_phase3e_validation`,
`run_phase3f_evaluation`, `run_phase4b_evaluation`: read the module source via `tests/fixtures/paths.py`
anchors and assert that (a) `os.environ.setdefault("DATABASE_URL"` does not appear, (b) the literal
`postgresql+asyncpg://documind:documind@` does not appear anywhere, and (c) the source contains
`assert_safe_evaluation_target`. Precedent for source-level assertions:
`tests/unit/evaluation/test_runner_report_output.py:240`.

**T2 — the guard runs before any engine in every instrumented runner (F-1/F-3).**
Extend `tests/unit/evaluation/test_evaluation_isolation.py` with a source-order assertion for each
runner: `source.index("assert_safe_evaluation_target(") < source.index("create_async_engine(")`
and `< source.index('os.environ["DATABASE_URL"]')`.

**T3 — Phase 3D cleanup is scoped (F-3).** Two tests:
* unit: `test_phase3d_cleanup_is_scoped` — assert the source contains
  `DELETE FROM document_chunks WHERE document_id IN` and does **not** contain the bare
  `text("DELETE FROM document_chunks")`;
* integration (isolated DB, `tests/fixtures/integration_db.py` guard): seed two documents under two
  users, run only the harness's cleanup routine, and assert the foreign user's chunks are intact
  while the harness's are gone.

**T4 — no runner overwrites a historical report (F-2).**
`backend/tests/unit/evaluation/test_runner_report_output.py` extension: for each of
`run_structure_confirmation`, `run_structure_element_measurement`, `run_structure_rrf_calibration`,
`run_table_evidence_measurement`, assert the module source contains no `REPORTS_DIR` write
(`(REPORTS_DIR /` followed by `write_text`/`open(`) and that it constructs a `RunOutput`; plus a
runtime test that calling the fixed-name write path twice raises `ArtifactExistsError` instead of
replacing files.

**T5 — runners/tests do not write into the application storage root (F-4).**
* integration: a session-scoped fixture redirects `settings.upload_dir` to `tmp_path`; assert after a
  documents upload test that `backend/uploads/` gained **no** new entry (snapshot the directory
  before/after, as `tests/integration/verification/test_image_verification.py:125–135` already does
  for the media path);
* unit: assert no module under `evaluation/experiments/` calls `save_upload` without a preceding
  `settings.upload_dir` (or `DOCUMIND_UPLOAD_DIR`) redirection.

**T6 — manifest records source digests (F-5).**
`test_run_artifacts.py` extension: `collect_run_manifest` includes `sourceDigest` with a SHA-256 per
declared module, that mutating a tracked module changes only its digest, and that a `dirty` tree is
recorded as such (`repository.workingTree == "dirty"` with `changedPathCount > 0`).

---

## 13. Files inspected and commands executed

**Files inspected (source, read-only):**
`AGENTS.md`, `DOCUMIND_PROJECT_CONTEXT.md` (§64 pointer block), `CONTEXT.md`, `ARCHITECTURE.md`,
`PRD.md`; `backend/architecture/PHASE0_CLOSURE_2026-10-09.md`,
`backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md`,
`backend/architecture/PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md`;
`backend/evaluation/{README.md,isolation.py,artifacts.py,runner.py,schemas.py,denominator_sensitivity.py,structure_eval.py}`,
`evaluation/harness/{corpus.py,metrics.py,extraction.py}`, `evaluation/datasets/phase3d_corpus.py`,
`evaluation/baselines/**`, `evaluation/reports/**` (listing + mtimes);
all 13 modules in `evaluation/experiments/`;
`backend/chat/{rag.py,qa_model.py,routes.py}`, `backend/graph/service.py`,
`backend/brain/{adapters.py,gate.py,types.py,response.py}`, `backend/documents/{routes.py,processing.py,structure.py,models.py}`,
`backend/embeddings/model.py`, `backend/storage/{database.py,file_store.py}`, `backend/config.py`,
`backend/main.py`, `backend/answer_span.py`;
`backend/tests/{conftest.py,README.md}`, `tests/fixtures/{paths.py,integration_db.py,e2e_config.py,live_server.py,graph_data.py}`,
`tests/unit/evaluation/**` (listing), `tests/integration/documents/test_file_validation.py`,
`tests/integration/verification/test_image_verification.py`, `tests/e2e/browser/*` (searched);
`backend/scripts/**` (searched), `backend/phases/**` (searched), `backend/.env.example`,
`backend/pytest.ini`, `.gitignore`.

**Commands executed (all read-only; no DB connection, no test suite, no migration):**

```
git status --porcelain
git log --oneline -- backend/chat/rag.py
git show HEAD:backend/chat/rag.py | wc -l | grep "def "
git diff HEAD -- backend/chat/{rag.py,qa_model.py}
git diff HEAD -- backend/evaluation/harness/corpus.py
git diff -U0 HEAD -- backend/chat/rag.py | grep "^@@" | grep "^-"
grep -rn "storage\.database|create_async_engine|DATABASE_URL" backend/evaluation --include=*.py
grep -rn "delete\(|DELETE FROM|TRUNCATE|DROP |drop_all|unlink|rmtree" backend/evaluation/experiments/*.py
grep -rn "async def " backend/chat/rag.py   (and the HEAD revision)
sed -n '<ranges>' on the two instrumented runners, runner.py, isolation.py callers
grep -rn "upload_path|uploads|save_upload|delete_upload" backend/tests --include=*.py
grep -rn "save_upload|delete_upload|cleanup_new_file" backend/evaluation/experiments/*.py
grep -rn "snapshot_download|hf_hub_download|from_pretrained" backend/phases --include=*.py
grep -rli "lecturer" backend --include=*.py --include=*.md
ls backend/uploads | wc -l          # 1112 entries (listed, never modified)
ls -l backend/evaluation/reports    # mtimes only
python -c 'json line parse' on backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl  # read-only
```

No `git diff`/`status` call mutated the tree; no file was written except this report and the §64
pointer.

**Recorded execution evidence relied on (executed by Step 0 on 2026-10-09, not re-run here):**
unit **687 passed**; integration + e2e **275 passed / 6 skipped** (exit 0); focused
`tests/unit/evaluation` **75 passed**; real isolated-DB runs of R1 and R2 (identical repeat metrics;
40/0 checks), the refusal path (exit 2, no artifacts, no directory), the collision refusal
(byte-identical artifacts), and the unreachable-target failure. These are quoted as *previously
recorded* evidence, not as results obtained in this audit.

---

## 14. What could not be verified, and why

| Property | Why unverified | Classification |
|---|---|---|
| Actual behaviour of R3–R11 against a live application database | Executing them would be the destructive act under audit; the task forbids it. | **Unverified** (source-sourced only) |
| Whether the 0.5238 → 0.4524 delta originates in `rag.py`, `graph/service.py`, `brain/adapters.py`, `documents/structure.py`, `documents/processing.py`, or the environment | The entire stack is uncommitted; no earlier revision exists in git; the 2026-10-04 report has no manifest. | **Unverified** (hypothesis stated, §8) |
| Guard behaviour against a same-named database on a different host | Would require provisioning such a server and running a destructive harness. | **Unverified** (policy read from code) |
| Provenance/ownership of the 1 112 `backend/uploads/` entries | Requires inspecting the application database, which is out of scope and not running. | **Unverified** (mechanism verified in code) |
| Whether any historical report's content was previously replaced by a re-run | No backups/commits exist for the untracked `evaluation/reports/*` files. | **Unverified** |
| Behaviour of the 6 browser e2e harnesses | They self-skip without a live server, and starting the stack is out of scope for a read-only audit. | **Not run** (pre-existing skip, unchanged) |
| R24 archived phases | Not executed (GPU/model dependencies); their absence of PostgreSQL access is source-verified for the 40-module tree outside `phase4f_gpu/`. | **Verified by inspection only** |
| PostgreSQL/app-DB access inside the forbidden `backend/phases/phase4f_gpu/**` tree | Forbidden path per `AGENTS.md`; a git-ignored vendored Python environment (13 071 `.py` files, mostly `site-packages`). Deliberately not inspected. | **Not inspected** |
| Test-suite side effects beyond uploads (e.g. writes elsewhere) | Running the suite was deliberately avoided because its side effects are not fully understood — the exact reason the task lists this prohibition. | **Not run** |

---

## 15. Confirmation that no implementation was performed

* **No production code, evaluation runner, test, or fixture was edited, created or deleted.** No file
  in `backend/chat/`, `backend/brain/`, `backend/graph/`, `backend/documents/`, `backend/embedding*/`,
  `backend/evaluation/**` (except the two new documentation files listed below),
  `backend/tests/**` or `backend/scripts/**` was touched.
* **No database operation of any kind:** no connection, no migration, no create/drop/truncate, no
  query. No evaluation runner was executed. No test suite was run.
* **No artifact modified:** `backend/evaluation/reports/**`, `backend/uploads/**`, the frozen
  benchmark, model directories and `.env` files are untouched (read/ls/mtime inspection only).
* **No commit, push, deploy, revert or stash.** `backend/chat/rag.py` was **not** reverted.
* **Files written by this audit (documentation only):**
  1. `backend/architecture/STEP0_5_EVALUATION_RUNNER_SAFETY_AUDIT_2026-10-09.md` (this report);
  2. the one-line canonical pointer in `DOCUMIND_PROJECT_CONTEXT.md` §64.
* **Phase 1 was not started.** No finding was implemented.

The audit is complete. Implementation of any finding requires explicit authorization.
