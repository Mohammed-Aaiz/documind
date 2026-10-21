# DocuMind — Repository & Document Audit

**Date:** 2026-09-30
**Scope:** whole repository (frontend `src/`, backend `backend/`, root-level docs/artifacts).
**Nature:** inspection + reporting only. No production file was deleted or renamed by this audit.
Every statement below was verified against the working tree at the stated date; nothing is
restated from memory.

Evidence commands used (all read-only): `find`, `grep -rn`, `diff -q`, `sha256sum`, `ls -la`,
`git status --short`, `venv/Scripts/python.exe -m pytest tests -q`.

---

## 1. What the system actually is (verified architecture)

```
React 18 + TS + Vite (src/, port 3000, proxy /api -> 8000)
            |
            v  HTTP
FastAPI app  backend/main.py
  lifespan: alembic upgrade head  ->  require_production_jwt_secret()  ->  upload dir mkdir
  routers : auth, documents, chat, embeddings, verification, reliability, user, settings
            |
            v
Brain (backend/brain/) — deterministic orchestrator
  classify -> plan -> execute (CapabilityRegistry) -> evidence gate -> response assemble
  adapters: chat.rag.retrieve_chunks / build_qa_context / chat.qa_model.answer_question
            |
            v
chat/rag.py  : pgvector cosine retrieval over document_chunks (Vector(384))
chat/qa_model.py : custom DistilBERT extractive QA (models/documind-qa), torch+transformers
            |
            v
PostgreSQL + pgvector (I/O via storage/database.py, asyncpg, pool_pre_ping)
Alembic: 000 -> 001 -> 002 -> 003 -> 004 (head on disk)
```

Key production facts confirmed:

- `backend/tests` currently holds 20 test modules + `conftest.py` + 2 corpus/helper modules.
- `backend/evaluation/harness/` already exists (5 modules) — a *pre-existing evaluation harness*,
  separate from the pytest suite.
- `runbooks/README.md` claims a "single revision `001_add_reliability_logs.py`". **Stale** — five
  revisions exist (`000`…`004`).

---

## 2. Structural problems found (not documents)

| # | Problem | Evidence | Impact |
|---|---|---|---|
| S-1 | Test files were moved to repo-root `Testing_module/`, not into `backend/tests/` and not into a folder *inside* `backend/`. | `ls` root shows `Testing_module/`; `backend/` has no `Testing_module`. | Violates the isolation contract §2 (all tests under `backend/tests/`). Discoverable by neither `pytest tests` nor the app. Also outside git's tracked root paths for pytest. |
| S-2 | A **complete GPU virtualenv** now lives inside the repo at `backend/phases/phase4f_gpu/` (`Lib/site-packages/{torch,sympy,networkx,…}`, `Scripts/*.exe`, `pyvenv.cfg`). | `ls phases/phase4f_gpu`; `pyvenv.cfg` present. | Thousands of files. `.gitignore` still only ignores `backend/phase4f_gpu/` (old path) — the **new path is not ignored**, so `git add` would sweep the entire venv into history. |
| S-3 | Research/phase code was relocated `backend/phase4f|phase4d|phase4e` → `backend/phases/*`, and root phase reports → `backend/phases/`. Untracked whole tree. | `git status --short` shows `?? backend/phases/` plus ~289 modified/deleted paths. | Every path recorded in the research documents is now wrong (see §4, D-1). |
| S-4 | `llm/` at repo root is a **byte-identical duplicate** of the QA model. | `llm/model.safetensors` = 265,470,032 B == `backend/models/documind-qa/model.safetensors`; `diff -q` on `config.json`, `inference_config.json`, `tokenizer_config.json` produced no differences. No backend module references `llm/` (grep: 0 hits). | ~265 MB dead disk copy; risk of the two copies diverging silently. |
| S-5 | Operational scripts sit in the backend root, not `backend/scripts/`. | `cleanup_orphan_uploads.py`, `cleanup_smoke_test.py`, `create_test_user.py`, `setup_db.py`, `db_test.py`, `start_server.py`. | Contract §6 requires operational scripts in `backend/scripts/`. (`db_test.py` is a bare `asyncio.run()` connectivity probe, not a test.) |
| S-6 | `backend/pytest.ini` only sets `asyncio_mode = auto`; it does not set `testpaths`/`python_files`. | `cat backend/pytest.ini`. | A bare `pytest` from `backend/` currently discovers tests across the tree, which the contract forbids. |
| S-7 | `backend/orphaned_uploads_2026-09-28.zip` (10,440,277 B) is untracked and **not** gitignored. | `ls -la backend/`. | Stale runtime data one `git add -A` away from being committed. |

---

## 3. Documents — complete inventory and verdict

Legend — **KEEP**: current and correct. **KEEP-HISTORICAL**: accurate research record of a past
decision; keep as evidence, do not treat as current guidance. **STALE**: factually wrong or
contradicted by the working tree. **DUPLICATE**: redundant copy. **GENERATED**: machine output,
safe to delete. **REFERENCE**: design input, not project documentation.

### 3.1 Root-level documentation

| Document | Verdict | Reason |
|---|---|---|
| `DOCUMIND_PROJECT_CONTEXT.md` (1 442 lines) | **KEEP** | Declared authoritative source of truth; no contradiction found against the tree. |
| `CONTEXT.md` (152 lines) | **KEEP** | Explicitly subordinate index to the file above; it says so itself and defers on conflict. |
| `AGENTS.md` (185 lines) | **KEEP** | Agent ownership boundaries; still accurate and actively referenced by `prompts/`. |
| `prompts/00_coordinator.md` … `05_test_agent.md` (6 files, untracked) | **KEEP** | Per-agent prompts consistent with `AGENTS.md`; they read the same authoritative docs. Untracked — a decision is needed on whether to commit or move to `runbooks/`. |
| `runbooks/*.md` (8 files) | **KEEP, one correction needed** | Failure-mode recovery guides are written from the real implementation. **`runbooks/README.md` is STALE**: it states the migration chain is a "single revision `001_add_reliability_logs.py`" — the chain is now `000`…`004`. |
| `backend/CONTEXT.md` (24 lines) | **STALE — recommend delete** | An **unfilled template stub** whose filled-in facts are *all wrong*: it claims "Database: SQLite at backend/documind.db" (actual: remote PostgreSQL + pgvector), "Frontend: http://localhost:5173" (actual: 3000), "Model Location: models/llm/final_model/" (does not exist), and every section still reads `- (list … here)`. It duplicates the root `CONTEXT.md` name while contradicting the truth — the single most misleading file in the repo. |
| `backend/models/README.md` (47 lines) | **KEEP** | Correct description of the QA-model artifact directory; matches what is on disk. |
| `cinematic_intelligence/DESIGN.md` | **REFERENCE** | Design/visual source material. Not part of the 5-page product's runtime and not referenced by any code. |
| `*/code.html` + `*/screen.png` in `documind_ai_workspace_desktop/`, `documind_login_desktop/`, `documind_settings_desktop/`, `media_verification_desktop/`, `reliability_center_desktop/` | **REFERENCE** | Original generated mockups. Superseded by the live `src/pages/*.tsx` implementations; kept only as design provenance. |
| `.pytest_cache/README.md` | **GENERATED** | Written by pytest. Delete with the surrounding cache dir. |

### 3.2 Research architecture corpus — `backend/architecture/phase4f_6/`

35 `.md` files + 40+ `.json` artifacts + `e0_diagnostics/` (corpora, tools, results).

| Document | Verdict | Reason |
|---|---|---|
| `CURRENT_ARCHITECTURE.md` | **KEEP** | Describes the *current production* architecture; still a valid description of the code. |
| `TARGET_ARCHITECTURE.md` | **KEEP-HISTORICAL** | Forward-looking design. Marked target, not built; do not read as implemented. |
| `ARCHITECTURE_DECISION_RECORD.md` | **KEEP** | Live decision register (DECIDED / DEFERRED / BLOCKED / HYPOTHESIS states). Not superseded. |
| `DOMAIN_MODEL.md` | **KEEP-HISTORICAL** | Domain design; §3.2 provenance is design-only (so stated). |
| `MODULE_SEAMS.md` | **KEEP-HISTORICAL** | Seam design; no code exists yet (so stated in the migration gate). |
| `PHASE4F6_ARCHITECTURE_AUDIT.md`, `QUESTION_WORKFLOW_MATRIX.md` | **KEEP** | Measured audit + workflow matrix; both carry 4F.6-C-R update banners. |
| `decision/ARCHITECTURE_MIGRATION_GATE.md` | **KEEP** | The 10 gate criteria are still mostly **NOT MET** as written; current and useful. |
| `decision/EXPERIMENT_CONTROL_MATRIX.md` | **KEEP (self-corrected)** | Carries an explicit 4F.6-C-R banner superseding its early C0·P3 absence statement. |
| `decision/QA_HYPOTHESIS_MATRIX.md`, `PHASE4F6B_RECONCILIATION.md` | **KEEP-HISTORICAL** | Both carry the 4F.6-C-R supersession banner and point at the authoritative successor. |
| `decision/PHASE4F6C_RECONCILIATION.md` | **KEEP (current reconciliation)** | Latest reconciliation of the decision corpus; the reference point for the three above. |
| `decision/NEXT_EXPERIMENT_DECISION.md` | **KEEP-HISTORICAL** | Chose E0 as the next experiment. E0 has since produced artifacts, so this is now the *pre-E0* decision record. |
| `decision/E0_READINESS_CHECK.md` | **SUPERSEDED** (keep as record) | Explicitly superseded by `E0_PREREQUISITE_STATUS.md` (blockers B-2/B-3 resolved). |
| `decision/E0_PREREQUISITE_STATUS.md` | **KEEP-HISTORICAL** | Supersedes the readiness-check §A/§B sections; B-1 persists. |
| `decision/E0_ERRATUM_2026-09-27.md` | **KEEP** | An erratum is an active correction by definition; must not be deleted. |
| `decision/E0_OFFLINE_RUNTIME_PROVISIONING.md`, `E0_RETRIEVAL_RUNTIME_READINESS.md`, `E0_RETRIEVAL_RUNTIME_RESUME.md`, `E0_SOURCE_PROVENANCE.md` | **KEEP-HISTORICAL** | Chronological readiness chain (2026-09-23). Each states it is readiness-only and that E0 was not executed. Superseded in part by the resume note and the 09-27/09-28 records, but they are the honest audit trail. |
| `decision/E0_PREDICTION_PROVENANCE_2026-09-28.md` | **KEEP** | Latest E0 provenance position; it explicitly declares earlier provenance numbers **superseded, not corrected**. |
| `decision/{ABSTENTION_GATE_RESCORING, ANSWERABILITY_SIGNAL_FORENSICS, AUC_INFLUENCE_JACKKNIFE_FORENSICS, CLS_DIRECTION_REVERSAL_FORENSICS, ISO_COVERAGE_RESCORING, RECONSTRUCTION_BOUND, SCORE_STATISTIC_ISO_K47, SCORE_STATISTIC_ISO_K95, SPAN_BOUNDARY_FORENSICS, SPAN_SELECTION_PROTOCOL_EXPERIMENT, MODEL_40MIN_EVALUATION}.md` (+ matching `.json`) | **KEEP** | Each is a distinct, measured forensics/experiment record; no later document invalidates them as a group. |
| `decision/{DECISION_SAFETY_CHECK, E0_SCHEMA, E0_CORPUS_MANIFEST, E0_CHUNK_MANIFEST, E0_MEDIA_DETECTION_RECORD, E0_RETRIEVAL_RUN_MANIFEST, E0_RUNTIME_HANDOFF_MANIFEST, EXPERIMENT_CANDIDATE_MATRIX, EXPERIMENT_CONTROL_MATRIX}.json` | **KEEP** | Machine-readable decision data the `.md` files cite. |
| `e0_diagnostics/**` (corpora, tools, results) | **KEEP** | Reproducibility input for the E0 record. |

### 3.3 Moved phase documentation (now under `backend/phases/`)

| Document | Verdict | Reason |
|---|---|---|
| `phases/phase4f/phase4f_5f/h1_reconciliation/H1_RECONCILIATION_REPORT.md`, `README.md` | **KEEP-HISTORICAL** | H1 arm result (collapsed, 0 % EM) — the matrix cites it. |
| `phases/phase4f/phase4f_5f/research_ledger/RESEARCH_LEDGER.md` | **KEEP** | Claim-audit ledger; the 4F.6-B decision leans on it explicitly. |
| `phases/phase4f/experiments/final_gpu_package/README_GPU_EXECUTION.md` | **KEEP-HISTORICAL** | Instructions for the GPU handoff package; package itself is present. |
| ~30 root-level `phase3*`/`phase4*` `.json`/`.txt` reports now in `backend/phases/` (e.g. `phase3d_evaluation_report.json`, `phase4c_failure_matrix.json`, `phase4d_qa_model_improvement_report.txt`, `phase4f_qa_architecture_experiment_report.txt`) | **KEEP-HISTORICAL** | Superseded as *current status* by the `architecture/phase4f_6/decision/` corpus, but they are the primary evidence for the phases they name. Do not delete; do not cite as current. |
| `backend/p3d_uvicorn.log` | **GENERATED** | Runtime log. Also matched by the root `.gitignore` `*.log` rule. |
| root `uvicorn.log`, `vite.log`, `p3d_vite.log` | **GENERATED** | Same; produced by development runs. |

### 3.4 Duplicates

| Item | Verdict | Reason |
|---|---|---|
| `llm/` (whole directory, incl. 265 MB `model.safetensors`) | **DUPLICATE — recommend delete** | Byte-identical to `backend/models/documind-qa/`; zero code references. The runtime loads `./models/documind-qa` by default (`chat/qa_model.py` + `config.py`). |
| `backend/CONTEXT.md` vs root `CONTEXT.md` | **STALE duplicate** | Same name, contradictory content; the root one is authoritative and correct. |
| `.gitignore` repeats `backend/models/documind-qa/model.safetensors` twice (lines 48 and 53) | **DUPLICATE** | Harmless but redundant; same for `llm/model.safetensors` and `backend/phase4f_gpu/`. |

---

## 4. Stale references introduced by the relocation

| # | Finding | Evidence |
|---|---|---|
| D-1 | **44 files** under `backend/architecture/phase4f_6/` still cite `backend/phase4f/...` paths that no longer exist. **0 files** cite the new `backend/phases/phase4f/...` location. | `grep -rl "backend/phase4f/" . \| wc -l` → 44; `grep -rl "backend/phases/phase4f" . \| wc -l` → 0. |
| D-2 | The frozen benchmark is intact at its new path. | `sha256sum phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` → `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` (matches the recorded hash). |
| D-3 | `phases/phase4f/phase4f_5d/` also carries `analysis.pre_joint_selection_v1/` — the preserved protocol-v1 snapshot. | `ls phase4f_5d/`. |

**Consequence:** the architecture corpus is currently *internally coherent but externally unlocatable*
— a reader cannot follow a cited path. Recommended remedy (not performed here, to avoid a 44-file
mechanical edit): either move `architecture/` under `backend/phases/` and re-point paths, or add a
single `PATH_MIGRATION.md` note in `architecture/phase4f_6/` recording the `backend/phase4f/` →
`backend/phases/phase4f/` move once, and treat every path in the corpus as relative to that note.

---

## 5. Summary of recommended actions

| Priority | Action | Risk |
|---|---|---|
| 1 | Move `Testing_module/*.py` into the correct `backend/tests/{unit,integration,e2e}` categories (or `backend/evaluation/experiments/` for research harnesses). | Low — done in this session, verified by pytest. |
| 2 | Fix `.gitignore`: replace `backend/phase4f_gpu/` with `backend/phases/phase4f_gpu/` **before** any `git add`. | **High if skipped** — a full venv enters git history. |
| 3 | Delete `backend/CONTEXT.md` (misleading stub) and refresh `runbooks/README.md` migration facts. | Low. |
| 4 | Delete `llm/` after confirming no external consumer (265 MB). | Low — verified unreferenced. |
| 5 | Move operational scripts to `backend/scripts/`. | Low. |
| 6 | Add `PATH_MIGRATION.md` for the 44 stale phase paths. | Low. |
| 7 | Decide on `backend/orphaned_uploads_2026-09-28.zip` (delete or gitignore). | Low. |
| 8 | Commit or relocate `AGENTS.md`, `CONTEXT.md`, `prompts/`, `backend/architecture/`. | Low. |

---

## 6. Dead / broken code found

| # | Finding | Evidence | Disposition |
|---|---|---|---|
| F-1 | `backend/evaluation/harness/evaluator.py` (712 lines) was **never importable and never imported**. | It called `sys.path.insert`/`os.path.join` without importing `os`/`sys`, and contained an invalid walrus expression inside an import list (`CORRECT_ABSTAIN_LABEL := None,`). `python -m compileall` reported `SyntaxError: invalid syntax` at line 37. `grep` for importers: only `metrics.py`, `corpus.py` and `extraction.py` are imported by any runner — `evaluator.py` by nothing. | The two defects were repaired (imports added, invalid line removed) so the tree compiles and the module imports; it remains **UNEXECUTED and is not claimed to work**. It is superseded by the new `evaluation/runner.py`. Recommend deletion unless a measured Phase-3F run is reproduced with it. |

---

## 7. Actions taken while auditing (2026-09-30)

These were executed as part of the accompanying test-isolation contract work, and are
recorded here so this document stays an accurate description of the tree:

| Action | Detail |
|---|---|
| Tests relocated | `Testing_module/*.py` (repo root) and `backend/tests/*.py` were reorganised into `backend/tests/{unit,integration,e2e,fixtures}/`. See `backend/tests/README.md` for the full old→new mapping. |
| Research relocated | 7 measurement harnesses moved to `backend/evaluation/experiments/` and renamed `test_*.py` → `run_*.py`; the shared corpora moved to `backend/evaluation/datasets/`. See `backend/evaluation/README.md`. |
| Operational scripts relocated | `backend/{setup_db,create_test_user,cleanup_smoke_test,cleanup_orphan_uploads,db_test,start_server}.py` → `backend/scripts/`. `chat/qa_model.py` and `AGENTS.md` references updated. |
| `.gitignore` fixed | `backend/phase4f_gpu/` → `backend/phases/phase4f_gpu/` (see S-2) and `backend/phases/phase4f/models/` added. |
| `pytest.ini` hardened | `testpaths = tests`, `python_files = test_*.py *_test.py`, `e2e` marker. |
| Dead code repaired | F-1 (later superseded — see §8). |
| Scripts renamed | `backend/scripts/db_test.py` → `db_check.py`, `cleanup_smoke_test.py` → `cleanup_smoke.py` (removes the `*_test.py` discovery hazard). |

---

## 8. Cleanup executed (2026-09-30, after this audit)

The owner approved and ran the audit's cleanup recommendations:

| Document / artefact | Verdict in §3 | Action taken |
|---|---|---|
| `llm/` (repo root) | DUPLICATE of `backend/models/documind-qa` | **deleted** (265,470,032 B `model.safetensors`, 0 code references) |
| `backend/CONTEXT.md` | STALE stub | **deleted** |
| `backend/orphaned_uploads_2026-09-28.zip` | orphaned, unreferenced | **deleted** (10,440,277 B) |
| `backend/evaluation/harness/evaluator.py` | dead code (F-1) | **deleted** (never importable, never imported, never executed) |
| `runbooks/README.md`, `migration-failure.md`, `database-failure.md` | KEEP, stale migration claim | **corrected** to the real `000`–`005` chain |
| 34 architecture records citing `backend/phase4f/...` | KEEP-HISTORICAL | left as written; translated by the new `PATH_MIGRATION.md` |

KEEP items in §3 were not touched. `backend/architecture/PATH_MIGRATION.md` was added as
the single translation layer for the historical phase-directory paths.

