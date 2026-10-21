# DocuMind — Phase 0 Closure: Isolated End-to-End Evaluation and Readiness Verification

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (investigation, execution, consolidation).
**Specialist review lenses:** 8 Software Architect, 11 Database Architect, 14 Security
Architect, 36 RAG Engineer, 39 Model Evaluation, 41 Embeddings/Vector Search,
51 Test Architect, 53 Integration Testing, 54 E2E Testing, 57 AI Evaluation,
58 Security Testing, 59 Code Review, 61 Reliability, 62 DevOps, 68 Observability,
75 Identity/Auth, 79 Documentation, 81 Architecture Documentation, 82 Codebase Knowledge,
89 Database Optimization.
**Nature:** evaluation-readiness and verification only. No production code, schema,
migration, model weight, `.env`, or frozen-benchmark change. No commit. No push.

> Companion to `backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md` (the first Phase 0
> audit). This document closes the two gaps that audit left open: an isolated
> PostgreSQL + pgvector end-to-end evaluation, and a verified environment baseline.
> This is new append-only evidence; no existing evidence file was modified.

---

## 1. Executive summary

- **An isolated evaluation database was established and verified.** The project's own
  PostgreSQL 16 + pgvector cluster was started on the sanctioned runtime port, and the
  sanctioned isolation fixture provisioned a **separate database** `documind_integration`
  (identity `localhost:55433/documind_integration`) distinct from the application database
  (`localhost:55433/documind`). It was migrated to head, verified, used, and dropped.
- **The real production request path ran end to end against that isolated database**, both
  through the sanctioned integration validation (retrieval → Brain → answer → reliability →
  abstention → isolation → 503) and through the full HTTP path (`/api/documents/upload` →
  extraction → chunking → embeddings → persistence → `/api/chat/ask` → evidence/reliability).
- **A labelled 12-document / 39-question corpus was evaluated end to end** through the real
  HTTP path on the isolated database: **ingestion 12/12 ready, evidence-recall 89.7 %,
  answerable EM 33.3 % / token-F1 61.6 %**. Failures are **predominantly answer-stage**
  (22/39 wrong despite the gold evidence having been retrieved) rather than retrieval
  (4/39 gold-evidence misses).
- **Regression suite re-run (fresh):** unit **623 passed**; integration **275 passed,
  0 skipped** (the previously-skipped DB-gated validation now ran and passed); e2e
  **6 skipped** (no live server) — **898 passed, 6 skipped, 0 failed** of 904 collected.
- **Frozen benchmark unchanged** (SHA-256 verified, 182 examples); migration head `007`;
  working-tree changed-path count identical before and after (382).
- **Phase 0 exit criteria are met**, with the explicit scope note that the **lecturer-specific
  datasets** (exam marks, calculation, scanned/OCR, cross-document, entity multi-hop, charts)
  remain **untested capabilities**.

---

## 2. Verified environment baseline (Workstream A)

| Item | Value (verified 2026-10-09) |
|---|---|
| Branch / commit | `main` @ `6baaa2a` |
| Working tree | 382 changed paths before and after (pre-existing dirty state; unchanged by this audit) |
| Python | 3.11.0 (`backend/venv`) |
| Model artifacts | `backend/models/documind-qa`, `backend/models/media-verification`, `backend/models/whisper/small` — all present |
| Alembic head | `007 (head)` |
| Frozen benchmark | `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` — SHA-256 `1166bf4f…50a41d0`, 182 examples |
| Docker | **unavailable** (`docker info` fails; no Compose) |
| Local port 5432 | **closed** |
| Application DB (from `backend/.env`) | identity `('localhost', 55433, 'documind')` |
| Evaluation scripts | `backend/evaluation/experiments/` (14 runners incl. `run_dual_path_ablation.py`, `run_phase3d_upload_integration.py`) + `backend/evaluation/{structure_eval.py,denominator_sensitivity.py}` |
| Integration fixtures | `backend/tests/fixtures/{integration_db.py, e2e_config.py, live_server.py, pdf_layout.py, integration_http.py}` |
| Secrets | `.env` never read/printed; only `.env.example` (template) inspected; no credential appears in this report or its logs |

Note: the local cluster at `C:/pgdata/data` was **not running** at the start of this task;
it was started on port 55433 for the evaluation and stopped again at the end (§3.4).

---

## 3. Database isolation evidence (Workstream B)

### 3.1 Why the isolated database is required
`tests/integration/rag/test_real_e2e_validation.py` is destructive: its first act is to
delete every row from `users`, `documents` and `document_chunks`. It must therefore never
run against the application database.

### 3.2 The isolation mechanism (existing, reused — not invented)
`backend/tests/fixtures/integration_db.py`:
- resolves the target from the application DSN by swapping in the database name
  `documind_integration` (or `DOCUMIND_INTEGRATION_DATABASE_URL`);
- `assert_isolated_target()` compares the **complete identity `(host, port, database)`**
  and refuses when it equals the application's;
- drops/creates the database, runs `alembic upgrade head` in a subprocess pinned to that
  DSN, verifies `revision == head`, `pgvector` present, and the 14 required tables;
- drops the database on every exit path.

### 3.3 Isolation demonstrated
- app identity `('localhost', 55433, 'documind')` vs integration identity
  `('localhost', 55433, 'documind_integration')` — **same server, different database**.
- provisioning output (observed): `revision=007 pgvector=0.8.6 tables=14`.
- role `documind` has `rolcreatedb = t` (and `rolsuper = t`).
- after all runs, `SELECT datname FROM pg_database` returned only
  `documind, postgres, template0, template1` — **`documind_integration` was dropped**.
- the application database `documind` was used only as the maintenance connection for
  `CREATE DATABASE` / `DROP DATABASE` and catalogue reads — never written.

### 3.4 Repeatable setup / teardown
```bash
# start the project's own PostgreSQL 16 cluster on the sanctioned port (was stopped)
"C:/pg/pg16/pgsql/bin/pg_ctl.exe" -D "C:/pgdata/data" -o "-p 55433" -l "C:/pgdata/logs/pg_run.log" start
# provision + migrate + verify + drop the isolated database (fixture):
#   python -c "from tests.fixtures.integration_db import provisioned_integration_database as p; ..."
# stop again (restore baseline)
"C:/pg/pg16/pgsql/bin/pg_ctl.exe" -D "C:/pgdata/data" stop -m fast
```
An important operational note discovered here: `pg_ctl start` **must be run as a persistent
process**. When it was launched from a command whose process tree was later terminated, the
postgres children died with `0xC0000142` (STATUS_DLL_INIT_FAILED) ~60 s after startup. Started
as a long-lived process, the cluster ran normally for the whole evaluation.

---

## 4. End-to-end execution status (Workstream C)

### 4.1 Sanctioned integration validation — PASSED
Command: `python -m pytest tests/integration/rag/test_real_e2e_validation.py -q -s`
Result: **1 passed in 14.08 s** (exit 0). Stages exercised with real PostgreSQL + pgvector +
the real DocuMind QA model:
- **Step 4** document → embeddings → pgvector retrieval → Brain → answer:
  answer derived from the uploaded document, `qaConfidence 0.8352`, `retrievalScore 0.6691`,
  `factualGrounded True`, retrieval+answer 187 ms.
- **Step 5** out-of-corpus question → `INSUFFICIENT_EVIDENCE` (honest abstention).
- **Step 6** user isolation: User A cannot see User B's document; User B can.
- **Step 7** QA model unavailable → `UNAVAILABLE` → HTTP 503 contract preserved.
- The provisioned database was dropped at the end (`[integration-db] dropped documind_integration`).

### 4.2 Full HTTP production request path — executed
A throwaway driver (stdin script, **no repository file created**) drove the real FastAPI app
in-process via the ASGI transport against the isolated database:
`login 200 → upload 201 → PDF extraction → 8 chunks persisted → embeddings ready → document
status ready → /api/chat/ask`.

| Observation | Value |
|---|---|
| Upload → document status | `ready`, `chunkCount 8`, `embeddingStatus ready`, `fileType pdf` |
| Answerable question | answer `"1859"`, outcome `SUCCESS`, 13 sources |
| Reliability | `qaConfidence 0.5293`, `retrievalScore 0.774`, `sourceCount 13`, `retrievedSourceCount 13`, `factualGrounded true`, `pathAgreement true` |
| Unresolved question | outcome `INSUFFICIENT_EVIDENCE`, empty answer |

### 4.3 Labelled corpus end-to-end evaluation (isolated DB) — executed
`backend/evaluation/datasets/phase3d_corpus.py` (12 real documents, DOCX/PDF/TXT) was
ingested through the **real HTTP upload path** and its 39 answerable questions asked through
`/api/chat/ask`, on the isolated database:

| Metric | Value | Population / protocol |
|---|---:|---|
| Documents ingested | **12 / 12** (0 upload failures, 0 `error` statuses) | production upload → extraction → chunking → embeddings |
| Answerable EM | **33.3 %** | n = 39, normalised exact match vs corpus `expected_answer` |
| Answerable token-F1 | **61.6 %** | n = 39, token-set F1 |
| Answerable evidence recall | **89.7 %** | fraction where a corpus `evidence` substring is present in ≥1 returned source |
| Gold-evidence misses (retrieval gap) | **4 / 39** | evidence substring absent from all returned sources |
| Wrong answer **despite evidence present** | **22 / 39** | answer-stage failures |
| Unanswerable questions | **0** attached to corpus documents | corpus's unanswerable questions are not attached to `CorpusDoc.questions`; **not measured here** |

Representative answer-stage failures (evidence present, answer wrong):
`14` vs gold `14 watts`; `3 kilograms.` vs `3 kilograms`; `A Tundra torque wrench` vs
`Tundra torque wrench`; table `85 percent` vs gold `92 percent`; `Results\nThe recommended
configuration` for a table question. These are **span-boundary / wrong-region** errors, not
missing retrieval.

### 4.4 What did **not** run end to end
- The **full-ingestion evaluation runner** `backend/evaluation/experiments/run_phase3d_upload_integration.py`
  (which drives upload→ask for both chunkers) is **hardcoded to the application database**
  (`postgresql+asyncpg://documind:…@localhost:5432/documind`) and ignores `DATABASE_URL`.
  Pointing it at the isolated database would require editing evaluation code — **not
  authorized** in this task. §4.2/§4.3 reproduce its core path with an isolated-DB driver instead.
- The **A–D ablation runner** `run_dual_path_ablation.py` writes its reports into
  `backend/evaluation/reports/ablation_*.json`, which would **overwrite recorded evidence**
  (forbidden). It was not run.
- A **browser/E2E** run (Vite + live uvicorn) was not performed.

---

## 5. Test results (Workstream G) — fresh re-run

| Group | Command | Result | Exit | Wall |
|---|---|---|---|---|
| Unit | `python -m pytest tests/unit -q` | **623 passed** | 0 | 40.50 s |
| Integration | `python -m pytest tests/integration -q` | **275 passed** | 0 | 216.69 s |
| E2E | `python -m pytest tests/e2e -q` | **6 skipped** (no live server) | 0 | 15.17 s |
| Collection | `pytest tests --collect-only -q` | **904 collected** | — | — |
| **Totals** | — | **898 passed, 6 skipped, 0 failed** | — | — |

Difference vs the previous audit: integration is now **275 passed, 0 skipped** (previously
274 passed, 1 skipped) because the previously-skipped `test_real_e2e_validation` ran against
the now-reachable isolated database and passed. The 6 e2e skips remain environmental.

---

## 6. Benchmark integrity

- SHA-256 `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matched** (re-checked after all runs).
- 182 examples; manifest 140 answerable / 42 unanswerable. **Unchanged.**
- The 42 unanswerable examples are benchmark rows, not attached to the corpus documents, so
  the corpus end-to-end run (§4.3) does not measure abstention — see §8 (F-01) and §9.

---

## 7. Metrics and evaluation protocol (Workstream F)

| Metric | Value | Dataset | Protocol / boundary |
|---|---:|---|---|
| Unit/integration/e2e counts | 898/6/0 | `backend/tests/` | SQLite in-memory + isolated pgvector DB for the DB-gated test |
| Ingestion success | 12/12 docs ready | phase3d_corpus | real HTTP upload on isolated DB |
| Answerable EM | 33.3 % | phase3d_corpus (39 q) | normalised EM; production extractive QA |
| Answerable token-F1 | 61.6 % | phase3d_corpus (39 q) | token-set F1 |
| Evidence recall | 89.7 % | phase3d_corpus (39 q) | corpus `evidence` substring present in returned sources |
| Model-only EM / F1 | 15.71 % / 38.02 % | frozen benchmark (140 q) | production QA model, gold context, no retrieval (previous audit) |
| Model-only abstention | 0/42 | frozen benchmark (42 q) | model answers all unanswerable rows |
| End-to-end latency | 187 ms (retrieval+answer) | single Darwin question | in-process ASGI; not a load benchmark |

**Not measured (and why):** abstention on the corpus (no corpus-attached unanswerable
questions in the harness used); Recall@k / MRR / nDCG on the corpus (gold is the corpus
`evidence` substring, not labelled chunk ids, in this harness — the A–D runner computes
chunk-level recall but was not run to avoid overwriting recorded reports); completeness /
source-attribution rubrics; calculation correctness; OCR/chart accuracy; exam-mark scores;
peak RAM/VRAM. Do not compare the model-only numbers (§7 row 6) with the corpus numbers
(rows 3–4): different populations, protocols and boundaries.

---

## 8. Failure inventory and attribution (Workstream D)

Confidence: confirmed / strongly supported / tentative / unknown.

| ID | Reproduction | Expected → Actual | Earliest failing stage | Confidence | Reproduced vs inferred | Minimal fix | Regression test | Gate |
|---|---|---|---|---|---|---|---|---|
| F-01 | model-only benchmark (42 unanswerable) | abstain → **answered all 42** | answerability/abstention | confirmed | reproduced | separate answerability gate | gate seam test | ADR (Gate 2) |
| F-02 | corpus tables (`ts_1`, `tl_1`) | correct cell/row → wrong value / blended rows | answer selection + table representation | confirmed | reproduced | row/cell-aware evidence + typed span | table seam test | ADR + schema |
| F-03 | corpus (§4.3) 22/39 wrong with evidence present | correct span → **over-wide / wrong-region span** | answer selection (boundary) | confirmed | reproduced | span-boundary constraint | boundary unit test | model/answer review |
| F-04 | corpus 4/39 | correct evidence retrieved → **missing** | retrieval/ranking | confirmed (small n) | reproduced | retrieval recall work | retrieval seam test | ADR (Gate 1) |
| F-05 | structure reports (recorded) | ranked element contribution → none at 0.70/0.30 | retrieval/fusion | strongly supported | inferred from recorded | calibrate prior after replication | fusion test | ADR (weights) |
| F-06 | reachability audit (recorded) | chunk section/heading metadata → **0 persisted (legacy chunker)** | chunking/representation | strongly supported | inferred | enable structure-v2 (**schema**) | chunker test | ADR + schema |
| F-07 | §4.4 | full-ingestion runner on isolated DB → **hardcoded to app DB/5432** | evaluation infrastructure | confirmed | reproduced | accept isolated DSN + output dir in the runner | runner unit test | eval-infra |
| F-08 | corpus harness | abstention measured on corpus → **not measured** (no attached unanswerable) | evaluation infrastructure | confirmed | reproduced | attach unanswerable questions to the corpus harness | — | eval-infra |
| F-09 | OCR/math/scanned/cross-doc/marks | capabilities → **not implemented / no fixtures** | — | confirmed | absent | build datasets + capability (separate phases) | — | ADR + datasets |

Attribution rule applied: a wrong answer with the gold evidence present is attributed to the
**answer stage** (F-03), not retrieval; an answer with the evidence absent is attributed to
**retrieval** (F-04). No model-only inference was substituted for the end-to-end runs.

---

## 9. Dataset inventory and missing coverage (Workstream E)

| Capability | Dataset present | Status |
|---|---|---|
| Direct factual | frozen benchmark `DIRECT_SPAN` (24); phase3d_corpus | present |
| Table cell / row | benchmark `TABLE_CELL` (24) / `TABLE_ROW` (16); `table_evidence_*` | present |
| List / section | benchmark `LIST_ITEM` (20) / `SECTION_SPECIFIC` (16) | present |
| Long-context / multi-chunk | benchmark `LONG_CONTEXT` (10) / `MULTI_CHUNK` (10) | present |
| Unanswerable | benchmark 42 | present (benchmark) |
| Cross-document | — | **missing** |
| Genuine multi-hop entity–relation | structure_discriminating multi-hop subset (8) | **partial** (no entity ground truth) |
| Mathematical calculation / unit conversion | — | **missing** (benchmark `NUMERIC` is value extraction only) |
| Exam-style 5/10/15 marks | — | **missing** |
| Scanned PDF / OCR | — | **missing** |
| Charts / visual elements | — | **missing** |

**Collection specification for each missing dataset** (intended capability → sources →
annotation → metrics → QC → coverage → privacy/licensing):

1. **Cross-document** — capability: combine evidence across documents. Sources: 2–4 related
   public documents per question (e.g. spec + changelog). Annotation: gold answer + per-doc
   evidence spans and a contradiction flag. Metrics: EM/F1, evidence recall across docs,
   contradictory-source rate. QC: two annotators, adjudication. Coverage: ≥40 questions.
2. **Entity multi-hop** — capability: A→C→B relationship chains. Sources: documents with
   explicit entity relations. Annotation: entity/relation ground truth + supporting clause.
   Metrics: answer EM, path correctness, evidence coverage. QC: schema-validated annotations.
   Coverage: ≥30 chains. Licensing: original or permissively licensed text only.
3. **Mathematical calculation** — capability: retrieve formula/values, compute, validate units,
   explain. Sources: textbook-style problems with in-document formulas/tables. Annotation:
   values, formula, unit, expected numeric result with tolerance, step rubric. Metrics: numeric
   accuracy (tolerance), unit correctness, step completeness. QC: solver cross-check. Coverage:
   ≥50 problems across arithmetic/percentage/unit conversion.
4. **Exam-style 5/10/15** — capability: planned, mark-weighted answers. Sources: academic
   documents + a marks rubric. Annotation: mark value, required coverage points, per-point
   evidence link. Metrics: rubric coverage, evidence support per point, unsupported-claim rate
   (**not answer length**). QC: rubric reviewed by a subject expert. Coverage: ≥10 questions per
   mark tier.
5. **Scanned / OCR** — capability: layout-aware OCR. Sources: scanned pages (originals or
   permissively licensed scans) with a known ground-truth text. Annotation: page text, reading
   order, table structure. Metrics: CER/WER, table-cell accuracy; then end-to-end QA. QC:
   character-level comparison against the digital source. Coverage: ≥20 pages incl. multicolumn.
6. **Charts / visual** — capability: chart interpretation. Sources: documents with charts and
   a tabular ground truth. Annotation: chart type, axis values, key data points. Metrics:
   data-point accuracy. QC: cross-check against source data. Coverage: ≥15 charts. Licensing:
   only self-authored or permissively licensed charts.

---

## 10. Confirmed findings vs hypotheses

**Confirmed (this closure):** isolated DB provisioned/verified/dropped; full HTTP request path
runs end to end on it; ingestion 12/12 ready; evidence recall 89.7 %; answerable EM 33.3 % /
F1 61.6 % on the corpus; 22/39 failures are answer-stage with evidence present; 4/39 are
retrieval misses; the DB-gated integration validation passes; the previously-skipped test now
runs; frozen benchmark and migration head unchanged.

**Hypotheses (not proven here):** that structure-v2 + ranked elements would improve
table/list/section answers; that a grounded generative route improves completeness; that a
larger/different QA model raises the answer-stage ceiling; that the 4 retrieval misses are
systematic. Each needs its own experiment on its own population.

---

## 11. Proposed minimal fixes (ranked: impact → cost → risk → evidence)

| # | Fix | Impact | Cost | Risk | Evidence | Gate |
|---|---|---|---|---|---|---|
| 1 | Answer **span-boundary/selection** constraint (typed values; strip leading articles/units; reject cross-row spans) | High | Low | Low | strong (F-03) | model/answer review |
| 2 | Make the **full-ingestion runner** accept an isolated DSN + output dir (F-07) so the whole corpus runs chunker-vs-chunker on isolated infrastructure | Medium | Low | Low | strong (F-07) | eval-infra |
| 3 | **Answerability gate** calibration (F-01) with a pre-registered stable threshold | High | Medium | Medium | strong | ADR (Gate 2) |
| 4 | Table/list/section **representation + selection** (F-02, F-06) | High | High | Medium | strong | ADR + schema |
| 5 | **Retrieval recall** work (F-04), starting by labelling chunk-level gold for the corpus | Medium | Medium | Medium | moderate | ADR (Gate 1) |
| 6 | **Structural prior calibration** (F-05) only after independent replication | Medium | Medium | Medium | recorded, not replicated | ADR (weights) |
| 7 | Lecturer datasets + capabilities (F-09) | High | High | High | absent | datasets + ADR |

---

## 12. Required regression tests

- Answer-boundary unit tests (per failure shape in §4.3 sample errors).
- Table row/cell selection seam test (extends the existing `test_table_evidence_*`).
- Full-ingestion runner: an isolated-DSN unit test asserting it never targets the app DB.
- Corpus harness: abstention measured with attached unanswerable questions.
- Retrieval recall test once chunk-level gold exists.
- Gate seam test for any answerability threshold change.

## 13. Decisions requiring ADR / migration-gate approval

Answerability gate (Gate 2); production RRF weight calibration (post-replication);
structure-v2 default + parent/child persistence (schema); table/list/section-aware retrieval
(schema + seams); additive local generative route (§15/§17 waiver); OCR/chart/integrity scope;
entity–relation GraphRAG schema; evaluation runner isolation/output-dir change (small,
INFRA). The architecture gate remains **NOT OPEN**.

## 14. Remaining blockers

- Lecturer-specific datasets do not exist (§9) — **explicitly untested capabilities**.
- The full-ingestion and A–D evaluation runners are not isolation-safe/append-only-safe as
  written (F-07); they need a small eval-infra change before they can be used on the isolated DB.
- No browser/E2E run (needs Vite + live uvicorn + a browser driver).

## 15. Phase 0 exit-criteria assessment

| Criterion | Status |
|---|---|
| Production request path evaluated end to end against a verified isolated database | **MET** (§4.1–§4.3) |
| Evaluation protocol and limitations reproducible | **MET** (§3.4, §7) |
| Failures attributed to earliest demonstrable failing stage | **MET** (§8) |
| Benchmark unchanged | **MET** (§6) |
| Database isolation demonstrated | **MET** (§3.3) |
| Test results recorded accurately | **MET** (§5) |
| Missing datasets / unsupported capabilities documented | **MET** (§9) |
| No unauthorized production changes | **MET** (§17) |

**Phase 0: COMPLETE** — with the standing scope note that the lecturer-specific datasets
(§9) remain **untested capabilities**, and abort/ abstention is measured on the benchmark
(42 unanswerable) but **not** on the corpus harness (§4.3).

## 16. Recommended next task

**Phase 1 — Grounded generative answering** per the roadmap
(`DOCUMIND_PROJECT_CONTEXT.md` Part II §57), preceded by the two small, low-risk
evaluation-infrastructure repairs (§11 items 1 and 2) so the whole corpus and the whole
request path can be measured on isolated infrastructure. Do **not** change production
retrieval weights, topk, chunker, or QA behaviour without an approved ADR.

## 17. Files created / modified

- **Created:** `backend/architecture/PHASE0_CLOSURE_2026-10-09.md` (this file).
- **Modified:** `DOCUMIND_PROJECT_CONTEXT.md` — one pointer line (§64).
- **Temporary (outside the repository):** `/tmp/p0_unit.log`, `/tmp/p0_integration.log`,
  `/tmp/p0_benchmark.log`, `/tmp/p0_corpus.log`, `/tmp/p0_benchmark_predictions.json`.
- No production module, schema, migration, model, benchmark, `.env`, or existing evidence
  file was modified.

## 18. Final Git status and protected-artifact verification

- Branch `main` @ `6baaa2a`; working-tree changed-path count **382 before and after**.
- Benchmark SHA-256 verified, 182 examples.
- QA weights and media weights unchanged (from the previous audit: `cb9f1dde…`, `88ac0939…`).
- Alembic head `007`.
- `documind_integration` verified created-and-dropped; application database `documind`
  untouched.
- The project PostgreSQL cluster was **started for this evaluation and stopped again** to
  restore the pre-existing baseline (it was not running when the task began).
