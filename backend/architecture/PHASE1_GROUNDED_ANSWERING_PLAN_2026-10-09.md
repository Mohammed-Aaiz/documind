# DocuMind — Phase 1 Planning Package: Grounded Generative Answering

**Date:** 2026-10-09
**Status:** **PLANNING ONLY — not implemented, not authorized.**
**Operational agent:** COORDINATOR (investigation, planning, consolidation).
**Specialist review lenses (applied as review responsibilities, not run as separate agents):**
8 Software Architect · 10 Backend Architect · 11 Database Architect · 14 Security Architect ·
17 Backend Coding Specialist · 25 AI/ML Architect · 33 NLP Specialist · 35 LLM Engineer ·
36 RAG Engineer · 39 Model Evaluation · 41 Embeddings/Vector Search · 42 Knowledge Graph ·
43 AI Safety/Guardrails · 51 Test Architect · 53 Integration Testing · 57 AI Evaluation ·
58 Security Testing · 59 Code Review · 60 Debugging · 61 Reliability · 72 Application Security ·
75 Identity/Auth · 79 Documentation · 81 Architecture Documentation · 82 Codebase Knowledge ·
89 Database Optimization.

> This package changes no production code, tests, schema, migration, model, weights, `.env`,
> benchmark, or historical report. It starts no implementation. The architecture migration
> gate remains **NOT OPEN**. Where this plan needs a decision, it says so and stops.

---

## 1. Repository and baseline verification

Verified by reading the working tree on 2026-10-09. All required files exist:

| File | Result |
|---|---|
| `AGENTS.md` | OK |
| `DOCUMIND_PROJECT_CONTEXT.md` (Part II §50–§63) | OK |
| `CONTEXT.md`, `PRD.md`, `ARCHITECTURE.md`, `README.md` | OK |
| `backend/architecture/PHASE0_CLOSURE_2026-10-09.md` | OK |
| `backend/architecture/PHASE0_FAILURE_AUDIT_2026-10-09.md` | OK |
| `backend/architecture/phase4f_6/{PHASE4F6_ARCHITECTURE_AUDIT,ARCHITECTURE_DECISION_RECORD,NEXT_STAGE_RAG_EXECUTION_PLAN}.md` | OK |
| `backend/architecture/phase4f_6/decision/ARCHITECTURE_MIGRATION_GATE.md` | OK |
| `backend/phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl` | OK (sha `1166bf4f…50a41d0`, 182 examples) |

Baseline: branch `main` @ `6baaa2a`; Alembic head **`007`**; working tree 382 changed paths
(pre-existing). Provisioned models: `documind-qa` (DistilBERT extractive), `media-verification`
(ViT), `whisper/small`. **No generative/LLM dependency or model is present**
(`requirements.txt` has no LLM entry; `backend/models/` has none).

### 1.1 Discrepancies and facts that shape the plan

| # | Finding | Evidence | Consequence for Phase 1 |
|---|---|---|---|
| **D1** | **Two different span-selection rules exist.** Production uses `chat/qa_model.answer_question` (top-`n_best=20` start/end **probability product**, `max_answer_length=100`, offsets-mapped). `backend/answer_span.py` defines a **joint-logit** protocol (`select_joint_span`) used only by Phase 4F runners. | `chat/qa_model.py`; `answer_span.py` | The benchmarked protocol is **not** the production protocol. "Improved extractive QA" may be reachable by wiring an existing, already-tested selector — a small, localized change. |
| **D2** | **Compact table-row evidence is OFF by default** behind `DOCUMIND_TABLE_EVIDENCE` (kill switch, default off). | `chat/rag.py` (`TABLE_EVIDENCE_ENV`, default-OFF), `brain/adapters.py` | The Phase 0 corpus run had table evidence **disabled**; table failures cannot be attributed to that band. |
| **D3** | **Evaluation runners are not isolation/append-only safe.** `evaluation/runner.py` writes to a fixed `REPORTS_DIR = evaluation/reports` with no override, and the ablation runner writes `<prefix>_config.json` there; both use the production engine/session (`settings`), not a caller-supplied DSN. | `evaluation/runner.py` L41/270–306; `run_dual_path_ablation.py` L556/661–663 | Confirms the Phase 0 finding (F-07). Phase 1 experiments need the runner changes in §5 **before** measurement. |
| **D4** | `run_phase3d_upload_integration.py` hardcodes `…@localhost:5432/documind` (application DB); `.env` actually uses **55433**. | runner L47–50; `tests/fixtures/e2e_config.py` | Runner cannot be used safely for isolated evaluation as written. |
| **D5** | Documented test counts in `README.md`/old reports are stale (712/558); current collection is 904. | Phase 0 closure §5 | Do not quote historical counts. |
| **D6** | The gate's abstention rule keys on **exactly zero** confidence (a non-tuned boundary); QA confidence is **not calibrated** (correct answers occur at ~0.0001). | `brain/gate.py` docstring | Do **not** propose a confidence threshold as a solution — it was tried and rejected on measured evidence. |

Nothing in the supplied Phase 0 record contradicts the working tree; the discrepancies above
are internals the plan must respect.

---

## 2. Current request path (verified) and failure points

```text
POST /api/documents/upload                documents/routes.py
  → validation (type/size/magic)          documents/validation.py
  → storage (UUID filename)               storage/file_store.py
  → _process_document (sync, in-request)
      → extract_text (PDF/DOCX/TXT)       documents/processing.py
      → resolve_chunker_version           documents/chunking.py
      → _build_chunk_objects              documents/routes.py
      → embed_texts (MiniLM 384-d)        embeddings/model.py
      → parse_pdf + replace_document_structure (PDF)   documents/parser.py, documents/structure.py
      → replace_document_graph (chunk graph)           graph/service.py
      → status = READY                    documents/routes.py
POST /api/chat/ask                        chat/routes.py
  → Brain.process                         brain/__init__.py
      classify (keyword intent)           brain/classifier.py
      plan (fixed steps)                  brain/planner.py
      execute → retrieval_adapter         brain/executors.py, brain/adapters.py
          retrieve_chunks (pgvector)      chat/rag.py
          retrieve_dual_path (RRF 0.70/0.30, k=60; hops ≤ 2)  chat/rag.py
          _augment_with_structure (first 20 elements/doc, score 0)  brain/adapters.py
          [optional] table-row band, default OFF                 chat/rag.py
      context_adapter → build_qa_context (token budget = model window)  chat/rag.py
      qa_adapter → qa_model.answer_question (extractive DistilBERT)     chat/qa_model.py
      gate.evaluate (abstention/outcome)                         brain/gate.py
      response assemble                                          brain/response.py
  → reliability snapshot (reliability_logs)  reliability/routes.py
```

**Provenance boundaries.** Each `SourceOut` carries document/page/section/headingPath,
`retrievalPath` (semantic/structural/hybrid), `fusionScore`, `evidenceKind`
(chunk/structure_element/table_row), `structuralHops`, table `rowIndex`/`headerRepeated`.
`ReliabilityEvidence` carries `sourceCount` (supplied to QA), `retrievedSourceCount`,
`omittedSourceCount`, `contextBudgetTokens`, `contextUsedTokens`, `factualGrounded`,
`pathAgreement`, `pipelineVersion`. **Gap:** the response exposes what was *supplied* to QA but
not the *exact span* the model selected with its score per candidate; per-question
answer-context capture is therefore an evaluation gap (§5.5).

| Stage | Module | Contract in → out | Demonstrated failures (Phase 0) | Hypotheses | Tests | Phase 1 change needed? |
|---|---|---|---|---|---|---|
| Extraction | `documents/processing.py` | file → text blocks | none observed (12/12 docs extracted) | none | `tests/unit/documents/*`, `test_pdf_read_order` | No |
| Structural repr. | `documents/parser.py` | PDF → elements | table rows/cells not always emitted for evaluated PDFs (recorded audit) | row/cell extraction incomplete | `test_structured_extraction`, `test_table_rows` | Not for Phase 1 core (see §9) |
| Chunking | `documents/chunking.py` | elements → chunks | legacy default persists **null** section/heading metadata | structure-v2 helps | `test_phase3d_chunking` | No (schema-gated; out of scope) |
| Embedding | `embeddings/model.py` | text → 384-d | none observed | none | integration embeddings | No |
| Persistence | `documents/routes.py`, `graph/` | rows + graph | none observed | none | graph/storage tests | No |
| Retrieval | `chat/rag.py`, `brain/adapters.py` | query → ranked chunks+elements | 4/39 gold-evidence misses (corpus); element stream unranked at 0.70/0.30 | systematic recall gap | `test_structural_retrieval`, `test_fusion` | Only if §11 accepts retrieval work |
| Context construction | `chat/rag.py::build_qa_context` | chunks → token-budgeted context | evidence **was** in sources for 22/39 wrong answers ⇒ context admitted some evidence but the **answer was still wrong** | context omits the decisive sentence | `test_phase3d_context` | No (measure first) |
| Answer | `chat/qa_model.py` | context+question → span+score | 22/39 wrong with evidence present; over-wide/wrong-region spans; table/list/section 0 % EM (benchmark model-only) | selector/boundary, not knowledge | `test_qa_answer_reconstruction`, `test_answer_span` | **Yes — primary** |
| Abstention | `brain/gate.py` | evidence → outcome | model answers all 42 unanswerable; system gate abstained on the out-of-corpus question | gate precision/recall untuned | brain tests | Yes (guardrails) |
| Reliability | `reliability/` | snapshot row | counts are honest; no per-claim support | — | `test_table_row_reliability_api` | Extend for citations (§8) |

**Attribution rule held throughout:** an incorrect answer whose gold evidence *was* retrieved
is an **answer-stage** failure, not retrieval. Phase 0 measured 22/39 of these vs 4/39
retrieval misses.

---

## 3. Failure-to-fix matrix

| Failure | Earliest confirmed stage | Evidence / confidence | Candidate fix | Regression test | Required approval |
|---|---|---|---|---|---|
| F-01 no abstention on unanswerable (model-level) | answerability | Phase 0: 0/42; `gate.py` zero-confidence rule | add a **separate answerability/verification gate** with measurable precision/recall | gate seam + abstention tests | **ADR (Gate 2)** |
| F-02 table cell/row wrong | answer selection + representation | Phase 0: TABLE_CELL 16.7 %, TABLE_ROW 0 % EM; corpus `ts_1`,`tl_1` | table-aware selection; consider enabling the (default-off) table-row band **as an experiment** | table evidence seam tests | ADR (behavior change) |
| F-03 over-wide / wrong-region spans | answer selection (boundary) | corpus: `14` vs `14 watts`; `A Tundra torque wrench`; `3 kilograms.` | boundary normalization (units/punctuation/articles) + typed-span constraint | boundary unit tests | Class B (localized) |
| F-04 4/39 retrieval misses | retrieval | corpus evidence-recall 89.7 % | retrieval recall work (OUT of Phase 1 core) | retrieval seam test | ADR (Gate 1) |
| F-05 unranked element stream at 0.70/0.30 | retrieval/fusion | recorded + math | calibrate prior **after independent replication** | fusion test | **ADR (weights)** |
| F-06 legacy chunker null metadata | representation | recorded reachability audit | enable structure-v2 | chunker test | **ADR + schema** |
| F-07 runners not isolation-safe | evaluation infra | D3/D4 | §5 runner changes | runner unit tests | Class A (eval-only) |
| F-08 corpus abstention unmeasured | evaluation infra | Phase 0 closure §4.3 | attach unanswerable questions to the harness | harness test | Class A |
| F-09 OCR/math/cross-doc/marks absent | — | Phase 0 §9 | datasets + capabilities | — | **UNTESTED** (out of scope) |
| **F-10** production vs benchmarked selector differ | answer | D1 | wire/bench a single selector; decide which is production truth | selector equivalence test | Class B |
| **F-11** table-row band default OFF | retrieval/answer | D2 | evaluate it as a controlled experiment (flag on/off) | measurement runner test | Class A/B |

---

## 4. Architecture alternatives

**A. Existing extractive QA (baseline).** Production `qa_model.answer_question`. Cheap,
offline, already-integrated. Ceiling: 22/39 corpus answers wrong despite evidence;
0 % EM on table/list/section in the model-only benchmark; never abstains.
*Needed change: none (it is the control).*

**B. Improved extractive QA (Class B, low risk).**
- Answer-span **boundary constraints**: strip leading articles, trailing sentence punctuation;
  for numeric/unit questions prefer the value token (`14 watts`); forbid spans that cross a
  table row/column boundary; prefer the shortest span containing the maximum logit mass.
- Question-type-aware selection (numeric vs span vs list) — heuristic only.
- Optional: make `answer_span.select_joint_span` the production selector (currently only the
  Phase 4F runners) **after** an equivalence/quality check.
- Cost: no new model, no schema, no retrieval change; fully reversible.
- Expected: improves F-03 and some F-02; cannot fix F-01 (abstention) or completeness.

**C. Grounded generative answering (Class C).**
- Add an **additive**, locally-provisioned instruction model behind a router; DistilBERT stays
  the default extractive route.
- Prompt contract: answer **only** from numbered evidence blocks; emit answer + per-claim
  citation ids; emit `insufficient` when evidence does not support an answer; refuse
  instructions found inside document text (prompt-injection guard).
- Untested requirements: model availability/licence, RAM/VRAM, latency, context window,
  output stability, grounding rate. **No model is selected here** — selection is an experiment
  (§7) and a hardware measurement, and provisioning is an operator step.
- Expected: improves completeness/explanatory answers (F-04 category "long-context"); does
  **not** by itself fix span-boundary or table-selection failures, and can *introduce*
  unsupported claims if ungrounded.

**D. Controlled hybrid / fallback (Class C).**
- Route by question type + evidence signals: extractive for short factual/numeric spans
  (where it already works: NUMERIC 70 % EM model-only), generative for explanatory/multi-part,
  abstain when the evidence gate says insufficient.
- This is the architecture the evidence supports **if and only if** C is measured to beat B on
  its target categories without regressions elsewhere.

**Trade-offs and recommendation.** Evidence supports doing **B first** (cheap, addresses the
dominant confirmed failure F-03, no new infrastructure), measuring it, and only then
designing the **C/D** route as an additive, gated capability with a hardware/quality
evaluation. Generation is *not* assumed to improve metrics (§3 mission).

---

## 5. Evaluation infrastructure plan (must precede Phase 1 measurement)

Smallest safe changes (all **Class A — evaluation-only**, no production behavior):
1. **Explicit isolated DSN** — add an `--database-url`/env parameter to the evaluation runners
   so they can target `documind_integration` (or `DOCUMIND_INTEGRATION_DATABASE_URL`), reusing
   `tests/fixtures/integration_db.assert_isolated_target`.
2. **Identity guard before any destructive op** — call the existing guard first (already exists;
   wire it into the runners).
3. **Unique output directory** — `--out <dir>`; default `<archive>/phase1/<run_id>/`.
4. **No overwriting** — refuse to write if the target file exists (fail loudly), never
   silently replace a recorded report.
5. **Run manifest** — record model ids/checkpoint hashes, config, dataset version, git commit,
   protocol, timestamps, and the exact command for every run.
6. **Frozen benchmark preserved** — read-only; new diagnostic populations labelled separately.
7. **Unanswerable questions attached** to the correct harness (Phase 0 F-08).
8. **Per-question capture** — predictions, retrieved sources + ranks, answer context ids,
   outcome, reliability, and failure attribution, where safely possible.

7. **Reproducible commands** (planned):
```bash
cd backend
DOCUMIND_INTEGRATION_DATABASE_URL=postgresql+asyncpg://…/documind_integration \
  ./venv/Scripts/python.exe evaluation/experiments/run_<experiment>.py --out backend/evaluation/reports/<run_id>
```
`reports/` remains append-only: new runs write new files.

---

## 6. Dataset coverage matrix

| Capability | Present | Status |
|---|---|---|
| Direct factual | benchmark `DIRECT_SPAN` 24; `phase3d_corpus` | available |
| Table cell/row | benchmark `TABLE_CELL` 24 / `TABLE_ROW` 16; `table_evidence_*` | available |
| List / section | benchmark `LIST_ITEM` 20 / `SECTION_SPECIFIC` 16 | available |
| Numeric answers/units/punctuation | benchmark `NUMERIC` 20 (value extraction) | available (no calculation) |
| Long-context / multi-chunk | benchmark `LONG_CONTEXT` 10 / `MULTI_CHUNK` 10 | available |
| Unanswerable | benchmark 42 | available (harness attachment pending F-08) |
| Explanatory / completeness | — | **MISSING — UNTESTED** |
| Multi-document | — | **MISSING — UNTESTED** |
| Conflicting evidence | — | **MISSING — UNTESTED** |
| Exam 5/10/15 marks | — | **MISSING — UNTESTED** |
| Calculation / unit correctness | — | **MISSING — UNTESTED** |
| Scanned / OCR | — | **MISSING — UNTESTED** |
| Charts / figures | — | **MISSING — UNTESTED** |
| Entity-relation multi-hop | `structure_discriminating_v1` multi-hop subset (8) | partial, no entity ground truth |

Collection specs for the missing sets are recorded in
`PHASE0_CLOSURE_2026-10-09.md` §9 (capability → sources → annotation → metrics → QC →
coverage → privacy/licensing) and are carried forward unchanged; Phase 1 needs the
**explanatory/completeness** set first (to measure C's target benefit) and the **unanswerable
attachment** (F-08).

---

## 7. Evaluation protocol

**Design.** Controlled comparison on **the same corpus version and retrieval configuration**;
retrieval held fixed while answer stage varies (so a change is attributed correctly).

| Arm | Description |
|---|---|
| B0 | Baseline extractive QA (production `qa_model.answer_question`) |
| B1 | Improved extractive (boundary constraints, §4B) |
| C | Grounded generative (additive, local) |
| D | Hybrid router (B1 for factual/numeric, C for explanatory) |

**Metrics and formulas** (each with dataset, denominator, method, threshold):

| Metric | Formula / method | Dataset | Threshold (proposed, owner to confirm) |
|---|---|---|---|
| EM | normalised exact match | labelled corpora (answerable) | B1 ≥ B0 − 0; C/D ≥ B0 − 0 |
| token-F1 | token-set F1 | same | B1 ≥ B0; C/D ≥ B0 |
| Numeric/unit correctness | numeric equality within tolerance + unit match | numeric set | C/D ≥ B0 |
| Completeness | rubric coverage of required points | explanatory set (to build) | C > B0 (needs set) |
| Citation correctness | emitted citation ids ⊆ supplied source ids; claim maps to cited source | all arms | C/D = 100 % structural validity |
| Unsupported-claim rate | claims with no supporting evidence ÷ claims | all arms | C/D ≤ B0 |
| Evidence Recall@k | gold-evidence in top-k ÷ answerable | labelled corpora | report only (no change) |
| Answer-context availability | gold evidence present in the **QA context** | per-question capture (§5.8) | report only |
| Abstention precision/recall | on unanswerable/answerable sets | benchmark + harness | precision ≥ 0.8, recall ≥ 0.5 (proposed) |
| False-answer rate | answered unanswerable ÷ unanswerable | benchmark/harness | ≤ 0.2 |
| Latency (e2e, answer, model load) | wall clock, warmed | smoke set | **UNAVAILABLE until measured** |
| Peak memory | process RSS peak | same | **UNAVAILABLE until measured** |

Unavailable metrics are labelled unavailable — never fabricated. No statistical-improvement
claim without a pre-registered comparison (paired bootstrap over per-question results).
**Frozen benchmark is never merged** with new diagnostic populations.

---

## 8. Security and reliability plan

| Threat | Mitigation | Regression test | Class |
|---|---|---|---|
| Prompt injection in uploaded documents | treat document text as data only; delimit/quarantine instruction-like content; never execute document instructions | adversarial-document test | C |
| Cross-user leakage | retrieval already user-scoped; keep generative context strictly to retrieved, user-owned chunks | isolation test (exists) | C |
| Unauthorized source retrieval | no new retrieval path; generative route receives only the existing context | seam test | C |
| Sensitive content exposure in logs | never log document text/answers; log ids + sizes only | log-scan test | A/C |
| Unsupported/malicious model output | citation-required prompt + post-hoc grounding check; strip HTML/control chars | output-validity test | C |
| Model-serving resource exhaustion | single shared instance, timeouts, bounded input/context, rate-limit at route | timeout/overload test | C |
| Dependency/model-artifact security | pinned versions + hashes in a run manifest; operator-provisioned, local-only | manifest test | C |
| Unintended external calls | force offline flags; forbid external APIs | network-guard test | C |

Reliability rules to define (no confidence-based proof of correctness): no evidence →
abstain; conflicting evidence → report both with citations, do not silently pick; weak
retrieval → PARTIAL/abstain; malformed model output → reject and fall back or abstain; model
unavailable/timeout → honest 503 (exists); answerability decided by an **independent** gate
(ADR DECIDED). Do not treat self-reported model confidence as correctness.

---

## 9. Implementation sequence (smallest safe order)

| Step | Change | Class | Depends on | Files likely to change | Tests | Rollback | Approval |
|---|---|---|---|---|---|---|---|
| 0 | Evaluation runner isolation: isolated DSN, identity guard, unique out dir, no-overwrite, run manifest, per-question capture, unanswerable attachment | **A** | — | `evaluation/runner.py`, `evaluation/experiments/run_dual_path_ablation.py`, (new) `evaluation/manifest.py` | new runner unit tests | revert files | Coordinator/owner (eval-only) |
| 1 | Corpus harness with unanswerable questions + explanatory set scaffold | **A** | 0 | `evaluation/datasets/*`, `evaluation/` | harness tests | revert | owner |
| 2 | Answer-boundary normalization + typed-span selection (extractive) | **B** | 0,1 | `chat/qa_model.py` (or a new `chat/answer_policy.py`), `answer_span.py` | boundary unit tests; corpus re-run | flag off → baseline | ADR-light (behavior change) |
| 3 | Measurement: B0 vs B1 on same corpus version | **A** | 2 | reports only (new dir) | — | — | owner |
| 4 | Generative route **design + hardware/quality model evaluation** (no selection yet) | **C** (design) | 3 | docs + eval harness | — | — | **ADR waiver (§15/§17)** |
| 5 | Additive grounded generative route behind a router (default off) | **C** | 4 | `chat/`, `brain/adapters.py`, `requirements.txt` (BACKEND_AGENT), new `chat/generate.py` | seam + grounding + injection + timeout tests | route disabled → baseline | **ADR + gate** |
| 6 | Hybrid router (B1/C) with abstention | **C** | 5 | `brain/router.py`, `brain/gate.py` (integration) | router tests | flag off | **ADR (Gate 2)** |
| 7 | Retrieval/criteria work (recall, weight calibration, structure-v2) | **C/D** | measured evidence | `chat/rag.py`, `documents/chunking.py`, migrations | dedicated tests | flags/migration down | **ADR (Gate 1/3)** |

`AGENTS.md` ownership applies: `chat/**` (except `models.py`), `brain/**`, `graph/**` (except
`models.py`) → AI_AGENT; `documents/**` (except `models.py`), `config.py`, `requirements.txt` →
BACKEND_AGENT; `migrations/**`, `*/models.py` → DATABASE_AGENT; `tests/**` → TEST_AGENT;
`evaluation/**`, `phases/**` → EVALUATION_AGENT; `architecture/**` + root docs → COORDINATOR.

---

## 10. Phase 1 acceptance criteria (measurable, no unsupported claims)

1. **Evaluation infra:** the isolated-DSN runner exists, refuses the application DB, writes to
   a unique directory, refuses to overwrite, and records a run manifest; a full corpus run
   reproduces the same metrics on repeat (deterministic).
2. **B1 (extractive improvements):** on the same corpus version as baseline, token-F1 **does
   not decrease**, EM **does not decrease by >1 point**, and the answer-boundary failure
   cases from Phase 0 §4.3 (`14` vs `14 watts`; trailing punctuation; over-wide spans) are
   fixed with regression tests.
3. **C (generative), if authorized:** 100 % of emitted citations reference supplied source
   ids; unsupported-claim rate ≤ B0; abstains on the unanswerable set with precision ≥ 0.8;
   no user-isolation regression; honest timeout/unavailable handling; measured latency and
   peak memory recorded.
4. **Guardrails:** no unanswerable question is answered as SUCCESS in the gated path beyond the
   false-answer threshold; no confidence value is presented as correctness.
5. **Non-regression:** existing suite remains **898 passed / 6 skipped / 0 failed** (or better),
   benchmark unchanged, head unchanged, no schema change without an ADR.
6. **Untested capabilities remain labelled UNTESTED** (exam marks, calculation, scanned/OCR,
   cross-document, entity multi-hop, charts).

---

## 11. Proposed ADR (DRAFT — do not activate or commit)

> **ADR-XXX: Additive grounded generative answering route (PROPOSED)**
> **Status:** Proposed — not decided. Requires owner approval; the migration gate must open or
> a written waiver recorded.
> **Context:** Extractive QA is the ceiling (22/39 corpus answers wrong with evidence
> present; 0 % EM model-only on table/list/section; no abstention). The project forbids
> external model APIs and requires the trained DistilBERT model by default.
> **Decision (proposed):** add an **additive** generative answering route that (a) runs only on
> **locally provisioned** weights with offline flags, (b) receives **only** retrieved,
> user-owned evidence, (c) must emit per-claim citations, (d) abstains when unsupported, and
> (e) is **off by default** with route-disabled rollback. DistilBERT remains the default
> extractive path.
> **Alternatives:** B0 (extractive only), B1 (improved extractive), D (hybrid router).
> **Consequences:** new dependency + model artifact (operator-provisioned); new failure modes
> (hallucination, injection, latency); requires Gate 2 (answerability), a hardware measurement,
> and an evaluation on a new explanatory dataset.
> **Not decided here:** the specific model. Selection is an experiment (§7) plus a
> hardware/licence measurement; **no model is downloaded or chosen in this task.**

---

## 12. Final recommendation

**First implementation slice (do this first): Step 0 — evaluation-infrastructure hardening
(Class A).** Rationale: every Phase 1 claim is unmeasurable until runners are isolation-safe,
append-only, and capture per-question evidence; it is low-risk, changes no product behavior,
and unblocks B0/B1/C/D comparisons. **Then Step 2 (answer-boundary + typed-span, Class B)**,
because it attacks the single dominant *confirmed* failure (F-03, 22/39) with no new
infrastructure and a clean rollback.

**Explicitly out of scope for Phase 1:** retrieval-weight changes, structure-v2 default or any
schema change, entity-relation GraphRAG, OCR, mathematical reasoning, exam-mark engine, chart
understanding, and any external model API.

---

## 13. Verification performed for this package

- Confirmed all §4-mandatory files exist (table in §1).
- Confirmed baseline: `main` @ `6baaa2a`, head `007`, benchmark sha unchanged, 382 changed paths.
- Confirmed **no** LLM dependency/model present.
- Confirmed the runner isolation/report-writing finding by reading
  `evaluation/runner.py` (fixed `REPORTS_DIR`, no override) and `run_dual_path_ablation.py`
  (writes `<prefix>_config.json`; uses production settings).
- Confirmed the gate's zero-confidence abstention rule and the two span-selection rules.
- No test, evaluation, migration, or write against the application database was executed in
  this task (read-only inspection only).
