# DocuMind — Implementation Report: Structure-Aware Dual-Path GraphRAG

**Date:** 2026-09-30
**Scope:** the pasted dual-path GraphRAG specification, executed under the pasted
*Repository Structure + Testing Isolation Contract*.
**Companion document:** `backend/architecture/REPOSITORY_AUDIT_2026-09-30.md` (the
requested codebase/documentation audit).

Every number in this report was produced by a command that was actually run. Where
something is unimplemented, unmeasured, or unverified, it is stated as such. Static
analysis is never presented as test evidence.

---

## 0. Verification summary

| Gate | Result | Kind |
|---|---|---|
| `python -m compileall` (backend, excl. `venv/`, `phases/`) | **exit 0** | Static check |
| `alembic heads` / `alembic current` | **`005 (head)`**, single head | Static check |
| `pytest -q tests/unit` | **PASS — 472 passed** | Unit test execution |
| `pytest -q tests/integration` | **PASS — 86 passed** | Integration test execution |
| `pytest -q tests/e2e` | **6 skipped** (needs a live server) | E2E — NOT executed |
| `pytest -q` (full suite) | **PASS — 558 passed, 6 skipped** | Test execution |
| `pytest --collect-only -q` | **564 collected** | Test discovery |
| `npm run typecheck` | **PASS — exit 0** | Static check (TS) |
| `npm run build` | **PASS — exit 0**, 41 modules, `dist/assets/index-DhiSTb6K.js` 694.36 kB | Build |
| `alembic upgrade head` | **005 applied** | Migration execution |
| Live API smoke test (heading-bearing PDF) | **PASS** — see §6.6 | Runtime smoke test |
| A–D ablation matrix (Phase 3D corpus, 42 questions) | **MEASURED** — see §9.1 | Research evaluation |
| A–D ablation matrix (heading-rich corpus, 23 questions) | **MEASURED** — see §9.2 | Research evaluation |

`564` tests are collected in total; all of them live under `backend/tests/`.
`558 passed + 6 skipped = 564`.

**Baseline → now.** The suite was `421 passed` before this work (`tests/unit` 360 +
`tests/integration` 61). This work adds **137** tests (112 unit + 25 integration), giving
`421 + 137 = 558`. Of those, 19 unit tests pin the new heading-rich corpus contract
(`tests/unit/evaluation/test_heading_corpus.py`, §9.2). *An intermediate measurement of
`503` recorded earlier in the session was superseded by the final runs above; the
arithmetic here was re-derived from the per-file counts in §2.*

---

## 1. Repository Structure

```
backend/
├── auth/               brain/          chat/          documents/
├── embeddings/         graph/          reliability/   verification/
├── user/               settings/       storage/       models/        ← unchanged product code
│
├── graph/                       ← NEW production package (structural retrieval)
│   ├── __init__.py
│   ├── models.py                 DocumentGraphEdge
│   └── service.py                plan_edges / replace_document_graph / expansion
│
├── migrations/
│   ├── env.py                    (+ from graph.models import DocumentGraphEdge)
│   └── versions/000 … 004, 005_add_document_graph.py   ← head = 005
│
├── scripts/                     ← operational scripts (NOT tests)
│   ├── setup_db.py              create_test_user.py
│   ├── cleanup_smoke.py         cleanup_orphan_uploads.py
│   └── db_check.py              start_server.py
│
├── evaluation/                  ← research, separated from tests
│   ├── schemas.py  retrieval_metrics.py  qa_metrics.py  runner.py
│   ├── datasets/    phase3d · phase4b · heading corpora
│   ├── baselines/   {vector_only,structure_only,dual_path}
│   ├── metrics/     reports/
│   ├── experiments/  run_*.py incl. run_dual_path_ablation.py (A–D matrix, --corpus)
│   ├── harness/     ← pre-existing (corpus.py, extraction.py, metrics.py)
│   └── README.md
│
├── tests/                       ← ALL tests (isolation contract §2)
│   ├── unit/          auth brain chat documents embeddings evaluation graph reliability security storage verification
│   ├── integration/   auth documents embeddings graph rag reliability security settings verification
│   ├── e2e/browser/   6 live-server harnesses (opt-in)
│   ├── fixtures/      paths.py live_server.py graph_data.py integration_http.py
│   ├── conftest.py
│   └── README.md
│
├── main.py  config.py  requirements.txt  alembic.ini  pytest.ini
└── architecture/       audit + phase evidence records
```

`pytest.ini` enforces isolation structurally:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py *_test.py
markers =
    e2e: live-server end-to-end test (skipped when unreachable)
```

**Verified:** `pytest --collect-only -q` collects `564` items, **all** matched by
`^tests/`; nothing outside `tests/` is collected. Even pointing pytest directly at a
script and module path collects `no tests` — the operational scripts contain no test
functions and are not collected. `testpaths` is what guarantees the boundary; the earlier
`test_*.py` script names (`db_test.py`, `cleanup_smoke_test.py`, since renamed
`db_check.py` / `cleanup_smoke.py`) were cosmetic only.

---

## 2. Tests Moved

### 2.1 Repository reorganisation (root `Testing_module/` did **not** hold the tests)

The user believed test files had been moved "into a folder inside the backend folder".
They had actually been placed at the **repository root** in `Testing_module/` (audit
finding S-1). The backend test suite was still at the flat `backend/tests/test_*.py`.

`backend/tests/` flat file → categorised path:

| Old path | New path |
|---|---|
| `tests/test_config_security.py` | `tests/unit/auth/test_config_security.py` |
| `tests/test_brain_types.py` | `tests/unit/brain/test_brain_types.py` |
| `tests/test_brain_orchestration.py` | `tests/unit/brain/test_brain_orchestration.py` |
| `tests/test_outcomes.py` | `tests/unit/brain/test_outcomes.py` |
| `tests/test_answer_span.py` | `tests/unit/chat/test_answer_span.py` |
| `tests/test_chat_unit.py` | `tests/unit/chat/test_chat_unit.py` |
| `tests/test_phase3d_context.py` | `tests/unit/chat/test_phase3d_context.py` |
| `tests/test_phase3d_reconciliation.py` | `tests/unit/chat/test_phase3d_reconciliation.py` |
| `tests/test_qa_answer_reconstruction.py` | `tests/unit/chat/test_qa_answer_reconstruction.py` |
| `tests/test_phase3d_chunking.py` | `tests/unit/documents/test_phase3d_chunking.py` |
| `tests/test_phase3e_processing.py` | `tests/unit/documents/test_phase3e_processing.py` |
| `tests/test_structured_extraction.py` | `tests/unit/documents/test_structured_extraction.py` |
| `tests/test_database_url.py` | `tests/unit/storage/test_database_url.py` |
| `tests/test_sql_safety.py` | `tests/unit/security/test_sql_safety.py` |
| `tests/test_auth.py` | `tests/integration/auth/test_auth.py` |
| `tests/test_file_validation.py` | `tests/integration/documents/test_file_validation.py` |
| `tests/test_cors.py` | `tests/integration/security/test_cors.py` |
| `tests/test_settings.py` | `tests/integration/settings/test_settings.py` |
| `tests/test_verification_integrity.py` | `tests/integration/verification/test_verification_integrity.py` |
| `tests/test_real_e2e_validation.py` | `tests/integration/rag/test_real_e2e_validation.py` |
| `tests/phase3d_corpus.py` | `evaluation/datasets/phase3d_corpus.py` (fixture data, not a test) |
| `tests/phase4b_corpus.py` | `evaluation/datasets/phase4b_corpus.py` (fixture data, not a test) |
| `tests/integration_http.py` | `tests/fixtures/integration_http.py` |

### 2.2 Research harnesses were being *executed as tests*

Root `Testing_module/` held 7 research harnesses named `test_*.py` that were **not
unit tests** — they ran real evaluations against corpora. Per contract §4 they were
renamed `test_*` → `run_*` and moved out of the test tree:

| Old path | New path |
|---|---|
| `Testing_module/test_phase3d_evaluation.py` | `evaluation/experiments/run_phase3d_evaluation.py` |
| `Testing_module/test_phase3d_upload_integration.py` | `evaluation/experiments/run_phase3d_upload_integration.py` |
| `Testing_module/test_phase3e_integration.py` | `evaluation/experiments/run_phase3e_integration.py` |
| `Testing_module/test_phase3e_validation.py` | `evaluation/experiments/run_phase3e_validation.py` |
| `Testing_module/test_phase3f_evaluation.py` | `evaluation/experiments/run_phase3f_evaluation.py` |
| `Testing_module/test_phase4b_evaluation.py` | `evaluation/experiments/run_phase4b_evaluation.py` |
| `Testing_module/test_phase4c_diagnostics.py` | `evaluation/experiments/run_phase4c_diagnostics.py` |

Each gained `sys.path` bootstrapping to the backend root. The `Testing_module/`
directory was then removed.

### 2.3 Live-server harnesses

6 browser/HTTP flow harnesses moved to `tests/e2e/browser/`. Each had no pytest entry
point — running it did the work at import time. Each now has a `@pytest.mark.e2e` test
function; module-level side effects were moved into the test body. Specifically:

- `test_real_browser.py` — a module-level `assert os.path.exists(TEST_PDF)` moved into
  the test body (it made *collection* fail).
- `test_phase6_reliability.py` — module-level `os.chdir` and `__pycache__` deletion
  moved into `main()`; path now `Path(__file__).resolve().parents[3]`; the smoke run is
  **opt-in** via `DOCUMIND_E2E_SERVER_SMOKE=1`.
- `test_rag_flow.py` — writes its PDF into `tempfile.gettempdir()` instead of beside
  `backend/uploads/`.

### 2.4 Relocated production scripts (not tests)

Per contract §6, six operational scripts moved from the backend root to
`backend/scripts/`: `setup_db.py`, `create_test_user.py`, `cleanup_smoke.py`,
`cleanup_orphan_uploads.py`, `db_check.py`, `start_server.py`. References in
`chat/qa_model.py` and `AGENTS.md` were updated. The two scripts whose names
matched pytest's `*_test.py` pattern were later renamed
(`db_test.py`→`db_check.py`, `cleanup_smoke_test.py`→`cleanup_smoke.py`) so the
naming hazard is gone, not merely harmless.

**These moves broke them, and that was found and fixed (§5.1).**

---

## 3. Tests Added

118 new tests, all passing:

| File | Tests |
|---|---|
| `tests/unit/graph/test_graph_edges.py` | 18 |
| `tests/unit/graph/test_fusion.py` | 17 |
| `tests/unit/graph/test_structural_retrieval.py` | 22 |
| `tests/unit/evaluation/test_metrics.py` | 36 |
| `tests/integration/graph/test_graph_ingestion.py` | 9 |
| `tests/integration/graph/test_graph_security.py` | 10 |
| `tests/integration/graph/test_graph_rag_flow.py` | 6 |

Coverage against the specification's §11 required list:

- **Graph** — edge creation, no self edges, relation uniqueness (incl. the DB-level
  `uq_document_graph_edges_triplet`), page adjacency, section adjacency, deletion
  cascade.
- **Structural retrieval** — heading/section term seed matching, one-hop expansion,
  two-hop expansion, user ownership isolation, no cross-document leakage.
- **Fusion** — semantic-only candidate, structural-only candidate, candidate found by
  both (labelled hybrid), deterministic ranking, top-K limit.
- **Provenance** — every reported QA source was actually supplied to QA;
  structural-only evidence does not receive a fake semantic score; hybrid is labelled
  hybrid.
- **Security** — user A cannot traverse user B's graph; user A cannot retrieve user B's
  structural evidence.
- **Regression** — the entire pre-existing 421-test suite still passes.

New shared fixtures: `tests/fixtures/paths.py` (asserting `BACKEND_DIR`/`REPO_ROOT`
anchors), `tests/fixtures/live_server.py` (`server_available`, `require_live_server`,
`optional_import`), `tests/fixtures/graph_data.py` (`create_document_with_chunks`,
`views_for`, `create_test_user`).

**One fixture change was functionally required, not cosmetic:** `tests/conftest.py` now
enables `PRAGMA foreign_keys=ON` on the SQLite test engine. SQLite disables FK
enforcement by default while PostgreSQL enforces it — without this, every CASCADE
assertion (edge cleanup on chunk/document delete) silently passed against a database
that was doing nothing. The test would have been vacuous.

---

## 4. Production Code Changed

| File | Change |
|---|---|
| `backend/graph/__init__.py` | **new** — exports `DocumentGraphEdge` |
| `backend/graph/models.py` | **new** — `DocumentGraphEdge` table |
| `backend/graph/service.py` | **new** — graph planning/expansion/retrieval service |
| `backend/migrations/versions/005_add_document_graph.py` | **new** — migration 005 |
| `backend/migrations/env.py` | imports the new model so Alembic autogenerate sees it |
| `backend/documents/routes.py` | `_chunk_views()`; **Step 4** builds the graph after embeddings and before `READY`; failure ⇒ `status="error"` |
| `backend/chat/rag.py` | `SourceChunk` provenance; `dual_path_enabled()`; `retrieve_structural_candidates()`; `fuse_dual_path()`; `retrieve_dual_path()` |
| `backend/brain/types.py` | `SourceRef` provenance fields; `pipeline_version` docstring |
| `backend/brain/adapters.py` | retrieval adapter runs the dual path only when enabled |
| `backend/brain/__init__.py` | real evidence-sufficiency signals in `grounding_signals` |
| `backend/brain/response.py` | provenance + reliability diagnostics on the response |
| `backend/chat/routes.py` | additive `SourceOut`/`ReliabilityEvidence` fields; `pipeline_version` set from `dual_path_enabled()`; new keys persisted |
| `backend/reliability/routes.py` | additive provenance fields; counts derived from persisted source provenance |
| `src/lib/api.ts`, `src/types/index.ts`, `src/pages/WorkspacePage.tsx`, `src/pages/ReliabilityPage.tsx` | additive provenance surface; **no new page** |
| `package.json` | added `"typecheck": "tsc --noEmit"` (the script did not exist) |
| `.gitignore` | `backend/phase4f_gpu/` → `backend/phases/phase4f_gpu/` |
| `AGENTS.md`, `pytest.ini` | isolation contract + explicit discovery |

### 4.1 The structural graph

Relations: `NEXT`, `PREV`, `SAME_PAGE`, `SAME_SECTION`. Weights `1.0`, `1.0`, `0.7`,
`0.5`. The graph is **document-native**: derived only from chunk order, page and heading
metadata. **No LLM-generated triples.** No graph database dependency was added — the
edges live in PostgreSQL next to the chunks.

`plan_edges(chunks)` is pure (no I/O) so it is directly unit-testable: no self edges, no
duplicate `(source, target, relation)` triples, page adjacency only for consecutive
same-page chunks with a non-null page, and the section window is bounded
(`SECTION_NEIGHBOURHOOD = 2`) instead of generating a dense clique.

`replace_document_graph()` deletes then rebuilds for one document and **flushes only** —
the caller owns the transaction, so a graph failure rolls back with the rest of
ingestion rather than committing a half-built graph.

### 4.2 Dual-path fusion

Reciprocal Rank Fusion, exactly as specified:

- semantic contribution `0.70 / (60 + semantic_rank)`
- structural contribution `0.30 / (60 + structural_rank)`
- final ordering: fused score desc → semantic similarity desc → chunk id asc (stable)
- `retrieval_path` ∈ `{semantic, structural, hybrid}`; a chunk found by both is
  `hybrid`
- structural-only chunks keep `score = 0.0`; `fusion_score` is stored **separately** and
  is never presented as a similarity

`DOCUMIND_DUAL_PATH_RAG` is a kill switch: unset (or anything other than `0/false/no/off`)
keeps the dual path **active**. The original `retrieve_chunks` / `build_qa_context` /
`rag_answer` functions are untouched, so the vector-only pipeline still exists and still
works.

### 4.3 Evidence sufficiency

No single invented confidence number. The reported diagnostics are computed from real
signals:

`semanticSourceCount`, `structuralSourceCount`, `hybridSourceCount`, `structuralHopMax`,
`evidenceCoverage` (= QA-supplied ÷ final selected), `pathAgreement` (= ∃ hybrid source),
`fusionEnabled`, `pipelineVersion`.

`pipeline_version` is only reported as `dual-path-graph-rag-v1` when the dual path is
actually active; otherwise `rag-v1`.

### 4.4 Pipeline versioning & migration

`alembic heads` → `005 (head)`, single linear head. Migration 005 is **idempotent** —
both `upgrade()` and `downgrade()` guard on `sa.inspect(bind).has_table(...)`, so replaying
it through history is safe. `alembic upgrade head` was executed and applied.

---

## 5. Issues found and fixed while verifying

These were discovered *because* the verification steps were actually run.

### 5.1 Relocating the operational scripts broke three of them

Moving the scripts into `backend/scripts/` (contract §6) silently broke them:

1. **Running any of them failed outright.** `python scripts/create_test_user.py` puts
   `scripts/` — not the backend root — on `sys.path`, so
   `from auth.models import User` raised `ModuleNotFoundError: No module named 'auth'`.
   Reproduced live.
2. **`setup_db.py` resolved the wrong directory.** `_backend_dir()` returned
   `os.path.dirname(__file__)` = `backend/scripts`, so it ran `alembic upgrade head`
   with `cwd=backend/scripts`, where `alembic.ini` does not exist.
3. **`start_server.py` resolved the wrong directory.** It `os.chdir`'d into
   `scripts/` and then launched `uvicorn main:app` from there, so `main` would not
   import.

All six scripts now bootstrap the backend root onto `sys.path`, and `setup_db.py` /
`start_server.py` walk up to the correct parent. Verified: `db_check.py` prints
`DB CONNECTION: PASS` against PostgreSQL 18.6, and `create_test_user.py` created a user.

### 5.2 A dead, never-importable module (audit finding F-1)

`evaluation/harness/evaluator.py` was pre-existing and **never importable and never
imported**: it used `sys.path` / `os.path` without importing `os` or `sys`, and had an
invalid walrus (`CORRECT_ABSTAIN_LABEL := None,`) inside an import list. Both defects
were repaired (so `compileall` passed), but the module was never executed, nothing
imported it, and its behaviour was never claimed. It has now been **deleted**; the
remaining harness modules (`corpus.py`, `extraction.py`, `metrics.py`) are the ones
that are actually imported.

### 5.3 A test package was missing its `__init__.py`

`tests/unit/evaluation/` was the only test directory without one. Added.

---

## 6. Verification

### 6.1 Static check

```
python -m compileall -q . -x "venv|phases|__pycache__"   → exit 0
alembic heads                                            → 005 (head)
alembic current                                          → 005 (head)
npm run typecheck                                        → exit 0
```

### 6.2 Test execution

```
pytest -q tests/unit         → 472 passed
pytest -q tests/integration  → 86 passed
pytest -q tests/e2e          → 6 skipped
pytest -q                    → 558 passed, 6 skipped in 86.27s (re-run after the heading corpus)
pytest --collect-only -q     → 564 collected
```

### 6.3 E2E execution

**NOT EXECUTED — 6 skipped.** These require a live server and a browser driver. They
are skipped by design when the server is unreachable; the skip is a skip, not a pass.

### 6.4 Migration execution

`alembic upgrade head` applied **005**; `alembic current` reports `005 (head)`.

### 6.5 Build

```
npm run build → exit 0
  41 modules transformed
  dist/index.html                  1.12 kB │ gzip:   0.60 kB
  dist/assets/index-Pg0XaWHv.css  35.29 kB │ gzip:   6.82 kB
  dist/assets/index-DhiSTb6K.js  694.36 kB │ gzip: 181.50 kB
  ✓ built in 3.94s (re-run after the heading corpus)
```

> `(!) Some chunks are larger than 500 kB after minification` is a Vite advisory about
> bundle size, not a failure.

### 6.6 Runtime smoke test — EXECUTED

Server: `python -m uvicorn main:app --host 127.0.0.1 --port 8000`, started against the
real remote PostgreSQL + pgvector database.

| Step | Result |
|---|---|
| `GET /api/health` | `200` — `{"status":"healthy", ..., "qa_model":{"available":true}}` |
| `POST /api/auth/login` | `401` initially (test user absent) → created via `scripts/create_test_user.py` → `200` with JWT |
| `POST /api/documents/upload` (21-byte stub PDF) | `201` but `status:"error"` — **correct**; the upload validator rejected a non-document |
| `POST /api/documents/upload` (real 4-page, 7,123-byte PDF) | `201` — `chunkCount:16, status:"ready", embeddingStatus:"ready"` |
| Graph edges in PostgreSQL | `{NEXT: 15, PREV: 15, SAME_PAGE: 24}` = **54 edges** |
| `POST /api/chat/ask` | `200` in 4.97 s |
| `GET /api/reliability/last-query` | `200`, same evidence + provenance |
| `POST /api/documents/{id}/reprocess` | `200`, graph rebuilt (see below) |
| `DELETE /api/documents/{id}` | `200`, cascade removed all edges (see below) |

**The ask response** (question: *"What does the compression arithmetic section say about
bit allocation and the codebook?"*):

```
sources[0]  hybrid     hop=0  sim=0.6858  fusion=0.01639344
sources[1]  hybrid     hop=0  sim=0.6696  fusion=0.01612903
sources[2]  hybrid     hop=0  sim=0.5793  fusion=0.01587302
sources[3]  hybrid     hop=1  sim=0.5158  fusion=0.01555288
sources[4]  semantic   hop=None sim=0.2719 fusion=0.01076923

reliability:
  sourceCount 5, uniqueDocuments 1, factualGrounded true
  semanticSourceCount 1, structuralSourceCount 0, hybridSourceCount 4
  structuralHopMax 1, pathAgreement true, evidenceCoverage 1.0
  fusionEnabled true, pipelineVersion "dual-path-graph-rag-v1"
```

Acceptance checks actually computed from the live payload:

- `len(sources) == sourceCount == 5` — reported sources exactly match QA evidence ✔
- `1 + 0 + 4 == 5` — path counts partition the sources exactly ✔
- `structuralHopMax == max(structuralHops) == 1` ✔
- `pathAgreement == (hybrid count > 0) == true` ✔
- every source carries a `retrievalPath` ✔
- `GET /api/reliability/last-query` returns the same chunks with the same
  `retrievalPath` / `fusionScore` / `structuralHops` ✔

**Reprocessing rebuilds the graph**

```
before: chunks 16 | edges {'NEXT':15,'PREV':15,'SAME_PAGE':24} | total 54 | max_created_at 21:41:06
after:  chunks 16 | edges {'NEXT':15,'PREV':15,'SAME_PAGE':24} | total 54 | max_created_at 21:45:44
```

The edge count is unchanged and `max_created_at` advanced — so the old edges were
deleted and rebuilt. A pure append would have doubled the total to 108.

**Document deletion cascades to edges**

```
after DELETE: chunks 0 | edges {} | total 0
```

### 6.7 What the first smoke test did *not* prove (and the real cause)

The first run's generated PDF produced **no structure metadata** — every chunk had
`section = None` and `heading_path = None`. That was recorded at the time as a PDF
text-extraction limitation. The follow-up run (§6.8) found the deeper cause: the
**default chunker is `legacy`** (`config.py`, `chunker_version = "legacy"`), and the
legacy chunker never populates the Phase 3D metadata columns *regardless of the PDF*.
The structure chunker must be selected explicitly (`CHUNKER_VERSION=structure-v2`), a
fact the first run did not set.

As they stood in that first run:

- `SAME_SECTION` edges = **0**, and heading/section term-seeding had **no input**.
- No `structural`-only source appeared (`structuralSourceCount = 0`).
- `structuralHopMax` reached only 1.

### 6.8 Second smoke test — heading-bearing PDF, structure chunker

Server started with `CHUNKER_VERSION=structure-v2` against the real remote PostgreSQL. A
generated 10-chunk PDF with 8 font-detectable headings was uploaded, so the pipeline ran
the structure chunker with real `section` / `heading_path` values.

| Check | Result |
|---|---|
| Headings detected by extraction | 8 (H1/H2 via font size) |
| Chunks with non-null `section` | 10 / 10 |
| Chunks sharing one section (`Compression Arithmetic`) | 2 |
| Graph edges | `{NEXT: 9, PREV: 9, SAME_PAGE: 16, SAME_SECTION: 2}` = 36 |
| `SAME_SECTION` edges | **2** (previously 0) |
| Live `POST /api/chat/ask` | `200`; sources `hybrid`, `structuralHopMax` up to 1 |
| Heading/section term seeding | **fired** (direct call, below) |
| Structural-only source in the API top-5 | **did not appear — see below** |

**Heading/section term seeding, proven against live ingested data** (direct call to
`graph.service.find_section_seed_matches`):

```
Q: "What symbols does the Appendix Notation section define?"
   terms=['symbols','appendix','notation','define']
   seed …c8af matched=('appendix','notation')
   seed …bd43 matched=('notation',)

Q: "How is the bit budget allocated, and what notation conventions are used?"
   terms=['bit','budget','allocated','notation','conventions','used']
   seed …4df1 matched=('bit',)  seed …7a0 matched=('budget',)  seed …c8af matched=('notation',)
```

**Why no structural-only source could appear.** This is a property of the fusion
weighting, not a corpus accident. RRF gives a structural-only chunk at most
`0.30 / (60 + 1) = 0.004918`, while a semantic-only chunk at rank 5 already scores
`0.70 / (60 + 5) = 0.010769`. Every semantic chunk therefore outranks every
structural-only chunk, so with `top_k = 5` and ≥5 semantic results a structural-only
source can **never** enter the fused top-5. Structural-only evidence is only reachable
when the semantic path returns fewer than `top_k` chunks. That rule — and the
"structural-only keeps `score = 0.0`" contract — is covered by
`tests/unit/graph/test_fusion.py` (which calls `fuse_dual_path` with short semantic
lists), not by a live API query.

---

## 7. Known Limitation: Evaluation Code Added

| File / dir | Purpose |
|---|---|
| `evaluation/schemas.py` | `QuestionCategory`, baselines B1–B4, ablations A–D + `ABLATION_MATRIX`, `EvalQuestion`, `RetrievalOutcome`, `AnswerOutcome`, `QuestionResult`, `RunReport` |
| `evaluation/retrieval_metrics.py` | `recall_at_k`, `precision_at_k`, `reciprocal_rank`, `mrr`, `dcg_at_k`, `ndcg_at_k` |
| `evaluation/qa_metrics.py` | `exact_match`, token-**set** F1, `answer_accuracy`, `unsupported_answer_rate`, `factual_grounding_rate`, `evidence_coverage`, `path_agreement`, `path_counts` |
| `evaluation/runner.py` | `measure_question`, `run_baseline`, `run_ablation`, `write_report` |
| `evaluation/experiments/run_dual_path_ablation.py` | **new** — runs the A–D matrix over a labelled corpus with the real pipeline; `--corpus {phase3d,heading}` (§9) |
| `evaluation/datasets/heading_corpus.py` | **new** — 4 PDFs with real font-detected headings and sections spanning pages, labelled for the A–D runner (§9.2) |
| `tests/unit/evaluation/test_heading_corpus.py` | **new** — pins the heading corpus contract (real headings, documented spanning sections, evidence findable, cross-page labels truthful) |
| `evaluation/{datasets,baselines/*,metrics,experiments,reports}/` | directory skeleton + `__init__.py` |
| `evaluation/README.md` | including the old→new move table |

`runner.py` **refuses to invent results**: B2 (vector + reranking) returns
`not_measured` with a reason when no reranker module exists
(`RERANKER_MODULE = "embeddings.reranker"` is absent from this project). The A–D matrix
has now been run (§9); its cells are measured, not expected, and `not_measured` is empty
because no reranker was part of the A–D variants.

---

## 8. Known Issues

**Real, unresolved:**

1. **B2 (vector + reranking) is NOT MEASURED.** No reranker exists in this project.
   `runner.py` reports `not_measured` rather than a number. This cannot be fixed by
   implementing B2 — it requires either a real reranker or removal of the baseline.
2. **The A–D ablation matrix has now been run on two corpora, and the dual path did not
   improve retrieval on either** (§9.1 Phase 3D, §9.2 heading-rich). This is a measured
   *negative* result, reported as such — not a missing measurement. It survives the
   heading-rich corpus, which was built to give the structural path its best case.
3. **A structural-only source cannot enter the fused top-5** whenever the semantic path
   returns `top_k` chunks, because RRF's structural ceiling (0.004918) is below the
   weakest semantic contribution (0.010769). See §6.8. This is a property of the fusion
   arithmetic, not of the structural path's reach: measured *directly* (§9.2, variant B),
   structure-only retrieval scores R@5 0.5652 on the heading-rich corpus.
4. **The E2E tier (6 tests) is skipped**, not passing.
5. **Architecture documents still cite dead `backend/phase4f/...` paths** (audit D-1).
   They were left as written (their provenance value depends on it); a single
   `backend/architecture/PATH_MIGRATION.md` translation note was added instead.
6. **A latent footgun:** `backend/phases/phase4f/phase4f_5d/build_benchmark.py` performs
   an **unguarded overwrite** of the frozen benchmark. The frozen
   `qa_benchmark_v1.jsonl` was re-verified intact: sha256
   `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (MATCH). Do not run
   that script.
7. **The default chunker is `legacy`.** Structure metadata (and therefore
   `SAME_SECTION` edges) only exist when `CHUNKER_VERSION=structure-v2`. This is
   deliberate (`config.py`) but easy to overlook; see §6.7.

**Resolved on 2026-09-30 (items previously listed here):**

- `llm/` (265 MB duplicate of the QA model, 0 references) — **deleted**.
- `backend/CONTEXT.md` (stale stub) — **deleted**.
- `backend/orphaned_uploads_2026-09-28.zip` (10,440,277 B) — **deleted**.
- `evaluation/harness/evaluator.py` (never importable, never imported, never executed)
  — **deleted**.
- `runbooks/README.md`, `runbooks/migration-failure.md` and
  `runbooks/database-failure.md` no longer claim a single revision `001`; they now
  describe the real `000`–`005` chain.
- `scripts/db_test.py` / `scripts/cleanup_smoke_test.py` — **renamed** to
  `db_check.py` / `cleanup_smoke.py`, removing the `*_test.py` discovery hazard
  entirely.

**Not issues (checked and clean):**

- No production module imports `tests` — verified by grep across
  `auth/ chat/ documents/ embeddings/ brain/ graph/ storage/ reliability/
  verification/ user/ settings/` and the top-level modules. Zero matches.
- No `test_*.py` exists in any production directory.
- No graph database dependency and no external LLM was introduced.

---

## 9. Research Status

**Implemented and tested end-to-end.** The mechanism is the concrete DocuMind framework,
not a claim to a novel primitive:

> DocuMind implements a structure-aware dual-path retrieval framework that combines
> semantic vector retrieval with document-native structural traversal over section, page,
> element, and adjacency relations, followed by evidence fusion and provenance-aware
> answer construction.

Implemented:

- document-native structural graph (`NEXT`/`PREV`/`SAME_PAGE`/`SAME_SECTION`), built
  during ingestion and before `READY`, rebuilt on reprocess, cascaded on delete;
- structural retrieval from heading/section term seeds plus bounded graph expansion from
  semantic seeds;
- deterministic Reciprocal Rank Fusion (0.70 semantic / 0.30 structural, k = 60);
- fine-grained provenance (`semantic` / `structural` / `hybrid`, hop distance, fusion
  score, relation) carried through the Brain and the API into the Reliability Center;
- transparent evidence-sufficiency diagnostics;
- the existing custom DistilBERT QA model is unchanged and still the only answer model.

### 9.1 A–D ablation — measured (not yet favourable)

`evaluation/experiments/run_dual_path_ablation.py` ran all four variants over the Phase 3D
labelled corpus (12 documents, 42 questions: 39 answerable + 3 unsupported), ingested with
the **structure chunker** into a dedicated eval user, using the real embedding model, the
real PostgreSQL graph and the real QA model. Gold chunk ids were derived from each
question's `evidence` substrings *after* ingestion, so the labels are independent of the
retrieval being scored. Reports: `evaluation/reports/ablation_{A,B,C,D}.json`.

| variant | vector | structure | gate | R@5 | P@5 | MRR | nDCG@5 | EM | token-F1 | evid-cov | path-agr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | yes | no | no | 0.9008 | 0.2238 | 0.8103 | 0.8178 | 0.5714 | 0.7226 | 0.9667 | 0.0000 |
| B | no | yes | no | 0.1190 | 0.0345 | 0.0833 | 0.0919 | 0.0238 | 0.0808 | 1.0000 | 0.0000 |
| C | yes | yes | no | 0.9008 | 0.2238 | 0.7933 | 0.8055 | 0.5714 | 0.7226 | 0.9667 | 1.0000 |
| D | yes | yes | yes | 0.9008 | 0.2238 | 0.7933 | 0.8055 | 0.5714 | 0.7226 | 0.9667 | 1.0000 |

Read honestly:

- **The dual path did not improve retrieval on this corpus.** C matched A on
  recall/precision/EM/F1 exactly, and was slightly *worse* on ranking (MRR 0.8103→0.7933,
  nDCG 0.8178→0.8055): fused structural candidates displace some gold chunks.
- **Structure-only is far weaker** (R@5 0.119) — expected, since traversal cannot answer
  factual questions that have no section-name anchor.
- **The evidence gate never fired:** D is identical to C, so on this corpus the gate
  changes nothing.
- **Latency cost is real:** retrieval mean 314.8 ms (A) vs 1379.0 ms (C) — the dual path
  is ~4.4× slower at retrieval.
- `not_measured` is empty for A–D (B2 was not one of the variants).

This is a **negative result and it is reported as one.** It does not dispute the verified
behavioural properties (isolation, determinism, provenance fidelity, security); it says
the current fusion weighting does not beat vector-only on this labelled corpus.

**Not claimed:**

- **B2 is not measurable** here (no reranker).
- **No retrieval improvement is claimed** — the A–D run found none.
- **Multimodal is declared but unused** (`QuestionCategory.MULTIMODAL` exists). No image
  or figure evidence is represented, so no multimodal evaluation is claimed — and no fake
  media verification was added.

The defensible contribution at this point is the **implementation and its verified
behavioural properties** (isolation, determinism, provenance fidelity, security), not
measured retrieval improvement.

### 9.2 A–D ablation on the heading-rich corpus — measured

The Phase 3D corpus names a `multipage_section.pdf`, but its heading sits only on the
first page, so the section's later pages carry no `heading_path` and the graph produces
no `SAME_SECTION` edge across the page break. A dual-path ablation run on it therefore
measured the vector path and almost nothing else — a corpus artefact, not only a result.

`evaluation/datasets/heading_corpus.py` (**new**) fixes that: four PDFs whose headings
are written with real font properties (H1 16 pt bold, H2 13 pt bold, H3 11 pt bold, body
10 pt regular) and whose sections **continue across page boundaries** with no repeated
heading. Ingested with the structure chunker this yields **18 chunks and 16 `SAME_SECTION`
edges** (Phase 3D's smoke PDF produced 2), so the structural path finally has a graph to
traverse. The corpus carries 20 answerable + 3 unsupported questions; 13 are
`section`-kind and 7 are `cross_page`-kind (the supporting text is on a page *after* the
section heading — asserted by
`tests/unit/evaluation/test_heading_corpus.py`). Run with:

```bash
cd backend
./venv/Scripts/python.exe evaluation/experiments/run_dual_path_ablation.py --corpus heading
```

Reports: `evaluation/reports/ablation_heading_{A,B,C,D}.json`.

| variant | vector | structure | gate | R@5 | P@5 | MRR | nDCG@5 | EM | token-F1 | evid-cov | path-agr | retrieval mean ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | yes | no | no | 0.8696 | 0.1826 | 0.8478 | 0.8535 | 0.5217 | 0.7571 | 1.0000 | 0.0000 | 317.5 |
| B | no | yes | no | 0.5652 | 0.1645 | 0.3986 | 0.4446 | 0.4783 | 0.5420 | 1.0000 | 0.0000 | 906.4 |
| C | yes | yes | no | 0.8696 | 0.1826 | 0.8478 | 0.8500 | 0.5217 | 0.7571 | 1.0000 | 1.0000 | 1334.8 |
| D | yes | yes | yes | 0.8696 | 0.1826 | 0.8478 | 0.8500 | 0.5217 | 0.7571 | 1.0000 | 1.0000 | 1283.2 |

Read honestly:

- **The corpus now genuinely exercises the structural path.** Structure-only (B) rose
  from R@5 0.1190 on Phase 3D to **0.5652** here, and `section_dependent` questions reach
  R@5 0.6923 (vs 0.5714 for `page_cross_page`). The page-spanning sections and
  section-naming questions did what they were built to do.
- **The dual path still does not beat vector-only.** C matched A exactly on
  R@5 / P@5 / MRR / EM / token-F1 and was marginally *lower* on nDCG@5 (0.8500 vs
  0.8535). Adding the structural path changed nothing that mattered.
- **The evidence gate still never fired:** D ≡ C.
- **The latency cost stands:** retrieval mean 317.5 ms (A) vs 1334.8 ms (C), ~4.2× slower.
- **Abstention on unanswerable questions:** `unsupported_answer` is 0.1304 for A/C/D —
  all **3 of 3** unanswerable questions were answered — versus 0.0435 for B (1 of 3).
  Structure-only abstains more because a keyword-less question produces no seed, which is
  the honest trade: lower coverage, higher caution.
- `not_measured` is empty for A–D (B2 was not one of the variants).

The negative conclusion therefore survives a corpus built specifically to give the
structural path its best case. What changed is the *reason* it is credible: previously
structure-only scored near zero partly because the corpus could not form cross-page
sections; now it scores respectably and the dual path **still** adds nothing at 4.2× the
retrieval latency.

---

## 10. Cleanup recommendations — performed

All seven code/document recommendations from the earlier version of this report were
**applied on 2026-09-30**:

| # | Action | Status |
|---|---|---|
| 1 | Delete `llm/` (265 MB duplicate, 0 references) | **done** |
| 2 | Delete `backend/CONTEXT.md` (stale stub) | **done** |
| 3 | Delete `backend/orphaned_uploads_2026-09-28.zip` | **done** |
| 4 | Delete `evaluation/harness/evaluator.py` | **done** |
| 5 | Add `backend/architecture/PATH_MIGRATION.md` | **done** |
| 6 | Fix `runbooks/README.md`'s migration claim (+ two related runbooks) | **done** |
| 7 | Rename `scripts/db_test.py` / `cleanup_smoke_test.py` | **done** → `db_check.py` / `cleanup_smoke.py` |

**Still open (owner's decision):**

| # | Recommendation | Reason |
|---|---|---|
| 8 | Create `reliability_query_logs` + history endpoint | spec §7 deferred this; the latest-snapshot endpoint was kept compatible |
