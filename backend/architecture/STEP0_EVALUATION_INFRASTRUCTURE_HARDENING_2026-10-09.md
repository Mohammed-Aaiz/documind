# DocuMind — Step 0: Evaluation Infrastructure Hardening

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (investigation, implementation, execution, consolidation).
**Specialist review lenses applied (as review responsibilities, not delegated runtime agents):**
8 Software Architect · 11 Database Architect · 17 Backend Coding Specialist · 39 Model
Evaluation · 51 Test Architect · 53 Integration Testing · 54 E2E Testing · 57 AI Evaluation ·
58 Security Testing · 59 Code Review · 61 Reliability · 62 DevOps · 68 Observability ·
72 Application Security · 79 Documentation · 82 Codebase Knowledge · 89 Database Optimization.
**Nature:** evaluation-infrastructure only. No production QA behaviour, retrieval weight,
top-k, chunking, ranking, model, schema, migration, auth or `.env` change. No commit, no push,
no deployment. The architecture/migration gate remains **NOT OPEN** and was not approached.

> Delivers Step 0 of `PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md` §9, and closes the
> evaluation-infrastructure failure **F-07** recorded in
> `PHASE0_CLOSURE_2026-10-09.md` §4.4/§8. New append-only evidence: no existing report,
> benchmark or evidence file was modified.

---

## 1. Initial repository state (verified before any edit)

| Item | Value |
|---|---|
| Branch / commit | `main` @ `6baaa2a0773df66e5fb26814afbe67647fb43435` |
| Working tree | 382 changed paths (pre-existing dirty state, unchanged by this task at start) |
| Alembic head | `007` (not touched) |
| Frozen benchmark | `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` — SHA-256 `1166bf4f…50a41d0`, 182 examples |
| QA weights | `backend/models/documind-qa/model.safetensors` — SHA-256 `cb9f1dde…f69deb` |
| PostgreSQL | **stopped** (the pre-existing baseline); local port 5432 closed, sanctioned port **55433** |
| Application database | identity `('localhost', 55433, 'documind')` |
| Python | 3.11.0 (`backend/venv`) |
| Requirements read | `AGENTS.md`, `DOCUMIND_PROJECT_CONTEXT.md` §64, `backend/evaluation/README.md`, `backend/tests/README.md`, `PHASE0_CLOSURE_2026-10-09.md`, `PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md` |

Both architecture documents named in the task exist and were used as the specification
(`PHASE0_CLOSURE_2026-10-09.md`, `PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md`).

---

## 2. Root cause of each runner's isolation / reporting problem

Traced individually — they are **not** the same defect.

### 2.1 `evaluation/runner.py` (shared report writer)

* `REPORTS_DIR` is a module constant (`evaluation/reports`) with **no override parameter**;
  `write_report(report, name)` always writes `<name>.json` / `<name>.md` there and always
  replaces a same-named file. Re-running a measurement therefore silently replaced recorded
  research evidence.
* `RunReport.to_dict()` dropped `QuestionResult.detail` entirely, so the per-question
  measurements the runner already computes (retrieved/supplied ids, prediction, expected
  answers, confidence) never reached the artifact. "Any number can be traced back to the
  questions that produced it" was true in memory only.
* No run metadata of any kind (commit, corpus version, benchmark digest, model revision) was
  recorded, so a report could not be tied to the state that produced it.

### 2.2 `evaluation/experiments/run_dual_path_ablation.py`

* It imports `from storage.database import async_session, engine` **at module import time**,
  which freezes the engine built from `settings.database_url` — the **application** database.
  There was no parameter, flag or environment variable that could retarget it.
* Every run therefore created and deleted rows in the application database (scoped to its own
  eval user, but still the application database).
* Its report paths were fixed: `evaluation/reports/<prefix>_{A,B,C,D}.json/.md` plus
  `<prefix>_config.json` — running it overwrote the recorded A–D ablations.
* No manifest; `include_detail` did not exist.

### 2.3 `evaluation/experiments/run_phase3d_upload_integration.py`

* A literal DSN was hard-coded twice:
  `create_async_engine("postgresql+asyncpg://documind:documind@localhost:5432/documind")` and
  `os.environ.setdefault("DATABASE_URL", …localhost:5432…)` at import. `DATABASE_URL` and
  `backend/.env` (which uses port **55433**) were both ignored, so the harness could not be
  pointed anywhere else without editing it.
* Its teardown issues an **unscoped `DELETE FROM document_chunks`** (no `WHERE`), in addition
  to deleting the rows of the accounts it created. Against the application database that is a
  destructive operation on live data.
* It produced no artifact at all — its only record was console output — so a run left nothing
  reproducible behind.

### 2.4 Inventory of the remaining runners (unchanged, documented)

| runner | database target as written | guarded? |
|---|---|---|
| `run_phase3d_evaluation.py`, `run_phase3e_integration.py`, `run_phase3e_validation.py`, `run_phase3f_evaluation.py`, `run_phase4b_evaluation.py` | literal `…@localhost:5432/documind` | no |
| `run_structure_confirmation.py`, `run_structure_element_measurement.py`, `run_structure_rrf_calibration.py` | application engine (`storage.database`) | no |
| `run_table_evidence_measurement.py` | `DOCUMIND_PHASE4_DATABASE_URL` else `settings.database_url`, plus a **loopback-only** host check | loopback only (no application-identity comparison) |
| `run_phase4c_diagnostics.py` | model/offline only | n/a |

Only the two runners named in the task's mandatory inspection list were instrumented. The
others are explicitly **not** fixed, and §7 records that as a limitation with the evidence
above rather than implying they are safe.

---

## 3. Files changed and why

### Added

| File | Why |
|---|---|
| `backend/evaluation/isolation.py` | Resolves the evaluation DSN and owns the *identity* guard that refuses the application database (and fails closed when an identity cannot be established). Pure string inspection: no connection, no DDL. |
| `backend/evaluation/artifacts.py` | `RunOutput` (caller-specified directory, pre-flight reservation, exclusive create, never overwrite) + `collect_run_manifest` / `benchmark_digest` / `model_provenance` / `repository_state` (reproducibility metadata, credential-free). |
| `backend/tests/unit/evaluation/test_evaluation_isolation.py` | 26 tests: target resolution, guard acceptance/rejection, fail-closed cases, credential-free errors, no-connection property, consistency with the test layer's guard. |
| `backend/tests/unit/evaluation/test_run_artifacts.py` | 18 tests: exclusive writes, pre-flight, race behaviour, two-run separation, manifest fields, unavailable-not-invented, frozen benchmark digest, real QA weights digest, no credentials. |
| `backend/tests/unit/evaluation/test_runner_report_output.py` | 20 tests: attribution taxonomy, per-question diagnostics, legacy report-format compatibility, `--out` append-only behaviour, CLI contract. |
| `backend/architecture/STEP0_EVALUATION_INFRASTRUCTURE_HARDENING_2026-10-09.md` | This report. |

### Modified

| File | Change |
|---|---|
| `backend/evaluation/runner.py` | `classify_question_outcome` (read-only attribution), `measure_question` records evidence ranks + outcome + failure category in `detail`, `write_report(..., out_dir=None, include_detail=False)`. Default path and default payload are unchanged. |
| `backend/evaluation/schemas.py` | `RunReport.to_dict(include_detail=False)`; per-result `detail` only when requested; additive `includes_per_question_detail` marker. |
| `backend/evaluation/experiments/run_dual_path_ablation.py` | `--database-url` + `--out` (required); guard before the first connection; `storage.database` imported *after* the verified DSN is placed in the environment; artifacts reserved before the run; reports + config + `run_manifest.json` written to `--out`; manifest written in a `finally` (status `failed` + exception type on failure). |
| `backend/evaluation/experiments/run_phase3d_upload_integration.py` | Hard-coded DSN removed; `--database-url` (env override) + guard before import of the app; optional `--out` writing `checks.json` + `run_manifest.json`; structured per-check results; manifest in a `finally`. |
| `backend/evaluation/README.md` | Documents the isolation model, the guard, `--out`/append-only behaviour, the manifest, and which runners are instrumented vs not. |

No production module, model, schema, migration, benchmark, historical report, `.env` or
frontend file was modified. `Tests → evaluation` remained the only import direction
(`evaluation/isolation.py` deliberately **mirrors** `tests/fixtures/integration_db.py` instead
of importing it; a unit test pins that the two stay in step).

---

## 4. Database safety mechanism, and its limits

**Resolution precedence for the evaluation target**

```
--database-url <dsn>                     (highest)
DOCUMIND_INTEGRATION_DATABASE_URL=<dsn>  (same variable the test layer honours)
the application DSN                     (pre-existing behaviour; the guard then refuses it)
```

`application_database_url()` reads `backend/.env` **first** and only then falls back to the
environment/settings, so a runner that exports `DATABASE_URL` for its own child processes
cannot redefine which database counts as the application's.

**The guard** (`assert_safe_evaluation_target`) compares the complete identity
`(host, port, database)` — never a bare name — and:

1. refuses when the target is the application database;
2. fails closed when the **target's** identity cannot be established (no host / no database
   name, e.g. a SQLite DSN);
3. fails closed when the **application's** identity cannot be established, because the target
   then cannot be *shown* to differ;
4. raises a credential-free, actionable error naming the operation and the environment
   variable to set.

It reads no rows and opens no connection, so it is safe against a database that is down or
does not exist (a unit test pins that the module contains no engine/connection/subprocess call).

**Limitations (deliberate):**

* It does **not** provision, create, migrate, verify or drop a database. The runner consumes a
  pre-existing isolated database; if none is provided it stops rather than provisioning one.
* It cannot prove the target is empty, migrated or dedicated — only that it is not the
  application database.
* It does not require the conventional name `documind_integration`: any target whose identity
  differs from the application's is accepted (a different name, host or port), which is the
  documented test-layer rule.
* `--database-url` places credentials on the process command line; the environment variable is
  the documented, argv-safe form. Credentials never appear in output, errors, reports or
  manifests (only `scheme://host:port/database` and `host:port/database` are printed).
* The unscoped `DELETE FROM document_chunks` inside the Phase 3D harness was **left as it is**
  (minimal change); it is now only reachable against a guarded, isolated database. Scoping it
  is a follow-up, not part of Step 0.

**Evidence (executed):**

| Check | Command | Observed |
|---|---|---|
| application DB rejected | `run_dual_path_ablation.py --out …` (no override) | exit **2**, `REFUSING … the target localhost:55433/documind is the application database`, output directory **not created** |
| application DB rejected | `run_phase3d_upload_integration.py --out …` (no override) | exit **2**, same refusal, output directory not created |
| isolated target accepted | both runners with `DOCUMIND_INTEGRATION_DATABASE_URL` | printed `application : localhost:55433/documind` / `evaluation : localhost:55433/documind_integration`, then ran against the isolated database |
| unreachable isolated target | explicit DSN, PostgreSQL stopped | guard passed (no silent fallback), connection refused, exit **1**, `run_manifest.json` written with `result.status = failed` |
| isolation never touched the app DB | `SELECT datname FROM pg_database` after all runs | only `documind, postgres, template0, template1` — `documind_integration` was created, used and dropped; the application database was used solely as the maintenance connection |

---

## 5. Output directory, no-overwrite behaviour, and partial runs

* `--out` is **required** for the ablation runner and **optional** for the Phase 3D harness.
* Every artifact the run will produce is **reserved before the run starts**; any collision
  aborts the run before a single byte is written (and, for the ablation runner, before any
  connection or ingestion).
* Writes use `open(path, "x")` (exclusive create), so a file appearing between reservation and
  write is not replaced either; `FileExistsError` is re-raised as `ArtifactExistsError`.
* `newline="\n"` keeps the recorded bytes platform-independent.
* The **manifest is written last and always**: a directory containing reports but no
  `run_manifest.json` is by definition an interrupted run; on failure the manifest records
  `result.status = "failed"` with the exception type (never a message that could carry
  credentials).
* Nothing is deleted and nothing outside `--out` is written. `evaluation/reports/*` is never
  touched by these runners.
* **Documented exceptions:** `structure_eval.py` and `denominator_sensitivity.py` keep their
  existing overwrite behaviour. Their output is a timestamp-free, byte-reproducible *derived*
  artifact and their unit tests pin regeneration (`write twice → identical bytes`); changing
  that contract is a separate decision, and it is recorded in `evaluation/README.md` rather
  than silently changed.

**Evidence (executed):** a second run into the **same** `--out` directory exited **2** with
`refusing to overwrite existing evaluation artifacts: …`, and all ten previously written files
were byte-identical afterwards (`sha256sum -c` → `OK` for every file).

---

## 6. Manifest and diagnostic schema

### 6.1 `run_manifest.json` (schema version 1)

```
schemaVersion, runId (YYYYMMDDTHHMMSSZ-<8hex>), runner, protocol, generatedAt, python
repository  : commit, branch, workingTree (clean|dirty|unavailable), changedPathCount
database    : evaluation / application identities (host:port/db), isolated, operation
dataset     : identifier, version, documents, questions, answerable, unanswerable,
              withGoldChunks, categories, chunker, goldChunkLabels
benchmark   : path (backend-relative), sha256, bytes, examples
configuration: the exact production configuration measured (chunker, retrieval weights, topK,
              RRF, hop limits, element-stream caps, gate thresholds)
model       : qaModelPath, qaModelWeights, qaModelWeightsSha256, qaModelWeightsBytes,
              embeddingModel, embeddingDimensions
output      : directory (repo-relative, else base name), plannedFiles, filesWritten
result      : status (completed | completed_with_failures | failed) + counts or errorType
```

Every field that cannot be determined is `"unavailable"` — never invented. Nothing in the
manifest is a credential: database entries are identities, and no environment value, `.env`
content, document text or absolute checkout path is copied in.

### 6.2 Per-question diagnostics (`detail`, opt-in via `include_detail`)

Added to each result when a run writes to a caller-supplied directory; the historical report
format is untouched otherwise.

```
retrieved, retrieved_ranks {id: rank}, supplied, supplied_ranks {id: rank},
predicted, expected, confidence, insufficient_context,
retrieval_paths, structural_hops,
gold_retrieved, gold_supplied,
outcome         : correct | incorrect | abstained | unsupported_answer | correct_abstention
failure_category: none | answer_stage | retrieval_miss | unlabelled_evidence |
                  abstained_on_answerable | unsupported_answer
```

The attribution rule is the Phase 0 one: an incorrect answer **whose gold evidence was
supplied** to the answer stage is an `answer_stage` failure; an incorrect answer whose gold
evidence was never retrieved is a `retrieval_miss`; a question with no gold labels is reported
as `unlabelled_evidence` rather than being assigned a cause. `unsupported_answer` mirrors
`qa_metrics.unsupported_answer_rate` exactly, so the label and the aggregate can never disagree.
The Phase 3D harness additionally writes `checks.json` (structured `name`/`status`/`detail` per
check).

---

## 7. Tests executed and actual results

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `python -m pytest -q tests/unit/evaluation` | **184 passed** (120 collected before this task; +64 new) | 0 |
| 2 | `python -m pytest -q tests/unit` | **687 passed** (623 before; +64 new — the same 623 the Phase 0 closure recorded) | 0 |
| 3 | `python -m pytest -q tests/integration tests/e2e` (PostgreSQL up) | **275 passed, 6 skipped** (the 6 are the live-server e2e harnesses; the DB-gated `test_real_e2e_validation` ran and passed) | 0 |
| 4 | `run_dual_path_ablation.py` on a **freshly provisioned isolated DB**, `--out` | 12 docs → 79 chunks, 39/42 labelled; A `R@5 0.7738 / EM 0.4524 / F1 0.5701`, C/D `R@5 0.7738`; **10 artifacts** written; manifest `result.status = completed`; isolated DB dropped | 0 |
| 5 | same runner, **second** run into a second directory | **identical metrics** to run 4 — the runner is deterministic run-to-run | 0 |
| 6 | same runner, **same** `--out` directory | exit **2**, refusal before connecting, all 10 artifacts byte-identical afterwards | 2 |
| 7 | `run_phase3d_upload_integration.py` on a freshly provisioned isolated DB, `--out` | **40 passed / 0 failed**; `checks.json` + `run_manifest.json` written; isolated DB dropped | 0 |
| 8 | both runners with no isolated target | exit **2**, credential-free refusal, no artifacts, no directory created | 2 |

Coverage against the required test list (§5 of the task): (1) explicit isolated configuration
— `TestTargetResolution`; (2) invalid configuration fails safely — empty-string override,
unparseable identity, unreachable target; (3) application-database targets rejected before
destructive operations — `TestGuardRefusesTheApplicationDatabase` + executed refusals;
(4) unresolvable identity fails closed (both directions); (5) caller-specified output
directories honoured; (6) existing reports not overwritten; (7) two runs produce separate
artifacts; (8) manifests contain the expected non-sensitive metadata;
(9) secrets/credentials absent from reports, manifests and console output; (10) existing
runner behaviour remains compatible — `TestLegacyReportFormatIsUnchanged`.

**Destructive protections were never tested by attacking the application database**: the guard
is pure string inspection, so the rejection tests need no database, and the real runs used a
throwaway database created and dropped by the sanctioned integration fixture.

### 7.1 Protected-artifact verification

| Artifact | Before | After |
|---|---|---|
| Frozen benchmark SHA-256 | `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (182 examples) | **unchanged** — re-verified by `benchmark_digest()`, recorded in every manifest, and pinned by a unit test |
| QA weights SHA-256 | `cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb` | **unchanged** (digest recorded per run) |
| Alembic head | `007` | **unchanged** (no migration added or run against the application database) |
| `evaluation/reports/*` (recorded measurements) | mtimes 2026-10-04 | **unchanged** — no runner wrote into that directory during this task |
| Application database `documind` | identity `('localhost', 55433, 'documind')` | **untouched** — only ever the maintenance connection for `CREATE`/`DROP DATABASE` |
| PostgreSQL service | stopped | stopped again (cluster started for the isolated runs, then stopped to restore the baseline) |

### 7.2 A measurement observation (recorded, not a Step 0 defect)

The fresh A–D run does **not** reproduce the 2026-10-04 recorded report exactly: retrieval
metrics are **identical** (`recall@5 0.7738`, `precision@5 0.1905`, `mrr 0.7417`, `ndcg@5
0.7268`, `evidence_coverage 0.9905`, `factual_grounded 0.9762`, `unsupported_answer 1.0`), but
`exact_match` is **0.4524** vs the recorded **0.5238** and `token_f1` 0.5701 vs 0.6296. Three
questions differ: `ss_3`, `dp_4`, `md_1`.

The new diagnostics localise all three to the **answer stage**, with the gold evidence
supplied: `'3 kilograms.'` vs gold `'3 kilograms'`, and `'1850.\n\n1'` / `'2005.\n\n1'` vs gold
`'1850'` / `'2005'` — the over-wide / trailing-boundary spans recorded as **F-03** in the
Phase 0 closure. Two facts bound the cause: (a) the scoring and aggregation code paths were not
touched (retrieval metrics are byte-identical, and the change adds only read-only bookkeeping);
(b) `backend/chat/rag.py` — which contains context construction and retrieval — carries an
**uncommitted** modification dated **2026-10-06 03:04**, i.e. *after* the recorded report
(2026-10-04 18:16). The most probable explanation is therefore that the recorded report predates
an uncommitted change to production retrieval/context code, not anything in Step 0.

This is exactly the class of drift Step 0 exists to make visible; it is **not** a claim that
either number is wrong, and no product behaviour was changed to reconcile them.

---

## 8. Tests not run, and why

* **Live-server / browser e2e** (6 tests): no Vite dev server and no uvicorn were started, so
  they report as *skipped*. Unchanged from the Phase 0 baseline.
* **The full 42-question frozen benchmark run** and the other research runners
  (`run_phase3*`, `run_phase4b`, `run_table_evidence_measurement`, `run_structure_*`): they
  remain un-instrumented and were deliberately not executed — running them would target the
  application database (five hard-code it) or overwrite recorded reports. Their status is
  documented in §2.4 instead of being implied safe.
* **No new evaluation result is claimed.** The two real runs above are verification of the
  infrastructure (artifacts, guard, determinism), not a new measurement of the system, and the
  numbers in §7.2 are recorded as an observation for Phase 1.

A safe command for a later, provisioned run:

```bash
cd backend
DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:<port>/documind_integration \
  ./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py \
    --corpus phase3d --out <new-empty-directory>
```

---

## 9. Known limitations

1. Only `run_dual_path_ablation.py` and `run_phase3d_upload_integration.py` are instrumented;
   ten research runners still hard-code or default to the application database (§2.4).
2. No provisioning helper: an isolated database must exist and be migrated before a run
   (deliberate — it keeps destructive DDL out of research code). If none is available the run
   stops and reports the blocker.
3. `dataset.version` is `"unavailable"` for the labelled corpora: they carry no version
   constant, and inventing one would be worse than recording the absence.
4. The Phase 3D harness's unscoped `DELETE FROM document_chunks` is unchanged (only reachable
   against a guarded isolated database) — scoping it is a follow-up.
5. The manifest records what the runner knows: latency and peak-memory metrics are not
   captured (still `UNAVAILABLE`, per the Phase 1 plan §7).
6. `--database-url` puts credentials on argv; the environment variable is the argv-safe form.
7. Corpus-level abstention (Phase 0 F-08) is **not** addressed here: the phase3d corpus'
   unanswerable questions are still not attached to its documents.
8. **`backend/uploads/` is written by the test suite, not by the runners.** The evaluation
   runners were executed with `UPLOAD_DIR` pointed at a temporary directory (30 files landed
   outside the repository, and no runner wrote into the repository). Running the sanctioned
   integration suite, however, drives the real upload route, which stores files under the
   application's own `settings.upload_dir` (`./uploads`) — that is why `backend/uploads/` gained
   files during this task's test runs (the clusters at 21:00 and 21:07–21:08 are inside the two
   suite windows; earlier clusters in the same day predate this task's first edit). Nothing in
   that directory was deleted or modified by hand, and it is untracked/ignored. Pointing the
   test app at a test-owned upload directory (as `tests/e2e/browser` already does via
   `GENERATED_UPLOADS_DIR`) or purging it in a fixture is a TEST_AGENT-owned follow-up.

---

## 10. Confirmations

* **Production QA behaviour was not changed.** No file under `chat/`, `brain/`, `documents/`,
  `embeddings/`, `graph/`, `reliability/`, `auth/`, `storage/` or `config.py` was modified; no
  model, weight, threshold, retrieval weight, top-k, chunker, prompt or gate rule changed; no
  schema or migration changed; the frontend was not touched. The changed code paths are
  additive: report routing, metadata capture and safety checks. The run-4/run-5 evidence
  (identical metrics on repeat, retrieval metrics identical to the recorded run) is consistent
  with there being no behavioural change.
* **No commit, push or deployment occurred.** `git` was used only for read-only inspection
  (`rev-parse`, `status`, `log`) and as a manifest data source.
* **No hidden writes by the code under change.** All run artifacts went outside the repository
  (temporary directories); the isolated database was created, used and dropped; both evaluation
  runners ran with `UPLOAD_DIR` redirected to a temporary directory (30 stored files, all
  outside the repository); the application database was never written. The one write inside the
  repository is the side effect described in §9.8: the integration suite exercises the real
  upload route, which stores files in the application's configured storage root.

## 11. Recommended next step

Per `PHASE1_GROUNDED_ANSWERING_PLAN_2026-10-09.md` §12, **Step 2 — answer-boundary / typed-span
selection (Class B)** is now measurable: the runner is isolation-safe, append-only, and captures
per-question evidence. The three boundary failures in §7.2 (`'3 kilograms.'`, `'1850.\n\n1'`,
`'2005.\n\n1'`) are the concrete acceptance cases it should fix. Instrumenting the remaining
runners (F-07's second half) and attaching the corpus' unanswerable questions (F-08) remain
small, separately-approvable infrastructure items.
