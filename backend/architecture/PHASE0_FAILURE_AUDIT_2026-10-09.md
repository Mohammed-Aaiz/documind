# DocuMind — Phase 0: Failure Audit and Baseline Evaluation

**Date:** 2026-10-09
**Operational agent:** COORDINATOR (audit + consolidation).
**Specialist review lenses:** 8 Software Architect, 25 AI/ML Architect, 34 Multimodal AI,
35 LLM Engineer, 36 RAG Engineer, 39 Model Evaluation, 41 Embeddings/Vector Search,
42 Knowledge Graph, 51 Test Architect, 57 AI Evaluation, 58 Security Testing,
61 Reliability, 79 Documentation, 81 Architecture Documentation, 82 Codebase Knowledge.
**Nature:** audit and evaluation only. No production source, schema, migration, model
weight, `.env`, or frozen-benchmark change was made. No commit. No push.

> Companion to `DOCUMIND_PROJECT_CONTEXT.md` Part II (§50–§63), which defines the
> capability status labels used here. This document is new append-only evidence; no
> existing architecture evidence file was modified.

---

## 1. Executive summary

- The backend behaves as its own tests describe: **897 passed, 7 skipped, 0 failed** across
  unit (623), integration (274 passed / 1 skipped) and e2e (6 skipped, needs a live server).
- The frozen benchmark is **intact** (182 examples, SHA-256 verified) and **safe to execute
  read-only without a database** (each example carries its own context).
- A **fresh** run of the *production* QA model (`chat.qa_model.answer_question`, production
  `inference_config`, no retrieval/DB) over the frozen benchmark gives **EM 15.71 % / token-F1
  38.02 % on the 140 answerable examples**, and **answers all 42 unanswerable examples**
  (0 % abstention).
- Failure is **not uniform**, and is **not a single-model problem**:
  - `NUMERIC` extraction is **strong at the model level** (EM 70 %, F1 88.5 %).
  - `TABLE_CELL` is partial (EM 16.7 %), `TABLE_ROW` is 0 % EM (F1 44.8 %).
  - `LIST_ITEM`, `SECTION_SPECIFIC`, `LONG_CONTEXT` are **0 % EM**; `MULTI_CHUNK` 10 %.
  - `DIRECT_SPAN` is only 12.5 % EM despite high overlap — **span-boundary/selection**, not
    missing knowledge (`142.6 million` predicted as `$142.6 million`).
- The dominant answer-stage defects are **span selection/boundary** (too-wide or wrong-region
  spans) and **structural representation** (tables/lists/sections), matching the lecturer's
  "short spans or nearby words" complaint. Abstention is a **system** gap, not a model gap.
- Retrieval: the persisted structure-element stream is **unranked** and cannot enter
  production top-k at weights 0.70/0.30, and dual-path retrieval showed **no measured quality
  gain** on the corpora tested. OCR, chart understanding, document-manipulation detection,
  mathematical reasoning and exam-mark answers are **not implemented / not evaluable**.
- **Phase 0 exit criteria are NOT MET**: a genuine end-to-end production-pipeline evaluation
  (real PostgreSQL + pgvector + retrieval + gate) was not performed, and the lecturer-specific
  datasets (exam marks, calculation, scanned, cross-document) do not exist.

---

## 2. Current architecture and verified capability matrix

Per `DOCUMIND_PROJECT_CONTEXT.md` Part II §53 and §55 (unchanged), re-verified against the tree:

- Frontend React/TS/Vite at repo-root `src/`; FastAPI backend at `backend/`.
- PostgreSQL + pgvector (production vector path); SQLAlchemy async; Alembic linear chain
  `000`–`007` (**verified head `007_add_table_rows.py`**).
- `all-MiniLM-L6-v2`, 384-dim embeddings; local DistilBERT extractive QA
  (`backend/models/documind-qa`, weights sha256 `cb9f1dde…`).
- Dual-path retrieval with RRF `semantic 0.70 / structural 0.30`, `k=60` (`backend/chat/rag.py`).
- **Document-native structure graph** (chunk graph + structure-element graph) — **not** an
  entity–relation knowledge graph.
- Deterministic keyword-intent Brain orchestrator (no LLM agent).
- Reliability/provenance snapshot in `reliability_logs`.
- Local image media verification (ViT) and local voice (Whisper STT, gTTS TTS).

No discrepancy was found between the production code executed here and the Part II
capability matrix. One documentation discrepancy is re-confirmed: `CONTEXT.md`/`README.md`
historic test counts (712) are stale — see §7.

---

## 3. Repository and environment baseline

| Item | Value (verified 2026-10-09) |
|---|---|
| Branch / HEAD | `main` @ `6baaa2a fix: stabilize backend runtime and database migrations` |
| Working tree | pre-existing dirty state: **382 changed paths** before and after this audit (no change from the audit itself) |
| Protected-frozen dir | `backend/architecture/` is untracked (`??`) as before; nothing in it modified |
| Python | 3.11.0 in `backend/venv` |
| Migration head | `alembic heads` → **`007 (head)`** |
| QA model | `backend/models/documind-qa` present (config, safetensors, tokenizer, `inference_config.json`) |
| Media model | `backend/models/media-verification` present |
| Voice model | `backend/models/whisper/small` present |
| Test DB | SQLite in-memory (`tests/conftest.py`), **isolated from the application database** |
| Secret exposure | none; `.env` was not read or printed; only `.env.example` (template) inspected |

---

## 4. Test execution results (actual)

Collection: `pytest tests --collect-only -q` → **904 collected in 12.02 s**.
Discovery is constrained by `pytest.ini` (`testpaths = tests`).

| Group | Command | Result | Exit | Wall |
|---|---|---|---|---|
| Unit | `python -m pytest tests/unit -q` | **623 passed**, 1 warning | 0 | 35.28 s |
| Integration | `python -m pytest tests/integration -q` | **274 passed, 1 skipped** | 0 | 213.27 s |
| E2E | `python -m pytest tests/e2e -q` | **6 skipped** (needs a live server) | 0 | 15.15 s |
| Totals | unit+integration+e2e | **897 passed, 7 skipped, 0 failed** (= 904) | 0 | — |

Notes:
- The one integration skip and the six e2e skips are **environmental** (no live server),
  not product failures. They are reported as skipped, not passed.
- The very first `pytest tests -q` attempt exceeded a 300 s window; the suite was therefore
  run in the three groups above, which together cover all 904 collected tests.
- The SQLite suite does **not** exercise pgvector, the real QA model, voice, or media
  verification end to end.

---

## 5. Frozen benchmark integrity and execution

### 5.1 Integrity (verified)

- Path: `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl`
- SHA-256: `1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0` — **matched**.
- Lines/examples: **182**; manifest records **140 answerable / 42 unanswerable**, 6 documents,
  9 category labels. Content unchanged; the audit only read the file.

### 5.2 Safe execution performed (read-only, no DB)

The benchmark rows are self-contained (each carries `question`, `context`, `answer`), so the
**answer stage** can be measured with no retrieval and no database. A throwaway stdin script
(in `/tmp`, not in the repository) called the **production** function
`chat.qa_model.answer_question` on all 182 rows with the model forced offline
(`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`), using the **production** `inference_config`
(`max_input_length=384`, `max_answer_length=100`, `n_best=20`). EM = normalised exact match;
F1 = token-set F1 (same definitions as the recorded Phase 4F protocol).

**Measured result — production QA model, frozen benchmark contexts, answer stage only:**

| Metric | Value | Denominator |
|---|---:|---|
| EM (answerable) | **15.71 %** | 140 |
| Token-F1 (answerable) | **38.02 %** | 140 |
| EM (all 182) | 12.09 % | 182 |
| Token-F1 (all 182) | 29.24 % | 182 |
| Non-empty answers (answerable) | **100.0 %** | 140 |
| Spurious answers on unanswerable | **42 / 42 = 100 %** | 42 |
| Spurious as share of all | 23.1 % | 182 |
| Inference time (CPU) | 15.7 s | 182 |

Category breakdown (answerable):

| Category | n | EM % | F1 % |
|---|---:|---:|---:|
| NUMERIC | 20 | **70.0** | 88.5 |
| TABLE_CELL | 24 | 16.7 | 23.2 |
| DIRECT_SPAN | 24 | 12.5 | 48.0 |
| MULTI_CHUNK | 10 | 10.0 | 18.3 |
| TABLE_ROW | 16 | 0.0 | 44.8 |
| LIST_ITEM | 20 | 0.0 | 18.9 |
| SECTION_SPECIFIC | 16 | 0.0 | 22.9 |
| LONG_CONTEXT | 10 | 0.0 | 19.8 |

Interpretation and limits: this measures the **answer stage only** against gold context. It is
**not** an end-to-end score (production retrieval/context construction can drop the correct
evidence, so end-to-end ≤ this unless retrieval is perfect), and it is **not** a generalisation
result (the benchmark's provenance notes training-set overlap). It is directly comparable to
the recorded production checkpoint `A0`; it is **not** protocol-identical to the recorded F2
run (different `max_answer_length`), so it must not be quoted against those numbers.

### 5.3 Recorded baselines (cited, not re-run)

- `MODEL_40MIN_EVALUATION.md` (2026-09-28, recorded): F2 checkpoint answerable EM 2.9 % / F1 19.7 %
  pre-decoder-fix; **A0 ungated EM 5.0 % / F1 24.4 %**; both **0/42 abstention**, spurious 42/42;
  `null_score` AUC (unanswerable vs answerable) **0.430**; confidence AUC (correct vs incorrect)
  0.811. Its own provenance note records that the decoder fix later raised F2 answerable EM
  2.86 → 14.29 % — consistent with the fresh 15.71 % measured here.
- `a0_benchmark_v1.json` (recorded, harness provenance UNVERIFIED): EM 2.1 / F1 12.0 at a
  **gated** operating point — abstention 64.3 % on unanswerable **but 55.7 % false abstention**
  on answerable (78/140 discarded).

### 5.4 Blocker for the *full-pipeline* benchmark run

Executing the benchmark through the **production request path** (`/api/chat/ask`: retrieval →
context → QA → gate) requires a reachable PostgreSQL + pgvector database with the benchmark
corpus ingested and an isolated evaluation user. That was **not performed** because it cannot
be established from the tree alone that a target database is isolated from the application
database, and the existing production-aligned evaluator
(`backend/evaluation/experiments/run_dual_path_ablation.py`) ingests and tears down a dedicated
eval user (`ablation_eval@test.local`) but still requires a live PostgreSQL + pgvector stack.
Proposed safe method: a dedicated evaluation database/instance with its own URL, benchmark
corpus ingested under a scoped eval user, run the production `brain.adapters` path, and record
per-question evidence/ranking. This is a Phase 1 measurement-infrastructure task.

---

## 6. Failure inventory and attribution

Confidence labels: **confirmed** (observed directly), **strongly supported** (multiple
recorded sources), **tentative**, **unknown**. "Stage" = earliest pipeline layer where the
failure is demonstrable.

| ID | Category | Test case | Expected → Actual | Earliest failing stage | Root cause / hypothesis | Confidence | Smallest fix | Regression test | Change class |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | I | 42 unanswerable | abstain → **42/42 answered** | Answer/abstention | Answerability not separated from extraction; model cannot abstain | **confirmed** | Route to a separate answerability gate | gate seam test | ADR (Gate 2) |
| F-02 | B | TABLE_CELL/ROW | correct cell → **16.7 % / 0 % EM** | Answer selection + representation | Table not represented as row/cell for the model; span grabs headers/adjacent columns | **confirmed** | Row/cell-aware evidence + typed span | table seam test | ADR + schema |
| F-03 | E | LIST_ITEM | correct item → **0 % EM** | Answer selection | Wrong region within list; no list-item target | **confirmed** | List-aware retrieval/selection | list seam test | ADR |
| F-04 | E | SECTION_SPECIFIC | heading → **0 % EM** | Answer boundary | Span too wide (heading + following text) | **confirmed** | Answer-boundary constraint | unit boundary test | model/answer |
| F-05 | D/E | LONG_CONTEXT, MULTI_CHUNK | correct value → **0 % / 10 % EM** | Evidence assembly / multi-hop | Wrong region across evidence; no synthesis | **confirmed** | Bounded multi-evidence assembly | multi-evidence test | ADR |
| F-06 | A/G | NUMERIC | correct value → **70 % EM**, 6/20 over-wide | Answer boundary | Extraction works; boundary/selection errors remain | **confirmed** | Typed/constrained span | numeric boundary test | model/answer |
| F-07 | A | DIRECT_SPAN | `142.6 million` → `$142.6 million` | Answer boundary | Span boundary includes currency/prefix | **confirmed** | Boundary post-condition | boundary test | model/answer |
| F-08 | R | structure-element ranking | element in top-k → **never at 0.70/0.30** | Retrieval/fusion | Mathematically impossible: `0.30/61 = 0.004918` < `0.70/65 = 0.010769` | **confirmed** | Calibrate structural prior **only after replication** | fusion test | ADR (weights) |
| F-09 | R | element stream | ranked contribution → **unranked, first 20/doc, score 0** | Evidence selection | Elements appended post-top-k, not candidates | **strongly supported** | Make elements query-conditioned candidates | retrieval seam test | architecture |
| F-10 | C | chunk metadata | section/heading metadata → **0/46 chunks persisted** | Chunking/representation | Production default chunker is `legacy` (char-based), metadata null | **strongly supported** | Enable `structure-v2` (**schema change**) | chunker test | ADR + schema |
| F-11 | R | A vs C ablation | benefit → **null** on production config (5–7× latency) | Retrieval | Structure signal too weak on the corpora tested | **strongly supported** | Advance only with independent replication | — | ADR |
| F-12 | H | scanned pages | OCR → **not implemented** | Extraction | No OCR library; PyMuPDF text-only | **confirmed** | OCR adapter (separate phase) | OCR fixture test | ADR |
| F-13 | H | charts/figures | interpretation → **not implemented** | Extraction/vision | No chart model | **confirmed** | Visual-region phase | — | ADR |
| F-14 | F | document integrity | tamper detection → **not implemented** | — | Media verification is a separate image classifier | **confirmed** | Separate integrity phase | — | ADR |
| F-15 | G | calculation | solve → **not implemented** | Reasoning | Only value extraction tested; no calculator/symbolic path | **confirmed** | Tool-assisted math path | numeric suite | ADR |
| F-16 | F | exam marks 5/10/15 | evaluate → **no dataset/rubric** | Evaluation | No labelled marks dataset | **confirmed (gap)** | Create the dataset + rubric | — | BLOCKED |
| F-17 | C/D | cross-document / entity multi-hop | multi-hop → **no knowledge graph; cross-doc questions absent** | Representation/retrieval | Document-native graph only; no entity/relation extraction | **confirmed** | Phase 5 GraphRAG | multi-hop suite | ADR |
| F-18 | Eval | unsupported-answer denominator; A0/A1/A2 harness provenance | — | Evaluation infrastructure | `unsupported_answer` denominator bug (superseded); A0/A1/A2 provenance UNVERIFIED | **strongly supported** | Freeze a versioned suite | metric tests | test/eval |
| F-19 | Env | e2e | browser flow → **6 skipped** | Environment | No live server during audit | **confirmed (environmental)** | Run e2e on a live isolated server | — | infra |

Symptoms aggregated under one cause are intentionally not counted as independent failures
(e.g. F-04/F-05 share the "span too wide / wrong region" boundary mechanism; F-02/F-03 share
structural representation).

---

## 7. Dataset and evaluation coverage gaps

| Lecturer requirement | Available now | Gap |
|---|---|---|
| Direct factual | 24 `DIRECT_SPAN` (+ structure corpora) | boundary errors limit score |
| Tables / layout | 24 `TABLE_CELL`, 16 `TABLE_ROW`; `table_evidence_*` reports | no chart fixture; row/cell not represented for the model |
| Multi-document | **none** | no cross-document / contradictory-source dataset |
| Multi-hop | 10 `MULTI_CHUNK`; `structure_discriminating_v1` multi-hop subset | no entity-relation ground truth |
| Completeness / explanatory | `LONG_CONTEXT` (10), `SECTION_SPECIFIC` (16) | no rubric for completeness |
| Exam-style 5/10/15 | **none** | dataset + objective rubric required |
| Mathematics (calculation) | 20 `NUMERIC` (value extraction) | no calculation/unit-validation fixtures |
| OCR / scanned / charts | **none** | scanned + chart fixtures and an OCR capability required |
| Unanswerable / reliability | 42 unanswerable | gate-threshold stability population small |

Metric gaps: no end-to-end (retrieval→answer) benchmark run was recorded in this audit;
`Recall@k`/`nDCG` exist only in the separate structure corpora; completeness, source-attribution
and calculator correctness have **no** measurement harness.

---

## 8. Highest-priority failure categories

1. **Abstention / reliability (I)** — 0 % abstention at the model level; the recorded gate
   trades 55.7 % false abstention for 64.3 % unanswerable abstention. Gate 2 unmet.
2. **Structural representation & selection (B/E)** — tables, lists, sections ~0 % EM.
3. **Answer span boundary/selection (A/E)** — direct spans and numerics fail on boundaries.
4. **Multi-evidence / multi-hop assembly (D/E)** — no effective synthesis; no entity graph.
5. **Untested capabilities (F/G/H)** — OCR, charts, calculation, exam marks: no dataset ⇒ no score.

---

## 9. Proposed minimal fixes (ranked: impact → cost → risk → evidence strength)

| # | Fix | Impact | Cost | Risk | Evidence strength | Gate |
|---|---|---|---|---|---|---|
| 1 | Build the **end-to-end evaluation harness** on an isolated DB (production path) | High | Medium | Low | gap-filling | none (eval only) |
| 2 | Constrain **answer span boundaries** (typed values, boundary post-conditions) | High | Low | Low | strong (F-06/F-07) | model/answer review |
| 3 | Address **table/list/section representation + selection** | High | High | Medium | strong (F-02/F-03/F-04) | ADR + schema |
| 4 | Calibrate the **answerability gate** (Gate 2) with a pre-registered stable threshold | High | Medium | Medium | strong (F-01) | ADR (Gate 2) |
| 5 | **Structural prior calibration** (0.50/0.50) — only after independent replication | Medium | Medium | Medium | positive but not replicated (F-08/F-11) | ADR (weights) |
| 6 | Phase 1 **grounded generative answering** behind a gated, additive route | High | High | Medium | roadmap (F-04/F-05) | ADR (§15/§17 waiver) |
| 7 | OCR / math / GraphRAG / integrity | High | High | High | roadmap | separate phases |

Do **not** change production retrieval weights, top-k, chunker, or QA behaviour as part of
this audit; every item above that touches those requires an approved ADR and gate review.

---

## 10. Metrics obtained vs unavailable

**Obtained (this audit):** test pass/fail/skip counts; collection count; frozen-benchmark
integrity; EM and token-F1 (answerable and all) for the production QA model on the frozen
benchmark; per-category EM/F1; abstention/spurious counts; answer-stage CPU latency (15.7 s).

**Available only as recorded (cited, not re-run):** recall@K / precision@K / MRR / nDCG@K on
the structure corpora (A/B/C/D ablation), gate/margin statistics, AUC values.

**Unavailable:** end-to-end retrieval→answer metrics on the production path; completeness and
source-attribution scores; calculator/unit correctness; OCR/chart accuracy; exam-mark scores;
peak RAM/VRAM. Each requires the annotation or instrumentation named in §7–§8.

---

## 11. Files created / modified, and Git status

- **Created:** `backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md` (this file).
- **Modified:** `DOCUMIND_PROJECT_CONTEXT.md` — one pointer line added to Part II §64.
- **Temporary (outside the repository):** `/tmp/p0_unit.log`, `/tmp/p0_integration.log`,
  `/tmp/p0_benchmark.log`, `/tmp/p0_benchmark_predictions.json`.
- **Protected artifacts (verified unchanged after the audit):**
  - benchmark `qa_benchmark_v1.jsonl` sha256 `1166bf4f…50a41d0`, 182 lines;
  - QA weights `backend/models/documind-qa/model.safetensors` sha256 `cb9f1dde…`;
  - media weights `backend/models/media-verification/model.safetensors` sha256 `88ac0939…`;
  - Alembic head `007`;
  - working-tree changed-path count **382 before and after** (no tracked change introduced
    by this audit); `.env` untouched.
- No production module, schema, migration, model, or evaluation benchmark was modified.

---

## 12. Architecture decisions still requiring approval

1. Answerability gate design + threshold (ADR Gate 2).
2. Production RRF weight calibration (only after independent replication, ADR Gate 1/weights).
3. Structure-v2 chunker as production default and any parent/child persistence (schema; ADR).
4. Table/list/section-aware retrieval and answer handling (schema + seams; ADR).
5. Additive local generative route (waiver of §15/§17; ADR).
6. OCR / chart / document-integrity scope (separate phase; ADR).
7. Knowledge-graph / entity–relation GraphRAG schema and provenance (Phase 5; ADR).
8. Evaluation-database isolation policy for destructive-capable harnesses (infra).

---

## 13. Phase 0 exit criteria

| Criterion | Status |
|---|---|
| Architecture and capability claims checked against implementation | MET |
| Baseline test and benchmark status recorded accurately | MET |
| Highest-priority failures have reproducible evidence or are marked unverified | MET |
| Failure causes attributed to pipeline stages with confidence | MET (answer stage confirmed; retrieval/gate from recorded evidence) |
| Evaluation gaps documented | MET |
| Fixes ranked and linked to regression tests | MET |
| Gated decisions identified | MET |
| Protected artifacts unchanged | MET |
| **Genuine end-to-end production-pipeline evaluation** | **NOT MET** — needs an isolated PostgreSQL + pgvector stack (Phase 1 infra) |
| **Lecturer-specific datasets (exam marks, calculation, scanned, cross-document)** | **NOT MET** — do not exist |

**Phase 0 is INCOMPLETE.** The blocker is the absence of an isolated, database-backed
end-to-end evaluation harness and the lecturer-specific datasets; both are scoped in §14.

---

## 14. Proposed Phase 1 scope

1. **Measurement infrastructure first:** a versioned evaluation suite plus an isolated
   PostgreSQL + pgvector evaluation instance that runs the real production request path
   (retrieval → evidence → QA → gate) with per-question evidence and ranking recorded.
2. **Datasets:** exam-mark (5/10/15) with rubric; calculation/unit-validation; scanned/OCR;
   cross-document and multi-hop entity; each kept separate from the frozen benchmark.
3. **Then feature work** per the roadmap: grounded generative answering behind a gated,
   additive route — informed by the answer-stage evidence here (boundary/selection and
   structural representation dominate; generation alone is not the only gap).

---

## 15. Limitations, skipped tests, timeouts, environmental blockers

- The full `pytest tests -q` run exceeded a 300 s window once; it was completed as three
  groups (unit/integration/e2e) that cover all 904 collected tests. This is a throughput
  limitation, not a failure.
- 7 tests skipped: 1 integration + 6 e2e (no live server) — environmental.
- SQLite test suite does not exercise pgvector, the real QA model, voice, or media
  verification end to end.
- The benchmark was executed **answer-stage only**; no end-to-end run (see §5.4, §13).
- The fresh benchmark measurement is on a population with training overlap (per the frozen
  benchmark's provenance notes) and is **not** a generalisation claim.
- Docker runtime remains unverified (no Docker engine on the host).
